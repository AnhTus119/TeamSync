import hashlib, re, uuid
from datetime import timedelta
from urllib.parse import urlsplit
from flask import current_app
from ..academic.core import *
from ..models.teamwork import *


def team(pid, leader=False, mutable=False):
    p = project(pid, mutable=mutable)
    a = get(Assignment, p.assignment_id)
    e, m = enrollment(a.course_id), membership(pid)
    need(e and e.role == 'student' and m, 'FORBIDDEN', 'Chỉ thành viên nhóm được truy cập khu vực nội bộ', 403)
    if leader:
        need(m.role == 'leader', 'FORBIDDEN', 'Cần quyền trưởng nhóm', 403)
    return p


def vault(pid, kind):
    need(kind in ('internal', 'final'))
    v = Vault.query.filter_by(project_id=pid, kind=kind).first()
    if not v:
        v = Vault(project_id=pid, kind=kind)
        db.session.add(v)
        db.session.flush()
    return v


def entry_dto(e):
    f = get(StoredFile, e.file_id)
    # Teacher-facing DTO has no source chat, internal entry IDs or storage keys.
    return {'id': e.id, 'title': e.title, 'note': e.note, 'kind': f.kind,
            'filename': f.original_filename, 'size_bytes': f.size_bytes,
            'sha256': f.sha256, 'created_at': iso(e.created_at),
            'download_url': f'/api/v1/vault-entries/{e.id}/download',
            'url': f.url if f.kind == 'link' else None}


def add_entry(pid, f, kind='internal', title=None, note=''):
    need(f.project_id == pid, 'INVALID_FILE_SCOPE', 'Tài liệu thuộc nhóm khác', 403)
    v = vault(pid, kind)
    e = VaultEntry.query.filter_by(vault_id=v.id, file_id=f.id).first()
    if not e:
        e = VaultEntry(vault_id=v.id, file_id=f.id, submitted_by=current_user().id,
                       title=(title or f.original_filename or f.url)[:240], note=note)
        db.session.add(e)
        db.session.flush()
    return e


def valid_url(url):
    try:
        u = urlsplit(url)
        return u.scheme in ('http', 'https') and bool(u.hostname) and not u.username and not u.password
    except ValueError:
        return False


def message_dto(m):
    return {**dto(m), 'sender': user_brief(m.sender_id),
            'files': [entry_dto(e) for e in VaultEntry.query.join(Vault).filter(
                Vault.project_id == m.project_id, Vault.kind == 'internal',
                VaultEntry.file_id.in_(m.file_ids)).all()]}


def send_message(pid, body, system=False):
    team(pid, mutable=True)
    content = textval(body, 'content', default='') if body.get('content') else ''
    need(len(content) <= 4000, message='Tin nhắn tối đa 4.000 ký tự')
    key = textval(body, 'client_key')
    need(len(key) <= 80)
    existing = Message.query.filter_by(project_id=pid, sender_id=current_user().id, client_key=key).first()
    if existing:
        return existing
    ids = body.get('file_ids', [])
    need(isinstance(ids, list) and len(ids) <= 10)
    need(content or ids, message='Nhập nội dung hoặc đính kèm tài liệu')
    for ident in ids:
        integer(ident)
    need(Message.query.filter(Message.project_id==pid,Message.sender_id==current_user().id,Message.created_at>now()-timedelta(minutes=1)).count()<30, 'RATE_LIMITED','Tối đa 30 tin nhắn mỗi phút',429)
    files = []
    for ident in set(ids):
        f = get(StoredFile, integer(ident))
        need(f.project_id == pid and f.uploaded_by == current_user().id,
             'INVALID_FILE_SCOPE', 'Chỉ đính kèm file của bạn trong nhóm này', 403)
        files.append(f)
    for url in dict.fromkeys(re.findall(r'https?://[^\s<>"\x27]+', content)):
        url = url.rstrip('.,;!?)')
        if not valid_url(url):
            continue
        f = StoredFile(project_id=pid, uploaded_by=current_user().id, kind='link', url=url)
        db.session.add(f)
        files.append(f)
    for f in files:
        add_entry(pid, f)
    m = Message(project_id=pid, sender_id=current_user().id, content=content,
                file_ids=[f.id for f in files], client_key=key, kind='ping' if system else 'chat')
    db.session.add(m)
    db.session.flush()
    return m


def bind_submission(t, s, branch_id=None):
    if branch_id:
        b = get(TaskBranch, integer(branch_id), lock=True)
        need(b.task_id == t.id and b.author_id == current_user().id and b.status == 'open',
             'INVALID_BRANCH', 'Nhánh không hợp lệ hoặc không thuộc bạn', 403)
    else:
        b = TaskBranch(task_id=t.id, author_id=current_user().id,
                       name=f'work/{current_user().id}/{s.attempt_no}-{uuid.uuid4().hex[:6]}')
        db.session.add(b)
        db.session.flush()
    db.session.add(BranchMergeRequest(branch_id=b.id, submission_id=s.id))


def commitment(pid, uid, at=None):
    at = at or now()
    cutoff = at - timedelta(days=90)
    tasks = Task.query.join(TaskParticipant, TaskParticipant.task_id == Task.id).filter(
        Task.project_id == pid, TaskParticipant.user_id == uid, Task.archived_at == None).all()
    due, ontime = 0, 0
    for t in tasks:
        s = db.session.get(TaskSubmission, t.latest_submission_id) if t.latest_submission_id else None
        # A pending, on-time MR is not a late completion caused by the review queue.
        if s and s.status == 'pending':
            continue
        if s and s.status == 'accepted' and s.received_at >= cutoff:
            due += 1
            ontime += int(s.received_at <= s.submitted_due_at)
        elif t.due_at and cutoff <= t.due_at < at and t.status != 'done':
            due += 1
    extensions = DeadlineExtension.query.join(Task).filter(Task.project_id == pid,
        DeadlineExtension.requested_by == uid, DeadlineExtension.created_at >= cutoff).count()
    # Count distinct active days, rather than rewarding message spam.
    chat_days = {x.created_at.date() for x in Message.query.filter(Message.project_id == pid,
        Message.sender_id == uid, Message.kind == 'chat', Message.created_at >= at-timedelta(days=14)).all()}
    meeting_days = {x.joined_at.date() for x in MeetingAttendance.query.join(Meeting).filter(
        Meeting.project_id == pid, MeetingAttendance.user_id == uid,
        MeetingAttendance.active_seconds >= 300, MeetingAttendance.joined_at >= at-timedelta(days=14)).all()}
    engagement = min(1, (len(chat_days) + len(meeting_days)) / 5)
    rate = ontime / due if due else None
    score = round(65 * rate + 20 * max(0, 1-extensions/5) + 15 * engagement, 1) if due else None
    return {'user': user_brief(uid), 'score': score, 'provisional': due < 3,
            'algorithm': 'ci-v1', 'metrics': {'eligible_tasks': due, 'on_time': ontime,
            'on_time_rate': rate, 'extension_requests': extensions, 'chat_days': len(chat_days),
            'meeting_days': len(meeting_days), 'engagement': engagement},
            'explanation': '65% đúng hạn + 20% ít xin hoãn + 15% tương tác theo ngày. Không dùng làm điểm học phần tự động.'}


def extract_drafts(meeting):
    """Deterministic local fallback; never represented as an AI provider result."""
    for line in meeting.notes.splitlines():
        title = re.sub(r'^\s*(?:[-*•]|\d+[.)]|\[[ xX]\])\s*', '', line).strip()
        if len(title) < 5:
            continue
        digest = hashlib.sha256(title.casefold().encode()).hexdigest()
        if MeetingTaskDraft.query.filter_by(meeting_id=meeting.id, source_hash=digest).first():
            continue
        db.session.add(MeetingTaskDraft(meeting_id=meeting.id, title=title[:200],
                                       source_line=line, source_hash=digest))
    db.session.flush()
    return {'provider': 'local-rule-based', 'ai_enabled': False,
            'items': rows(MeetingTaskDraft, meeting_id=meeting.id)}
