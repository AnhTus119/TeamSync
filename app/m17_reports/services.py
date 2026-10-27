"""Truy vấn + tính toán cho API M17. Chủ sở hữu: Thành viên 3. CHỈ ĐỌC bảng M06/M20; bảng duy nhất ghi là PeerReview."""
import csv
import io
from collections import defaultdict
from datetime import date, timedelta

from flask import current_app

from ..common.utils import iso
from ..extensions import db
from ..models import (Attachment, Milestone, PeerReview, Project, ProjectMember, Task, TaskDependency, TaskHistory,
                      User)
from . import risk
from .risk import STATUS_LABELS, ProjectData, Thresholds

STATUSES = ("todo", "in_progress", "review", "done")
WORKER_ROLES = ("manager", "member")
ROLE_ORDER = {"manager": 0, "member": 1, "supervisor": 2}


def today():
    return date.today()


def thresholds():
    return Thresholds.from_config(current_app.config)


def pct(a, b):
    return round(100 * a / b, 1) if b else 0.0


def rate(a, b):
    """Tỷ lệ phần trăm; None khi chưa có mẫu."""
    return round(100 * a / b, 1) if b else None


# ----------------------------------------------------------------------------- nạp dữ liệu
def load_project_data(project):
    tasks = Task.query.filter_by(project_id=project.id).order_by(Task.id).all()
    ids = [t.id for t in tasks]
    history = defaultdict(list)
    deps = defaultdict(list)
    if ids:
        rows = (TaskHistory.query.filter(TaskHistory.task_id.in_(ids))
                .order_by(TaskHistory.created_at, TaskHistory.id).all())
        for h in rows:
            history[h.task_id].append(h)
        for d in TaskDependency.query.filter(TaskDependency.task_id.in_(ids)).all():
            deps[d.task_id].append(d.depends_on_id)
    milestones = Milestone.query.filter_by(project_id=project.id).order_by(Milestone.due_date, Milestone.id).all()
    return ProjectData(project, tasks, history, deps, milestones)


def project_info(project, my_role, user):
    ws = project.workspace
    return {"id": project.id, "name": project.name, "description": project.description,
            "workspace_id": project.workspace_id, "workspace_name": ws.name if ws else "",
            "start_date": iso(project.start_date), "due_date": iso(project.due_date),
            "my_role": my_role, "is_workspace_owner": bool(ws and ws.owner_id == user.id)}


def members_of(project_id, roles=None):
    q = ProjectMember.query.filter_by(project_id=project_id)
    out = q.all()
    if roles:
        out = [m for m in out if m.project_role in roles]
    out.sort(key=lambda m: (ROLE_ORDER.get(m.project_role, 9), m.user.full_name.lower(), m.user_id))
    return out


# ----------------------------------------------------------------------------- thống kê
def _is_done_on_time(t):
    return bool(t.status == "done" and t.due_date and t.completed_at and t.completed_at.date() <= t.due_date)


def _is_done_late(t):
    return bool(t.status == "done" and t.due_date and t.completed_at and t.completed_at.date() > t.due_date)


def _is_overdue_open(t, day):
    return bool(t.status != "done" and t.due_date and t.due_date < day)


def _bucket(tasks, day):
    """Gom số liệu cho một nhóm việc (dự án / cột mốc)."""
    total = len(tasks)
    done = [t for t in tasks if t.status == "done"]
    on_time = sum(_is_done_on_time(t) for t in tasks)
    late = sum(_is_done_late(t) for t in tasks)
    overdue = sum(_is_overdue_open(t, day) for t in tasks)
    pts_total, pts_done = sum(t.points for t in tasks), sum(t.points for t in done)
    return {"total": total, "done": len(done), "percent_done": pct(len(done), total),
            "points_total": pts_total, "points_done": pts_done, "percent_points": pct(pts_done, pts_total),
            "overdue": overdue, "on_time": on_time, "late": late, "on_time_rate": rate(on_time, on_time + late + overdue)}


def timeline(data, day, max_points=60):
    """Đường tiến độ: điểm kế hoạch (cộng dồn theo hạn) so với điểm đã hoàn thành (cộng dồn theo ngày xong)."""
    p = data.project
    created = [t.created_at.date() for t in data.tasks]
    start = p.start_date or (min(created) if created else day)
    end = max([p.due_date or day, day] + [t.due_date for t in data.tasks if t.due_date])
    if end < start:
        start, end = end, start
    span = (end - start).days
    step = max(1, -(-span // max_points))
    days = [start + timedelta(days=i) for i in range(0, span + 1, step)]
    if days[-1] != end:
        days.append(end)
    out = {"labels": [d.isoformat() for d in days], "planned_points": [], "done_points": [],
           "today": day.isoformat() if start <= day <= end else None}
    for d in days:
        out["planned_points"].append(sum(t.points for t in data.tasks if t.due_date and t.due_date <= d))
        out["done_points"].append(sum(t.points for t in data.tasks if t.status == "done" and t.completed_at
                                      and t.completed_at.date() <= d) if d <= day else None)
    return out


def compute_stats(data, day):
    tasks = data.tasks
    base = _bucket(tasks, day)
    by_status = {s: sum(1 for t in tasks if t.status == s) for s in STATUSES}
    by_ms = []
    for m in data.milestones:
        b = _bucket([t for t in tasks if t.milestone_id == m.id], day)
        by_ms.append({"milestone_id": m.id, "title": m.title, "status": m.status, "due_date": iso(m.due_date),
                      "is_late": bool(m.due_date and m.due_date < day and m.status != "accepted"), **b})
    loose = [t for t in tasks if t.milestone_id is None]
    if loose:
        by_ms.append({"milestone_id": None, "title": "Chưa gắn cột mốc", "status": None, "due_date": None,
                      "is_late": False, **_bucket(loose, day)})
    return {**base, "by_status": by_status, "by_milestone": by_ms, "timeline": timeline(data, day)}


def compute_health(data, day, th=None):
    th = th or thresholds()
    return risk.project_health(data, day, th)


# ----------------------------------------------------------------------------- sổ đóng góp
def can_see_peer_scores(user, my_role):
    return user.role == "admin" or my_role in ("manager", "supervisor")


def compute_contributions(data, day, show_peer):
    pid = data.project.id
    members = members_of(pid, WORKER_ROLES)
    by_user = defaultdict(list)
    for t in data.tasks:
        if t.assignee_id:
            by_user[t.assignee_id].append(t)
    evidence = defaultdict(int)
    ids = [t.id for t in data.tasks]
    if ids:
        for a in Attachment.query.filter(Attachment.task_id.in_(ids)).all():
            evidence[a.uploaded_by] += 1
    peer = defaultdict(list)
    if show_peer:
        for r in PeerReview.query.filter_by(project_id=pid).all():
            peer[r.reviewee_id].append(r.score)
    done_points_all = sum(t.points for t in data.tasks if t.status == "done")
    rows = []
    for m in members:
        mine = by_user.get(m.user_id, [])
        b = _bucket(mine, day)
        returned = sum(1 for t in mine for h in data.history.get(t.id, []) if risk._is_return(h))
        scores = peer.get(m.user_id, [])
        rows.append({
            "user_id": m.user_id, "full_name": m.user.full_name, "email": m.user.email, "project_role": m.project_role,
            "assigned_tasks": b["total"], "assigned_points": b["points_total"],
            "completed_tasks": b["done"], "completed_points": b["points_done"],
            "on_time": b["on_time"], "late": b["late"], "overdue_open": b["overdue"], "on_time_rate": b["on_time_rate"],
            "returned_count": returned, "evidence_count": evidence.get(m.user_id, 0),
            "points_share": pct(b["points_done"], done_points_all),
            "peer_review_average": round(sum(scores) / len(scores), 2) if scores else None,
            "peer_review_count": len(scores) if show_peer else None,
        })
    return rows


# ----------------------------------------------------------------------------- hoạt động
def _fmt_day(value):
    try:
        return date.fromisoformat(value).strftime("%d/%m/%Y")
    except (TypeError, ValueError):
        return "chưa đặt"


def describe(h, title, names):
    t = f"“{title}”"
    st = lambda v: STATUS_LABELS.get(v, v)  # noqa: E731
    if h.field == "created":
        return f"tạo việc {t}"
    if h.field == "status":
        return f"chuyển {t} từ {st(h.old_value)} sang {st(h.new_value)}"
    if h.field == "review":
        base = f"duyệt {t}" if h.old_value == "approve" else f"trả lại {t}"
        return base + (f" — {h.note}" if h.note else "")
    if h.field == "attachment":
        return f"nộp minh chứng {h.new_value} cho {t}" if h.new_value else f"nộp minh chứng cho {t}"
    if h.field == "assignee_id":
        who = lambda v: names.get(int(v), "chưa giao") if v and str(v).isdigit() else "chưa giao"  # noqa: E731
        return f"đổi người làm của {t} từ {who(h.old_value)} sang {who(h.new_value)}"
    if h.field == "due_date":
        return f"đổi hạn của {t} từ {_fmt_day(h.old_value)} sang {_fmt_day(h.new_value)}"
    if h.field == "points":
        return f"đổi điểm của {t} từ {h.old_value} sang {h.new_value}"
    if h.field == "dependency":
        return f"cập nhật việc phụ thuộc của {t}"
    return f"cập nhật {h.field} của {t}"


def recent_activity(project_id, limit):
    ids = {t.id: t.title for t in Task.query.filter_by(project_id=project_id).all()}
    if not ids:
        return []
    rows = (TaskHistory.query.filter(TaskHistory.task_id.in_(list(ids)))
            .order_by(TaskHistory.created_at.desc(), TaskHistory.id.desc()).limit(min(limit * 3, 300)).all())
    names = {u.id: u.full_name for u in User.query.all()}
    reviews = [(h.task_id, h.new_value, h.created_at) for h in rows if h.field == "review"]
    out = []
    for h in rows:
        # dòng status đi kèm dòng review (duyệt/trả lại) là trùng ý → bỏ
        if h.field == "status" and any(tid == h.task_id and nv == h.new_value
                                       and abs((ts - h.created_at).total_seconds()) <= 3600
                                       for tid, nv, ts in reviews):
            continue
        out.append({"id": h.id, "task_id": h.task_id, "task_title": ids[h.task_id], "user": h.user.brief(),
                    "field": h.field, "old_value": h.old_value, "new_value": h.new_value, "note": h.note,
                    "summary": describe(h, ids[h.task_id], names), "created_at": iso(h.created_at)})
        if len(out) >= limit:
            break
    return out


# ----------------------------------------------------------------------------- đánh giá chéo
def peer_summary(project_id):
    """Tổng hợp theo người được đánh giá. KHÔNG chứa thông tin người chấm."""
    reviews = PeerReview.query.filter_by(project_id=project_id).order_by(PeerReview.id).all()
    by = defaultdict(list)
    for r in reviews:
        by[r.reviewee_id].append(r)
    out = []
    for m in members_of(project_id, WORKER_ROLES):
        rs = by.get(m.user_id, [])
        scores = [r.score for r in rs]
        out.append({"reviewee": m.user.brief(), "project_role": m.project_role, "count": len(rs),
                    "average": round(sum(scores) / len(scores), 2) if scores else None,
                    "distribution": {str(i): scores.count(i) for i in range(1, 6)},
                    "comments": [{"score": r.score, "comment": r.comment} for r in rs if (r.comment or "").strip()]})
    return out


def my_reviews(project_id, user_id):
    members = {m.user_id: m for m in members_of(project_id)}
    out = []
    for r in PeerReview.query.filter_by(project_id=project_id, reviewer_id=user_id).order_by(PeerReview.id).all():
        m = members.get(r.reviewee_id)
        out.append({**r.to_dict(hide_reviewer=False), "reviewee": m.user.brief() if m else None})
    return out


def pending_reviewees(project_id, user_id):
    done = {r.reviewee_id for r in PeerReview.query.filter_by(project_id=project_id, reviewer_id=user_id).all()}
    return [{**m.user.brief(), "project_role": m.project_role} for m in members_of(project_id, WORKER_ROLES)
            if m.user_id != user_id and m.user_id not in done]


# ----------------------------------------------------------------------------- tổng quan workspace
def workspace_overview(workspace, day):
    th = thresholds()
    projects = Project.query.filter_by(workspace_id=workspace.id).order_by(Project.id).all()
    items, totals = [], defaultdict(int)
    order = {"red": 0, "yellow": 1, "green": 2}
    for p in projects:
        data = load_project_data(p)
        st = compute_stats(data, day)
        hl = risk.project_health(data, day, th)
        sup = [m.user.full_name for m in members_of(p.id) if m.project_role == "supervisor"]
        mgr = [m.user.full_name for m in members_of(p.id) if m.project_role == "manager"]
        items.append({"project": {"id": p.id, "name": p.name, "start_date": iso(p.start_date),
                                  "due_date": iso(p.due_date)},
                      "manager": mgr[0] if mgr else None, "supervisors": sup,
                      "member_count": len(members_of(p.id, WORKER_ROLES)),
                      "stats": {k: st[k] for k in ("total", "done", "percent_done", "points_total", "points_done",
                                                   "percent_points", "overdue", "on_time_rate")},
                      "health": hl})
        totals["total"] += st["total"]
        totals["done"] += st["done"]
        totals["overdue"] += st["overdue"]
        totals["risk_count"] += hl["risk_count"]
        totals["points_total"] += st["points_total"]
        totals["points_done"] += st["points_done"]
        totals[hl["level"]] += 1
    items.sort(key=lambda x: (order[x["health"]["level"]], -x["health"]["overdue_count"], x["project"]["id"]))
    totals = dict(totals)
    return {"workspace": {"id": workspace.id, "name": workspace.name}, "project_count": len(projects),
            "totals": {"total": totals.get("total", 0), "done": totals.get("done", 0),
                       "percent_done": pct(totals.get("done", 0), totals.get("total", 0)),
                       "percent_points": pct(totals.get("points_done", 0), totals.get("points_total", 0)),
                       "overdue": totals.get("overdue", 0), "risk_count": totals.get("risk_count", 0),
                       "red": totals.get("red", 0), "yellow": totals.get("yellow", 0), "green": totals.get("green", 0)},
            "projects": items}


# ----------------------------------------------------------------------------- CSV
def csv_safe(value):
    """Chống CSV injection: ô bắt đầu bằng = + - @ (hoặc tab/CR) bị Excel hiểu là công thức."""
    s = "" if value is None else str(value)
    return "'" + s if s[:1] in ("=", "+", "-", "@", "\t", "\r") else s


def contributions_csv(rows, show_peer):
    head = ["Họ tên", "Email", "Vai trò", "Việc được giao", "Điểm được giao", "Việc hoàn thành", "Điểm hoàn thành",
            "Hoàn thành đúng hạn", "Hoàn thành trễ hạn", "Quá hạn chưa xong", "Tỷ lệ đúng hạn (%)",
            "Số lần bị trả lại", "Số minh chứng"]
    if show_peer:
        head += ["Điểm đánh giá chéo TB", "Số lượt đánh giá"]
    labels = {"manager": "Quản lý", "member": "Thành viên"}
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(head)
    for r in rows:
        line = [r["full_name"], r["email"], labels.get(r["project_role"], r["project_role"]), r["assigned_tasks"],
                r["assigned_points"], r["completed_tasks"], r["completed_points"], r["on_time"], r["late"],
                r["overdue_open"], "" if r["on_time_rate"] is None else r["on_time_rate"], r["returned_count"],
                r["evidence_count"]]
        if show_peer:
            line += ["" if r["peer_review_average"] is None else r["peer_review_average"], r["peer_review_count"]]
        w.writerow([csv_safe(x) if isinstance(x, str) else x for x in line])
    return "\ufeff" + buf.getvalue()


def commit_review(review):
    """Lưu PeerReview; trùng cặp → trả False (đã rollback)."""
    from sqlalchemy.exc import IntegrityError
    db.session.add(review)
    try:
        db.session.commit()
        return True
    except IntegrityError:
        db.session.rollback()
        return False
