"""Kiểm tra nhanh BẮT BUỘC chạy trước khi tạo Pull Request:   python tests/smoke.py

Bắt lỗi tích hợp hay gặp nhất khi merge: trùng route giữa 2 module, app không khởi động, seed hỏng,
đăng nhập/phân quyền dùng chung bị sửa sai, format lỗi JSON bị đổi, trang HTML không render.
"""
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from flask import session  # noqa: E402

from app import create_app  # noqa: E402
from app.m20_accounts.permissions import MANAGER, check_project_access  # noqa: E402
from app.models import User  # noqa: E402


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

    # 4. Đăng nhập được với mọi tài khoản mẫu, không lộ mật khẩu
    for who in ("admin", "gv", "sv1", "sv2", "sv3", "sv4"):
        r = c.post("/api/auth/login", json={"email": f"{who}@teamsync.local", "password": "123456"})
        assert r.status_code == 200, (who, r.get_json())
        assert "password_hash" not in r.get_json()["data"]

    # 5. Phân quyền dự án demo (id=1): sv1 quản lý, sv2/sv3 thành viên, gv giám sát + chủ workspace, sv4 ngoài dự án
    expect = {("admin", None): 200, ("gv", None): 200, ("sv1", MANAGER): 200, ("sv2", None): 200,
              ("sv2", MANAGER): 403, ("gv", MANAGER): 403, ("sv4", None): 403}
    for (who, roles), code in expect.items():
        with app.test_request_context():
            session["user_id"] = User.query.filter_by(email=f"{who}@teamsync.local").one().id
            try:
                check_project_access(1, roles)
                got = 200
            except Exception as e:  # fail() ném HTTPException
                got = e.response.status_code
        assert got == code, f"check_project_access({who}, {roles}) = {got}, mong đợi {code}"

    # 6. Mọi trang HTML render được (admin xem được mọi trang)
    c.post("/api/auth/login", json={"email": "admin@teamsync.local", "password": "123456"})
    pages = ("/projects", "/projects/1", "/projects/1/milestones", "/tasks/1", "/projects/1/dashboard",
             "/projects/1/contributions", "/projects/1/members", "/workspaces", "/workspaces/1", "/account",
             "/admin/users", "/admin/projects", "/admin/templates", "/invitations/abc")
    for url in pages:
        assert c.get(url).status_code == 200, url
    assert c.get("/login").status_code == 200 and c.get("/register").status_code == 200

    # 7. Mọi API GET của dự án demo trả 200 với admin
    for url in ("/api/projects/1", "/api/projects/1/tasks", "/api/projects/1/milestones", "/api/projects/1/members",
                "/api/projects/1/stats", "/api/projects/1/risks", "/api/projects/1/health",
                "/api/projects/1/contributions", "/api/projects/1/activity", "/api/projects/1/peer-reviews",
                "/api/projects/1/report", "/api/projects/1/risk-evaluation", "/api/workspaces/1/overview",
                "/api/templates", "/api/workspaces", "/api/projects"):
        assert c.get(url).status_code in (200, 501), url  # 501 = module chưa cài đặt

    todo = 0
    for r in app.url_map.iter_rules():
        if not r.rule.startswith("/api") or r.endpoint.endswith("logout"):
            continue
        url = r.rule
        for k, v in {"<int:workspace_id>": "1", "<int:project_id>": "1", "<int:task_id>": "1", "<int:milestone_id>": "1",
                     "<int:user_id>": "99", "<int:invitation_id>": "99", "<int:comment_id>": "99", "<int:template_id>": "99",
                     "<int:attachment_id>": "1", "<int:depends_on_id>": "1", "<token>": "x"}.items():
            url = url.replace(k, v)
        for m in r.methods - {"HEAD", "OPTIONS"}:
            todo += c.open(url, method=m, json={}).status_code == 501
    n = sum(len(r.methods - {"HEAD", "OPTIONS"}) for r in app.url_map.iter_rules() if r.rule.startswith("/api"))
    print(f"SMOKE OK — {n} endpoint API, còn {todo} endpoint chưa cài đặt (501)")


if __name__ == "__main__":
    main()
