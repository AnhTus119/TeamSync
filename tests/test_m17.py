"""Kiểm thử M17 — chạy:  python tests/test_m17.py
Seed: dự án 1 (demo) — sv1 quản lý, sv2/sv3 thành viên, gv giám sát + chủ workspace, sv4 ngoài dự án; mật khẩu 123456.
Dự án 2–5 là dự án mô phỏng của M17. Ngày trong dữ liệu tính tương đối so với hôm nay nên kiểm thử không phụ thuộc ngày chạy.
"""
from datetime import date, datetime, timedelta
from types import SimpleNamespace

from helpers import Api, make_client

from app.extensions import db
from app.m17_reports import risk, services
from app.models import PeerReview, Project, Task, TaskHistory, User

app, c = make_client()
api = Api(c)
TODAY = date.today()
with app.app_context():
    ids = {u.email.split("@")[0]: u.id for u in User.query.all()}

GET_URLS = ("stats", "risks", "health", "contributions", "activity", "peer-reviews", "report", "risk-evaluation")

# ---------------------------------------------------------------- xác thực và quyền xem
for u in GET_URLS:
    api("GET", f"/api/projects/1/{u}", status=401, code="UNAUTHORIZED")
api("GET", "/api/workspaces/1/overview", status=401, code="UNAUTHORIZED")
api("POST", "/api/projects/1/peer-reviews", {"reviewee_id": 1, "score": 3}, 401, "UNAUTHORIZED")

api.login("sv4")  # ngoài dự án
for u in GET_URLS:
    api("GET", f"/api/projects/1/{u}", status=403, code="FORBIDDEN")
api("POST", "/api/projects/1/peer-reviews", {"reviewee_id": ids["sv1"], "score": 3}, 403, "FORBIDDEN")
api("GET", "/api/workspaces/1/overview", status=403, code="FORBIDDEN")  # thành viên workspace nhưng không phải chủ
api("GET", "/api/projects/999/stats", status=404, code="PROJECT_NOT_FOUND")
api("GET", "/api/workspaces/999/overview", status=404, code="WORKSPACE_NOT_FOUND")

# ---------------------------------------------------------------- thống kê (dự án demo)
api.login("sv2")
s = api("GET", "/api/projects/1/stats")
assert s["total"] == 7 and s["done"] == 1 and s["percent_done"] == 14.3
assert s["by_status"] == {"todo": 4, "in_progress": 1, "review": 1, "done": 1}
assert (s["points_total"], s["points_done"], s["percent_points"]) == (21, 3, 14.3)
assert s["overdue"] == 1 and s["on_time"] == 1 and s["late"] == 0 and s["on_time_rate"] == 50.0
assert [m["title"] for m in s["by_milestone"]] == ["Phân tích yêu cầu", "Xây dựng", "Báo cáo và demo"]
ms = {m["title"]: m for m in s["by_milestone"]}
assert ms["Phân tích yêu cầu"]["percent_done"] == 100 and ms["Xây dựng"]["total"] == 4 and ms["Xây dựng"]["overdue"] == 1
assert ms["Báo cáo và demo"]["on_time_rate"] is None  # chưa có mẫu → null chứ không phải 0
assert s["my_role"] == "member" and s["project"]["name"] == "TeamSync demo" and not s["project"]["is_workspace_owner"]
tl = s["timeline"]
assert len(tl["labels"]) == len(tl["planned_points"]) == len(tl["done_points"]) and tl["today"] == TODAY.isoformat()
assert tl["planned_points"] == sorted(tl["planned_points"])  # kế hoạch cộng dồn → không giảm
done_so_far = [x for x in tl["done_points"] if x is not None]
assert done_so_far == sorted(done_so_far) and done_so_far[-1] == 3
assert tl["done_points"][-1] is None or tl["labels"][-1] <= TODAY.isoformat()  # sau hôm nay không vẽ "thực tế"

# ---------------------------------------------------------------- rủi ro + lý do
rs = api("GET", "/api/projects/1/risks")
by_title = {r["title"]: r for r in rs}
assert set(by_title) == {"Kiểm thử Postman", "Trang dashboard", "Giao diện bảng Kanban"}, list(by_title)
assert [x["code"] for x in by_title["Kiểm thử Postman"]["reasons"]] == ["OVERDUE"]
assert "1 ngày" in by_title["Kiểm thử Postman"]["reasons"][0]["detail"]
assert [x["code"] for x in by_title["Trang dashboard"]["reasons"]] == ["NEAR_DUE_NOT_STARTED"]
assert [x["code"] for x in by_title["Giao diện bảng Kanban"]["reasons"]] == ["STALE"]
assert "7 ngày không có cập nhật" in by_title["Giao diện bảng Kanban"]["reasons"][0]["detail"]
assert all({"code", "label", "detail"} <= set(x) for r in rs for x in r["reasons"])
assert rs[0]["title"] == "Kiểm thử Postman" and rs[0]["severity"] == "high"  # nặng nhất đứng đầu
assert by_title["Kiểm thử Postman"]["assignee"]["id"] == ids["sv2"]

# ---------------------------------------------------------------- đèn sức khỏe
h = api("GET", "/api/projects/1/health")
assert h["level"] == "yellow" and h["overdue_count"] == 1 and h["risk_count"] == 3 and h["late_milestones"] == 0
assert h["reasons"] and all(isinstance(x, str) for x in h["reasons"])
# đổi ngưỡng đỏ xuống 1 → đỏ (ngưỡng đọc từ config, không gõ cứng)
app.config["HEALTH_RED_OVERDUE"] = 1
assert api("GET", "/api/projects/1/health")["level"] == "red"
app.config["HEALTH_RED_OVERDUE"] = 2
# đổi ngưỡng cảnh báo qua config
app.config["RISK_DAYS_BEFORE_DUE"] = 0
assert "Trang dashboard" not in [r["title"] for r in api("GET", "/api/projects/1/risks")]
app.config["RISK_DAYS_BEFORE_DUE"] = 2
# cột mốc quá hạn mà chưa nghiệm thu → đèn đỏ
api.login("admin")
for pid in range(2, 6):
    hh = api("GET", f"/api/projects/{pid}/health")
    assert hh["level"] in ("green", "yellow", "red") and hh["late_milestones"] == len(hh["late_milestone_items"])
    if hh["late_milestones"]:
        assert hh["level"] == "red" and any("Cột mốc" in x for x in hh["reasons"])
levels = {api("GET", f"/api/projects/{p}/health")["level"] for p in range(1, 6)}
assert levels == {"green", "yellow", "red"}, levels  # dữ liệu mô phỏng có đủ ba màu

# ---------------------------------------------------------------- sổ đóng góp
rows = api("GET", "/api/projects/1/contributions")
r = {x["user_id"]: x for x in rows}
assert [x["project_role"] for x in rows] == ["manager", "member", "member"]  # không có giám sát, không xếp hạng
assert (r[ids["sv1"]]["assigned_tasks"], r[ids["sv1"]]["completed_tasks"], r[ids["sv1"]]["completed_points"]) == (2, 1, 3)
assert r[ids["sv1"]]["on_time"] == 1 and r[ids["sv1"]]["on_time_rate"] == 100.0 and r[ids["sv1"]]["evidence_count"] == 1
assert (r[ids["sv2"]]["assigned_points"], r[ids["sv2"]]["returned_count"], r[ids["sv2"]]["evidence_count"],
        r[ids["sv2"]]["overdue_open"]) == (7, 1, 2, 1)
assert r[ids["sv3"]]["assigned_tasks"] == 2 and r[ids["sv3"]]["on_time_rate"] is None
assert "rank" not in rows[0] and "score" not in rows[0]
# điểm đánh giá chéo: thành viên KHÔNG thấy; quản lý/giám sát/admin thấy
assert all(x["peer_review_average"] is None and x["peer_review_count"] is None for x in rows) is False  # admin thấy
api.login("sv3")
assert all(x["peer_review_average"] is None and x["peer_review_count"] is None for x in api("GET", "/api/projects/1/contributions"))
api.login("gv")
pr = {x["user_id"]: x for x in api("GET", "/api/projects/1/contributions")}
assert pr[ids["sv2"]]["peer_review_average"] == 4.0 and pr[ids["sv2"]]["peer_review_count"] == 2
api.login("sv1")
assert {x["user_id"]: x["peer_review_average"] for x in api("GET", "/api/projects/1/contributions")}[ids["sv3"]] == 4.0

# ---------------------------------------------------------------- hoạt động
act = api("GET", "/api/projects/1/activity?limit=3")
assert len(act) == 3 and act[0]["created_at"] >= act[1]["created_at"] >= act[2]["created_at"]
assert all(a["summary"] and a["task_title"] and a["user"]["full_name"] for a in act)
full = api("GET", "/api/projects/1/activity")
assert len(full) <= 20 and any(a["field"] == "review" and a["summary"].startswith("trả lại") for a in full)
api("GET", "/api/projects/1/activity?limit=abc", status=400, code="VALIDATION_ERROR")
api("GET", "/api/projects/1/activity?limit=0", status=400, code="VALIDATION_ERROR")
assert len(api("GET", "/api/projects/1/activity?limit=9999")) <= 100
# dòng "status" trùng với dòng "review" không bị lặp trong bảng tin
reviews = [a for a in full if a["field"] == "review"]
for a in reviews:
    assert not any(b["field"] == "status" and b["task_id"] == a["task_id"] and b["new_value"] == a["new_value"]
                   and abs((datetime.fromisoformat(b["created_at"]) - datetime.fromisoformat(a["created_at"])).total_seconds()) <= 3600
                   for b in full)

# ---------------------------------------------------------------- đánh giá chéo
api.login("sv2")
mine = api("GET", "/api/projects/1/peer-reviews")  # thành viên: các đánh giá mình đã gửi
assert [(x["reviewee_id"], x["score"]) for x in mine] == [(ids["sv3"], 4)]
m = api("GET", "/api/projects/1/peer-reviews?mine=1")
assert [u["id"] for u in m["pending"]] == [ids["sv1"]] and len(m["reviews"]) == 1
bad = [({"score": 3}, "VALIDATION_ERROR"), ({"reviewee_id": ids["sv1"]}, "VALIDATION_ERROR"),
       ({"reviewee_id": ids["sv1"], "score": 0}, "VALIDATION_ERROR"), ({"reviewee_id": ids["sv1"], "score": 6}, "VALIDATION_ERROR"),
       ({"reviewee_id": ids["sv1"], "score": 4.5}, "VALIDATION_ERROR"), ({"reviewee_id": ids["sv1"], "score": "5"}, "VALIDATION_ERROR"),
       ({"reviewee_id": ids["sv1"], "score": True}, "VALIDATION_ERROR"), ({"reviewee_id": "x", "score": 3}, "VALIDATION_ERROR"),
       ({"reviewee_id": ids["sv1"], "score": 3, "comment": 5}, "VALIDATION_ERROR"),
       ({"reviewee_id": ids["sv1"], "score": 3, "comment": "x" * 1001}, "VALIDATION_ERROR"),
       ({"reviewee_id": ids["sv2"], "score": 3}, "VALIDATION_ERROR")]  # tự đánh giá
for body, code in bad:
    api("POST", "/api/projects/1/peer-reviews", body, 400, code)
api("POST", "/api/projects/1/peer-reviews", {"reviewee_id": ids["sv4"], "score": 3}, 404, "REVIEWEE_NOT_FOUND")  # ngoài dự án
api("POST", "/api/projects/1/peer-reviews", {"reviewee_id": ids["gv"], "score": 3}, 404, "REVIEWEE_NOT_FOUND")  # giám sát
api("POST", "/api/projects/1/peer-reviews", {"reviewee_id": 9999, "score": 3}, 404, "REVIEWEE_NOT_FOUND")
api("POST", "/api/projects/1/peer-reviews", {"reviewee_id": ids["sv3"], "score": 2}, 409, "ALREADY_REVIEWED")  # trùng cặp
new = api("POST", "/api/projects/1/peer-reviews", {"reviewee_id": ids["sv1"], "score": 5, "comment": "  Quản lý tốt  "}, 201)
assert new["score"] == 5 and new["comment"] == "Quản lý tốt" and "reviewer_id" not in new  # người chấm ẩn danh
api("POST", "/api/projects/1/peer-reviews", {"reviewee_id": ids["sv1"], "score": 1}, 409, "ALREADY_REVIEWED")
assert api("GET", "/api/projects/1/peer-reviews?mine=1")["pending"] == []

api.login("gv")  # giám sát: xem tổng hợp, không được chấm
api("POST", "/api/projects/1/peer-reviews", {"reviewee_id": ids["sv1"], "score": 3}, 403, "FORBIDDEN")
summary = {x["reviewee"]["id"]: x for x in api("GET", "/api/projects/1/peer-reviews")}
assert summary[ids["sv1"]]["count"] == 2 and summary[ids["sv1"]]["average"] == 4.5
assert summary[ids["sv1"]]["distribution"] == {"1": 0, "2": 0, "3": 0, "4": 1, "5": 1}
assert {x["comment"] for x in summary[ids["sv1"]]["comments"]} == {"Phân việc rõ ràng", "Quản lý tốt"}
raw = c.get("/api/projects/1/peer-reviews").get_data(as_text=True)
assert "reviewer" not in raw  # không rò rỉ người chấm dưới bất kỳ trường nào
assert api("GET", "/api/projects/1/peer-reviews?mine=1") == {"reviews": [], "pending": []}
api.login("admin")
assert len(api("GET", "/api/projects/1/peer-reviews")) == 3
api("POST", "/api/projects/1/peer-reviews", {"reviewee_id": ids["sv1"], "score": 3}, 403, "FORBIDDEN")  # admin không chấm
api.login("sv1")  # quản lý vừa xem tổng hợp vừa chấm được
assert len(api("GET", "/api/projects/1/peer-reviews")) == 3
api("POST", "/api/projects/1/peer-reviews", {"reviewee_id": ids["sv3"], "score": 3, "comment": ""}, 201)
with app.app_context():
    assert PeerReview.query.filter_by(project_id=1).count() == 6
    try:  # ràng buộc DB chặn điểm ngoài 1–5 kể cả khi qua mặt API
        db.session.add(PeerReview(project_id=1, reviewer_id=ids["sv3"], reviewee_id=ids["sv2"], score=9))
        db.session.commit()
        raise AssertionError("CHECK constraint không hoạt động")
    except AssertionError:
        raise
    except Exception:
        db.session.rollback()

# ---------------------------------------------------------------- CSV
api.login("sv1")
resp = c.get("/api/projects/1/report")
assert resp.status_code == 200 and resp.mimetype == "text/csv"
assert "attachment" in resp.headers["Content-Disposition"] and ".csv" in resp.headers["Content-Disposition"]
body = resp.get_data()
assert body.startswith(b"\xef\xbb\xbf")  # BOM UTF-8 cho Excel
text = body.decode("utf-8-sig").splitlines()
assert text[0].startswith("Họ tên,Email,Vai trò") and "Điểm đánh giá chéo TB" in text[0] and len(text) == 4
api.login("sv3")
text = c.get("/api/projects/1/report").get_data().decode("utf-8-sig")
assert "Điểm đánh giá chéo" not in text and "Sinh viên 2" in text  # thành viên không thấy cột đánh giá chéo
with app.app_context():  # chống CSV injection
    User.query.filter_by(email="sv3@teamsync.local").one().full_name = '=HYPERLINK("http://x")'
    db.session.commit()
assert "'=HYPERLINK" in c.get("/api/projects/1/report").get_data().decode("utf-8-sig")
assert services.csv_safe("+1") == "'+1" and services.csv_safe("An") == "An" and services.csv_safe(None) == ""

# ---------------------------------------------------------------- tổng quan workspace
api.login("gv")
ov = api("GET", "/api/workspaces/1/overview")
assert ov["project_count"] == 5 and len(ov["projects"]) == 5 and ov["workspace"]["name"] == "Lớp Lập trình Web 01"
order = {"red": 0, "yellow": 1, "green": 2}
lv = [order[p["health"]["level"]] for p in ov["projects"]]
assert lv == sorted(lv)  # dự án nguy cấp đứng đầu
t = ov["totals"]
assert t["red"] + t["yellow"] + t["green"] == 5 and t["total"] == sum(p["stats"]["total"] for p in ov["projects"])
assert all(p["manager"] and p["supervisors"] == ["Giảng viên A (giám sát)"] for p in ov["projects"])
api.login("sv1")
api("GET", "/api/workspaces/1/overview", status=403, code="FORBIDDEN")
api.login("admin")
assert api("GET", "/api/workspaces/1/overview")["project_count"] == 5

# ---------------------------------------------------------------- đánh giá luật cảnh báo
api.login("sv2")
api("GET", "/api/projects/1/risk-evaluation", status=403, code="FORBIDDEN")  # thành viên không xem
api.login("gv")
ev = api("GET", "/api/projects/1/risk-evaluation")
assert (ev["evaluated"], ev["late_tasks"], ev["on_time_tasks"], ev["warned_late"]) == (2, 1, 1, 1)
assert ev["recall"] == 100.0 and ev["avg_lead_days"] == 2.0 and ev["false_alarm_rate"] == 0.0
late = next(d for d in ev["details"] if d["outcome"] == "late")
assert late["title"] == "Kiểm thử Postman" and late["lead_days"] == 2 and late["codes"] == ["NEAR_DUE_NOT_STARTED"]
assert ev["per_rule"]["NEAR_DUE_NOT_STARTED"] == {"late_hit": 1, "on_time_hit": 0}
assert ev["thresholds"] == {"days_before_due": 2, "days_no_update": 3, "return_count": 2, "health_red_overdue": 2}
# đổi ngưỡng để so sánh: sắp tới hạn = 0 ngày thì không còn cảnh báo sớm
e0 = api("GET", "/api/projects/1/risk-evaluation?days_before_due=0")
assert e0["recall"] == 0.0 and e0["avg_lead_days"] is None
e5 = api("GET", "/api/projects/1/risk-evaluation?days_before_due=5")
assert e5["avg_lead_days"] == 5.0  # ngưỡng lớn hơn → cảnh báo sớm hơn
api("GET", "/api/projects/1/risk-evaluation?days_before_due=x", status=400, code="VALIDATION_ERROR")
api("GET", "/api/projects/1/risk-evaluation?return_count=999", status=400, code="VALIDATION_ERROR")
for pid in range(2, 6):  # chỉ số hợp lệ trên dữ liệu mô phỏng
    e = api("GET", f"/api/projects/{pid}/risk-evaluation")
    assert e["late_tasks"] + e["on_time_tasks"] == e["evaluated"] == len(e["details"])
    assert e["warned_late"] <= e["late_tasks"] and e["false_alarm_tasks"] <= e["on_time_tasks"]
    for k in ("recall", "false_alarm_rate"):
        assert e[k] is None or 0 <= e[k] <= 100
    assert all(d["lead_days"] is None or d["lead_days"] >= 1 for d in e["details"])  # cảnh báo luôn TRƯỚC hạn

# ---------------------------------------------------------------- dữ liệu mô phỏng
with app.app_context():
    assert Task.query.count() == 63 and TaskHistory.query.count() > 150
    # dựng lại trạng thái từ lịch sử tại hôm nay phải khớp trạng thái hiện tại của mọi việc
    for p_id in range(1, 6):
        data = services.load_project_data(db.session.get(Project, p_id))
        for task in data.tasks:
            a, b = risk.state_now(task, data.history[task.id]), risk.state_at(task, data.history[task.id], TODAY)
            assert (a.status, a.due_date, a.assignee_id, a.return_count) == (b.status, b.due_date, b.assignee_id, b.return_count), task.title
            assert a.last_update.date() == b.last_update.date(), task.title
    kinds = {h.field for h in TaskHistory.query.all()}
    assert {"status", "review", "attachment", "due_date"} <= kinds  # có đủ tình huống: trả lại, minh chứng, đổi hạn
    assert any(h.old_value == "return" for h in TaskHistory.query.filter_by(field="review"))
    ghosts = [r for p_id in range(2, 6) for r in risk.project_risks(
        services.load_project_data(db.session.get(Project, p_id)),
        TODAY, risk.Thresholds())]
    codes = {x["code"] for r in ghosts for x in r["reasons"]}
    assert {"OVERDUE", "STALE", "RETURNED", "NEAR_DUE_NOT_STARTED"} <= codes, codes
# seed lặp lại được: cùng số liệu
_, c2 = make_client()
api2 = Api(c2)
api2.login("admin")
for pid in range(2, 6):
    assert api2("GET", f"/api/projects/{pid}/stats")["by_status"] == api("GET", f"/api/projects/{pid}/stats")["by_status"]

# ---------------------------------------------------------------- luật cảnh báo: kiểm thử đơn vị (không cần DB)
D = lambda n: TODAY + timedelta(days=n)  # noqa: E731
TH = risk.Thresholds()


def st(status="todo", due=None, last=0, ret=0, title="T"):
    return risk.TaskState(1, title, status, due, None, datetime.combine(D(last), datetime.min.time()), ret, None)


codes = lambda s, deps=(): [x["code"] for x in risk.risk_reasons(s, list(deps), TODAY, TH)]  # noqa: E731
assert codes(st(due=D(-1))) == ["OVERDUE"] and codes(st(due=D(0))) == ["NEAR_DUE_NOT_STARTED"]
assert codes(st(due=D(2))) == ["NEAR_DUE_NOT_STARTED"] and codes(st(due=D(3))) == []  # biên ngưỡng 2 ngày
assert codes(st("in_progress", due=D(2))) == [] and codes(st("done", due=D(-9))) == [] and codes(None) == []
assert codes(st("in_progress", last=-3)) == [] and codes(st("in_progress", last=-4)) == ["STALE"]  # "quá 3 ngày"
assert codes(st("todo", last=-30)) == []  # chỉ việc đang làm mới bị tính là lâu không cập nhật
assert codes(st("review", ret=1)) == [] and codes(st("review", ret=2)) == ["RETURNED"]
assert codes(st("done", ret=5)) == []
late_dep = risk.TaskState(2, "Việc A", "in_progress", None, None, datetime.now(), 0, None)
late_dep = late_dep.__class__(2, "Việc A", "in_progress", D(-2), None, datetime.now(), 0, None)
assert codes(st(due=D(20)), [late_dep]) == ["BLOCKED"]
assert "Việc A" in risk.risk_reasons(st(due=D(20)), [late_dep], TODAY, TH)[0]["detail"]
ok_dep = late_dep.__class__(2, "Việc A", "done", D(-2), None, datetime.now(), 0, None)
assert codes(st(due=D(20)), [ok_dep]) == []
assert codes(st("in_progress", due=D(-3), last=-9, ret=2)) == ["OVERDUE", "STALE", "RETURNED"]  # nhiều lý do cùng lúc
assert risk.severity(risk.risk_reasons(st(due=D(1)), [], TODAY, TH)) == "medium"

# dựng lại trạng thái theo thời gian: hạn bị đổi sau mốc → lấy old_value; việc chưa tạo → None
at = lambda n, h=9: datetime.combine(D(n), datetime.min.time()).replace(hour=h)  # noqa: E731
task = SimpleNamespace(id=1, title="X", created_at=at(-10, 8), updated_at=at(-1), status="in_progress",
                       due_date=D(5), assignee_id=7, completed_at=None)
hist = [SimpleNamespace(field="status", old_value="todo", new_value="in_progress", created_at=at(-8)),
        SimpleNamespace(field="due_date", old_value=str(D(1)), new_value=str(D(5)), created_at=at(-4)),
        SimpleNamespace(field="assignee_id", old_value="3", new_value="7", created_at=at(-3)),
        SimpleNamespace(field="review", old_value="return", new_value="in_progress", created_at=at(-2))]
assert risk.state_at(task, hist, D(-11)) is None
s0 = risk.state_at(task, hist, D(-9))
assert s0.status == "todo" and s0.due_date == D(1) and s0.assignee_id == 3 and s0.return_count == 0
s1 = risk.state_at(task, hist, D(-5))
assert s1.status == "in_progress" and s1.due_date == D(1) and s1.last_update == at(-8)
s2 = risk.state_at(task, hist, D(-3))
assert s2.due_date == D(5) and s2.assignee_id == 7 and s2.return_count == 0
assert risk.state_at(task, hist, D(0)).return_count == 1
bad_hist = [SimpleNamespace(field="due_date", old_value="không-phải-ngày", new_value=str(D(5)), created_at=at(-4))]
assert risk.state_at(task, bad_hist, D(-9)).due_date is None  # dữ liệu lịch sử hỏng không làm sập

# ---------------------------------------------------------------- trang HTML
for who, url, ok_ in (("sv1", "/projects/1/dashboard", 200), ("sv4", "/projects/1/dashboard", 200),
                      ("sv1", "/projects/1/contributions", 200), ("gv", "/workspaces/1/overview", 200)):
    api.login(who)
    r = c.get(url)
    assert r.status_code == ok_, (who, url)
    html = r.get_data(as_text=True)
    assert "m17.css" in html and "m17.js" in html and f'data-{"workspace" if "workspaces" in url else "project"}-id="1"' in html
assert "chart.js" in c.get("/projects/1/dashboard").get_data(as_text=True)
c.post("/api/auth/logout")
r = c.get("/projects/1/dashboard")
assert r.status_code == 302 and "/login" in r.headers["Location"]
assert c.get("/workspaces/1/overview").status_code == 302

# ---------------------------------------------------------------- M17 chỉ ĐỌC bảng M06
api.login("admin")
snapshot = lambda: (TaskHistory.query.count(), Task.query.count(), sum(t.updated_at.timestamp() for t in Task.query))  # noqa: E731
with app.app_context():
    before = snapshot()
for u in GET_URLS:
    c.get(f"/api/projects/2/{u}")
c.get("/api/workspaces/1/overview")
with app.app_context():
    assert snapshot() == before, "API M17 không được ghi vào bảng M06"

print("M17 OK — tất cả kiểm thử đạt")
