from flask import render_template

from ..m20_accounts.permissions import page_login_required
from . import pages_bp


@pages_bp.get("/projects/<int:project_id>/dashboard")
@page_login_required
def dashboard(project_id):
    return render_template("m11/dashboard.html", project_id=project_id)
