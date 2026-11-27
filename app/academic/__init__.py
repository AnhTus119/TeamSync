from flask import Blueprint

api = Blueprint("academic_api", __name__, url_prefix="/api/v1")


def register_domains():
    from ..m20_accounts import academic_api as accounts
    from ..m06_projects import academic_api as projects
    from ..m17_reports import academic_api as reports
    from . import collaboration
    from . import evidence  # noqa: F401  (registers /submissions/<sid>/refer)
