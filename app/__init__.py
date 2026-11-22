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
    if app.config.get("APP_ENV") == "production":
        secret = app.config.get("SECRET_KEY", "")
        if len(secret) < 32 or secret.startswith(
            ("dev", "doi-", "replace-", "change-me")
        ):
            raise RuntimeError(
                "Production requires a random SECRET_KEY of at least 32 characters"
            )
        if app.config.get("DEMO_CLOCK_ENABLED") or app.config.get("DEBUG"):
            raise RuntimeError("Production forbids demo clock and debug")
    app.json.ensure_ascii = False
    os.makedirs(app.instance_path, exist_ok=True)

    db.init_app(app)
    from flask_migrate import Migrate

    Migrate(app, db, compare_type=True)
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

    from .common.security import install_security

    install_security(app)
    from .academic import api as academic_api, register_domains

    register_domains()
    app.register_blueprint(academic_api)
    from .academic.legacy import install_legacy_guard

    install_legacy_guard(app)
    from .academic.pages import pages, install_shell_overrides

    app.register_blueprint(pages)
    install_shell_overrides(app)
    from .collab import init_app as init_collaboration

    init_collaboration(app)
    from .academic.cli import register_cli

    register_cli(app)
    from .m20_accounts.permissions import current_user

    @app.context_processor
    def inject_user():
        return {"me": current_user()}

    @app.get("/")
    def home():
        return redirect("/home" if current_user() else "/login")

    @app.cli.command("seed")
    def seed_command():
        """Xóa sạch DB, tạo lại bảng và nạp dữ liệu mẫu theo thứ tự M20 → M06 → M17."""
        if not app.config.get("TESTING"):
            raise RuntimeError(
                "Destructive legacy seed is test-only. Use db upgrade and seed-demo"
            )
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
