// FILE DÙNG CHUNG — mọi trang gọi backend qua hàm api(), không tự viết fetch() khác.
// Thành công: trả về phần "data". Lỗi: ném Error có .code, .status (lấy từ {"error": {...}}).
async function api(method, url, body) {
  const opts = { method, headers: {}, credentials: "same-origin" };
  if (body instanceof FormData) opts.body = body;               // upload file
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

function showAlert(message, type = "danger") {
  const box = document.getElementById("alert-box");
  box.innerHTML = `<div class="alert alert-${type}">${message.replace(/</g, "&lt;")}</div>`;
}

// Hiển thị user đang đăng nhập trên menu
(async () => {
  try {
    const me = await fetch("/api/auth/me").then(r => r.ok ? r.json() : null);
    if (!me) return;
    document.getElementById("nav-user").textContent = `${me.data.full_name} (${me.data.role})`;
    document.getElementById("nav-login").classList.add("d-none");
    const out = document.getElementById("nav-logout");
    out.classList.remove("d-none");
    out.onclick = async () => { await api("POST", "/api/auth/logout"); location.href = "/login"; };
  } catch (_) {}
})();
