"""App factory. FILE DÙNG CHUNG — cả 3 blueprint đã được đăng ký sẵn, không ai cần sửa file này."""
from flask import Flask, render_template

from .config import Config
from .extensions import db


def create_app(config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config)
    if config:
        app.config.update(config)
    app.json.ensure_ascii = False

    db.init_app(app)
    from . import models  # noqa: F401  (đăng ký toàn bộ bảng)

    from .common.errors import register_error_handlers
    register_error_handlers(app)

    from .m20_accounts import api_bp as m20_api, pages_bp as m20_pages
    from .m10_lms import api_bp as m10_api, pages_bp as m10_pages
    from .m11_analytics import api_bp as m11_api, pages_bp as m11_pages
    for bp in (m20_api, m10_api, m11_api):
        app.register_blueprint(bp, url_prefix="/api")
    for bp in (m20_pages, m10_pages, m11_pages):
        app.register_blueprint(bp)

    @app.get("/")
    def home():
        return render_template("home.html")

    @app.cli.command("seed")
    def seed_command():
        """Xóa sạch DB, tạo lại bảng và nạp dữ liệu mẫu của cả 3 module (theo thứ tự M20 → M10 → M11)."""
        from .m20_accounts.seed import seed as seed_m20
        from .m10_lms.seed import seed as seed_m10
        from .m11_analytics.seed import seed as seed_m11
        db.drop_all()
        db.create_all()
        seed_m20()
        seed_m10()
        seed_m11()
        db.session.commit()
        print("Seed xong. Tài khoản mẫu: xem README.md")

    return app
