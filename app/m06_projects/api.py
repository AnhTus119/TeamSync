"""API M06 — Quản lý khoa học (quản lý dự án). Chủ sở hữu: Thành viên 2.

Luồng trạng thái việc: todo → in_progress → review → done
  - sang in_progress: mọi việc phụ thuộc đã done
  - sang review: có ít nhất 1 minh chứng
  - done chỉ qua /review (quản lý duyệt); trả lại → in_progress, bắt buộc ghi lý do
Cột mốc: open → pending_review (quản lý gửi) → accepted | changes_requested (giám sát; dự án không có giám sát thì quản lý)
"""
import os
import uuid
from datetime import date, timedelta

from flask import current_app, request, send_from_directory
from werkzeug.utils import secure_filename

from ..common.responses import fail, ok, require_json
from ..common.utils import now, parse_date
from ..extensions import db
from ..m20_accounts.permissions import (MANAGER, SUPERVISORS, WORKERS, check_project_access,
                                        check_workspace_access, current_user, login_required, project_role)
from ..m20_accounts.services import add_member
from ..models import (POINTS, PRIORITIES, Attachment, Comment, Milestone, Project, ProjectMember,
                      ProjectTemplate, Task, TaskDependency, TaskHistory)
from . import api_bp
from .services import apply_template, creates_cycle, get_milestone, get_task, log_history


def _date(body, key):
    try:
        return parse_date(body.get(key))
    except (TypeError, ValueError):
        fail(400, "VALIDATION_ERROR", f"{key} phải có dạng YYYY-MM-DD")


def _check_assignee(project_id, user_id):
    if user_id is None:
        return None
    if project_role(project_id, user_id) not in WORKERS:
        fail(400, "INVALID_ASSIGNEE", "Người được giao phải là quản lý hoặc thành viên của dự án")
    return user_id


def _check_milestone(project_id, milestone_id):
    if milestone_id is None:
        return None
    ms = db.session.get(Milestone, milestone_id)
    if ms is None or ms.project_id != project_id:
        fail(400, "INVALID_MILESTONE", "Cột mốc không thuộc dự án này")
    return milestone_id


def _with_my_role(project):
    return {**project.to_dict(), "my_role": project_role(project.id, current_user().id),
            "workspace_name": project.workspace.name}


# ===================== Mẫu dự án =====================
@api_bp.get("/templates")
@login_required
def list_templates():
    return ok([t.to_dict() for t in ProjectTemplate.query.order_by(ProjectTemplate.id)])


# ===================== Dự án =====================
@api_bp.get("/projects")
@login_required
def my_projects():
    """Mọi dự án mình tham gia (admin: tất cả), kèm my_role."""
    user = current_user()
    if user.role == "admin":
        projects = Project.query.order_by(Project.id).all()
    else:
        projects = (Project.query.join(ProjectMember).filter(ProjectMember.user_id == user.id)
                    .order_by(Project.id).all())
    return ok([_with_my_role(p) for p in projects])


@api_bp.get("/workspaces/<int:workspace_id>/projects")
@login_required
def list_workspace_projects(workspace_id):
    """Chủ workspace/admin thấy mọi dự án; thành viên chỉ thấy dự án mình tham gia."""
    ws = check_workspace_access(workspace_id)
    user = current_user()
    query = Project.query.filter_by(workspace_id=ws.id)
    if user.role != "admin" and ws.owner_id != user.id:
        query = query.join(ProjectMember).filter(ProjectMember.user_id == user.id)
    return ok([_with_my_role(p) for p in query.order_by(Project.id)])


@api_bp.post("/workspaces/<int:workspace_id>/projects")
@login_required
def create_project(workspace_id):
    """Thành viên workspace. Body: {name, description?, start_date?, due_date?, template_id?} → 201.
    Người tạo thành quản lý (add_member của M20); nếu có template_id thì tạo sẵn cột mốc và việc."""
    check_workspace_access(workspace_id)
    body = require_json("name")
    start, due = _date(body, "start_date"), _date(body, "due_date")
    if start and due and due < start:
        fail(400, "VALIDATION_ERROR", "Hạn kết thúc phải sau ngày bắt đầu")
    template = None
    if body.get("template_id") is not None:
        template = db.session.get(ProjectTemplate, body["template_id"])
        if template is None:
            fail(404, "TEMPLATE_NOT_FOUND", "Không tìm thấy mẫu dự án")
    user = current_user()
    project = Project(workspace_id=workspace_id, name=body["name"].strip(), description=body.get("description", ""),
                      start_date=start or date.today(), due_date=due,
                      template_id=template.id if template else None, created_by=user.id)
    db.session.add(project)
    db.session.flush()
    add_member(project.id, user.id, "manager")
    if template:
        apply_template(project, template, user.id)
    db.session.commit()
    return ok(_with_my_role(project), 201)


@api_bp.get("/projects/<int:project_id>")
@login_required
def get_project(project_id):
    return ok(_with_my_role(check_project_access(project_id)))


@api_bp.patch("/projects/<int:project_id>")
@login_required
def update_project(project_id):
    """Chỉ quản lý. Body: {name?, description?, start_date?, due_date?}."""
    project = check_project_access(project_id, MANAGER)
    body = request.get_json(silent=True) or {}
    if "name" in body:
        if not str(body["name"]).strip():
            fail(400, "VALIDATION_ERROR", "Tên dự án không được để trống")
        project.name = body["name"].strip()
    if "description" in body:
        project.description = body["description"]
    for key in ("start_date", "due_date"):
        if key in body:
            setattr(project, key, _date(body, key))
    db.session.commit()
    return ok(_with_my_role(project))


@api_bp.delete("/projects/<int:project_id>")
@login_required
def delete_project(project_id):
    """Chỉ quản lý / admin. Xóa luôn cột mốc, việc, lịch sử, thành viên của dự án."""
    project = check_project_access(project_id, MANAGER)
    db.session.delete(project)
    db.session.commit()
    return ok(None)


# ===================== Cột mốc =====================
@api_bp.get("/projects/<int:project_id>/milestones")
@login_required
def list_milestones(project_id):
    """→ [milestone + task_count + done_count]."""
    project = check_project_access(project_id)
    result = []
    for ms in project.milestones:
        tasks = Task.query.filter_by(milestone_id=ms.id).all()
        result.append({**ms.to_dict(), "task_count": len(tasks),
                       "done_count": sum(t.status == "done" for t in tasks)})
    return ok(result)


@api_bp.post("/projects/<int:project_id>/milestones")
@login_required
def create_milestone(project_id):
    """Chỉ quản lý. Body: {title, description?, due_date?} → 201."""
    check_project_access(project_id, MANAGER)
    body = require_json("title")
    ms = Milestone(project_id=project_id, title=body["title"].strip(), description=body.get("description", ""),
                   due_date=_date(body, "due_date"))
    db.session.add(ms)
    db.session.commit()
    return ok(ms.to_dict(), 201)


@api_bp.patch("/milestones/<int:milestone_id>")
@login_required
def update_milestone(milestone_id):
    """Chỉ quản lý. Body: {title?, description?, due_date?}. Cột mốc đã nghiệm thu thì không sửa."""
    ms = get_milestone(milestone_id, MANAGER)
    if ms.status == "accepted":
        fail(409, "MILESTONE_ACCEPTED", "Cột mốc đã được nghiệm thu")
    body = request.get_json(silent=True) or {}
    if "title" in body:
        if not str(body["title"]).strip():
            fail(400, "VALIDATION_ERROR", "Tiêu đề không được để trống")
        ms.title = body["title"].strip()
    if "description" in body:
        ms.description = body["description"]
    if "due_date" in body:
        ms.due_date = _date(body, "due_date")
    db.session.commit()
    return ok(ms.to_dict())


@api_bp.delete("/milestones/<int:milestone_id>")
@login_required
def delete_milestone(milestone_id):
    """Chỉ quản lý. Các việc thuộc cột mốc được giữ lại, chỉ bỏ liên kết."""
    ms = get_milestone(milestone_id, MANAGER)
    Task.query.filter_by(milestone_id=ms.id).update({"milestone_id": None})
    db.session.delete(ms)
    db.session.commit()
    return ok(None)


@api_bp.post("/milestones/<int:milestone_id>/submit")
@login_required
def submit_milestone(milestone_id):
    """Quản lý gửi nghiệm thu. Mọi việc của cột mốc phải done."""
    ms = get_milestone(milestone_id, MANAGER)
    if ms.status not in ("open", "changes_requested"):
        fail(409, "INVALID_TRANSITION", "Cột mốc đang chờ nghiệm thu hoặc đã nghiệm thu")
    pending = Task.query.filter(Task.milestone_id == ms.id, Task.status != "done").count()
    if pending:
        fail(409, "MILESTONE_NOT_READY", f"Còn {pending} việc chưa hoàn thành trong cột mốc")
    ms.status = "pending_review"
    db.session.commit()
    return ok(ms.to_dict())


@api_bp.post("/milestones/<int:milestone_id>/review")
@login_required
def review_milestone(milestone_id):
    """Giám sát nghiệm thu. Body: {action: accept|request_changes, note}. request_changes bắt buộc note.
    Dự án chưa có giám sát thì quản lý được tự nghiệm thu."""
    ms = get_milestone(milestone_id)
    user = current_user()
    role = project_role(ms.project_id, user.id)
    has_supervisor = ProjectMember.query.filter_by(project_id=ms.project_id, project_role="supervisor").count()
    if not (user.role == "admin" or role in SUPERVISORS or (role == "manager" and not has_supervisor)):
        fail(403, "FORBIDDEN", "Chỉ người giám sát được nghiệm thu cột mốc")
    body = require_json("action")
    if body["action"] not in ("accept", "request_changes"):
        fail(400, "VALIDATION_ERROR", "action phải là accept hoặc request_changes")
    if ms.status != "pending_review":
        fail(409, "INVALID_TRANSITION", "Cột mốc chưa được gửi nghiệm thu")
    note = (body.get("note") or "").strip()
    if body["action"] == "request_changes" and not note:
        fail(400, "VALIDATION_ERROR", "Yêu cầu sửa phải ghi rõ nội dung cần sửa")
    ms.status = "accepted" if body["action"] == "accept" else "changes_requested"
    ms.review_note, ms.reviewed_by, ms.reviewed_at = note or None, user.id, now()
    db.session.commit()
    return ok(ms.to_dict())


# ===================== Nhiệm vụ =====================
@api_bp.get("/projects/<int:project_id>/tasks")
@login_required
def list_tasks(project_id):
    """Query: ?status=&assignee_id=&milestone_id=&due=overdue|today|week → [task + blocked]."""
    check_project_access(project_id)
    query = Task.query.filter_by(project_id=project_id)
    args = request.args
    if args.get("status"):
        query = query.filter_by(status=args["status"])
    if args.get("assignee_id", "").isdigit():
        query = query.filter_by(assignee_id=int(args["assignee_id"]))
    if args.get("milestone_id", "").isdigit():
        query = query.filter_by(milestone_id=int(args["milestone_id"]))
    today = date.today()
    due = args.get("due")
    if due == "overdue":
        query = query.filter(Task.due_date < today, Task.status != "done")
    elif due == "today":
        query = query.filter(Task.due_date == today)
    elif due == "week":
        query = query.filter(Task.due_date >= today, Task.due_date <= today + timedelta(days=7))
    tasks = query.order_by(Task.due_date.is_(None), Task.due_date, Task.id).all()
    return ok([{**t.to_dict(), "blocked": _blocked(t)} for t in tasks])


def _blocked(task):
    return any(d.depends_on.status != "done" for d in task.depends_on)


@api_bp.post("/projects/<int:project_id>/tasks")
@login_required
def create_task(project_id):
    """Chỉ quản lý. Body: {title, description?, priority?, points?, due_date?, assignee_id?, milestone_id?} → 201."""
    check_project_access(project_id, MANAGER)
    body = require_json("title")
    priority = body.get("priority", "medium")
    points = body.get("points", 1)
    if priority not in PRIORITIES:
        fail(400, "VALIDATION_ERROR", "priority phải là: " + ", ".join(PRIORITIES))
    if points not in POINTS:
        fail(400, "VALIDATION_ERROR", "points phải là 1, 2, 3 hoặc 5")
    task = Task(project_id=project_id, title=body["title"].strip(), description=body.get("description", ""),
                priority=priority, points=points, due_date=_date(body, "due_date"),
                assignee_id=_check_assignee(project_id, body.get("assignee_id")),
                milestone_id=_check_milestone(project_id, body.get("milestone_id")),
                created_by=current_user().id)
    db.session.add(task)
    db.session.flush()
    log_history(task, "created", new=task.title)
    db.session.commit()
    return ok(task.to_dict(), 201)


@api_bp.get("/tasks/<int:task_id>")
@login_required
def get_task_detail(task_id):
    """→ task + attachments + depends_on + blocked + my_role."""
    task = get_task(task_id)
    return ok({**task.to_dict(), "blocked": _blocked(task),
               "attachments": [a.to_dict() for a in task.attachments],
               "depends_on": [{"id": d.depends_on.id, "title": d.depends_on.title, "status": d.depends_on.status}
                              for d in task.depends_on],
               "my_role": project_role(task.project_id, current_user().id)})


@api_bp.patch("/tasks/<int:task_id>")
@login_required
def update_task(task_id):
    """Chỉ quản lý. Body: {title?, description?, priority?, points?, due_date?, assignee_id?, milestone_id?}.
    Đổi người nhận, hạn, điểm đều được ghi lịch sử."""
    task = get_task(task_id, MANAGER)
    body = request.get_json(silent=True) or {}
    if "title" in body:
        if not str(body["title"]).strip():
            fail(400, "VALIDATION_ERROR", "Tiêu đề không được để trống")
        task.title = body["title"].strip()
    if "description" in body:
        task.description = body["description"]
    if "priority" in body:
        if body["priority"] not in PRIORITIES:
            fail(400, "VALIDATION_ERROR", "priority phải là: " + ", ".join(PRIORITIES))
        task.priority = body["priority"]
    tracked = {}
    if "points" in body:
        if body["points"] not in POINTS:
            fail(400, "VALIDATION_ERROR", "points phải là 1, 2, 3 hoặc 5")
        tracked["points"] = body["points"]
    if "due_date" in body:
        tracked["due_date"] = _date(body, "due_date")
    if "assignee_id" in body:
        tracked["assignee_id"] = _check_assignee(task.project_id, body["assignee_id"])
    if "milestone_id" in body:
        task.milestone_id = _check_milestone(task.project_id, body["milestone_id"])
    for field, value in tracked.items():
        old = getattr(task, field)
        if old != value:
            setattr(task, field, value)
            log_history(task, field, old, value)
    db.session.commit()
    return ok(task.to_dict())


@api_bp.delete("/tasks/<int:task_id>")
@login_required
def delete_task(task_id):
    task = get_task(task_id, MANAGER)
    db.session.delete(task)
    db.session.commit()
    return ok(None)


ALLOWED_MOVES = {("todo", "in_progress"), ("in_progress", "todo"), ("in_progress", "review")}


@api_bp.patch("/tasks/<int:task_id>/status")
@login_required
def change_status(task_id):
    """Người được giao hoặc quản lý. Body: {status: todo|in_progress|review, note?}.
    'done' chỉ đi qua /review. Sai luồng → 409 INVALID_TRANSITION."""
    task = get_task(task_id, WORKERS)
    user = current_user()
    if user.role != "admin" and project_role(task.project_id, user.id) != "manager" and task.assignee_id != user.id:
        fail(403, "FORBIDDEN", "Chỉ người được giao hoặc quản lý được đổi trạng thái")
    body = require_json("status")
    new = body["status"]
    if (task.status, new) not in ALLOWED_MOVES:
        fail(409, "INVALID_TRANSITION", f"Không thể chuyển từ {task.status} sang {new}")
    if new == "in_progress" and task.status == "todo" and _blocked(task):
        fail(409, "BLOCKED_BY_DEPENDENCY", "Còn việc phụ thuộc chưa hoàn thành")
    if new == "review" and not task.attachments:
        fail(409, "EVIDENCE_REQUIRED", "Cần nộp ít nhất một minh chứng trước khi gửi duyệt")
    log_history(task, "status", task.status, new, body.get("note"))
    task.status = new
    db.session.commit()
    return ok(task.to_dict())


@api_bp.post("/tasks/<int:task_id>/review")
@login_required
def review_task(task_id):
    """Chỉ quản lý, task đang 'review'. Body: {action: approve|return, note}. return bắt buộc note."""
    task = get_task(task_id, MANAGER)
    body = require_json("action")
    if body["action"] not in ("approve", "return"):
        fail(400, "VALIDATION_ERROR", "action phải là approve hoặc return")
    if task.status != "review":
        fail(409, "INVALID_TRANSITION", "Nhiệm vụ chưa được gửi duyệt")
    note = (body.get("note") or "").strip()
    if body["action"] == "return" and not note:
        fail(400, "VALIDATION_ERROR", "Trả lại phải ghi rõ lý do")
    new = "done" if body["action"] == "approve" else "in_progress"
    log_history(task, "review", body["action"], new, note or None)
    log_history(task, "status", task.status, new)
    task.status = new
    task.completed_at = now() if new == "done" else None
    db.session.commit()
    return ok(task.to_dict())


# ===================== Phụ thuộc =====================
@api_bp.post("/tasks/<int:task_id>/dependencies")
@login_required
def add_dependency(task_id):
    """Chỉ quản lý. Body: {depends_on_id} — cùng dự án, không tự phụ thuộc, không tạo vòng."""
    task = get_task(task_id, MANAGER)
    dep_id = require_json("depends_on_id")["depends_on_id"]
    dep = db.session.get(Task, dep_id)
    if dep is None or dep.project_id != task.project_id:
        fail(400, "INVALID_DEPENDENCY", "Việc phụ thuộc phải thuộc cùng dự án")
    if dep.id == task.id:
        fail(400, "INVALID_DEPENDENCY", "Một việc không thể phụ thuộc chính nó")
    if TaskDependency.query.filter_by(task_id=task.id, depends_on_id=dep.id).first():
        fail(409, "DEPENDENCY_EXISTS", "Phụ thuộc này đã có")
    if creates_cycle(task.id, dep.id):
        fail(409, "DEPENDENCY_CYCLE", "Thêm phụ thuộc này sẽ tạo vòng lặp")
    db.session.add(TaskDependency(task_id=task.id, depends_on_id=dep.id))
    log_history(task, "dependency", None, dep.id)
    db.session.commit()
    return ok({"task_id": task.id, "depends_on_id": dep.id}, 201)


@api_bp.delete("/tasks/<int:task_id>/dependencies/<int:depends_on_id>")
@login_required
def remove_dependency(task_id, depends_on_id):
    task = get_task(task_id, MANAGER)
    d = TaskDependency.query.filter_by(task_id=task.id, depends_on_id=depends_on_id).first()
    if d is None:
        fail(404, "DEPENDENCY_NOT_FOUND", "Không có phụ thuộc này")
    db.session.delete(d)
    log_history(task, "dependency", depends_on_id, None)
    db.session.commit()
    return ok(None)


# ===================== Minh chứng, bình luận, lịch sử =====================
@api_bp.post("/tasks/<int:task_id>/attachments")
@login_required
def add_attachment(task_id):
    """Người được giao hoặc quản lý. multipart/form-data field 'file' HOẶC JSON {url} → 201."""
    task = get_task(task_id, WORKERS)
    user = current_user()
    if user.role != "admin" and project_role(task.project_id, user.id) != "manager" and task.assignee_id != user.id:
        fail(403, "FORBIDDEN", "Chỉ người được giao hoặc quản lý được nộp minh chứng")
    if task.status == "done":
        fail(409, "TASK_DONE", "Nhiệm vụ đã hoàn thành")
    file = request.files.get("file")
    if file and file.filename:
        ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
        if ext not in current_app.config["ALLOWED_EXTENSIONS"]:
            fail(400, "FILE_TYPE_NOT_ALLOWED", "Chỉ nhận: " + ", ".join(sorted(current_app.config["ALLOWED_EXTENSIONS"])))
        folder = os.path.join(current_app.instance_path, current_app.config["UPLOAD_FOLDER"])
        os.makedirs(folder, exist_ok=True)
        stored = f"{uuid.uuid4().hex}.{ext}"
        file.save(os.path.join(folder, stored))
        att = Attachment(task_id=task.id, uploaded_by=user.id, kind="file", url=stored,
                         filename=secure_filename(file.filename) or stored)
    else:
        url = ((request.get_json(silent=True) or {}).get("url") or "").strip()
        if not url.startswith(("http://", "https://")):
            fail(400, "VALIDATION_ERROR", "Cần file hoặc url bắt đầu bằng http:// hoặc https://")
        att = Attachment(task_id=task.id, uploaded_by=user.id, kind="link", url=url, filename=url)
    db.session.add(att)
    db.session.flush()
    log_history(task, "attachment", None, att.filename)
    db.session.commit()
    return ok(att.to_dict(), 201)


@api_bp.get("/attachments/<int:attachment_id>/download")
@login_required
def download_attachment(attachment_id):
    att = db.session.get(Attachment, attachment_id)
    if att is None or att.kind != "file":
        fail(404, "ATTACHMENT_NOT_FOUND", "Không tìm thấy file")
    get_task(att.task_id)
    folder = os.path.join(current_app.instance_path, current_app.config["UPLOAD_FOLDER"])
    return send_from_directory(folder, att.url, as_attachment=True, download_name=att.filename)


@api_bp.get("/tasks/<int:task_id>/comments")
@login_required
def list_comments(task_id):
    get_task(task_id)
    return ok([c.to_dict() for c in Comment.query.filter_by(task_id=task_id).order_by(Comment.id)])


@api_bp.post("/tasks/<int:task_id>/comments")
@login_required
def add_comment(task_id):
    """Mọi người trong dự án (cả giám sát). Body: {content} → 201."""
    get_task(task_id)
    content = require_json("content")["content"].strip()
    if not content:
        fail(400, "VALIDATION_ERROR", "Nội dung không được để trống")
    c = Comment(task_id=task_id, user_id=current_user().id, content=content[:2000])
    db.session.add(c)
    db.session.commit()
    return ok(c.to_dict(), 201)


@api_bp.get("/tasks/<int:task_id>/history")
@login_required
def task_history(task_id):
    get_task(task_id)
    return ok([h.to_dict() for h in TaskHistory.query.filter_by(task_id=task_id).order_by(TaskHistory.id)])
