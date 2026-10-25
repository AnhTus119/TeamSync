"""Hàm nội bộ M06. Chủ sở hữu: Thành viên 2."""
import os
from datetime import timedelta

from flask import current_app

from ..common.responses import fail
from ..extensions import db
from ..m20_accounts.permissions import check_project_access, current_user
from ..models import (Attachment, Comment, Invitation, Milestone, PeerReview, Project, ProjectMember, Task,
                      TaskDependency, TaskHistory)


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


def delete_tasks(task_ids):
    """Xóa việc kèm bình luận, minh chứng, lịch sử và phụ thuộc theo CẢ HAI chiều.
    SQLite không bật khóa ngoại nên ondelete="CASCADE" không chạy; nếu không xóa tay, dòng phụ thuộc
    trỏ tới việc đã xóa làm GET /api/projects/{id}/tasks lỗi 500. Không commit; trả về tên file cần xóa sau commit."""
    if not task_ids:
        return []
    files = [a.url for a in Attachment.query.filter(Attachment.task_id.in_(task_ids), Attachment.kind == "file")]
    TaskDependency.query.filter(db.or_(TaskDependency.task_id.in_(task_ids),
                                       TaskDependency.depends_on_id.in_(task_ids))).delete(synchronize_session=False)
    for model in (Comment, Attachment, TaskHistory):
        model.query.filter(model.task_id.in_(task_ids)).delete(synchronize_session=False)
    Task.query.filter(Task.id.in_(task_ids)).delete(synchronize_session=False)
    return files


def delete_project(project):
    """Xóa dự án và mọi dữ liệu thuộc nó (cả lời mời của M20 và đánh giá chéo của M17, để không còn dòng mồ côi).
    Không commit; trả về tên file cần xóa sau commit."""
    files = delete_tasks([tid for (tid,) in db.session.query(Task.id).filter_by(project_id=project.id)])
    for model in (Milestone, ProjectMember, Invitation, PeerReview):
        model.query.filter_by(project_id=project.id).delete(synchronize_session=False)
    Project.query.filter_by(id=project.id).delete(synchronize_session=False)
    db.session.expunge(project)
    return files


def remove_files(names):
    """Gọi SAU commit: xóa file minh chứng khỏi instance/uploads/. File đã mất thì bỏ qua."""
    folder = os.path.join(current_app.instance_path, current_app.config["UPLOAD_FOLDER"])
    for name in names:
        try:
            os.remove(os.path.join(folder, name))
        except OSError:
            pass
