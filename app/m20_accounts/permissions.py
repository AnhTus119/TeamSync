"""Hàm phân quyền dùng chung cho cả 3 module. Chủ sở hữu: Thành viên 1.

CHỮ KÝ HÀM ĐÃ CHỐT — M06/M17 gọi trực tiếp, không tự viết lại kiểm tra quyền.

    @login_required                                     # chưa đăng nhập → 401
    @role_required("admin")                             # sai vai trò hệ thống → 403
    project = check_project_access(pid)                 # mọi người trong dự án + chủ workspace + admin được xem
    project = check_project_access(pid, MANAGER)        # chỉ quản lý dự án (và admin)
    project = check_project_access(pid, WORKERS)        # quản lý + thành viên (không gồm giám sát)
    ws = check_workspace_access(wid)                    # thành viên workspace + admin
    ws = check_workspace_access(wid, owner=True)        # chủ workspace + admin
"""
from functools import wraps

from flask import abort, g, redirect, request, session, url_for

from ..common.responses import fail
from ..extensions import db
from ..models import Project, ProjectMember, User, Workspace, WorkspaceMember

MANAGER = ("manager",)
WORKERS = ("manager", "member")
SUPERVISORS = ("supervisor",)


def current_user():
    """User đang đăng nhập (user_id lưu trong Flask Session) hoặc None. Tài khoản bị khóa bị đăng xuất ngay."""
    if "user" not in g:
        uid = session.get("user_id")
        g.user = db.session.get(User, uid) if uid else None
        if g.user is not None and not g.user.is_active:
            session.clear()
            g.user = None
    return g.user


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if current_user() is None:
            fail(401, "UNAUTHORIZED", "Bạn cần đăng nhập")
        return view(*args, **kwargs)
    return wrapper


def role_required(*roles):
    def deco(view):
        @wraps(view)
        @login_required
        def wrapper(*args, **kwargs):
            if current_user().role not in roles:
                fail(403, "FORBIDDEN", "Bạn không có quyền thực hiện thao tác này")
            return view(*args, **kwargs)
        return wrapper
    return deco


def project_role(project_id, user_id):
    """'manager' | 'member' | 'supervisor' | None."""
    m = ProjectMember.query.filter_by(project_id=project_id, user_id=user_id).first()
    return m.project_role if m else None


def workspace_role(workspace_id, user_id):
    """'owner' | 'member' | None."""
    m = WorkspaceMember.query.filter_by(workspace_id=workspace_id, user_id=user_id).first()
    return m.role if m else None


def check_project_access(project_id, roles=None):
    """Trả về Project nếu user hiện tại có quyền; nếu không thì dừng request với 401/404/403.

    roles=None   : mọi vai trò trong dự án, chủ workspace chứa dự án, admin (quyền XEM).
    roles=(...)  : chỉ những vai trò dự án được liệt kê, và admin.
    """
    user = current_user()
    if user is None:
        fail(401, "UNAUTHORIZED", "Bạn cần đăng nhập")
    project = db.session.get(Project, project_id)
    if project is None:
        fail(404, "PROJECT_NOT_FOUND", "Không tìm thấy dự án")
    if user.role == "admin":
        return project
    role = project_role(project_id, user.id)
    if roles is None:
        if role or workspace_role(project.workspace_id, user.id) == "owner":
            return project
        fail(403, "FORBIDDEN", "Bạn không thuộc dự án này")
    if role not in roles:
        fail(403, "FORBIDDEN", "Vai trò của bạn trong dự án không được thực hiện thao tác này")
    return project


def check_workspace_access(workspace_id, owner=False):
    user = current_user()
    if user is None:
        fail(401, "UNAUTHORIZED", "Bạn cần đăng nhập")
    ws = db.session.get(Workspace, workspace_id)
    if ws is None:
        fail(404, "WORKSPACE_NOT_FOUND", "Không tìm thấy không gian làm việc")
    if user.role == "admin":
        return ws
    role = workspace_role(workspace_id, user.id)
    if role == "owner" or (role and not owner):
        return ws
    fail(403, "FORBIDDEN", "Chỉ chủ không gian làm việc được thực hiện thao tác này" if owner
         else "Bạn không thuộc không gian làm việc này")


def page_login_required(view):
    """Cho route trả HTML: chưa đăng nhập → chuyển về /login."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        if current_user() is None:
            return redirect(url_for("m20_pages.login", next=request.path))
        return view(*args, **kwargs)
    return wrapper


def page_admin_required(view):
    @wraps(view)
    @page_login_required
    def wrapper(*args, **kwargs):
        if current_user().role != "admin":
            abort(403)
        return view(*args, **kwargs)
    return wrapper
