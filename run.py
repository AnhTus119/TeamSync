"""Local TeamSync server: migrate, prepare demo data, then serve the app."""

import os, secrets, threading, logging
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)
if os.getenv("APP_ENV") == "production":
    raise RuntimeError("run.py chỉ dành cho môi trường phát triển")
os.environ["APP_ENV"] = "development"
os.environ["DEMO_CLOCK_ENABLED"] = "1"
INSTANCE = Path(os.environ.get("TEAMSYNC_DATA_DIR", str(ROOT / "instance"))).resolve()
INSTANCE.mkdir(parents=True, exist_ok=True)
os.environ["DATABASE_URL"] = "sqlite:///" + str(
    INSTANCE / "teamsync-workspace.db"
).replace("\\", "/")
os.environ["PRIVATE_STORAGE"] = str(INSTANCE / "private")
secret_file = INSTANCE / "pycharm-secret.txt"
if not secret_file.exists():
    secret_file.write_text(secrets.token_urlsafe(48), encoding="utf-8")
    try:
        secret_file.chmod(0o600)
    except OSError:
        pass
os.environ["SECRET_KEY"] = secret_file.read_text(encoding="utf-8").strip()
from app import create_app

app = create_app()


def prepare():
    from flask_migrate import upgrade
    from app.academic.workflow_seed import seed_demo
    with app.app_context():
        upgrade(directory=str(ROOT / "migrations"))
        seed_demo()
        from app.extensions import db
        from app.models.academic import RuntimeSetting
        from app.academic.workflow_seed import KEY
        if not db.session.get(RuntimeSetting, KEY):
            print(
                "CẢNH BÁO: database " + str(INSTANCE / "teamsync-workspace.db") + " không phải dữ liệu demo hiện tại,"
                " nên các tài khoản trong README (mật khẩu 12345) có thể không đăng nhập được.\n"
                "  Kiểm tra: python tools/kiem_tra_tai_khoan.py\n"
                "  Tạo lại dữ liệu demo: tắt run.py, đổi tên thư mục instance (để sao lưu) rồi chạy lại run.py."
            )


def background_worker(stop):
    from app.common.jobs import dispatch_outbox

    elapsed = 900
    while not stop.is_set():
        with app.app_context():
            try:
                if elapsed >= 900:
                    from app.academic.workflow import deadline_reminders
                    deadline_reminders()
                    elapsed = 0
                dispatch_outbox()
            except Exception:
                logging.getLogger(__name__).exception("Local worker failed; will retry")
        elapsed += 5
        stop.wait(5)


if __name__ == "__main__":
    prepare()
    stop = threading.Event()
    threading.Thread(target=background_worker, args=(stop,), daemon=True).start()
    print(
        f"TeamSync: http://127.0.0.1:{os.getenv('PORT', '5000')} | minhanh@sv.teamsync.test / khanhan@gv.teamsync.test | mật khẩu: 12345 (xem docs/TAI_KHOAN_DEMO.md)"
    )
    try:
        app.run(
            host="127.0.0.1",
            port=int(os.getenv("PORT", "5000")),
            debug=False,
            use_reloader=False,
        )
    finally:
        stop.set()
