"""Dữ liệu mô phỏng để thử nghiệm luật cảnh báo. Chủ sở hữu: Thành viên 3.
Ngoại lệ duy nhất M17 được GHI vào bảng M06 — chỉ trong seed, không bao giờ trong API.

Tạo 4 dự án mô phỏng (cùng workspace "Lớp Lập trình Web 01") + vài đánh giá chéo cho dự án demo.
  - random cố định seed → chạy lại cho cùng kết quả (ngày tính tương đối so với hôm nay)
  - mỗi thành viên có KIỂU LÀM VIỆC khác nhau: steady (đều đặn), crunch (nước rút), rework (hay bị trả lại),
    slow (chậm, hay quá hạn / bỏ dở)
  - lịch sử việc được ghi bằng m06_projects.seed.build_task nên luật cảnh báo chạy lại theo ngày được
Chỉ dùng tài khoản có sẵn gv, sv1, sv2, sv3 (sv4 giữ nguyên "ngoài dự án" cho kiểm thử phân quyền).
"""
import random
from datetime import date, timedelta

from ..extensions import db
from ..m06_projects.seed import at, build_task
from ..models import Milestone, PeerReview, Project, ProjectMember, TaskDependency, User, Workspace

SEED = 9  # đã chọn để 4 dự án mô phỏng có đủ đỏ / vàng / xanh

# (tên, mô tả, ngày bắt đầu so với hôm nay, ngày hạn so với hôm nay, quản lý, kiểu làm việc {user: profile}, số việc)
PROJECTS = [
    ("Đồ án Cơ sở dữ liệu — Nhóm A", "Thiết kế và cài đặt CSDL quản lý thư viện (đã kết thúc, đang chờ nghiệm thu)",
     -42, -4, "sv2", {"sv2": "steady", "sv1": "slow", "sv3": "rework"}, 14),
    ("Khảo sát nhu cầu CLB Tin học", "Khảo sát 120 sinh viên và tổng hợp báo cáo (tiến độ tốt)",
     -28, 16, "sv3", {"sv3": "steady", "sv1": "steady", "sv2": "crunch"}, 12),
    ("Website sự kiện Open Day", "Website đăng ký tham dự Open Day (trễ tiến độ nghiêm trọng)",
     -24, 6, "sv1", {"sv1": "crunch", "sv2": "slow", "sv3": "slow"}, 15),
    ("Ứng dụng quản lý kho", "Ứng dụng nhập/xuất kho cho cửa hàng nhỏ (tiến độ trung bình)",
     -20, 22, "sv2", {"sv2": "rework", "sv1": "steady", "sv3": "crunch"}, 13),
]

TASK_TITLES = ["Chốt phạm vi", "Phân tích yêu cầu", "Thiết kế giao diện", "Thiết kế cơ sở dữ liệu", "Xây dựng API",
               "Xây dựng giao diện", "Tích hợp hệ thống", "Viết kiểm thử", "Sửa lỗi đợt 1", "Sửa lỗi đợt 2",
               "Tối ưu hiệu năng", "Viết tài liệu", "Chuẩn bị dữ liệu mẫu", "Quay video demo", "Viết báo cáo",
               "Làm slide thuyết trình", "Rà soát bảo mật"]
MILESTONES = ["Khởi động và phân tích", "Xây dựng", "Hoàn thiện và báo cáo"]
RETURN_NOTES = ["Thiếu minh chứng chạy thử", "Chưa xử lý trường hợp lỗi", "Cần bổ sung ảnh chụp kết quả",
                "Sai so với yêu cầu đã chốt", "Mã nguồn chưa được rà soát"]


def _simulate(rng, profile, created, due, ready, assignee, manager):
    """Mô phỏng vòng đời MỘT việc. Trả về (events, final_due). Các số là độ lệch ngày so với hôm nay (≤ 0 là quá khứ).
    events theo định dạng build_task: [(days_ago,)] + [(days_ago, field, old, new, note, user)]."""
    ev = [(-created,)]
    window = max(due - created, 4)
    final_due = due
    if ready is None:  # việc phụ thuộc chưa xong → chưa thể bắt đầu
        return ev, final_due
    if profile == "steady":
        start = ready + rng.randint(0, 1)
        work = max(1, round(window * rng.uniform(0.25, 0.4)))
        ghost, return_p = False, 0.08
    elif profile == "crunch":
        start = ready + round(window * rng.uniform(0.45, 0.65))
        work = max(1, round(window * rng.uniform(0.15, 0.3)))
        ghost, return_p = False, 0.2
    elif profile == "rework":
        start = ready + rng.randint(0, 2)
        work = max(1, round(window * rng.uniform(0.3, 0.45)))
        ghost, return_p = False, 0.6
    else:  # slow
        start = ready + round(window * rng.uniform(0.3, 0.6))
        work = max(2, round(window * rng.uniform(0.4, 0.8)))
        ghost, return_p = rng.random() < 0.2, 0.3
        if rng.random() < 0.25:  # xin gia hạn → ghi lịch sử đổi hạn
            new_due = due + rng.randint(2, 4)
            when = min(due - 1, 0)
            if when >= ready:
                ev.append((-when, "due_date", str(_d(due)), str(_d(new_due)), "Gia hạn theo đề nghị", manager))
                final_due = new_due
    start = max(start, created + 1)
    if start > 0:
        return ev, final_due
    ev.append((-start, "status", "todo", "in_progress", None, assignee))
    day = start
    if ghost:
        return ev, final_due
    returns = 0
    while True:
        day += work if returns == 0 else rng.randint(1, 3)
        if day > 0:
            break
        ev.append((-day, "attachment", None, f"pull/{rng.randint(10, 99)}", None, assignee))
        ev.append((-day, "status", "in_progress", "review", None, assignee))
        day += rng.randint(0, 2)  # chờ quản lý duyệt
        if day > 0:
            break
        if returns < 3 and rng.random() < return_p * (0.7 ** returns):
            ev.append((-day, "review", "return", "in_progress", rng.choice(RETURN_NOTES), manager))
            ev.append((-day, "status", "review", "in_progress", None, manager))
            returns += 1
            continue
        ev.append((-day, "review", "approve", "done", None, manager))
        ev.append((-day, "status", "review", "done", None, manager))
        break
    return ev, final_due


def _d(offset):
    return date.today() + timedelta(days=offset)


def _done_day(events):
    """Ngày (độ lệch) việc được duyệt done; None nếu chưa xong."""
    for e in reversed(events):
        if len(e) > 1 and e[1] == "status" and e[3] == "done":
            return -e[0]
    return None


def _seed_project(rng, ws, users, spec):
    name, desc, start, due, mgr_key, profiles, n_tasks = spec
    gv = users["gv"]
    mgr = users[mgr_key]
    p = Project(workspace_id=ws.id, name=name, description=desc, start_date=_d(start), due_date=_d(due),
                created_by=mgr.id, created_at=at(-start, 8))
    db.session.add(p)
    db.session.flush()
    for key in profiles:
        db.session.add(ProjectMember(project_id=p.id, user_id=users[key].id, joined_at=at(-start, 8),
                                     project_role="manager" if key == mgr_key else "member"))
    db.session.add(ProjectMember(project_id=p.id, user_id=gv.id, project_role="supervisor", joined_at=at(-start, 8)))

    span = due - start
    ms_due = [start + round(span * f) for f in (0.3, 0.7, 1.0)]
    milestones = [Milestone(project_id=p.id, title=t, due_date=_d(d)) for t, d in zip(MILESTONES, ms_due)]
    db.session.add_all(milestones)
    db.session.flush()

    members = list(profiles)
    titles = rng.sample(TASK_TITLES, min(n_tasks, len(TASK_TITLES)))
    built, done_day = [], {}  # done_day: index → ngày xong
    deps = []
    for i, title in enumerate(titles):
        mi = min(2, i * 3 // n_tasks)
        assignee_key = members[(i + rng.randint(0, 1)) % len(members)]
        assignee = users[assignee_key]
        created = start + rng.randint(0, 2)
        t_due = max(created + 4, ms_due[mi] - rng.randint(0, 3))
        dep = rng.choice([j for j in range(i) if built[j][1] <= mi]) if i >= 2 and rng.random() < 0.35 else None
        ready = created
        if dep is not None:
            ready = done_day.get(dep)
            if ready is not None:
                ready = max(created, ready + 1)
        events, final_due = _simulate(rng, profiles[assignee_key], created, t_due, ready, assignee, mgr)
        # build_task cần sự kiện theo thứ tự thời gian (days_ago giảm dần); sort ổn định giữ thứ tự cùng ngày
        events = [events[0]] + sorted(events[1:], key=lambda e: -e[0])
        pts = rng.choice([1, 2, 3, 3, 5])
        task = build_task(p, title, assignee, mgr, events, milestone_id=milestones[mi].id, points=pts,
                          due_date=_d(final_due), priority=rng.choice(["low", "medium", "high"]))
        built.append((task, mi))
        done_day[i] = _done_day(events)
        if dep is not None:
            deps.append(TaskDependency(task_id=task.id, depends_on_id=built[dep][0].id))
    db.session.add_all(deps)

    # trạng thái cột mốc: xong hết + đến hạn → thường được nghiệm thu; còn lại để mở (cột mốc trễ → đèn đỏ)
    today = date.today()
    for mi, m in enumerate(milestones):
        tasks = [t for t, k in built if k == mi]
        if tasks and all(t.status == "done" for t in tasks) and m.due_date <= today + timedelta(days=3):
            if rng.random() < 0.8:
                m.status, m.reviewed_by, m.reviewed_at, m.review_note = "accepted", gv.id, at(0), "Đạt yêu cầu"
            else:
                m.status = "pending_review"
    db.session.flush()
    return p, mgr_key, profiles


def _scenarios(project, users, mgr):
    """Hai việc dựng tay trong dự án 'Ứng dụng quản lý kho' để luôn có đủ ca RETURNED và NEAR_DUE_NOT_STARTED."""
    ms = Milestone.query.filter_by(project_id=project.id).order_by(Milestone.due_date).all()
    sv1, sv3 = users["sv1"], users["sv3"]
    build_task(project, "Cải tiến màn hình nhập kho", sv3, mgr, [
        (12,), (11, "status", "todo", "in_progress", None, sv3),
        (9, "attachment", None, "pull/31", None, sv3), (9, "status", "in_progress", "review", None, sv3),
        (8, "review", "return", "in_progress", "Chưa kiểm tra dữ liệu đầu vào", mgr), (8, "status", "review", "in_progress", None, mgr),
        (6, "attachment", None, "pull/34", None, sv3), (6, "status", "in_progress", "review", None, sv3),
        (5, "review", "return", "in_progress", "Thiếu ảnh chụp kết quả", mgr), (5, "status", "review", "in_progress", None, mgr),
        (1, "attachment", None, "pull/37", None, sv3), (1, "status", "in_progress", "review", None, sv3)],
        milestone_id=ms[1].id, points=3, due_date=_d(4), priority="high")
    build_task(project, "Báo cáo tồn kho theo tuần", sv1, mgr, [(5,)], milestone_id=ms[1].id, points=2,
               due_date=_d(1), priority="medium")


def _peer_reviews(rng, project, profiles, users, full):
    """Đánh giá chéo: điểm phụ thuộc kiểu làm việc của người được đánh giá."""
    base = {"steady": 4.4, "crunch": 3.6, "rework": 3.3, "slow": 2.6}
    notes = {"steady": ["Làm việc đều tay, đúng hẹn", "Giao tiếp rõ ràng"], "crunch": ["Hay dồn việc sát hạn", "Kết quả tốt nhưng gấp"],
             "rework": ["Cần tự kiểm tra kỹ hơn trước khi nộp", "Sửa lỗi nhanh"], "slow": ["Cần cập nhật tiến độ thường xuyên", ""]}
    keys = list(profiles)
    for a in keys:
        for b in keys:
            if a == b or (not full and rng.random() < 0.4):
                continue
            score = max(1, min(5, round(base[profiles[b]] + rng.uniform(-0.9, 0.9))))
            db.session.add(PeerReview(project_id=project.id, reviewer_id=users[a].id, reviewee_id=users[b].id,
                                      score=score, comment=rng.choice(notes[profiles[b]])))


def seed():
    rng = random.Random(SEED)
    users = {u.email.split("@")[0]: u for u in User.query.all()}
    ws = Workspace.query.filter_by(name="Lớp Lập trình Web 01").one()
    demo = Project.query.filter_by(name="TeamSync demo").first()
    for i, spec in enumerate(PROJECTS):
        p, mgr_key, profiles = _seed_project(rng, ws, users, spec)
        if i == len(PROJECTS) - 1:
            _scenarios(p, users, users[mgr_key])
        _peer_reviews(rng, p, profiles, users, full=(i == 0))
    if demo:  # vài đánh giá cho dự án demo; còn thiếu sv1→sv3 và sv2→sv1 để thử form
        for a, b, score, text in (("sv1", "sv2", 3, "Cần cập nhật tiến độ thường xuyên hơn"),
                                  ("sv3", "sv2", 5, "Hỗ trợ nhóm rất tốt"),
                                  ("sv3", "sv1", 4, "Phân việc rõ ràng"),
                                  ("sv2", "sv3", 4, "")):
            db.session.add(PeerReview(project_id=demo.id, reviewer_id=users[a].id, reviewee_id=users[b].id,
                                      score=score, comment=text))
    db.session.flush()
