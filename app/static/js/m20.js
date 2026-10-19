// JS của M20 (Thành viên 1). Mỗi khối chỉ chạy khi trang có phần tử tương ứng.
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const formData = (form) => Object.fromEntries(new FormData(form));

// ---------- Đăng nhập ----------
const loginForm = document.getElementById("login-form");
if (loginForm) loginForm.onsubmit = async (e) => {
  e.preventDefault();
  try {
    await api("POST", "/api/auth/login", formData(loginForm));
    location.href = new URLSearchParams(location.search).get("next") || "/courses";
  } catch (err) { showAlert(err.message); }
};

// ---------- Đăng ký ----------
const registerForm = document.getElementById("register-form");
if (registerForm) registerForm.onsubmit = async (e) => {
  e.preventDefault();
  const body = formData(registerForm);
  try {
    await api("POST", "/api/auth/register", body);
    await api("POST", "/api/auth/login", { email: body.email, password: body.password });
    location.href = "/courses";
  } catch (err) { showAlert(err.message); }
};

// ---------- Tài khoản ----------
const profile = document.getElementById("profile");
if (profile) (async () => {
  const me = await api("GET", "/api/auth/me");
  profile.innerHTML = `<dt class="col-4">Họ tên</dt><dd class="col-8">${esc(me.full_name)}</dd>
    <dt class="col-4">Email</dt><dd class="col-8">${esc(me.email)}</dd>
    <dt class="col-4">Vai trò</dt><dd class="col-8">${esc(me.role)}</dd>`;
})().catch((err) => showAlert(err.message));

const passwordForm = document.getElementById("password-form");
if (passwordForm) passwordForm.onsubmit = async (e) => {
  e.preventDefault();
  try {
    await api("PATCH", "/api/auth/me/password", formData(passwordForm));
    passwordForm.reset();
    showAlert("Đã đổi mật khẩu", "success");
  } catch (err) { showAlert(err.message); }
};

// ---------- Thành viên dự án ----------
const membersPage = document.getElementById("members-page");
if (membersPage) {
  const pid = membersPage.dataset.projectId;
  const body = document.getElementById("members-body");

  async function loadMembers() {
    const [me, members] = await Promise.all([api("GET", "/api/auth/me"), api("GET", `/api/projects/${pid}/members`)]);
    const iAmLeader = me.role === "admin" || members.some((m) => m.user.id === me.id && m.project_role === "leader");
    document.getElementById("invite-box").classList.toggle("d-none", !iAmLeader);
    body.innerHTML = members.map((m) => `<tr>
      <td>${esc(m.user.full_name)}</td><td>${esc(m.user.email)}</td>
      <td>${m.project_role === "leader" ? '<span class="badge bg-primary">Trưởng nhóm</span>' : "Thành viên"}</td>
      <td class="text-end">${iAmLeader && m.project_role !== "leader" ? `
        <button class="btn btn-sm btn-outline-primary" data-act="lead" data-uid="${m.user.id}">Chuyển trưởng nhóm</button>
        <button class="btn btn-sm btn-outline-danger" data-act="remove" data-uid="${m.user.id}">Xóa</button>` : ""}</td>
    </tr>`).join("");
  }

  body.onclick = async (e) => {
    const btn = e.target.closest("button[data-act]");
    if (!btn) return;
    const uid = btn.dataset.uid;
    try {
      if (btn.dataset.act === "lead") await api("PATCH", `/api/projects/${pid}/members/${uid}`, { project_role: "leader" });
      else await api("DELETE", `/api/projects/${pid}/members/${uid}`);
      await loadMembers();
    } catch (err) { showAlert(err.message); }
  };

  const inviteForm = document.getElementById("invite-form");
  inviteForm.onsubmit = async (e) => {
    e.preventDefault();
    try {
      const inv = await api("POST", `/api/projects/${pid}/invitations`, formData(inviteForm));
      const link = location.origin + inv.accept_url;
      document.getElementById("invite-result").innerHTML =
        `Gửi link này cho <b>${esc(inv.email)}</b>: <code>${esc(link)}</code>`;
      inviteForm.reset();
    } catch (err) { showAlert(err.message); }
  };

  loadMembers().catch((err) => showAlert(err.message));
}

// ---------- Nhận lời mời ----------
const invitationPage = document.getElementById("invitation-page");
if (invitationPage) document.getElementById("accept-btn").onclick = async () => {
  try {
    const m = await api("POST", `/api/invitations/${invitationPage.dataset.token}/accept`);
    location.href = `/projects/${m.project_id}`;
  } catch (err) { showAlert(err.message); }
};

// ---------- Quản trị người dùng ----------
const usersBody = document.getElementById("users-body");
if (usersBody) {
  const filter = document.getElementById("user-filter");
  let meId = null;

  async function loadUsers() {
    meId = meId ?? (await api("GET", "/api/auth/me")).id;
    const qs = new URLSearchParams(Object.entries(formData(filter)).filter(([, v]) => v));
    const users = await api("GET", "/api/admin/users?" + qs);
    usersBody.innerHTML = users.map((u) => `<tr>
      <td>${u.id}</td><td>${esc(u.full_name)}</td><td>${esc(u.email)}</td>
      <td><select class="form-select form-select-sm" data-uid="${u.id}" ${u.id === meId ? "disabled" : ""}>
        ${["admin", "lecturer", "student"].map((r) => `<option ${r === u.role ? "selected" : ""}>${r}</option>`).join("")}
      </select></td>
      <td>${u.is_active ? '<span class="badge bg-success">Hoạt động</span>' : '<span class="badge bg-secondary">Đã khóa</span>'}</td>
      <td class="text-end">${u.id === meId ? "" : `<button class="btn btn-sm btn-outline-${u.is_active ? "danger" : "success"}"
        data-uid="${u.id}" data-active="${u.is_active}">${u.is_active ? "Khóa" : "Mở khóa"}</button>`}</td>
    </tr>`).join("") || '<tr><td colspan="6" class="text-muted">Không có kết quả</td></tr>';
  }

  filter.onsubmit = (e) => { e.preventDefault(); loadUsers().catch((err) => showAlert(err.message)); };
  usersBody.onchange = async (e) => {
    if (!e.target.matches("select[data-uid]")) return;
    try { await api("PATCH", `/api/admin/users/${e.target.dataset.uid}`, { role: e.target.value }); showAlert("Đã đổi vai trò", "success"); }
    catch (err) { showAlert(err.message); }
    await loadUsers();
  };
  usersBody.onclick = async (e) => {
    const btn = e.target.closest("button[data-uid]");
    if (!btn) return;
    try { await api("PATCH", `/api/admin/users/${btn.dataset.uid}`, { is_active: btn.dataset.active !== "true" }); await loadUsers(); }
    catch (err) { showAlert(err.message); }
  };
  loadUsers().catch((err) => showAlert(err.message));
}

// ---------- Giám sát dự án ----------
const projectsBody = document.getElementById("projects-body");
if (projectsBody) api("GET", "/api/admin/projects").then((projects) => {
  projectsBody.innerHTML = projects.map((p) => `<tr>
    <td>${p.id}</td><td><a href="/projects/${p.id}">${esc(p.name)}</a></td><td>${esc(p.course_code)}</td>
    <td>${esc(p.leader ? p.leader.full_name : "—")}</td>
    <td class="text-end"><a href="/projects/${p.id}/members">${p.member_count}</a></td>
    <td class="text-end">${p.task_count}</td><td>${esc(p.due_date || "—")}</td>
  </tr>`).join("") || '<tr><td colspan="7" class="text-muted">Chưa có dự án</td></tr>';
}).catch((err) => showAlert(err.message));
