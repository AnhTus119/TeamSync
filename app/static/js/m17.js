// JS của M17 (Thành viên 3): trang Dashboard, Sổ đóng góp + đánh giá chéo, Tổng quan không gian làm việc.
// Dùng api(), esc(), fmtDate()... từ api.js. Chart.js chỉ nạp ở trang dashboard.
(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const page = $("m17-dashboard") ? "dashboard" : $("m17-contributions") ? "contributions" : $("m17-overview") ? "overview" : null;
  if (!page) return;
  const root = $(`m17-${page}`);
  const projectId = root.dataset.projectId;
  const workspaceId = root.dataset.workspaceId;

  // ------------------------------------------------------------------ tiện ích
  const COLORS = { todo: "#cbd5e1", in_progress: "#3b82f6", review: "#f59e0b", done: "#16a34a" };
  const AVATARS = ["#2563eb", "#7c3aed", "#db2777", "#ea580c", "#0d9488", "#4f46e5", "#0891b2", "#65a30d"];
  const LEVELS = {
    green: { title: "Dự án ổn định", lamp: "green" },
    yellow: { title: "Cần theo dõi", lamp: "yellow" },
    red: { title: "Có nguy cơ cao", lamp: "red" },
  };
  const SCORE_HINT = ["", "Cần cải thiện nhiều", "Dưới kỳ vọng", "Đạt yêu cầu", "Tốt", "Xuất sắc"];
  const RULES = {
    OVERDUE: "Đã quá hạn", NEAR_DUE_NOT_STARTED: "Sắp đến hạn", STALE: "Lâu không cập nhật",
    RETURNED: "Bị trả lại nhiều", BLOCKED: "Bị chặn",
  };

  const dec = (n) => (n == null ? "—" : String(n).replace(".", ","));
  const pct = (n) => (n == null ? "—" : `${dec(n)}%`);
  const clamp = (n) => Math.max(0, Math.min(100, Number(n) || 0));
  const plainName = (s) => String(s || "").replace(/\s*\(.*?\)\s*/g, " ").trim() || "?";
  const initials = (s) => {
    const w = plainName(s).split(/\s+/);
    return ((w[0][0] || "") + (w.length > 1 ? w[w.length - 1][0] : "")).toUpperCase();
  };
  const avatar = (u, cls = "") =>
    `<span class="m17-avatar ${cls}" style="background:${AVATARS[(u.id ?? u.user_id ?? 0) % AVATARS.length]}" aria-hidden="true">${esc(initials(u.full_name))}</span>`;
  const bar = (value, cls = "") => `<div class="m17-bar thin ${cls}"><span style="width:${clamp(value)}%"></span></div>`;
  const stars = (n) => `<span class="m17-stars-static" aria-label="${n} trên 5 sao">${"★".repeat(Math.round(n))}<span class="off">${"★".repeat(5 - Math.round(n))}</span></span>`;
  const empty = (icon, text) => `<div class="m17-empty"><i class="bi bi-${icon}"></i>${text}</div>`;

  function relTime(iso) {
    if (!iso) return "—";
    const d = new Date(iso);
    const days = Math.round((new Date().setHours(0, 0, 0, 0) - new Date(d).setHours(0, 0, 0, 0)) / 864e5);
    const hm = iso.slice(11, 16);
    if (days <= 0) return `Hôm nay ${hm}`;
    if (days === 1) return `Hôm qua ${hm}`;
    if (days < 7) return `${days} ngày trước`;
    return fmtDate(iso);
  }
  function showError(message) {
    const el = $("m17-error");
    el.hidden = false;
    el.textContent = message;
  }
  function setHeader(p, myRole) {
    $("pn-title").textContent = p.name;
    $("pn-workspace").innerHTML = `<a href="/workspaces/${p.workspace_id}">${esc(p.workspace_name)}</a>`;
    $("pn-role").textContent = myRole ? `Bạn là: ${label(myRole)}` : (ME.role === "admin" ? "Quản trị viên" : "Chủ không gian làm việc");
    document.title = `${p.name} — TeamSync`;
  }
  const ok = (r) => r.status === "fulfilled";
  const g = (url) => api("GET", url);

  // ================================================================== DASHBOARD
  const charts = {};
  function drawChart(key, canvasId, config) {
    if (charts[key]) charts[key].destroy();
    const canvas = $(canvasId);
    if (typeof Chart === "undefined") {
      canvas.parentElement.innerHTML = empty("wifi-off", "Không tải được thư viện biểu đồ (Chart.js). Kiểm tra kết nối mạng.");
      return;
    }
    charts[key] = new Chart(canvas, config);
  }

  async function dashboard() {
    let stats;
    try {
      stats = await g(`/api/projects/${projectId}/stats`);
    } catch (e) {
      $("m17-hero").innerHTML = "";
      showError(e.status === 403 ? "Bạn không thuộc dự án này nên không xem được dashboard." : e.message);
      return;
    }
    setHeader(stats.project, stats.my_role);
    const [health, risks, activity, contrib] = await Promise.allSettled([
      g(`/api/projects/${projectId}/health`), g(`/api/projects/${projectId}/risks`),
      g(`/api/projects/${projectId}/activity?limit=12`), g(`/api/projects/${projectId}/contributions`),
    ]);
    const h = ok(health) ? health.value : null;
    h ? renderHero(h, stats.project) : ($("m17-hero").innerHTML = empty("exclamation-circle", "Không tải được đèn sức khỏe."));
    renderKpis(stats, h);
    renderStatus(stats);
    renderTimeline(stats.timeline);
    renderMilestones(stats.by_milestone);
    ok(contrib) ? renderWorkload(contrib.value) : ($("m17-workload-chart").parentElement.innerHTML = empty("exclamation-circle", "Không tải được khối lượng thành viên."));
    ok(risks) ? renderRisks(risks.value) : ($("m17-risks").innerHTML = empty("exclamation-circle", "Không tải được cảnh báo rủi ro."));
    ok(activity) ? renderActivity(activity.value) : ($("m17-activity").innerHTML = empty("exclamation-circle", "Không tải được hoạt động."));
  }

  function renderHero(h, p) {
    const lv = LEVELS[h.level] || LEVELS.green;
    const hero = $("m17-hero");
    hero.className = `m17-hero mb-4 ${h.level}`;
    const lamp = (c) => `<span class="m17-lamp ${c} ${h.level === c ? "on" : ""}"></span>`;
    const overview = p.is_workspace_owner || ME.role === "admin"
      ? `<a class="m17-btn" href="/workspaces/${p.workspace_id}/overview"><i class="bi bi-grid-1x2"></i>Tổng quan không gian</a>` : "";
    hero.innerHTML = `
      <div class="m17-lights" aria-hidden="true">${lamp("red")}${lamp("yellow")}${lamp("green")}</div>
      <div class="m17-hero-main">
        <div class="m17-eyebrow">Đèn sức khỏe dự án</div>
        <div class="m17-hero-title">${lv.title}</div>
        <ul class="m17-reasons">${h.reasons.map((r) => `<li>${esc(r)}</li>`).join("")}</ul>
      </div>
      <div class="m17-hero-actions">
        <a class="m17-btn" href="/projects/${projectId}/contributions"><i class="bi bi-journal-check"></i>Sổ đóng góp</a>
        ${overview}
        <a class="m17-btn primary" href="/api/projects/${projectId}/report"><i class="bi bi-download"></i>Xuất CSV</a>
      </div>`;
  }

  function renderKpis(s, h) {
    const kpi = (icon, color, value, label_, sub, barHtml = "") => `
      <div class="col-6 col-lg"><div class="m17-card m17-kpi">
        <div class="m17-kpi-top"><span class="m17-kpi-icon ${color}"><i class="bi bi-${icon}"></i></span></div>
        <div class="m17-kpi-value m17-num">${value}</div>
        <div class="m17-kpi-label">${label_}</div>${barHtml}<div class="m17-kpi-sub mt-1">${sub}</div>
      </div></div>`;
    const overdueColor = s.overdue ? "red" : "green";
    const risk = h ? h.risk_count : "—";
    $("m17-kpis").innerHTML = [
      kpi("check2-circle", "green", `${dec(s.percent_done)}<small>%</small>`, "Hoàn thành", `${s.done}/${s.total} việc`, bar(s.percent_done, "green")),
      kpi("speedometer2", "violet", `${s.points_done}<small> / ${s.points_total}</small>`, "Điểm khối lượng", `${pct(s.percent_points)} tổng điểm`, bar(s.percent_points, "violet")),
      kpi("alarm", "blue", s.on_time_rate == null ? "—" : `${dec(s.on_time_rate)}<small>%</small>`, "Đúng hạn", `${s.on_time} đúng · ${s.late} trễ · ${s.overdue} quá hạn`),
      kpi("hourglass-split", overdueColor, s.overdue, "Việc quá hạn", s.overdue ? "Chưa xong và đã qua hạn" : "Không có việc quá hạn"),
      kpi("exclamation-triangle", risk ? "yellow" : "green", risk, "Việc có nguy cơ", "Theo các luật cảnh báo"),
    ].join("");
  }

  function renderStatus(s) {
    const keys = ["todo", "in_progress", "review", "done"];
    const vals = keys.map((k) => s.by_status[k] || 0);
    $("m17-donut-total").textContent = s.total;
    $("m17-status-legend").innerHTML = keys.map((k, i) =>
      `<div><span class="m17-dot" style="background:${COLORS[k]}"></span>${label(k)}<strong class="m17-num">${vals[i]}</strong></div>`).join("");
    drawChart("status", "m17-status-chart", {
      type: "doughnut",
      data: { labels: keys.map(label), datasets: [{ data: s.total ? vals : [1], backgroundColor: s.total ? keys.map((k) => COLORS[k]) : ["#e2e8f0"], borderWidth: 2, borderColor: "#fff", hoverOffset: 4 }] },
      options: { responsive: true, maintainAspectRatio: false, cutout: "72%", plugins: { legend: { display: false }, tooltip: { enabled: !!s.total } } },
    });
  }

  function renderTimeline(t) {
    const idx = t.today ? t.labels.reduce((acc, l, i) => (l <= t.today ? i : acc), -1) : -1;
    const pill = $("m17-timeline-pill");
    if (idx >= 0 && t.done_points[idx] != null) {
      const diff = t.done_points[idx] - t.planned_points[idx];
      pill.className = `m17-pill ${diff >= 0 ? "green" : diff > -4 ? "yellow" : "red"}`;
      pill.textContent = diff >= 0 ? (diff ? `Vượt kế hoạch ${diff} điểm` : "Đúng kế hoạch") : `Chậm ${-diff} điểm so với kế hoạch`;
    } else pill.hidden = true;
    const todayLine = {
      id: "m17Today",
      afterDatasetsDraw(chart) {
        if (idx < 0) return;
        const { ctx, chartArea: a, scales: { x } } = chart;
        const px = x.getPixelForValue(idx);
        ctx.save();
        ctx.strokeStyle = "#94a3b8"; ctx.setLineDash([4, 4]); ctx.beginPath(); ctx.moveTo(px, a.top); ctx.lineTo(px, a.bottom); ctx.stroke();
        ctx.setLineDash([]); ctx.fillStyle = "#64748b"; ctx.font = "11px system-ui"; ctx.textAlign = "center"; ctx.fillText("Hôm nay", px, a.top - 4);
        ctx.restore();
      },
    };
    drawChart("timeline", "m17-timeline-chart", {
      type: "line",
      data: {
        labels: t.labels.map(fmtDate).map((s) => s.slice(0, 5)),
        datasets: [
          { label: "Kế hoạch (cộng dồn theo hạn)", data: t.planned_points, borderColor: "#94a3b8", borderDash: [6, 4], pointRadius: 0, tension: 0.25, borderWidth: 2 },
          { label: "Thực tế (đã hoàn thành)", data: t.done_points, borderColor: "#16a34a", backgroundColor: "rgba(22,163,74,.12)", fill: true, pointRadius: 0, pointHoverRadius: 4, tension: 0.25, borderWidth: 2.5, spanGaps: false },
        ],
      },
      options: {
        responsive: true, maintainAspectRatio: false, interaction: { mode: "index", intersect: false }, layout: { padding: { top: 14 } },
        plugins: { legend: { position: "bottom", labels: { usePointStyle: true, boxWidth: 8 } } },
        scales: { y: { beginAtZero: true, ticks: { precision: 0 }, grid: { color: "#eef2f7" }, title: { display: true, text: "Điểm" } }, x: { grid: { display: false }, ticks: { maxTicksLimit: 8, maxRotation: 0 } } },
      },
      plugins: [todayLine],
    });
  }

  function renderMilestones(items) {
    const late = items.filter((m) => m.is_late).length;
    $("m17-ms-pill").textContent = items.length ? (late ? `${late} cột mốc trễ` : `${items.length} cột mốc`) : "";
    $("m17-ms-pill").className = `m17-pill ${late ? "red" : ""}`;
    $("m17-milestones").innerHTML = items.length ? items.map((m) => {
      const cls = m.status === "accepted" ? "green" : m.is_late ? "red" : "";
      const tag = m.milestone_id == null ? "" : `<span class="m17-pill ${m.status === "accepted" ? "green" : m.is_late ? "red" : ""}">${m.is_late ? "Trễ hạn" : label(m.status)}</span>`;
      return `<div class="m17-ms">
        <div class="m17-ms-head"><span class="m17-ms-title">${esc(m.title)}</span><b class="m17-num">${dec(m.percent_done)}%</b></div>
        ${bar(m.percent_done, cls || "")}
        <div class="m17-ms-meta"><span>${m.done}/${m.total} việc</span><span>${m.points_done}/${m.points_total} điểm</span>
          ${m.due_date ? `<span><i class="bi bi-calendar-event"></i> ${fmtDate(m.due_date)}</span>` : ""}
          ${m.overdue ? `<span class="text-danger"><i class="bi bi-exclamation-circle"></i> ${m.overdue} quá hạn</span>` : ""}${tag}</div>
      </div>`;
    }).join("") : empty("flag", "Dự án chưa có cột mốc.");
  }

  function renderWorkload(rows) {
    if (!rows.length) { $("m17-workload-chart").parentElement.innerHTML = empty("people", "Chưa có thành viên."); return; }
    drawChart("workload", "m17-workload-chart", {
      type: "bar",
      data: {
        labels: rows.map((r) => plainName(r.full_name)),
        datasets: [
          { label: "Điểm được giao", data: rows.map((r) => r.assigned_points), backgroundColor: "#c7d2fe", borderRadius: 6 },
          { label: "Điểm đã hoàn thành", data: rows.map((r) => r.completed_points), backgroundColor: "#16a34a", borderRadius: 6 },
        ],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { position: "bottom", labels: { usePointStyle: true, boxWidth: 8 } } },
        scales: { y: { beginAtZero: true, ticks: { precision: 0 }, grid: { color: "#eef2f7" } }, x: { grid: { display: false } } },
      },
    });
  }

  let showAllRisks = false;
  function renderRisks(items) {
    const pill = $("m17-risk-pill");
    pill.textContent = `${items.length} cảnh báo`;
    pill.className = `m17-pill ${items.some((i) => i.severity === "high") ? "red" : items.length ? "yellow" : "green"}`;
    if (!items.length) { $("m17-risks").innerHTML = empty("shield-check", "Chưa phát hiện cảnh báo theo các luật hiện tại."); return; }
    const LIMIT = 5;
    const shown = showAllRisks ? items : items.slice(0, LIMIT);
    $("m17-risks").innerHTML = shown.map((r) => `
      <div class="m17-risk ${r.severity}">
        <span class="m17-risk-bar"></span>
        <div class="m17-risk-body">
          <a class="m17-risk-title" href="/tasks/${r.task_id}">${esc(r.title)}</a>
          <div class="m17-risk-meta">
            <span class="m17-status ${r.status}">${label(r.status)}</span>
            <span>${r.assignee ? `${avatar(r.assignee, "sm")} ${esc(plainName(r.assignee.full_name))}` : '<i class="bi bi-person-dash"></i> Chưa giao'}</span>
            <span><i class="bi bi-calendar-event"></i> ${r.due_date ? fmtDate(r.due_date) : "Chưa đặt hạn"}</span>
            <span>${r.points} điểm</span>
          </div>
          ${r.reasons.map((x) => `<div class="m17-reason"><span class="m17-chip ${x.code}">${esc(RULES[x.code] || x.label)}</span><span>${esc(x.detail)}</span></div>`).join("")}
        </div>
      </div>`).join("") + (items.length > LIMIT
      ? `<button type="button" class="m17-btn mt-3" id="m17-risk-toggle">${showAllRisks ? "Thu gọn" : `Xem thêm ${items.length - LIMIT} việc`}</button>` : "");
    const t = $("m17-risk-toggle");
    if (t) t.onclick = () => { showAllRisks = !showAllRisks; renderRisks(items); };
  }

  function renderActivity(items) {
    if (!items.length) { $("m17-activity").innerHTML = empty("clock-history", "Chưa có hoạt động được ghi nhận."); return; }
    const icon = (a) => a.field === "review" ? (a.old_value === "approve" ? ["done", "check2"] : ["return", "arrow-return-left"])
      : a.field === "attachment" ? ["", "paperclip"] : a.field === "status" ? [a.new_value === "review" ? "review" : a.new_value === "done" ? "done" : "", "arrow-right-short"]
      : a.field === "created" ? ["", "plus"] : ["", "pencil"];
    $("m17-activity").innerHTML = `<ul class="m17-feed">${items.map((a) => {
      const [cls, ic] = icon(a);
      return `<li><span class="m17-feed-dot ${cls}"><i class="bi bi-${ic}"></i></span>
        <div><strong>${esc(plainName(a.user.full_name))}</strong> ${esc(a.summary)}<time>${relTime(a.created_at)}</time></div></li>`;
    }).join("")}</ul>`;
  }

  // ================================================================== SỔ ĐÓNG GÓP
  const state = { score: 0, role: null, privileged: false, canReview: false };

  async function contributions() {
    let stats;
    try {
      stats = await g(`/api/projects/${projectId}/stats`);
    } catch (e) {
      $("m17-ledger").innerHTML = "";
      showError(e.status === 403 ? "Bạn không thuộc dự án này nên không xem được sổ đóng góp." : e.message);
      return;
    }
    setHeader(stats.project, stats.my_role);
    state.role = stats.my_role;
    state.privileged = ME.role === "admin" || ["manager", "supervisor"].includes(stats.my_role);
    state.canReview = ["manager", "member"].includes(stats.my_role);
    $("m17-peer-form-col").hidden = !state.canReview;
    $("m17-peer-form-col").className = `col-lg-${state.privileged ? 5 : 12}`;
    $("m17-peer-summary-col").hidden = !state.privileged;
    $("m17-eval-card").hidden = !state.privileged;
    if (!state.canReview && !state.privileged) { /* chủ workspace không có vai trò dự án: chỉ xem sổ */ }
    setupReviewForm();
    await Promise.all([loadLedger(), loadPeer(), state.privileged ? loadEvaluation() : null]);
    if (state.privileged) setupEvalForm();
  }

  async function loadLedger() {
    try {
      renderLedger(await g(`/api/projects/${projectId}/contributions`));
    } catch (e) {
      $("m17-ledger").innerHTML = `<tr><td colspan="7">${empty("exclamation-circle", esc(e.message))}</td></tr>`;
    }
  }

  function renderLedger(rows) {
    if (!rows.length) { $("m17-ledger").innerHTML = `<tr><td colspan="7">${empty("people", "Dự án chưa có quản lý/thành viên.")}</td></tr>`; return; }
    $("m17-ledger").innerHTML = rows.map((r) => {
      const peer = r.peer_review_average != null
        ? `${stars(r.peer_review_average)} <strong class="m17-num">${dec(r.peer_review_average)}</strong><div class="m17-cell-sub">${r.peer_review_count} lượt chấm</div>`
        : state.privileged ? '<span class="m17-cell-sub">Chưa có đánh giá</span>' : '<span class="m17-cell-sub"><i class="bi bi-lock"></i> Chỉ quản lý/giám sát xem</span>';
      return `<tr>
        <td><div class="m17-person">${avatar(r)}<div><strong>${esc(plainName(r.full_name))}</strong>
          <small><span class="m17-badge-role ${r.project_role}">${label(r.project_role)}</span> ${esc(r.email)}</small></div></div></td>
        <td style="min-width:150px"><strong class="m17-num">${r.completed_tasks}</strong><span class="m17-muted"> / ${r.assigned_tasks} việc</span>${bar(r.assigned_tasks ? 100 * r.completed_tasks / r.assigned_tasks : 0, "green")}</td>
        <td style="min-width:150px"><strong class="m17-num">${r.completed_points}</strong><span class="m17-muted"> / ${r.assigned_points} điểm</span>${bar(r.assigned_points ? 100 * r.completed_points / r.assigned_points : 0, "violet")}
          <div class="m17-cell-sub">${dec(r.points_share)}% điểm đã xong của dự án</div></td>
        <td><strong class="m17-num">${r.on_time_rate == null ? "—" : `${dec(r.on_time_rate)}%`}</strong>
          <div class="m17-cell-sub">${r.on_time} đúng · ${r.late} trễ · <span class="${r.overdue_open ? "text-danger" : ""}">${r.overdue_open} quá hạn</span></div></td>
        <td class="text-center"><span class="m17-num-pill ${r.returned_count >= 2 ? "warn" : ""}">${r.returned_count}</span></td>
        <td class="text-center"><span class="m17-num-pill">${r.evidence_count}</span></td>
        <td>${peer}</td></tr>`;
    }).join("");
  }

  // ---- đánh giá chéo
  function setupReviewForm() {
    const box = $("m17-stars");
    box.innerHTML = [1, 2, 3, 4, 5].map((n) => `<button type="button" role="radio" aria-checked="false" aria-label="${n} sao" data-score="${n}">★</button>`).join("");
    box.onclick = (ev) => {
      const b = ev.target.closest("button");
      if (b) setScore(Number(b.dataset.score));
    };
    $("m17-peer-form").onsubmit = submitReview;
  }
  function setScore(n) {
    state.score = n;
    document.querySelectorAll("#m17-stars button").forEach((b) => {
      const on = Number(b.dataset.score) <= n;
      b.classList.toggle("on", on);
      b.setAttribute("aria-checked", String(Number(b.dataset.score) === n));
    });
    $("m17-score-hint").textContent = n ? `${n}/5 — ${SCORE_HINT[n]}` : "Chọn số sao";
  }

  async function loadPeer() {
    const jobs = [];
    if (state.canReview) jobs.push(g(`/api/projects/${projectId}/peer-reviews?mine=1`).then(renderMine).catch((e) => { $("m17-mine").innerHTML = empty("exclamation-circle", esc(e.message)); }));
    if (state.privileged) jobs.push(g(`/api/projects/${projectId}/peer-reviews`).then(renderPeerSummary).catch((e) => { $("m17-peer-summary").innerHTML = empty("exclamation-circle", esc(e.message)); }));
    await Promise.all(jobs);
  }

  function renderMine({ reviews, pending }) {
    const sel = $("m17-reviewee");
    const submit = $("m17-submit-review");
    sel.innerHTML = pending.length
      ? '<option value="">Chọn đồng đội…</option>' + pending.map((u) => `<option value="${u.id}">${esc(plainName(u.full_name))} — ${label(u.project_role)}</option>`).join("")
      : '<option value="">Bạn đã đánh giá tất cả đồng đội</option>';
    sel.disabled = submit.disabled = !pending.length;
    $("m17-mine").innerHTML = reviews.length ? reviews.map((r) => `
      <div class="m17-mine">${avatar(r.reviewee || { id: r.reviewee_id, full_name: "?" }, "sm")}
        <div><strong>${esc(plainName(r.reviewee?.full_name))}</strong> ${stars(r.score)} <span class="m17-cell-sub">${fmtDate(r.created_at)}</span>
        ${r.comment ? `<div class="m17-cell-sub">${esc(r.comment)}</div>` : ""}</div></div>`).join("")
      : '<div class="m17-cell-sub">Bạn chưa gửi đánh giá nào.</div>';
  }

  function renderPeerSummary(items) {
    $("m17-peer-summary").innerHTML = items.length ? `<div class="row g-3">${items.map((it) => {
      const max = Math.max(1, ...Object.values(it.distribution));
      return `<div class="col-md-6 col-xl-4"><div class="m17-review-card">
        <div class="m17-person">${avatar(it.reviewee)}<div><strong>${esc(plainName(it.reviewee.full_name))}</strong><small>${label(it.project_role)}</small></div></div>
        ${it.count ? `<div class="d-flex align-items-end gap-2 mt-3"><span class="m17-avg m17-num">${dec(it.average)}</span><div>${stars(it.average)}<div class="m17-cell-sub">${it.count} lượt chấm ẩn danh</div></div></div>
        <div class="m17-dist">${[5, 4, 3, 2, 1].map((s) => `<span>${s}</span><div class="m17-bar thin yellow"><span style="width:${100 * it.distribution[s] / max}%"></span></div><span class="m17-num">${it.distribution[s]}</span>`).join("")}</div>
        ${it.comments.slice(0, 3).map((c) => `<div class="m17-quote"><b>${c.score}★</b>${esc(c.comment)}</div>`).join("")}
        ${it.comments.length > 3 ? `<div class="m17-cell-sub mt-1">+${it.comments.length - 3} nhận xét khác</div>` : ""}`
        : '<div class="m17-cell-sub mt-3">Chưa có đánh giá nào.</div>'}
      </div></div>`;
    }).join("")}</div>` : empty("chat-square", "Chưa có thành viên để đánh giá.");
  }

  async function submitReview(ev) {
    ev.preventDefault();
    const reviewee = Number($("m17-reviewee").value);
    if (!reviewee) return showAlert("Hãy chọn người được đánh giá.");
    if (!state.score) return showAlert("Hãy chọn số sao từ 1 đến 5.");
    const btn = $("m17-submit-review");
    btn.disabled = true;
    try {
      await api("POST", `/api/projects/${projectId}/peer-reviews`, { reviewee_id: reviewee, score: state.score, comment: $("m17-comment").value });
      showAlert("Đã gửi đánh giá. Cảm ơn bạn!", "success");
      $("m17-comment").value = "";
      setScore(0);
      await Promise.all([loadPeer(), loadLedger()]);
    } catch (e) {
      showAlert(e.message);
    } finally {
      btn.disabled = false;
    }
  }

  // ---- đánh giá luật cảnh báo
  function setupEvalForm() {
    $("m17-eval-form").onsubmit = (ev) => { ev.preventDefault(); loadEvaluation(true); };
  }
  async function loadEvaluation(custom = false) {
    const box = $("m17-eval");
    box.innerHTML = '<div class="m17-skel h-md"></div>';
    const qs = custom ? `?days_before_due=${$("m17-th-due").value}&days_no_update=${$("m17-th-stale").value}&return_count=${$("m17-th-ret").value}` : "";
    try {
      const r = await g(`/api/projects/${projectId}/risk-evaluation${qs}`);
      $("m17-th-due").value = r.thresholds.days_before_due;
      $("m17-th-stale").value = r.thresholds.days_no_update;
      $("m17-th-ret").value = r.thresholds.return_count;
      renderEvaluation(r);
    } catch (e) {
      box.innerHTML = empty("exclamation-circle", esc(e.message));
    }
  }
  function renderEvaluation(r) {
    if (!r.evaluated) { $("m17-eval").innerHTML = empty("hourglass", "Chưa có việc nào đủ điều kiện đánh giá (cần có hạn và đã xong hoặc đã quá hạn)."); return; }
    const metric = (title, value, sub, color) => `<div class="col-md-4"><div class="m17-metric"><span class="m17-eyebrow">${title}</span><b class="m17-num" style="color:${color}">${value}</b><small>${sub}</small></div></div>`;
    $("m17-eval").innerHTML = `
      <div class="row g-3 mb-3">
        ${metric("Recall — phát hiện việc trễ", r.recall == null ? "—" : `${dec(r.recall)}%`, `${r.warned_late}/${r.late_tasks} việc trễ được cảnh báo trước hạn`, "#2563eb")}
        ${metric("Cảnh báo sớm trung bình", r.avg_lead_days == null ? "—" : `${dec(r.avg_lead_days)} ngày`, "tính từ cảnh báo đầu tiên tới hạn chót", "#16a34a")}
        ${metric("Cảnh báo thừa", r.false_alarm_rate == null ? "—" : `${dec(r.false_alarm_rate)}%`, `${r.false_alarm_tasks}/${r.on_time_tasks} việc đúng hạn từng bị cảnh báo`, "#d97706")}
      </div>
      <div class="m17-scroll"><table class="m17-table"><thead><tr><th>Luật</th><th>Việc trễ được phát hiện</th><th>Cảnh báo thừa (việc đúng hạn)</th></tr></thead><tbody>
      ${Object.entries(r.per_rule).map(([c, v]) => `<tr><td><span class="m17-chip ${c}">${esc(RULES[c])}</span></td><td class="m17-num">${v.late_hit}</td><td class="m17-num">${v.on_time_hit}</td></tr>`).join("")}
      </tbody></table></div>
      <details class="mt-3"><summary class="small fw-semibold" style="cursor:pointer">Chi tiết ${r.details.length} việc đã đánh giá</summary>
        <div class="m17-scroll mt-2"><table class="m17-table"><thead><tr><th>Việc</th><th>Kết quả</th><th>Hạn</th><th>Cảnh báo đầu tiên</th><th>Sớm (ngày)</th></tr></thead><tbody>
        ${r.details.map((d) => `<tr><td>${esc(d.title)}</td><td><span class="m17-pill ${d.outcome === "late" ? "red" : "green"}">${d.outcome === "late" ? "Trễ" : "Đúng hạn"}</span></td>
          <td>${fmtDate(d.due_date)}</td><td>${d.warned ? `${fmtDate(d.first_warning)} <span class="m17-cell-sub">${d.first_reasons.map((c) => esc(RULES[c])).join(", ")}</span>` : '<span class="m17-cell-sub">Không cảnh báo</span>'}</td><td class="m17-num">${d.lead_days ?? "—"}</td></tr>`).join("")}
        </tbody></table></div></details>`;
  }

  // ================================================================== TỔNG QUAN WORKSPACE
  async function overview() {
    try {
      const o = await g(`/api/workspaces/${workspaceId}/overview`);
      $("m17-ws-title").textContent = `Tổng quan: ${o.workspace.name}`;
      document.title = `Tổng quan ${o.workspace.name} — TeamSync`;
      const t = o.totals;
      const kpi = (icon, color, value, text) => `<div class="col-6 col-lg-3"><div class="m17-card m17-kpi"><span class="m17-kpi-icon ${color}"><i class="bi bi-${icon}"></i></span>
        <div class="m17-kpi-value m17-num">${value}</div><div class="m17-kpi-label">${text}</div></div></div>`;
      $("m17-ov-totals").innerHTML = [
        kpi("folder2-open", "blue", o.project_count, "Dự án"),
        kpi("check2-circle", "green", `${dec(t.percent_done)}<small>%</small>`, `Hoàn thành (${t.done}/${t.total} việc)`),
        kpi("hourglass-split", t.overdue ? "red" : "green", t.overdue, "Việc quá hạn"),
        `<div class="col-6 col-lg-3"><div class="m17-card m17-kpi"><span class="m17-kpi-icon yellow"><i class="bi bi-traffic-light"></i></span>
          <div class="m17-kpi-value m17-num"><span class="text-danger">${t.red}</span><small> / </small><span style="color:#d97706">${t.yellow}</span><small> / </small><span class="text-success">${t.green}</span></div>
          <div class="m17-kpi-label">Đỏ / Vàng / Xanh</div></div></div>`,
      ].join("");
      $("m17-ov-projects").innerHTML = o.projects.length ? o.projects.map((p) => {
        const s = p.stats, h = p.health;
        return `<div class="col-md-6 col-xl-4"><a class="m17-card m17-proj" href="/projects/${p.project.id}/dashboard">
          <div class="m17-proj-head"><span class="m17-mini-light ${h.level}"></span><div class="flex-grow-1" style="min-width:0">
            <strong class="d-block text-truncate">${esc(p.project.name)}</strong>
            <span class="m17-cell-sub">${p.manager ? `Quản lý: ${esc(plainName(p.manager))} · ` : ""}${p.member_count} người${p.supervisors.length ? ` · Giám sát: ${esc(plainName(p.supervisors[0]))}` : ""}</span></div>
            <span class="m17-pill ${h.level}">${LEVELS[h.level].title}</span></div>
          <div><div class="d-flex justify-content-between small mb-1"><span>Tiến độ</span><b class="m17-num">${dec(s.percent_done)}%</b></div>${bar(s.percent_done, h.level === "red" ? "red" : h.level === "yellow" ? "yellow" : "green")}</div>
          <div class="m17-proj-stats"><div><b class="m17-num">${s.done}/${s.total}</b><span>Việc xong</span></div>
            <div><b class="m17-num ${s.overdue ? "text-danger" : ""}">${s.overdue}</b><span>Quá hạn</span></div><div><b class="m17-num">${h.risk_count}</b><span>Nguy cơ</span></div></div>
          <div class="m17-cell-sub"><i class="bi bi-info-circle"></i> ${esc(h.reasons[0])}${p.project.due_date ? ` · Hạn ${fmtDate(p.project.due_date)}` : ""}</div>
        </a></div>`;
      }).join("") : `<div class="col-12">${empty("folder2", "Không gian làm việc chưa có dự án.")}</div>`;
    } catch (e) {
      $("m17-ov-totals").innerHTML = "";
      showError(e.status === 403 ? "Chỉ chủ không gian làm việc hoặc quản trị viên xem được trang tổng quan." : e.message);
    }
  }

  ({ dashboard, contributions, overview })[page]();
})();
