"""App factory. FILE DÙNG CHUNG — cả 3 module đã được đăng ký sẵn."""
import os

from flask import Flask, redirect, url_for

from .config import Config
from .extensions import db


def create_app(config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config)
    if config:
        app.config.update(config)
    app.json.ensure_ascii = False
    os.makedirs(app.instance_path, exist_ok=True)

    db.init_app(app)
    from . import models  # noqa: F401  (đăng ký toàn bộ bảng)

    from .common.errors import register_error_handlers
    register_error_handlers(app)

    from .m20_accounts import api_bp as m20_api, pages_bp as m20_pages
    from .m06_projects import api_bp as m06_api, pages_bp as m06_pages
    from .m17_reports import api_bp as m17_api, pages_bp as m17_pages
    for bp in (m20_api, m06_api, m17_api):
        app.register_blueprint(bp, url_prefix="/api")
    for bp in (m20_pages, m06_pages, m17_pages):
        app.register_blueprint(bp)

    from .m20_accounts.permissions import current_user

    @app.context_processor
    def inject_user():
        return {"me": current_user()}

    @app.get("/")
    def home():
        return redirect(url_for("m06_pages.projects") if current_user() else url_for("m20_pages.login"))

    @app.cli.command("seed")
    def seed_command():
        """Xóa sạch DB, tạo lại bảng và nạp dữ liệu mẫu theo thứ tự M20 → M06 → M17."""
        from .m20_accounts.seed import seed as seed_m20
        from .m06_projects.seed import seed as seed_m06
        from .m17_reports.seed import seed as seed_m17
        db.drop_all()
        db.create_all()
        seed_m20()
        seed_m06()
        seed_m17()
        db.session.commit()
        print("Seed xong. Tài khoản mẫu: xem README.md (mật khẩu 123456)")

    return app
