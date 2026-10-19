"""Bảng của M10 — LMS/LCMS & tài nguyên học tập. Chủ sở hữu: Thành viên 2."""
from ..common.utils import iso, now
from ..extensions import db

TASK_STATUSES = ("todo", "in_progress", "review", "done")
PRIORITIES = ("low", "medium", "high")


class Course(db.Model):
    """Lớp học phần, do giảng viên tạo."""
    __tablename__ = "course"
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(30), unique=True, nullable=False)    # vd: "LTWEB_K66_01"
    name = db.Column(db.String(200), nullable=False)
    lecturer_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=now)

    def to_dict(self):
        return {"id": self.id, "code": self.code, "name": self.name,
                "lecturer_id": self.lecturer_id, "created_at": iso(self.created_at)}


class Project(db.Model):
    """Dự án nhóm (một nhóm làm một bài tập nhóm trong một lớp)."""
    __tablename__ = "project"
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("course.id"), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default="")
    due_date = db.Column(db.Date)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=now)

    course = db.relationship("Course")
    members = db.relationship("ProjectMember", cascade="all, delete-orphan", passive_deletes=True)

    def to_dict(self):
        return {"id": self.id, "course_id": self.course_id, "name": self.name,
                "description": self.description, "due_date": iso(self.due_date),
                "created_by": self.created_by, "created_at": iso(self.created_at)}


class Task(db.Model):
    __tablename__ = "task"
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id", ondelete="CASCADE"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default="")
    status = db.Column(db.String(20), nullable=False, default="todo")
    priority = db.Column(db.String(10), nullable=False, default="medium")
    due_date = db.Column(db.Date)
    assignee_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=now)
    updated_at = db.Column(db.DateTime, nullable=False, default=now, onupdate=now)
    completed_at = db.Column(db.DateTime)  # thời điểm được duyệt Done — M11 dùng để tính đúng/trễ hạn

    def to_dict(self):
        return {"id": self.id, "project_id": self.project_id, "title": self.title,
                "description": self.description, "status": self.status, "priority": self.priority,
                "due_date": iso(self.due_date), "assignee_id": self.assignee_id,
                "created_by": self.created_by, "created_at": iso(self.created_at),
                "updated_at": iso(self.updated_at), "completed_at": iso(self.completed_at)}


class Comment(db.Model):
    __tablename__ = "comment"
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey("task.id", ondelete="CASCADE"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    content = db.Column(db.Text, nullable=False)
    is_hidden = db.Column(db.Boolean, nullable=False, default=False)  # quản trị viên ẩn nội dung vi phạm
    created_at = db.Column(db.DateTime, nullable=False, default=now)

    def to_dict(self):
        return {"id": self.id, "task_id": self.task_id, "user_id": self.user_id,
                "content": self.content, "is_hidden": self.is_hidden, "created_at": iso(self.created_at)}


class Attachment(db.Model):
    """Minh chứng: file tải lên hoặc đường link (GitHub, Drive...)."""
    __tablename__ = "attachment"
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey("task.id", ondelete="CASCADE"), nullable=False)
    uploaded_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    kind = db.Column(db.String(10), nullable=False)  # file | link
    url = db.Column(db.String(500), nullable=False)  # đường dẫn file đã lưu hoặc link ngoài
    filename = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, nullable=False, default=now)

    def to_dict(self):
        return {"id": self.id, "task_id": self.task_id, "uploaded_by": self.uploaded_by,
                "kind": self.kind, "url": self.url, "filename": self.filename,
                "created_at": iso(self.created_at)}


class TaskHistory(db.Model):
    """Mỗi thay đổi trên task là 1 dòng. field ∈ created | status | assignee_id | due_date | review | attachment."""
    __tablename__ = "task_history"
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey("task.id", ondelete="CASCADE"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    field = db.Column(db.String(30), nullable=False)
    old_value = db.Column(db.String(255))
    new_value = db.Column(db.String(255))
    note = db.Column(db.Text)  # lý do trả lại, ghi chú tiến độ...
    created_at = db.Column(db.DateTime, nullable=False, default=now)

    def to_dict(self):
        return {"id": self.id, "task_id": self.task_id, "user_id": self.user_id, "field": self.field,
                "old_value": self.old_value, "new_value": self.new_value, "note": self.note,
                "created_at": iso(self.created_at)}
