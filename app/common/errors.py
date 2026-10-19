from werkzeug.exceptions import HTTPException
from flask import request

from .responses import error

CODES = {400: "BAD_REQUEST", 401: "UNAUTHORIZED", 403: "FORBIDDEN", 404: "NOT_FOUND",
         405: "METHOD_NOT_ALLOWED", 409: "CONFLICT", 413: "FILE_TOO_LARGE"}


def register_error_handlers(app):
    @app.errorhandler(HTTPException)
    def handle_http(e):
        if not request.path.startswith("/api/"):
            return e
        if e.response is not None:  # đã là response chuẩn từ fail()
            return e.response
        return error(CODES.get(e.code, "HTTP_ERROR"), e.description, e.code)
