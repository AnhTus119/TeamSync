"""Bảng của M06 — Quản lý khoa học (quản lý dự án). Chủ sở hữu: Thành viên 2."""
import json

from ..common.utils import iso, now
from ..extensions import db

TASK_STATUSES = ("todo", "in_progress", "review", "done")
PRIORITIES = ("low", "medium", "high")
POINTS = (1, 2, 3, 5)  # điểm khối lượng của một việc
MILESTONE_STATUSES = ("open", "pending_review", "accepted", "changes_requested")


class ProjectTemplate(db.Model):
    """Mẫu dự án. milestones_json = [{"title", "offset_days"}]; tasks_json = [{"title", "milestone", "points", "offset_days"}]."""
    __tablename__ = "project_template"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    description = db.Column(db.Text, default="")
    milestones_json = db.Column(db.Text, nullable=False, default="[]")
    tasks_json = db.Column(db.Text, nullable=False, default="[]")
    created_at = db.Column(db.DateTime, nullable=False, default=now)

    @property
    def milestones(self):
        return json.loads(self.milestones_json or "[]")

    @property
    def tasks(self):
        return json.loads(self.tasks_json or "[]")

    def to_dict(self):
        return {"id": self.id, "name": self.name, "description": self.description,
                "milestones": self.milestones, "tasks": self.tasks}


class Project(db.Model):
    __tablename__ = "project"
    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey("workspace.id", ondelete="CASCADE"), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default="")
    start_date = db.Column(db.Date)
    due_date = db.Column(db.Date)
    template_id = db.Column(db.Integer, db.ForeignKey("project_template.id"))
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=now)

    workspace = db.relationship("Workspace")
    members = db.relationship("ProjectMember", cascade="all, delete-orphan", passive_deletes=True)
    tasks = db.relationship("Task", cascade="all, delete-orphan", passive_deletes=True)
    milestones = db.relationship("Milestone", cascade="all, delete-orphan", passive_deletes=True,
                                 order_by="Milestone.due_date")

    def to_dict(self):
        return {"id": self.id, "workspace_id": self.workspace_id, "name": self.name,
                "description": self.description, "start_date": iso(self.start_date),
                "due_date": iso(self.due_date), "template_id": self.template_id,
                "created_by": self.created_by, "created_at": iso(self.created_at)}


class Milestone(db.Model):
    """Cột mốc. open → pending_review (quản lý gửi nghiệm thu) → accepted | changes_requested (giám sát)."""
    __tablename__ = "milestone"
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id", ondelete="CASCADE"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default="")
    due_date = db.Column(db.Date)
    status = db.Column(db.String(20), nullable=False, default="open")
    review_note = db.Column(db.Text)
    reviewed_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    reviewed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, nullable=False, default=now)

    def to_dict(self):
        return {"id": self.id, "project_id": self.project_id, "title": self.title,
                "description": self.description, "due_date": iso(self.due_date), "status": self.status,
                "review_note": self.review_note, "reviewed_by": self.reviewed_by,
                "reviewed_at": iso(self.reviewed_at), "created_at": iso(self.created_at)}


class Task(db.Model):
    __tablename__ = "task"
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id", ondelete="CASCADE"), nullable=False)
    milestone_id = db.Column(db.Integer, db.ForeignKey("milestone.id", ondelete="SET NULL"))
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default="")
    status = db.Column(db.String(20), nullable=False, default="todo")
    priority = db.Column(db.String(10), nullable=False, default="medium")
    points = db.Column(db.Integer, nullable=False, default=1)
    due_date = db.Column(db.Date)
    assignee_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=now)
    updated_at = db.Column(db.DateTime, nullable=False, default=now, onupdate=now)
    completed_at = db.Column(db.DateTime)  # thời điểm được duyệt done

    assignee = db.relationship("User", foreign_keys=[assignee_id])
    attachments = db.relationship("Attachment", cascade="all, delete-orphan", passive_deletes=True)
    history = db.relationship("TaskHistory", cascade="all, delete-orphan", passive_deletes=True,
                              order_by="TaskHistory.id")
    depends_on = db.relationship("TaskDependency", foreign_keys="TaskDependency.task_id",
                                 cascade="all, delete-orphan", passive_deletes=True)

    def to_dict(self):
        return {"id": self.id, "project_id": self.project_id, "milestone_id": self.milestone_id,
                "title": self.title, "description": self.description, "status": self.status,
                "priority": self.priority, "points": self.points, "due_date": iso(self.due_date),
                "assignee_id": self.assignee_id,
                "assignee": self.assignee.brief() if self.assignee else None,
                "created_by": self.created_by, "created_at": iso(self.created_at),
                "updated_at": iso(self.updated_at), "completed_at": iso(self.completed_at)}


class TaskDependency(db.Model):
    """task_id chỉ được bắt đầu khi depends_on_id đã done."""
    __tablename__ = "task_dependency"
    __table_args__ = (db.UniqueConstraint("task_id", "depends_on_id"),)
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey("task.id", ondelete="CASCADE"), nullable=False)
    depends_on_id = db.Column(db.Integer, db.ForeignKey("task.id", ondelete="CASCADE"), nullable=False)

    depends_on = db.relationship("Task", foreign_keys=[depends_on_id])


class Comment(db.Model):
    __tablename__ = "comment"
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey("task.id", ondelete="CASCADE"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    content = db.Column(db.Text, nullable=False)
    is_hidden = db.Column(db.Boolean, nullable=False, default=False)  # quản trị viên ẩn nội dung vi phạm
    created_at = db.Column(db.DateTime, nullable=False, default=now)

    user = db.relationship("User")

    def to_dict(self):
        return {"id": self.id, "task_id": self.task_id, "user": self.user.brief(),
                "content": "[Nội dung đã bị ẩn]" if self.is_hidden else self.content,
                "is_hidden": self.is_hidden, "created_at": iso(self.created_at)}


class Attachment(db.Model):
    """Minh chứng: file tải lên hoặc link (GitHub, Drive...)."""
    __tablename__ = "attachment"
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey("task.id", ondelete="CASCADE"), nullable=False)
    uploaded_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    kind = db.Column(db.String(10), nullable=False)  # file | link
    url = db.Column(db.String(500), nullable=False)  # tên file đã lưu hoặc link ngoài
    filename = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, nullable=False, default=now)

    def to_dict(self):
        return {"id": self.id, "task_id": self.task_id, "uploaded_by": self.uploaded_by, "kind": self.kind,
                "url": f"/api/attachments/{self.id}/download" if self.kind == "file" else self.url,
                "filename": self.filename, "created_at": iso(self.created_at)}


class TaskHistory(db.Model):
    """Mỗi thay đổi trên task là 1 dòng.
    field ∈ created | status | assignee_id | due_date | points | review | attachment | dependency."""
    __tablename__ = "task_history"
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey("task.id", ondelete="CASCADE"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    field = db.Column(db.String(30), nullable=False)
    old_value = db.Column(db.String(255))
    new_value = db.Column(db.String(255))
    note = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False, default=now)

    user = db.relationship("User")

    def to_dict(self):
        return {"id": self.id, "task_id": self.task_id, "user": self.user.brief(), "field": self.field,
                "old_value": self.old_value, "new_value": self.new_value, "note": self.note,
                "created_at": iso(self.created_at)}
