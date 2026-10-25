"""Bảng của M20 — Tài khoản, SSO và phân quyền. Chủ sở hữu: Thành viên 1."""
from werkzeug.security import check_password_hash, generate_password_hash

from ..common.utils import iso, now
from ..extensions import db

ROLES = ("admin", "user")                          # vai trò hệ thống
WORKSPACE_ROLES = ("owner", "member")              # vai trò trong không gian làm việc
PROJECT_ROLES = ("manager", "member", "supervisor")  # vai trò trong một dự án


class User(db.Model):
    __tablename__ = "user"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="user")
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=now)

    def set_password(self, raw):
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw):
        return check_password_hash(self.password_hash, raw)

    def to_dict(self):  # KHÔNG bao giờ trả password_hash
        return {"id": self.id, "email": self.email, "full_name": self.full_name,
                "role": self.role, "is_active": self.is_active, "created_at": iso(self.created_at)}

    def brief(self):
        return {"id": self.id, "full_name": self.full_name, "email": self.email}


class Workspace(db.Model):
    """Không gian làm việc: gom nhiều dự án của một nhóm người (một lớp, CLB, công ty nhỏ)."""
    __tablename__ = "workspace"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default="")
    owner_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=now)

    members = db.relationship("WorkspaceMember", cascade="all, delete-orphan", passive_deletes=True)

    def to_dict(self):
        return {"id": self.id, "name": self.name, "description": self.description,
                "owner_id": self.owner_id, "created_at": iso(self.created_at)}


class WorkspaceMember(db.Model):
    __tablename__ = "workspace_member"
    __table_args__ = (db.UniqueConstraint("workspace_id", "user_id"),)
    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey("workspace.id", ondelete="CASCADE"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="member")
    joined_at = db.Column(db.DateTime, nullable=False, default=now)

    user = db.relationship("User")
    workspace = db.relationship("Workspace", overlaps="members")

    def to_dict(self):
        return {"workspace_id": self.workspace_id, "user": self.user.to_dict(),
                "role": self.role, "joined_at": iso(self.joined_at)}


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
    project_role = db.Column(db.String(20), nullable=False, default="member")  # member | supervisor
    token = db.Column(db.String(64), unique=True, nullable=False)
    invited_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="pending")  # pending | accepted | revoked
    created_at = db.Column(db.DateTime, nullable=False, default=now)

    def to_dict(self):
        return {"id": self.id, "project_id": self.project_id, "email": self.email,
                "project_role": self.project_role, "token": self.token, "status": self.status,
                "created_at": iso(self.created_at)}
