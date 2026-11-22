import secrets, time, uuid
from collections import defaultdict, deque
from flask import request, session, g, jsonify
from ..common.responses import fail


# Local pilot limit. Multi-instance production must enforce shared limits at ingress.
def install_security(app):
    attempts = defaultdict(deque)
    uploads = defaultdict(deque)

    @app.before_request
    def protect():
        g.request_id = uuid.uuid4().hex
        if request.method in (
            "POST",
            "PUT",
            "PATCH",
            "DELETE",
        ) and request.path.startswith("/api/"):
            if app.config.get("CSRF_ENABLED", True):
                supplied = request.headers.get("X-CSRF-Token", "")
                expected = session.get("csrf", "")
                if not expected or not secrets.compare_digest(supplied, expected):
                    fail(
                        400, "CSRF_FAILED", "Phiên xác nhận không hợp lệ. Tải lại trang"
                    )
        if request.method == "POST" and (
            request.path.endswith("/assets") or request.path.endswith("/evidence")
        ):
            key = session.get("user_id") or request.remote_addr
            queue = uploads[key]
            cut = time.monotonic() - 60
            while queue and queue[0] < cut:
                queue.popleft()
            if len(queue) >= app.config.get("UPLOAD_RATE_LIMIT", 60):
                fail(429, "RATE_LIMITED", "Đã đạt giới hạn tải file trong một phút")
            queue.append(time.monotonic())
        if request.path.endswith("/auth/login") and request.method == "POST":
            key = request.remote_addr or "local"
            queue = attempts[key]
            cut = time.monotonic() - 60
            while queue and queue[0] < cut:
                queue.popleft()
            if len(queue) >= app.config.get("LOGIN_RATE_LIMIT", 20):
                fail(429, "RATE_LIMITED", "Thử lại sau một phút")
            queue.append(time.monotonic())

    @app.after_request
    def headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["X-Request-ID"] = g.get("request_id", "")
        if not request.path.startswith("/static/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/api/auth/csrf")
    @app.get("/api/v1/auth/csrf")
    def csrf():
        session.setdefault("csrf", secrets.token_urlsafe(32))
        return jsonify(data={"token": session["csrf"]})
