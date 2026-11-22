from flask import Blueprint, render_template, redirect
from ..m20_accounts.permissions import page_login_required

pages = Blueprint("academic_pages", __name__)


def shell(**kwargs):
    return render_template("academic/workspace.html")


for n, path in enumerate(
    (
        "/projects/<int:pid>/board",
        "/home",
        "/courses",
        "/courses/<int:cid>",
        "/courses/<int:cid>/imports/new",
        "/courses/<int:cid>/risk-cases",
        "/assignments/<int:aid>/settings",
        "/assignments/<int:aid>/policy",
        "/assignments/<int:aid>/groups",
        "/assignments/<int:aid>/evaluations",
        "/assignments/<int:aid>/portfolio/<int:uid>",
        "/tasks/<int:tid>/submit",
        "/risk-cases/<int:rid>",
        "/admin/operations",
        "/notifications",
        "/my-tasks",
        "/portfolios",
    )
):
    pages.add_url_rule(path, endpoint=f"view_{n}", view_func=page_login_required(shell))


def install_shell_overrides(app):
    @app.before_request
    def override_legacy_pages():
        from flask import request
        from ..models import Task, Project
        from ..extensions import db
        from ..m20_accounts.permissions import current_user

        if request.method != "GET":
            return
        if request.path == "/account":
            return page_login_required(shell)()
        if request.path == "/login":
            return shell()
        if request.path in ("/admin/users","/admin/templates"):
            if not current_user():
                return redirect("/login")
            if current_user().role != "admin":
                from flask import abort

                abort(403)
            return shell()
        if request.path in ("/workspaces", "/register", "/admin/projects", "/admin/templates"):
            return redirect("/home")
        args = request.view_args or {}
        pid = args.get("project_id")
        if "task_id" in args:
            t = db.session.get(Task, args["task_id"])
            pid = t.project_id if t else None
        if pid and not request.path.startswith("/api/"):
            p = db.session.get(Project, pid)
            if p and p.mode == "academic":
                if not current_user():
                    return redirect("/login")
                return shell()
