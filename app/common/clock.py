"""UTC business clock; persistent demo time is shared by web and worker."""

from datetime import datetime, timezone
from sqlalchemy.types import TypeDecorator, DateTime
from flask import current_app


class UTCDateTime(TypeDecorator):
    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            if value.tzinfo is None:
                raise ValueError("Timezone required")
            return value.astimezone(timezone.utc)

    def process_result_value(self, value, dialect):
        return (
            value.replace(tzinfo=timezone.utc)
            if value and value.tzinfo is None
            else value
        )


def utcnow():
    return datetime.now(timezone.utc)


def now():
    fixed = current_app.config.get("CLOCK_NOW")
    if fixed:
        return fixed
    if current_app.config.get("DEMO_CLOCK_ENABLED"):
        from ..extensions import db
        from ..models.academic import RuntimeSetting

        row = db.session.get(RuntimeSetting, "demo_clock")
        if row and row.value.get("at"):
            return datetime.fromisoformat(row.value["at"])
    return utcnow()


def iso(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    return value.isoformat() if hasattr(value, "isoformat") else value
