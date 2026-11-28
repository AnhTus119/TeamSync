"""Đánh giá chéo theo từng công việc (thay cho đợt đánh giá).

Rules (checked on the server):
- A task becomes reviewable when it is done; the workers are the roster stored on its accepted
  submission (fallback: the task participants).
- Every active student member of the group who is NOT a worker may review each worker:
  Hợp tác and Chất lượng on a 1–10 scale plus an optional comment. Reviews are optional,
  can be skipped (not counted as 0) and edited until the window closes.
- The window is REVIEW_DAYS days after completion. Results (averages, count, comments) are
  published only after it closes and never carry the reviewer's identity.
"""
from datetime import timedelta, timezone
from flask import request
from .core import *
from ..models.workflow import TaskPeerReview

REVIEW_DAYS = 7


def completed_at(t):
    if t.status != 'done':
        return None
    at = t.completed_at
    if at is None and t.latest_submission_id:
        s = db.session.get(TaskSubmission, t.latest_submission_id)
        at = s.reviewed_at or s.received_at if s else None
    if at is None:
        at = t.updated_at
    return at.replace(tzinfo=timezone.utc) if at and at.tzinfo is None else at


def closes_at(t):
    done = completed_at(t)
    return done + timedelta(days=REVIEW_DAYS) if done else None


def is_open(t):
    end = closes_at(t)
    return bool(end and now() <= end)


def is_published(t):
    end = closes_at(t)
    return bool(end and now() > end)


def workers(t):
    s = db.session.get(TaskSubmission, t.latest_submission_id) if t.latest_submission_id else None
    if s and s.status == 'accepted' and s.participant_ids:
        return list(dict.fromkeys(s.participant_ids))
    return [x.user_id for x in TaskParticipant.query.filter_by(task_id=t.id).order_by(TaskParticipant.id)]


def reviewers(t):
    """Active student members who did not work on the task."""
    ws = set(workers(t))
    return [m.user_id for m in AssignmentMembership.query.filter_by(project_id=t.project_id, status='active') if m.user_id not in ws]


def score(x):
    return (x.attitude + x.quality) / 2


def aggregate(rs):
    if not rs:
        return None
    # One formula everywhere (member card, peer tab, report, dashboard): mean of each review's (Hợp tác + Chất lượng) / 2.
    at = round(sum(x.attitude for x in rs) / len(rs), 2)
    qu = round(sum(x.quality for x in rs) / len(rs), 2)
    return {'count': len(rs), 'attitude': at, 'quality': qu, 'average': round(sum(score(x) for x in rs) / len(rs), 2)}


def task_results(t):
    """Published per-worker aggregates for one task (anonymous)."""
    rs = TaskPeerReview.query.filter_by(task_id=t.id, skipped=False).all()
    out = []
    for uid in workers(t):
        mine = [x for x in rs if x.reviewee_id == uid]
        agg = aggregate(mine)
        comments = sorted((x.comment for x in mine if x.comment), key=str.lower)
        out.append({'user': user_brief(uid), **(agg or {'count': 0, 'attitude': None, 'quality': None, 'average': None}), 'comments': comments})
    return out


def published_tasks(p):
    return [t for t in Task.query.filter_by(project_id=p.id, status='done').order_by(Task.id) if is_published(t)]


def peer_scores(p, uids=None):
    """Mean of all published task reviews each member received in this project."""
    ids = [t.id for t in published_tasks(p)]
    if not ids:
        return {}
    q = TaskPeerReview.query.filter(TaskPeerReview.task_id.in_(ids), TaskPeerReview.skipped.is_(False))
    if uids is not None:
        if not uids:
            return {}
        q = q.filter(TaskPeerReview.reviewee_id.in_(list(uids)))
    acc = {}
    for x in q:
        acc.setdefault(x.reviewee_id, []).append(score(x))
    return {uid: round(sum(v) / len(v), 2) for uid, v in acc.items()}


def member_summary(p):
    """Per-member published aggregate across tasks (for the report and the peer tab)."""
    ids = [t.id for t in published_tasks(p)]
    rs = TaskPeerReview.query.filter(TaskPeerReview.task_id.in_(ids), TaskPeerReview.skipped.is_(False)).all() if ids else []
    by = {}
    for x in rs:
        by.setdefault(x.reviewee_id, []).append(x)
    out = []
    for m in AssignmentMembership.query.filter_by(project_id=p.id).order_by(AssignmentMembership.id):
        if m.user_id in by:
            out.append({'user': user_brief(m.user_id), 'tasks': len({x.task_id for x in by[m.user_id]}), **aggregate(by[m.user_id])})
    return out


def task_rows(p):
    """Published per-task results, for the report and exports."""
    out = []
    for t in published_tasks(p):
        for r in task_results(t):
            out.append({'task_id': t.id, 'task_title': t.title, 'completed_at': iso(completed_at(t)), **r})
    return out


def task_dto(t, uid, can_review_all):
    ws = workers(t)
    end = closes_at(t)
    opened = is_open(t)
    eligible = can_review_all and uid not in ws and uid in reviewers(t)
    own = {x.reviewee_id: x for x in TaskPeerReview.query.filter_by(task_id=t.id, reviewer_id=uid)} if eligible else {}
    d = {'id': t.id, 'title': t.title, 'completed_at': iso(completed_at(t)), 'closes_at': iso(end), 'open': opened,
         'published': not opened, 'workers': [user_brief(x) for x in ws], 'i_worked': uid in ws,
         'can_review': bool(eligible and opened), 'reviewed': len(own), 'expected': len(ws) if eligible else 0,
         'own': [{'reviewee_id': k, 'skipped': x.skipped, 'attitude': x.attitude, 'quality': x.quality, 'comment': x.comment} for k, x in own.items()],
         'reviewer_count': len(reviewers(t)),
         'received': TaskPeerReview.query.filter_by(task_id=t.id, skipped=False).count()}
    if not opened:
        d['results'] = task_results(t)
    return d


def register(bp):
    @bp.get('/projects/<int:pid>/peer')
    @command()
    def peer(pid):
        p = project(pid)
        uid = current_user().id
        student = membership(pid) is not None and not is_staff(p)
        tasks = sorted(Task.query.filter_by(project_id=pid, status='done').all(), key=lambda t: completed_at(t), reverse=True)
        items = [task_dto(t, uid, student) for t in tasks]
        return {'review_days': REVIEW_DAYS, 'tasks': items, 'members': member_summary(p),
                'pending': sum(1 for x in items if x['can_review'] and x['reviewed'] < x['expected'])}

    @bp.put('/tasks/<int:tid>/peer')
    @command()
    def peer_save(tid):
        t = task(tid, mutable=True)
        p = db.session.get(Project, t.project_id)
        uid = current_user().id
        need(membership(p.id) and not is_staff(p), 'FORBIDDEN', 'Chỉ thành viên nhóm được đánh giá', 403)
        need(t.status == 'done', 'INVALID_TRANSITION', 'Chỉ đánh giá công việc đã hoàn thành', 409)
        need(is_open(t), 'REVIEW_CLOSED', f'Đã hết hạn đánh giá ({REVIEW_DAYS} ngày sau khi hoàn thành)', 409)
        ws = workers(t)
        need(uid not in ws and uid in reviewers(t), 'FORBIDDEN', 'Người làm công việc không tự đánh giá công việc này', 403)
        items = json_body().get('items')
        need(isinstance(items, list) and items, message='Cần ít nhất một phiếu')
        seen = set()
        for i in items:
            need(isinstance(i, dict))
            rid = integer(i.get('reviewee_id'))
            need(rid in ws and rid not in seen, message='Chỉ đánh giá người làm công việc này')
            seen.add(rid)
            row = TaskPeerReview.query.filter_by(task_id=t.id, reviewer_id=uid, reviewee_id=rid).first()
            if not row:
                row = TaskPeerReview(task_id=t.id, project_id=p.id, reviewer_id=uid, reviewee_id=rid)
                db.session.add(row)
            if i.get('skip'):  # answered "bỏ qua": kept so the task is no longer pending, never scored
                row.skipped, row.attitude, row.quality, row.comment = True, None, None, ''
                continue
            at, qu = integer(i.get('attitude'), 1, 10), integer(i.get('quality'), 1, 10)
            comment = i.get('comment') or ''
            need(isinstance(comment, str) and len(comment) <= 1000, message='Nhận xét tối đa 1000 ký tự')
            row.skipped, row.attitude, row.quality, row.comment = False, at, qu, comment.strip()
        db.session.flush()
        return task_dto(t, uid, True)
