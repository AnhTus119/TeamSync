// JS của M17 (Thành viên 3): dashboard, sổ đóng góp, đánh giá chéo.
const $ = (id) => document.getElementById(id);
const HEALTH = { green: "Dự án đang ổn", yellow: "Cần chú ý", red: "Có nguy cơ trễ" };
const pct = (x) => (x === null || x === undefined ? "—" : `${Math.round(x * 100)}%`);

// ---------- Dashboard ----------
if ($("dashboard-page")) {
  const pid = $("dashboard-page").dataset.projectId;
  (async () => {
    await loadProjectHeader(pid);
    const [h, s, risks, contrib, act] = await Promise.all(["health", "stats", "risks", "contributions", "activity?limit=15"]
      .map((x) => api("GET", `/api/projects/${pid}/${x}`)));
    $("h-light").className = `m17-light ${h.level}`;
    $("h-title").textContent = HEALTH[h.level];
    $("h-reasons").textContent = h.reasons.join(" · ");
    const kpi = (v, t) => `<div class="col-6 col-md-3"><div class="card p-3"><div class="h4 mb-0">${v}</div><div class="small text-muted">${t}</div></div></div>`;
    $("kpis").innerHTML = kpi(`${s.percent_points}%`, `Hoàn thành theo điểm (${s.points_done}/${s.points_total})`)
      + kpi(`${s.by_status.done}/${s.total}`, "Việc hoàn thành") + kpi(s.overdue, "Việc quá hạn") + kpi(pct(s.on_time_rate), "Tỷ lệ đúng hạn");

    if (window.Chart) {
      new Chart($("chart-status"), { type: "doughnut", data: { labels: ["Cần làm", "Đang làm", "Chờ duyệt", "Hoàn thành"],
        datasets: [{ data: ["todo", "in_progress", "review", "done"].map((k) => s.by_status[k]),
          backgroundColor: ["#adb5bd", "#0d6efd", "#e0a800", "#2e9d5b"] }] }, options: { plugins: { legend: { position: "bottom" } } } });
      new Chart($("chart-points"), { type: "bar", data: { labels: contrib.map((c) => c.user.full_name),
        datasets: [{ label: "Đã hoàn thành", data: contrib.map((c) => c.points_done), backgroundColor: "#2e9d5b" },
          { label: "Còn lại", data: contrib.map((c) => c.assigned_points - c.points_done), backgroundColor: "#ced4da" }] },
        options: { indexAxis: "y", scales: { x: { stacked: true, beginAtZero: true }, y: { stacked: true } }, plugins: { legend: { position: "bottom" } } } });
    }
    $("risks").innerHTML = risks.map((r) => `<div class="border-bottom py-2">
      <a href="/tasks/${r.task_id}" class="fw-semibold">${esc(r.title)}</a>
      <span class="small text-muted">· ${esc(r.assignee ? r.assignee.full_name : "Chưa giao")} · hạn ${fmtDate(r.due_date)}</span>
      <ul class="small mb-0">${r.reasons.map((x) => `<li><b>${esc(x.label)}:</b> ${esc(x.detail)}</li>`).join("")}</ul></div>`).join("")
      || '<div class="small text-muted">Không có việc nào có nguy cơ.</div>';
    const FIELD = { created: "tạo", status: "đổi trạng thái", review: "duyệt/trả lại", attachment: "nộp minh chứng",
      assignee_id: "đổi người làm", due_date: "đổi hạn", points: "đổi điểm", dependency: "đổi phụ thuộc" };
    $("activity").innerHTML = act.map((a) => `<li class="mb-2"><span class="text-muted">${fmtTime(a.created_at)}</span><br>
      <b>${esc(a.user.full_name)}</b> ${FIELD[a.field] || a.field}${a.field === "status" ? ` → ${label(a.new_value)}` : ""}
      · <a href="/tasks/${a.task_id}">${esc(a.task_title)}</a></li>`).join("") || '<li class="text-muted">Chưa có hoạt động</li>';
  })().catch((err) => showAlert(err.message));
}

// ---------- Sổ đóng góp + đánh giá chéo ----------
if ($("contrib-page")) {
  const pid = $("contrib-page").dataset.projectId;
  (async () => {
    const p = await loadProjectHeader(pid);
    const canSeeReviews = ["manager", "supervisor"].includes(p.my_role) || ME.role === "admin";
    const rows = await api("GET", `/api/projects/${pid}/contributions`);
    const cols = [["Thành viên", (r) => `${esc(r.user.full_name)}${r.project_role === "manager" ? ' <span class="badge text-bg-primary">QL</span>' : ""}`],
      ["Điểm xong / giao", (r) => `${r.points_done} / ${r.assigned_points}`], ["Việc xong / giao", (r) => `${r.done} / ${r.assigned}`],
      ["Đúng hạn", (r) => pct(r.on_time_rate)], ["Trễ", (r) => r.late], ["Quá hạn chưa xong", (r) => r.overdue_open],
      ["Bị trả lại", (r) => r.returned], ["Minh chứng", (r) => r.evidence]];
    if (canSeeReviews) cols.push(["Đánh giá chéo", (r) => (r.peer_score === null ? "—" : `${r.peer_score} (${r.peer_count})`)]);
    $("ledger-head").innerHTML = `<tr>${cols.map(([h]) => `<th>${h}</th>`).join("")}</tr>`;
    $("ledger-body").innerHTML = rows.map((r) => `<tr>${cols.map(([, f]) => `<td>${f(r)}</td>`).join("")}</tr>`).join("");

    const canReview = ["manager", "member"].includes(p.my_role);
    $("review-box").classList.toggle("d-none", !canReview);
    if (canReview) {
      const mine = await api("GET", `/api/projects/${pid}/peer-reviews`);
      const done = new Set((Array.isArray(mine) ? mine : []).filter((x) => x.reviewee_id).map((x) => x.reviewee_id));
      const others = rows.filter((r) => r.user.id !== ME.id && !done.has(r.user.id));
      $("reviewee").innerHTML = others.map((r) => `<option value="${r.user.id}">${esc(r.user.full_name)}</option>`).join("");
      $("my-reviews").textContent = others.length ? `Bạn đã đánh giá ${done.size}/${rows.length - 1} người.` : "Bạn đã đánh giá tất cả thành viên.";
      $("review-form").querySelector("button").disabled = !others.length;
    }
    if (canSeeReviews) {
      $("eval-box").classList.remove("d-none");
      const ev = await api("GET", `/api/projects/${pid}/risk-evaluation`);
      $("eval").innerHTML = `<p class="mb-1">Chạy lại luật cảnh báo từng ngày trên lịch sử của dự án:</p><ul class="mb-0">
        <li>Việc trễ hạn: <b>${ev.late_tasks}</b>, được cảnh báo trước hạn: <b>${ev.late_warned_before_due}</b> (${pct(ev.recall)})</li>
        <li>Cảnh báo sớm trung bình: <b>${ev.avg_lead_days ?? "—"}</b> ngày</li>
        <li>Việc đúng hạn: <b>${ev.on_time_tasks}</b>, bị cảnh báo thừa: <b>${ev.false_alarms}</b> (${pct(ev.false_alarm_rate)})</li></ul>`;
    }
  })().catch((err) => showAlert(err.message));

  $("review-form").onsubmit = (e) => {
    e.preventDefault();
    const b = formData(e.target);
    handle(api("POST", `/api/projects/${pid}/peer-reviews`, { reviewee_id: Number(b.reviewee_id), score: Number(b.score), comment: b.comment })
      .then(() => { showAlert("Đã gửi đánh giá", "success"); setTimeout(() => location.reload(), 600); }));
  };
}
