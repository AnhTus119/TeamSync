from flask import render_template

from ..m20_accounts.permissions import page_login_required
from . import pages_bp


@pages_bp.get("/projects/<int:project_id>/dashboard")
@page_login_required
def dashboard(project_id):
    return render_template("m17/dashboard.html", project_id=project_id)


@pages_bp.get("/projects/<int:project_id>/contributions")
@page_login_required
def contributions(project_id):
    return render_template("m17/contributions.html", project_id=project_id)


@pages_bp.get("/workspaces/<int:workspace_id>/overview")
@page_login_required
def workspace_overview(workspace_id):
    return render_template("m17/overview.html", workspace_id=workspace_id)
