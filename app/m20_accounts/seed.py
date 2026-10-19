"""Tài khoản mẫu cho cả nhóm dùng. Mật khẩu chung: 123456"""
from ..extensions import db
from ..models import User

ACCOUNTS = [
    ("admin@teamsync.local", "Quản trị viên", "admin"),
    ("gv@teamsync.local", "Giảng viên A", "lecturer"),
    ("sv1@teamsync.local", "Sinh viên 1 (trưởng nhóm)", "student"),
    ("sv2@teamsync.local", "Sinh viên 2", "student"),
    ("sv3@teamsync.local", "Sinh viên 3", "student"),
    ("sv4@teamsync.local", "Sinh viên 4 (ngoài nhóm)", "student"),
]


def seed():
    for email, name, role in ACCOUNTS:
        u = User(email=email, full_name=name, role=role)
        u.set_password("123456")
        db.session.add(u)
    db.session.flush()
