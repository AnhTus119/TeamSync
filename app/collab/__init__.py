"""Collaboration features retain ownership by M20, M06 and M17."""
from flask import Blueprint
bp = Blueprint('teamwork', __name__, url_prefix='/api/v1')


def init_app(app):
    from flask import request
    @app.before_request
    def assignment_upload_limit():
        if request.method == 'POST' and request.path.startswith('/api/v1/assignments/') and request.path.endswith('/files'):
            request.max_content_length = 101 * 1024 * 1024
    from . import api, identity, organization, personal
    from ..academic import workflow
    app.register_blueprint(workflow.bp)
    app.register_blueprint(bp)
    from .privacy import install_privacy
    install_privacy(app)
    @app.cli.command('teamwork-setup')
    def setup():
        from .seed import setup_teamwork
        setup_teamwork()
        print('Mẫu cộng tác và liên kết MR đã sẵn sàng')
