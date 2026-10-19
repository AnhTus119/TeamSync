"""API M20 — Tài khoản, SSO & phân quyền. Chủ sở hữu: Thành viên 1.
Đường dẫn/method theo contract đã chốt. Mọi response dùng ok()/fail()."""
import secrets

from flask import request, session

from ..common.responses import fail, ok, require_json
from ..extensions import db
from ..models import PROJECT_ROLES, ROLES, Invitation, Project, ProjectMember, Task, User
from . import api_bp
from .permissions import check_project_access, current_user, login_required, role_required
from .services import add_member


def _member_or_404(project_id, user_id):
    m = ProjectMember.query.filter_by(project_id=project_id, user_id=user_id).first()
    if m is None:
        fail(404, "MEMBER_NOT_FOUND", "Người này không phải thành viên dự án")
    return m


def _check_password(raw):
    if not isinstance(raw, str) or len(raw) < 6:
        fail(400, "VALIDATION_ERROR", "Mật khẩu tối thiểu 6 ký tự")


# ---------- Xác thực ----------
@api_bp.post("/auth/register")
def register():
    """Body: {email, password, full_name} → 201 {data: user}. Tài khoản mới luôn là student."""
    body = require_json("email", "password", "full_name")
    email = body["email"].strip().lower()
    if "@" not in email:
        fail(400, "VALIDATION_ERROR", "Email không hợp lệ")
    if User.query.filter_by(email=email).first():
        fail(409, "EMAIL_EXISTS", "Email đã được sử dụng")
    _check_password(body["password"])
    user = User(email=email, full_name=body["full_name"].strip(), role="student")
    user.set_password(body["password"])
    db.session.add(user)
    db.session.commit()
    return ok(user.to_dict(), 201)


@api_bp.post("/auth/login")
def login():
    """Body: {email, password} → 200 {data: user}; set cookie session."""
    body = require_json("email", "password")
    user = User.query.filter_by(email=body["email"].strip().lower()).first()
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


# ---------- Thành viên & lời mời ----------
@api_bp.post("/projects/<int:project_id>/invitations")
@login_required
def create_invitation(project_id):
    """Chỉ trưởng nhóm. Body: {email} → 201 {data: invitation + accept_url}.
    Ghi chú: chưa gửi email thật — trưởng nhóm copy accept_url gửi cho bạn qua chat."""
    check_project_access(project_id, leader=True)
    email = require_json("email")["email"].strip().lower()
    invitee = User.query.filter_by(email=email).first()
    if invitee and ProjectMember.query.filter_by(project_id=project_id, user_id=invitee.id).first():
        fail(409, "ALREADY_MEMBER", "Người này đã là thành viên dự án")
    if Invitation.query.filter_by(project_id=project_id, email=email, status="pending").first():
        fail(409, "INVITATION_EXISTS", "Đã có lời mời đang chờ cho email này")
    inv = Invitation(project_id=project_id, email=email, token=secrets.token_urlsafe(24),
                     invited_by=current_user().id)
    db.session.add(inv)
    db.session.commit()
    data = inv.to_dict()
    data["accept_url"] = f"/invitations/{inv.token}"
    return ok(data, 201)


@api_bp.post("/invitations/<token>/accept")
@login_required
def accept_invitation(token):
    """User đang đăng nhập (đúng email được mời) nhận lời → 200 {data: member}."""
    inv = Invitation.query.filter_by(token=token).first()
    if inv is None:
        fail(404, "INVITATION_NOT_FOUND", "Lời mời không tồn tại")
    if inv.status != "pending":
        fail(409, "INVITATION_USED", "Lời mời đã được sử dụng hoặc đã bị hủy")
    user = current_user()
    if inv.email != user.email:
        fail(403, "INVITATION_EMAIL_MISMATCH", "Lời mời này dành cho email khác")
    member = ProjectMember.query.filter_by(project_id=inv.project_id, user_id=user.id).first()
    if member is None:
        member = add_member(inv.project_id, user.id, "member")
    inv.status = "accepted"
    db.session.commit()
    return ok(member.to_dict())


@api_bp.get("/projects/<int:project_id>/members")
@login_required
def list_members(project_id):
    """→ 200 {data: [member...]}, trưởng nhóm đứng đầu."""
    check_project_access(project_id)
    members = ProjectMember.query.filter_by(project_id=project_id).all()
    members.sort(key=lambda m: (m.project_role != "leader", m.joined_at))
    return ok([m.to_dict() for m in members])


@api_bp.patch("/projects/<int:project_id>/members/<int:user_id>")
@login_required
def update_member(project_id, user_id):
    """Chỉ trưởng nhóm. Body: {project_role}. Chuyển 'leader' cho người khác thì trưởng nhóm cũ thành 'member'.
    Mỗi dự án luôn có đúng một trưởng nhóm."""
    check_project_access(project_id, leader=True)
    role = require_json("project_role")["project_role"]
    if role not in PROJECT_ROLES:
        fail(400, "VALIDATION_ERROR", "project_role phải là: " + ", ".join(PROJECT_ROLES))
    member = _member_or_404(project_id, user_id)
    if role == member.project_role:
        return ok(member.to_dict())
    if role == "leader":
        ProjectMember.query.filter_by(project_id=project_id, project_role="leader").update({"project_role": "member"})
    else:  # hạ trưởng nhóm duy nhất → dự án mất trưởng nhóm
        fail(409, "LAST_LEADER", "Hãy chuyển quyền trưởng nhóm cho người khác thay vì hạ quyền")
    member.project_role = role
    db.session.commit()
    return ok(member.to_dict())


@api_bp.delete("/projects/<int:project_id>/members/<int:user_id>")
@login_required
def remove_member(project_id, user_id):
    """Chỉ trưởng nhóm; không xóa trưởng nhóm; người còn task chưa xong phải được giao lại trước. → 200."""
    check_project_access(project_id, leader=True)
    member = _member_or_404(project_id, user_id)
    if member.project_role == "leader":
        fail(409, "CANNOT_REMOVE_LEADER", "Không thể xóa trưởng nhóm")
    open_tasks = Task.query.filter(Task.project_id == project_id, Task.assignee_id == user_id,
                                   Task.status != "done").count()
    if open_tasks:
        fail(409, "MEMBER_HAS_TASKS", f"Thành viên còn {open_tasks} nhiệm vụ chưa xong, hãy giao lại trước")
    db.session.delete(member)
    db.session.commit()
    return ok(None)


# ---------- Quản trị ----------
@api_bp.get("/admin/users")
@role_required("admin")
def admin_list_users():
    """Query: ?q=&role=&is_active=true|false → 200 {data: [user...]}."""
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
    """Body: {role?, is_active?} → 200 {data: user}. Không tự sửa chính mình."""
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
    """→ 200 {data: [project + course_code + leader + member_count + task_count]}."""
    counts = dict(db.session.query(Task.project_id, db.func.count(Task.id)).group_by(Task.project_id).all())
    result = []
    for p in Project.query.order_by(Project.id).all():
        leader = next((m.user for m in p.members if m.project_role == "leader"), None)
        d = p.to_dict()
        d.update(course_code=p.course.code, member_count=len(p.members), task_count=counts.get(p.id, 0),
                 leader={"id": leader.id, "full_name": leader.full_name} if leader else None)
        result.append(d)
    return ok(result)
