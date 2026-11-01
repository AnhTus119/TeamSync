"""Sinh Postman collection LUỒNG NGHIỆP VỤ đầy đủ có kiểm tra tự động (M17 — Thành viên 3).

    python tests/postman/build_collection.py
Ghi tests/postman/TeamSync.postman_collection.json. Import cùng TeamSync.postman_environment.json (do gen_postman.py sinh).

Cách chạy:
    flask --app run seed && flask --app run run          # database sạch có dữ liệu mẫu
    newman run tests/postman/TeamSync.postman_collection.json -e tests/postman/TeamSync.postman_environment.json
Postman tự giữ cookie phiên; mỗi request "Đăng nhập" đổi vai trò. Luồng 02 tạo dự án riêng rồi xóa ở cuối nên chạy lại được nhiều lần.
Luồng 02 cần M06 đã cài đặt đầy đủ (tạo dự án, cột mốc, việc, duyệt). Folder 00 và 01 chạy được ngay cả khi M06 còn khung.
"""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent / "TeamSync.postman_collection.json"
USERS = ("admin", "gv", "sv1", "sv2", "sv3", "sv4")


def req(name, method, path, body=None, tests="", pre=""):
    item = {"name": name, "request": {"method": method, "header": [], "url": {
        "raw": "{{base_url}}" + path, "host": ["{{base_url}}"], "path": [p for p in path.split("?")[0].split("/") if p]}}}
    if "?" in path:
        item["request"]["url"]["query"] = [dict(zip(("key", "value"), kv.split("=", 1))) for kv in path.split("?")[1].split("&")]
    if body is not None:
        item["request"]["header"] = [{"key": "Content-Type", "value": "application/json"}]
        item["request"]["body"] = {"mode": "raw", "raw": json.dumps(body, ensure_ascii=False, indent=2)}
    events = []
    if pre:
        events.append({"listen": "prerequest", "script": {"type": "text/javascript", "exec": pre.strip().splitlines()}})
    if tests:
        events.append({"listen": "test", "script": {"type": "text/javascript", "exec": tests.strip().splitlines()}})
    if events:
        item["event"] = events
    return item


def login(who, save=True):
    t = f'pm.test("Đăng nhập {who} → 200", () => pm.response.to.have.status(200));\n'
    if save:
        t += f'pm.collectionVariables.set("uid_{who}", pm.response.json().data.id);'
    return req(f"Đăng nhập: {who}", "POST", "/api/auth/login", {"email": f"{who}@teamsync.local", "password": "123456"}, t)


def status(code, extra=""):
    return f'pm.test("HTTP {code}", () => pm.response.to.have.status({code}));\n{extra}'


def err(code, http):
    return (f'pm.test("HTTP {http} + mã lỗi {code}", () => {{ pm.response.to.have.status({http}); '
            f'pm.expect(pm.response.json().error.code).to.eql("{code}"); }});')


def j(js):
    return "const j = pm.response.json().data;\n" + js


# ------------------------------------------------------------------ 00 — đăng nhập
f00 = {"name": "00 — Đăng nhập theo vai trò (lưu id tài khoản)", "item": [login(u) for u in USERS]}

# ------------------------------------------------------------------ 01 — M17 trên dự án demo (phân quyền theo vai trò)
READS = ("stats", "risks", "health", "contributions", "activity", "peer-reviews")
f01 = {"name": "01 — M17 trên dự án demo: quyền theo vai trò", "item": [
    req("Chưa đăng nhập → 401", "POST", "/api/auth/logout", {}, status(200)),
    req("[ẩn danh] GET stats → 401", "GET", "/api/projects/{{project_id}}/stats", tests=err("UNAUTHORIZED", 401)),
    req("[ẩn danh] POST peer-reviews → 401", "POST", "/api/projects/{{project_id}}/peer-reviews", {"reviewee_id": 1, "score": 3},
        err("UNAUTHORIZED", 401)),
    login("sv4", False),
    *[req(f"[sv4 ngoài dự án] GET {u} → 403", "GET", f"/api/projects/{{{{project_id}}}}/{u}", tests=err("FORBIDDEN", 403)) for u in READS],
    req("[sv4] GET risk-evaluation → 403", "GET", "/api/projects/{{project_id}}/risk-evaluation", tests=err("FORBIDDEN", 403)),
    req("[sv4] GET workspace overview → 403 (không phải chủ)", "GET", "/api/workspaces/{{workspace_id}}/overview", tests=err("FORBIDDEN", 403)),
    req("Dự án không tồn tại → 404", "GET", "/api/projects/99999/stats", tests=err("PROJECT_NOT_FOUND", 404)),
    login("sv2", False),
    req("[sv2 thành viên] GET stats", "GET", "/api/projects/{{project_id}}/stats", tests=status(200, j("""
pm.test("Có đủ trường thống kê", () => ["total","by_status","percent_done","points_total","points_done","percent_points","overdue","on_time_rate","by_milestone"].forEach(k => pm.expect(j).to.have.property(k)));
pm.test("Tổng các trạng thái = tổng việc", () => pm.expect(Object.values(j.by_status).reduce((a,b)=>a+b,0)).to.eql(j.total));
pm.test("% hoàn thành trong 0–100", () => pm.expect(j.percent_done).to.be.within(0, 100));
pm.test("Vai trò của tôi là member", () => pm.expect(j.my_role).to.eql("member"));"""))),
    req("[sv2] GET risks — mỗi cảnh báo có lý do", "GET", "/api/projects/{{project_id}}/risks", tests=status(200, j("""
pm.test("Là mảng, mỗi việc có reasons{code,label,detail}", () => { pm.expect(j).to.be.an("array");
  j.forEach(r => { pm.expect(r.reasons).to.be.an("array").that.is.not.empty; r.reasons.forEach(x => ["code","label","detail"].forEach(k => pm.expect(x).to.have.property(k))); }); });
pm.test("Mã cảnh báo hợp lệ", () => j.forEach(r => r.reasons.forEach(x => pm.expect(["OVERDUE","NEAR_DUE_NOT_STARTED","STALE","RETURNED","BLOCKED"]).to.include(x.code))));"""))),
    req("[sv2] GET health", "GET", "/api/projects/{{project_id}}/health", tests=status(200, j("""
pm.test("level ∈ green|yellow|red + đủ trường", () => { pm.expect(["green","yellow","red"]).to.include(j.level);
  ["reasons","overdue_count","risk_count","late_milestones"].forEach(k => pm.expect(j).to.have.property(k)); });"""))),
    req("[sv2] GET contributions — KHÔNG thấy điểm đánh giá chéo", "GET", "/api/projects/{{project_id}}/contributions", tests=status(200, j("""
pm.test("Không có giám sát, không có điểm xếp hạng", () => j.forEach(r => { pm.expect(r.project_role).to.not.eql("supervisor"); pm.expect(r).to.not.have.property("rank"); }));
pm.test("Điểm đánh giá chéo bị ẩn với thành viên", () => j.forEach(r => pm.expect(r.peer_review_average).to.be.null));"""))),
    req("[sv2] GET activity?limit=5", "GET", "/api/projects/{{project_id}}/activity?limit=5", tests=status(200, j(
        'pm.test("≤ 5 dòng, có summary", () => { pm.expect(j.length).to.be.at.most(5); j.forEach(a => pm.expect(a.summary).to.be.a("string")); });'))),
    req("[sv2] GET activity?limit=abc → 400", "GET", "/api/projects/{{project_id}}/activity?limit=abc", tests=err("VALIDATION_ERROR", 400)),
    req("[sv2] GET peer-reviews (đã gửi của mình)", "GET", "/api/projects/{{project_id}}/peer-reviews", tests=status(200, j(
        'pm.test("Danh sách đánh giá mình đã gửi, không lộ người chấm khác", () => { pm.expect(j).to.be.an("array"); j.forEach(r => pm.expect(r.reviewer_id).to.eql(pm.collectionVariables.get("uid_sv2"))); });'))),
    req("[sv2] GET risk-evaluation → 403", "GET", "/api/projects/{{project_id}}/risk-evaluation", tests=err("FORBIDDEN", 403)),
    req("[sv2] GET report → CSV", "GET", "/api/projects/{{project_id}}/report", tests=status(200, """
pm.test("Content-Type text/csv + attachment", () => { pm.expect(pm.response.headers.get("Content-Type")).to.include("text/csv"); pm.expect(pm.response.headers.get("Content-Disposition")).to.include("attachment"); });
pm.test("Có dòng tiêu đề tiếng Việt", () => pm.expect(pm.response.text()).to.include("Họ tên"));
pm.test("Thành viên không thấy cột đánh giá chéo", () => pm.expect(pm.response.text()).to.not.include("Điểm đánh giá chéo"));""")),
    req("[sv2] POST peer-reviews: tự đánh giá → 400", "POST", "/api/projects/{{project_id}}/peer-reviews",
        {"reviewee_id": "{{uid_sv2}}", "score": 3}, err("VALIDATION_ERROR", 400), pre='pm.request.body.raw = JSON.stringify({reviewee_id: Number(pm.collectionVariables.get("uid_sv2")), score: 3});'),
    req("[sv2] POST peer-reviews: điểm 6 → 400", "POST", "/api/projects/{{project_id}}/peer-reviews", {"reviewee_id": 3, "score": 6},
        err("VALIDATION_ERROR", 400)),
    req("[sv2] POST peer-reviews: người ngoài dự án → 404", "POST", "/api/projects/{{project_id}}/peer-reviews",
        {"reviewee_id": 9999, "score": 3}, err("REVIEWEE_NOT_FOUND", 404)),
    login("gv", False),
    req("[gv giám sát] GET peer-reviews — tổng hợp ẩn danh", "GET", "/api/projects/{{project_id}}/peer-reviews", tests=status(200, j("""
pm.test("Tổng hợp theo người được đánh giá, không có người chấm", () => { pm.expect(j).to.be.an("array");
  j.forEach(x => { ["reviewee","count","average","distribution","comments"].forEach(k => pm.expect(x).to.have.property(k)); }); });
pm.test("Không rò rỉ reviewer", () => pm.expect(pm.response.text()).to.not.include("reviewer"));"""))),
    req("[gv] POST peer-reviews → 403 (giám sát không chấm)", "POST", "/api/projects/{{project_id}}/peer-reviews", {"reviewee_id": 3, "score": 3},
        err("FORBIDDEN", 403)),
    req("[gv] GET contributions — thấy điểm đánh giá chéo", "GET", "/api/projects/{{project_id}}/contributions", tests=status(200, j(
        'pm.test("Có ít nhất một người có điểm trung bình", () => pm.expect(j.some(r => r.peer_review_average !== null)).to.be.true);'))),
    req("[gv] GET risk-evaluation", "GET", "/api/projects/{{project_id}}/risk-evaluation", tests=status(200, j("""
pm.test("Có recall, cảnh báo sớm, cảnh báo thừa", () => ["recall","avg_lead_days","false_alarm_rate","late_tasks","on_time_tasks","per_rule","details","thresholds"].forEach(k => pm.expect(j).to.have.property(k)));
pm.test("Tỷ lệ trong 0–100 hoặc null", () => ["recall","false_alarm_rate"].forEach(k => { if (j[k] !== null) pm.expect(j[k]).to.be.within(0, 100); }));"""))),
    req("[gv] GET risk-evaluation với ngưỡng khác", "GET", "/api/projects/{{project_id}}/risk-evaluation?days_before_due=5&days_no_update=2&return_count=2",
        tests=status(200, j('pm.test("Ngưỡng được áp dụng", () => { pm.expect(j.thresholds.days_before_due).to.eql(5); pm.expect(j.thresholds.days_no_update).to.eql(2); });'))),
    req("[gv] GET risk-evaluation ngưỡng sai → 400", "GET", "/api/projects/{{project_id}}/risk-evaluation?days_before_due=abc", tests=err("VALIDATION_ERROR", 400)),
    req("[gv chủ workspace] GET overview", "GET", "/api/workspaces/{{workspace_id}}/overview", tests=status(200, j("""
pm.test("Có tổng hợp và danh sách dự án, dự án nguy cấp đứng đầu", () => { pm.expect(j.projects).to.be.an("array").that.is.not.empty;
  const o = {red:0, yellow:1, green:2}; const lv = j.projects.map(p => o[p.health.level]); pm.expect(lv).to.eql([...lv].sort((a,b)=>a-b));
  pm.expect(j.totals.red + j.totals.yellow + j.totals.green).to.eql(j.project_count); });"""))),
    login("sv1", False),
    req("[sv1 quản lý] GET workspace overview → 403 (không phải chủ)", "GET", "/api/workspaces/{{workspace_id}}/overview", tests=err("FORBIDDEN", 403)),
    req("[sv1 quản lý] GET risk-evaluation", "GET", "/api/projects/{{project_id}}/risk-evaluation", tests=status(200)),
    req("[sv1] GET report — quản lý thấy cột đánh giá chéo", "GET", "/api/projects/{{project_id}}/report", tests=status(200,
        'pm.test("Có cột Điểm đánh giá chéo", () => pm.expect(pm.response.text()).to.include("Điểm đánh giá chéo"));')),
    login("admin", False),
    req("[admin] GET overview", "GET", "/api/workspaces/{{workspace_id}}/overview", tests=status(200)),
    req("[admin] POST peer-reviews → 403 (admin không phải người trong cuộc)", "POST", "/api/projects/{{project_id}}/peer-reviews",
        {"reviewee_id": 3, "score": 3}, err("FORBIDDEN", 403)),
]}

# ------------------------------------------------------------------ 02 — luồng nghiệp vụ đầy đủ
PRE_DATES = """
const d = (n) => { const x = new Date(); x.setDate(x.getDate() + n); return x.toISOString().slice(0, 10); };
pm.collectionVariables.set("flow_start", d(-6)); pm.collectionVariables.set("flow_due", d(8)); pm.collectionVariables.set("flow_ms_due", d(5));
pm.collectionVariables.set("flow_a_due", d(3)); pm.collectionVariables.set("flow_b_due", d(-1)); pm.collectionVariables.set("flow_c_due", d(1));
"""
PM = "pm.collectionVariables"
P = "/api/projects/{{flow_project_id}}"


def invite(who, role, var):
    return req(f"[sv1] Mời {who} ({role})", "POST", P + "/invitations", {"email": f"{who}@teamsync.local", "project_role": role},
               status(201, f'{PM}.set("{var}", pm.response.json().data.token);'))


def accept(who, var):
    return [login(who, False), req(f"[{who}] Nhận lời mời", "POST", f"/api/invitations/{{{{{var}}}}}/accept", {}, status(200))]


def set_status(who, task_var, new, note=None):
    body = {"status": new}
    if note:
        body["note"] = note
    return req(f"[{who}] Chuyển việc sang {new}", "PATCH", f"/api/tasks/{{{{{task_var}}}}}/status", body, status(200))


f02 = {"name": "02 — Luồng nghiệp vụ: tạo dự án → … → nghiệm thu → dashboard", "item": [
    login("sv1", False),
    req("[sv1] Tạo dự án", "POST", "/api/workspaces/{{workspace_id}}/projects",
        {"name": "Luồng Postman {{$timestamp}}", "description": "Dự án do Postman tạo, tự xóa ở cuối", "start_date": "{{flow_start}}", "due_date": "{{flow_due}}"},
        status(201, j(f'pm.test("Người tạo là quản lý", () => pm.expect(j.my_role).to.eql("manager"));\n{PM}.set("flow_project_id", j.id);')), PRE_DATES),
    invite("sv2", "member", "inv_sv2"), invite("sv3", "member", "inv_sv3"), invite("gv", "supervisor", "inv_gv"),
    *accept("sv2", "inv_sv2"), *accept("sv3", "inv_sv3"), *accept("gv", "inv_gv"),
    login("sv1", False),
    req("[sv1] Lập cột mốc", "POST", P + "/milestones", {"title": "Cột mốc Postman", "due_date": "{{flow_ms_due}}"},
        status(201, f'{PM}.set("flow_ms", pm.response.json().data.id);')),
    req("[sv1] Giao việc A (sv2, 3 điểm, thuộc cột mốc)", "POST", P + "/tasks",
        {"title": "Việc A", "points": 3, "due_date": "{{flow_a_due}}", "assignee_id": "{{uid_sv2}}", "milestone_id": "{{flow_ms}}"},
        status(201, f'{PM}.set("flow_a", pm.response.json().data.id);'),
        'pm.request.body.raw = JSON.stringify({title:"Việc A", points:3, due_date: pm.collectionVariables.get("flow_a_due"), assignee_id:Number(pm.collectionVariables.get("uid_sv2")), milestone_id:Number(pm.collectionVariables.get("flow_ms"))});'),
    req("[sv1] Giao việc B (sv3, 2 điểm, ĐÃ QUÁ HẠN)", "POST", P + "/tasks", {"title": "Việc B"},
        status(201, f'{PM}.set("flow_b", pm.response.json().data.id);'),
        'pm.request.body.raw = JSON.stringify({title:"Việc B", points:2, due_date: pm.collectionVariables.get("flow_b_due"), assignee_id:Number(pm.collectionVariables.get("uid_sv3"))});'),
    req("[sv1] Giao việc C (sv2, 1 điểm, sắp tới hạn, chưa bắt đầu)", "POST", P + "/tasks", {"title": "Việc C"},
        status(201, f'{PM}.set("flow_c", pm.response.json().data.id);'),
        'pm.request.body.raw = JSON.stringify({title:"Việc C", points:1, due_date: pm.collectionVariables.get("flow_c_due"), assignee_id:Number(pm.collectionVariables.get("uid_sv2"))});'),
    login("sv2", False),
    set_status("sv2", "flow_a", "in_progress"),
    req("[sv2] Nộp minh chứng cho việc A", "POST", "/api/tasks/{{flow_a}}/attachments", {"url": "https://github.com/example/teamsync/pull/1"}, status(201)),
    set_status("sv2", "flow_a", "review"),
    login("sv1", False),
    req("[sv1] Trả lại việc A (ghi lý do)", "POST", "/api/tasks/{{flow_a}}/review", {"action": "return", "note": "Thiếu kiểm thử"}, status(200)),
    login("sv2", False),
    set_status("sv2", "flow_a", "review"),
    login("sv1", False),
    req("[sv1] Duyệt việc A → done", "POST", "/api/tasks/{{flow_a}}/review", {"action": "approve", "note": "Đạt"},
        status(200, 'pm.test("Việc A đã done", () => pm.expect(pm.response.json().data.status).to.eql("done"));')),
    # ---- M17 đọc số liệu thật vừa sinh ra
    req("[sv1] M17 stats — số liệu khớp luồng vừa chạy", "GET", P + "/stats", tests=status(200, j("""
pm.test("3 việc: 1 done, 2 todo", () => { pm.expect(j.total).to.eql(3); pm.expect(j.by_status.done).to.eql(1); pm.expect(j.by_status.todo).to.eql(2); });
pm.test("Điểm: 3/6 = 50%", () => { pm.expect(j.points_total).to.eql(6); pm.expect(j.points_done).to.eql(3); pm.expect(j.percent_points).to.eql(50); });
pm.test("1 việc quá hạn, 1 việc đúng hạn → 50%", () => { pm.expect(j.overdue).to.eql(1); pm.expect(j.on_time).to.eql(1); pm.expect(j.on_time_rate).to.eql(50); });
pm.test("Cột mốc có 1 việc đã xong", () => { const m = j.by_milestone.find(x => x.title === "Cột mốc Postman"); pm.expect(m.total).to.eql(1); pm.expect(m.percent_done).to.eql(100); });"""))),
    req("[sv1] M17 risks — B quá hạn, C sắp tới hạn", "GET", P + "/risks", tests=status(200, j("""
const codes = (t) => (j.find(r => r.title === t) || {reasons: []}).reasons.map(x => x.code);
pm.test("Việc B: OVERDUE", () => pm.expect(codes("Việc B")).to.include("OVERDUE"));
pm.test("Việc C: NEAR_DUE_NOT_STARTED", () => pm.expect(codes("Việc C")).to.include("NEAR_DUE_NOT_STARTED"));
pm.test("Việc A đã xong không bị cảnh báo", () => pm.expect(codes("Việc A")).to.be.empty);
pm.test("Mỗi lý do có chi tiết", () => j.forEach(r => r.reasons.forEach(x => pm.expect(x.detail).to.be.a("string").that.is.not.empty)));"""))),
    req("[sv1] M17 health — vàng", "GET", P + "/health", tests=status(200, j(
        'pm.test("1 việc quá hạn < ngưỡng đỏ → vàng", () => { pm.expect(j.level).to.eql("yellow"); pm.expect(j.overdue_count).to.eql(1); pm.expect(j.risk_count).to.eql(2); });'))),
    req("[sv1] M17 contributions — sổ đóng góp", "GET", P + "/contributions", tests=status(200, j("""
const u = (id) => j.find(r => r.user_id === Number(pm.collectionVariables.get(id)));
pm.test("sv2: 2 việc, xong 1, bị trả lại 1, 1 minh chứng", () => { const r = u("uid_sv2"); pm.expect(r.assigned_tasks).to.eql(2); pm.expect(r.completed_tasks).to.eql(1); pm.expect(r.returned_count).to.eql(1); pm.expect(r.evidence_count).to.eql(1); pm.expect(r.on_time_rate).to.eql(100); });
pm.test("sv3: 1 việc quá hạn chưa xong", () => { const r = u("uid_sv3"); pm.expect(r.assigned_tasks).to.eql(1); pm.expect(r.overdue_open).to.eql(1); pm.expect(r.completed_tasks).to.eql(0); });"""))),
    req("[sv1] M17 activity — có dòng trả lại", "GET", P + "/activity", tests=status(200, j(
        'pm.test("Có bước trả lại và duyệt", () => { const s = j.map(a => a.summary).join("|"); pm.expect(s).to.include("trả lại"); pm.expect(s).to.include("duyệt"); });'))),
    # ---- đánh giá chéo
    login("sv2", False),
    req("[sv2] Chấm sv3: 4 sao", "POST", P + "/peer-reviews", {"reviewee_id": 0, "score": 4, "comment": "Hợp tác tốt"}, status(201, j(
        'pm.test("Không lộ người chấm", () => pm.expect(j).to.not.have.property("reviewer_id"));')),
        'pm.request.body.raw = JSON.stringify({reviewee_id:Number(pm.collectionVariables.get("uid_sv3")), score:4, comment:"Hợp tác tốt"});'),
    req("[sv2] Chấm sv3 lần nữa → 409", "POST", P + "/peer-reviews", {"reviewee_id": 0, "score": 5}, err("ALREADY_REVIEWED", 409),
        'pm.request.body.raw = JSON.stringify({reviewee_id:Number(pm.collectionVariables.get("uid_sv3")), score:5});'),
    login("sv3", False),
    req("[sv3] Chấm sv1: 5 sao", "POST", P + "/peer-reviews", {"reviewee_id": 0, "score": 5}, status(201),
        'pm.request.body.raw = JSON.stringify({reviewee_id:Number(pm.collectionVariables.get("uid_sv1")), score:5});'),
    req("[sv3] Sổ đóng góp không có điểm đánh giá chéo", "GET", P + "/contributions", tests=status(200, j(
        'pm.test("Ẩn với thành viên", () => j.forEach(r => pm.expect(r.peer_review_average).to.be.null));'))),
    login("gv", False),
    req("[gv] Tổng hợp đánh giá chéo", "GET", P + "/peer-reviews", tests=status(200, j("""
pm.test("sv3 nhận 1 lượt, trung bình 4", () => { const r = j.find(x => x.reviewee.id === Number(pm.collectionVariables.get("uid_sv3"))); pm.expect(r.count).to.eql(1); pm.expect(r.average).to.eql(4); });
pm.test("Ẩn danh", () => pm.expect(pm.response.text()).to.not.include("reviewer"));"""))),
    # ---- nghiệm thu cột mốc
    login("sv1", False),
    req("[sv1] Gửi nghiệm thu cột mốc", "POST", "/api/milestones/{{flow_ms}}/submit", {}, status(200)),
    login("gv", False),
    req("[gv] Nghiệm thu cột mốc", "POST", "/api/milestones/{{flow_ms}}/review", {"action": "accept", "note": "Đạt"}, status(200)),
    req("[gv] stats: cột mốc đã nghiệm thu", "GET", P + "/stats", tests=status(200, j(
        'pm.test("Cột mốc accepted", () => pm.expect(j.by_milestone.find(x => x.title === "Cột mốc Postman").status).to.eql("accepted"));'))),
    # ---- báo cáo, tổng quan, đánh giá luật
    req("[gv] Xuất CSV sổ đóng góp", "GET", P + "/report", tests=status(200, """
pm.test("CSV có đủ thành viên và cột đánh giá chéo (giám sát)", () => { const t = pm.response.text(); pm.expect(pm.response.headers.get("Content-Type")).to.include("text/csv"); pm.expect(t).to.include("Sinh viên 2"); pm.expect(t).to.include("Điểm đánh giá chéo TB"); });""")),
    req("[gv] Tổng quan workspace có dự án vừa tạo", "GET", "/api/workspaces/{{workspace_id}}/overview", tests=status(200, j(
        'pm.test("Có dự án luồng Postman", () => pm.expect(j.projects.some(p => p.project.id === Number(pm.collectionVariables.get("flow_project_id")))).to.be.true);'))),
    req("[gv] Đánh giá luật: việc B (trễ) được cảnh báo trước hạn?", "GET", P + "/risk-evaluation", tests=status(200, j("""
pm.test("Chỉ số hợp lệ", () => { pm.expect(j.evaluated).to.be.at.least(0); pm.expect(j.warned_late).to.be.at.most(j.late_tasks); });"""))),
    # ---- dọn dẹp để chạy lại được
    login("sv1", False),
    req("[sv1] Xóa dự án Postman (dọn dẹp)", "DELETE", P, tests=status(200)),
    req("Sau khi xóa → stats 404", "GET", P + "/stats", tests=err("PROJECT_NOT_FOUND", 404)),
]}

collection = {
    "info": {"name": "TeamSync — luồng nghiệp vụ đầy đủ", "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
             "description": "Sinh bởi tests/postman/build_collection.py. Chạy trên database mới seed. 00: đăng nhập; 01: M17 theo vai trò; "
                            "02: tạo dự án → mời → giao việc → minh chứng → duyệt/trả lại → nghiệm thu → dashboard/sổ đóng góp → xóa."},
    "item": [f00, f01, f02],
}
OUT.write_text(json.dumps(collection, ensure_ascii=False, indent=2), encoding="utf-8")
n = sum(len(f["item"]) for f in collection["item"])
print(f"Đã ghi {n} request vào {OUT}")
