"""API M10 — LMS/LCMS & tài nguyên học tập. Chủ sở hữu: Thành viên 2.
Route nào còn `return not_implemented()` là việc cần làm. Đường dẫn/method đã chốt theo contract.

Luồng trạng thái: todo → in_progress → review → done
  - sang 'review' cần ≥ 1 Attachment
  - chỉ trưởng nhóm duyệt (review → done, set completed_at) hoặc trả lại (review → in_progress, bắt buộc note)
"""
from ..common.responses import not_implemented
from ..m20_accounts.permissions import login_required, role_required
from . import api_bp


# ---------- Lớp học phần ----------
@api_bp.get("/courses")
@login_required
def list_courses():
    """GV: lớp mình dạy; SV: lớp có dự án mình tham gia; admin: tất cả → 200 {data: [course]}."""
    return not_implemented()


@api_bp.post("/courses")
@role_required("lecturer", "admin")
def create_course():
    """Body: {code, name} → 201 {data: course}."""
    return not_implemented()


# ---------- Dự án nhóm ----------
@api_bp.get("/courses/<int:course_id>/projects")
@login_required
def list_projects(course_id):
    return not_implemented()


@api_bp.post("/courses/<int:course_id>/projects")
@login_required
def create_project(course_id):
    """Body: {name, description?, due_date?} → 201 {data: project}.
    Sau khi tạo: m20_accounts.services.add_member(project.id, user.id, "leader")."""
    return not_implemented()


@api_bp.get("/projects/<int:project_id>")
@login_required
def get_project(project_id):
    return not_implemented()


@api_bp.patch("/projects/<int:project_id>")
@login_required
def update_project(project_id):
    """Chỉ trưởng nhóm. Body: {name?, description?, due_date?}."""
    return not_implemented()


@api_bp.delete("/projects/<int:project_id>")
@login_required
def delete_project(project_id):
    """Chỉ trưởng nhóm / admin."""
    return not_implemented()


# ---------- Nhiệm vụ ----------
@api_bp.get("/projects/<int:project_id>/tasks")
@login_required
def list_tasks(project_id):
    """Query: ?status=&assignee_id=&due=overdue|today|week → 200 {data: [task]}."""
    return not_implemented()


@api_bp.post("/projects/<int:project_id>/tasks")
@login_required
def create_task(project_id):
    """Chỉ trưởng nhóm. Body: {title, description?, priority?, due_date?, assignee_id?} → 201.
    assignee_id phải là thành viên dự án. Ghi log_history(task, "created")."""
    return not_implemented()


@api_bp.get("/tasks/<int:task_id>")
@login_required
def get_task(task_id):
    return not_implemented()


@api_bp.patch("/tasks/<int:task_id>")
@login_required
def update_task(task_id):
    """Chỉ trưởng nhóm. Body: {title?, description?, priority?, due_date?, assignee_id?}."""
    return not_implemented()


@api_bp.delete("/tasks/<int:task_id>")
@login_required
def delete_task(task_id):
    return not_implemented()


@api_bp.patch("/tasks/<int:task_id>/status")
@login_required
def change_status(task_id):
    """Người được giao hoặc trưởng nhóm. Body: {status: todo|in_progress|review, note?}.
    Không cho set 'done' ở đây — 'done' chỉ đi qua /review. Sai luồng → 409 INVALID_TRANSITION."""
    return not_implemented()


@api_bp.post("/tasks/<int:task_id>/review")
@login_required
def review_task(task_id):
    """Chỉ trưởng nhóm, task đang 'review'. Body: {action: approve|return, note}. return bắt buộc note."""
    return not_implemented()


# ---------- Minh chứng, bình luận, lịch sử ----------
@api_bp.post("/tasks/<int:task_id>/attachments")
@login_required
def add_attachment(task_id):
    """multipart/form-data field 'file' HOẶC JSON {url} → 201 {data: attachment}. Chỉ pdf, png, jpg, docx, zip."""
    return not_implemented()


@api_bp.get("/tasks/<int:task_id>/comments")
@login_required
def list_comments(task_id):
    return not_implemented()


@api_bp.post("/tasks/<int:task_id>/comments")
@login_required
def add_comment(task_id):
    """Body: {content} → 201."""
    return not_implemented()


@api_bp.get("/tasks/<int:task_id>/history")
@login_required
def task_history(task_id):
    return not_implemented()
