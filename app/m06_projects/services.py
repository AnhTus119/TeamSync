"""Hàm nội bộ M06. Chủ sở hữu: Thành viên 2."""
from ..common.responses import fail
from ..extensions import db
from ..m20_accounts.permissions import check_project_access, current_user
from ..models import Milestone, Task, TaskDependency, TaskHistory


def get_task(task_id, roles=None):
    """Lấy task + kiểm tra quyền trên dự án chứa nó (roles giống check_project_access)."""
    task = db.session.get(Task, task_id)
    if task is None:
        fail(404, "TASK_NOT_FOUND", "Không tìm thấy nhiệm vụ")
    check_project_access(task.project_id, roles)
    return task


def get_milestone(milestone_id, roles=None):
    ms = db.session.get(Milestone, milestone_id)
    if ms is None:
        fail(404, "MILESTONE_NOT_FOUND", "Không tìm thấy cột mốc")
    check_project_access(ms.project_id, roles)
    return ms


def log_history(task, field, old=None, new=None, note=None, user_id=None):
    """BẮT BUỘC gọi mỗi khi đổi trạng thái, người nhận, hạn, điểm; duyệt/trả lại; nộp minh chứng; thêm phụ thuộc.
    M17 tính số lần bị trả lại, lần cập nhật cuối và chạy lại luật cảnh báo theo thời gian từ bảng này."""
    db.session.add(TaskHistory(task_id=task.id, user_id=user_id or current_user().id, field=field,
                               old_value=None if old is None else str(old),
                               new_value=None if new is None else str(new), note=note))


def creates_cycle(task_id, depends_on_id):
    """TODO(TV2): True nếu thêm phụ thuộc task_id → depends_on_id tạo vòng lặp."""
    raise NotImplementedError


def apply_template(project, template, user_id):
    """TODO(TV2): tạo cột mốc và việc từ mẫu; hạn = ngày bắt đầu dự án + offset_days."""
    raise NotImplementedError
