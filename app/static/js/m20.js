// JS của M20 (Thành viên 1). Mỗi khối chỉ chạy khi trang có phần tử tương ứng.
const $ = (id) => document.getElementById(id);
const healthDot = (level) => `<span class="m17-light ${level}" title="${level}"></span>`;

// ---------- Đăng nhập / đăng ký / đổi mật khẩu ----------
if ($("login-form")) $("login-form").onsubmit = (e) => {
  e.preventDefault();
  handle(api("POST", "/api/auth/login", formData(e.target)).then(() => {
    location.href = new URLSearchParams(location.search).get("next") || "/projects";
  }));
};

if ($("register-form")) $("register-form").onsubmit = (e) => {
  e.preventDefault();
  const body = formData(e.target);
  handle(api("POST", "/api/auth/register", body)
    .then(() => api("POST", "/api/auth/login", { email: body.email, password: body.password }))
    .then(() => (location.href = "/workspaces")));
};

if ($("password-form")) $("password-form").onsubmit = (e) => {
  e.preventDefault();
  handle(api("PATCH", "/api/auth/me/password", formData(e.target)).then(() => {
    e.target.reset();
    showAlert("Đã đổi mật khẩu", "success");
  }));
};

// ---------- Danh sách workspace ----------
if ($("ws-list")) {
  const load = () => api("GET", "/api/workspaces").then((list) => {
    $("ws-list").innerHTML = list.map((w) => `<div class="col-md-4"><a class="card p-3 h-100 text-decoration-none text-body" href="/workspaces/${w.id}">
      <div class="fw-semibold">${esc(w.name)}</div><div class="small text-muted mb-2">${esc(w.description || "")}</div>
      <div class="small mt-auto">${w.project_count} dự án · ${label(w.my_role || "admin")}</div></a></div>`).join("")
      || '<p class="text-muted">Bạn chưa ở trong không gian làm việc nào. Tạo một cái bên dưới.</p>';
  });
  $("ws-form").onsubmit = (e) => {
    e.preventDefault();
    handle(api("POST", "/api/workspaces", formData(e.target)).then((w) => (location.href = `/workspaces/${w.id}`)));
  };
  handle(load());
}

// ---------- Chi tiết workspace ----------
if ($("ws-page")) {
  const wid = $("ws-page").dataset.workspaceId;
  let templates = [];

  async function loadWorkspace() {
    const [ws, members, projects] = await Promise.all([
      api("GET", `/api/workspaces/${wid}`), api("GET", `/api/workspaces/${wid}/members`), api("GET", `/api/workspaces/${wid}/projects`)]);
    const isOwner = ws.my_role === "owner" || ME.role === "admin";
    $("ws-name").textContent = ws.name;
    $("ws-desc").textContent = ws.description || "";
    $("ws-add-member").classList.toggle("d-none", !isOwner);
    $("ws-members").innerHTML = members.map((m) => `<li class="list-group-item d-flex justify-content-between align-items-center px-0">
      <span>${esc(m.user.full_name)}<br><span class="small text-muted">${esc(m.user.email)}</span></span>
      ${m.role === "owner" ? '<span class="badge text-bg-primary">Chủ</span>'
        : isOwner ? `<button class="btn btn-sm btn-link text-danger" data-remove="${m.user.id}">Xóa</button>` : ""}</li>`).join("");
    const overview = isOwner ? await api("GET", `/api/workspaces/${wid}/overview`) : [];
    const ov = Object.fromEntries(overview.map((o) => [o.project_id, o]));
    $("ws-projects").innerHTML = projects.map((p) => `<tr>
      <td><a href="/projects/${p.id}">${esc(p.name)}</a></td><td>${p.my_role ? label(p.my_role) : "—"}</td>
      <td>${fmtDate(p.due_date)}</td><td>${ov[p.id] ? healthDot(ov[p.id].health) : ""}</td>
      <td class="text-end">${ov[p.id] ? ov[p.id].percent_points + "%" : ""}</td></tr>`).join("")
      || '<tr><td colspan="5" class="text-muted">Chưa có dự án</td></tr>';
  }

  $("ws-members").onclick = (e) => {
    const uid = e.target.dataset.remove;
    if (uid) handle(api("DELETE", `/api/workspaces/${wid}/members/${uid}`).then(loadWorkspace));
  };
  $("ws-add-member").onsubmit = (e) => {
    e.preventDefault();
    handle(api("POST", `/api/workspaces/${wid}/members`, formData(e.target)).then(() => { e.target.reset(); return loadWorkspace(); }));
  };
  api("GET", "/api/templates").then((list) => {
    templates = list;
    $("tpl-select").innerHTML += list.map((t) => `<option value="${t.id}">${esc(t.name)}</option>`).join("");
  });
  $("tpl-select").onchange = (e) => {
    const t = templates.find((x) => String(x.id) === e.target.value);
    $("tpl-hint").textContent = t ? `Tạo sẵn ${t.milestones.length} cột mốc và ${t.tasks.length} việc: ${t.milestones.map((m) => m.title).join(", ")}` : "";
  };
  $("new-project").onsubmit = (e) => {
    e.preventDefault();
    const body = Object.fromEntries(Object.entries(formData(e.target)).filter(([, v]) => v !== ""));
    if (body.template_id) body.template_id = Number(body.template_id);
    handle(api("POST", `/api/workspaces/${wid}/projects`, body).then((p) => (location.href = `/projects/${p.id}`)));
  };
  handle(loadWorkspace());
}

// ---------- Thành viên dự án ----------
if ($("members-page")) {
  const pid = $("members-page").dataset.projectId;
  let isManager = false;

  async function loadMembers() {
    const [p, members] = await Promise.all([loadProjectHeader(pid), api("GET", `/api/projects/${pid}/members`)]);
    isManager = p.my_role === "manager" || ME.role === "admin";
    $("invite-box").classList.toggle("d-none", !isManager);
    $("members-body").innerHTML = members.map((m) => {
      const actions = isManager && m.project_role !== "manager" ? `
        <button class="btn btn-sm btn-outline-primary" data-act="manager" data-uid="${m.user.id}">Chuyển quản lý</button>
        <button class="btn btn-sm btn-outline-secondary" data-act="${m.project_role === "supervisor" ? "member" : "supervisor"}" data-uid="${m.user.id}">
          ${m.project_role === "supervisor" ? "Đổi thành thành viên" : "Đổi thành giám sát"}</button>
        <button class="btn btn-sm btn-outline-danger" data-act="remove" data-uid="${m.user.id}">Xóa</button>` : "";
      const badge = { manager: "primary", member: "secondary", supervisor: "info" }[m.project_role];
      return `<tr><td>${esc(m.user.full_name)}</td><td>${esc(m.user.email)}</td>
        <td><span class="badge text-bg-${badge}">${label(m.project_role)}</span></td><td class="text-end">${actions}</td></tr>`;
    }).join("");
    if (isManager) {
      const invs = await api("GET", `/api/projects/${pid}/invitations`);
      $("invite-list").innerHTML = invs.map((i) => `<li class="list-group-item px-0 d-flex justify-content-between">
        <span>${esc(i.email)} · ${label(i.project_role)}<br><code class="small">${esc(location.origin + i.accept_url)}</code></span>
        <button class="btn btn-sm btn-link text-danger" data-revoke="${i.id}">Hủy</button></li>`).join("") || '<li class="list-group-item px-0 text-muted">Không có</li>';
    }
  }

  $("members-body").onclick = (e) => {
    const btn = e.target.closest("button[data-act]");
    if (!btn) return;
    const url = `/api/projects/${pid}/members/${btn.dataset.uid}`;
    handle((btn.dataset.act === "remove" ? api("DELETE", url) : api("PATCH", url, { project_role: btn.dataset.act })).then(loadMembers));
  };
  $("invite-list").onclick = (e) => {
    if (e.target.dataset.revoke) handle(api("DELETE", `/api/invitations/${e.target.dataset.revoke}`).then(loadMembers));
  };
  $("invite-form").onsubmit = (e) => {
    e.preventDefault();
    handle(api("POST", `/api/projects/${pid}/invitations`, formData(e.target)).then((inv) => {
      $("invite-result").innerHTML = `Gửi link này cho <b>${esc(inv.email)}</b>: <code>${esc(location.origin + inv.accept_url)}</code>`;
      e.target.reset();
      return loadMembers();
    }));
  };
  handle(loadMembers());
}

// ---------- Nhận lời mời ----------
if ($("invitation-page")) {
  const token = $("invitation-page").dataset.token;
  handle(api("GET", `/api/invitations/${token}`).then((inv) => {
    $("inv-info").innerHTML = `<b>${esc(inv.invited_by)}</b> mời bạn vào dự án <b>${esc(inv.project.name)}</b> với vai trò <b>${label(inv.project_role)}</b>.`;
    if (inv.status === "pending") $("accept-btn").classList.remove("d-none");
    else $("inv-info").innerHTML += "<br>Lời mời này đã được sử dụng hoặc đã bị hủy.";
  }).catch((err) => { $("inv-info").textContent = err.message; }));
  $("accept-btn").onclick = () => handle(api("POST", `/api/invitations/${token}/accept`).then((m) => (location.href = `/projects/${m.project_id}`)));
}

// ---------- Quản trị: người dùng ----------
if ($("users-body")) {
  const filter = $("user-filter");
  async function loadUsers() {
    const qs = new URLSearchParams(Object.entries(formData(filter)).filter(([, v]) => v));
    const users = await api("GET", "/api/admin/users?" + qs);
    $("users-body").innerHTML = users.map((u) => `<tr>
      <td>${u.id}</td><td>${esc(u.full_name)}</td><td>${esc(u.email)}</td>
      <td><select class="form-select form-select-sm" data-uid="${u.id}" ${u.id === ME.id ? "disabled" : ""}>
        ${["admin", "user"].map((r) => `<option value="${r}" ${r === u.role ? "selected" : ""}>${label(r)}</option>`).join("")}</select></td>
      <td>${u.is_active ? '<span class="badge text-bg-success">Hoạt động</span>' : '<span class="badge text-bg-secondary">Đã khóa</span>'}</td>
      <td class="text-end">${u.id === ME.id ? "" : `<button class="btn btn-sm btn-outline-${u.is_active ? "danger" : "success"}"
        data-uid="${u.id}" data-active="${u.is_active}">${u.is_active ? "Khóa" : "Mở khóa"}</button>`}</td></tr>`).join("")
      || '<tr><td colspan="6" class="text-muted">Không có kết quả</td></tr>';
  }
  filter.onsubmit = (e) => { e.preventDefault(); handle(loadUsers()); };
  $("users-body").onchange = (e) => {
    if (!e.target.matches("select[data-uid]")) return;
    handle(api("PATCH", `/api/admin/users/${e.target.dataset.uid}`, { role: e.target.value })
      .then(() => showAlert("Đã đổi vai trò", "success")).finally(loadUsers));
  };
  $("users-body").onclick = (e) => {
    const btn = e.target.closest("button[data-uid]");
    if (btn) handle(api("PATCH", `/api/admin/users/${btn.dataset.uid}`, { is_active: btn.dataset.active !== "true" }).then(loadUsers));
  };
  handle(loadUsers());
}

// ---------- Quản trị: dự án ----------
if ($("projects-body")) handle(api("GET", "/api/admin/projects").then((projects) => {
  $("projects-body").innerHTML = projects.map((p) => `<tr>
    <td>${p.id}</td><td><a href="/projects/${p.id}">${esc(p.name)}</a></td><td>${esc(p.workspace_name)}</td>
    <td>${esc(p.manager ? p.manager.full_name : "—")}</td><td class="text-end">${p.member_count}</td>
    <td class="text-end">${p.task_count}</td><td>${fmtDate(p.due_date)}</td></tr>`).join("")
    || '<tr><td colspan="7" class="text-muted">Chưa có dự án</td></tr>';
}));

// ---------- Quản trị: mẫu dự án ----------
if ($("tpl-list")) {
  const form = $("tpl-form");
  const toLines = (items, keys) => items.map((i) => keys.map((k) => i[k] ?? "").join(" | ")).join("\n");
  const parse = (text, build) => text.split("\n").map((l) => l.trim()).filter(Boolean).map((l) => build(l.split("|").map((s) => s.trim())));
  let templates = [];

  async function loadTemplates() {
    templates = await api("GET", "/api/templates");
    $("tpl-list").innerHTML = templates.map((t) => `<li class="list-group-item px-0 d-flex justify-content-between">
      <span><b>${esc(t.name)}</b><br><span class="small text-muted">${t.milestones.length} cột mốc · ${t.tasks.length} việc</span></span>
      <span><button class="btn btn-sm btn-link" data-edit="${t.id}">Sửa</button>
      <button class="btn btn-sm btn-link text-danger" data-del="${t.id}">Xóa</button></span></li>`).join("");
  }
  function reset() { form.reset(); form.id.value = ""; $("tpl-form-title").textContent = "Thêm mẫu"; }
  $("tpl-reset").onclick = reset;
  $("tpl-list").onclick = (e) => {
    if (e.target.dataset.del) return handle(api("DELETE", `/api/admin/templates/${e.target.dataset.del}`).then(loadTemplates));
    const t = templates.find((x) => String(x.id) === e.target.dataset.edit);
    if (!t) return;
    form.id.value = t.id; form.name.value = t.name; form.description.value = t.description || "";
    form.milestones.value = toLines(t.milestones, ["title", "offset_days"]);
    form.tasks.value = toLines(t.tasks, ["title", "milestone", "points"]);
    $("tpl-form-title").textContent = "Sửa mẫu: " + t.name;
  };
  form.onsubmit = (e) => {
    e.preventDefault();
    const body = {
      name: form.name.value, description: form.description.value,
      milestones: parse(form.milestones.value, ([title, d]) => ({ title, offset_days: Number(d) || 7 })),
      tasks: parse(form.tasks.value, ([title, milestone, pts]) => ({ title, milestone: milestone || undefined, points: Number(pts) || 1 })),
    };
    const req = form.id.value ? api("PATCH", `/api/admin/templates/${form.id.value}`, body) : api("POST", "/api/admin/templates", body);
    handle(req.then(() => { reset(); showAlert("Đã lưu mẫu", "success"); return loadTemplates(); }));
  };
  handle(loadTemplates());
}
