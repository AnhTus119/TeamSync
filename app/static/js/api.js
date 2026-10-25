// FILE DÙNG CHUNG — mọi trang gọi backend qua api(), không tự viết fetch() khác.
// Thành công: trả về phần "data". Lỗi: ném Error có .code, .status (lấy từ {"error": {...}}).
async function api(method, url, body) {
  const opts = { method, headers: {}, credentials: "same-origin" };
  if (body instanceof FormData) opts.body = body;
  else if (body !== undefined) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(url, opts);
  const json = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = new Error((json.error && json.error.message) || res.statusText);
    err.code = json.error && json.error.code;
    err.status = res.status;
    if (res.status === 401 && !location.pathname.startsWith("/login")) location.href = "/login?next=" + location.pathname;
    throw err;
  }
  return json.data;
}

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const formData = (form) => Object.fromEntries(new FormData(form));
const fmtDate = (s) => (s ? s.slice(0, 10).split("-").reverse().join("/") : "—");
const fmtTime = (s) => (s ? `${fmtDate(s)} ${s.slice(11, 16)}` : "—");
const LABEL = {
  todo: "Cần làm", in_progress: "Đang làm", review: "Chờ duyệt", done: "Hoàn thành",
  low: "Thấp", medium: "Trung bình", high: "Cao",
  manager: "Quản lý", member: "Thành viên", supervisor: "Giám sát", owner: "Chủ", admin: "Quản trị viên", user: "Người dùng",
  open: "Đang làm", pending_review: "Chờ nghiệm thu", accepted: "Đã nghiệm thu", changes_requested: "Yêu cầu sửa",
};
const label = (k) => LABEL[k] || k;

function showAlert(message, type = "danger") {
  const box = document.getElementById("alert-box");
  box.innerHTML = `<div class="alert alert-${type} alert-dismissible">${esc(message)}<button class="btn-close" data-bs-dismiss="alert" onclick="this.parentElement.remove()"></button></div>`;
  window.scrollTo({ top: 0, behavior: "smooth" });
}
const handle = (p) => p.catch((err) => showAlert(err.message));

// Tiêu đề chung của trang dự án (_project_nav.html). Trả về project kèm my_role.
async function loadProjectHeader(pid) {
  const p = await api("GET", `/api/projects/${pid}`);
  document.getElementById("pn-title").textContent = p.name;
  document.getElementById("pn-workspace").innerHTML = `<a href="/workspaces/${p.workspace_id}">${esc(p.workspace_name)}</a>`;
  document.getElementById("pn-role").textContent = p.my_role ? `Bạn là: ${label(p.my_role)}` : (ME.role === "admin" ? "Quản trị viên" : "Chủ không gian làm việc");
  document.title = `${p.name} — TeamSync`;
  return p;
}

const logout = document.getElementById("nav-logout");
if (logout) logout.onclick = async () => { await api("POST", "/api/auth/logout"); location.href = "/login"; };
