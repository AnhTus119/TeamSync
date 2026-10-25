"""Kiểm thử M17 — chạy:  python tests/test_m17.py
Dự án demo (seed): việc 5 quá hạn; việc 3 đang làm nhưng 7 ngày không cập nhật; việc 4 còn 1 ngày tới hạn mà chưa bắt đầu;
việc 2 đã bị trả lại 1 lần. Kỳ vọng: 3 việc có nguy cơ, đèn vàng."""
import csv
import io
from datetime import date, timedelta

from helpers import Api, make_client

app, c = make_client()
api = Api(c)
ids = {}
api.login("admin")
for u in api("GET", "/api/admin/users"):
    ids[u["email"].split("@")[0]] = u["id"]

# --- thống kê ---
api.login("sv2")
s = api("GET", "/api/projects/1/stats")
assert s["total"] == 7 and s["by_status"] == {"todo": 4, "in_progress": 1, "review": 1, "done": 1}
assert s["points_total"] == 21 and s["points_done"] == 3 and s["percent_points"] == 14
assert s["overdue"] == 1 and s["on_time_rate"] == 1.0
assert [m["done"] for m in s["by_milestone"]] == [1, 0, 0]

# --- cảnh báo rủi ro có giải thích ---
risks = {r["task_id"]: {x["code"] for x in r["reasons"]} for r in api("GET", "/api/projects/1/risks")}
assert risks == {5: {"OVERDUE"}, 3: {"STALE"}, 4: {"NEAR_DUE_NOT_STARTED"}}, risks
first = api("GET", "/api/projects/1/risks")[0]
assert first["task_id"] == 5 and first["reasons"][0]["detail"].startswith("Quá hạn 1 ngày")
h = api("GET", "/api/projects/1/health")
assert h["level"] == "yellow" and h["overdue_count"] == 1 and h["risk_count"] == 3

# luật tính lại được tại một ngày trong quá khứ (dựng lại từ TaskHistory)
with app.app_context():
    from app.extensions import db
    from app.m17_reports.risk import reasons_at
    from app.models import Task
    kanban = db.session.get(Task, 3)
    assert reasons_at(kanban, date.today() - timedelta(days=5)) == []          # mới 2 ngày không cập nhật
    assert [c for c, _ in reasons_at(kanban, date.today())] == ["STALE"]      # 7 ngày
    api_task = db.session.get(Task, 2)
    assert reasons_at(api_task, date.today() - timedelta(days=20)) == []       # chưa được tạo

# đổi ngưỡng → đèn đỏ khi có 1 việc quá hạn
app.config["HEALTH_RED_OVERDUE"] = 1
assert api("GET", "/api/projects/1/health")["level"] == "red"
app.config["HEALTH_RED_OVERDUE"] = 2

# --- sổ đóng góp ---
rows = {r["user"]["id"]: r for r in api("GET", "/api/projects/1/contributions")}
assert set(rows) == {ids["sv1"], ids["sv2"], ids["sv3"]}  # không có giám sát
assert rows[ids["sv1"]]["points_done"] == 3 and rows[ids["sv1"]]["on_time"] == 1
assert rows[ids["sv2"]]["assigned_points"] == 7 and rows[ids["sv2"]]["returned"] == 1 and rows[ids["sv2"]]["evidence"] == 2
assert rows[ids["sv2"]]["overdue_open"] == 1
assert "peer_score" not in rows[ids["sv1"]]  # thành viên không thấy điểm đánh giá chéo

# --- đánh giá chéo ---
api("POST", "/api/projects/1/peer-reviews", {"reviewee_id": ids["sv2"], "score": 6}, 400, "VALIDATION_ERROR")
api("POST", "/api/projects/1/peer-reviews", {"reviewee_id": ids["sv2"], "score": 5}, 400, "VALIDATION_ERROR")  # tự đánh giá
api("POST", "/api/projects/1/peer-reviews", {"reviewee_id": ids["gv"], "score": 5}, 400, "VALIDATION_ERROR")  # giám sát
api("POST", "/api/projects/1/peer-reviews", {"reviewee_id": ids["sv1"], "score": 5, "comment": "Điều phối tốt"}, 201)
api("POST", "/api/projects/1/peer-reviews", {"reviewee_id": ids["sv1"], "score": 4}, 409, "ALREADY_REVIEWED")
mine = api("GET", "/api/projects/1/peer-reviews")
assert len(mine) == 1 and "reviewer_id" not in mine[0]
api.login("sv3")
api("POST", "/api/projects/1/peer-reviews", {"reviewee_id": ids["sv1"], "score": 3}, 201)
api.login("gv")
api("POST", "/api/projects/1/peer-reviews", {"reviewee_id": ids["sv1"], "score": 3}, 403)  # giám sát không chấm
summary = {r["user"]["id"]: r for r in api("GET", "/api/projects/1/peer-reviews")}
assert summary[ids["sv1"]]["average"] == 4.0 and summary[ids["sv1"]]["count"] == 2
assert summary[ids["sv1"]]["comments"] == ["Điều phối tốt"] and "reviewer_id" not in str(summary)
assert api("GET", "/api/projects/1/contributions")[0]["peer_score"] is not None

# --- tổng quan workspace, báo cáo, hoạt động, đánh giá luật ---
ov = api("GET", "/api/workspaces/1/overview")
assert ov[0]["project_id"] == 1 and ov[0]["health"] == "yellow"
r = c.get("/api/projects/1/report")
assert r.status_code == 200 and r.mimetype == "text/csv"
table = list(csv.reader(io.StringIO(r.data.decode("utf-8-sig"))))
assert table[0][0] == "Họ tên" and "Điểm đánh giá chéo" in table[0] and len(table) == 4
act = api("GET", "/api/projects/1/activity?limit=5")
assert len(act) == 5 and act[0]["created_at"] >= act[-1]["created_at"] and act[0]["task_title"]
ev = api("GET", "/api/projects/1/risk-evaluation")
assert {"recall", "avg_lead_days", "false_alarm_rate", "tasks"} <= set(ev)
api.login("sv1")
api("GET", "/api/workspaces/1/overview", status=403)
api.login("sv2")
api("GET", "/api/projects/1/risk-evaluation", status=403)
api.login("sv4")
api("GET", "/api/projects/1/stats", status=403)

# --- dữ liệu mô phỏng ---
api.login("admin")
sim = [p for p in api("GET", "/api/projects") if p["name"].startswith("Mô phỏng")]
assert len(sim) == 3
total = {"late": 0, "warned": 0}
for p in sim:
    e = api("GET", f"/api/projects/{p['id']}/risk-evaluation")
    total["late"] += e["late_tasks"]
    total["warned"] += e["late_warned_before_due"]
assert total["late"] > 0 and 0 < total["warned"] <= total["late"]

for url in ("/projects/1/dashboard", "/projects/1/contributions"):
    assert c.get(url).status_code == 200, url

print("M17 OK — tất cả kiểm thử đạt")
