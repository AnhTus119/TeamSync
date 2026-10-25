"""Kiểm thử M20 — chạy:  python tests/test_m20.py
Seed: workspace 1 "Lớp Lập trình Web 01" (chủ: gv; thành viên sv1–sv4).
Dự án 1: sv1 quản lý, sv2/sv3 thành viên, gv giám sát; sv4 ngoài dự án. Mật khẩu 123456."""
from helpers import Api, make_client

app, c = make_client()
api = Api(c)
ids = {}
api.login("admin")
for u in api("GET", "/api/admin/users"):
    ids[u["email"].split("@")[0]] = u["id"]

# --- đăng ký / đăng nhập / mật khẩu ---
api("POST", "/api/auth/register", {"email": "x@y.vn", "password": "123", "full_name": "A"}, 400, "VALIDATION_ERROR")
u = api("POST", "/api/auth/register", {"email": "New@Y.vn", "password": "123456", "full_name": "Bạn Mới"}, 201)
assert u["email"] == "new@y.vn" and u["role"] == "user" and "password_hash" not in u
api("POST", "/api/auth/register", {"email": "new@y.vn", "password": "123456", "full_name": "B"}, 409, "EMAIL_EXISTS")
api("POST", "/api/auth/login", {"email": "new@y.vn", "password": "sai"}, 401, "INVALID_CREDENTIALS")
c.post("/api/auth/login", json={"email": "new@y.vn", "password": "123456"})
api("PATCH", "/api/auth/me/password", {"old_password": "sai", "new_password": "abcdef"}, 400, "WRONG_PASSWORD")
api("PATCH", "/api/auth/me/password", {"old_password": "123456", "new_password": "abcdef"})
api("POST", "/api/auth/logout")
api("GET", "/api/auth/me", status=401, code="UNAUTHORIZED")
assert c.post("/api/auth/login", json={"email": "new@y.vn", "password": "abcdef"}).status_code == 200

# --- workspace ---
ws = api("POST", "/api/workspaces", {"name": "CLB Tin học"}, 201)
assert ws["my_role"] == "owner"
api("POST", f"/api/workspaces/{ws['id']}/members", {"email": "khong-co@x.vn"}, 404, "USER_NOT_FOUND")
api("POST", f"/api/workspaces/{ws['id']}/members", {"email": "sv4@teamsync.local"}, 201)
api("POST", f"/api/workspaces/{ws['id']}/members", {"email": "sv4@teamsync.local"}, 409, "ALREADY_MEMBER")
assert [m["role"] for m in api("GET", f"/api/workspaces/{ws['id']}/members")] == ["owner", "member"]
api("PATCH", f"/api/workspaces/{ws['id']}", {"name": "CLB Tin học NEU"})
api.login("sv4")
assert any(w["id"] == ws["id"] and w["my_role"] == "member" for w in api("GET", "/api/workspaces"))
api("PATCH", f"/api/workspaces/{ws['id']}", {"name": "x"}, 403, "FORBIDDEN")
api.login("sv1")
api("GET", f"/api/workspaces/{ws['id']}", status=403, code="FORBIDDEN")
api("GET", "/api/workspaces/999", status=404, code="WORKSPACE_NOT_FOUND")
api("DELETE", "/api/workspaces/1", status=403)
api.login("gv")
api("DELETE", "/api/workspaces/1", status=409, code="WORKSPACE_NOT_EMPTY")
api("DELETE", f"/api/workspaces/1/members/{ids['gv']}", status=409, code="CANNOT_REMOVE_OWNER")
api("DELETE", f"/api/workspaces/1/members/{ids['sv2']}", status=409, code="MEMBER_IN_PROJECTS")

# --- thành viên dự án ---
api.login("sv4")
api("GET", "/api/projects/1/members", status=403, code="FORBIDDEN")
api.login("gv")  # giám sát vẫn xem được
assert [m["project_role"] for m in api("GET", "/api/projects/1/members")] == ["manager", "member", "member", "supervisor"]
api("POST", "/api/projects/1/invitations", {"email": "sv4@teamsync.local"}, 403, "FORBIDDEN")

# --- lời mời ---
api.login("sv1")
api("POST", "/api/projects/1/invitations", {"email": "sv2@teamsync.local"}, 409, "ALREADY_MEMBER")
api("POST", "/api/projects/1/invitations", {"email": "a@b.vn", "project_role": "manager"}, 400, "VALIDATION_ERROR")
inv = api("POST", "/api/projects/1/invitations", {"email": "SV4@teamsync.local"}, 201)
assert inv["accept_url"] == f"/invitations/{inv['token']}" and inv["project_role"] == "member"
api("POST", "/api/projects/1/invitations", {"email": "sv4@teamsync.local"}, 409, "INVITATION_EXISTS")
other = api("POST", "/api/projects/1/invitations", {"email": "new@y.vn", "project_role": "supervisor"}, 201)
assert len(api("GET", "/api/projects/1/invitations")) == 2
api("DELETE", f"/api/invitations/{other['id']}")
assert len(api("GET", "/api/projects/1/invitations")) == 1
api.login("sv3")
api("POST", f"/api/invitations/{inv['token']}/accept", status=403, code="INVITATION_EMAIL_MISMATCH")
api.login("sv4")
info = api("GET", f"/api/invitations/{inv['token']}")
assert info["project"]["id"] == 1 and info["project_role"] == "member"
api("POST", "/api/invitations/khong-co/accept", status=404, code="INVITATION_NOT_FOUND")
m = api("POST", f"/api/invitations/{inv['token']}/accept")
assert m["project_role"] == "member" and m["user"]["id"] == ids["sv4"]
api("POST", f"/api/invitations/{inv['token']}/accept", status=409, code="INVITATION_USED")
assert len(api("GET", "/api/projects/1/members")) == 5

# --- đổi vai trò / chuyển quản lý / xóa ---
api.login("sv1")
api("PATCH", f"/api/projects/1/members/{ids['sv2']}", {"project_role": "boss"}, 400, "VALIDATION_ERROR")
api("PATCH", "/api/projects/1/members/9999", {"project_role": "member"}, 404, "MEMBER_NOT_FOUND")
api("PATCH", f"/api/projects/1/members/{ids['sv1']}", {"project_role": "member"}, 409, "LAST_MANAGER")
api("DELETE", f"/api/projects/1/members/{ids['sv1']}", status=409, code="CANNOT_REMOVE_MANAGER")
api("DELETE", f"/api/projects/1/members/{ids['sv2']}", status=409, code="MEMBER_HAS_TASKS")
api("PATCH", f"/api/projects/1/members/{ids['sv2']}", {"project_role": "supervisor"}, 409, "MEMBER_HAS_TASKS")
api("PATCH", f"/api/projects/1/members/{ids['sv4']}", {"project_role": "supervisor"})
api("DELETE", f"/api/projects/1/members/{ids['sv4']}")
api("PATCH", f"/api/projects/1/members/{ids['sv3']}", {"project_role": "manager"})
roles = {m["user"]["id"]: m["project_role"] for m in api("GET", "/api/projects/1/members")}
assert roles[ids["sv3"]] == "manager" and roles[ids["sv1"]] == "member" and list(roles.values()).count("manager") == 1
api("POST", "/api/projects/1/invitations", {"email": "z@y.vn"}, 403, "FORBIDDEN")

# --- quản trị ---
api("GET", "/api/admin/users", status=403, code="FORBIDDEN")
admin = api.login("admin")
assert all(u["role"] == "user" for u in api("GET", "/api/admin/users?role=user"))
assert [u["id"] for u in api("GET", "/api/admin/users?q=sinh viên 2")] == [ids["sv2"]]
api("PATCH", f"/api/admin/users/{admin['id']}", {"is_active": False}, 400, "CANNOT_MODIFY_SELF")
api("PATCH", f"/api/admin/users/{ids['sv4']}", {"role": "root"}, 400, "VALIDATION_ERROR")
api("PATCH", f"/api/admin/users/{ids['sv4']}", {"is_active": "no"}, 400, "VALIDATION_ERROR")
api("PATCH", "/api/admin/users/9999", {"is_active": False}, 404, "USER_NOT_FOUND")
assert api("PATCH", f"/api/admin/users/{ids['sv4']}", {"is_active": False})["is_active"] is False
r = c.post("/api/auth/login", json={"email": "sv4@teamsync.local", "password": "123456"})
assert r.status_code == 403 and r.get_json()["error"]["code"] == "ACCOUNT_LOCKED"
api.login("admin")
api("PATCH", f"/api/admin/users/{ids['sv4']}", {"is_active": True})
p = next(x for x in api("GET", "/api/admin/projects") if x["id"] == 1)
assert p["manager"]["id"] == ids["sv3"] and p["workspace_name"] == "Lớp Lập trình Web 01"

# ẩn bình luận
comment = api("GET", "/api/tasks/2/comments")[0]
hidden = api("PATCH", f"/api/admin/comments/{comment['id']}", {"is_hidden": True})
assert hidden["is_hidden"] and hidden["content"] == "[Nội dung đã bị ẩn]"
api("PATCH", "/api/admin/comments/999", {"is_hidden": True}, 404, "COMMENT_NOT_FOUND")

# mẫu dự án
t = api("POST", "/api/admin/templates", {"name": "Mẫu thử", "milestones": [{"title": "M1", "offset_days": 3}],
                                         "tasks": [{"title": "Việc A", "milestone": "M1", "points": 2}]}, 201)
api("POST", "/api/admin/templates", {"name": "Mẫu thử"}, 409, "TEMPLATE_EXISTS")
api("POST", "/api/admin/templates", {"name": "Sai", "tasks": [{"title": "x", "points": 4}]}, 400, "VALIDATION_ERROR")
assert api("PATCH", f"/api/admin/templates/{t['id']}", {"description": "mô tả"})["description"] == "mô tả"
api("DELETE", f"/api/admin/templates/{t['id']}")
api.login("sv1")
api("POST", "/api/admin/templates", {"name": "x"}, 403, "FORBIDDEN")

# --- trang HTML ---
assert c.get("/admin/users").status_code == 403
for url in ("/account", "/workspaces", "/workspaces/1", "/projects/1/members", "/invitations/abc"):
    assert c.get(url).status_code == 200, url
c.post("/api/auth/logout")
assert c.get("/account").status_code == 302

print("M20 OK — tất cả kiểm thử đạt")
