"""Định dạng JSON chung cho MỌI API. Không tự jsonify theo kiểu khác.

Thành công: {"data": ...}                  (HTTP 200/201)
Lỗi:        {"error": {"code": "...", "message": "..."}}  (HTTP 4xx/5xx)
"""
from flask import abort, jsonify, make_response


def ok(data=None, status=200):
    return jsonify({"data": data}), status


def error(code, message, status):
    return jsonify({"error": {"code": code, "message": message}}), status


def fail(status, code, message):
    """Dừng request ngay và trả lỗi chuẩn. Dùng: fail(404, "TASK_NOT_FOUND", "Không tìm thấy nhiệm vụ")."""
    abort(make_response(*error(code, message, status)))


def not_implemented():
    """Endpoint đã có trong contract nhưng chưa code. Chủ module thay bằng code thật."""
    return error("NOT_IMPLEMENTED", "Endpoint chưa được cài đặt", 501)


def require_json(*fields):
    """Lấy body JSON và kiểm tra các trường bắt buộc. Thiếu → 400 VALIDATION_ERROR."""
    from flask import request
    body = request.get_json(silent=True) or {}
    missing = [f for f in fields if body.get(f) in (None, "")]
    if missing:
        fail(400, "VALIDATION_ERROR", "Thiếu trường: " + ", ".join(missing))
    return body
