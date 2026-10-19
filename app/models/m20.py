"""Bảng của M20 — Tài khoản, SSO & phân quyền. Chủ sở hữu: Thành viên 1."""
from werkzeug.security import check_password_hash, generate_password_hash

from ..common.utils import iso, now
from ..extensions import db

ROLES = ("admin", "lecturer", "student")       # vai trò hệ thống
PROJECT_ROLES = ("leader", "member")           # vai trò trong một dự án


class User(db.Model):
    __tablename__ = "user"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="student")
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=now)

    def set_password(self, raw):
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw):
        return check_password_hash(self.password_hash, raw)

    def to_dict(self):  # KHÔNG bao giờ trả password_hash
        return {"id": self.id, "email": self.email, "full_name": self.full_name,
                "role": self.role, "is_active": self.is_active, "created_at": iso(self.created_at)}


class ProjectMember(db.Model):
    __tablename__ = "project_member"
    __table_args__ = (db.UniqueConstraint("project_id", "user_id"),)
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id", ondelete="CASCADE"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    project_role = db.Column(db.String(20), nullable=False, default="member")
    joined_at = db.Column(db.DateTime, nullable=False, default=now)

    user = db.relationship("User")

    def to_dict(self):
        return {"project_id": self.project_id, "user": self.user.to_dict(),
                "project_role": self.project_role, "joined_at": iso(self.joined_at)}


class Invitation(db.Model):
    __tablename__ = "invitation"
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id", ondelete="CASCADE"), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    token = db.Column(db.String(64), unique=True, nullable=False)
    invited_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="pending")  # pending | accepted | revoked
    created_at = db.Column(db.DateTime, nullable=False, default=now)

    def to_dict(self):
        return {"id": self.id, "project_id": self.project_id, "email": self.email,
                "token": self.token, "status": self.status, "created_at": iso(self.created_at)}
