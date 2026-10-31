"""API M17 — Dashboard, báo cáo và đánh giá. Chủ sở hữu: Thành viên 3. Yêu cầu chi tiết ở docs/M17.md.
Nguyên tắc: CHỈ ĐỌC bảng M06 (Task, TaskHistory, Attachment...). Bảng duy nhất M17 ghi là PeerReview.
Ngưỡng luật cảnh báo đọc từ current_app.config: RISK_DAYS_BEFORE_DUE, RISK_DAYS_NO_UPDATE, RISK_RETURN_COUNT, HEALTH_RED_OVERDUE.
"""
from datetime import datetime

from flask import Response, request

from ..common.responses import fail, ok, require_json
from ..m20_accounts.permissions import (MANAGER, SUPERVISORS, WORKERS, check_project_access, check_workspace_access,
                                        current_user, login_required, project_role)
from ..models import PeerReview
from . import api_bp, risk, services


def _ctx(project_id, roles=None):
    """(project, data, my_role, user) sau khi kiểm tra quyền."""
    project = check_project_access(project_id, roles)
    user = current_user()
    return project, services.load_project_data(project), project_role(project_id, user.id), user


@api_bp.get("/projects/<int:project_id>/stats")
@login_required
def stats(project_id):
    """→ total, by_status, percent_done, points_total/done, percent_points, overdue, on_time_rate, by_milestone
    (+ done, on_time, late, timeline, project, my_role)."""
    project, data, my_role, user = _ctx(project_id)
    out = services.compute_stats(data, services.today())
    out["project"] = services.project_info(project, my_role, user)
    out["my_role"] = my_role
    return ok(out)


@api_bp.get("/projects/<int:project_id>/risks")
@login_required
def risks(project_id):
    """→ [{task_id, title, status, due_date, assignee, reasons: [{code, label, detail}]}]."""
    _, data, _, _ = _ctx(project_id)
    return ok(risk.project_risks(data, services.today(), services.thresholds()))


@api_bp.get("/projects/<int:project_id>/health")
@login_required
def project_health(project_id):
    """→ {level: green|yellow|red, reasons, overdue_count, risk_count, late_milestones}."""
    _, data, _, _ = _ctx(project_id)
    return ok(services.compute_health(data, services.today()))


@api_bp.get("/projects/<int:project_id>/contributions")
@login_required
def project_contributions(project_id):
    """Sổ đóng góp. Điểm đánh giá chéo chỉ hiện với quản lý, giám sát, admin (người khác nhận null)."""
    _, data, my_role, user = _ctx(project_id)
    return ok(services.compute_contributions(data, services.today(), services.can_see_peer_scores(user, my_role)))


@api_bp.get("/projects/<int:project_id>/activity")
@login_required
def activity(project_id):
    """Query: ?limit=20 (tối đa 100) → lịch sử mới nhất của dự án."""
    check_project_access(project_id)
    try:
        limit = int(request.args.get("limit", 20))
    except ValueError:
        fail(400, "VALIDATION_ERROR", "limit phải là số nguyên")
    if limit < 1:
        fail(400, "VALIDATION_ERROR", "limit phải ≥ 1")
    return ok(services.recent_activity(project_id, min(limit, 100)))


@api_bp.get("/projects/<int:project_id>/peer-reviews")
@login_required
def list_peer_reviews(project_id):
    """Mặc định — quản lý/giám sát/admin: tổng hợp theo người được đánh giá (ẩn người chấm);
    thành viên: các đánh giá mình đã gửi. `?mine=1`: {reviews, pending} của chính mình (quản lý dùng để biết ai chưa chấm).
    Người ngoài dự án (kể cả chủ workspace không có vai trò dự án) → 403."""
    check_project_access(project_id, WORKERS + SUPERVISORS)
    user = current_user()
    my_role = project_role(project_id, user.id)
    if request.args.get("mine") in ("1", "true"):
        if my_role not in WORKERS:
            return ok({"reviews": [], "pending": []})
        return ok({"reviews": services.my_reviews(project_id, user.id),
                   "pending": services.pending_reviewees(project_id, user.id)})
    if services.can_see_peer_scores(user, my_role):
        return ok(services.peer_summary(project_id))
    return ok(services.my_reviews(project_id, user.id))


def _int_field(body, name, lo=None, hi=None):
    v = body.get(name)
    if isinstance(v, bool) or not isinstance(v, int):
        fail(400, "VALIDATION_ERROR", f"{name} phải là số nguyên")
    if (lo is not None and v < lo) or (hi is not None and v > hi):
        fail(400, "VALIDATION_ERROR", f"{name} phải trong khoảng {lo}–{hi}")
    return v


@api_bp.post("/projects/<int:project_id>/peer-reviews")
@login_required
def create_peer_review(project_id):
    """Quản lý hoặc thành viên. Body: {reviewee_id, score 1..5, comment?}. Không tự đánh giá; trùng → 409."""
    check_project_access(project_id, WORKERS)
    user = current_user()
    if project_role(project_id, user.id) not in WORKERS:  # admin không phải người trong cuộc
        fail(403, "FORBIDDEN", "Chỉ quản lý và thành viên của dự án mới đánh giá chéo")
    body = require_json("reviewee_id", "score")
    reviewee_id = _int_field(body, "reviewee_id")
    score = _int_field(body, "score", 1, 5)
    comment = body.get("comment") or ""
    if not isinstance(comment, str):
        fail(400, "VALIDATION_ERROR", "comment phải là chuỗi")
    comment = comment.strip()
    if len(comment) > 1000:
        fail(400, "VALIDATION_ERROR", "Nhận xét tối đa 1000 ký tự")
    if reviewee_id == user.id:
        fail(400, "VALIDATION_ERROR", "Không thể tự đánh giá chính mình")
    if project_role(project_id, reviewee_id) not in WORKERS:
        fail(404, "REVIEWEE_NOT_FOUND", "Người được đánh giá phải là quản lý hoặc thành viên của dự án")
    if PeerReview.query.filter_by(project_id=project_id, reviewer_id=user.id, reviewee_id=reviewee_id).first():
        fail(409, "ALREADY_REVIEWED", "Bạn đã đánh giá người này rồi")
    review = PeerReview(project_id=project_id, reviewer_id=user.id, reviewee_id=reviewee_id, score=score,
                        comment=comment)
    if not services.commit_review(review):
        fail(409, "ALREADY_REVIEWED", "Bạn đã đánh giá người này rồi")
    return ok(review.to_dict(), 201)


@api_bp.get("/workspaces/<int:workspace_id>/overview")
@login_required
def workspace_overview(workspace_id):
    """Chủ workspace/admin: tiến độ và sức khỏe mọi dự án trong workspace."""
    ws = check_workspace_access(workspace_id, owner=True)
    return ok(services.workspace_overview(ws, services.today()))


@api_bp.get("/projects/<int:project_id>/report")
@login_required
def project_report(project_id):
    """→ file CSV sổ đóng góp (text/csv, UTF-8 có BOM để Excel đọc đúng tiếng Việt)."""
    project, data, my_role, user = _ctx(project_id)
    show_peer = services.can_see_peer_scores(user, my_role)
    body = services.contributions_csv(services.compute_contributions(data, services.today(), show_peer), show_peer)
    name = f"teamsync-du-an-{project.id}-dong-gop-{datetime.now():%Y%m%d}.csv"
    return Response(body, mimetype="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="{name}"', "Cache-Control": "no-store"})


def _threshold_overrides():
    """Cho phép thử ngưỡng khác qua query để so sánh: ?days_before_due=&days_no_update=&return_count=."""
    vals = services.thresholds().to_dict()
    for key in ("days_before_due", "days_no_update", "return_count"):
        raw = request.args.get(key)
        if raw is None:
            continue
        try:
            v = int(raw)
        except ValueError:
            fail(400, "VALIDATION_ERROR", f"{key} phải là số nguyên")
        if not 0 <= v <= 60:
            fail(400, "VALIDATION_ERROR", f"{key} phải trong khoảng 0–60")
        vals[key] = v
    return risk.Thresholds(**vals)


@api_bp.get("/projects/<int:project_id>/risk-evaluation")
@login_required
def risk_evaluation(project_id):
    """Quản lý/giám sát/admin: chạy lại luật cảnh báo trên lịch sử dự án → recall, số ngày cảnh báo sớm, cảnh báo thừa."""
    _, data, _, _ = _ctx(project_id, MANAGER + SUPERVISORS)
    result = risk.evaluate(data, services.today(), _threshold_overrides())
    result.pop("lead_days_sum", None)
    return ok(result)
