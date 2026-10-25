from flask import render_template

from ..m20_accounts.permissions import page_login_required
from . import pages_bp


@pages_bp.get("/projects")
@page_login_required
def projects():
    return render_template("m06/projects.html")


@pages_bp.get("/projects/<int:project_id>")
@page_login_required
def board(project_id):
    return render_template("m06/board.html", project_id=project_id)


@pages_bp.get("/projects/<int:project_id>/milestones")
@page_login_required
def milestones(project_id):
    return render_template("m06/milestones.html", project_id=project_id)


@pages_bp.get("/tasks/<int:task_id>")
@page_login_required
def task_detail(task_id):
    return render_template("m06/task.html", task_id=task_id)
