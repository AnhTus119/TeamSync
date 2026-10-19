from flask import Blueprint

api_bp = Blueprint("m11_api", __name__)
pages_bp = Blueprint("m11_pages", __name__)

from . import api, pages  # noqa: E402,F401
