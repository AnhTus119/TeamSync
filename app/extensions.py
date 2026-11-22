from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event
from sqlalchemy.engine import Engine

db = SQLAlchemy()


@event.listens_for(Engine, "connect")
def _sqlite_fk_on(dbapi_conn, _):
    # SQLite mặc định TẮT khóa ngoại → ON DELETE CASCADE không chạy (xóa workspace để lại dòng mồ côi)
    if dbapi_conn.__class__.__module__.startswith("sqlite3"):
        dbapi_conn.execute("PRAGMA foreign_keys=ON")
