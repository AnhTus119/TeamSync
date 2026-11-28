"""Thông báo trong ứng dụng cho mọi thay đổi quan trọng.

`audit()` gọi `from_audit()` sau mỗi thao tác. Mỗi hành động trong bảng RULES biết ai cần biết, tiêu đề, nội dung
và đường dẫn. Người thực hiện không nhận thông báo về chính thao tác của mình. Hành động đã có thông báo riêng
(lời mời nhóm, bài chờ duyệt, kết quả duyệt, chuyển giảng viên, hỗ trợ, phản ánh đóng góp, nhắc hạn) không lặp lại ở đây.
"""
import logging
from datetime import timedelta, timezone
from flask import has_request_context
from ..extensions import db
from ..models import Project, Task, User
from ..models.academic import (Assignment, AssignmentMembership, CourseEnrollment, CourseOffering, OutboxEvent,
                               TaskParticipant, TaskSubmission)
from ..common.clock import now
from ..m20_accounts.permissions import current_user


def push(event, recipients, title, body, path, aggregate_id=0, include_actor=False):
    """Queue one in-app notification (delivered by the outbox worker within seconds)."""
    me = current_user().id if has_request_context() and current_user() and not include_actor else None
    ids = sorted({uid for uid in recipients if uid and uid != me})
    if not ids:
        return
    db.session.add(OutboxEvent(event_type=event, aggregate_id=aggregate_id or 0, created_at=now(),
                               payload={'recipients': ids, 'title': title[:200], 'subject': body, 'path': path}))


# ---------------------------------------------------------------- recipients
def members(pid):
    return [m.user_id for m in AssignmentMembership.query.filter_by(project_id=pid, status='active')]


def leaders(pid):
    return [m.user_id for m in AssignmentMembership.query.filter_by(project_id=pid, status='active', role='leader')]


def participants(tid):
    return [x.user_id for x in TaskParticipant.query.filter_by(task_id=tid)]


def students(cid):
    return [e.user_id for e in CourseEnrollment.query.filter_by(course_id=cid, status='active', role='student')]


def instructors(cid):
    return [e.user_id for e in CourseEnrollment.query.filter_by(course_id=cid, status='active', role='instructor')]


def project_name(pid):
    p = db.session.get(Project, pid)
    return (p.name + (f' · {p.team_name}' if p.team_name else '')) if p else ''


def actor_name():
    u = current_user() if has_request_context() else None
    return u.full_name if u else 'Hệ thống'


VN = timezone(timedelta(hours=7))


def dmy(at):
    if not at:
        return ''
    if at.tzinfo is None:
        at = at.replace(tzinfo=timezone.utc)
    return at.astimezone(VN).strftime('%d/%m/%Y')


# ---------------------------------------------------------------- rules
def task_created(obj, pid, reason):
    push('task.assigned', participants(obj.id), 'Bạn được giao công việc mới',
         f'{obj.title} · {project_name(pid)} · hạn {dmy(obj.due_at)} · giao bởi {actor_name()}', f'/tasks/{obj.id}', obj.id)


def task_updated(obj, pid, reason):
    push('task.updated', participants(obj.id) + leaders(pid), 'Công việc được cập nhật',
         f'{obj.title} · {project_name(pid)} · hạn {dmy(obj.due_at)} · {actor_name()} cập nhật phân công / nội dung', f'/tasks/{obj.id}', obj.id)


def task_started(obj, pid, reason):
    push('task.started', leaders(pid), 'Thành viên bắt đầu công việc', f'{actor_name()} bắt đầu: {obj.title} · {project_name(pid)}',
         f'/tasks/{obj.id}', obj.id)


def submission_accepted(obj, pid, reason):
    """Task done: invite the members who did not work on it to the per-task peer review."""
    t = db.session.get(Task, obj.task_id)
    workers = set(obj.participant_ids or []) | {obj.submitted_by}
    push('peer.open', [u for u in members(pid) if u not in workers], 'Mời đánh giá chéo',
         f'{t.title} đã hoàn thành · {project_name(pid)} · đánh giá người làm trong 7 ngày', f'/projects/{pid}?tab=peer#peer-task-{t.id}', t.id)


def extension_requested(obj, pid, reason):
    t = db.session.get(Task, obj.task_id)
    push('extension.requested', leaders(pid), 'Có đề nghị gia hạn',
         f'{actor_name()} xin gia hạn "{t.title}" tới {dmy(obj.requested_due_at)}: {obj.reason}', f'/tasks/{t.id}', obj.id)


def extension_decided(obj, pid, reason):
    t = db.session.get(Task, obj.task_id)
    ok = obj.status == 'approved'
    push('extension.decided', [obj.requested_by] + (participants(t.id) if ok else []), 'Đề nghị gia hạn được đồng ý' if ok else 'Đề nghị gia hạn bị từ chối',
         f'{t.title} · {"hạn mới " + dmy(obj.requested_due_at) if ok else "giữ hạn " + dmy(t.due_at)}' + (f' · {reason}' if reason else ''), f'/tasks/{t.id}', obj.id)


def assignment_updated(obj, cid, reason):
    push('assignment.updated', students(obj.course_id), 'Đề bài được cập nhật',
         f'{obj.title} · hạn nộp {dmy(obj.due_at)} · {actor_name()} vừa sửa đề bài', f'/courses/{obj.course_id}?tab=brief', obj.id)


def assignment_published(obj, cid, reason):
    push('assignment.published', students(obj.course_id), 'Có đề bài nhóm mới',
         f'{obj.title} · hạn nộp {dmy(obj.due_at)}', f'/courses/{obj.course_id}?tab=brief', obj.id)


def group_assigned(obj, pid, reason):
    push('group.assigned', members(pid), 'Bạn được xếp vào nhóm',
         f'{project_name(pid)} · xếp bởi {actor_name()}', f'/projects/{pid}?tab=members', pid)


def group_readmitted(obj, pid, reason):
    push('group.readmitted', members(pid), 'Nhóm có thành viên mới', f'{project_name(pid)} · {reason or ""}', f'/projects/{pid}?tab=members', pid)


def minutes_saved(obj, pid, reason):
    push('minutes.saved', members(pid), 'Biên bản họp mới', f'{obj.title} · {project_name(pid)}', f'/projects/{pid}?tab=minutes', obj.id)


def schedule_shared(obj, pid, reason):
    push('schedule.shared', members(pid), 'Lịch nhóm mới',
         f'{obj.title} · {obj.start_date.strftime("%d/%m")}{" – " + obj.end_date.strftime("%d/%m") if obj.end_date != obj.start_date else ""} · {actor_name()}',
         '/timeline', obj.id)


def group_delivered(obj, pid, reason):
    p = db.session.get(Project, pid)
    a = db.session.get(Assignment, p.assignment_id)
    push('group.delivered', members(pid) + instructors(a.course_id), 'Nhóm đã bàn giao sản phẩm',
         f'{obj.title} · {project_name(pid)}', f'/projects/{pid}?tab=report', obj.id)


def criterion_created(obj, cid, reason):
    a = db.session.get(Assignment, obj.assignment_id)
    push('criterion.created', students(a.course_id), 'Tiêu chí minh chứng mới', f'{obj.title} · {a.title}',
         f'/courses/{a.course_id}?tab=brief', obj.id)


def departure_requested(obj, pid, reason):
    pass  # already announced by the workflow ("Có yêu cầu rời nhóm cần xử lý")


RULES = {
    'task.created': task_created, 'task.updated': task_updated, 'task.started': task_started,
    'submission.accepted': submission_accepted,
    'extension.requested': extension_requested, 'extension.approved': extension_decided, 'extension.rejected': extension_decided,
    'assignment.updated': assignment_updated, 'assignment.published': assignment_published,
    'group.assigned': group_assigned, 'group.readmitted': group_readmitted, 'minutes.saved': minutes_saved,
    'schedule.shared': schedule_shared, 'group.delivered': group_delivered, 'evidence_criterion.created': criterion_created,
}


def from_audit(action, obj, cid=None, pid=None, reason=None):
    rule = RULES.get(action)
    if not rule:
        return
    try:
        rule(obj, pid if pid is not None else cid, reason)
    except Exception:  # a notification must never block the user's action
        logging.getLogger(__name__).exception('Notification for %s failed', action)


def leader_changed(p, successor_id, old_leader_id):
    """New team leader chosen after the old leader left (random among members after the vote)."""
    u = db.session.get(User, successor_id)
    push('group.leader', [successor_id], 'Bạn trở thành trưởng nhóm', f'{project_name(p.id)} · sau biểu quyết khi trưởng nhóm cũ rời nhóm',
         f'/projects/{p.id}?tab=members', p.id, include_actor=True)  # the last voter may be the one chosen
    push('group.leader', [x for x in members(p.id) if x != successor_id], 'Nhóm có trưởng nhóm mới',
         f'{u.full_name if u else ""} là trưởng nhóm mới của {project_name(p.id)}', f'/projects/{p.id}?tab=members', p.id, include_actor=True)
