"""Hàm nội bộ M10. Chủ sở hữu: Thành viên 2."""
from ..common.responses import fail
from ..extensions import db
from ..m20_accounts.permissions import check_project_access, current_user
from ..models import Task, TaskHistory


def get_task(task_id, leader=False):
    """Lấy task + kiểm tra quyền trên dự án chứa nó. Không có → 404, không quyền → 403."""
    task = db.session.get(Task, task_id)
    if task is None:
        fail(404, "TASK_NOT_FOUND", "Không tìm thấy nhiệm vụ")
    check_project_access(task.project_id, leader=leader)
    return task


def log_history(task, field, old=None, new=None, note=None):
    """BẮT BUỘC gọi mỗi khi đổi status/assignee_id/due_date, duyệt/trả lại, nộp minh chứng.
    M11 tính 'số lần bị trả lại', 'lần cập nhật cuối' từ bảng này."""
    db.session.add(TaskHistory(task_id=task.id, user_id=current_user().id, field=field,
                               old_value=None if old is None else str(old),
                               new_value=None if new is None else str(new), note=note))
