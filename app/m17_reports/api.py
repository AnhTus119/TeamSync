"""API M17 — Dashboard, báo cáo và đánh giá. Chủ sở hữu: Thành viên 3.
Mỗi route còn `return not_implemented()` là một việc cần làm. Yêu cầu chi tiết ở docs/M17.md.
Nguyên tắc: CHỈ ĐỌC bảng M06 (Task, TaskHistory, Attachment...). Bảng duy nhất M17 ghi là PeerReview.
Ngưỡng luật cảnh báo đọc từ current_app.config: RISK_DAYS_BEFORE_DUE, RISK_DAYS_NO_UPDATE, RISK_RETURN_COUNT, HEALTH_RED_OVERDUE.
"""
from ..common.responses import not_implemented
from ..m20_accounts.permissions import login_required
from . import api_bp


@api_bp.get("/projects/<int:project_id>/stats")
@login_required
def stats(project_id):
    """→ total, by_status, percent_done, points_total/done, percent_points, overdue, on_time_rate, by_milestone."""
    return not_implemented()


@api_bp.get("/projects/<int:project_id>/risks")
@login_required
def risks(project_id):
    """→ [{task_id, title, status, due_date, assignee, reasons: [{code, label, detail}]}]."""
    return not_implemented()


@api_bp.get("/projects/<int:project_id>/health")
@login_required
def project_health(project_id):
    """→ {level: green|yellow|red, reasons, overdue_count, risk_count, late_milestones}."""
    return not_implemented()


@api_bp.get("/projects/<int:project_id>/contributions")
@login_required
def project_contributions(project_id):
    """Sổ đóng góp. Điểm đánh giá chéo chỉ hiện với quản lý, giám sát, admin."""
    return not_implemented()


@api_bp.get("/projects/<int:project_id>/activity")
@login_required
def activity(project_id):
    """Query: ?limit=20 (tối đa 100) → lịch sử mới nhất của dự án."""
    return not_implemented()


@api_bp.get("/projects/<int:project_id>/peer-reviews")
@login_required
def list_peer_reviews(project_id):
    """Quản lý/giám sát/admin: tổng hợp theo người được đánh giá (ẩn người chấm). Thành viên: các đánh giá mình đã gửi."""
    return not_implemented()


@api_bp.post("/projects/<int:project_id>/peer-reviews")
@login_required
def create_peer_review(project_id):
    """Quản lý hoặc thành viên. Body: {reviewee_id, score 1..5, comment?}. Không tự đánh giá; trùng → 409."""
    return not_implemented()


@api_bp.get("/workspaces/<int:workspace_id>/overview")
@login_required
def workspace_overview(workspace_id):
    """Chủ workspace/admin: tiến độ và sức khỏe mọi dự án trong workspace."""
    return not_implemented()


@api_bp.get("/projects/<int:project_id>/report")
@login_required
def project_report(project_id):
    """→ file CSV sổ đóng góp (text/csv, UTF-8 có BOM để Excel đọc đúng tiếng Việt)."""
    return not_implemented()


@api_bp.get("/projects/<int:project_id>/risk-evaluation")
@login_required
def risk_evaluation(project_id):
    """Quản lý/giám sát/admin: chạy lại luật cảnh báo trên lịch sử dự án → recall, số ngày cảnh báo sớm, cảnh báo thừa."""
    return not_implemented()
