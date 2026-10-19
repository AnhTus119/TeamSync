"""Kiểm tra nhanh BẮT BUỘC chạy trước khi tạo Pull Request:   python tests/smoke.py

Bắt lỗi tích hợp hay gặp nhất khi merge: trùng route giữa 2 module, app không khởi động,
seed hỏng, đăng nhập/phân quyền dùng chung bị sửa sai, format lỗi JSON bị đổi.
"""
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app  # noqa: E402
from app.m20_accounts.permissions import check_project_access  # noqa: E402


def main():
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})

    # 1. Không có 2 route trùng (path + method) giữa các module
    pairs = Counter((r.rule, m) for r in app.url_map.iter_rules() for m in r.methods - {"HEAD", "OPTIONS"})
    dup = [p for p, n in pairs.items() if n > 1]
    assert not dup, f"Trùng route: {dup}"

    # 2. Seed của cả 3 module chạy được
    result = app.test_cli_runner().invoke(args=["seed"])
    assert result.exit_code == 0, result.output

    c = app.test_client()
    # 3. Chưa đăng nhập → 401 đúng format lỗi chuẩn
    r = c.get("/api/auth/me")
    assert r.status_code == 401 and r.get_json()["error"]["code"] == "UNAUTHORIZED", r.get_json()
    assert c.get("/api/khong-ton-tai").get_json()["error"]["code"] == "NOT_FOUND"

    # 4. Đăng nhập được với mọi tài khoản mẫu
    for who in ("admin", "gv", "sv1", "sv2", "sv3", "sv4"):
        r = c.post("/api/auth/login", json={"email": f"{who}@teamsync.local", "password": "123456"})
        assert r.status_code == 200, (who, r.get_json())
        assert "password_hash" not in r.get_json()["data"]
    assert c.post("/api/auth/login", json={"email": "sv1@teamsync.local", "password": "sai"}).status_code == 401

    # 5. Phân quyền dự án (dự án demo id=1: sv1 trưởng nhóm, sv2/sv3 thành viên, gv phụ trách lớp, sv4 ngoài nhóm)
    expect = {("admin", False): 200, ("gv", False): 200, ("sv1", True): 200, ("sv2", False): 200,
              ("sv2", True): 403, ("gv", True): 403, ("sv4", False): 403}
    from app.models import User
    for (who, leader), code in expect.items():
        with app.test_request_context():
            from flask import session
            session["user_id"] = User.query.filter_by(email=f"{who}@teamsync.local").one().id
            try:
                check_project_access(1, leader=leader)
                got = 200
            except Exception as e:  # fail() ném HTTPException
                got = e.response.status_code
        assert got == code, f"check_project_access({who}, leader={leader}) = {got}, mong đợi {code}"
    with app.test_request_context():
        from flask import session
        session["user_id"] = 1
        try:
            check_project_access(999)
            raise AssertionError("dự án không tồn tại phải 404")
        except Exception as e:
            assert e.response.status_code == 404

    # 6. Các trang HTML render được
    c.post("/api/auth/login", json={"email": "admin@teamsync.local", "password": "123456"})  # admin xem được mọi trang
    for url in ("/", "/login", "/courses", "/projects/1", "/projects/1/dashboard", "/admin/users"):
        assert c.get(url).status_code == 200, url

    # 7. Đếm endpoint còn để 501 (đăng nhập admin để không bị chặn 401/403)
    c.post("/api/auth/login", json={"email": "admin@teamsync.local", "password": "123456"})
    sample = {"<int:course_id>": "1", "<int:project_id>": "1", "<int:task_id>": "1",
              "<int:user_id>": "4", "<token>": "x"}
    todo = 0
    for r in app.url_map.iter_rules():
        if not r.rule.startswith("/api") or r.endpoint.endswith("logout"):
            continue
        url = r.rule
        for k, v in sample.items():
            url = url.replace(k, v)
        for m in r.methods - {"HEAD", "OPTIONS"}:
            todo += c.open(url, method=m, json={}).status_code == 501
    print(f"SMOKE OK — còn {todo} endpoint chưa cài đặt (501)")


if __name__ == "__main__":
    main()
