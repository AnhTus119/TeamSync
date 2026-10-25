"""API M06 — Quản lý khoa học (quản lý dự án). Chủ sở hữu: Thành viên 2.
Mỗi route còn `return not_implemented()` là một việc cần làm. Đường dẫn/method đã chốt; yêu cầu chi tiết ở docs/M06.md.

Luồng trạng thái việc: todo → in_progress → review → done
  - sang in_progress: mọi việc phụ thuộc đã done
  - sang review: có ít nhất 1 minh chứng
  - done chỉ qua /review (quản lý duyệt); trả lại → in_progress, bắt buộc ghi lý do
Cột mốc: open → pending_review (quản lý gửi) → accepted | changes_requested (giám sát)
Gợi ý import: permissions (MANAGER, WORKERS, SUPERVISORS, check_project_access, check_workspace_access, current_user,
project_role), services (get_task, get_milestone, log_history), m20_accounts.services.add_member, models.
"""
from ..common.responses import not_implemented
from ..m20_accounts.permissions import login_required
from . import api_bp


@api_bp.get("/templates")
@login_required
def list_templates():
    return not_implemented()


@api_bp.get("/projects")
@login_required
def my_projects():
    """Mọi dự án mình tham gia (admin: tất cả), kèm my_role."""
    return not_implemented()


@api_bp.get("/workspaces/<int:workspace_id>/projects")
@login_required
def list_workspace_projects(workspace_id):
    """Chủ workspace/admin thấy mọi dự án; thành viên chỉ thấy dự án mình tham gia."""
    return not_implemented()


@api_bp.post("/workspaces/<int:workspace_id>/projects")
@login_required
def create_project(workspace_id):
    """Thành viên workspace. Body: {name, description?, start_date?, due_date?, template_id?} → 201.
    Người tạo thành quản lý (add_member của M20); nếu có template_id thì tạo sẵn cột mốc và việc."""
    return not_implemented()


@api_bp.get("/projects/<int:project_id>")
@login_required
def get_project(project_id):
    return not_implemented()


@api_bp.patch("/projects/<int:project_id>")
@login_required
def update_project(project_id):
    """Chỉ quản lý. Body: {name?, description?, start_date?, due_date?}."""
    return not_implemented()


@api_bp.delete("/projects/<int:project_id>")
@login_required
def delete_project(project_id):
    """Chỉ quản lý / admin. Xóa luôn cột mốc, việc, lịch sử, thành viên của dự án."""
    return not_implemented()


@api_bp.get("/projects/<int:project_id>/milestones")
@login_required
def list_milestones(project_id):
    """→ [milestone + task_count + done_count]."""
    return not_implemented()


@api_bp.post("/projects/<int:project_id>/milestones")
@login_required
def create_milestone(project_id):
    """Chỉ quản lý. Body: {title, description?, due_date?} → 201."""
    return not_implemented()


@api_bp.patch("/milestones/<int:milestone_id>")
@login_required
def update_milestone(milestone_id):
    """Chỉ quản lý. Body: {title?, description?, due_date?}. Cột mốc đã nghiệm thu thì không sửa."""
    return not_implemented()


@api_bp.delete("/milestones/<int:milestone_id>")
@login_required
def delete_milestone(milestone_id):
    """Chỉ quản lý. Các việc thuộc cột mốc được giữ lại, chỉ bỏ liên kết."""
    return not_implemented()


@api_bp.post("/milestones/<int:milestone_id>/submit")
@login_required
def submit_milestone(milestone_id):
    """Quản lý gửi nghiệm thu. Mọi việc của cột mốc phải done."""
    return not_implemented()


@api_bp.post("/milestones/<int:milestone_id>/review")
@login_required
def review_milestone(milestone_id):
    """Giám sát nghiệm thu. Body: {action: accept|request_changes, note}. request_changes bắt buộc note.
    Dự án chưa có giám sát thì quản lý được tự nghiệm thu."""
    return not_implemented()


@api_bp.get("/projects/<int:project_id>/tasks")
@login_required
def list_tasks(project_id):
    """Query: ?status=&assignee_id=&milestone_id=&due=overdue|today|week → [task + blocked]."""
    return not_implemented()


@api_bp.post("/projects/<int:project_id>/tasks")
@login_required
def create_task(project_id):
    """Chỉ quản lý. Body: {title, description?, priority?, points?, due_date?, assignee_id?, milestone_id?} → 201."""
    return not_implemented()


@api_bp.get("/tasks/<int:task_id>")
@login_required
def get_task_detail(task_id):
    """→ task + attachments + depends_on + blocked + my_role."""
    return not_implemented()


@api_bp.patch("/tasks/<int:task_id>")
@login_required
def update_task(task_id):
    """Chỉ quản lý. Body: {title?, description?, priority?, points?, due_date?, assignee_id?, milestone_id?}.
    Đổi người nhận, hạn, điểm đều được ghi lịch sử."""
    return not_implemented()


@api_bp.delete("/tasks/<int:task_id>")
@login_required
def delete_task(task_id):
    return not_implemented()


@api_bp.patch("/tasks/<int:task_id>/status")
@login_required
def change_status(task_id):
    """Người được giao hoặc quản lý. Body: {status: todo|in_progress|review, note?}.
    'done' chỉ đi qua /review. Sai luồng → 409 INVALID_TRANSITION."""
    return not_implemented()


@api_bp.post("/tasks/<int:task_id>/review")
@login_required
def review_task(task_id):
    """Chỉ quản lý, task đang 'review'. Body: {action: approve|return, note}. return bắt buộc note."""
    return not_implemented()


@api_bp.post("/tasks/<int:task_id>/dependencies")
@login_required
def add_dependency(task_id):
    """Chỉ quản lý. Body: {depends_on_id} — cùng dự án, không tự phụ thuộc, không tạo vòng."""
    return not_implemented()


@api_bp.delete("/tasks/<int:task_id>/dependencies/<int:depends_on_id>")
@login_required
def remove_dependency(task_id, depends_on_id):
    return not_implemented()


@api_bp.post("/tasks/<int:task_id>/attachments")
@login_required
def add_attachment(task_id):
    """Người được giao hoặc quản lý. multipart/form-data field 'file' HOẶC JSON {url} → 201."""
    return not_implemented()


@api_bp.get("/attachments/<int:attachment_id>/download")
@login_required
def download_attachment(attachment_id):
    return not_implemented()


@api_bp.get("/tasks/<int:task_id>/comments")
@login_required
def list_comments(task_id):
    return not_implemented()


@api_bp.post("/tasks/<int:task_id>/comments")
@login_required
def add_comment(task_id):
    """Mọi người trong dự án (cả giám sát). Body: {content} → 201."""
    return not_implemented()


@api_bp.get("/tasks/<int:task_id>/history")
@login_required
def task_history(task_id):
    return not_implemented()
