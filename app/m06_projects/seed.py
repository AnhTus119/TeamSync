"""Mẫu dự án + một dự án demo có đủ tình huống. Chủ sở hữu: Thành viên 2."""
import json
from datetime import date, datetime, time, timedelta

from ..extensions import db
from ..models import (Attachment, Comment, Milestone, Project, ProjectMember, ProjectTemplate, Task,
                      TaskDependency, TaskHistory, User, Workspace)

TEMPLATES = [
    ("Bài tập nhóm", "Bài tập nhóm của một học phần",
     [{"title": "Phân tích yêu cầu", "offset_days": 4}, {"title": "Xây dựng", "offset_days": 11},
      {"title": "Báo cáo và demo", "offset_days": 14}],
     [{"title": "Chốt đề tài và phân công", "milestone": "Phân tích yêu cầu", "points": 1},
      {"title": "Thiết kế cơ sở dữ liệu", "milestone": "Phân tích yêu cầu", "points": 3},
      {"title": "Code chức năng chính", "milestone": "Xây dựng", "points": 5},
      {"title": "Kiểm thử", "milestone": "Xây dựng", "points": 2},
      {"title": "Viết báo cáo", "milestone": "Báo cáo và demo", "points": 3},
      {"title": "Chuẩn bị slide và demo", "milestone": "Báo cáo và demo", "points": 2}]),
    ("Đề tài nghiên cứu", "Đề tài nghiên cứu khoa học sinh viên",
     [{"title": "Đề cương", "offset_days": 14}, {"title": "Thu thập và xử lý dữ liệu", "offset_days": 45},
      {"title": "Báo cáo tổng kết", "offset_days": 75}],
     [{"title": "Tổng quan tài liệu", "milestone": "Đề cương", "points": 3},
      {"title": "Viết đề cương", "milestone": "Đề cương", "points": 3},
      {"title": "Thiết kế khảo sát", "milestone": "Thu thập và xử lý dữ liệu", "points": 2},
      {"title": "Thu thập dữ liệu", "milestone": "Thu thập và xử lý dữ liệu", "points": 5},
      {"title": "Phân tích kết quả", "milestone": "Báo cáo tổng kết", "points": 5},
      {"title": "Viết báo cáo tổng kết", "milestone": "Báo cáo tổng kết", "points": 3}]),
    ("Sự kiện câu lạc bộ", "Tổ chức một sự kiện",
     [{"title": "Lên kế hoạch", "offset_days": 7}, {"title": "Chuẩn bị", "offset_days": 18},
      {"title": "Tổ chức và tổng kết", "offset_days": 25}],
     [{"title": "Kế hoạch và ngân sách", "milestone": "Lên kế hoạch", "points": 3},
      {"title": "Liên hệ địa điểm, khách mời", "milestone": "Chuẩn bị", "points": 3},
      {"title": "Truyền thông", "milestone": "Chuẩn bị", "points": 2},
      {"title": "Hậu cần ngày sự kiện", "milestone": "Tổ chức và tổng kết", "points": 3},
      {"title": "Báo cáo tổng kết", "milestone": "Tổ chức và tổng kết", "points": 1}]),
    ("Phát triển phần mềm", "Dự án phần mềm nhỏ theo vòng lặp",
     [{"title": "Yêu cầu và thiết kế", "offset_days": 7}, {"title": "Sprint 1", "offset_days": 21},
      {"title": "Sprint 2 và phát hành", "offset_days": 35}],
     [{"title": "Viết user story", "milestone": "Yêu cầu và thiết kế", "points": 2},
      {"title": "Thiết kế kiến trúc và API", "milestone": "Yêu cầu và thiết kế", "points": 3},
      {"title": "Chức năng lõi", "milestone": "Sprint 1", "points": 5},
      {"title": "Kiểm thử tự động", "milestone": "Sprint 1", "points": 3},
      {"title": "Hoàn thiện giao diện", "milestone": "Sprint 2 và phát hành", "points": 3},
      {"title": "Triển khai", "milestone": "Sprint 2 và phát hành", "points": 2}]),
]


def at(days_ago, hour=9):
    return datetime.combine(date.today() - timedelta(days=days_ago), time(hour, 0))


def build_task(project, title, assignee, creator, events, **fields):
    """events: [(days_ago, field, old, new, note, user)] theo thứ tự thời gian. Trạng thái cuối lấy từ events."""
    created = events[0][0] if events else 0
    t = Task(project_id=project.id, title=title, assignee_id=assignee.id if assignee else None,
             created_by=creator.id, created_at=at(created, 8), updated_at=at(created, 8), **fields)
    db.session.add(t)
    db.session.flush()
    db.session.add(TaskHistory(task_id=t.id, user_id=creator.id, field="created", new_value=title,
                               created_at=at(created, 8)))
    for i, (days_ago, field, old, new, note, user) in enumerate(events[1:], 1):
        when = at(days_ago, 9) + timedelta(minutes=10 * i)
        db.session.add(TaskHistory(task_id=t.id, user_id=user.id, field=field, old_value=old, new_value=new,
                                   note=note, created_at=when))
        if field == "attachment":
            db.session.add(Attachment(task_id=t.id, uploaded_by=user.id, kind="link", filename=new,
                                      url=f"https://github.com/example/teamsync/{new}", created_at=when))
        if field == "status":
            t.status = new
            t.completed_at = when if new == "done" else None
        t.updated_at = when
    db.session.flush()
    return t


def seed():
    for name, desc, ms, tasks in TEMPLATES:
        db.session.add(ProjectTemplate(name=name, description=desc, milestones_json=json.dumps(ms, ensure_ascii=False),
                                       tasks_json=json.dumps(tasks, ensure_ascii=False)))
    u = {x.email.split("@")[0]: x for x in User.query.all()}
    ws = Workspace.query.filter_by(name="Lớp Lập trình Web 01").one()
    tpl = ProjectTemplate.query.filter_by(name="Bài tập nhóm").first()
    db.session.flush()
    today = date.today()
    p = Project(workspace_id=ws.id, name="TeamSync demo", description="Dự án mẫu có đủ các tình huống để demo",
                start_date=today - timedelta(days=10), due_date=today + timedelta(days=10), template_id=tpl.id,
                created_by=u["sv1"].id, created_at=at(10, 8))
    db.session.add(p)
    db.session.flush()
    for key, role in (("sv1", "manager"), ("sv2", "member"), ("sv3", "member"), ("gv", "supervisor")):
        db.session.add(ProjectMember(project_id=p.id, user_id=u[key].id, project_role=role, joined_at=at(10, 8)))
    m1 = Milestone(project_id=p.id, title="Phân tích yêu cầu", due_date=today - timedelta(days=4), status="accepted",
                   reviewed_by=u["gv"].id, reviewed_at=at(3), review_note="Đạt")
    m2 = Milestone(project_id=p.id, title="Xây dựng", due_date=today + timedelta(days=5))
    m3 = Milestone(project_id=p.id, title="Báo cáo và demo", due_date=today + timedelta(days=10))
    db.session.add_all([m1, m2, m3])
    db.session.flush()
    sv1, sv2, sv3 = u["sv1"], u["sv2"], u["sv3"]
    erd = build_task(p, "Thiết kế cơ sở dữ liệu", sv1, sv1, [
        (10,), (9, "status", "todo", "in_progress", None, sv1), (7, "attachment", None, "erd.png", None, sv1),
        (7, "status", "in_progress", "review", None, sv1), (6, "review", "approve", "done", None, sv1),
        (6, "status", "review", "done", None, sv1)],
        milestone_id=m1.id, points=3, due_date=today - timedelta(days=5), priority="high")
    api = build_task(p, "API đăng nhập và phân quyền", sv2, sv1, [
        (9,), (8, "status", "todo", "in_progress", None, sv2), (5, "attachment", None, "pull/12", None, sv2),
        (5, "status", "in_progress", "review", None, sv2),
        (4, "review", "return", "in_progress", "Thiếu kiểm tra quyền khi xóa thành viên", sv1),
        (4, "status", "review", "in_progress", None, sv1), (1, "attachment", None, "pull/15", None, sv2),
        (1, "status", "in_progress", "review", None, sv2)],
        milestone_id=m2.id, points=5, due_date=today + timedelta(days=2), priority="high")
    kanban = build_task(p, "Giao diện bảng Kanban", sv3, sv1, [
        (9,), (7, "status", "todo", "in_progress", None, sv3)],
        milestone_id=m2.id, points=3, due_date=today + timedelta(days=3))
    dash = build_task(p, "Trang dashboard", sv3, sv1, [(8,)],
                      milestone_id=m2.id, points=3, due_date=today + timedelta(days=1))
    test = build_task(p, "Kiểm thử Postman", sv2, sv1, [(8,)],
                      milestone_id=m2.id, points=2, due_date=today - timedelta(days=1))
    build_task(p, "Viết báo cáo", sv1, sv1, [(6,)], milestone_id=m3.id, points=3, due_date=today + timedelta(days=9))
    build_task(p, "Chuẩn bị slide và demo", None, sv1, [(6,)], milestone_id=m3.id, points=2,
               due_date=today + timedelta(days=10))
    db.session.add_all([TaskDependency(task_id=dash.id, depends_on_id=kanban.id),
                        TaskDependency(task_id=kanban.id, depends_on_id=erd.id),
                        TaskDependency(task_id=test.id, depends_on_id=api.id)])
    db.session.add(Comment(task_id=api.id, user_id=sv2.id, content="Em đã sửa phần kiểm tra quyền, nhờ anh xem lại",
                           created_at=at(1, 15)))
    db.session.flush()
