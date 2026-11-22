"""Prevent legacy endpoints from bypassing academic commands, locking or scope."""

from flask import request, g
from sqlalchemy import event
from sqlalchemy.orm import Session, with_loader_criteria
from ..extensions import db
from ..models import (
    Project,
    Task,
    Milestone,
    Attachment,
    Comment,
    Invitation,
    ProjectMember,
)
from ..common.responses import fail


@event.listens_for(Session, "do_orm_execute")
def filter_legacy(execute_state):
    from flask import has_request_context

    if has_request_context() and g.get("filter_legacy") and execute_state.is_select:
        execute_state.statement = execute_state.statement.options(
            with_loader_criteria(
                Project, lambda p: p.mode == "legacy", include_aliases=True
            )
        )
        academic_ids = (
            db.select(Project.id)
            .where(Project.mode == "academic")
            .execution_options(include_academic=True)
        )
        # Nested subquery cannot use the Project loader criterion above; use table-level expression.
        ptable = Project.__table__
        academic_ids = db.select(ptable.c.id).where(ptable.c.mode == "academic")
        for cls in (Task, Milestone, Attachment, Comment, Invitation, ProjectMember):
            if cls in (Attachment, Comment):
                tt = Task.__table__
                condition = cls.task_id.notin_(
                    db.select(tt.c.id).where(tt.c.project_id.in_(academic_ids))
                )
            else:
                condition = cls.project_id.notin_(academic_ids)
            execute_state.statement = execute_state.statement.options(
                with_loader_criteria(cls, condition, include_aliases=True)
            )


def install_legacy_guard(app):
    @app.before_request
    def guard():
        if (
            not request.path.startswith("/api/")
            or request.path.startswith("/api/v1/")
            or "/auth/" in request.path
        ):
            return
        args = request.view_args or {}
        pid = args.get("project_id")
        models = {
            "task_id": Task,
            "milestone_id": Milestone,
            "attachment_id": Attachment,
            "comment_id": Comment,
            "invitation_id": Invitation,
        }
        for key, cls in models.items():
            if key in args:
                obj = db.session.get(cls, args[key])
                if obj:
                    if cls in (Attachment, Comment):
                        t = db.session.get(Task, obj.task_id)
                        pid = t.project_id if t else None
                    else:
                        pid = obj.project_id
        if pid:
            p = db.session.get(Project, pid)
            if p and p.mode == "academic":
                from .core import project

                project(pid)
                fail(
                    409,
                    "ACADEMIC_API_REQUIRED",
                    "Sử dụng API /api/v1 cho hồ sơ học thuật",
                )
        if request.method == "DELETE" and "workspace_id" in args:
            if Project.query.filter_by(
                workspace_id=args["workspace_id"], mode="academic"
            ).first():
                fail(
                    409,
                    "ACADEMIC_RECORD_PROTECTED",
                    "Không xóa không gian chứa hồ sơ học thuật",
                )
        g.filter_legacy = True
