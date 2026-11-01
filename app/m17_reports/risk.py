"""Luật cảnh báo rủi ro, đèn sức khỏe và đánh giá luật trên lịch sử. Chủ sở hữu: Thành viên 3.

Thiết kế:
  - Mọi hàm ở đây là hàm thuần (không truy vấn DB). Dữ liệu vào là `ProjectData` do services.load_project_data() dựng.
  - Cùng MỘT bộ luật (`risk_reasons`) dùng cho cả API hôm nay lẫn đánh giá trên lịch sử:
        hôm nay  → state_now()  : đọc thẳng các cột hiện tại của Task
        quá khứ  → state_at()   : dựng lại từ TaskHistory tại cuối ngày được hỏi
  - Chỉ ĐỌC dữ liệu M06, không ghi.
"""
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

# Mã cảnh báo (khớp docs/M17.md)
OVERDUE = "OVERDUE"
NEAR_DUE = "NEAR_DUE_NOT_STARTED"
STALE = "STALE"
RETURNED = "RETURNED"
BLOCKED = "BLOCKED"
RULE_CODES = (OVERDUE, NEAR_DUE, STALE, RETURNED, BLOCKED)
RULE_LABELS = {
    OVERDUE: "Đã quá hạn",
    NEAR_DUE: "Sắp đến hạn mà chưa bắt đầu",
    STALE: "Lâu không cập nhật",
    RETURNED: "Bị trả lại nhiều lần",
    BLOCKED: "Bị chặn bởi việc trễ hạn",
}
STATUS_LABELS = {"todo": "Cần làm", "in_progress": "Đang làm", "review": "Chờ duyệt", "done": "Hoàn thành"}

MAX_EVAL_DAYS = 400  # chặn vòng lặp khi dữ liệu có hạn quá xa


@dataclass(frozen=True)
class Thresholds:
    days_before_due: int = 2   # RISK_DAYS_BEFORE_DUE
    days_no_update: int = 3    # RISK_DAYS_NO_UPDATE
    return_count: int = 2      # RISK_RETURN_COUNT
    health_red_overdue: int = 2  # HEALTH_RED_OVERDUE

    @classmethod
    def from_config(cls, cfg):
        return cls(int(cfg.get("RISK_DAYS_BEFORE_DUE", 2)), int(cfg.get("RISK_DAYS_NO_UPDATE", 3)),
                   int(cfg.get("RISK_RETURN_COUNT", 2)), int(cfg.get("HEALTH_RED_OVERDUE", 2)))

    def to_dict(self):
        return {"days_before_due": self.days_before_due, "days_no_update": self.days_no_update,
                "return_count": self.return_count, "health_red_overdue": self.health_red_overdue}


@dataclass(frozen=True)
class TaskState:
    """Trạng thái của một việc tại một thời điểm."""
    task_id: int
    title: str
    status: str
    due_date: date | None
    assignee_id: int | None
    last_update: datetime
    return_count: int
    completed_at: datetime | None


@dataclass
class ProjectData:
    """Dữ liệu một dự án đã nạp sẵn (tránh truy vấn lặp)."""
    project: object
    tasks: list
    history: dict       # task_id -> [TaskHistory] sắp theo (created_at, id)
    deps: dict          # task_id -> [depends_on_task_id]
    milestones: list


# ----------------------------------------------------------------------------- tiện ích ngày
def end_of_day(day):
    return datetime.combine(day, time.max)


def _parse_date(value):
    try:
        return date.fromisoformat(value) if value else None
    except (TypeError, ValueError):
        return None


def _parse_int(value):
    try:
        return int(value) if value not in (None, "", "None") else None
    except (TypeError, ValueError):
        return None


def _is_return(row):
    return row.field == "review" and row.old_value == "return"


# ----------------------------------------------------------------------------- dựng trạng thái
def state_now(task, history):
    """Trạng thái hiện tại: đọc các cột hiện tại của Task (đáng tin hơn dựng lại khi dữ liệu thiếu lịch sử)."""
    last = max([task.updated_at or task.created_at] + [h.created_at for h in history])
    return TaskState(task.id, task.title, task.status, task.due_date, task.assignee_id, last,
                     sum(1 for h in history if _is_return(h)), task.completed_at)


def state_at(task, history, day):
    """Trạng thái của việc vào CUỐI NGÀY `day`, dựng lại từ TaskHistory. Việc chưa được tạo → None.

    status      : giá trị mới của dòng `status` gần nhất (mặc định todo)
    due_date    : nếu sau đó hạn còn bị đổi → lấy old_value của lần đổi sớm nhất sau mốc; không thì giá trị hiện tại
    assignee_id : tương tự due_date
    last_update : thời điểm dòng lịch sử gần nhất (hoặc lúc tạo việc)
    """
    cutoff = end_of_day(day)
    if task.created_at > cutoff:
        return None
    before = [h for h in history if h.created_at <= cutoff]
    after = [h for h in history if h.created_at > cutoff]
    status, completed = "todo", None
    for h in before:
        if h.field == "status" and h.new_value in STATUS_LABELS:
            status = h.new_value
            completed = h.created_at if status == "done" else None
    due, assignee = task.due_date, task.assignee_id
    for h in after:  # lần đổi sớm nhất sau mốc cho biết giá trị tại mốc
        if h.field == "due_date":
            due = _parse_date(h.old_value)
            break
    for h in after:
        if h.field == "assignee_id":
            assignee = _parse_int(h.old_value)
            break
    last = max([task.created_at] + [h.created_at for h in before])
    return TaskState(task.id, task.title, status, due, assignee, last,
                     sum(1 for h in before if _is_return(h)), completed)


# ----------------------------------------------------------------------------- luật cảnh báo
def risk_reasons(state, dep_states, today, th):
    """Danh sách lý do cảnh báo của một việc tại ngày `today`. Việc đã done → không cảnh báo.

    dep_states: các TaskState của việc mà việc này phụ thuộc vào (cùng thời điểm).
    Mỗi lý do: {"code", "label", "detail"}.
    """
    if state is None or state.status == "done":
        return []
    out = []

    def add(code, detail):
        out.append({"code": code, "label": RULE_LABELS[code], "detail": detail})

    if state.due_date and state.due_date < today:
        add(OVERDUE, f"Quá hạn {(today - state.due_date).days} ngày (hạn {state.due_date:%d/%m/%Y}), chưa hoàn thành")
    if state.status == "todo" and state.due_date and 0 <= (state.due_date - today).days <= th.days_before_due:
        left = (state.due_date - today).days
        add(NEAR_DUE, "Hạn là hôm nay nhưng vẫn ở trạng thái Cần làm" if left == 0
            else f"Còn {left} ngày tới hạn nhưng vẫn ở trạng thái Cần làm")
    if state.status == "in_progress":
        idle = (today - state.last_update.date()).days
        if idle > th.days_no_update:
            add(STALE, f"{idle} ngày không có cập nhật (ngưỡng {th.days_no_update} ngày)")
    if state.return_count >= th.return_count:
        add(RETURNED, f"Bị trả lại {state.return_count} lần (ngưỡng {th.return_count} lần)")
    late = [d for d in dep_states if d and d.status != "done" and d.due_date and d.due_date < today]
    if late:
        add(BLOCKED, "; ".join(f"Phụ thuộc vào “{d.title}” đã quá hạn {(today - d.due_date).days} ngày mà chưa xong"
                               for d in late))
    return out


def severity(reasons):
    """high: đã quá hạn hoặc ≥ 2 lý do; medium: còn lại."""
    return "high" if any(r["code"] == OVERDUE for r in reasons) or len(reasons) >= 2 else "medium"


def current_states(data):
    return {t.id: state_now(t, data.history.get(t.id, [])) for t in data.tasks}


def states_at(data, day):
    return {t.id: state_at(t, data.history.get(t.id, []), day) for t in data.tasks}


def project_risks(data, today, th, states=None):
    """Danh sách việc có nguy cơ (kèm lý do), việc nặng nhất đứng đầu. `states` mặc định = trạng thái hiện tại."""
    states = states if states is not None else current_states(data)
    by_id = {t.id: t for t in data.tasks}
    items = []
    for t in data.tasks:
        st = states[t.id]
        reasons = risk_reasons(st, [states.get(d) for d in data.deps.get(t.id, [])], today, th)
        if not reasons:
            continue
        items.append({"task_id": t.id, "title": t.title, "status": st.status,
                      "due_date": st.due_date.isoformat() if st.due_date else None,
                      "assignee": t.assignee.brief() if t.assignee else None,
                      "milestone_id": t.milestone_id, "points": t.points,
                      "severity": severity(reasons), "reasons": reasons})
    items.sort(key=lambda x: (x["severity"] != "high", -len(x["reasons"]), x["due_date"] or "9999-12-31", x["task_id"]))
    return items


# ----------------------------------------------------------------------------- đèn sức khỏe
def late_milestones(data, today):
    """Cột mốc đã quá hạn mà chưa được nghiệm thu."""
    out = []
    for m in data.milestones:
        if m.due_date and m.due_date < today and m.status != "accepted":
            out.append({"id": m.id, "title": m.title, "due_date": m.due_date.isoformat(), "status": m.status,
                        "days_late": (today - m.due_date).days})
    return out


def project_health(data, today, th, risks=None):
    """Đèn sức khỏe: đỏ khi việc quá hạn ≥ ngưỡng hoặc có cột mốc quá hạn chưa nghiệm thu;
    vàng khi có việc quá hạn hoặc có việc nguy cơ; còn lại xanh."""
    risks = risks if risks is not None else project_risks(data, today, th)
    overdue = sum(1 for r in risks if any(x["code"] == OVERDUE for x in r["reasons"]))
    lates = late_milestones(data, today)
    reasons = []
    if overdue >= th.health_red_overdue:
        level = "red"
        reasons.append(f"{overdue} việc đã quá hạn (ngưỡng đỏ: {th.health_red_overdue} việc)")
    elif overdue:
        level = "yellow"
    elif risks:
        level = "yellow"
    else:
        level = "green"
    if lates:
        level = "red"
        reasons += [f"Cột mốc “{m['title']}” quá hạn {m['days_late']} ngày mà chưa được nghiệm thu" for m in lates]
    if level != "red" and overdue:
        reasons.append(f"{overdue} việc đã quá hạn")
    other = len(risks) - overdue
    if other > 0:
        reasons.append(f"{other} việc có nguy cơ trễ hạn")
    if not reasons:
        reasons.append("Mọi việc đang đúng tiến độ, không có cảnh báo")
    return {"level": level, "reasons": reasons, "overdue_count": overdue, "risk_count": len(risks),
            "late_milestones": len(lates), "late_milestone_items": lates}


# ----------------------------------------------------------------------------- đánh giá luật trên lịch sử
def _final_outcome(task, today):
    """('late' | 'on_time' | None, hạn cuối) — None nếu chưa thể kết luận (chưa xong và chưa tới hạn / không có hạn)."""
    due = task.due_date
    if due is None:
        return None, None
    if task.status == "done" and task.completed_at:
        return ("late" if task.completed_at.date() > due else "on_time"), due
    if task.status != "done" and due < today:
        return "late", due
    return None, due


def evaluate(data, today, th):
    """Chạy lại luật từng ngày, từ lúc tạo việc tới TRƯỚC hạn, trên các việc đã kết luận được đúng/trễ.

    Việc trễ  = xong sau hạn hoặc vẫn quá hạn chưa xong.   Việc đúng hạn = xong trước hoặc đúng hạn.
    recall            = việc trễ được cảnh báo trước hạn / tổng việc trễ
    avg_lead_days     = số ngày cảnh báo sớm trung bình (hạn − ngày cảnh báo đầu tiên) của các việc trễ được cảnh báo
    false_alarm_rate  = việc đúng hạn từng bị cảnh báo / tổng việc đúng hạn
    Trả về số đếm thô (để cộng gộp nhiều dự án) + chỉ số tính sẵn + chi tiết từng việc.
    """
    tasks = []
    for t in data.tasks:
        outcome, due = _final_outcome(t, today)
        if outcome:
            tasks.append((t, outcome, due))
    first_day = min((t.created_at.date() for t, _, _ in tasks), default=None)
    last_day = max((min(due - timedelta(days=1), today) for _, _, due in tasks), default=None)
    by_day = {}
    if first_day and last_day:
        span = min((last_day - first_day).days, MAX_EVAL_DAYS)
        for i in range(span + 1):
            day = first_day + timedelta(days=i)
            by_day[day] = states_at(data, day)

    per_rule = {c: {"late_hit": 0, "on_time_hit": 0} for c in RULE_CODES}
    details, leads = [], []
    late_n = on_time_n = warned_late = false_alarm = 0
    for t, outcome, due in tasks:
        start = t.created_at.date()
        first_warn, codes = None, set()
        d = start
        while d <= min(due - timedelta(days=1), today) and d in by_day:
            states = by_day[d]
            st = states.get(t.id)
            reasons = risk_reasons(st, [states.get(x) for x in data.deps.get(t.id, [])], d, th)
            if reasons:
                if first_warn is None:
                    first_warn = (d, reasons)
                codes.update(r["code"] for r in reasons)
            d += timedelta(days=1)
        warned = first_warn is not None
        lead = (due - first_warn[0]).days if warned else None
        if outcome == "late":
            late_n += 1
            warned_late += warned
            if warned:
                leads.append(lead)
            for c in codes:
                per_rule[c]["late_hit"] += 1
        else:
            on_time_n += 1
            false_alarm += warned
            for c in codes:
                per_rule[c]["on_time_hit"] += 1
        details.append({"task_id": t.id, "title": t.title, "outcome": outcome, "due_date": due.isoformat(),
                        "warned": warned, "first_warning": first_warn[0].isoformat() if warned else None,
                        "lead_days": lead, "codes": sorted(codes),
                        "first_reasons": [r["code"] for r in first_warn[1]] if warned else []})
    return {"thresholds": th.to_dict(), "evaluated": len(tasks), "late_tasks": late_n, "on_time_tasks": on_time_n,
            "warned_late": warned_late, "lead_days_sum": sum(leads), "false_alarm_tasks": false_alarm,
            "per_rule": per_rule, "details": details, **evaluation_metrics(late_n, warned_late, sum(leads), len(leads),
                                                                           on_time_n, false_alarm)}


def evaluation_metrics(late_n, warned_late, lead_sum, lead_n, on_time_n, false_alarm):
    pct = lambda a, b: round(100 * a / b, 1) if b else None  # noqa: E731
    return {"recall": pct(warned_late, late_n), "avg_lead_days": round(lead_sum / lead_n, 1) if lead_n else None,
            "false_alarm_rate": pct(false_alarm, on_time_n)}


def merge_evaluations(results):
    """Cộng gộp kết quả evaluate() của nhiều dự án (dùng cho scripts/evaluate_risks.py)."""
    keys = ("evaluated", "late_tasks", "on_time_tasks", "warned_late", "lead_days_sum", "false_alarm_tasks")
    total = {k: sum(r[k] for r in results) for k in keys}
    total["per_rule"] = {c: {k: sum(r["per_rule"][c][k] for r in results) for k in ("late_hit", "on_time_hit")}
                         for c in RULE_CODES}
    lead_n = sum(1 for r in results for d in r["details"] if d["lead_days"] is not None)
    total.update(evaluation_metrics(total["late_tasks"], total["warned_late"], total["lead_days_sum"], lead_n,
                                    total["on_time_tasks"], total["false_alarm_tasks"]))
    return total
