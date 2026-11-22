"""Backfill old deadlines and evidence truthfully; install immutable record guards.
Revision ID: c70420261108
Revises: bbb9c163f4ca
"""

from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo
from pathlib import Path
import hashlib, uuid
from alembic import op
import sqlalchemy as sa
from flask import current_app

revision = "c70420261108"
down_revision = "bbb9c163f4ca"
branch_labels = None
depends_on = None

IMMUTABLE = (
    "evidence_asset",
    "evidence_revision",
    "evidence_revision_asset",
    "claim_revision",
    "peer_response_revision",
    "assessment_snapshot",
    "appeal_decision",
    "audit_event",
    "final_submission",
)


def upgrade():
    conn = op.get_bind()
    pg = conn.dialect.name == "postgresql"
    meta = sa.MetaData()
    tasks = sa.Table("task", meta, autoload_with=conn)
    milestones = sa.Table("milestone", meta, autoload_with=conn)
    assets = sa.Table("evidence_asset", meta, autoload_with=conn)
    attachments = sa.Table("attachment", meta, autoload_with=conn)
    at = datetime.now(timezone.utc)
    for table in (tasks, milestones):
        for row in conn.execute(sa.select(table)).mappings().all():
            if table is tasks:
                conn.execute(
                    table.update()
                    .where(table.c.id == row["id"])
                    .values(
                        submission_time_unknown=True,
                        primary_assignee_id=row["assignee_id"],
                    )
                )
            if row["due_date"]:
                due = datetime.combine(
                    row["due_date"], time(23, 59, 59), ZoneInfo("Asia/Ho_Chi_Minh")
                ).astimezone(timezone.utc)
                data = {"due_at": due}
                if table is tasks:
                    data.update(
                        original_due_at=due,
                        deadline_inferred=True,
                        submission_time_unknown=True,
                        primary_assignee_id=row["assignee_id"],
                    )
                conn.execute(
                    table.update().where(table.c.id == row["id"]).values(**data)
                )
    old_root = Path(current_app.config["UPLOAD_FOLDER"]).resolve()
    private = Path(current_app.config["PRIVATE_STORAGE"]).resolve()
    private.mkdir(parents=True, exist_ok=True)
    for row in conn.execute(sa.select(attachments)).mappings().all():
        values = {
            "task_id": row["task_id"],
            "uploaded_by": row["uploaded_by"],
            "kind": row["kind"],
            "legacy_attachment_id": row["id"],
            "original_filename": row["filename"],
            "created_at": at,
            "updated_at": at,
            "version": 1,
            "size_bytes": 0,
            "integrity_status": (
                "external_mutable" if row["kind"] == "link" else "missing"
            ),
        }
        if row["kind"] == "link":
            values["url"] = row["url"]
        else:
            path = old_root / row["url"]
            if (
                not path.is_symlink()
                and path.is_file()
                and path.resolve().parent == old_root
            ):
                key = uuid.uuid4().hex
                raw = path.read_bytes()
                (private / key).write_bytes(raw)
                values.update(
                    storage_key=key,
                    sha256=hashlib.sha256(raw).hexdigest(),
                    size_bytes=len(raw),
                    integrity_status="legacy_file",
                    mime_type="application/octet-stream",
                )
        conn.execute(assets.insert().values(**values))
    if pg:
        # use_alter circular FKs need explicit creation after both tables exist.
        names = {x["name"] for x in sa.inspect(conn).get_foreign_keys("task")}
        if "fk_task_submission" not in names:
            op.create_foreign_key(
                "fk_task_submission",
                "task",
                "task_submission",
                ["latest_submission_id"],
                ["id"],
            )
        conn.execute(
            sa.text(
                "CREATE FUNCTION teamsync_immutable() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'immutable academic record'; END $$"
            )
        )
        for table in IMMUTABLE:
            conn.execute(
                sa.text(
                    f"CREATE TRIGGER immutable_{table} BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION teamsync_immutable()"
                )
            )
        conn.execute(
            sa.text(
                """CREATE FUNCTION teamsync_finalized() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF (SELECT status FROM project WHERE id=OLD.project_id) IN ('finalized','archived') THEN RAISE EXCEPTION 'finalized academic record'; END IF;
          RETURN COALESCE(NEW, OLD);
        END $$"""
            )
        )
        for table in ("task", "milestone"):
            conn.execute(
                sa.text(
                    f"CREATE TRIGGER finalized_{table} BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION teamsync_finalized()"
                )
            )
    else:
        for table in IMMUTABLE:
            for operation in ("UPDATE", "DELETE"):
                conn.exec_driver_sql(
                    f"CREATE TRIGGER immutable_{table}_{operation.lower()} BEFORE {operation} ON {table} BEGIN SELECT RAISE(ABORT, 'immutable academic record'); END"
                )
        for table in ("task", "milestone"):
            for operation in ("UPDATE", "DELETE"):
                conn.exec_driver_sql(
                    f"CREATE TRIGGER finalized_{table}_{operation.lower()} BEFORE {operation} ON {table} WHEN (SELECT status FROM project WHERE id=OLD.project_id) IN ('finalized','archived') AND (SELECT mode FROM project WHERE id=OLD.project_id)='academic' BEGIN SELECT RAISE(ABORT, 'finalized academic record'); END"
                )


def downgrade():
    raise RuntimeError(
        "Restore the pre-upgrade backup; downgrade destroys academic history"
    )
