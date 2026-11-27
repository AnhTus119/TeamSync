"""Evidence criteria, independent review, instructor referral and dashboard data.

Review rule (checked on the server for every decision):
- an active student member of the group may decide on the latest pending
  submission when they are neither the submitter nor listed in the roster
  stored on that exact submission (leaders included);
- the course instructor may decide only on a submission the leader referred
  to them, identified by its own submission ID.
"""
import math
from datetime import timedelta
from flask import request
from . import api
from .core import *
from ..models.workflow import EvidenceCriterion, SubmissionEvidence, SubmissionReferral
from ..models.teamwork import MatrixReview

wf = None  # workflow blueprint, injected by register()

ACTIVITY_TITLES = {
    'task.created': 'Tạo công việc', 'task.started': 'Bắt đầu thực hiện', 'task.updated': 'Cập nhật công việc',
    'task.submitted': 'Nộp bài', 'submission.accepted': 'Duyệt bài nộp', 'submission.returned': 'Yêu cầu sửa bài',
    'submission.referred': 'Chuyển bài cho giảng viên', 'group.readmitted': 'Thêm thành viên',
    'group.assigned': 'Xếp nhóm', 'group.approval': 'Cập nhật duyệt nhóm', 'project.member_added': 'Thêm thành viên',
    'group.departure_approved': 'Thành viên rời nhóm', 'minutes.saved': 'Lưu biên bản họp',
    'group.delivered': 'Bàn giao sản phẩm',
}


def submission_link(task_id, sid):
    return f'/tasks/{task_id}?submission={sid}#submission-{sid}'


def instructor_ids(p):
    cid = get(Assignment, p.assignment_id).course_id
    return [e.user_id for e in CourseEnrollment.query.filter_by(course_id=cid, role='instructor', status='active')]


def open_referral(sid):
    return SubmissionReferral.query.filter_by(submission_id=sid, status='open').first()


def review_scope(s, uid=None, t=None):
    """Return ('member'|'instructor', None) or (None, reason) for one submission."""
    uid = uid or current_user().id
    t = t or get(Task, s.task_id)
    if s.status != 'pending' or t.latest_submission_id != s.id or t.status != 'review':
        return None, 'Bản nộp này không còn chờ duyệt'
    p = get(Project, t.project_id)
    cid = get(Assignment, p.assignment_id).course_id
    e = enrollment(cid, uid)
    if not e:
        return None, 'Không thuộc học phần'
    if e.role == 'student':
        if not membership(p.id, uid):
            return None, 'Chỉ thành viên đang hoạt động trong nhóm được duyệt'
        if uid == s.submitted_by or uid in (s.participant_ids or []):
            return None, 'Bạn có tên trong lần nộp này nên cần người khác duyệt'
        return 'member', None
    if e.role == 'instructor':
        r = open_referral(s.id)
        if r and r.instructor_id == uid:
            return 'instructor', None
        return None, 'Giảng viên chỉ duyệt bản nộp được trưởng nhóm chuyển'
    return None, 'Vai trò này không duyệt bài nộp'


def can_refer(s, uid=None, t=None):
    uid = uid or current_user().id
    t = t or get(Task, s.task_id)
    m = membership(t.project_id, uid)
    return bool(m and m.role == 'leader' and s.status == 'pending' and t.latest_submission_id == s.id
                and t.status == 'review' and not open_referral(s.id))


def criterion_dto(c):
    return {'id': c.id, 'assignment_id': c.assignment_id, 'title': c.title, 'description': c.description,
            'is_active': c.is_active, 'version': c.version, 'created_at': iso(c.created_at)}


def submission_extras(s, t):
    """Per-submission evidence, referral and permissions for task detail."""
    from .core import asset_dto
    links = SubmissionEvidence.query.filter_by(submission_id=s.id).order_by(SubmissionEvidence.id).all()
    evidence = []
    for x in links:
        c = db.session.get(EvidenceCriterion, x.criterion_id)
        a = db.session.get(EvidenceAsset, x.asset_id)
        evidence.append({'criterion_id': x.criterion_id, 'criterion_title': c.title if c else '',
                         'criterion_active': bool(c and c.is_active), 'asset': asset_dto(a) if a else None})
    r = SubmissionReferral.query.filter_by(submission_id=s.id).first()
    referral = None
    if r:
        referral = {'id': r.id, 'reason': r.reason, 'status': r.status, 'created_at': iso(r.created_at),
                    'referred_by_name': user_brief(r.referred_by)['full_name'],
                    'instructor_name': user_brief(r.instructor_id)['full_name']}
    scope, why = review_scope(s, t=t)
    return {'evidence': evidence, 'referral': referral, 'can_review': bool(scope), 'review_scope': scope,
            'review_block_reason': why if s.status == 'pending' and s.id == t.latest_submission_id else None,
            'can_refer': can_refer(s, t=t), 'link': submission_link(t.id, s.id),
            'reviewed_by_name': user_brief(s.reviewed_by)['full_name'] if s.reviewed_by else None}


def attach_evidence(t, s, revision_id, items):
    """Validate criterion scope and that each asset belongs to the submitted revision."""
    if not items:
        return
    need(isinstance(items, list) and len(items) <= 50, message='Danh sách minh chứng không hợp lệ')
    p = get(Project, t.project_id)
    seen = set()
    for item in items:
        need(isinstance(item, dict))
        cid, aid = integer(item.get('criterion_id')), integer(item.get('asset_id'))
        c = get(EvidenceCriterion, cid)
        need(c.assignment_id == p.assignment_id, 'INVALID_EVIDENCE_SCOPE', 'Tiêu chí không thuộc đề bài của nhóm')
        need(c.is_active, 'CRITERION_HIDDEN', 'Tiêu chí đã ẩn, không nhận minh chứng mới', 409)
        need(db.session.get(EvidenceRevisionAsset, (revision_id, aid)) is not None,
             'INVALID_EVIDENCE_SCOPE', 'Tệp hoặc liên kết không thuộc lần nộp này')
        if (cid, aid) in seen:
            continue
        seen.add((cid, aid))
        db.session.add(SubmissionEvidence(submission_id=s.id, criterion_id=cid, asset_id=aid))


def decide_referral(s):
    r = open_referral(s.id)
    if r:
        r.status = 'decided'
        r.decided_at = now()


# ---------------------------------------------------------------- referral
@api.post('/submissions/<int:sid>/refer')
@command(idempotent=True)
def submission_refer(sid):
    s = get(TaskSubmission, sid, lock=True)
    t = task(s.task_id, mutable=True)
    p = get(Project, t.project_id)
    m = membership(p.id)
    need(m and m.role == 'leader', 'FORBIDDEN', 'Chỉ trưởng nhóm được chuyển bài cho giảng viên', 403)
    need(s.status == 'pending' and t.latest_submission_id == sid and t.status == 'review',
         'VERSION_CONFLICT', 'Bản nộp đang xem đã thay đổi. Tải lại để xem bản mới nhất', 409)
    need(not open_referral(sid), 'ALREADY_REFERRED', 'Bản nộp này đã được chuyển cho giảng viên', 409)
    b = json_body()
    reason = textval(b, 'reason')
    teachers = instructor_ids(p)
    need(teachers, 'NO_INSTRUCTOR', 'Học phần chưa có giảng viên phụ trách', 409)
    r = SubmissionReferral(submission_id=sid, project_id=p.id, referred_by=current_user().id,
                           instructor_id=teachers[0], reason=reason)
    db.session.add(r)
    db.session.flush()
    audit('submission.referred', s, pid=p.id, reason=reason)
    db.session.add(OutboxEvent(event_type='submission.referred', aggregate_id=s.id, payload={
        'recipients': [teachers[0]], 'path': submission_link(t.id, sid),
        'subject': f'{t.title} · {p.name} · Lần {s.attempt_no}'}))
    return {'id': r.id, 'submission_id': sid, 'status': r.status, 'reason': reason}, 201


def register(bp):
    global wf
    wf = bp

    @bp.route('/assignments/<int:aid>/evidence-criteria', methods=['GET', 'POST'])
    @command()
    def evidence_criteria(aid):
        a = assignment(aid)
        e = enrollment(a.course_id)
        q = EvidenceCriterion.query.filter_by(assignment_id=aid)
        if request.method == 'GET':
            if e.role == 'student':
                q = q.filter_by(is_active=True)
            items = [criterion_dto(c) for c in q.order_by(EvidenceCriterion.id)]
            return {'items': items, 'can_manage': e.role == 'instructor'}
        need(e.role == 'instructor', 'FORBIDDEN', 'Chỉ giảng viên phụ trách quản lý tiêu chí minh chứng', 403)
        b = json_body()
        title = textval(b, 'title')
        need(len(title) <= 200, message='Tên tiêu chí tối đa 200 ký tự')
        need(not q.filter(db.func.lower(EvidenceCriterion.title) == title.lower()).first(),
             'DUPLICATE', 'Tiêu chí đã tồn tại', 409)
        c = EvidenceCriterion(assignment_id=aid, title=title, description=(b.get('description') or '').strip()[:2000],
                              created_by=current_user().id)
        db.session.add(c)
        db.session.flush()
        audit('evidence_criterion.created', c, cid=a.course_id, reason=title)
        return criterion_dto(c), 201

    @bp.patch('/evidence-criteria/<int:crid>')
    @command()
    def evidence_criterion_update(crid):
        c = get(EvidenceCriterion, crid, lock=True)
        a = assignment(c.assignment_id)
        need(enrollment(a.course_id).role == 'instructor', 'FORBIDDEN', 'Chỉ giảng viên phụ trách quản lý tiêu chí minh chứng', 403)
        b = json_body()
        version(c, b)
        need(type(b.get('is_active')) is bool, message='Cần chọn ẩn hoặc bật lại tiêu chí')
        c.is_active = b['is_active']
        audit('evidence_criterion.' + ('enabled' if c.is_active else 'hidden'), c, cid=a.course_id, reason=c.title)
        return criterion_dto(c)

    @bp.get('/submissions')
    @command()
    def submission_queue():
        return queue_data()

    @bp.get('/tasks')
    @command()
    def global_tasks():
        # scope=mine: personal board, only tasks the signed-in user is assigned to (responsible or collaborator).
        mine = request.args.get('scope') == 'mine'
        uid = current_user().id
        ps = visible_projects()
        out = []
        for p, c, a, role in ps:
            q = Task.query.filter_by(project_id=p.id)
            if mine:
                q = q.join(TaskParticipant, TaskParticipant.task_id == Task.id).filter(TaskParticipant.user_id == uid)
            ts = q.order_by(Task.due_at, Task.id).all()
            prefetch_tasks(ts)
            for t in ts:
                out.append({**task_summary(t), 'project_name': p.name, 'team_name': p.team_name, 'course_title': c.title})
        return {'items': out, 'projects': [project_card(p, c, a, role) for p, c, a, role in ps]}


# ---------------------------------------------------------------- scope helpers
def visible_projects(include_inactive=False):
    """(project, course, assignment, my_role) for projects the user may open."""
    out = []
    uid = current_user().id
    for e in CourseEnrollment.query.filter_by(user_id=uid, status='active').order_by(CourseEnrollment.course_id):
        c = db.session.get(CourseOffering, e.course_id)
        for a in Assignment.query.filter_by(course_id=c.id).order_by(Assignment.id):
            if a.is_hidden and e.role not in STAFF:
                continue
            for p in Project.query.filter_by(assignment_id=a.id, mode='academic').order_by(Project.id):
                if p.status == 'archived' and not include_inactive:
                    continue
                if e.role in STAFF:
                    out.append((p, c, a, e.role))
                else:
                    m = membership(p.id, uid)
                    if m:
                        out.append((p, c, a, m.role))
    return out


def project_card(p, c, a, role):
    total = Task.query.filter_by(project_id=p.id).count()
    done = Task.query.filter_by(project_id=p.id, status='done').count()
    late = Task.query.filter(Task.project_id == p.id, Task.status.in_(['todo', 'in_progress']), Task.due_at < now()).count()
    return {'id': p.id, 'name': p.name, 'team_name': p.team_name or '', 'status': p.status, 'my_role': role,
            'created_at': iso(p.created_at), 'assignment_id': a.id,
            'course_id': c.id, 'course_title': c.title, 'course_code': c.code, 'assignment_title': a.title,
            'members': AssignmentMembership.query.filter_by(project_id=p.id, status='active').count(),
            'total': total, 'done': done, 'late': late,
            'help': HelpRequest.query.filter(HelpRequest.project_id == p.id, HelpRequest.status.in_(['submitted', 'under_review'])).count(),
            'pending_review': Task.query.filter_by(project_id=p.id, status='review').count()}


def queue_row(s, t, p, uid):
    scope, _ = review_scope(s, uid, t)
    r = SubmissionReferral.query.filter_by(submission_id=s.id).first()
    return {'id': s.id, 'task_id': t.id, 'task_title': t.title, 'attempt_no': s.attempt_no, 'project_id': p.id,
            'project_name': p.name, 'team_name': p.team_name or '', 'submitted_by_name': user_brief(s.submitted_by)['full_name'],
            'participant_names': [user_brief(x)['full_name'] for x in s.participant_ids or []],
            'received_at': iso(s.received_at), 'status': s.status, 'is_latest': t.latest_submission_id == s.id,
            'referred': bool(r), 'referral_reason': r.reason if r else None, 'can_review': bool(scope),
            'link': submission_link(t.id, s.id)}


def queue_data():
    uid = current_user().id
    mine, review = [], []
    for p, c, a, role in visible_projects():
        if role in STAFF:
            if role != 'instructor':
                continue
            for r in SubmissionReferral.query.filter_by(project_id=p.id, instructor_id=uid).order_by(SubmissionReferral.id.desc()):
                s = get(TaskSubmission, r.submission_id)
                t = get(Task, s.task_id)
                row = queue_row(s, t, p, uid)
                if row['can_review']:
                    review.append(row)
                else:
                    mine.append(row)
            continue
        for t in Task.query.filter_by(project_id=p.id):
            for s in TaskSubmission.query.filter_by(task_id=t.id).order_by(TaskSubmission.attempt_no):
                involved = s.submitted_by == uid or uid in (s.participant_ids or [])
                if involved:
                    mine.append(queue_row(s, t, p, uid))
                elif s.id == t.latest_submission_id and review_scope(s, uid, t)[0]:
                    review.append(queue_row(s, t, p, uid))
    key = lambda x: x['received_at'] or ''
    mine.sort(key=key, reverse=True)
    review.sort(key=key)
    return {'mine': mine, 'to_review': review, 'counts': {'mine': len(mine), 'to_review': len(review)},
            'is_instructor': any(e.role == 'instructor' for e in CourseEnrollment.query.filter_by(user_id=uid, status='active'))}


def peer_scores(p, uids):
    """Published (closed-round) mean score per member of one project; reviewer identities never leave here."""
    rounds = [r.id for r in PeerRound.query.filter_by(assignment_id=p.assignment_id)
              if not (r.status == 'open' and now() <= r.closes_at)]
    if not rounds or not uids:
        return {}
    acc = {}
    for x in MatrixReview.query.filter(MatrixReview.project_id == p.id, MatrixReview.reviewee_id.in_(list(uids)),
                                       MatrixReview.round_id.in_(rounds)):
        acc.setdefault(x.reviewee_id, []).append(((x.attitude10 or x.attitude * 2) + (x.quality10 or x.quality * 2)) / 2)
    return {uid: round(sum(v) / len(v), 2) for uid, v in acc.items()}


def peer_score(p, uid):
    """Mean of valid reviews the user received in closed rounds of this project."""
    rounds = [r.id for r in PeerRound.query.filter_by(assignment_id=p.assignment_id)
              if not (r.status == 'open' and now() <= r.closes_at)]
    if not rounds:
        return None
    rs = MatrixReview.query.filter(MatrixReview.project_id == p.id, MatrixReview.reviewee_id == uid,
                                   MatrixReview.round_id.in_(rounds)).all()
    vals = [((x.attitude10 or x.attitude * 2) + (x.quality10 or x.quality * 2)) / 2 for x in rs]
    return round(sum(vals) / len(vals), 2) if vals else None


def dashboard_data():
    """Extra Tổng quan data computed from the same business clock as alerts."""
    uid = current_user().id
    at = now()
    soon = at + timedelta(hours=24)
    ps = visible_projects()
    cards = [project_card(p, c, a, role) for p, c, a, role in ps]
    student_ps = [(p, c, a, role) for p, c, a, role in ps if role not in STAFF]
    pids = [p.id for p, *_ in ps]
    task_rows = Task.query.filter(Task.project_id.in_(pids)).all() if pids else []
    by_project = {p.id: p for p, *_ in ps}
    latest = {}
    returns = {}
    for t in task_rows:
        subs = TaskSubmission.query.filter_by(task_id=t.id).all()
        returns[t.id] = sum(s.status == 'returned' for s in subs)
        latest[t.id] = next((s for s in subs if s.id == t.latest_submission_id), None)
    data = {'projects': cards}
    queue = queue_data()
    data['review_queue'] = queue['counts']['to_review']
    if student_ps:
        # Task metrics use the same personal set as the Kanban board (/kanban): tasks assigned to the user.
        assigned = {x.task_id for x in TaskParticipant.query.filter(TaskParticipant.user_id == uid,
                                                                     TaskParticipant.task_id.in_([t.id for t in task_rows]))} if task_rows else set()
        my_rows = [t for t in task_rows if t.id in assigned]
        open_tasks = [t for t in my_rows if t.status in ('todo', 'in_progress')]
        repair = [t for t in my_rows if t.status == 'in_progress' and latest[t.id] and latest[t.id].status == 'returned']
        due = [t for t in open_tasks if t.due_at <= soon]
        waiting = [t for t in my_rows if t.status == 'review']
        scores = [x for x in (peer_score(p, uid) for p, *_ in student_ps) if x is not None]
        lead = sum(role == 'leader' for *_, role in student_ps)
        overlap = len({t.id for t in repair} & {t.id for t in due})
        data['stats'] = {
            'task_total': len(my_rows), 'project_tasks': len(task_rows), 'repair': len(repair), 'due': len(due), 'overdue': sum(t.due_at < at for t in due),
            'review': len(waiting), 'repair_due_overlap': overlap, 'projects': len(student_ps), 'lead': lead,
            'peer_score': round(sum(scores) / len(scores), 2) if scores else None, 'peer_projects': len(scores),
            'my_tasks': len(my_rows),
        }
        data['upcoming'] = [{**task_summary(t), 'project_name': by_project[t.project_id].name,
                             'overdue': t.due_at < at} for t in sorted(open_tasks, key=lambda t: t.due_at)[:6]]
    alerts = []
    for row in queue['to_review']:
        if row['received_at'] and at - timestamp(row['received_at']) > timedelta(hours=48):
            alerts.append({'kind': 'stale_review', 'label': 'Chờ duyệt quá 48 giờ', 'task_id': row['task_id'],
                           'task_title': row['task_title'], 'project_name': row['project_name'], 'link': row['link'],
                           'received_at': row['received_at']})
    for t in task_rows:
        if returns[t.id] >= 2 and t.status in ('todo', 'in_progress'):
            p = by_project[t.project_id]
            role = next(r for q, *_, r in ps if q.id == p.id)
            mine = TaskParticipant.query.filter_by(task_id=t.id, user_id=uid).first()
            if role == 'leader' or mine:
                s = latest[t.id]
                alerts.append({'kind': 'repeat_return', 'label': f'Đã yêu cầu sửa {returns[t.id]} lần', 'task_id': t.id,
                               'task_title': t.title, 'project_name': p.name,
                               'link': submission_link(t.id, s.id) if s else f'/tasks/{t.id}',
                               'received_at': iso(s.received_at) if s else None})
    data['alerts'] = alerts
    contacts = {}
    for p, c, a, role in ps:
        if role in STAFF:
            continue
        for e in CourseEnrollment.query.filter_by(course_id=c.id, role='instructor', status='active'):
            contacts.setdefault(e.user_id, 'Giảng viên phụ trách')
        for m in AssignmentMembership.query.filter_by(project_id=p.id, status='active'):
            if m.user_id != uid:
                contacts.setdefault(m.user_id, 'Thành viên dự án')
    data['contacts'] = [{'full_name': u.full_name, 'email': u.email, 'role': contacts[u.id]}
                        for u in User.query.filter(User.id.in_(list(contacts))).order_by(User.full_name)] if contacts else []
    events = (AuditEvent.query.filter(AuditEvent.project_id.in_(pids), AuditEvent.action.in_(list(ACTIVITY_TITLES)))
              .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc()).limit(6).all()) if pids else []
    data['activity'] = [activity_dto(e, by_project) for e in events]
    data['notifications'] = [{'id': n.id, 'title': n.title, 'body': n.body, 'path': n.target_path,
                              'created_at': iso(n.created_at), 'read': bool(n.read_at)}
                             for n in Notification.query.filter_by(recipient_id=uid).order_by(Notification.id.desc()).limit(5)]
    return data


def activity_dto(e, by_project):
    p = by_project.get(e.project_id)
    subject = ''
    if e.entity_type == 'task':
        t = db.session.get(Task, e.entity_id)
        subject = t.title if t else ''
    elif e.entity_type == 'task_submission':
        s = db.session.get(TaskSubmission, e.entity_id)
        t = db.session.get(Task, s.task_id) if s else None
        subject = t.title if t else ''
    elif e.entity_type == 'project' and p:
        subject = p.team_name or p.name
    actor = user_brief(e.actor_id) if e.actor_id else None
    return {'id': e.id, 'title': ACTIVITY_TITLES.get(e.action, 'Cập nhật'), 'subject': subject or (e.reason or ''),
            'actor': actor['full_name'] if actor else 'Hệ thống', 'project_name': p.name if p else '',
            'project_id': e.project_id, 'created_at': iso(e.created_at)}


def evidence_summary(p):
    """Count criteria using the latest submission of each task in the project."""
    crits = EvidenceCriterion.query.filter_by(assignment_id=p.assignment_id).order_by(EvidenceCriterion.id).all()
    out = {c.id: {'criterion_id': c.id, 'title': c.title, 'is_active': c.is_active, 'accepted': 0, 'pending': 0, 'returned': 0}
           for c in crits}
    for t in Task.query.filter_by(project_id=p.id):
        if not t.latest_submission_id:
            continue
        s = db.session.get(TaskSubmission, t.latest_submission_id)
        for cid in {x.criterion_id for x in SubmissionEvidence.query.filter_by(submission_id=s.id)}:
            if cid in out and s.status in ('accepted', 'pending', 'returned'):
                out[cid][s.status] += 1
    return list(out.values())
