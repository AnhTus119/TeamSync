"""Timeline (lịch theo ngày).

- view=mine: everything on my schedule, read-only here: tasks I am assigned to (placed on
  their due date) plus timeline entries I can see (mine and those shared with my projects).
- view=created: entries I created; only the owner may move, re-categorise, edit or delete them.
"""
from datetime import date, datetime, time, timedelta, timezone
from flask import request
from .core import *
from ..models.workflow import ScheduleItem

CATEGORIES = {'task': 'Công việc nhóm', 'meeting': 'Họp nhóm', 'deadline': 'Mốc nộp', 'study': 'Học tập',
              'review': 'Rà soát', 'personal': 'Cá nhân', 'other': 'Khác'}
EDITABLE = [k for k in CATEGORIES if k != 'task']
MAX_SPAN = 60


def day(value, field):
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        need(False, message=f'{field}: cần ngày dạng YYYY-MM-DD')


def course_of(p):
    a = db.session.get(Assignment, p.assignment_id) if p and p.assignment_id else None
    return a.course_id if a else None


def item_dto(x, editable):
    p = db.session.get(Project, x.project_id) if x.project_id else None
    return {'id': x.id, 'kind': 'item', 'title': x.title, 'note': x.note, 'category': x.category,
            'start': x.start_date.isoformat(), 'end': x.end_date.isoformat(), 'project_id': x.project_id,
            'project_name': p.name if p else '', 'course_id': course_of(p), 'owner_id': x.owner_id,
            'owner_name': user_brief(x.owner_id)['full_name'], 'editable': editable, 'version': x.version, 'source': x.source}


def milestones(uid, lo, hi):
    """Course deadlines visible to the user: assignment due dates and group formation deadlines."""
    out = []
    for e in CourseEnrollment.query.filter_by(user_id=uid, status='active'):
        c = db.session.get(CourseOffering, e.course_id)
        for a in Assignment.query.filter_by(course_id=c.id).order_by(Assignment.id):
            if a.is_hidden and e.role not in STAFF:
                continue
            for key, label, at in (('due', 'Hạn nộp đề bài', a.due_at), ('formation', 'Hạn lập nhóm', a.formation_due_at)):
                if at and lo <= at <= hi:
                    out.append({'id': f'{a.id}-{key}', 'kind': 'milestone', 'title': f'{label}: {a.title}', 'note': '', 'category': 'deadline',
                                'due_at': iso(at), 'course_id': c.id, 'project_id': None, 'project_name': c.title, 'editable': False,
                                'link': f'/courses/{c.id}?tab=brief'})
    return out


def my_project_ids(uid):
    ids = {m.project_id for m in AssignmentMembership.query.filter_by(user_id=uid, status='active')}
    for e in CourseEnrollment.query.filter_by(user_id=uid, status='active'):
        if e.role in STAFF:
            ids |= {p.id for p in Project.query.join(Assignment, Assignment.id == Project.assignment_id).filter(Assignment.course_id == e.course_id)}
    return ids


def shareable(pid):
    """Owner may share with a project they belong to (student) or supervise (course staff)."""
    p = project(pid)
    need(p.status not in ('archived',), message='Dự án đã lưu trữ')
    return p


def owned(iid):
    x = get(ScheduleItem, iid, lock=True)
    need(x.owner_id == current_user().id, 'FORBIDDEN', 'Chỉ người tạo được sửa mục lịch này', 403)
    return x


def apply(x, b, creating=False):
    if creating or 'title' in b:
        x.title = textval(b, 'title')
        need(len(x.title) <= 200, message='Tiêu đề tối đa 200 ký tự')
    if 'note' in b:
        need(isinstance(b['note'], str) and len(b['note']) <= 2000, message='Ghi chú tối đa 2000 ký tự')
        x.note = b['note'].strip()
    if creating or 'category' in b:
        need(b.get('category', 'other') in EDITABLE, message='Loại lịch không hợp lệ')
        x.category = b.get('category', 'other')
    if creating or 'start' in b or 'end' in b:
        start = day(b.get('start', x.start_date and x.start_date.isoformat()), 'start')
        end = day(b.get('end', x.end_date and x.end_date.isoformat()) or start, 'end')
        need(start <= end, message='Ngày kết thúc phải từ ngày bắt đầu trở đi')
        need((end - start).days < MAX_SPAN, message=f'Một mục lịch dài tối đa {MAX_SPAN} ngày')
        x.start_date, x.end_date = start, end
    if 'project_id' in b:
        x.project_id = shareable(integer(b['project_id'])).id if b['project_id'] else None
    if creating:
        x.source = 'ai' if b.get('source') == 'ai' else ''


def register(bp):
    @bp.route('/schedule', methods=['GET', 'POST'])
    @command(idempotent=True)
    def schedule():
        need(current_user().role != 'admin', 'FORBIDDEN', 'Tài khoản quản trị không dùng lịch học tập', 403)
        uid = current_user().id
        if request.method == 'POST':
            b = json_body()
            x = ScheduleItem(owner_id=uid)
            apply(x, b, creating=True)
            db.session.add(x)
            db.session.flush()
            if x.project_id:
                audit('schedule.shared', x, pid=x.project_id, reason=x.title)
            return item_dto(x, True), 201
        view = request.args.get('view', 'mine')
        need(view in ('mine', 'created'))
        today = now().date()
        start = day(request.args.get('from') or (today - timedelta(days=3)).isoformat(), 'from')
        end = day(request.args.get('to') or (start + timedelta(days=13)).isoformat(), 'to')
        need(start <= end and (end - start).days <= 92, message='Khoảng xem tối đa 93 ngày')
        q = ScheduleItem.query.filter(ScheduleItem.start_date <= end, ScheduleItem.end_date >= start)
        if view == 'created':
            items = [item_dto(x, True) for x in q.filter(ScheduleItem.owner_id == uid).order_by(ScheduleItem.start_date, ScheduleItem.id)]
        else:
            pids = my_project_ids(uid)
            cond = ScheduleItem.owner_id == uid
            if pids:
                cond = db.or_(cond, ScheduleItem.project_id.in_(list(pids)))
            items = [item_dto(x, False) for x in q.filter(cond).order_by(ScheduleItem.start_date, ScheduleItem.id)]
            lo = datetime.combine(start, time.min, tzinfo=timezone.utc) - timedelta(days=1)  # local dates differ from UTC by hours
            hi = lo + timedelta(days=(end - start).days + 3)
            rows = (Task.query.join(TaskParticipant, TaskParticipant.task_id == Task.id)
                    .filter(TaskParticipant.user_id == uid, Task.due_at >= lo, Task.due_at <= hi).all())
            for t in rows:
                p = db.session.get(Project, t.project_id)
                if not p or p.id not in pids or not membership(p.id, uid):
                    continue
                items.append({'id': t.id, 'kind': 'task', 'title': t.title, 'note': '', 'category': 'task', 'due_at': iso(t.due_at),
                              'status': t.status, 'overdue': t.status in ('todo', 'in_progress') and t.due_at < now(),
                              'project_id': p.id, 'project_name': p.name, 'course_id': course_of(p), 'editable': False, 'link': f'/tasks/{t.id}'})
            items.extend(milestones(uid, lo, hi))
        projects = []
        for pid in sorted(my_project_ids(uid)):
            p = db.session.get(Project, pid)
            if p and p.status != 'archived':
                projects.append({'id': p.id, 'name': p.name + (f' · {p.team_name}' if p.team_name else ''), 'course_id': course_of(p)})
        staff = [e for e in CourseEnrollment.query.filter_by(user_id=uid, status='active') if e.role in STAFF]
        courses = [{'id': e.course_id, 'title': db.session.get(CourseOffering, e.course_id).title} for e in staff]
        return {'items': items, 'from': start.isoformat(), 'to': end.isoformat(), 'today': today.isoformat(),
                'categories': [{'key': k, 'label': v} for k, v in CATEGORIES.items()], 'projects': projects, 'courses': courses,
                'is_staff': bool(staff), 'view': view}

    @bp.route('/schedule/<int:iid>', methods=['PATCH', 'DELETE'])
    @command()
    def schedule_item(iid):
        x = owned(iid)
        if request.method == 'DELETE':
            db.session.delete(x)
            return {'deleted': iid}
        b = json_body()
        version(x, b)
        apply(x, b)
        x.source = ''  # edited by hand: the next AI run keeps it as it is
        return item_dto(x, True)
