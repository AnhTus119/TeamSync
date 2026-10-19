"""Một lớp + một dự án demo nhỏ. Dữ liệu mô phỏng nhiều dự án do M11 tạo trong m11_analytics/seed.py."""
from datetime import date, timedelta

from ..common.utils import now
from ..extensions import db
from ..models import Course, Project, ProjectMember, Task, User


def seed():
    u = {x.email.split("@")[0]: x for x in User.query.all()}
    course = Course(code="LTWEB_01", name="Lập trình Web — Lớp 01", lecturer_id=u["gv"].id)
    db.session.add(course)
    db.session.flush()
    project = Project(course_id=course.id, name="TeamSync demo", description="Dự án mẫu",
                      due_date=date.today() + timedelta(days=14), created_by=u["sv1"].id)
    db.session.add(project)
    db.session.flush()
    for key, role in (("sv1", "leader"), ("sv2", "member"), ("sv3", "member")):
        db.session.add(ProjectMember(project_id=project.id, user_id=u[key].id, project_role=role))
    for title, status, who, days in [("Thiết kế ERD", "done", "sv1", -3),
                                     ("API đăng nhập", "review", "sv2", 1),
                                     ("Trang Kanban", "in_progress", "sv3", 2),
                                     ("Dashboard", "todo", "sv3", 6)]:
        db.session.add(Task(project_id=project.id, title=title, status=status, assignee_id=u[who].id,
                            due_date=date.today() + timedelta(days=days), created_by=u["sv1"].id,
                            completed_at=now() if status == "done" else None))
    db.session.flush()
