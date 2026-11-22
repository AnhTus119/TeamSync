from flask import render_template

from . import pages_bp
from .permissions import page_admin_required, page_login_required


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


@pages_bp.get("/workspaces")
@page_login_required
def workspaces():
    return render_template("m20/workspaces.html")


@pages_bp.get("/workspaces/<int:workspace_id>")
@page_login_required
def workspace_detail(workspace_id):
    return render_template("m20/workspace_detail.html", workspace_id=workspace_id)


@pages_bp.get("/projects/<int:project_id>/members")
@page_login_required
def members(project_id):
    return render_template("m20/members.html", project_id=project_id)


@pages_bp.get("/invitations/<token>")
@page_login_required
def invitation(token):
    return render_template("m20/invitation.html", token=token)


@pages_bp.get("/admin/users")
@page_admin_required
def admin_users():
    return render_template("m20/admin_users.html")


@pages_bp.get("/admin/projects")
@page_admin_required
def admin_projects():
    return render_template("m20/admin_projects.html")


@pages_bp.get("/admin/templates")
@page_admin_required
def admin_templates():
    return render_template("m20/admin_templates.html")
