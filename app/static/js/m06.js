// JS của M06 (Thành viên 2): danh sách dự án, Kanban, cột mốc, chi tiết việc.
const $ = (id) => document.getElementById(id);
const today = new Date().toISOString().slice(0, 10);
const isOverdue = (t) => t.due_date && t.due_date < today && t.status !== "done";
const PRIORITY_BADGE = { low: "secondary", medium: "info", high: "danger" };
const MS_BADGE = { open: "secondary", pending_review: "warning", accepted: "success", changes_requested: "danger" };

// ---------- Dự án của tôi ----------
if ($("project-list")) handle(api("GET", "/api/projects").then((list) => {
  $("project-list").innerHTML = list.map((p) => `<div class="col-md-4"><a class="card p-3 h-100 text-decoration-none text-body" href="/projects/${p.id}">
    <div class="small text-muted">${esc(p.workspace_name)}</div><div class="fw-semibold">${esc(p.name)}</div>
    <div class="small text-muted mb-2">${esc(p.description || "")}</div>
    <div class="small mt-auto">${p.my_role ? label(p.my_role) : "Quản trị viên"} · Hạn ${fmtDate(p.due_date)}</div></a></div>`).join("")
    || '<p class="text-muted">Bạn chưa tham gia dự án nào. Vào <a href="/workspaces">Không gian làm việc</a> để tạo dự án.</p>';
}));

// ---------- Kanban ----------
if ($("board-page")) {
  const pid = $("board-page").dataset.projectId;
  const filter = $("task-filter");

  function card(t) {
    return `<div class="card m06-card p-2 mb-2" onclick="location.href='/tasks/${t.id}'">
      <div class="small fw-semibold">${esc(t.title)}</div>
      <div class="d-flex flex-wrap gap-1 mt-1">
        <span class="badge text-bg-light border">${t.points} điểm</span>
        <span class="badge text-bg-${PRIORITY_BADGE[t.priority]}">${label(t.priority)}</span>
        ${t.blocked ? '<span class="badge text-bg-dark">Bị chặn</span>' : ""}
      </div>
      <div class="small mt-1 ${isOverdue(t) ? "text-danger fw-semibold" : "text-muted"}">
        ${esc(t.assignee ? t.assignee.full_name : "Chưa giao")} · ${fmtDate(t.due_date)}</div></div>`;
  }

  async function loadTasks() {
    const qs = new URLSearchParams(Object.entries(formData(filter)).filter(([, v]) => v));
    const tasks = await api("GET", `/api/projects/${pid}/tasks?${qs}`);
    for (const s of ["todo", "in_progress", "review", "done"]) {
      const col = tasks.filter((t) => t.status === s);
      $(`col-${s}`).innerHTML = col.map(card).join("") || '<div class="small text-muted px-1">Trống</div>';
      $(`count-${s}`).textContent = `(${col.length})`;
    }
  }

  (async () => {
    const [p, members, milestones] = await Promise.all([loadProjectHeader(pid), api("GET", `/api/projects/${pid}/members`),
      api("GET", `/api/projects/${pid}/milestones`)]);
    const workers = members.filter((m) => m.project_role !== "supervisor");
    const opts = workers.map((m) => `<option value="${m.user.id}">${esc(m.user.full_name)}</option>`).join("");
    const msOpts = milestones.map((m) => `<option value="${m.id}">${esc(m.title)}</option>`).join("");
    $("f-assignee").innerHTML += opts; $("nt-assignee").innerHTML += opts;
    $("f-milestone").innerHTML += msOpts; $("nt-milestone").innerHTML += msOpts;
    if (p.my_role === "manager" || ME.role === "admin") $("new-task-btn").classList.remove("d-none");
    await loadTasks();
  })().catch((err) => showAlert(err.message));

  filter.onchange = () => handle(loadTasks());
  $("new-task-btn").onclick = () => $("new-task").classList.toggle("d-none");
  $("new-task").onsubmit = (e) => {
    e.preventDefault();
    const b = formData(e.target);
    const body = { title: b.title, description: b.description, priority: b.priority, points: Number(b.points),
      due_date: b.due_date || null, assignee_id: b.assignee_id ? Number(b.assignee_id) : null,
      milestone_id: b.milestone_id ? Number(b.milestone_id) : null };
    handle(api("POST", `/api/projects/${pid}/tasks`, body).then(() => { e.target.reset(); return loadTasks(); }));
  };
}

// ---------- Cột mốc ----------
if ($("milestones-page")) {
  const pid = $("milestones-page").dataset.projectId;
  let project;

  async function loadMilestones() {
    const [list, members] = await Promise.all([api("GET", `/api/projects/${pid}/milestones`), api("GET", `/api/projects/${pid}/members`)]);
    const role = project.my_role;
    const isManager = role === "manager" || ME.role === "admin";
    const hasSupervisor = members.some((m) => m.project_role === "supervisor");
    const canReview = ME.role === "admin" || role === "supervisor" || (role === "manager" && !hasSupervisor);
    $("new-milestone").classList.toggle("d-none", !isManager);
    $("ms-list").innerHTML = list.map((m) => {
      const pct = m.task_count ? Math.round((100 * m.done_count) / m.task_count) : 0;
      const late = m.due_date && m.due_date < today && m.status !== "accepted";
      let actions = "";
      if (isManager && ["open", "changes_requested"].includes(m.status))
        actions += `<button class="btn btn-sm btn-outline-primary" data-submit="${m.id}">Gửi nghiệm thu</button> `;
      if (canReview && m.status === "pending_review")
        actions += `<button class="btn btn-sm btn-success" data-accept="${m.id}">Nghiệm thu</button>
          <button class="btn btn-sm btn-outline-danger" data-changes="${m.id}">Yêu cầu sửa</button>`;
      if (isManager && m.status !== "accepted") actions += ` <button class="btn btn-sm btn-link text-danger" data-del="${m.id}">Xóa</button>`;
      return `<div class="card p-3 mb-2">
        <div class="d-flex justify-content-between flex-wrap gap-2">
          <div><span class="fw-semibold">${esc(m.title)}</span>
            <span class="badge text-bg-${MS_BADGE[m.status]} ms-1">${label(m.status)}</span>
            <div class="small ${late ? "text-danger" : "text-muted"}">Hạn ${fmtDate(m.due_date)}${late ? " · đã quá hạn" : ""}</div>
            ${m.description ? `<div class="small">${esc(m.description)}</div>` : ""}
            ${m.review_note ? `<div class="small mt-1"><b>Nhận xét nghiệm thu:</b> ${esc(m.review_note)}</div>` : ""}</div>
          <div class="text-end">${actions}</div></div>
        <div class="progress mt-2" style="height:6px"><div class="progress-bar" style="width:${pct}%"></div></div>
        <div class="small text-muted mt-1">${m.done_count}/${m.task_count} việc hoàn thành</div></div>`;
    }).join("") || '<p class="text-muted">Chưa có cột mốc.</p>';
  }

  $("ms-list").onclick = (e) => {
    const d = e.target.dataset;
    let req;
    if (d.submit) req = api("POST", `/api/milestones/${d.submit}/submit`);
    else if (d.accept) req = api("POST", `/api/milestones/${d.accept}/review`, { action: "accept", note: prompt("Nhận xét (không bắt buộc):") || "" });
    else if (d.changes) {
      const note = prompt("Cần sửa những gì?");
      if (!note) return;
      req = api("POST", `/api/milestones/${d.changes}/review`, { action: "request_changes", note });
    } else if (d.del) req = api("DELETE", `/api/milestones/${d.del}`);
    if (req) handle(req.then(loadMilestones));
  };
  $("new-milestone").onsubmit = (e) => {
    e.preventDefault();
    const b = formData(e.target);
    handle(api("POST", `/api/projects/${pid}/milestones`, { ...b, due_date: b.due_date || null })
      .then(() => { e.target.reset(); return loadMilestones(); }));
  };
  handle(loadProjectHeader(pid).then((p) => { project = p; return loadMilestones(); }));
}

// ---------- Chi tiết việc ----------
if ($("task-page")) {
  const tid = $("task-page").dataset.taskId;
  const HIST = {
    created: () => "tạo việc", status: (h) => `đổi trạng thái ${label(h.old_value)} → ${label(h.new_value)}`,
    assignee_id: (h) => `đổi người làm (#${h.old_value ?? "—"} → #${h.new_value ?? "—"})`,
    due_date: (h) => `đổi hạn ${fmtDate(h.old_value)} → ${fmtDate(h.new_value)}`,
    points: (h) => `đổi điểm ${h.old_value} → ${h.new_value}`,
    review: (h) => (h.old_value === "approve" ? "duyệt hoàn thành" : "trả lại"),
    attachment: (h) => `nộp minh chứng "${h.new_value}"`,
    dependency: (h) => (h.new_value ? `thêm phụ thuộc vào việc #${h.new_value}` : `bỏ phụ thuộc việc #${h.old_value}`),
  };

  async function loadTask() {
    const t = await api("GET", `/api/tasks/${tid}`);
    const [members, tasks, comments, history] = await Promise.all([
      api("GET", `/api/projects/${t.project_id}/members`), api("GET", `/api/projects/${t.project_id}/tasks`),
      api("GET", `/api/tasks/${tid}/comments`), api("GET", `/api/tasks/${tid}/history`)]);
    const isManager = t.my_role === "manager" || ME.role === "admin";
    const isAssignee = t.assignee_id === ME.id;
    const canWork = (isManager || isAssignee) && t.my_role !== "supervisor";
    $("back-link").href = `/projects/${t.project_id}`;
    $("t-title").textContent = t.title;
    $("t-status").textContent = label(t.status);
    $("t-meta").innerHTML = `${esc(t.assignee ? t.assignee.full_name : "Chưa giao")} · Hạn ${fmtDate(t.due_date)} · ${t.points} điểm · Ưu tiên ${label(t.priority)}`
      + (isOverdue(t) ? ' · <span class="text-danger fw-semibold">Quá hạn</span>' : "") + (t.blocked ? ' · <span class="badge text-bg-dark">Bị chặn</span>' : "");
    $("t-desc").textContent = t.description || "";

    const btn = (status, text, cls = "outline-primary") => `<button class="btn btn-sm btn-${cls}" data-status="${status}">${text}</button>`;
    let actions = "";
    if (canWork && t.status === "todo") actions += btn("in_progress", "Bắt đầu làm", "primary");
    if (canWork && t.status === "in_progress") actions += btn("review", "Gửi duyệt", "primary") + btn("todo", "Về Cần làm", "outline-secondary");
    if (isManager && t.status === "review") actions += '<button class="btn btn-sm btn-success" data-approve="1">Duyệt hoàn thành</button>'
      + '<button class="btn btn-sm btn-outline-danger" data-return="1">Trả lại</button>';
    if (isManager) actions += '<button class="btn btn-sm btn-link text-danger ms-auto" data-delete="1">Xóa việc</button>';
    $("t-actions").innerHTML = actions;

    $("t-evidence").innerHTML = t.attachments.map((a) => `<li class="list-group-item px-0 small">
      <a href="${esc(a.url)}" target="_blank" rel="noopener">${esc(a.filename)}</a> <span class="text-muted">· ${fmtTime(a.created_at)}</span></li>`).join("")
      || '<li class="list-group-item px-0 small text-muted">Chưa có minh chứng. Cần ít nhất một minh chứng để gửi duyệt.</li>';
    $("evidence-form").classList.toggle("d-none", !(canWork && t.status !== "done"));

    const f = $("edit-form");
    f.assignee_id.innerHTML = '<option value="">Chưa giao</option>' + members.filter((m) => m.project_role !== "supervisor")
      .map((m) => `<option value="${m.user.id}">${esc(m.user.full_name)}</option>`).join("");
    f.assignee_id.value = t.assignee_id ?? ""; f.due_date.value = t.due_date || ""; f.points.value = t.points; f.priority.value = t.priority;
    [...f.elements].forEach((el) => { if (el.tagName !== "BUTTON") el.disabled = !isManager; });
    $("edit-save").classList.toggle("d-none", !isManager);

    $("t-deps").innerHTML = t.depends_on.map((d) => `<li class="list-group-item px-0 small d-flex justify-content-between">
      <a href="/tasks/${d.id}">${esc(d.title)}</a><span><span class="badge text-bg-${d.status === "done" ? "success" : "secondary"}">${label(d.status)}</span>
      ${isManager ? `<button class="btn btn-sm btn-link text-danger p-0 ms-1" data-undep="${d.id}">×</button>` : ""}</span></li>`).join("")
      || '<li class="list-group-item px-0 small text-muted">Không phụ thuộc việc nào</li>';
    $("dep-form").classList.toggle("d-none", !isManager);
    $("dep-select").innerHTML = tasks.filter((x) => x.id !== t.id && !t.depends_on.some((d) => d.id === x.id))
      .map((x) => `<option value="${x.id}">${esc(x.title)}</option>`).join("");

    $("t-comments").innerHTML = comments.map((c) => `<div class="border-bottom py-2 small">
      <b>${esc(c.user.full_name)}</b> <span class="text-muted">${fmtTime(c.created_at)}</span>
      ${ME.role === "admin" ? `<button class="btn btn-sm btn-link p-0 ms-2" data-hide="${c.id}" data-hidden="${c.is_hidden}">${c.is_hidden ? "Hiện lại" : "Ẩn (vi phạm)"}</button>` : ""}
      <div class="${c.is_hidden ? "text-muted fst-italic" : ""}">${esc(c.content)}</div></div>`).join("") || '<div class="small text-muted">Chưa có bình luận</div>';
    $("t-history").innerHTML = history.slice().reverse().map((h) => `<li class="mb-2"><span class="text-muted">${fmtTime(h.created_at)}</span><br>
      <b>${esc(h.user.full_name)}</b> ${(HIST[h.field] || (() => h.field))(h)}${h.note ? `<br><i>“${esc(h.note)}”</i>` : ""}</li>`).join("");
  }

  $("t-actions").onclick = (e) => {
    const d = e.target.dataset;
    if (d.status) handle(api("PATCH", `/api/tasks/${tid}/status`, { status: d.status }).then(loadTask));
    if (d.approve) handle(api("POST", `/api/tasks/${tid}/review`, { action: "approve" }).then(loadTask));
    if (d.return) $("return-form").classList.toggle("d-none");
    if (d.delete && confirm("Xóa việc này?")) handle(api("DELETE", `/api/tasks/${tid}`).then(() => history.back()));
  };
  $("return-form").onsubmit = (e) => {
    e.preventDefault();
    handle(api("POST", `/api/tasks/${tid}/review`, { action: "return", note: e.target.note.value })
      .then(() => { e.target.reset(); $("return-form").classList.add("d-none"); return loadTask(); }));
  };
  $("evidence-form").onsubmit = (e) => {
    e.preventDefault();
    const f = e.target;
    const req = f.file.files.length ? api("POST", `/api/tasks/${tid}/attachments`, new FormData(f))
      : api("POST", `/api/tasks/${tid}/attachments`, { url: f.url.value });
    handle(req.then(() => { f.reset(); return loadTask(); }));
  };
  $("edit-form").onsubmit = (e) => {
    e.preventDefault();
    const b = formData(e.target);
    handle(api("PATCH", `/api/tasks/${tid}`, { assignee_id: b.assignee_id ? Number(b.assignee_id) : null,
      due_date: b.due_date || null, points: Number(b.points), priority: b.priority })
      .then(() => { showAlert("Đã lưu", "success"); return loadTask(); }));
  };
  $("dep-form").onsubmit = (e) => {
    e.preventDefault();
    handle(api("POST", `/api/tasks/${tid}/dependencies`, { depends_on_id: Number(e.target.depends_on_id.value) }).then(loadTask));
  };
  $("t-deps").onclick = (e) => {
    if (e.target.dataset.undep) handle(api("DELETE", `/api/tasks/${tid}/dependencies/${e.target.dataset.undep}`).then(loadTask));
  };
  $("comment-form").onsubmit = (e) => {
    e.preventDefault();
    handle(api("POST", `/api/tasks/${tid}/comments`, formData(e.target)).then(() => { e.target.reset(); return loadTask(); }));
  };
  $("t-comments").onclick = (e) => {
    const d = e.target.dataset;
    if (d.hide) handle(api("PATCH", `/api/admin/comments/${d.hide}`, { is_hidden: d.hidden !== "true" }).then(loadTask));
  };
  handle(loadTask());
}
