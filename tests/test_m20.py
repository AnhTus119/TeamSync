"""Kiểm thử M20 — chạy:  python tests/test_m20.py
Dữ liệu seed: dự án 1 có sv1 (trưởng nhóm), sv2, sv3; sv4 ngoài nhóm; mật khẩu 123456."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app  # noqa: E402

app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
assert app.test_cli_runner().invoke(args=["seed"]).exit_code == 0
c = app.test_client()


def login(who, pw="123456"):
    r = c.post("/api/auth/login", json={"email": f"{who}@teamsync.local", "password": pw})
    assert r.status_code == 200, r.get_json()
    return r.get_json()["data"]


def call(method, url, json=None, status=200, code=None):
    r = c.open(url, method=method, json=json)
    body = r.get_json()
    assert r.status_code == status, f"{method} {url} → {r.status_code} {body}, mong đợi {status}"
    if code:
        assert body["error"]["code"] == code, body
    return body and body.get("data")


def uid(who):
    login("admin")
    return next(u["id"] for u in call("GET", f"/api/admin/users?q={who}@") if u["email"].startswith(who + "@"))


# --- đăng ký / đổi mật khẩu ---
call("POST", "/api/auth/register", {"email": "new@x.vn", "password": "123", "full_name": "A"}, 400, "VALIDATION_ERROR")
u = call("POST", "/api/auth/register", {"email": "New@X.vn", "password": "123456", "full_name": "Bạn Mới"}, 201)
assert u["email"] == "new@x.vn" and u["role"] == "student" and "password_hash" not in u
call("POST", "/api/auth/register", {"email": "new@x.vn", "password": "123456", "full_name": "B"}, 409, "EMAIL_EXISTS")
c.post("/api/auth/login", json={"email": "new@x.vn", "password": "123456"})
call("PATCH", "/api/auth/me/password", {"old_password": "sai", "new_password": "abcdef"}, 400, "WRONG_PASSWORD")
call("PATCH", "/api/auth/me/password", {"old_password": "123456", "new_password": "abc"}, 400, "VALIDATION_ERROR")
call("PATCH", "/api/auth/me/password", {"old_password": "123456", "new_password": "abcdef"})
call("POST", "/api/auth/logout")
call("PATCH", "/api/auth/me/password", {"old_password": "x", "new_password": "y"}, 401, "UNAUTHORIZED")
assert c.post("/api/auth/login", json={"email": "new@x.vn", "password": "abcdef"}).status_code == 200

SV2, SV3, SV4 = uid("sv2"), uid("sv3"), uid("sv4")

# --- danh sách thành viên ---
login("sv4")
call("GET", "/api/projects/1/members", status=403, code="FORBIDDEN")
call("GET", "/api/projects/999/members", status=404, code="PROJECT_NOT_FOUND")
login("gv")
members = call("GET", "/api/projects/1/members")
assert [m["project_role"] for m in members] == ["leader", "member", "member"]

# --- lời mời ---
login("sv2")
call("POST", "/api/projects/1/invitations", {"email": "sv4@teamsync.local"}, 403, "FORBIDDEN")
login("sv1")
call("POST", "/api/projects/1/invitations", {"email": "sv2@teamsync.local"}, 409, "ALREADY_MEMBER")
inv = call("POST", "/api/projects/1/invitations", {"email": "SV4@teamsync.local"}, 201)
assert inv["accept_url"] == f"/invitations/{inv['token']}" and inv["status"] == "pending"
call("POST", "/api/projects/1/invitations", {"email": "sv4@teamsync.local"}, 409, "INVITATION_EXISTS")
login("sv3")
call("POST", f"/api/invitations/{inv['token']}/accept", status=403, code="INVITATION_EMAIL_MISMATCH")
login("sv4")
call("POST", "/api/invitations/khong-co/accept", status=404, code="INVITATION_NOT_FOUND")
m = call("POST", f"/api/invitations/{inv['token']}/accept")
assert m["project_role"] == "member" and m["user"]["id"] == SV4
call("POST", f"/api/invitations/{inv['token']}/accept", status=409, code="INVITATION_USED")
assert len(call("GET", "/api/projects/1/members")) == 4

# --- đổi vai trò / chuyển trưởng nhóm / xóa ---
login("sv1")
SV1 = call("GET", "/api/auth/me")["id"]
call("PATCH", f"/api/projects/1/members/{SV2}", {"project_role": "boss"}, 400, "VALIDATION_ERROR")
call("PATCH", "/api/projects/1/members/9999", {"project_role": "leader"}, 404, "MEMBER_NOT_FOUND")
call("PATCH", f"/api/projects/1/members/{SV1}", {"project_role": "member"}, 409, "LAST_LEADER")
call("DELETE", f"/api/projects/1/members/{SV1}", status=409, code="CANNOT_REMOVE_LEADER")
call("DELETE", f"/api/projects/1/members/{SV2}", status=409, code="MEMBER_HAS_TASKS")  # sv2 còn task 'review'
call("DELETE", f"/api/projects/1/members/{SV4}")
call("PATCH", f"/api/projects/1/members/{SV3}", {"project_role": "leader"})
roles = {m["user"]["id"]: m["project_role"] for m in call("GET", "/api/projects/1/members")}
assert roles[SV3] == "leader" and roles[SV1] == "member" and list(roles.values()).count("leader") == 1
call("POST", "/api/projects/1/invitations", {"email": "x@y.vn"}, 403, "FORBIDDEN")  # sv1 không còn là trưởng nhóm

# --- quản trị ---
call("GET", "/api/admin/users", status=403, code="FORBIDDEN")
admin = login("admin")
assert len(call("GET", "/api/admin/users?role=student")) == 5
assert [u["id"] for u in call("GET", "/api/admin/users?q=sinh viên 2")] == [SV2]
call("PATCH", f"/api/admin/users/{admin['id']}", {"is_active": False}, 400, "CANNOT_MODIFY_SELF")
call("PATCH", f"/api/admin/users/{SV4}", {"role": "root"}, 400, "VALIDATION_ERROR")
call("PATCH", f"/api/admin/users/{SV4}", {"is_active": "no"}, 400, "VALIDATION_ERROR")
call("PATCH", "/api/admin/users/9999", {"is_active": False}, 404, "USER_NOT_FOUND")
assert call("PATCH", f"/api/admin/users/{SV4}", {"is_active": False})["is_active"] is False
assert len(call("GET", "/api/admin/users?is_active=false")) == 1
r = c.post("/api/auth/login", json={"email": "sv4@teamsync.local", "password": "123456"})
assert r.status_code == 403 and r.get_json()["error"]["code"] == "ACCOUNT_LOCKED"
login("admin")
assert call("PATCH", f"/api/admin/users/{SV4}", {"is_active": True, "role": "lecturer"})["role"] == "lecturer"
p = call("GET", "/api/admin/projects")[0]
assert p["member_count"] == 3 and p["task_count"] == 4 and p["leader"]["id"] == SV3 and p["course_code"] == "LTWEB_01"

# --- trang HTML ---
for url in ("/register", "/account", "/projects/1/members", "/invitations/abc", "/admin/users", "/admin/projects"):
    assert c.get(url).status_code == 200, url
login("sv1")
assert c.get("/admin/users").status_code == 403
c.post("/api/auth/logout")
assert c.get("/account").status_code == 302

print("M20 OK — tất cả kiểm thử đạt")
