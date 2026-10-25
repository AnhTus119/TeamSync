"""API M20 — Tài khoản, SSO và phân quyền. Chủ sở hữu: Thành viên 1."""
import json
import secrets

from flask import request, session

from ..common.responses import fail, ok, require_json
from ..extensions import db
from ..models import (POINTS, PROJECT_ROLES, ROLES, Comment, Invitation, Project, ProjectMember,
                      ProjectTemplate, Task, User, Workspace, WorkspaceMember)
from . import api_bp
from .permissions import (MANAGER, check_project_access, check_workspace_access, current_user,
                          login_required, role_required)
from .services import add_member, ensure_workspace_member


def _check_password(raw):
    if not isinstance(raw, str) or len(raw) < 6:
        fail(400, "VALIDATION_ERROR", "Mật khẩu tối thiểu 6 ký tự")


def _user_by_email(email):
    return User.query.filter_by(email=(email or "").strip().lower()).first()


# ===================== Xác thực =====================
@api_bp.post("/auth/register")
def register():
    """Body: {email, password, full_name} → 201 {data: user}. Tài khoản mới luôn là 'user'."""
    body = require_json("email", "password", "full_name")
    email = body["email"].strip().lower()
    if "@" not in email:
        fail(400, "VALIDATION_ERROR", "Email không hợp lệ")
    if _user_by_email(email):
        fail(409, "EMAIL_EXISTS", "Email đã được sử dụng")
    _check_password(body["password"])
    user = User(email=email, full_name=body["full_name"].strip(), role="user")
    user.set_password(body["password"])
    db.session.add(user)
    db.session.commit()
    return ok(user.to_dict(), 201)


@api_bp.post("/auth/login")
def login():
    """Body: {email, password} → 200 {data: user}; set cookie session."""
    body = require_json("email", "password")
    user = _user_by_email(body["email"])
    if user is None or not user.check_password(body["password"]):
        fail(401, "INVALID_CREDENTIALS", "Sai email hoặc mật khẩu")
    if not user.is_active:
        fail(403, "ACCOUNT_LOCKED", "Tài khoản đã bị khóa")
    session.clear()
    session["user_id"] = user.id
    return ok(user.to_dict())


@api_bp.post("/auth/logout")
def logout():
    session.clear()
    return ok(None)


@api_bp.get("/auth/me")
@login_required
def me():
    return ok(current_user().to_dict())


@api_bp.patch("/auth/me/password")
@login_required
def change_password():
    """Body: {old_password, new_password} → 200."""
    body = require_json("old_password", "new_password")
    user = current_user()
    if not user.check_password(body["old_password"]):
        fail(400, "WRONG_PASSWORD", "Mật khẩu hiện tại không đúng")
    _check_password(body["new_password"])
    user.set_password(body["new_password"])
    db.session.commit()
    return ok(None)


# ===================== Không gian làm việc =====================
@api_bp.get("/workspaces")
@login_required
def list_workspaces():
    """Workspace mình sở hữu hoặc là thành viên (admin: tất cả). Kèm my_role và project_count."""
    user = current_user()
    if user.role == "admin":
        rows = [(w, workspace_role_of(w.id, user.id)) for w in Workspace.query.order_by(Workspace.id)]
    else:
        rows = [(m.workspace, m.role) for m in
                WorkspaceMember.query.filter_by(user_id=user.id).join(Workspace).order_by(Workspace.id)]
    counts = dict(db.session.query(Project.workspace_id, db.func.count(Project.id)).group_by(Project.workspace_id))
    return ok([{**w.to_dict(), "my_role": role, "project_count": counts.get(w.id, 0)} for w, role in rows])


def workspace_role_of(wid, uid):
    m = WorkspaceMember.query.filter_by(workspace_id=wid, user_id=uid).first()
    return m.role if m else None


@api_bp.post("/workspaces")
@login_required
def create_workspace():
    """Body: {name, description?} → 201. Người tạo là chủ (owner)."""
    body = require_json("name")
    ws = Workspace(name=body["name"].strip(), description=body.get("description", ""), owner_id=current_user().id)
    db.session.add(ws)
    db.session.flush()
    db.session.add(WorkspaceMember(workspace_id=ws.id, user_id=current_user().id, role="owner"))
    db.session.commit()
    return ok({**ws.to_dict(), "my_role": "owner", "project_count": 0}, 201)


@api_bp.get("/workspaces/<int:workspace_id>")
@login_required
def get_workspace(workspace_id):
    ws = check_workspace_access(workspace_id)
    return ok({**ws.to_dict(), "my_role": workspace_role_of(ws.id, current_user().id)})


@api_bp.patch("/workspaces/<int:workspace_id>")
@login_required
def update_workspace(workspace_id):
    """Chỉ chủ workspace. Body: {name?, description?}."""
    ws = check_workspace_access(workspace_id, owner=True)
    body = request.get_json(silent=True) or {}
    if "name" in body:
        if not str(body["name"]).strip():
            fail(400, "VALIDATION_ERROR", "Tên không được để trống")
        ws.name = body["name"].strip()
    if "description" in body:
        ws.description = body["description"]
    db.session.commit()
    return ok(ws.to_dict())


@api_bp.delete("/workspaces/<int:workspace_id>")
@login_required
def delete_workspace(workspace_id):
    """Chỉ chủ workspace; chỉ xóa được khi không còn dự án."""
    ws = check_workspace_access(workspace_id, owner=True)
    if Project.query.filter_by(workspace_id=ws.id).count():
        fail(409, "WORKSPACE_NOT_EMPTY", "Hãy xóa hoặc chuyển hết dự án trước khi xóa không gian làm việc")
    db.session.delete(ws)
    db.session.commit()
    return ok(None)


@api_bp.get("/workspaces/<int:workspace_id>/members")
@login_required
def list_workspace_members(workspace_id):
    check_workspace_access(workspace_id)
    members = WorkspaceMember.query.filter_by(workspace_id=workspace_id).all()
    members.sort(key=lambda m: (m.role != "owner", m.joined_at))
    return ok([m.to_dict() for m in members])


@api_bp.post("/workspaces/<int:workspace_id>/members")
@login_required
def add_workspace_member(workspace_id):
    """Chỉ chủ workspace. Body: {email} — người đó phải đã có tài khoản."""
    check_workspace_access(workspace_id, owner=True)
    user = _user_by_email(require_json("email")["email"])
    if user is None:
        fail(404, "USER_NOT_FOUND", "Chưa có tài khoản dùng email này")
    if WorkspaceMember.query.filter_by(workspace_id=workspace_id, user_id=user.id).first():
        fail(409, "ALREADY_MEMBER", "Người này đã ở trong không gian làm việc")
    m = WorkspaceMember(workspace_id=workspace_id, user_id=user.id, role="member")
    db.session.add(m)
    db.session.commit()
    return ok(m.to_dict(), 201)


@api_bp.delete("/workspaces/<int:workspace_id>/members/<int:user_id>")
@login_required
def remove_workspace_member(workspace_id, user_id):
    """Chỉ chủ workspace; không xóa chủ; người còn trong dự án của workspace phải rời dự án trước."""
    ws = check_workspace_access(workspace_id, owner=True)
    m = WorkspaceMember.query.filter_by(workspace_id=workspace_id, user_id=user_id).first()
    if m is None:
        fail(404, "MEMBER_NOT_FOUND", "Người này không ở trong không gian làm việc")
    if m.role == "owner":
        fail(409, "CANNOT_REMOVE_OWNER", "Không thể xóa chủ không gian làm việc")
    in_projects = ProjectMember.query.join(Project).filter(Project.workspace_id == ws.id,
                                                           ProjectMember.user_id == user_id).count()
    if in_projects:
        fail(409, "MEMBER_IN_PROJECTS", f"Người này còn ở {in_projects} dự án trong không gian làm việc")
    db.session.delete(m)
    db.session.commit()
    return ok(None)


# ===================== Thành viên dự án & lời mời =====================
def _member_or_404(project_id, user_id):
    m = ProjectMember.query.filter_by(project_id=project_id, user_id=user_id).first()
    if m is None:
        fail(404, "MEMBER_NOT_FOUND", "Người này không phải thành viên dự án")
    return m


@api_bp.get("/projects/<int:project_id>/members")
@login_required
def list_members(project_id):
    """→ [member], thứ tự: quản lý, thành viên, giám sát."""
    check_project_access(project_id)
    order = {r: i for i, r in enumerate(PROJECT_ROLES)}
    members = ProjectMember.query.filter_by(project_id=project_id).all()
    members.sort(key=lambda m: (order[m.project_role], m.joined_at))
    return ok([m.to_dict() for m in members])


@api_bp.patch("/projects/<int:project_id>/members/<int:user_id>")
@login_required
def update_member(project_id, user_id):
    """Chỉ quản lý. Body: {project_role: manager|member|supervisor}.
    Chuyển 'manager' cho người khác thì quản lý cũ thành 'member'. Dự án luôn có đúng 1 quản lý."""
    check_project_access(project_id, MANAGER)
    role = require_json("project_role")["project_role"]
    if role not in PROJECT_ROLES:
        fail(400, "VALIDATION_ERROR", "project_role phải là: " + ", ".join(PROJECT_ROLES))
    member = _member_or_404(project_id, user_id)
    if role == member.project_role:
        return ok(member.to_dict())
    if member.project_role == "manager":
        fail(409, "LAST_MANAGER", "Hãy chuyển quyền quản lý cho người khác thay vì hạ quyền")
    if role == "supervisor" and _open_tasks(project_id, user_id):
        fail(409, "MEMBER_HAS_TASKS", "Người này còn việc chưa xong, hãy giao lại trước khi chuyển sang giám sát")
    if role == "manager":
        ProjectMember.query.filter_by(project_id=project_id, project_role="manager").update({"project_role": "member"})
    member.project_role = role
    db.session.commit()
    return ok(member.to_dict())


def _open_tasks(project_id, user_id):
    return Task.query.filter(Task.project_id == project_id, Task.assignee_id == user_id,
                             Task.status != "done").count()


@api_bp.delete("/projects/<int:project_id>/members/<int:user_id>")
@login_required
def remove_member(project_id, user_id):
    """Chỉ quản lý; không xóa quản lý; người còn việc chưa xong phải được giao lại trước."""
    check_project_access(project_id, MANAGER)
    member = _member_or_404(project_id, user_id)
    if member.project_role == "manager":
        fail(409, "CANNOT_REMOVE_MANAGER", "Không thể xóa quản lý dự án")
    n = _open_tasks(project_id, user_id)
    if n:
        fail(409, "MEMBER_HAS_TASKS", f"Thành viên còn {n} nhiệm vụ chưa xong, hãy giao lại trước")
    db.session.delete(member)
    db.session.commit()
    return ok(None)


@api_bp.post("/projects/<int:project_id>/invitations")
@login_required
def create_invitation(project_id):
    """Chỉ quản lý. Body: {email, project_role?: member|supervisor} → 201 {data: invitation + accept_url}.
    Ghi chú: chưa gửi email thật — quản lý copy accept_url gửi cho người được mời."""
    check_project_access(project_id, MANAGER)
    body = require_json("email")
    email = body["email"].strip().lower()
    role = body.get("project_role", "member")
    if role not in ("member", "supervisor"):
        fail(400, "VALIDATION_ERROR", "Chỉ mời được với vai trò member hoặc supervisor")
    invitee = _user_by_email(email)
    if invitee and ProjectMember.query.filter_by(project_id=project_id, user_id=invitee.id).first():
        fail(409, "ALREADY_MEMBER", "Người này đã ở trong dự án")
    if Invitation.query.filter_by(project_id=project_id, email=email, status="pending").first():
        fail(409, "INVITATION_EXISTS", "Đã có lời mời đang chờ cho email này")
    inv = Invitation(project_id=project_id, email=email, project_role=role,
                     token=secrets.token_urlsafe(24), invited_by=current_user().id)
    db.session.add(inv)
    db.session.commit()
    return ok({**inv.to_dict(), "accept_url": f"/invitations/{inv.token}"}, 201)


@api_bp.get("/projects/<int:project_id>/invitations")
@login_required
def list_invitations(project_id):
    """Chỉ quản lý → lời mời đang chờ."""
    check_project_access(project_id, MANAGER)
    invs = Invitation.query.filter_by(project_id=project_id, status="pending").order_by(Invitation.id).all()
    return ok([{**i.to_dict(), "accept_url": f"/invitations/{i.token}"} for i in invs])


@api_bp.delete("/invitations/<int:invitation_id>")
@login_required
def revoke_invitation(invitation_id):
    """Quản lý hủy lời mời đang chờ."""
    inv = db.session.get(Invitation, invitation_id)
    if inv is None:
        fail(404, "INVITATION_NOT_FOUND", "Lời mời không tồn tại")
    check_project_access(inv.project_id, MANAGER)
    if inv.status != "pending":
        fail(409, "INVITATION_USED", "Lời mời đã được sử dụng hoặc đã bị hủy")
    inv.status = "revoked"
    db.session.commit()
    return ok(None)


def _invitation_or_404(token):
    inv = Invitation.query.filter_by(token=token).first()
    if inv is None:
        fail(404, "INVITATION_NOT_FOUND", "Lời mời không tồn tại")
    return inv


@api_bp.get("/invitations/<token>")
@login_required
def get_invitation(token):
    """Thông tin lời mời để hiển thị trang nhận lời mời."""
    inv = _invitation_or_404(token)
    project = db.session.get(Project, inv.project_id)
    inviter = db.session.get(User, inv.invited_by)
    return ok({"email": inv.email, "project_role": inv.project_role, "status": inv.status,
               "project": {"id": project.id, "name": project.name},
               "invited_by": inviter.full_name})


@api_bp.post("/invitations/<token>/accept")
@login_required
def accept_invitation(token):
    """User đang đăng nhập (đúng email được mời) nhận lời → 200 {data: member}."""
    inv = _invitation_or_404(token)
    if inv.status != "pending":
        fail(409, "INVITATION_USED", "Lời mời đã được sử dụng hoặc đã bị hủy")
    user = current_user()
    if inv.email != user.email:
        fail(403, "INVITATION_EMAIL_MISMATCH", "Lời mời này dành cho email khác")
    member = ProjectMember.query.filter_by(project_id=inv.project_id, user_id=user.id).first()
    if member is None:
        member = add_member(inv.project_id, user.id, inv.project_role)
        ensure_workspace_member(db.session.get(Project, inv.project_id).workspace_id, user.id)
    inv.status = "accepted"
    db.session.commit()
    return ok(member.to_dict())


# ===================== Quản trị =====================
@api_bp.get("/admin/users")
@role_required("admin")
def admin_list_users():
    """Query: ?q=&role=admin|user&is_active=true|false → [user]."""
    query = User.query
    q = request.args.get("q", "").strip()
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(User.email.ilike(like), User.full_name.ilike(like)))
    if request.args.get("role") in ROLES:
        query = query.filter_by(role=request.args["role"])
    if request.args.get("is_active") in ("true", "false"):
        query = query.filter_by(is_active=request.args["is_active"] == "true")
    return ok([u.to_dict() for u in query.order_by(User.id).all()])


@api_bp.patch("/admin/users/<int:user_id>")
@role_required("admin")
def admin_update_user(user_id):
    """Body: {role?: admin|user, is_active?: bool}. Không tự sửa chính mình."""
    body = request.get_json(silent=True) or {}
    user = db.session.get(User, user_id)
    if user is None:
        fail(404, "USER_NOT_FOUND", "Không tìm thấy người dùng")
    if user.id == current_user().id:
        fail(400, "CANNOT_MODIFY_SELF", "Không thể tự đổi vai trò hoặc tự khóa tài khoản của mình")
    if "role" in body:
        if body["role"] not in ROLES:
            fail(400, "VALIDATION_ERROR", "role phải là: " + ", ".join(ROLES))
        user.role = body["role"]
    if "is_active" in body:
        if not isinstance(body["is_active"], bool):
            fail(400, "VALIDATION_ERROR", "is_active phải là true/false")
        user.is_active = body["is_active"]
    db.session.commit()
    return ok(user.to_dict())


@api_bp.get("/admin/projects")
@role_required("admin")
def admin_list_projects():
    """→ [project + workspace_name + manager + member_count + task_count]."""
    counts = dict(db.session.query(Task.project_id, db.func.count(Task.id)).group_by(Task.project_id))
    result = []
    for p in Project.query.order_by(Project.id).all():
        manager = next((m.user for m in p.members if m.project_role == "manager"), None)
        result.append({**p.to_dict(), "workspace_name": p.workspace.name, "member_count": len(p.members),
                       "task_count": counts.get(p.id, 0), "manager": manager.brief() if manager else None})
    return ok(result)


@api_bp.patch("/admin/comments/<int:comment_id>")
@role_required("admin")
def admin_hide_comment(comment_id):
    """Body: {is_hidden: bool} — ẩn/hiện bình luận vi phạm."""
    comment = db.session.get(Comment, comment_id)
    if comment is None:
        fail(404, "COMMENT_NOT_FOUND", "Không tìm thấy bình luận")
    value = (request.get_json(silent=True) or {}).get("is_hidden")
    if not isinstance(value, bool):
        fail(400, "VALIDATION_ERROR", "is_hidden phải là true/false")
    comment.is_hidden = value
    db.session.commit()
    return ok(comment.to_dict())


def _template_body(body, partial=False):
    data = {}
    if not partial or "name" in body:
        if not str(body.get("name", "")).strip():
            fail(400, "VALIDATION_ERROR", "Thiếu tên mẫu")
        data["name"] = body["name"].strip()
    if "description" in body:
        data["description"] = body["description"]
    for key in ("milestones", "tasks"):
        if key in body:
            if not isinstance(body[key], list):
                fail(400, "VALIDATION_ERROR", f"{key} phải là danh sách")
            for item in body[key]:
                if not isinstance(item, dict) or not str(item.get("title", "")).strip():
                    fail(400, "VALIDATION_ERROR", f"Mỗi phần tử của {key} cần có title")
                if key == "tasks" and item.get("points", 1) not in POINTS:
                    fail(400, "VALIDATION_ERROR", "points phải là 1, 2, 3 hoặc 5")
            data[f"{key}_json"] = json.dumps(body[key], ensure_ascii=False)
    return data


@api_bp.post("/admin/templates")
@role_required("admin")
def admin_create_template():
    """Body: {name, description?, milestones: [{title, offset_days}], tasks: [{title, milestone?, points?, offset_days?}]}."""
    data = _template_body(request.get_json(silent=True) or {})
    if ProjectTemplate.query.filter_by(name=data["name"]).first():
        fail(409, "TEMPLATE_EXISTS", "Đã có mẫu cùng tên")
    t = ProjectTemplate(**data)
    db.session.add(t)
    db.session.commit()
    return ok(t.to_dict(), 201)


@api_bp.patch("/admin/templates/<int:template_id>")
@role_required("admin")
def admin_update_template(template_id):
    t = db.session.get(ProjectTemplate, template_id)
    if t is None:
        fail(404, "TEMPLATE_NOT_FOUND", "Không tìm thấy mẫu dự án")
    for k, v in _template_body(request.get_json(silent=True) or {}, partial=True).items():
        setattr(t, k, v)
    db.session.commit()
    return ok(t.to_dict())


@api_bp.delete("/admin/templates/<int:template_id>")
@role_required("admin")
def admin_delete_template(template_id):
    t = db.session.get(ProjectTemplate, template_id)
    if t is None:
        fail(404, "TEMPLATE_NOT_FOUND", "Không tìm thấy mẫu dự án")
    Project.query.filter_by(template_id=t.id).update({"template_id": None})
    db.session.delete(t)
    db.session.commit()
    return ok(None)
