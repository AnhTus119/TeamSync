"""Sinh Postman collection chạy theo luồng nghiệp vụ đầy đủ (có kiểm tra tự động):

    python scripts/build_postman_flow.py   → tests/postman/TeamSync.postman_collection.json

Mỗi lần chạy collection tạo workspace và dự án MỚI nên chạy lại bao nhiêu lần cũng được, không cần seed lại.
"""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "tests" / "postman"


def req(name, method, path, body=None, status=200, tests=None, setvars=None):
    lines = [f'pm.test("HTTP {status}", () => pm.response.to.have.status({status}));']
    for code in [t for t in (tests or []) if t.startswith("code:")]:
        lines.append(f'pm.test("error.code = {code[5:]}", () => pm.expect(pm.response.json().error.code).to.eql("{code[5:]}"));')
    lines += [t for t in (tests or []) if not t.startswith("code:")]
    for var, expr in (setvars or {}).items():
        lines.append(f'pm.collectionVariables.set("{var}", {expr});')
    raw = "{{base_url}}" + path
    clean = path.split("?")[0]
    r = {"method": method, "header": [], "url": {"raw": raw, "host": ["{{base_url}}"], "path": [p for p in clean.split("/") if p]}}
    if "?" in path:
        r["url"]["query"] = [{"key": k, "value": v} for k, v in (x.split("=") for x in path.split("?")[1].split("&"))]
    if body is not None:
        r["header"] = [{"key": "Content-Type", "value": "application/json"}]
        r["body"] = {"mode": "raw", "raw": json.dumps(body, ensure_ascii=False, indent=2).replace('"#', "").replace('#"', "")}
    return {"name": name, "event": [{"listen": "test", "script": {"type": "text/javascript", "exec": lines}}], "request": r}


def login(who):
    return req(f"Đăng nhập {who}", "POST", "/api/auth/login", {"email": f"{who}@teamsync.local", "password": "123456"},
               setvars={f"{who}_id": "pm.response.json().data.id"})


D = "pm.response.json().data"
expect = lambda cond, title: f'pm.test("{title}", () => pm.expect({cond}).to.be.true);'  # noqa: E731

flow = [
    {"name": "0. Chuẩn bị", "item": [
        login("gv"), login("sv2"),
        req("Đăng nhập sai mật khẩu", "POST", "/api/auth/login", {"email": "sv1@teamsync.local", "password": "sai"}, 401,
            ["code:INVALID_CREDENTIALS"]),
        login("sv1"),
        req("Xem tôi là ai", "GET", "/api/auth/me", tests=[expect(f'{D}.email === "sv1@teamsync.local"', "đúng sv1")]),
    ]},
    {"name": "1. M20 — Workspace, lời mời, vai trò", "item": [
        req("Tạo workspace", "POST", "/api/workspaces", {"name": "Postman workspace {{$timestamp}}"}, 201,
            [expect(f'{D}.my_role === "owner"', "là chủ")], {"ws_id": f"{D}.id"}),
        req("Thêm sv2 vào workspace", "POST", "/api/workspaces/{{ws_id}}/members", {"email": "sv2@teamsync.local"}, 201),
        req("Thêm email chưa có tài khoản", "POST", "/api/workspaces/{{ws_id}}/members", {"email": "khong-co@x.vn"}, 404,
            ["code:USER_NOT_FOUND"]),
        req("Danh sách mẫu dự án", "GET", "/api/templates", tests=[expect(f"{D}.length >= 4", "có ≥ 4 mẫu")],
            setvars={"tpl_id": f'{D}.find(t => t.name === "Phát triển phần mềm").id'}),
        req("Tạo dự án từ mẫu", "POST", "/api/workspaces/{{ws_id}}/projects",
            {"name": "Dự án Postman {{$timestamp}}", "description": "Tạo bởi Postman", "template_id": "#{{tpl_id}}#"}, 201,
            [expect(f'{D}.my_role === "manager"', "người tạo là quản lý")], {"pid": f"{D}.id"}),
        req("Mời sv2 làm thành viên", "POST", "/api/projects/{{pid}}/invitations", {"email": "sv2@teamsync.local"}, 201,
            setvars={"token_member": f"{D}.token"}),
        req("Mời gv làm giám sát", "POST", "/api/projects/{{pid}}/invitations",
            {"email": "gv@teamsync.local", "project_role": "supervisor"}, 201, setvars={"token_sup": f"{D}.token"}),
        req("Mời với vai trò không hợp lệ", "POST", "/api/projects/{{pid}}/invitations",
            {"email": "a@b.vn", "project_role": "manager"}, 400, ["code:VALIDATION_ERROR"]),
        login("sv2"),
        req("sv2 xem lời mời", "GET", "/api/invitations/{{token_member}}",
            tests=[expect(f'{D}.project_role === "member"', "vai trò member")]),
        req("sv2 nhận lời mời", "POST", "/api/invitations/{{token_member}}/accept"),
        req("Nhận lại lời mời đã dùng", "POST", "/api/invitations/{{token_member}}/accept", status=409, tests=["code:INVITATION_USED"]),
        login("gv"),
        req("gv nhận lời mời giám sát", "POST", "/api/invitations/{{token_sup}}/accept",
            tests=[expect(f'{D}.project_role === "supervisor"', "là giám sát")]),
        login("sv1"),
        req("Danh sách thành viên", "GET", "/api/projects/{{pid}}/members",
            tests=[expect(f'{D}.map(m => m.project_role).join() === "manager,member,supervisor"', "đủ 3 vai trò, đúng thứ tự")]),
        req("Hạ quyền quản lý duy nhất", "PATCH", "/api/projects/{{pid}}/members/{{sv1_id}}", {"project_role": "member"}, 409,
            ["code:LAST_MANAGER"]),
    ]},
    {"name": "2. M06 — Nhiệm vụ, minh chứng, duyệt, cột mốc", "item": [
        req("Danh sách việc tạo từ mẫu", "GET", "/api/projects/{{pid}}/tasks", tests=[expect(f"{D}.length === 6", "6 việc từ mẫu")]),
        req("Giao việc cho giám sát (không hợp lệ)", "POST", "/api/projects/{{pid}}/tasks",
            {"title": "x", "assignee_id": "#{{gv_id}}#"}, 400, ["code:INVALID_ASSIGNEE"]),
        req("Tạo việc cho sv2", "POST", "/api/projects/{{pid}}/tasks",
            {"title": "Viết API đăng nhập", "assignee_id": "#{{sv2_id}}#", "points": 3, "priority": "high"}, 201,
            setvars={"task_a": f"{D}.id"}),
        req("Tạo việc phụ thuộc", "POST", "/api/projects/{{pid}}/tasks",
            {"title": "Kiểm thử API đăng nhập", "assignee_id": "#{{sv2_id}}#", "points": 2}, 201, setvars={"task_b": f"{D}.id"}),
        req("B phụ thuộc A", "POST", "/api/tasks/{{task_b}}/dependencies", {"depends_on_id": "#{{task_a}}#"}, 201),
        req("A phụ thuộc B → vòng lặp", "POST", "/api/tasks/{{task_a}}/dependencies", {"depends_on_id": "#{{task_b}}#"}, 409,
            ["code:DEPENDENCY_CYCLE"]),
        login("sv2"),
        req("sv2 tạo việc (không phải quản lý)", "POST", "/api/projects/{{pid}}/tasks", {"title": "x"}, 403, ["code:FORBIDDEN"]),
        req("Bắt đầu B khi A chưa xong", "PATCH", "/api/tasks/{{task_b}}/status", {"status": "in_progress"}, 409,
            ["code:BLOCKED_BY_DEPENDENCY"]),
        req("Bắt đầu A", "PATCH", "/api/tasks/{{task_a}}/status", {"status": "in_progress"}),
        req("Gửi duyệt khi chưa có minh chứng", "PATCH", "/api/tasks/{{task_a}}/status", {"status": "review"}, 409,
            ["code:EVIDENCE_REQUIRED"]),
        req("Nộp minh chứng (link)", "POST", "/api/tasks/{{task_a}}/attachments", {"url": "https://github.com/AnhTus119/TeamSync/pull/1"}, 201),
        req("Gửi duyệt", "PATCH", "/api/tasks/{{task_a}}/status", {"status": "review"}),
        req("Bình luận", "POST", "/api/tasks/{{task_a}}/comments", {"content": "Em đã nộp, nhờ anh duyệt"}, 201,
            setvars={"comment_id": f"{D}.id"}),
        login("sv1"),
        req("Trả lại không ghi lý do", "POST", "/api/tasks/{{task_a}}/review", {"action": "return"}, 400, ["code:VALIDATION_ERROR"]),
        req("Trả lại có lý do", "POST", "/api/tasks/{{task_a}}/review", {"action": "return", "note": "Thiếu kiểm tra tài khoản bị khóa"},
            tests=[expect(f'{D}.status === "in_progress"', "về Đang làm")]),
        login("sv2"),
        req("Gửi duyệt lại", "PATCH", "/api/tasks/{{task_a}}/status", {"status": "review"}),
        login("sv1"),
        req("Duyệt hoàn thành", "POST", "/api/tasks/{{task_a}}/review", {"action": "approve"},
            tests=[expect(f'{D}.status === "done" && !!{D}.completed_at', "done, có completed_at")]),
        req("Lịch sử việc A", "GET", "/api/tasks/{{task_a}}/history",
            tests=[expect(f'{D}.filter(h => h.field === "review").length === 2', "ghi 2 lần duyệt/trả lại")]),
        req("Chi tiết B — hết bị chặn", "GET", "/api/tasks/{{task_b}}", tests=[expect(f"{D}.blocked === false", "không còn bị chặn")]),
        req("Lọc việc quá hạn", "GET", "/api/projects/{{pid}}/tasks?due=overdue"),
        req("Tạo cột mốc", "POST", "/api/projects/{{pid}}/milestones", {"title": "Bản demo nội bộ", "description": "Chạy được luồng chính"},
            201, setvars={"ms_id": f"{D}.id"}),
        req("Gửi nghiệm thu", "POST", "/api/milestones/{{ms_id}}/submit",
            tests=[expect(f'{D}.status === "pending_review"', "chờ nghiệm thu")]),
        req("Quản lý tự nghiệm thu khi đã có giám sát", "POST", "/api/milestones/{{ms_id}}/review", {"action": "accept"}, 403),
        login("gv"),
        req("Giám sát yêu cầu sửa", "POST", "/api/milestones/{{ms_id}}/review",
            {"action": "request_changes", "note": "Bổ sung tài liệu hướng dẫn"},
            tests=[expect(f'{D}.status === "changes_requested"', "yêu cầu sửa")]),
        req("Giám sát không được đổi trạng thái việc", "PATCH", "/api/tasks/{{task_b}}/status", {"status": "in_progress"}, 403),
        login("sv1"),
        req("Gửi nghiệm thu lại", "POST", "/api/milestones/{{ms_id}}/submit"),
        login("gv"),
        req("Giám sát nghiệm thu", "POST", "/api/milestones/{{ms_id}}/review", {"action": "accept", "note": "Đạt"},
            tests=[expect(f'{D}.status === "accepted"', "đã nghiệm thu")]),
    ]},
    {"name": "3. M17 — Dashboard, cảnh báo, đóng góp", "item": [
        login("sv2"),
        req("Thống kê dự án", "GET", "/api/projects/{{pid}}/stats",
            tests=[expect(f"{D}.by_status.done === 1 && {D}.points_done === 3", "1 việc xong, 3 điểm")]),
        req("Việc có nguy cơ", "GET", "/api/projects/{{pid}}/risks"),
        req("Đèn sức khỏe", "GET", "/api/projects/{{pid}}/health",
            tests=[expect(f'["green","yellow","red"].includes({D}.level)', "có level hợp lệ")]),
        req("Sổ đóng góp (thành viên)", "GET", "/api/projects/{{pid}}/contributions",
            tests=[expect(f'{D}.every(r => !("peer_score" in r))', "thành viên không thấy điểm đánh giá chéo"),
                   expect(f'{D}.find(r => r.user.email === "sv2@teamsync.local").returned === 1', "sv2 bị trả lại 1 lần")]),
        req("Tự đánh giá mình", "POST", "/api/projects/{{pid}}/peer-reviews", {"reviewee_id": "#{{sv2_id}}#", "score": 5}, 400),
        req("sv2 đánh giá sv1", "POST", "/api/projects/{{pid}}/peer-reviews",
            {"reviewee_id": "#{{sv1_id}}#", "score": 5, "comment": "Phân công rõ ràng"}, 201),
        req("Đánh giá trùng", "POST", "/api/projects/{{pid}}/peer-reviews", {"reviewee_id": "#{{sv1_id}}#", "score": 4}, 409,
            ["code:ALREADY_REVIEWED"]),
        req("Thành viên chạy đánh giá luật", "GET", "/api/projects/{{pid}}/risk-evaluation", status=403),
        login("gv"),
        req("Giám sát xem tổng hợp đánh giá chéo", "GET", "/api/projects/{{pid}}/peer-reviews",
            tests=[expect(f'{D}.find(r => r.user.email === "sv1@teamsync.local").average === 5', "sv1 trung bình 5")]),
        req("Đánh giá luật cảnh báo", "GET", "/api/projects/{{pid}}/risk-evaluation"),
        req("Hoạt động gần đây", "GET", "/api/projects/{{pid}}/activity?limit=10", tests=[expect(f"{D}.length === 10", "10 dòng")]),
        login("sv1"),
        req("Xuất CSV", "GET", "/api/projects/{{pid}}/report",
            tests=['pm.test("là CSV", () => pm.expect(pm.response.headers.get("Content-Type")).to.include("text/csv"));']),
        req("Tổng quan workspace (chủ)", "GET", "/api/workspaces/{{ws_id}}/overview", tests=[expect(f"{D}.length === 1", "1 dự án")]),
    ]},
    {"name": "4. Quản trị", "item": [
        req("Người dùng gọi API admin", "GET", "/api/admin/users", status=403, tests=["code:FORBIDDEN"]),
        req("Đăng nhập admin", "POST", "/api/auth/login", {"email": "admin@teamsync.local", "password": "123456"},
            setvars={"admin_id": f"{D}.id"}),
        req("Lọc người dùng", "GET", "/api/admin/users?role=user"),
        req("Admin tự khóa mình", "PATCH", "/api/admin/users/{{admin_id}}", {"is_active": False}, 400, ["code:CANNOT_MODIFY_SELF"]),
        req("Giám sát mọi dự án", "GET", "/api/admin/projects"),
        req("Ẩn bình luận vi phạm", "PATCH", "/api/admin/comments/{{comment_id}}", {"is_hidden": True},
            tests=[expect(f'{D}.content === "[Nội dung đã bị ẩn]"', "nội dung bị ẩn")]),
        req("Thêm mẫu dự án", "POST", "/api/admin/templates",
            {"name": "Mẫu Postman {{$timestamp}}", "milestones": [{"title": "Giai đoạn 1", "offset_days": 7}],
             "tasks": [{"title": "Việc đầu tiên", "milestone": "Giai đoạn 1", "points": 2}]}, 201, setvars={"new_tpl": f"{D}.id"}),
        req("Xóa mẫu vừa thêm", "DELETE", "/api/admin/templates/{{new_tpl}}"),
        req("Đăng xuất", "POST", "/api/auth/logout"),
        req("Sau khi đăng xuất → 401", "GET", "/api/auth/me", status=401, tests=["code:UNAUTHORIZED"]),
    ]},
]

collection = {
    "info": {"name": "TeamSync — luồng nghiệp vụ đầy đủ",
             "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
             "description": "Chạy theo thứ tự bằng Run collection sau khi `flask --app run seed`. Postman tự giữ cookie đăng nhập. "
                            "Mỗi lần chạy tạo workspace và dự án mới nên chạy lại nhiều lần được."},
    "item": flow,
    "variable": [{"key": "base_url", "value": "http://127.0.0.1:5000"}],
}
OUT.mkdir(parents=True, exist_ok=True)
(OUT / "TeamSync.postman_collection.json").write_text(json.dumps(collection, ensure_ascii=False, indent=2), "utf-8")
print(f"Đã sinh {sum(len(f['item']) for f in flow)} request")
