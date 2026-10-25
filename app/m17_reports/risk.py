"""Luật cảnh báo rủi ro có giải thích + đánh giá luật trên lịch sử. Chủ sở hữu: Thành viên 3.

Mọi luật tính được "tại một ngày bất kỳ" bằng cách dựng lại trạng thái việc từ TaskHistory,
nên cùng một hàm dùng cho cả API (hôm nay) lẫn đánh giá (chạy lại từng ngày trong quá khứ).
"""
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from flask import current_app

REASONS = {
    "OVERDUE": "Đã quá hạn nhưng chưa hoàn thành",
    "NEAR_DUE_NOT_STARTED": "Sắp tới hạn nhưng chưa bắt đầu",
    "STALE": "Lâu không có cập nhật",
    "RETURNED": "Bị trả lại nhiều lần",
    "BLOCKED": "Bị chặn bởi việc phụ thuộc đang trễ",
}


@dataclass
class State:
    status: str
    last_activity: datetime
    returns: int


def state_at(task, moment):
    """Trạng thái của task tại thời điểm moment (cuối ngày). None nếu task chưa được tạo."""
    if task.created_at > moment:
        return None
    status, last, returns = "todo", task.created_at, 0
    for h in task.history:
        if h.created_at > moment:
            break
        last = max(last, h.created_at)
        if h.field == "status" and h.new_value:
            status = h.new_value
        elif h.field == "review" and h.old_value == "return":
            returns += 1
    return State(status, last, returns)


def reasons_at(task, day, states=None):
    """Danh sách (code, chi tiết) của task tại ngày `day`. states: cache {task_id: State} cho việc phụ thuộc."""
    cfg = current_app.config
    moment = datetime.combine(day, time.max)
    st = (states or {}).get(task.id) or state_at(task, moment)
    if st is None or st.status == "done":
        return []
    out = []
    if task.due_date:
        left = (task.due_date - day).days
        if left < 0:
            out.append(("OVERDUE", f"Quá hạn {-left} ngày (hạn {task.due_date.isoformat()})"))
        elif st.status == "todo" and left <= cfg["RISK_DAYS_BEFORE_DUE"]:
            out.append(("NEAR_DUE_NOT_STARTED", f"Còn {left} ngày tới hạn nhưng vẫn chưa bắt đầu"))
    idle = (day - st.last_activity.date()).days
    if st.status == "in_progress" and idle > cfg["RISK_DAYS_NO_UPDATE"]:
        out.append(("STALE", f"{idle} ngày không có cập nhật"))
    if st.returns >= cfg["RISK_RETURN_COUNT"]:
        out.append(("RETURNED", f"Đã bị trả lại {st.returns} lần"))
    for d in task.depends_on:
        dep = d.depends_on
        dep_state = (states or {}).get(dep.id) or state_at(dep, moment)
        if dep_state and dep_state.status != "done" and dep.due_date and dep.due_date < day:
            out.append(("BLOCKED", f"Phụ thuộc '{dep.title}' đã quá hạn và chưa xong"))
            break
    return out


def project_risks(project, day=None):
    day = day or date.today()
    result = []
    for t in project.tasks:
        reasons = reasons_at(t, day)
        if reasons:
            result.append({"task_id": t.id, "title": t.title, "status": t.status, "due_date": t.due_date.isoformat()
                           if t.due_date else None, "assignee": t.assignee.brief() if t.assignee else None,
                           "reasons": [{"code": c, "label": REASONS[c], "detail": d} for c, d in reasons]})
    order = list(REASONS)
    result.sort(key=lambda r: min(order.index(x["code"]) for x in r["reasons"]))
    return result


def health(project, day=None):
    """Đèn sức khỏe: red | yellow | green, kèm lý do."""
    day = day or date.today()
    risks = project_risks(project, day)
    overdue = sum(any(x["code"] == "OVERDUE" for x in r["reasons"]) for r in risks)
    late_ms = [m for m in project.milestones if m.due_date and m.due_date < day and m.status != "accepted"]
    reasons = []
    if overdue:
        reasons.append(f"{overdue} việc quá hạn")
    if late_ms:
        reasons.append(f"{len(late_ms)} cột mốc quá hạn chưa nghiệm thu")
    at_risk = len(risks) - overdue
    if at_risk:
        reasons.append(f"{at_risk} việc có nguy cơ trễ")
    if overdue >= current_app.config["HEALTH_RED_OVERDUE"] or late_ms:
        level = "red"
    elif risks:
        level = "yellow"
    else:
        level = "green"
    return {"level": level, "reasons": reasons or ["Không có việc quá hạn hay có nguy cơ"],
            "overdue_count": overdue, "risk_count": len(risks), "late_milestones": len(late_ms)}


def evaluate(tasks, until=None):
    """Chạy lại luật từng ngày trên lịch sử để đo chất lượng cảnh báo.

    Việc 'trễ' = hoàn thành sau hạn, hoặc tới `until` vẫn quá hạn chưa xong.
    Cảnh báo sớm = có ít nhất một lý do (trừ OVERDUE) vào một ngày TRƯỚC hạn.
    """
    until = until or date.today()
    late, late_warned, lead_days, on_time, false_alarm = 0, 0, [], 0, 0
    rows = []
    for t in tasks:
        if not t.due_date or t.created_at.date() >= t.due_date:
            continue
        done_day = t.completed_at.date() if t.completed_at else None
        if done_day is None and t.due_date >= until:
            continue  # chưa tới hạn, chưa biết kết quả
        is_late = (done_day or until) > t.due_date
        first = None
        day = t.created_at.date()
        while day < t.due_date and (done_day is None or day < done_day):
            if any(code != "OVERDUE" for code, _ in reasons_at(t, day)):
                first = day
                break
            day += timedelta(days=1)
        if is_late:
            late += 1
            if first:
                late_warned += 1
                lead_days.append((t.due_date - first).days)
        else:
            on_time += 1
            false_alarm += first is not None
        rows.append({"task_id": t.id, "title": t.title, "late": is_late,
                     "first_warning": first.isoformat() if first else None})
    return {"late_tasks": late, "late_warned_before_due": late_warned,
            "recall": round(late_warned / late, 3) if late else None,
            "avg_lead_days": round(sum(lead_days) / len(lead_days), 1) if lead_days else None,
            "on_time_tasks": on_time, "false_alarms": false_alarm,
            "false_alarm_rate": round(false_alarm / on_time, 3) if on_time else None, "tasks": rows}
