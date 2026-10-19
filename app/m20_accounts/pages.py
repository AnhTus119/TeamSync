from flask import abort, render_template

from . import pages_bp
from .permissions import current_user, page_login_required


def _admin_only():
    if current_user().role != "admin":
        abort(403)


@pages_bp.get("/login")
def login():
    return render_template("m20/login.html")


@pages_bp.get("/register")
def register():
    return render_template("m20/register.html")


@pages_bp.get("/account")
@page_login_required
def account():
    return render_template("m20/account.html")


@pages_bp.get("/projects/<int:project_id>/members")
@page_login_required
def members(project_id):
    return render_template("m20/members.html", project_id=project_id)


@pages_bp.get("/invitations/<token>")
@page_login_required
def invitation(token):
    return render_template("m20/invitation.html", token=token)


@pages_bp.get("/admin/users")
@page_login_required
def admin_users():
    _admin_only()
    return render_template("m20/admin_users.html")


@pages_bp.get("/admin/projects")
@page_login_required
def admin_projects():
    _admin_only()
    return render_template("m20/admin_projects.html")
