from datetime import date, datetime


def now():
    # Ghi chú: giờ máy chủ, không lưu múi giờ — đủ cho app 1 server; chuyển sang UTC nếu deploy nhiều vùng
    return datetime.now().replace(microsecond=0)


def iso(value):
    """datetime/date → chuỗi ISO 8601 cho JSON ("2026-10-20T09:30:00" / "2026-10-20")."""
    return value.isoformat() if isinstance(value, (date, datetime)) else value


def parse_date(value):
    """Chuỗi "YYYY-MM-DD" → date; None nếu rỗng. Sai định dạng → ValueError."""
    return date.fromisoformat(value) if value else None
