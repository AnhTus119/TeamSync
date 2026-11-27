"""Tạo lại docs/TAI_KHOAN_DEMO.md từ dữ liệu demo (chạy trên database tạm, không đụng instance/).

    python tools/tai_khoan_demo.py
"""
import sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from flask_migrate import upgrade
from app import create_app

tmp = Path(tempfile.mkdtemp())
app = create_app({'TESTING': True, 'SQLALCHEMY_DATABASE_URI': 'sqlite:///' + str(tmp / 'db.sqlite'), 'PRIVATE_STORAGE': str(tmp / 'files'), 'DEMO_CLOCK_ENABLED': True})
with app.app_context():
    upgrade(directory=str(ROOT / 'migrations'))
    from app.academic.workflow_seed import seed_demo
    seed_demo()
    from app.models import User, Project
    from app.extensions import db
    from app.models.academic import CourseOffering, CourseEnrollment, Assignment, AssignmentMembership
    out = ['# Tài khoản demo', '', 'Mật khẩu của **mọi** tài khoản: `12345`. Dữ liệu được tạo khi chạy `python run.py` lần đầu (database mới).', '',
           '## Quản trị và quản lý học phần', '', '| Họ tên | Email | Vai trò |', '|---|---|---|']
    admin = User.query.filter_by(role='admin').first()
    out.append(f'| {admin.full_name} | `{admin.email}` | Quản trị tài khoản (không xem dữ liệu học tập) |')
    for e in CourseEnrollment.query.filter_by(role='coordinator').limit(1):
        u = db.session.get(User, e.user_id); out.append(f'| {u.full_name} | `{u.email}` | Quản lý học phần (tất cả học phần) |')
    out += ['', '## Giảng viên', '', '| Họ tên | Email | Học phần phụ trách |', '|---|---|---|']
    for u in User.query.filter_by(role='instructor').order_by(User.id):
        cs = [db.session.get(CourseOffering, e.course_id) for e in CourseEnrollment.query.filter_by(user_id=u.id, role='instructor')]
        out.append(f'| {u.full_name} | `{u.email}` | ' + '; '.join(f'{c.title} ({c.code})' for c in cs) + ' |')
    out += ['', '## Học phần và dự án', '']
    for c in CourseOffering.query.order_by(CourseOffering.id):
        a = Assignment.query.filter_by(course_id=c.id).first()
        t = db.session.get(User, CourseEnrollment.query.filter_by(course_id=c.id, role='instructor').first().user_id)
        out += [f'### {c.title} ({c.code}) — {t.full_name}', '', f'Đề bài: {a.title}', '', '| Dự án | Đội | Trạng thái | Trưởng nhóm | Thành viên |', '|---|---|---|---|---|']
        for p in Project.query.filter_by(assignment_id=a.id).order_by(Project.id):
            ms = AssignmentMembership.query.filter_by(project_id=p.id, status='active').all()
            lead = next((db.session.get(User, m.user_id) for m in ms if m.role == 'leader'), None)
            mem = ', '.join(db.session.get(User, m.user_id).full_name for m in ms if m.role != 'leader')
            out.append(f'| {p.name} | {p.team_name} | {"Đang hoạt động" if p.status == "active" else "Chờ duyệt" if p.status == "pending" else p.status} | {lead.full_name if lead else "—"} | {mem} |')
        free = [db.session.get(User, e.user_id).full_name for e in CourseEnrollment.query.filter_by(course_id=c.id, role='student')
                if not AssignmentMembership.query.filter_by(assignment_id=a.id, user_id=e.user_id, status='active').first()]
        out += ['', f'Chưa có nhóm: {", ".join(free) or "—"}', '']
    out += ['## Sinh viên', '', '| Họ tên | Email | Mã sinh viên | Dự án (vai trò) |', '|---|---|---|---|']
    for u in User.query.filter_by(role='user').order_by(User.id):
        e = CourseEnrollment.query.filter_by(user_id=u.id, role='student').first()
        if not e:
            continue
        ps = [f'{db.session.get(Project, m.project_id).name}{" (trưởng nhóm)" if m.role == "leader" else ""}' for m in AssignmentMembership.query.filter_by(user_id=u.id, status='active')]
        out.append(f'| {u.full_name} | `{u.email}` | {e.student_code} | {"; ".join(ps) or "—"} |')
    (ROOT / 'docs' / 'TAI_KHOAN_DEMO.md').write_text('\n'.join(out) + '\n', encoding='utf-8')
    print('Đã ghi docs/TAI_KHOAN_DEMO.md:', User.query.count(), 'tài khoản')
