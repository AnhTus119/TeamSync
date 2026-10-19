"""API M11 — Phân tích học tập. Chủ sở hữu: Thành viên 3.
Route nào còn `return not_implemented()` là việc cần làm. Đường dẫn/method đã chốt theo contract.

Nguyên tắc: CHỈ ĐỌC bảng M10 (Task, TaskHistory, Attachment...). Không sửa dữ liệu M10.
Ngưỡng luật cảnh báo: current_app.config["RISK_DAYS_BEFORE_DUE"], ["RISK_DAYS_NO_UPDATE"].
"""
from ..common.responses import not_implemented
from ..m20_accounts.permissions import login_required, role_required
from . import api_bp


@api_bp.get("/projects/<int:project_id>/stats")
@login_required
def project_stats(project_id):
    """→ {data: {total, by_status: {todo, in_progress, review, done}, percent_done, overdue, on_time_rate}}."""
    return not_implemented()


@api_bp.get("/projects/<int:project_id>/members/stats")
@login_required
def member_stats(project_id):
    """→ {data: [{user_id, full_name, assigned, done, on_time, late, returned, attachments}]}."""
    return not_implemented()


@api_bp.get("/projects/<int:project_id>/risks")
@login_required
def project_risks(project_id):
    """→ {data: [{task_id, title, assignee_id, due_date, reasons: ["NEAR_DUE_NOT_STARTED"|"OVERDUE"|"STALE"]}]}."""
    return not_implemented()


@api_bp.get("/projects/<int:project_id>/activity")
@login_required
def project_activity(project_id):
    """Query: ?limit=20 → {data: [task_history mới nhất của dự án]}."""
    return not_implemented()


@api_bp.get("/projects/<int:project_id>/peer-reviews")
@login_required
def list_peer_reviews(project_id):
    """Trưởng nhóm/GV: tổng hợp điểm theo reviewee (ẩn reviewer). Thành viên: chỉ các đánh giá mình đã gửi."""
    return not_implemented()


@api_bp.post("/projects/<int:project_id>/peer-reviews")
@login_required
def create_peer_review(project_id):
    """Body: {reviewee_id, score 1..5, comment?}. Không tự đánh giá mình; trùng → 409."""
    return not_implemented()


@api_bp.get("/courses/<int:course_id>/overview")
@role_required("lecturer", "admin")
def course_overview(course_id):
    """→ {data: [{project_id, name, percent_done, overdue, risks}]} cho mọi dự án trong lớp."""
    return not_implemented()


@api_bp.get("/projects/<int:project_id>/report")
@login_required
def project_report(project_id):
    """→ file CSV (text/csv) tổng hợp theo thành viên. Ngoại lệ duy nhất không trả JSON."""
    return not_implemented()
