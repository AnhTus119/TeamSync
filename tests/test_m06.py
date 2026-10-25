"""Kiểm thử M06 — chạy:  python tests/test_m06.py
Dự án 1 (seed): sv1 quản lý, sv2/sv3 thành viên, gv giám sát. Việc 1 done, 2 review, 3 in_progress, 4–7 todo.
Phụ thuộc: 4 → 3 → 1, 5 → 2."""
import io
from datetime import date, timedelta

from helpers import Api, make_client

app, c = make_client()
api = Api(c)
day = lambda n: (date.today() + timedelta(days=n)).isoformat()  # noqa: E731
ids = {}
api.login("admin")
for u in api("GET", "/api/admin/users"):
    ids[u["email"].split("@")[0]] = u["id"]

# --- tạo dự án từ mẫu ---
api.login("sv4")  # thành viên workspace 1
templates = api("GET", "/api/templates")
assert len(templates) == 4
tpl = next(t for t in templates if t["name"] == "Bài tập nhóm")
api("POST", "/api/workspaces/1/projects", {"name": "X", "start_date": day(5), "due_date": day(1)}, 400, "VALIDATION_ERROR")
api("POST", "/api/workspaces/1/projects", {"name": "X", "template_id": 999}, 404, "TEMPLATE_NOT_FOUND")
p = api("POST", "/api/workspaces/1/projects", {"name": "Dự án của sv4", "template_id": tpl["id"], "due_date": day(14)}, 201)
assert p["my_role"] == "manager"
ms = api("GET", f"/api/projects/{p['id']}/milestones")
tasks = api("GET", f"/api/projects/{p['id']}/tasks")
assert len(ms) == 3 and len(tasks) == 6 and all(t["milestone_id"] for t in tasks)
assert sum(t["points"] for t in tasks) == 16
assert any(x["id"] == p["id"] for x in api("GET", "/api/projects"))
api.login("sv1")
api("POST", "/api/workspaces/999/projects", {"name": "X"}, 404, "WORKSPACE_NOT_FOUND")
api("GET", f"/api/projects/{p['id']}", status=403)  # sv1 không ở trong dự án của sv4
api.login("gv")  # chủ workspace xem được mọi dự án trong workspace
api("GET", f"/api/projects/{p['id']}")
api("PATCH", f"/api/projects/{p['id']}", {"name": "x"}, 403)
api.login("sv4")
assert api("PATCH", f"/api/projects/{p['id']}", {"name": "Đổi tên"})["name"] == "Đổi tên"
api("DELETE", f"/api/projects/{p['id']}")
api("GET", f"/api/projects/{p['id']}", status=404, code="PROJECT_NOT_FOUND")

# --- nhiệm vụ: tạo, lọc, sửa ---
api.login("sv2")
api("POST", "/api/projects/1/tasks", {"title": "x"}, 403, "FORBIDDEN")
api.login("sv1")
api("POST", "/api/projects/1/tasks", {"title": "x", "points": 4}, 400, "VALIDATION_ERROR")
api("POST", "/api/projects/1/tasks", {"title": "x", "assignee_id": ids["gv"]}, 400, "INVALID_ASSIGNEE")
api("POST", "/api/projects/1/tasks", {"title": "x", "assignee_id": ids["sv4"]}, 400, "INVALID_ASSIGNEE")
api("POST", "/api/projects/1/tasks", {"title": "x", "due_date": "20/10/2026"}, 400, "VALIDATION_ERROR")
t = api("POST", "/api/projects/1/tasks", {"title": "Việc mới", "assignee_id": ids["sv2"], "points": 2,
                                          "due_date": day(4), "milestone_id": 2}, 201)
assert t["status"] == "todo" and t["assignee"]["id"] == ids["sv2"]
assert {x["id"] for x in api("GET", f"/api/projects/1/tasks?assignee_id={ids['sv2']}")} >= {2, 5, t["id"]}
assert [x["id"] for x in api("GET", "/api/projects/1/tasks?due=overdue")] == [5]
assert all(x["status"] == "review" for x in api("GET", "/api/projects/1/tasks?status=review"))
api("PATCH", f"/api/tasks/{t['id']}", {"points": 5, "due_date": day(6)})
fields = [h["field"] for h in api("GET", f"/api/tasks/{t['id']}/history")]
assert fields == ["created", "points", "due_date"]
api("PATCH", f"/api/tasks/{t['id']}", {"milestone_id": 999}, 400, "INVALID_MILESTONE")

# --- luồng trạng thái + minh chứng + duyệt ---
api.login("sv3")
api("PATCH", f"/api/tasks/{t['id']}/status", {"status": "in_progress"}, 403, "FORBIDDEN")  # không phải người được giao
api.login("gv")
api("PATCH", f"/api/tasks/{t['id']}/status", {"status": "in_progress"}, 403)  # giám sát không làm việc
api.login("sv2")
api("PATCH", f"/api/tasks/{t['id']}/status", {"status": "done"}, 409, "INVALID_TRANSITION")
api("PATCH", f"/api/tasks/{t['id']}/status", {"status": "review"}, 409, "INVALID_TRANSITION")
api("PATCH", f"/api/tasks/{t['id']}/status", {"status": "in_progress"})
api("PATCH", f"/api/tasks/{t['id']}/status", {"status": "review"}, 409, "EVIDENCE_REQUIRED")
api("POST", f"/api/tasks/{t['id']}/attachments", {"url": "ftp://x"}, 400, "VALIDATION_ERROR")
r = c.post(f"/api/tasks/{t['id']}/attachments", data={"file": (io.BytesIO(b"virus"), "a.exe")},
           content_type="multipart/form-data")
assert r.status_code == 400 and r.get_json()["error"]["code"] == "FILE_TYPE_NOT_ALLOWED"
r = c.post(f"/api/tasks/{t['id']}/attachments", data={"file": (io.BytesIO(b"%PDF-1.4 test"), "bao cao.pdf")},
           content_type="multipart/form-data")
assert r.status_code == 201, r.get_json()
att = r.get_json()["data"]
assert c.get(att["url"]).data == b"%PDF-1.4 test"
api("PATCH", f"/api/tasks/{t['id']}/status", {"status": "review"})
api("POST", f"/api/tasks/{t['id']}/review", {"action": "approve"}, 403)  # chỉ quản lý duyệt
api.login("sv1")
api("POST", f"/api/tasks/{t['id']}/review", {"action": "return"}, 400, "VALIDATION_ERROR")  # thiếu lý do
assert api("POST", f"/api/tasks/{t['id']}/review", {"action": "return", "note": "Thiếu phần kết luận"})["status"] == "in_progress"
api.login("sv2")
api("PATCH", f"/api/tasks/{t['id']}/status", {"status": "review"})
api.login("sv1")
done = api("POST", f"/api/tasks/{t['id']}/review", {"action": "approve"})
assert done["status"] == "done" and done["completed_at"]
api("POST", f"/api/tasks/{t['id']}/review", {"action": "approve"}, 409, "INVALID_TRANSITION")
api("POST", f"/api/tasks/{t['id']}/attachments", {"url": "https://x.vn"}, 409, "TASK_DONE")

# --- phụ thuộc ---
api("POST", "/api/tasks/1/dependencies", {"depends_on_id": 1}, 400, "INVALID_DEPENDENCY")
api("POST", "/api/tasks/1/dependencies", {"depends_on_id": 4}, 409, "DEPENDENCY_CYCLE")  # 4 → 3 → 1
api("POST", "/api/tasks/4/dependencies", {"depends_on_id": 3}, 409, "DEPENDENCY_EXISTS")
detail = api("GET", "/api/tasks/4")
assert detail["blocked"] and detail["depends_on"][0]["id"] == 3
api.login("sv3")
api("PATCH", "/api/tasks/4/status", {"status": "in_progress"}, 409, "BLOCKED_BY_DEPENDENCY")
api.login("sv1")
api("POST", "/api/tasks/7/dependencies", {"depends_on_id": 6}, 201)
api("DELETE", "/api/tasks/7/dependencies/6")
api("DELETE", "/api/tasks/7/dependencies/6", status=404, code="DEPENDENCY_NOT_FOUND")

# --- bình luận ---
api.login("gv")
api("POST", "/api/tasks/2/comments", {"content": "Nhớ kiểm tra cả quyền giám sát"}, 201)
assert len(api("GET", "/api/tasks/2/comments")) == 2
api.login("sv4")
api("GET", "/api/tasks/2/comments", status=403)
api("GET", "/api/tasks/999", status=404, code="TASK_NOT_FOUND")

# --- cột mốc: gửi nghiệm thu, nghiệm thu ---
api.login("sv1")
api("POST", "/api/milestones/2/submit", status=409, code="MILESTONE_NOT_READY")
m = api("POST", "/api/projects/1/milestones", {"title": "Cột mốc thử", "due_date": day(3)}, 201)
api("POST", f"/api/milestones/{m['id']}/review", {"action": "accept"}, 403)  # có giám sát nên quản lý không tự nghiệm thu
api("POST", f"/api/milestones/{m['id']}/submit")
api.login("sv2")
api("POST", f"/api/milestones/{m['id']}/review", {"action": "accept"}, 403)
api.login("gv")
api("POST", f"/api/milestones/{m['id']}/review", {"action": "request_changes"}, 400, "VALIDATION_ERROR")
assert api("POST", f"/api/milestones/{m['id']}/review", {"action": "request_changes", "note": "Bổ sung tài liệu"})["status"] == "changes_requested"
api.login("sv1")
api("POST", f"/api/milestones/{m['id']}/submit")
api.login("gv")
acc = api("POST", f"/api/milestones/{m['id']}/review", {"action": "accept", "note": "Đạt"})
assert acc["status"] == "accepted" and acc["reviewed_by"] == ids["gv"]
api.login("sv1")
api("PATCH", f"/api/milestones/{m['id']}", {"title": "x"}, 409, "MILESTONE_ACCEPTED")
ms = {x["id"]: x for x in api("GET", "/api/projects/1/milestones")}
assert ms[1]["status"] == "accepted" and ms[2]["task_count"] == 5
api("DELETE", "/api/milestones/3")
assert api("GET", "/api/tasks/6")["milestone_id"] is None

# --- xóa việc ---
api("DELETE", f"/api/tasks/{t['id']}")
api("GET", f"/api/tasks/{t['id']}", status=404)

# --- trang HTML ---
for url in ("/projects", "/projects/1", "/projects/1/milestones", "/tasks/1"):
    assert c.get(url).status_code == 200, url

print("M06 OK — tất cả kiểm thử đạt")
