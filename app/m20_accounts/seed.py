"""Tài khoản và không gian làm việc mẫu. Mật khẩu chung: 123456"""
from ..extensions import db
from ..models import User, Workspace, WorkspaceMember

ACCOUNTS = [
    ("admin@teamsync.local", "Quản trị viên", "admin"),
    ("gv@teamsync.local", "Giảng viên A (giám sát)", "user"),
    ("sv1@teamsync.local", "Sinh viên 1 (quản lý dự án)", "user"),
    ("sv2@teamsync.local", "Sinh viên 2", "user"),
    ("sv3@teamsync.local", "Sinh viên 3", "user"),
    ("sv4@teamsync.local", "Sinh viên 4 (ngoài dự án)", "user"),
]


def seed():
    users = {}
    for email, name, role in ACCOUNTS:
        u = User(email=email, full_name=name, role=role)
        u.set_password("123456")
        db.session.add(u)
        users[email.split("@")[0]] = u
    db.session.flush()
    ws = Workspace(name="Lớp Lập trình Web 01", description="Không gian làm việc của lớp", owner_id=users["gv"].id)
    db.session.add(ws)
    db.session.flush()
    db.session.add(WorkspaceMember(workspace_id=ws.id, user_id=users["gv"].id, role="owner"))
    for key in ("sv1", "sv2", "sv3", "sv4"):
        db.session.add(WorkspaceMember(workspace_id=ws.id, user_id=users[key].id, role="member"))
    db.session.flush()
