"""Dữ liệu mô phỏng để thử nghiệm luật cảnh báo. Chủ sở hữu: Thành viên 3.
Ngoại lệ duy nhất M17 được GHI vào bảng M06 — chỉ trong seed, không bao giờ trong API.

Mỗi thành viên mô phỏng có một "tính cách" quyết định khi nào bắt đầu, có bị trả lại không, xong sớm hay muộn.
Cố định seed ngẫu nhiên nên lần nào chạy cũng ra cùng dữ liệu.
"""
import random
from datetime import date, timedelta

from ..extensions import db
from ..m06_projects.seed import build_task
from ..models import PeerReview, Project, ProjectMember, User, Workspace, WorkspaceMember

PROFILES = {  # (bắt đầu sau bao nhiêu % thời gian, xác suất bị trả lại, số ngày khựng lại khi đang làm)
    "chăm chỉ": (0.1, 0.1, 0),
    "trung bình": (0.4, 0.3, 2),
    "chậm": (0.8, 0.5, 5),
}
PEOPLE = [("Mô phỏng An", "chăm chỉ"), ("Mô phỏng Bình", "trung bình"), ("Mô phỏng Chi", "chậm"),
          ("Mô phỏng Dũng", "trung bình"), ("Mô phỏng Hà", "chăm chỉ"), ("Mô phỏng Khoa", "chậm")]
PROJECTS = ["Mô phỏng: Website câu lạc bộ", "Mô phỏng: Đề tài khảo sát sinh viên", "Mô phỏng: Ứng dụng đặt lịch"]


def simulate_events(rng, profile, created, due, worker, manager):
    """Sinh chuỗi sự kiện [(days_ago, field, old, new, note, user)] cho một việc. days_ago tính từ hôm nay."""
    start_pct, p_return, stall = PROFILES[profile]
    span = created - due  # created, due là days_ago (số lớn = xa hơn trong quá khứ)
    ev = [(created,)]
    day = created - max(1, round(span * start_pct + rng.uniform(-0.5, 1)))
    if day < 0:
        return ev
    ev.append((day, "status", "todo", "in_progress", None, worker))
    day -= stall + rng.randint(1, 3)
    while day >= 0:
        ev.append((day, "attachment", None, f"bang-chung-{rng.randint(100, 999)}.pdf", None, worker))
        ev.append((day, "status", "in_progress", "review", None, worker))
        day -= rng.randint(0, 1)
        if day < 0:
            return ev
        if rng.random() < p_return:
            ev.append((day, "review", "return", "in_progress", "Chưa đạt yêu cầu, cần bổ sung", manager))
            ev.append((day, "status", "review", "in_progress", None, manager))
            day -= rng.randint(1, 3)
            continue
        ev.append((day, "review", "approve", "done", None, manager))
        ev.append((day, "status", "review", "done", None, manager))
        return ev
    return ev


def seed():
    rng = random.Random(2026)
    admin = User.query.filter_by(email="admin@teamsync.local").one()
    ws = Workspace(name="Dữ liệu mô phỏng", description="Dự án mô phỏng để đánh giá luật cảnh báo", owner_id=admin.id)
    db.session.add(ws)
    db.session.flush()
    db.session.add(WorkspaceMember(workspace_id=ws.id, user_id=admin.id, role="owner"))
    people = []
    for i, (name, profile) in enumerate(PEOPLE, 1):
        u = User(email=f"sim{i}@teamsync.local", full_name=name, role="user")
        u.set_password("123456")
        db.session.add(u)
        people.append((u, profile))
    db.session.flush()
    for u, _ in people:
        db.session.add(WorkspaceMember(workspace_id=ws.id, user_id=u.id, role="member"))
    today = date.today()
    for pi, pname in enumerate(PROJECTS):
        team = people[pi * 2: pi * 2 + 2] + [people[(pi * 2 + 2) % len(people)]]
        manager = team[0][0]
        p = Project(workspace_id=ws.id, name=pname, description="Sinh tự động", created_by=manager.id,
                    start_date=today - timedelta(days=35), due_date=today + timedelta(days=5))
        db.session.add(p)
        db.session.flush()
        for j, (u, _) in enumerate(team):
            db.session.add(ProjectMember(project_id=p.id, user_id=u.id, project_role="manager" if j == 0 else "member"))
        tasks = []
        for k in range(12):
            worker, profile = team[k % len(team)]
            created = rng.randint(6, 34)
            due = created - rng.randint(4, 10)
            events = simulate_events(rng, profile, created, due, worker, manager)
            tasks.append(build_task(p, f"Việc {k + 1:02d}", worker, manager, events,
                                    points=rng.choice((1, 2, 3, 5)), due_date=today - timedelta(days=due)))
        for a, b in ((u1, u2) for u1, _ in team for u2, _ in team if u1 is not u2):
            db.session.add(PeerReview(project_id=p.id, reviewer_id=a.id, reviewee_id=b.id, score=rng.randint(3, 5)))
    db.session.flush()
