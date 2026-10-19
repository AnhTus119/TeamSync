from flask import render_template

from ..m20_accounts.permissions import page_login_required
from . import pages_bp


@pages_bp.get("/courses")
@page_login_required
def courses():
    return render_template("m10/courses.html")


@pages_bp.get("/projects/<int:project_id>")
@page_login_required
def project_board(project_id):
    return render_template("m10/board.html", project_id=project_id)
