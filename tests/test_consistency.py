"""Cross-account consistency: the same project shows the same data to every account and on every page.

For each project the checks compare what members, the instructor and the coordinator receive from
the project page, the dashboard cards, the course group cards, the task list, the report, the peer
tab and the timeline. Any difference means two screens would disagree.
"""
import pytest
from test_workflow import app, template, Client, MA, TH, GV, COORD
from app.models import *
from app.models.academic import *


def facts(c, pid):
    """Everything a viewer can see about one project, normalised for comparison."""
    p = c.req(f'/projects/{pid}')
    tasks = c.req(f'/projects/{pid}/tasks?page_size=100')['items']
    report = c.req(f'/workflow/projects/{pid}/report')
    peer = c.req(f'/workflow/projects/{pid}/peer')
    active = sorted((m['user_id'], m['role']) for m in p['members'] if m['status'] == 'active')
    return {
        'name': p['name'], 'team': p['team_name'], 'status': p['status'],
        'assignment': (p['assignment_id'], p['assignment']['title'], p['assignment']['due_at']), 'course': p['course_id'],
        'progress': (p['progress']['done'], p['progress']['total']), 'members': active,
        'scores': sorted((m['user_id'], m['peer_score']) for m in p['members'] if m['status'] == 'active'),
        'tasks': sorted((t['id'], t['title'], t['status'], t['due_at'], t['latest_submission_status']) for t in tasks),
        'report_tasks': sorted((t['id'], t['status']) for t in report['tasks']),
        'report_peer': sorted((x['user']['id'], x['average'], x['count']) for x in report['peer']),
        'peer_members': sorted((x['user']['id'], x['average'], x['count']) for x in peer['members']),
        'peer_published': sorted((t['id'], str(t.get('results'))) for t in peer['tasks'] if t['published']),
    }


def check_project(app, pid, viewers):
    seen = {email: facts(Client(app, email) if isinstance(email, str) else email, pid) for email in viewers}
    base_email, base = next(iter(seen.items()))
    # internal agreement on one account
    assert base['progress'] == (sum(t[2] == 'done' for t in base['tasks']), len(base['tasks'])), pid
    assert base['report_tasks'] == sorted((t[0], t[2]) for t in base['tasks']), pid
    assert base['report_peer'] == base['peer_members'], pid
    published = dict((uid, avg) for uid, avg, _ in base['peer_members'])
    for uid, score in base['scores']:
        assert score == published.get(uid), (pid, uid, score, published.get(uid))
    # every account sees the same thing
    for email, f in seen.items():
        assert f == base, (pid, email, base_email, {k: (f[k], base[k]) for k in f if f[k] != base[k]})
    return base


def card_agrees(card, f, pid):
    assert (card['name'], card['team_name'], card['status']) == (f['name'], f['team'], f['status']), pid
    assert (card['done'], card['total']) == f['progress'], pid
    assert card['members'] == len(f['members']), pid
    assert card['assignment_id'] == f['assignment'][0] and card['course_id'] == f['course'], pid


def test_every_project_is_identical_for_all_members_and_staff(app):
    with app.app_context():
        projects = [(p.id, p.assignment_id) for p in Project.query.filter_by(mode='academic').filter(Project.status != 'archived').order_by(Project.id)]
        people = {}
        for pid, aid in projects:
            a = db.session.get(Assignment, aid)
            members = [db.session.get(User, m.user_id).email for m in AssignmentMembership.query.filter_by(project_id=pid, status='active')]
            staff = [db.session.get(User, e.user_id).email for e in CourseEnrollment.query.filter_by(course_id=a.course_id, status='active') if e.role in ('instructor', 'coordinator')]
            people[pid] = members + staff
    clients = {}
    def client(email):
        if email not in clients:
            clients[email] = Client(app, email)
        return clients[email]
    homes = {}
    for pid, _ in projects:
        f = check_project(app, pid, [client(e) for e in people[pid]])
        for email in people[pid]:
            if email not in homes:
                homes[email] = client(email).req('/workflow/home')
            h = homes[email]
            card = next(x for x in h['projects'] if x['id'] == pid)
            card_agrees(card, f, pid)
            course = next(c for c in h['courses'] if c['id'] == f['course'])
            assert course['assignment']['title'] == f['assignment'][1], (pid, email)
            group = next(g for g in course['groups'] if g['id'] == pid)
            card_agrees(group, f, pid)


def test_personal_numbers_agree_across_pages(app):
    """Dashboard numbers, Kanban, Bài nộp and Timeline use the same personal sets."""
    for email in (MA, TH):
        c = Client(app, email)
        home = c.req('/workflow/home')
        mine = c.req('/workflow/tasks?scope=mine')['items']
        queue = c.req('/workflow/submissions')
        assert home['stats']['task_total'] == len(mine)
        assert home['stats']['review'] == sum(t['status'] == 'review' for t in mine)
        assert home['review_queue'] == queue['counts']['to_review'] == len(queue['to_review'])
        assert sorted(p['id'] for p in home['projects']) == sorted({t['project_id'] for t in mine} | {p['id'] for p in home['projects']})
        tl = c.req('/workflow/schedule?view=mine&from=2026-01-01&to=2026-04-01')  # any window: tasks shown must be assigned tasks
        ids = {t['id'] for t in mine}
        assert all(x['id'] in ids for x in tl['items'] if x['kind'] == 'task')
        tl = c.req('/workflow/schedule?view=mine')
        for x in (x for x in tl['items'] if x['kind'] == 'task'):
            t = next(t for t in mine if t['id'] == x['id'])
            assert (x['title'], x['due_at'], x['status']) == (t['title'], t['due_at'], t['status'])
        # peer-score tile = mean of the published scores on this user's member cards
        scores = []
        for p in home['projects']:
            m = next(m for m in c.req(f'/projects/{p["id"]}')['members'] if m['user']['email'] == email)
            if m['peer_score'] is not None:
                scores.append(m['peer_score'])
        expect = round(sum(scores) / len(scores), 2) if scores else None
        assert home['stats']['peer_score'] == expect and home['stats']['peer_projects'] == len(scores)


def test_staff_dashboard_matches_course_pages(app):
    for email in (GV, COORD):
        c = Client(app, email)
        home = c.req('/workflow/home')
        staff_courses = [x for x in home['courses'] if x['my_role'] in ('instructor', 'coordinator')]
        group_ids = sorted(g['id'] for x in staff_courses for g in x['groups'])
        assert group_ids == sorted(p['id'] for p in home['projects'])
        assert sorted(g['id'] for x in staff_courses for g in x['groups'] if g['status'] == 'pending') == sorted(g['id'] for g in home['pending_groups'])
        assert home['review_queue'] == len(home.get('review_rows', []))
