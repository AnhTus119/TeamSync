"""Hàm phân quyền dùng chung cho cả 3 module. Chủ sở hữu: Thành viên 1.

CHỮ KÝ HÀM ĐÃ CHỐT — M10/M11 gọi trực tiếp, không tự viết lại kiểm tra quyền.
Muốn đổi chữ ký → PR "contract:" và báo cả nhóm.

    @login_required                       # chưa đăng nhập → 401
    @role_required("admin")               # sai vai trò hệ thống → 403
    project = check_project_access(pid)               # thành viên / GV của lớp / admin được xem
    project = check_project_access(pid, leader=True)  # chỉ trưởng nhóm (và admin) được sửa
"""
from functools import wraps

from flask import g, redirect, request, session, url_for

from ..common.responses import fail
from ..extensions import db
from ..models import Project, ProjectMember, User


def current_user():
    """User đang đăng nhập (lưu user_id trong Flask Session) hoặc None."""
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
    """'leader' | 'member' | None."""
    m = ProjectMember.query.filter_by(project_id=project_id, user_id=user_id).first()
    return m.project_role if m else None


def check_project_access(project_id, leader=False):
    """Trả về Project nếu user hiện tại có quyền; nếu không thì dừng request với 404/403.

    leader=False: thành viên dự án, giảng viên phụ trách lớp, admin.
    leader=True : chỉ trưởng nhóm của dự án, admin.
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
    if leader:
        if role != "leader":
            fail(403, "FORBIDDEN", "Chỉ trưởng nhóm được thực hiện thao tác này")
        return project
    if role or (user.role == "lecturer" and project.course.lecturer_id == user.id):
        return project
    fail(403, "FORBIDDEN", "Bạn không thuộc dự án này")


def page_login_required(view):
    """Cho route trả HTML: chưa đăng nhập → chuyển về /login."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        if current_user() is None:
            return redirect(url_for("m20_pages.login", next=request.path))
        return view(*args, **kwargs)
    return wrapper
