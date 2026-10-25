"""Hàm nội bộ M06. Chủ sở hữu: Thành viên 2."""
from datetime import timedelta

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
    """True nếu thêm cạnh task_id → depends_on_id tạo vòng (depends_on_id đã gián tiếp phụ thuộc task_id)."""
    stack, seen = [depends_on_id], set()
    while stack:
        current = stack.pop()
        if current == task_id:
            return True
        if current in seen:
            continue
        seen.add(current)
        stack.extend(d.depends_on_id for d in TaskDependency.query.filter_by(task_id=current))
    return False


def apply_template(project, template, user_id):
    """Tạo cột mốc và việc mẫu. offset_days tính từ ngày bắt đầu dự án."""
    start = project.start_date
    by_title = {}
    for m in template.milestones:
        ms = Milestone(project_id=project.id, title=m["title"], description=m.get("description", ""),
                       due_date=start + timedelta(days=m.get("offset_days", 7)) if start else None)
        db.session.add(ms)
        by_title[m["title"]] = ms
    db.session.flush()
    for t in template.tasks:
        ms = by_title.get(t.get("milestone"))
        task = Task(project_id=project.id, title=t["title"], description=t.get("description", ""),
                    points=t.get("points", 1), milestone_id=ms.id if ms else None, created_by=user_id,
                    due_date=start + timedelta(days=t["offset_days"]) if start and "offset_days" in t else
                    (ms.due_date if ms else None))
        db.session.add(task)
        db.session.flush()
        log_history(task, "created", user_id=user_id, note=f"Tạo từ mẫu {template.name}")
