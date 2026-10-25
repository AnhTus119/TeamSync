"""API M17 — Dashboard, báo cáo và đánh giá. Chủ sở hữu: Thành viên 3.
Nguyên tắc: CHỈ ĐỌC bảng M06. Bảng duy nhất M17 ghi là PeerReview."""
import csv
import io
from datetime import date

from flask import Response, request

from ..common.responses import fail, ok, require_json
from ..extensions import db
from ..m20_accounts.permissions import (MANAGER, SUPERVISORS, WORKERS, check_project_access,
                                        check_workspace_access, current_user, login_required, project_role)
from ..models import Attachment, PeerReview, Project, ProjectMember, Task, TaskHistory
from . import api_bp
from .risk import evaluate, health, project_risks


def _can_see_reviews(project_id):
    user = current_user()
    return user.role == "admin" or project_role(project_id, user.id) in MANAGER + SUPERVISORS


def _on_time(t):
    return t.completed_at is not None and (t.due_date is None or t.completed_at.date() <= t.due_date)


def project_stats(project):
    tasks = project.tasks
    done = [t for t in tasks if t.status == "done"]
    today = date.today()
    points_total = sum(t.points for t in tasks)
    points_done = sum(t.points for t in done)
    by_ms = []
    for ms in project.milestones:
        ts = [t for t in tasks if t.milestone_id == ms.id]
        by_ms.append({"milestone_id": ms.id, "title": ms.title, "status": ms.status,
                      "due_date": ms.due_date.isoformat() if ms.due_date else None, "total": len(ts),
                      "done": sum(t.status == "done" for t in ts)})
    return {"total": len(tasks),
            "by_status": {s: sum(t.status == s for t in tasks) for s in ("todo", "in_progress", "review", "done")},
            "percent_done": round(100 * len(done) / len(tasks)) if tasks else 0,
            "points_total": points_total, "points_done": points_done,
            "percent_points": round(100 * points_done / points_total) if points_total else 0,
            "overdue": sum(1 for t in tasks if t.status != "done" and t.due_date and t.due_date < today),
            "on_time_rate": round(sum(map(_on_time, done)) / len(done), 2) if done else None,
            "by_milestone": by_ms}


def contributions(project, include_reviews):
    """Sổ đóng góp: từng chỉ số riêng, KHÔNG gộp thành một điểm xếp hạng."""
    today = date.today()
    returns = {}
    for h in (TaskHistory.query.join(Task).filter(Task.project_id == project.id, TaskHistory.field == "review",
                                                  TaskHistory.old_value == "return")):
        assignee = db.session.get(Task, h.task_id).assignee_id
        returns[assignee] = returns.get(assignee, 0) + 1
    evidence = dict(db.session.query(Attachment.uploaded_by, db.func.count(Attachment.id)).join(Task)
                    .filter(Task.project_id == project.id).group_by(Attachment.uploaded_by))
    reviews = {}
    for r in PeerReview.query.filter_by(project_id=project.id):
        reviews.setdefault(r.reviewee_id, []).append(r.score)
    rows = []
    for m in project.members:
        if m.project_role not in WORKERS:
            continue
        mine = [t for t in project.tasks if t.assignee_id == m.user_id]
        done = [t for t in mine if t.status == "done"]
        row = {"user": m.user.brief(), "project_role": m.project_role,
               "assigned": len(mine), "assigned_points": sum(t.points for t in mine),
               "done": len(done), "points_done": sum(t.points for t in done),
               "on_time": sum(map(_on_time, done)), "late": len(done) - sum(map(_on_time, done)),
               "overdue_open": sum(1 for t in mine if t.status != "done" and t.due_date and t.due_date < today),
               "on_time_rate": round(sum(map(_on_time, done)) / len(done), 2) if done else None,
               "returned": returns.get(m.user_id, 0), "evidence": evidence.get(m.user_id, 0)}
        if include_reviews:
            scores = reviews.get(m.user_id, [])
            row["peer_score"] = round(sum(scores) / len(scores), 2) if scores else None
            row["peer_count"] = len(scores)
        rows.append(row)
    rows.sort(key=lambda r: -r["points_done"])
    return rows


@api_bp.get("/projects/<int:project_id>/stats")
@login_required
def stats(project_id):
    """→ total, by_status, percent_done, points_total/done, percent_points, overdue, on_time_rate, by_milestone."""
    return ok(project_stats(check_project_access(project_id)))


@api_bp.get("/projects/<int:project_id>/risks")
@login_required
def risks(project_id):
    """→ [{task_id, title, status, due_date, assignee, reasons: [{code, label, detail}]}]."""
    return ok(project_risks(check_project_access(project_id)))


@api_bp.get("/projects/<int:project_id>/health")
@login_required
def project_health(project_id):
    """→ {level: green|yellow|red, reasons, overdue_count, risk_count, late_milestones}."""
    return ok(health(check_project_access(project_id)))


@api_bp.get("/projects/<int:project_id>/contributions")
@login_required
def project_contributions(project_id):
    """Sổ đóng góp. Điểm đánh giá chéo chỉ hiện với quản lý, giám sát, admin."""
    project = check_project_access(project_id)
    return ok(contributions(project, _can_see_reviews(project_id)))


@api_bp.get("/projects/<int:project_id>/activity")
@login_required
def activity(project_id):
    """Query: ?limit=20 (tối đa 100) → lịch sử mới nhất của dự án."""
    check_project_access(project_id)
    limit = min(int(request.args.get("limit", 20)) if request.args.get("limit", "").isdigit() else 20, 100)
    rows = (TaskHistory.query.join(Task).filter(Task.project_id == project_id)
            .order_by(TaskHistory.created_at.desc(), TaskHistory.id.desc()).limit(limit))
    return ok([{**h.to_dict(), "task_title": db.session.get(Task, h.task_id).title} for h in rows])


@api_bp.get("/projects/<int:project_id>/peer-reviews")
@login_required
def list_peer_reviews(project_id):
    """Quản lý/giám sát/admin: tổng hợp theo người được đánh giá (ẩn người chấm). Thành viên: các đánh giá mình đã gửi."""
    check_project_access(project_id)
    if _can_see_reviews(project_id):
        groups = {}
        for r in PeerReview.query.filter_by(project_id=project_id):
            groups.setdefault(r.reviewee_id, []).append(r)
        out = []
        for m in ProjectMember.query.filter_by(project_id=project_id):
            rs = groups.get(m.user_id, [])
            if m.project_role in WORKERS:
                out.append({"user": m.user.brief(), "count": len(rs),
                            "average": round(sum(r.score for r in rs) / len(rs), 2) if rs else None,
                            "comments": [r.comment for r in rs if r.comment]})
        return ok(out)
    mine = PeerReview.query.filter_by(project_id=project_id, reviewer_id=current_user().id)
    return ok([r.to_dict() for r in mine])


@api_bp.post("/projects/<int:project_id>/peer-reviews")
@login_required
def create_peer_review(project_id):
    """Quản lý hoặc thành viên. Body: {reviewee_id, score 1..5, comment?}. Không tự đánh giá; trùng → 409."""
    check_project_access(project_id, WORKERS)
    body = require_json("reviewee_id", "score")
    user = current_user()
    reviewee = body["reviewee_id"]
    if reviewee == user.id:
        fail(400, "VALIDATION_ERROR", "Không tự đánh giá chính mình")
    if project_role(project_id, reviewee) not in WORKERS:
        fail(400, "VALIDATION_ERROR", "Người được đánh giá phải là quản lý hoặc thành viên dự án")
    if body["score"] not in (1, 2, 3, 4, 5):
        fail(400, "VALIDATION_ERROR", "score phải từ 1 đến 5")
    if PeerReview.query.filter_by(project_id=project_id, reviewer_id=user.id, reviewee_id=reviewee).first():
        fail(409, "ALREADY_REVIEWED", "Bạn đã đánh giá người này trong dự án")
    r = PeerReview(project_id=project_id, reviewer_id=user.id, reviewee_id=reviewee,
                   score=body["score"], comment=(body.get("comment") or "")[:1000])
    db.session.add(r)
    db.session.commit()
    return ok(r.to_dict(), 201)


@api_bp.get("/workspaces/<int:workspace_id>/overview")
@login_required
def workspace_overview(workspace_id):
    """Chủ workspace/admin: tiến độ và sức khỏe mọi dự án trong workspace."""
    ws = check_workspace_access(workspace_id, owner=True)
    out = []
    for p in Project.query.filter_by(workspace_id=ws.id).order_by(Project.id):
        s, h = project_stats(p), health(p)
        out.append({"project_id": p.id, "name": p.name, "due_date": p.due_date.isoformat() if p.due_date else None,
                    "percent_done": s["percent_done"], "percent_points": s["percent_points"],
                    "overdue": s["overdue"], "health": h["level"], "risk_count": h["risk_count"]})
    return ok(out)


@api_bp.get("/projects/<int:project_id>/report")
@login_required
def project_report(project_id):
    """→ file CSV sổ đóng góp (text/csv, UTF-8 có BOM để Excel đọc đúng tiếng Việt)."""
    project = check_project_access(project_id)
    rows = contributions(project, _can_see_reviews(project_id))
    buf = io.StringIO()
    w = csv.writer(buf)
    head = ["Họ tên", "Email", "Vai trò", "Số việc", "Điểm được giao", "Việc xong", "Điểm hoàn thành",
            "Đúng hạn", "Trễ hạn", "Quá hạn chưa xong", "Số lần bị trả lại", "Minh chứng"]
    if rows and "peer_score" in rows[0]:
        head += ["Điểm đánh giá chéo", "Số lượt đánh giá"]
    w.writerow(head)
    for r in rows:
        line = [r["user"]["full_name"], r["user"]["email"], r["project_role"], r["assigned"], r["assigned_points"],
                r["done"], r["points_done"], r["on_time"], r["late"], r["overdue_open"], r["returned"], r["evidence"]]
        if "peer_score" in r:
            line += [r["peer_score"] if r["peer_score"] is not None else "", r["peer_count"]]
        w.writerow(line)
    return Response("﻿" + buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment; filename=teamsync_project_{project.id}.csv"})


@api_bp.get("/projects/<int:project_id>/risk-evaluation")
@login_required
def risk_evaluation(project_id):
    """Quản lý/giám sát/admin: chạy lại luật cảnh báo trên lịch sử dự án → recall, số ngày cảnh báo sớm, cảnh báo thừa."""
    project = check_project_access(project_id, MANAGER + SUPERVISORS)
    return ok(evaluate(project.tasks))
