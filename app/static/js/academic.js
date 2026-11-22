import {groupHeader,groupNavigation} from "./group-navigation.js?v=9";
import {contributionMarkup,reportSummary} from "./report-components.js?v=9";
import {mountStudio,cleanupStudio} from "./teamwork.js?v=9";
const rubricImports = new Map();
const view = document.querySelector("#view"),
  notice = document.querySelector("#notice");
const h = (s) =>
  String(s ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const labels = {
  committed: "Đã nhập",
  previewed: "Đã xem trước",
  downloaded: "Đã tải",
  failed: "Lỗi",
  left: "Đã rời nhóm",
  legacy: "Dữ liệu cũ",
  user: "Người dùng",
  admin: "Ops · Quản trị kỹ thuật",
  todo: "Cần làm",
  in_progress: "Đang làm",
  review: "Chờ duyệt",
  done: "Hoàn thành",
  draft: "Bản nháp",
  published: "Đã công bố",
  active: "Đang thực hiện",
  assessment: "Đang đánh giá",
  finalized: "Đã chốt",
  archived: "Lưu trữ",
  pending: "Chờ duyệt",
  accepted: "Đã chấp nhận",
  returned: "Cần sửa",
  submitted: "Đã gửi",
  confirmed: "Thành viên đã xác nhận",
  disputed: "Có phản đối",
  incomplete: "Chưa đủ dữ liệu",
  complete: "Đủ tiêu chí",
  provisional: "Kết quả sơ bộ",
  appeal_review: "Đang giải trình",
  under_review: "Đang xử lý",
  decided: "Đã quyết định",
  withdrawn: "Đã rút",
  new: "Chưa tiếp nhận",
  acknowledged: "Đã tiếp nhận",
  action_planned: "Đã có kế hoạch",
  monitoring: "Đang theo dõi",
  resolved: "Đã kết thúc",
  dismissed: "Tạm bỏ qua",
  open: "Đang mở",
  closed: "Đã đóng",
  released: "Đã công bố",
  pending_review: "Chờ nghiệm thu",
  changes_requested: "Yêu cầu sửa",
  leader: "Nhóm trưởng",
  member: "Thành viên",
  instructor: "Giảng viên",
  coordinator: "Giảng viên",
  student: "Sinh viên",
  high: "Cao",
  medium: "Trung bình",
  low: "Thấp",
  approved: "Đã duyệt",
  rejected: "Từ chối",
  sufficient_evidence: "Đủ căn cứ",
  needs_verification: "Cần xác minh",
  unresolved: "Chưa thể kết luận",
  created: "Đã tạo",
  upheld: "Giữ nguyên",
  adjusted: "Điều chỉnh",
};
const label = (k) => labels[k] || k,
  badge = (k) => `<span class="badge ${h(k)}">${h(label(k))}</span>`;
const dt = (s) =>
  s
    ? new Intl.DateTimeFormat("vi-VN", {
        dateStyle: "short",
        timeStyle: "short",
        timeZone: "Asia/Ho_Chi_Minh",
      }).format(new Date(s))
    : "—";
function setNotificationCount(value) {
  notificationUnread = Math.max(0, Number(value) || 0);
  const badge = document.querySelector("#notification-unread-count");
  if (!badge) return;
  badge.textContent = notificationUnread > 99 ? "99+" : String(notificationUnread);
  badge.hidden = notificationUnread === 0;
}
async function refreshNotificationMenu() {
  const box = document.querySelector("#notification-menu-items");
  if (!box || !me) return;
  try {
    const [result, unread] = await Promise.all([
      get("/me/notifications?page_size=6&page=1"),
      get("/me/notifications?unread_only=true&page_size=1&page=1"),
    ]);
    const items = result.items || [];
    setNotificationCount(unread.total || 0);
    box.innerHTML = items.length ? items.map(n => `<a class="notification-menu-item ${n.read_at ? "" : "is-unread"}" href="${h(n.target_path || "/notifications")}" data-notification-id="${n.id}" data-notification-version="${n.version}" data-notification-read="${n.read_at ? "true" : "false"}"><strong>${h(n.title)}</strong><span>${h(n.body || "")}</span><small>${dt(n.created_at)}</small></a>`).join("") : `<p class="notification-hint">Bạn chưa có thông báo nào.</p>`;
  } catch (_) {
    box.innerHTML = `<p class="notification-hint">Không thể tải thông báo lúc này.</p>`;
  }
}
const localInput = (s) => {
  if (!s) return "";
  const d = new Date(new Date(s).getTime() + 7 * 3600000);
  return d.toISOString().slice(0, 16);
};
const utc = (s) => (s ? new Date(s + ":00+07:00").toISOString() : null);
let interaction = null;
let renderId = 0;
let dashboardTasks = [];
let dashboardCalendarItems = [];
let dashboardCalendarMode = "tasks";
let dashboardActionQueue = [];
let dashboardExpanded = { tasks: false, actions: false };
let calendarMonth = new Date(new Date().getFullYear(), new Date().getMonth(), 1);
let me,
  token,
  notificationUnread = 0,
  actions = new Map(),
  forms = new Map(),
  seq = 0,
  dirty = false;
const staff = (r) => ["instructor", "coordinator"].includes(r);
function link(url, text, cls = "") {
  return `<a href="${h(url)}" class="${cls || "text-button"}">${h(text)}</a>`;
}
function btn(text, fn, secondary = false) {
  const id = "a" + ++seq;
  actions.set(id, fn);
  return `<button type="button" data-action="${id}" class="${secondary ? "secondary" : ""}">${h(text)}</button>`;
}
function field(
  name,
  title,
  type = "text",
  value = "",
  help = "",
  required = true,
) {
  const id = "input" + ++seq;
  return `<div><label for="${id}">${h(title)}</label><input id="${id}" name="${h(name)}" type="${h(type)}" value="${h(value)}" ${required ? "required" : ""} ${help ? `aria-describedby="${id}-help"` : ""}>${help ? `<p id="${id}-help" class="field-help">${h(help)}</p>` : ""}</div>`;
}
function area(name, title, value = "", required = true) {
  const id = "input" + ++seq;
  return `<div><label for="${id}">${h(title)}</label><textarea id="${id}" name="${h(name)}" ${required ? "required" : ""}>${h(value)}</textarea></div>`;
}
function select(name, title, options, value = "", required = true) {
  const id = "input" + ++seq;
  return `<div><label for="${id}">${h(title)}</label><select id="${id}" name="${h(name)}" ${required ? "required" : ""}>${options.map((x) => `<option value="${h(x[0])}" ${String(x[0]) === String(value) ? "selected" : ""}>${h(x[1])}</option>`).join("")}</select></div>`;
}
function check(name, value, text, checked = false) {
  return `<label><input type="checkbox" name="${h(name)}" value="${h(value)}" ${checked ? "checked" : ""}>${h(text)}</label>`;
}
function form(fields, onSubmit, text = "Lưu", extra = "") {
  const id = "f" + ++seq;
  forms.set(id, onSubmit);
  return `<form data-form="${id}">${fields}<div class="form-error" role="alert"></div><div class="stack"><button type="submit">${h(text)}</button>${extra}</div></form>`;
}
function panel(title, content, tools = "") {
  return `<section class="panel"><div class="panel-head"><h2>${h(title)}</h2>${tools}</div>${content || empty()}</section>`;
}
function empty(text = "Chưa có dữ liệu.") {
  return `<p class="empty">${h(text)}</p>`;
}
function table(caption, headers, rows) {
  return rows.length
    ? `<div class="table-wrap" role="region" aria-label="${h(caption)}" tabindex="0"><table><caption>${h(caption)}</caption><thead><tr>${headers.map((x) => `<th scope="col">${h(x)}</th>`).join("")}</tr></thead><tbody>${rows.map((r) => `<tr>${r.map((x) => `<td>${x ?? "—"}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`
    : empty();
}
function list(items) {
  return items.length
    ? `<div class="row-list">${items.map((i) => `<article class="row-item">${i}</article>`).join("")}</div>`
    : empty();
}
function heading(eyebrow, title, sub = "") {
  document.title = title + " — TeamSync";
  return `<h1>${h(title)}</h1>`;
}
function tabs(items) {
  return `<nav class="tabs" aria-label="Các phần">${items.map((x) => link(x[0], x[1], location.pathname + location.search === x[0] ? "active" : "")).join("")}</nav>`;
}
const payload = (f) => Object.fromEntries(new FormData(f)),
  nums = (f, n) => new FormData(f).getAll(n).map(Number);
async function api(method, path, body, options = {}) {
  let headers = {};
  if (method !== "GET") {
    headers["X-CSRF-Token"] = token;
    if (!(body instanceof FormData))
      headers["Idempotency-Key"] =
        options.key ||
        (interaction
          ? (interaction.keys ??= new Map()).get(path + JSON.stringify(body)) ||
            (() => {
              const key = crypto.randomUUID();
              interaction.keys.set(path + JSON.stringify(body), key);
              return key;
            })()
          : crypto.randomUUID());
  }
  if (body !== undefined && !(body instanceof FormData))
    headers["Content-Type"] = "application/json";
  let response;
  try {
    response = await fetch("/api/v1" + path, {
      method,
      headers,
      body:
        body instanceof FormData
          ? body
          : body === undefined
            ? undefined
            : JSON.stringify(body),
    });
  } catch (e) {
    throw Error("Mất kết nối. Nội dung được giữ lại; hãy thử gửi lại.");
  }
  const result = await response.json().catch(() => ({}));
  if (!response.ok) {
    const e = Error(result.error?.message || "Không thể xử lý yêu cầu");
    e.status = response.status;
    e.code = result.error?.code;
    if (response.status === 401 && location.pathname != "/login")
      location.href = "/login";
    throw e;
  }
  return result.data;
}
const get = (path) => api("GET", path),
  post = (path, body) => api("POST", path, body),
  patch = (path, body) => api("PATCH", path, body);
async function all(path) {
  let out = [],
    page = 1;
  do {
    const r = await get(
      path + (path.includes("?") ? "&" : "?") + "page_size=100&page=" + page,
    );
    out.push(...r.items);
    if (out.length >= r.total) break;
    page++;
  } while (page < 100);
  return out;
}
async function upload(path, f, body = null) {
  return new Promise((resolve, reject) => {
    const req = new XMLHttpRequest();
    req.open("POST", "/api/v1" + path);
    req.setRequestHeader("X-CSRF-Token", token);
    const progress = f.querySelector("progress");
    req.upload.onprogress = (e) => {
      if (progress && e.lengthComputable) {
        progress.hidden = false;
        progress.value = (e.loaded / e.total) * 100;
      }
    };
    req.onload = () => {
      let r;
      try {
        r = JSON.parse(req.responseText);
      } catch {
        reject(Error("Phản hồi không hợp lệ"));
        return;
      }
      if (req.status >= 200 && req.status < 300) resolve(r.data);
      else reject(Error(r.error?.message || "Tải file không thành công"));
    };
    req.onerror = () =>
      reject(Error("Tải file thất bại. Giữ file đã chọn và thử lại."));
    req.send(body || new FormData(f));
  });
}
function noticeMarkup(message,error=false){return `<div class="${error?'error':'success'} dismissable-notice" role="${error?'alert':'status'}"><span>${h(message)}</span><button type="button" data-dismiss-notice aria-label="Đóng thông báo">×</button></div>`;}
document.addEventListener('click',e=>{const b=e.target.closest('[data-dismiss-notice]');if(b){b.closest('.dismissable-notice').remove();document.querySelector('#content')?.focus();}});
function errorMessage(e) {
  notice.innerHTML = noticeMarkup(e.message,true);
  notice.scrollIntoView({ block: "nearest" });
}
function refFields(revisions, value = {}, prefix = "") {
  return (
    select(
      prefix + "revision_id",
      "Phiên bản minh chứng",
      [
        ["", "Chọn phiên bản"],
        ...revisions.map((r) => [
          r.id,
          "Phiên bản " + r.revision_no + " · " + r.description,
        ]),
      ],
      value.revision_id || "",
      false,
    ) +
    field(
      prefix + "locator",
      "Vị trí nội dung (trang, sheet, mục)",
      "text",
      value.locator || "",
      "",
      false,
    )
  );
}
function refs(b, prefix = "") {
  return b[prefix + "revision_id"]
    ? [
        {
          revision_id: Number(b[prefix + "revision_id"]),
          locator: b[prefix + "locator"],
        },
      ]
    : [];
}
async function loginPage() {
  document.body.classList.add("login-page");
  const providers=await get("/auth/providers");
  return `<div class="login-layout"><section class="login-intro"><a class="brand" href="/login"><span class="brand-mark">T<span>✦</span></span><span>TeamSync<small>Không gian học tập</small></span></a><div class="login-story"><span class="login-kicker">CÙNG NHAU TIẾN BỘ</span><h1>Mỗi dự án,<br>một hành trình chung.</h1><p>Một không gian gọn gàng để cùng làm việc, theo dõi tiến độ và ghi nhận đóng góp.</p><div class="login-illustration" aria-hidden="true"><div class="illustration-heading"><span></span><span></span><span></span></div><div class="illustration-line wide"></div><div class="illustration-row"><div><i></i><i></i></div><div><i></i><i></i></div><div><i></i><i></i></div></div><div class="illustration-progress"><span></span></div></div></div><small class="login-note">TEAMSYNC · DỰ ÁN HỌC TẬP</small></section><section class="login-form-panel"><span class="login-kicker">CHÀO MỪNG TRỞ LẠI</span><h2>Đăng nhập</h2><p>Đăng nhập để tiếp tục với nhóm của bạn.</p>${form(
    field("email", "Email", "email") +
      field("password", "Mật khẩu", "password"),
    async (f) => {
      await post("/auth/login", payload(f));
      location.href = "/home";
    },
    "Đăng nhập",
  )}${providers.google?'<a class="button secondary" href="/api/v1/auth/google">Đăng nhập bằng email trường</a>':""}</section></div>`;
}
function scopePath(course,assignment,project,base=location.pathname) {
  const params=new URLSearchParams();if(course)params.set("course",course);if(assignment)params.set("assignment",assignment);if(project)params.set("project",project);
  return base+"?"+params;
}
function statusChart(tasks) {
  const states=["todo","in_progress","review","done"],colors=["#68778c","#3569ad","#a76a15","#23815b"],total=tasks.length;
  let offset=0;const segments=states.map((state,i)=>{const n=tasks.filter(t=>t.status===state).length,fraction=total?n/total:0;const circle=`<circle cx="70" cy="70" r="53" fill="none" stroke="${colors[i]}" stroke-width="15" pathLength="100" stroke-dasharray="${fraction*100} ${100-fraction*100}" stroke-dashoffset="${-offset}" transform="rotate(-90 70 70)"/>`;offset+=fraction*100;return circle;}).join("");
  return `<div class="scope-chart"><svg viewBox="0 0 140 140" role="img" aria-label="${total} công việc: ${states.map(x=>label(x)+': '+tasks.filter(t=>t.status===x).length).join(', ')}"><circle cx="70" cy="70" r="53" fill="none" stroke="#edf0f4" stroke-width="15"/>${segments}<text x="70" y="68" text-anchor="middle" class="chart-total">${total}</text><text x="70" y="86" text-anchor="middle" class="chart-caption">công việc</text></svg><div class="chart-legend">${states.map((state,i)=>`<a href="#scope-work" data-state-link="${state}"><i style="background:${colors[i]}"></i><span>${h(label(state))}</span><strong>${tasks.filter(t=>t.status===state).length}</strong></a>`).join("")}</div></div>`;
}
let personalItems=[];
let personalFilter={q:'',course:'',group:'',bucket:'active',page:0};
const personalBuckets={ready:'Cần làm',in_progress:'Đang làm',later:'Chưa cần làm',review:'Chờ duyệt',done:'Đã hoàn thành'};
async function personalTasksPage(){
 const first=await get('/me/tasks?page_size=100');personalItems=[...first.items];
 for(let page=2;personalItems.length<first.total;page++)personalItems.push(...(await get(`/me/tasks?page_size=100&page=${page}`)).items);
 const courses=[...new Map(personalItems.map(t=>[t.course.id,t.course])).values()],groups=[...new Map(personalItems.map(t=>[t.project.id,{...t.project,course:t.course,assignment:t.assignment}])).values()];
 const params=new URLSearchParams(location.search);if(params.has('course'))personalFilter.course=params.get('course');if(params.has('project'))personalFilter.group=params.get('project');
 if(!courses.some(c=>String(c.id)===personalFilter.course))personalFilter.course='';if(!groups.some(p=>String(p.id)===personalFilter.group))personalFilter.group='';
 const done=personalItems.filter(t=>t.status==='done').length,pct=personalItems.length?Math.round(done*100/personalItems.length):0;
 return `<div id="personal-workview"><div class="personal-heading"><div><p class="eyebrow">KHÔNG GIAN CÁ NHÂN</p><h1>Công việc của tôi</h1><p>Chỉ những việc bạn được giao hoặc cùng thực hiện trong các nhóm của mình.</p></div><div class="personal-progress"><strong>${done}/${personalItems.length} việc hoàn thành · ${pct}%</strong><progress value="${done}" max="${personalItems.length||1}"></progress></div></div><div class="personal-filter-bar"><input data-personal-search aria-label="Tìm công việc của tôi" placeholder="Tìm tên công việc, bài tập hoặc nhóm…" value="${h(personalFilter.q)}"><select data-personal-course aria-label="Lọc lớp học phần"><option value="">Tất cả lớp học phần</option>${courses.map(c=>`<option value="${c.id}" ${String(c.id)===personalFilter.course?'selected':''}>${h(c.code)} · ${h(c.title)}</option>`).join('')}</select><select data-personal-group aria-label="Lọc nhóm"><option value="">Tất cả nhóm của tôi</option>${groups.map(p=>`<option value="${p.id}" data-course="${p.course.id}" ${String(p.id)===personalFilter.group?'selected':''}>${h(p.course.code)} · ${h(p.name)} · ${h(p.assignment.title)}</option>`).join('')}</select></div><nav class="personal-state-tabs" aria-label="Trạng thái công việc của tôi"><button type="button" data-personal-bucket="active">Đang cần theo dõi <strong data-personal-count="active"></strong></button>${Object.entries(personalBuckets).map(([k,v])=>`<button type="button" data-personal-bucket="${k}">${v} <strong data-personal-count="${k}"></strong></button>`).join('')}</nav><div class="personal-caption"><p data-personal-description></p><span data-personal-result aria-live="polite"></span></div><section class="personal-task-list" data-personal-list aria-label="Danh sách việc cá nhân"></section><div class="scope-pagination" data-personal-pager><button type="button" class="secondary" data-personal-page="-1" aria-label="Trang trước">←</button><span data-personal-page-label></span><button type="button" class="secondary" data-personal-page="1" aria-label="Trang sau">→</button></div></div>`;
}
function updatePersonalTasks(reset=false){
 const page=view.querySelector('#personal-workview');if(!page)return;if(reset)personalFilter.page=0;
 const q=personalFilter.q.toLocaleLowerCase('vi'),base=personalItems.filter(t=>(!personalFilter.course||String(t.course.id)===personalFilter.course)&&(!personalFilter.group||String(t.project.id)===personalFilter.group)&&`${t.title} ${t.assignment.title} ${t.project.name} ${t.course.code}`.toLocaleLowerCase('vi').includes(q));
 for(const b of page.querySelectorAll('[data-personal-bucket]')){const k=b.dataset.personalBucket,n=base.filter(t=>k==='active'?['ready','in_progress','review'].includes(t.bucket):t.bucket===k).length;b.querySelector('strong').textContent=n;b.classList.toggle('selected',personalFilter.bucket===k);b.setAttribute('aria-pressed',String(personalFilter.bucket===k));}
 const filtered=base.filter(t=>personalFilter.bucket==='active'?['ready','in_progress','review'].includes(t.bucket):t.bucket===personalFilter.bucket).sort((a,b)=>Number(b.is_overdue)-Number(a.is_overdue)||(a.due_at||'9999').localeCompare(b.due_at||'9999'));
 const pages=Math.max(1,Math.ceil(filtered.length/10));personalFilter.page=Math.max(0,Math.min(pages-1,personalFilter.page));
 page.querySelector('[data-personal-description]').textContent=personalFilter.bucket==='later'?'Chưa mở bài tập hoặc còn chờ công việc phụ thuộc. Không xếp việc vào đây chỉ vì hạn nộp còn xa.':'Đếm theo bộ lọc hiện tại. Chọn công việc để xem chi tiết và cập nhật kết quả.';
 page.querySelector('[data-personal-result]').textContent=`${filtered.length} công việc`;
 page.querySelector('[data-personal-list]').innerHTML=filtered.slice(personalFilter.page*10,personalFilter.page*10+10).map(t=>{
  const step={todo:0,in_progress:1,review:2,done:3}[t.status]||0;
  const action=t.bucket==='ready'?btn('Bắt đầu làm',()=>post(`/tasks/${t.id}/start`,{version:t.version}),true):link(`/tasks/${t.id}${t.status==='in_progress'?'/submit':''}`,t.status==='in_progress'?'Gửi review':t.status==='review'?'Xem bản nộp':t.status==='done'?'Xem kết quả':'Xem chi tiết','button secondary');
  return `<article class="personal-task" data-personal-task="${t.id}"><div class="personal-task-main"><div class="row-title"><h2>${link('/tasks/'+t.id,t.title)}</h2><span class="badge ${h(t.status)}">${h(personalBuckets[t.bucket])}</span>${t.is_overdue?'<span class="badge high">Quá hạn</span>':''}</div><p class="personal-task-context">${h(t.course.code)} · ${h(t.assignment.title)} · ${link(`/projects/${t.project.id}?tab=studio`,t.project.name)}</p><p class="meta">${t.participation==='responsible'?'Bạn phụ trách':'Bạn cùng thực hiện'} · Hạn ${dt(t.due_at)}</p>${t.blocked_by.length?`<p class="task-blocked">Chờ: ${t.blocked_by.map(x=>h(x.title)).join(', ')}</p>`:t.before_open?`<p class="task-blocked">Bài tập mở từ ${dt(t.assignment.opens_at)}</p>`:''}<div class="task-stage" aria-label="Tiến độ quy trình: ${h(label(t.status))}">${['Cần làm','Đang làm','Chờ duyệt','Hoàn thành'].map((name,i)=>`<span class="${i<=step?'reached':''}">${name}</span>`).join('')}</div></div><div class="personal-task-action">${action}</div></article>`;
 }).join('')||empty('Không có việc cá nhân khớp bộ lọc. Công việc của thành viên khác không xuất hiện ở đây.');
 const pager=page.querySelector('[data-personal-pager]');pager.hidden=pages<=1;pager.querySelector('[data-personal-page-label]').textContent=`${personalFilter.page+1} / ${pages}`;pager.querySelector('[data-personal-page="-1"]').disabled=personalFilter.page===0;pager.querySelector('[data-personal-page="1"]').disabled=personalFilter.page===pages-1;
 for(const option of page.querySelector('[data-personal-group]').options)if(option.value){option.disabled=!!personalFilter.course&&option.dataset.course!==personalFilter.course;option.hidden=option.disabled;}
}
document.addEventListener('input',e=>{if(e.target.matches('[data-personal-search]')){personalFilter.q=e.target.value;updatePersonalTasks(true);}});
document.addEventListener('change',e=>{if(e.target.matches('[data-personal-course]')){personalFilter.course=e.target.value;personalFilter.group='';view.querySelector('[data-personal-group]').value='';updatePersonalTasks(true);}if(e.target.matches('[data-personal-group]')){personalFilter.group=e.target.value;updatePersonalTasks(true);}});
document.addEventListener('click',e=>{const b=e.target.closest('[data-personal-bucket]'),p=e.target.closest('[data-personal-page]');if(b){personalFilter.bucket=b.dataset.personalBucket;updatePersonalTasks(true);}if(p){personalFilter.page+=Number(p.dataset.personalPage);updatePersonalTasks();}});

async function home() { return me?.role==="admin"?operationsPage():learningWorkspace(); }
async function learningWorkspace() {
  const courses=await all("/courses"),q=new URLSearchParams(location.search);
  const course=courses.find(c=>String(c.id)===q.get("course"))||courses[0];
  if(!course)return heading("Không gian học tập","Chào "+me.full_name)+empty("Bạn chưa tham gia lớp học phần. Các lớp được phân công sẽ xuất hiện tại đây.");
  const teacher=staff(course.my_role), assignments=await all(`/courses/${course.id}/assignments`);
  const assignment=assignments.find(a=>String(a.id)===q.get("assignment"))||assignments[0];
  const projects=assignment?await all(`/assignments/${assignment.id}/projects`):[];
  const project=projects.find(p=>String(p.id)===q.get("project"))||projects[0];
  const tasks=project?await all(`/projects/${project.id}/tasks`):[];
  const active=tasks.filter(t=>t.status!=="done"), done=tasks.filter(t=>t.status==="done").length,percent=tasks.length?Math.round(done/tasks.length*100):0;
  const own=tasks.filter(t=>t.primary_assignee_id===me.id||t.assignee_id===me.id||t.participants?.some(x=>x.user_id===me.id));
  const focus=teacher?active:active.filter(t=>own.some(x=>x.id===t.id));
  const counts=[{label:"Tiến độ nhóm",value:percent+"%",sub:`${done}/${tasks.length} việc hoàn thành`},{label:teacher?"Đang thực hiện":"Việc của tôi",value:teacher?active.length:own.filter(t=>t.status!=="done").length,sub:project?.name||"Chưa có nhóm"},{label:"Đợi review",value:tasks.filter(t=>t.status==="review").length,sub:"Trưởng nhóm xử lý"}];
  const groupBars=projects.map(p=>{const mine=p.id===project?.id;return `<a class="scope-group ${mine?"selected":""}" href="${scopePath(course.id,assignment.id,p.id)}"><span class="scope-group-icon">${h(p.name.slice(0,3))}</span><span><strong>${h(p.name)}</strong><small>${p.members.filter(m=>m.status==="active").length} thành viên · ${h(label(p.my_role))}</small></span><span aria-hidden="true">→</span></a>`;}).join("");
  const contribution=project?.members.filter(m=>m.status==="active").map(m=>{const assigned=tasks.filter(t=>t.primary_assignee_id===m.user_id||t.assignee_id===m.user_id||t.participants?.some(x=>x.user_id===m.user_id&&x.role==="responsible")),finished=assigned.filter(t=>t.status==="done").length,pct=assigned.length?Math.round(finished*100/assigned.length):0;return `<div class="scope-member"><span>${h(m.user.full_name)}</span><div class="scope-bar" role="meter" aria-label="${h(m.user.full_name)}: tiến độ công việc" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${pct}"><i style="width:${pct}%"></i></div><strong>${finished}/${assigned.length}</strong></div>`;}).join("");
  const rows=[...tasks].sort((a,b)=>(a.due_at||"9999").localeCompare(b.due_at||"9999")).map(t=>`<a class="scope-task" data-scope-task data-mine="${own.some(x=>x.id===t.id)?"yes":"no"}" data-state="${h(t.status)}" href="/tasks/${t.id}"><span class="task-indicator ${h(t.status)}"></span><span class="scope-task-title"><strong>${h(t.title)}</strong><small>${h(t.participants?.find(x=>x.role==="responsible")?.user?.full_name||project?.name||"")}</small></span><span class="focus-status ${h(t.status)}">${h(label(t.status))}</span><time>${t.due_at?new Intl.DateTimeFormat("vi-VN",{day:"2-digit",month:"2-digit"}).format(new Date(t.due_at)):"—"}</time></a>`).join("");
  const workspaceMarkup=`<div id="learning-workspace"><div class="scope-welcome"><div><p class="eyebrow">${teacher?"GÓC GIẢNG VIÊN":"KHÔNG GIAN SINH VIÊN"}</p><h1>${"Chào "+h(me.full_name)+" ✦"}</h1><p>Chọn một lớp, theo dõi một nhóm. Mọi việc đều ở đúng chỗ.</p></div>${me.demo_clock?'<span class="demo-pill">Demo sẵn dữ liệu</span>':""}</div><nav class="scope-courses" aria-label="Chọn lớp học phần">${courses.map(c=>`<a href="${scopePath(c.id)}" class="${c.id===course.id?"selected":""}" ${c.id===course.id?'aria-current="true"':""}><span>${h(c.code)}</span><strong>${h(c.title)}</strong><small>${h(c.term)}</small></a>`).join("")}</nav><section class="scope-context" aria-label="Phạm vi đang xem"><div><label for="scope-assignment">Bài tập nhóm</label><select id="scope-assignment" data-scope-select="assignment" data-course="${course.id}">${assignments.map(a=>`<option value="${a.id}" ${a.id===assignment?.id?"selected":""}>${h(a.title)}</option>`).join("")||'<option>Chưa có bài tập</option>'}</select></div><div><label for="scope-project">Nhóm thực hiện</label><select id="scope-project" data-scope-select="project" data-course="${course.id}" data-assignment="${assignment?.id||""}">${projects.map(p=>`<option value="${p.id}" ${p.id===project?.id?"selected":""}>${h(p.name)}</option>`).join("")||'<option>Chưa có nhóm</option>'}</select></div>${project?link(`/projects/${project.id}?tab=studio`,teacher?"Xem tiến độ nhóm →":"Mở bảng Kanban →","button"):link(`/courses/${course.id}`,"Mở lớp học phần","button")}</section><section class="scope-metrics">${counts.map(x=>`<article><span>${h(x.label)}</span><strong>${h(x.value)}</strong><small>${h(x.sub)}</small></article>`).join("")}</section><div class="scope-dashboard"><section class="workspace-card scope-work" id="scope-work"><div class="workspace-card-head"><div><p class="eyebrow">${h(course.code)} / ${h(project?.name||"Chưa có nhóm")}</p><h2>${teacher?"Nhóm cần thực hiện":"Tập trung hôm nay"}</h2></div>${link(teacher?(project?`/projects/${project.id}?tab=studio&pane=board`:`/courses/${course.id}`):scopePath(course.id,assignment?.id,project?.id,"/my-tasks"),teacher?"Bảng công việc nhóm →":"Tất cả việc của tôi →")}</div><div class="catalog-filters"><input data-scope-search placeholder="Tìm công việc trong nhóm…" aria-label="Tìm công việc"><select data-scope-status aria-label="Lọc trạng thái"><option value="">Tất cả trạng thái</option><option value="open" selected>Chưa hoàn thành</option>${["todo","in_progress","review","done"].map(x=>`<option value="${x}">${h(label(x))}</option>`).join("")}</select>${!teacher?`<select data-scope-owner aria-label="Phạm vi người làm"><option value="all">Toàn nhóm</option><option value="mine" selected>Việc của tôi</option></select>`:""}</div><div class="scope-task-list">${rows||'<div class="workspace-empty">Chưa có việc cần làm trong phạm vi này.</div>'}</div><div class="scope-pagination" data-scope-pagination hidden><button type="button" class="secondary" data-scope-page="-1" aria-label="Trang trước">←</button><span data-scope-page-label aria-live="polite"></span><button type="button" class="secondary" data-scope-page="1" aria-label="Trang sau">→</button></div><p class="scope-no-results" hidden>Không có công việc khớp bộ lọc.</p><footer class="scope-footnote">${assignment?link(`/assignments/${assignment.id}/groups`,assignment.title):"Chưa có bài tập"} ${assignment?`<span>Hạn bài tập: ${dt(assignment.due_at)}</span>`:""}</footer></section><aside class="scope-insights"><section class="workspace-card"><div class="workspace-card-head"><h2>Nhịp độ nhóm</h2>${project?link(`/projects/${project.id}?tab=studio&pane=summary`,"Chi tiết →"):""}</div>${statusChart(tasks)}<details class="scope-chart-data"><summary>Xem bảng số liệu</summary>${table("Trạng thái công việc",["Trạng thái","Số việc"],["todo","in_progress","review","done"].map(x=>[h(label(x)),tasks.filter(t=>t.status===x).length]))}</details></section><section class="workspace-card"><div class="workspace-card-head"><h2>Tiến độ theo thành viên</h2></div><p class="meta">Số việc hoàn thành / Số việc được giao</p>${contribution||empty("Nhóm chưa có thành viên.")}</section></aside></div><details class="scope-other-groups"><summary>Các nhóm trong bài tập · ${projects.length}</summary><div class="scope-group-list">${groupBars||empty("Chưa có nhóm.")}</div></details></div>`;
  return workspaceMarkup;
}
let scopeTaskPage=0;
function filterScopeTasks(reset=true){
  if(reset)scopeTaskPage=0;
  const q=(view.querySelector('[data-scope-search]')?.value||'').toLocaleLowerCase('vi'),state=view.querySelector('[data-scope-status]')?.value,mine=view.querySelector('[data-scope-owner]')?.value==='mine';
  const rows=[...view.querySelectorAll('[data-scope-task]')],matched=rows.filter(row=>row.textContent.toLocaleLowerCase('vi').includes(q)&&(!state||(state==='open'?row.dataset.state!=='done':row.dataset.state===state))&&(!mine||row.dataset.mine==='yes'));
  const pageSize=6;
  const pages=Math.max(1,Math.ceil(matched.length/pageSize));scopeTaskPage=Math.min(Math.max(0,scopeTaskPage),pages-1);
  for(const row of rows)row.hidden=true;matched.slice(scopeTaskPage*pageSize,scopeTaskPage*pageSize+pageSize).forEach(row=>row.hidden=false);
  const empty=view.querySelector('.scope-no-results');if(empty)empty.hidden=!!matched.length||!rows.length;
  const pager=view.querySelector('[data-scope-pagination]');if(pager){pager.hidden=pages<=1;pager.querySelector('[data-scope-page-label]').textContent=`${scopeTaskPage+1} / ${pages} · ${matched.length} công việc`;pager.querySelector('[data-scope-page="-1"]').disabled=scopeTaskPage===0;pager.querySelector('[data-scope-page="1"]').disabled=scopeTaskPage===pages-1;}
}
document.addEventListener('click',e=>{const btn=e.target.closest('[data-scope-page]');if(btn){scopeTaskPage+=Number(btn.dataset.scopePage);filterScopeTasks(false);}});
document.addEventListener('input',e=>{if(e.target.matches('[data-scope-search]'))filterScopeTasks();});
document.addEventListener('change',e=>{if(e.target.matches('[data-scope-status],[data-scope-owner]'))filterScopeTasks();if(e.target.matches('[data-scope-select]')){const el=e.target;if(el.dataset.scopeSelect==='course'){navigate(scopePath(el.value));return;}navigate(scopePath(el.dataset.course,el.dataset.scopeSelect==='assignment'?el.value:el.dataset.assignment,el.dataset.scopeSelect==='project'?el.value:null));}});
document.addEventListener('click',e=>{const a=e.target.closest('[data-state-link]');if(a){e.preventDefault();e.stopImmediatePropagation();const select=view.querySelector('[data-scope-status]');select.value=a.dataset.stateLink;const owner=view.querySelector("[data-scope-owner]");if(owner)owner.value="all";filterScopeTasks();view.querySelector('#scope-work')?.scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth',block:'nearest'});select.focus();}},true);

function staffCalendarMarkup(items) {
  const events = (items || []).map(n => ({...n, due_at:n.created_at, event_path:n.target_path || "/notifications"})).filter(n => n.due_at);
  const y=calendarMonth.getFullYear(), m=calendarMonth.getMonth();
  const first=new Date(y,m,1), start=(first.getDay()+6)%7, days=new Date(y,m+1,0).getDate();
  const byDay=new Map();
  events.forEach(n=>{const k=dateKey(n.due_at); if(!byDay.has(k)) byDay.set(k,[]); byDay.get(k).push(n);});
  const names=["T2","T3","T4","T5","T6","T7","CN"];
  let cells=names.map(n=>`<div class="calendar-weekday">${n}</div>`).join("");
  for(let i=0;i<start;i++) cells+=`<div class="calendar-empty"></div>`;
  for(let day=1;day<=days;day++){
    const key=`${y}-${String(m+1).padStart(2,"0")}-${String(day).padStart(2,"0")}`, list=byDay.get(key)||[];
    const listHtml=list.length?list.map(n=>`<a href="${h(n.event_path)}" class="calendar-event"><strong>${h(n.title || "Thông báo")}</strong><span>${h(n.body || "")}</span><small>${dt(n.created_at)}</small></a>`).join(""):`<p class="calendar-no-events">Không có thông báo trong ngày này.</p>`;
    cells+=`<div class="calendar-cell ${list.length?"has-deadline":""}"><button type="button" class="calendar-day ${list.length?"deadline-day":""}" aria-label="${day}/${m+1}/${y}, ${list.length} thông báo">${day}${list.length?`<span>${list.length}</span>`:""}</button>${list.length?`<div class="calendar-popover"><strong>${day}/${m+1}/${y} · ${list.length} thông báo</strong>${listHtml}</div>`:""}</div>`;
  }
  return `<div class="calendar-head"><button type="button" class="secondary" data-calendar-shift="-1" aria-label="Tháng trước">‹</button><h3>${new Intl.DateTimeFormat("vi-VN",{month:"long",year:"numeric"}).format(first)}</h3><button type="button" class="secondary" data-calendar-shift="1" aria-label="Tháng sau">›</button></div><div class="calendar-grid">${cells}</div><p class="calendar-legend"><span></span> Ngày có thông báo/công việc của tài khoản</p>`;
}

function dateKey(value) {
  if (!value) return "";
  const d = new Date(new Date(value).getTime() + 7 * 3600000);
  return d.toISOString().slice(0,10);
}
function calendarMarkup(tasks) {
  const y=calendarMonth.getFullYear(), m=calendarMonth.getMonth();
  const first=new Date(y,m,1), start=(first.getDay()+6)%7, days=new Date(y,m+1,0).getDate();
  const byDay=new Map();
  tasks.filter(t=>t.due_at).forEach(t=>{const k=dateKey(t.due_at); if(!byDay.has(k)) byDay.set(k,[]); byDay.get(k).push(t);});
  const names=["T2","T3","T4","T5","T6","T7","CN"];
  let cells=names.map(n=>`<div class="calendar-weekday">${n}</div>`).join("");
  for(let i=0;i<start;i++) cells+=`<div class="calendar-empty"></div>`;
  for(let day=1;day<=days;day++){
    const key=`${y}-${String(m+1).padStart(2,"0")}-${String(day).padStart(2,"0")}`, items=byDay.get(key)||[];
    const listHtml=items.length?items.map(t=>`<a href="/tasks/${t.id}" class="calendar-event"><strong>${h(t.title)}</strong><span>${h(t.course_code||"")}${t.project_name?" · Nhóm "+h(t.project_name):""}</span><small>${dt(t.due_at)} · ${h(label(t.status))}</small></a>`).join(""):`<p class="calendar-no-events">Không có deadline trong ngày này.</p>`;
    cells+=`<div class="calendar-cell ${items.length?"has-deadline":""}"><button type="button" class="calendar-day ${items.length?"deadline-day":""}" aria-label="${day}/${m+1}/${y}, ${items.length} deadline">${day}${items.length?`<span>${items.length}</span>`:""}</button>${items.length?`<div class="calendar-popover"><strong>${day}/${m+1}/${y} · ${items.length} deadline</strong>${listHtml}</div>`:""}</div>`;
  }
  return `<div class="calendar-head"><button type="button" class="secondary" data-calendar-shift="-1" aria-label="Tháng trước">‹</button><h3>${new Intl.DateTimeFormat("vi-VN",{month:"long",year:"numeric"}).format(first)}</h3><button type="button" class="secondary" data-calendar-shift="1" aria-label="Tháng sau">›</button></div><div class="calendar-grid">${cells}</div><p class="calendar-legend"><span></span> Ngày có deadline · Rê chuột hoặc chạm vào ngày để xem công việc</p>`;
}
function filteredDashboardTasks() {
  const q=(document.querySelector("#task-search")?.value||"").trim().toLocaleLowerCase("vi"), status=document.querySelector("#task-status-filter")?.value||"", assignee=document.querySelector("#task-assignee-filter")?.value||"", priority=document.querySelector("#task-priority-filter")?.value||"", due=document.querySelector("#task-due-filter")?.value||"", now=new Date(), end=new Date(now.getTime()+7*86400000);
  return dashboardTasks.filter(t=>{const d=t.due_at?new Date(t.due_at):null; return (!q||t.title.toLocaleLowerCase("vi").includes(q))&&(!status||t.status===status)&&(!assignee||t.assignee===assignee)&&(!priority||t.priority===priority)&&(!due||(due==="nodate"?!d:due==="overdue"?!!d&&d<now:!!d&&d>=now&&d<=end));});
}
function taskRows(tasks, expanded = dashboardExpanded.tasks) {
  const visible = expanded ? tasks : tasks.slice(0, 5);
  const rows = visible.length ? `<div class="task-list">${visible.map(t=>{const meta=[t.course_code,t.project_name?"Nhóm "+t.project_name:"",t.assignee?"Phụ trách: "+t.assignee:"","Hạn "+dt(t.due_at),"Khối lượng "+h(t.points)].filter(Boolean).join(" · "), warnings=(t.warnings||[]).map(w=>`<span class="badge ${h(w.severity||"medium")}">${h(w.message)}</span>`).join(""); return `<a class="card-link task-card" href="/tasks/${t.id}"><div class="row-title"><strong>${h(t.title)}</strong>${badge(t.status)}</div><div class="task-meta">${h(meta)}</div><div class="task-card-tags">${badge(t.priority||"medium")}${t.is_my_task?`<span class="badge">Việc của tôi</span>`:""}</div>${warnings?`<div class="task-warnings">${warnings}</div>`:""}</a>`;}).join("")}</div>`:empty("Không có công việc phù hợp với bộ lọc.");
  const controls = tasks.length > 5 ? `<div class="dashboard-list-controls"><span>${expanded ? `Đang hiển thị tất cả ${tasks.length} công việc` : `Hiển thị 5/${tasks.length} công việc`}</span><button type="button" class="secondary" data-dashboard-expand="tasks">${expanded ? "Ẩn" : "Hiển thị tất cả"}</button></div>` : "";
  return rows + controls;
}
function actionQueueMarkup(items, expanded = dashboardExpanded.actions) {
  const visible = expanded ? items : items.slice(0, 5);
  const content = visible.length ? list(visible.map((x) => `<div class="row-title">${link(x.path, x.title)}${badge(x.severity || x.status)}</div><small>${x.kind === "help" ? "Yêu cầu hỗ trợ" : "Cảnh báo"} · ${dt(x.at)}</small>`)) : empty("Hiện không có cảnh báo hoặc yêu cầu nào cần xử lý.");
  const controls = items.length > 5 ? `<div class="dashboard-list-controls"><span>${expanded ? `Đang hiển thị tất cả ${items.length} mục` : `Hiển thị 5/${items.length} mục`}</span><button type="button" class="secondary" data-dashboard-expand="actions">${expanded ? "Ẩn" : "Hiển thị tất cả"}</button></div>` : "";
  return content + controls;
}


async function courseList() {
  const cs=await all("/courses");
  const canCreate=staff(me.role)||me.enrollments?.some(e=>staff(e.role)&&e.status==="active");
  const create=canCreate?btn("+ Tạo lớp học phần",()=>modal("Tạo lớp học phần",form(field("code","Mã lớp")+field("title","Môn học / Tên lớp")+field("term","Học kỳ"),async f=>{const c=await post("/courses",payload(f));return "/courses/"+c.id+"?tab=roster";},"Tạo lớp"))):"";
  const filter=`<div class="catalog-filters"><input data-catalog-search placeholder="Tìm mã lớp hoặc môn học…" aria-label="Tìm lớp"><select data-catalog-term aria-label="Lọc học kỳ"><option value="">Tất cả học kỳ</option>${[...new Set(cs.map(c=>c.term))].map(t=>`<option>${h(t)}</option>`).join("")}</select></div>`;
  return `<div class="catalog-heading"><div><p class="eyebrow">KHÔNG GIAN HỌC TẬP</p><h1>Lớp học phần</h1><p>Mở lớp để xem dự án, thành viên và tiến độ.</p></div>${create}</div>${filter}<section class="catalog-grid">${cs.map((c,i)=>`<a class="catalog-card" data-term="${h(c.term)}" href="/courses/${c.id}"><span class="catalog-icon project-color-${i%4}">${h((c.code||"LH").slice(0,2))}</span><div><span class="catalog-code">${h(c.code)}</span><h2>${h(c.title)}</h2><p>${h(c.term||"")}</p></div><footer><span class="catalog-role">${h(label(c.my_role))}</span><span>Chi tiết lớp →</span></footer></a>`).join("")||'<div class="workspace-empty">Bạn chưa tham gia lớp học phần nào.</div>'}</section>`;
}

async function coursePage(cid, section) {
  const c = await get("/courses/" + cid),
    as = await all("/courses/" + cid + "/assignments");
  let nav = tabs([
    ["/courses/" + cid, "Bài tập nhóm"],
    ...(staff(c.my_role) ? [["/courses/" + cid + "?tab=roster", staff(c.my_role) ? "Quản lý sinh viên" : "Danh sách sinh viên"]] : []),
    
    ...(staff(c.my_role) ? [["/courses/" + cid + "/risk-cases", "Theo dõi rủi ro"]] : []),
  ]);
  let html = heading(c.term, c.code + " · " + c.title, label(c.my_role)) + nav;
  if (section === "risk") {
    const risks = await all("/courses/" + cid + "/risk-cases");
    html += panel(
      "Hàng đợi hỗ trợ",
      table(
        "Cảnh báo theo phạm vi",
        ["Mức độ", "Nguyên nhân", "Người phụ trách", "Trạng thái", "Xem lại"],
        risks.map((r) => [
          badge(r.severity),
          link("/risk-cases/" + r.id, r.reason_json.message),
          h(r.owner?.full_name || "Chưa phân công"),
          badge(r.status),
          dt(r.next_review_at),
        ]),
      ),
      "",
    );
    return html;
  }
  if (section === "import") return html + (await importPage(cid));
  if (
    new URLSearchParams(location.search).get("tab") === "roster" &&
    staff(c.my_role)
  ) {
    const es = (await all("/courses/"+cid+"/enrollments")).filter(e=>e.role==="student");
    const groupLists=await Promise.all(as.map(a=>all("/assignments/"+a.id+"/projects")));
    const groups=groupLists.flat();
    const groupNames=uid=>groups.filter(g=>(g.members||[]).some(m=>m.user_id===uid)).map(g=>g.name).join(", ")||"Chưa xếp nhóm";
    const manual=()=>modal("Thêm sinh viên",form(field("student_code","Mã sinh viên")+field("full_name","Họ tên")+field("email","Email","email"),f=>post("/courses/"+cid+"/students",payload(f)),"Thêm sinh viên"));
    html+=panel("Danh sách lớp",table("Danh sách sinh viên",["Họ tên","Mã sinh viên","Nhóm","Trạng thái","Thao tác"],es.map(e=>[h(e.user.full_name),h(e.student_code||"—"),h(groupNames(e.user_id)),badge(e.status),`<div class="stack">${btn("Chỉnh sửa",()=>modal("Chỉnh sửa sinh viên",form(field("full_name","Họ tên","text",e.user.full_name)+field("student_code","Mã sinh viên","text",e.student_code||""),f=>patch("/enrollments/"+e.id,{...payload(f),version:e.version}),"Lưu")),true)}${btn("Xóa",async()=>{if(!confirm("Rút sinh viên khỏi lớp?"))return false;return post("/enrollments/"+e.id+"/withdraw",{version:e.version,reason:"Giảng viên rút sinh viên khỏi lớp"});},true)}</div>`])),btn("Nhập danh sách sinh viên",()=>modal("Nhập danh sách sinh viên",`<p>Chọn phương thức nhập danh sách lớp.</p><div class="stack">${btn("Nhập thủ công",manual)}${link("/courses/"+cid+"/imports/new","Tải file theo mẫu","button secondary")}</div>`)));
    return html;
  }
  if (staff(c.my_role)) {
    const o = await get("/courses/" + cid + "/overview");
    html += panel(
      "Cần theo dõi",
      `<div class="stack">${link("/courses/" + cid + "/risk-cases", o.risk_cases + " cảnh báo cần xử lý", "button secondary")}<span>${o.pending_reviews} bản nộp đang chờ duyệt</span></div>`,
    );
  }
  html += panel(
    "Bài tập nhóm trong học phần",
    list(
      as.map(
        (a) =>
          `<div class="row-title">${link("/assignments/" + a.id + "/groups", a.title)}${assignmentBadge(a)}</div><p>Hạn ${dt(a.due_at)}</p><div class="stack">${link("/assignments/" + a.id + "/policy", "Bộ tiêu chí")}${staff(c.my_role) ? "" : link("/assignments/" + a.id + "/portfolio/" + me.id, "Hồ sơ đóng góp")}${staff(c.my_role) ? "" : link("/assignments/" + a.id + "/my-result", "Kết quả")}</div>`,
      ),
    ),
    c.my_role==="instructor"?btn("+ Tạo mới và thiết lập đề bài",()=>assignmentEditor(cid)):"",
  );
  return html;
}
async function importPage(cid) {
  const bid = new URLSearchParams(location.search).get("batch");
  let html = panel(
    "Nhập danh sách sinh viên",
    `<p>CSV UTF-8 gồm ba cột: student_code,full_name,email. Xem trước và đối soát trước khi ghi dữ liệu.</p><a href="data:text/csv;charset=utf-8,student_code%2Cfull_name%2Cemail%0ASV001%2CNguyen%20Van%20A%2Csv001%40example.test%0A" download="mau-danh-sach.csv">Tải mẫu CSV</a>${form(
      field("file", "Chọn CSV hoặc Excel (.xlsx)", "file"),
      async (f) => {
        const b = await api(
          "POST",
          "/courses/" + cid + "/imports/preview",
          new FormData(f),
        );
        return location.pathname + "?batch=" + b.id;
      },
      "Xem trước",
    )}`,
  );
  if (bid) {
    const b = await get("/imports/" + bid);
    html += panel(
      "Đối soát trước khi nhập",
      `<p>${b.counts.total} dòng · ${b.counts.errors} dòng lỗi · ${h(label(b.status))}</p>` +
        table(
          "Nội dung CSV",
          ["Dòng", "Mã", "Họ tên", "Email", "Lỗi"],
          b.rows.map((r) => [
            r.row_no,
            h(r.normalized_json.student_code),
            h(r.normalized_json.full_name),
            h(r.normalized_json.email),
            h(r.errors_json.join("; ") || "Hợp lệ"),
          ]),
        ) +
        (!b.counts.errors && b.status !== "committed"
          ? btn("Xác nhận nhập toàn bộ", () =>
              post("/imports/" + b.id + "/commit", { version: b.version }),
            )
          : ""),
    );
  }
  return html;
}
function criterionEditor(c, i) {
  const levels =
    c.levels?.length === 4
      ? c.levels
      : [
          { label: "Chưa đạt", score: 0, description: "" },
          { label: "Đạt", score: 5, description: "" },
          { label: "Tốt", score: 8, description: "" },
          { label: "Xuất sắc", score: 10, description: "" },
        ];
  return `<fieldset data-criterion-row="${i}"><legend>Tiêu chí ${i + 1}</legend><div class="criteria-row">${field("code" + i, "Mã", "text", c.code)}${field("title" + i, "Tiêu chí", "text", c.title)}${field("weight" + i, "Trọng số %", "number", c.weight)}</div>${area("description" + i, "Nội dung đánh giá", c.description || "")}${area("evidence" + i, "Minh chứng cần có", c.evidence_requirement || "")}<details><summary>Các mức đánh giá</summary>${levels.map((l, j) => field("level_label" + i + "_" + j, "Tên mức " + (j + 1), "text", l.label) + `<input type="hidden" name="level_score${i}_${j}" value="${h(l.score)}">` + area("level_description" + i + "_" + j, "Hành vi ở mức " + (j + 1), l.description)).join("")}</details><button type="button" class="secondary" data-remove-criterion>Bỏ tiêu chí này</button></fieldset>`;
}
document.addEventListener("click", (e) => {
  if (e.target.closest("[data-add-criterion]")) {
    const editor = e.target
      .closest("form")
      .querySelector("[data-criteria-editor]");
    const indices = Array.from(
      editor.querySelectorAll("[data-criterion-row]"),
    ).map((x) => Number(x.dataset.criterionRow));
    const i = indices.length ? Math.max(...indices) + 1 : 0;
    editor.insertAdjacentHTML(
      "beforeend",
      criterionEditor({ code: "C" + (i + 1), title: "", weight: 1 }, i),
    );
    dirty = true;refreshRubricTotal();
  }
  if (e.target.closest("[data-remove-criterion]")) {
    e.target.closest("[data-criterion-row]").remove();
    dirty = true;refreshRubricTotal();
  }
});
async function uploadAssignmentFiles(aid,input){
  if(!input?.files?.length)return;
  const files=[...input.files];if(files.length>10)throw Error("Mỗi lần chọn tối đa 10 file");
  if(files.some(f=>f.size>10*1024*1024))throw Error("Mỗi file tối đa 10 MB");
  const data=new FormData();for(const file of files)data.append("files",file);
  return api("POST",`/assignments/${aid}/files`,data);
}
function allocationFields(roster,a={},recovery=false) {
  return `<fieldset data-teacher-allocation data-recovery="${recovery&&a.formation_due_at&&new Date(a.formation_due_at)<=new Date(me.business_time)?"true":"false"}" hidden><legend>Xếp nhóm theo danh sách lớp</legend>${select("method","Cách chia nhóm",[["random","Xếp ngẫu nhiên"],["roster_cycle","Theo danh sách lớp · Đánh số lặp 1…N"]],a.group_method||"random")}<p class="meta">Số nhóm = làm tròn lên (số sinh viên chưa có nhóm / số người tối đa mỗi nhóm). Chia lặp số nhóm từ trên xuống dưới.</p><div data-roster-preview data-roster="${h(JSON.stringify(roster))}"></div></fieldset>`;
}
function syncFormationModal(){
  const dialog=document.querySelector('#ux-modal');if(!dialog)return;
  const mode=dialog.querySelector('[name=group_mode]');if(!mode)return;
  const teacher=mode.value==='teacher',due=dialog.querySelector('[name=formation_due_at]'),extra=dialog.querySelector('[data-teacher-allocation]');
  if(due){due.disabled=teacher;due.required=!teacher;due.closest('div').classList.toggle('muted-field',teacher);}
  if(extra){const show=teacher||extra.dataset.recovery==="true";extra.hidden=!show;extra.disabled=!show;}
  const preview=dialog.querySelector('[data-roster-preview]');if(!preview)return;
  const roster=JSON.parse(preview.dataset.roster),size=Math.max(1,Math.min(50,Number(dialog.querySelector('[name=team_size],[name=group_max]')?.value)||1)),count=Math.ceil(roster.length/size),method=dialog.querySelector('[name=method]')?.value;
  preview.innerHTML=`<p><strong>${roster.length} sinh viên chưa có nhóm · ${count} nhóm dự kiến</strong></p>${table("Danh sách xếp nhóm dự kiến",["STT","Mã sinh viên","Họ tên","Nhóm dự kiến"],roster.map((e,i)=>[i+1,h(e.student_code||"—"),h(e.user.full_name),method==='roster_cycle'?`G${String(i%count+1).padStart(2,'0')}`:"Ngẫu nhiên khi xác nhận"]))}`;
}
async function formationRoster(cid,aid=null){
  const roster=(await all(`/courses/${cid}/enrollments`)).filter(e=>e.role==='student'&&e.status==='active');
  const groups=aid?await all(`/assignments/${aid}/projects`):[],assigned=new Set(groups.flatMap(p=>p.members.filter(m=>m.status==='active').map(m=>m.user_id)));
  return roster.filter(e=>!assigned.has(e.user_id)).sort((a,b)=>((a.student_code||'')<(b.student_code||'')?-1:(a.student_code||'')>(b.student_code||'')?1:a.id-b.id));
}
async function assignmentEditor(cid,a=null){
  const roster=await formationRoster(cid,a?.id);
  return modal(a?"Chỉnh sửa đề bài":"Tạo mới và thiết lập đề bài",form(
    field("title","Tên bài tập nhóm","text",a?.title||"")+area("brief","Yêu cầu đề bài",a?.brief||"")+
    `<div class="grid equal">${field("opens_at","Mở bài tập","datetime-local",localInput(a?.opens_at||new Date().toISOString()))}${field("due_at","Hạn nộp bài","datetime-local",localInput(a?.due_at))}</div>`+
    `<div class="grid equal">${field("group_min","Tối thiểu sinh viên / nhóm","number",a?.group_min||1)}${field("group_max","Tối đa sinh viên / nhóm","number",a?.group_max||5)}</div>`+
    select("group_mode","Cách lập nhóm",[["self","Sinh viên tự lập nhóm"],["teacher","Giảng viên xếp nhóm"]],a?.group_mode||"self")+field("formation_due_at","Hạn tự lập nhóm","datetime-local",localInput(a?.formation_due_at),"Chỉ dùng khi sinh viên tự lập nhóm",false)+allocationFields(roster,a||{})+
    '<p class="meta">Với đề bài mới do giảng viên xếp nhóm, nhóm được tạo ngay khi lưu. Sinh viên thấy nhóm sau khi công bố. Những lần xếp bổ sung thực hiện ở Tổ chức nhóm.</p><label>Tài liệu bổ trợ (chọn nhiều file)<input type="file" name="support_files" multiple accept=".pdf,.docx,.xlsx,.pptx,.png,.jpg,.jpeg,.txt,.zip"></label>',
    async f=>{const b=payload(f);let aid=a?.id||f.dataset.createdAssignment;
      const due=b.group_mode==='teacher'?null:a?.formation_due_at&&Math.floor(new Date(a.formation_due_at).getTime()/60000)===Math.floor(new Date(utc(b.formation_due_at)).getTime()/60000)?a.formation_due_at:utc(b.formation_due_at);
      const data={title:b.title,brief:b.brief,opens_at:utc(b.opens_at),due_at:utc(b.due_at),group_min:Number(b.group_min),group_max:Number(b.group_max),group_mode:b.group_mode,formation_due_at:due,...(b.method?{method:b.method}:{})};
      if(a){a=await patch(`/assignments/${aid}`,{...data,version:a.version});}
      else if(!aid){const created=await post(`/courses/${cid}/assignments`,data);aid=created.id;f.dataset.createdAssignment=aid;}
      try{await uploadAssignmentFiles(aid,f.elements.support_files);}catch(err){throw Error("Đề bài đã lưu; tài liệu chưa tải được: "+err.message+". Có thể thử lại hoặc đính kèm sau.");}
      return `/assignments/${aid}/${!a&&b.group_mode==='teacher'?'groups':'settings'}`;
    },"Lưu đề bài",'<button type="button" data-cancel-modal class="secondary">Hủy</button>'));
}
async function organizationModal(a){
  const roster=await formationRoster(a.course_id,a.id);
  return modal("Tổ chức nhóm",form('<p>Chỉ xếp sinh viên chưa có nhóm; giữ nguyên phân công hiện có.</p>'+select("group_mode","Tổ chức nhóm",[["self","Sinh viên tự lập nhóm trong thời hạn"],["teacher","Giảng viên xếp từ đầu"]],a.group_mode||"self")+
    field("team_size","Số sinh viên tối đa mỗi nhóm","number",a.group_max)+field("formation_due_at","Hạn tự lập nhóm","datetime-local",localInput(a.formation_due_at),"Hết hạn, giảng viên xếp những sinh viên còn lại.",false)+allocationFields(roster,a,true)+
    '<p class="meta">Nếu tự lập đã hết hạn, nút xác nhận sẽ xếp ngẫu nhiên những sinh viên còn lại. Nhóm thiếu mức tối thiểu được đánh dấu.</p>',
    async(f,button)=>{const b=payload(f),allocate=button?.value==="random";
      const due=b.group_mode==='teacher'?null:a.formation_due_at&&Math.floor(new Date(a.formation_due_at).getTime()/60000)===Math.floor(new Date(utc(b.formation_due_at)).getTime()/60000)?a.formation_due_at:utc(b.formation_due_at);
      const changed=b.group_mode!==(a.group_mode||'self')||Number(b.team_size)!==a.group_max||due!==(a.formation_due_at||null)||b.method&&b.method!==a.group_method;
      if(changed||b.group_mode==='teacher'&&!allocate)a=await patch(`/assignments/${a.id}/organization`,{version:a.version,group_mode:b.group_mode,team_size:Number(b.team_size),formation_due_at:due,...(b.method?{method:b.method}:{})});
      if(allocate&&!a.new_group_count)await post(`/assignments/${a.id}/teams/generate`,{team_size:Number(b.team_size),method:b.method||'random'});
    },"Lưu cách tổ chức",'<button type="submit" name="intent" value="random">Xác nhận xếp nhóm</button><button type="button" data-cancel-modal class="secondary">Hủy</button>'));
}
document.addEventListener('change',e=>{if(e.target.closest('#ux-modal')&&e.target.matches('[name=group_mode],[name=method]'))syncFormationModal();});
document.addEventListener('input',e=>{if(e.target.closest('#ux-modal')&&e.target.matches('[name=team_size],[name=group_max]'))syncFormationModal();});
function assignmentBadge(a){return `<span class="badge ${a.is_hidden?'draft':'published'}">${a.status==='draft'?'Bản nháp':a.is_hidden?'Đã ẩn':'Công khai'}</span>`;}
async function assignmentEvaluations(a){
  const rounds=(await get(`/assignments/${a.id}/evaluation-rounds`)).items;
  const selected=rounds.find(r=>String(r.id)===new URLSearchParams(location.search).get("round"))||rounds[0];
  const create=()=>modal("Tạo đợt đánh giá",form(field("title","Tên đợt","text",`Đánh giá lần ${rounds.length+1}`)+field("opens_at","Mở từ","datetime-local",localInput(new Date().toISOString()))+field("closes_at","Đóng lúc","datetime-local"),f=>{const b=payload(f);return post(`/assignments/${a.id}/evaluation-rounds`,{title:b.title,opens_at:utc(b.opens_at),closes_at:utc(b.closes_at)});},"Tạo đợt"));
  return panel("Các đợt đánh giá",`<div class="evaluation-round-list">${rounds.map(r=>link(`/assignments/${a.id}/evaluations?round=${r.id}`,r.title+" · "+({open:"Đang mở",scheduled:"Sắp mở",closed:"Đã đóng"}[r.phase]),r.id===selected?.id?"button":"button secondary")).join("")||empty("Chưa có đợt đánh giá.")}</div>`,btn("+ Tạo đợt đánh giá",create))+(selected?panel(selected.title,`<p>${dt(selected.opens_at)} → ${dt(selected.closes_at)}</p><section class="scope-metrics"><article><span>Phiếu đã gửi</span><strong>${selected.response_count}</strong></article><article><span>Phiếu dự kiến theo nhóm hiện tại</span><strong>${selected.expected_count}</strong></article><article><span>Tỷ lệ phản hồi</span><strong>${selected.expected_count?Math.round(selected.response_count*100/selected.expected_count):0}%</strong></article></section>${table("Chi tiết kết quả theo thành viên",["Sinh viên","Nhóm","Đã gửi","Được đánh giá","Thái độ /10","Chất lượng /10"],selected.items.map(x=>[h(x.user.full_name),h(x.group_name),x.sent,x.received,x.attitude??"—",x.quality??"—"]))}`,selected.phase!=="closed"?btn("Đóng đợt",async()=>{if(!confirm("Đóng đợt đánh giá này?"))return false;return post(`/evaluation-rounds/${selected.id}/close`,{version:selected.version});},true):""):"");
}
function assignmentNav(a) {
  return tabs([
    ["/assignments/" + a.id + "/groups", "Nhóm và công việc"],
    ["/assignments/" + a.id + "/policy", "Bộ tiêu chí"],
    ["/assignments/" + a.id + "/settings", "Yêu cầu đề bài"],
    ...(staff(a.my_role)?[["/assignments/"+a.id+"/evaluations","Đánh giá"]]:[]),
    ...(!staff(a.my_role)
      ? [["/assignments/" + a.id + "/portfolio/" + me.id, "Hồ sơ đóng góp"]]
      : []),
  ]);
}
function weightGuide(){return '<div class="weight-guide"><strong>Trọng số = tỷ lệ ảnh hưởng vào điểm tổng</strong><p>Ví dụ: Nội dung 60%, trình bày 40%. Nếu hai tiêu chí được 8 và 9 điểm, điểm tổng = 8 × 60% + 9 × 40% = <strong>8,4/10</strong>. Tổng trọng số phải bằng 100% trước khi công bố.</p></div>';}
function rubricEditor(a,p,append=false){
 const cs=(p?.criteria||[]).map(c=>({...c}));if(!cs.length)cs.push({code:'C1',title:'',weight:100});else if(append){let n=cs.length+1;while(cs.some(c=>c.code==='C'+n))n++;cs.push({code:'C'+n,title:'',weight:1});}
 return modal(append?'Thêm tiêu chí':'Chỉnh sửa bộ tiêu chí',form(weightGuide()+`<p class="rubric-weight-total" data-rubric-weight-total>Tổng trọng số: ${cs.reduce((n,c)=>n+Number(c.weight||0),0)} / 100%</p><div data-criteria-editor>${cs.map((c,i)=>criterionEditor(c,i)).join('')}</div><button type="button" class="secondary" data-add-criterion>+ Thêm một tiêu chí</button>`,async f=>{
   const b=payload(f),criteria=[...f.querySelectorAll('[data-criterion-row]')].map(row=>{const i=row.dataset.criterionRow;return {code:b['code'+i],title:b['title'+i],weight:b['weight'+i],description:b['description'+i],evidence_requirement:b['evidence'+i],levels:[0,1,2,3].map(j=>({label:b['level_label'+i+'_'+j],score:b['level_score'+i+'_'+j],description:b['level_description'+i+'_'+j]}))};});
   if(p?.status==='draft')await patch(`/policies/${p.id}`,{version:p.version,criteria});else await post(`/assignments/${a.id}/policies`,{criteria});
 },'Lưu bộ tiêu chí','<button type="button" data-cancel-modal class="secondary">Hủy</button>'));
}
function refreshRubricTotal(){const f=document.querySelector('#ux-modal form'),out=f?.querySelector('[data-rubric-weight-total]');if(out){const n=[...f.querySelectorAll('input[name^="weight"]')].reduce((sum,x)=>sum+(Number(x.value)||0),0);out.textContent=`Tổng trọng số: ${Number(n.toFixed(2))} / 100%${Math.abs(n-100)>.001?' · Cần điều chỉnh trước khi công bố':''}`;out.classList.toggle('needs-attention',Math.abs(n-100)>.001);}}
document.addEventListener('input',e=>{if(e.target.matches('#ux-modal input[name^="weight"]'))refreshRubricTotal();});
async function policyView(a){
 const p=a.policies.at(-1),editable=a.my_role==='instructor'&&a.status==='draft';
 const controls=editable?`<div class="assignment-heading-actions">${p?btn('Chỉnh sửa',()=>rubricEditor(a,p),true):''}${btn('+ Thêm tiêu chí',()=>rubricEditor(a,p,true))}${btn('Nhập Excel',()=>modal('Nhập bộ tiêu chí từ Excel',`<p>${link(`/api/v1/assignments/${a.id}/rubric-template`,'Tải file mẫu Excel')}</p>`+form(field('file','Chọn file .xlsx','file'),async f=>{const preview=await api('POST',`/assignments/${a.id}/rubric-preview`,new FormData(f));rubricImports.set(a.id,preview.criteria);},'Xem trước')),true)}</div>`:'';
 let html=panel(p?`Bộ tiêu chí · Phiên bản ${p.revision}`:'Bộ tiêu chí',weightGuide()+(p?`<p>${badge(p.status)} · ${p.criteria.length} tiêu chí · Tổng trọng số ${p.criteria.reduce((sum,c)=>sum+Number(c.weight),0)}%</p>`+table('Bộ tiêu chí đã lưu',['Tiêu chí','Yêu cầu','Trọng số (%)','Minh chứng'],p.criteria.map(c=>[h(c.title),h(c.description),`<strong>${h(c.weight)}%</strong>`,h(c.evidence_requirement)]))+p.criteria.map(c=>`<details class="criterion-levels"><summary>${h(c.title)} · Các mức đánh giá</summary>${table('Mức đánh giá',['Mức','Điểm /10','Mô tả'],c.levels.map(l=>[h(l.label),h(l.score),h(l.description)]))}</details>`).join(''):empty('Chưa có tiêu chí. Bấm Thêm tiêu chí ở góc phải để bắt đầu.')),controls);
 if(editable&&p?.status==='draft')html+=panel('Hoàn tất bộ tiêu chí','<p>Bản nháp đã được lưu và hiển thị ở trên. Kiểm tra tổng trọng số và mô tả các mức trước khi công bố.</p>',btn('Công bố bộ tiêu chí',()=>post(`/policies/${p.id}/publish`,{version:p.version})));
 const imported=rubricImports.get(a.id);if(editable&&imported)html+=panel('Xem trước dữ liệu Excel',table('Tiêu chí nhập',['Mã','Tiêu chí','Trọng số'],imported.map(c=>[h(c.code),h(c.title),h(c.weight)+'%'])),btn('Lưu bộ tiêu chí nhập',async()=>{if(p?.status==='draft')await patch(`/policies/${p.id}`,{version:p.version,criteria:imported});else await post(`/assignments/${a.id}/policies`,{criteria:imported});rubricImports.delete(a.id);}));
 return html;
}
async function assignmentPage(aid, section) {
  const a = await get("/assignments/" + aid);
  let html =
    `<div class="breadcrumbs">${link("/courses/" + a.course_id, "Lớp học phần")} / Đề bài</div>` +
    heading("Dự án học tập", a.title, "Hạn cuối " + dt(a.due_at)) +
    assignmentNav(a);
  if (section === "evaluations") return html+await assignmentEvaluations(a);
  if (section === "policy") return html+await policyView(a);
  if (section === "settings") {
    const files=(await get(`/assignments/${aid}/files`)).items;
    const canEdit=a.my_role==='instructor'&&['draft','published','active'].includes(a.status);
    const tools=a.my_role==='instructor'&&['draft','published','active','assessment'].includes(a.status)?`<div class="assignment-heading-actions">${canEdit?btn('Chỉnh sửa',()=>assignmentEditor(a.course_id,a),true):""}${btn(a.status==='draft'||a.is_hidden?'Công bố đề bài':'Ẩn đề bài',()=>post(`/assignments/${aid}/visibility`,{version:a.version,visible:a.status==='draft'||a.is_hidden}))}</div>`:"";
    html=html+panel("Yêu cầu đề bài",`<p class="preserve">${h(a.brief)}</p><p>${assignmentBadge(a)} · Nhóm ${a.group_min}–${a.group_max} người</p>${a.status==='draft'&&a.my_role==='instructor'&&!a.published_policy_id?`<p class="meta">Cần công bố ${link(`/assignments/${aid}/policy`,"bộ tiêu chí")} trước khi công bố đề bài.</p>`:""}`,tools);
    html+=panel("Tài liệu bổ trợ",files.length?`<ul class="assignment-files">${files.map(f=>`<li><a href="${h(f.download_url)}" download>${h(f.name)}</a><small>${Math.ceil(f.size_bytes/1024)} KB</small></li>`).join("")}</ul>`:empty("Chưa có tài liệu đính kèm."),a.my_role==="instructor"&&["draft","published","active"].includes(a.status)?btn("+ Đính kèm file",()=>modal("Thêm tài liệu đề bài",form('<label>Chọn file<input name="files" type="file" multiple required></label>',f=>uploadAssignmentFiles(aid,f.elements.files),"Tải lên")),true):"");
    return html;
  }
  const groups = await all("/assignments/" + aid + "/projects");
  const canOrganize=a.my_role==="instructor"&&["draft","published","active"].includes(a.status);
  const closed=a.group_mode==="teacher"||a.formation_due_at&&new Date(a.formation_due_at)<=new Date(me.business_time);
  html+=panel("Nhóm thực hiện",`<p class="formation-summary">${a.group_mode==="teacher"?"Giảng viên tổ chức và phân công nhóm":`Sinh viên tự lập nhóm · Hạn: ${dt(a.formation_due_at)}`} · ${a.group_min}–${a.group_max} sinh viên/nhóm</p><div class="assignment-group-grid">${groups.map(p=>{const members=p.members.filter(m=>m.status==="active"),n=p.progress||{total:0,done:0},pct=n.total?Math.round(n.done*100/n.total):0;return `<article class="assignment-group-card"><div class="group-card-title"><span class="scope-group-icon">${h(p.name.slice(0,3))}</span><div><h2>${h(p.name)}</h2>${badge(p.status)}</div></div><p class="group-assignment-name">${h(a.title)}</p>${p.description?`<p class="meta">${h(p.description)}</p>`:""}<div class="group-card-count"><strong>${members.length}/${a.group_max} thành viên</strong><span>${pct}% hoàn thành</span></div><div class="scope-bar"><i style="width:${pct}%"></i></div><p class="meta">${n.done}/${n.total} công việc hoàn thành${members.length<a.group_min?" · Chưa đủ số thành viên tối thiểu":""}</p><details><summary>Xem thành viên</summary><ul>${members.map(m=>`<li>${h(m.user.full_name)} · ${h(label(m.role))}</li>`).join("")}</ul></details><footer>${link(`/projects/${p.id}?tab=studio`,"Mở không gian nhóm →","button")}</footer></article>`;}).join("")||empty("Chưa có nhóm. Hãy tổ chức nhóm hoặc lập nhóm trong thời hạn cho phép.")}</div>`,canOrganize?btn("Tổ chức nhóm",()=>organizationModal(a)):"");
  if(a.my_role==="student"&&!groups.length){
    if(!closed&&["published","active"].includes(a.status))html+=panel("Lập nhóm của bạn",`<p>Nhóm trưởng tạo nhóm và mời thành viên; mỗi sinh viên chỉ tham gia một nhóm trong bài tập này.</p>`,btn("+ Tạo nhóm",()=>modal("Tạo nhóm",form(field("name","Tên nhóm tự đặt")+area("description","Giới thiệu nhóm","",false),async f=>{const p=await post(`/assignments/${aid}/projects`,payload(f));return `/projects/${p.id}?tab=settings`;},"Tạo nhóm"))));
    else html+=panel("Phân công nhóm",'<p>Giảng viên sẽ xếp bạn vào nhóm. Bạn sẽ thấy nhóm tại đây sau khi được phân công.</p>');
  }
  return html;
}
async function projectPage(pid, board = false) {
  const p = await get("/projects/" + pid),
    tasks = await all("/projects/" + pid + "/tasks");
  document.title=p.name+" — TeamSync";
  const requestedTab=new URLSearchParams(location.search).get("tab")||"studio";
  const tab=requestedTab==="tasks"?"studio":requestedTab;
  const leader = p.my_role === "leader",
    teacher = staff(p.my_role),
    mutable = !["finalized", "archived"].includes(p.status);
  const legacySummary=['contributions','report'].includes(tab),requestedPane=new URLSearchParams(location.search).get('pane');
  if(tab==='studio'||legacySummary){
    const summary=legacySummary||['summary','report','insights'].includes(requestedPane);
    return `<div id="team-studio" data-pid="${pid}" ${summary?'data-start-pane="summary"':''} ${tab==='contributions'||tab==='changes'?'data-summary-section="reconcile"':tab==='report'?'data-summary-section="progress"':''}></div>`;
  }
  const stats={done:tasks.filter(t=>t.status==='done').length,total:tasks.length};
  const discussion=!teacher?`<a class="button discussion-launch" href="/projects/${pid}?tab=studio&pane=chat">Thảo luận & tài liệu</a>`:'';
  let html=groupHeader(p,stats)+groupNavigation(p,tab==='changes'?'contributions':tab,discussion);
  if (tab === "settings") return html + (await membersUI(p));
  if (tab === "help") return html + (await helpUI(p, tasks));
  if (tab === "changes") return html + (await changesUI(p, tasks));
  const done = tasks.filter((t) => t.status === "done").length;
  html += `<section class="stat-cards"><div><span>Công việc hoàn thành</span><strong>${done}/${tasks.length}</strong></div><div><span>Chờ duyệt</span><strong>${tasks.filter((t) => t.status === "review").length}</strong></div><div><span>Hạn bàn giao</span><strong class="date-stat">${dt(p.assignment.due_at)}</strong></div></section>`;
  if (board)
    html += `<section class="board" aria-label="Bảng công việc">${[
      "todo",
      "in_progress",
      "review",
      "done",
    ]
      .map(
        (status) =>
          `<div class="board-col"><h2>${h(label(status))}</h2>${tasks
            .filter((t) => t.status === status)
            .map(
              (t) =>
                `<a class="task-card card-link" href="/tasks/${t.id}"><strong>${h(t.title)}</strong><div class="meta">${t.participants.map((x) => h(x.user.full_name)).join(", ")}<br>Hạn ${dt(t.due_at)}</div></a>`,
            )
            .join("")}</div>`,
      )
      .join("")}</section>`;
  else {
    html += panel("Công việc", taskRows(tasks));
    html += panel(
      "Phân công và tiêu chí",
      table(
        "Kế hoạch nhóm",
        ["Công việc", "Người thực hiện", "Tiêu chí liên quan", "Khối lượng"],
        tasks.map((t) => [
          h(t.title),
          t.participants.map((x) => h(x.user.full_name)).join(", "),
          t.criteria.map((c) => h(c.title)).join(", "),
          h(t.points),
        ]),
      ),
    );
    const risks = (
      await all("/courses/" + p.assignment.course_id + "/risk-cases")
    ).filter(
      (r) =>
        r.project_id === pid && !["resolved", "dismissed"].includes(r.status),
    );
    if (risks.length)
      html += panel(
        "Cần chú ý",
        list(
          risks.map(
            (r) =>
              `<div class="row-title">${link("/risk-cases/" + r.id, r.reason_json.message)}${badge(r.severity)}</div>`,
          ),
        ),
      );
  }
  if (leader && mutable && p.status === "draft")
    html += panel(
      "Bắt đầu dự án",
      btn("Kích hoạt nhóm", () =>
        post("/projects/" + pid + "/activate", { version: p.version }),
      ),
    );
  if (leader && mutable && p.status === "active")
    html += panel(
      "Thêm công việc",
      `<details><summary>Tạo công việc mới</summary>${taskEditor(p)}</details>`,
    );
  return html;
}
function taskEditor(p) {
  return form(
    field("title", "Tên công việc") +
      area("description", "Yêu cầu và kết quả cần bàn giao") +
      select(
        "responsible",
        "Người phụ trách",
        p.members
          .filter((m) => m.status === "active")
          .map((m) => [m.user_id, m.user.full_name]),
      ) +
      `<fieldset><legend>Người cùng làm</legend>${p.members
        .filter((m) => m.status === "active")
        .map((m) => check("collaborators", m.user_id, m.user.full_name))
        .join("")}</fieldset>` +
      field("due_at", "Hạn hoàn thành (giờ Việt Nam)", "datetime-local") +
      select("priority", "Mức độ ưu tiên", [["low", "Thấp"], ["medium", "Trung bình"], ["high", "Cao"]], "medium") +
      select(
        "points",
        "Khối lượng công việc",
        [
          [1, "1 · Nhỏ"],
          [2, "2 · Vừa"],
          [3, "3 · Lớn"],
          [5, "5 · Rất lớn"],
        ],
        2,
      ) +
      `<fieldset><legend>Tiêu chí liên quan</legend>${p.criteria.map((c) => check("criteria", c.id, c.title)).join("")}</fieldset>`,
    async (f) => {
      const b = payload(f),
        uid = Number(b.responsible);
      const t = await post("/projects/" + p.id + "/tasks", {
        title: b.title,
        description: b.description,
        due_at: utc(b.due_at),
        priority: b.priority,
        points: Number(b.points),
        participants: [
          { user_id: uid, role: "responsible" },
          ...nums(f, "collaborators")
            .filter((x) => x !== uid)
            .map((user_id) => ({ user_id, role: "collaborator" })),
        ],
        criterion_ids: nums(f, "criteria"),
      });
      return "/tasks/" + t.id;
    },
    "Tạo công việc",
  );
}
async function membersUI(p){
 const teacher=staff(p.my_role),leader=p.my_role==='leader',members=p.members.filter(m=>m.status==='active');
 const edit=leader&&!['finalized','archived'].includes(p.status)?btn('Chỉnh sửa nhóm',()=>modal('Thông tin nhóm',form(field('name','Tên nhóm','text',p.name)+area('description','Mô tả',p.description||'',false),f=>patch(`/projects/${p.id}`,{version:p.version,...payload(f)}),'Lưu')),true):'';
 let html=panel(`Thành viên · ${members.length}/${p.assignment.group_max}`,`<p class="meta">${h(p.description||'Cùng theo dõi vai trò và phân công của nhóm.')}</p><div class="member-directory">${members.map(m=>`<article><span class="member-avatar">${h(m.user.full_name.split(' ').map(x=>x[0]).slice(-2).join(''))}</span><div><h3>${h(m.user.full_name)}</h3><p>${h(m.user.email||'')}</p><span class="badge ${h(m.role)}">${h(label(m.role))}</span></div></article>`).join('')}</div>`,edit);
 if(teacher)return html;
 const invs=await all(`/projects/${p.id}/invitations`),pending=invs.filter(i=>i.status==='pending');
 const mentors=invs.filter(i=>i.kind==='mentor'&&i.status==='accepted');
 if(mentors.length)html+=panel('Giảng viên hỗ trợ',list(mentors.map(i=>`<strong>${h(i.user.full_name)}</strong>`)));
 if(pending.length)html+=panel('Lời mời đang chờ',table('Lời mời',['Người nhận','Phạm vi','Trạng thái'],pending.map(i=>[h(i.user.full_name),i.kind==='member'?'Thành viên':'Giảng viên hỗ trợ',badge(i.status)])));
 if(leader&&!['finalized','archived'].includes(p.status)){
  const candidates=await get(`/assignments/${p.assignment_id}/invite-candidates`),actions=[];
  for(const [kind,title,people] of [['member','Mời thành viên',candidates.students],['mentor','Mời giảng viên hỗ trợ',candidates.instructors]]){
   if(kind==='member'&&(p.assignment.group_mode==='teacher'||p.assignment.formation_due_at&&new Date(p.assignment.formation_due_at)<=new Date(me.business_time)))continue;
   const choices=people.filter(u=>!invs.some(i=>i.user_id===u.id&&i.status!=='rejected'));
   if(choices.length)actions.push(btn(title,()=>modal(title,form(select('user_id','Chọn người nhận',choices.map(u=>[u.id,u.full_name+' · '+u.email])),f=>post(`/projects/${p.id}/invitations`,{version:p.version,kind,user_id:Number(payload(f).user_id)}),'Gửi lời mời')),true));
  }
  if(actions.length)html+=`<div class="section-actions">${actions.join('')}</div>`;
 }
 return html;
}
async function contributionUI(p, tasks,compact=false) {
  const report = compact?null:await get("/projects/" + p.id + "/report"),
    complaints = await all("/projects/" + p.id + "/complaints");
  let html=panel("Đối soát & phản ánh",'<p>Gửi phản ánh, giải trình và theo dõi quyết định phân bổ đóng góp.</p>');
  if(report)html+=reportSummary(report);
  for (const c of complaints) {
    const leader = p.my_role === "leader",
      teacher = staff(p.my_role),
      isHandler =
        c.handler === "instructor"
          ? teacher
          : leader && ![c.raised_by, c.target_id].includes(me.id);
    let content = `<div class="row-title"><strong>${h(c.task_title)} · ${h(c.target_name)}</strong>${badge(c.status)}</div><p>${h(c.raised_by_name)}: ${h(c.reason)}</p>`;
    if (c.explanation)
      content += `<div class="feedback"><strong>Giải trình</strong><p>${h(c.explanation)}</p></div>`;
    if (c.escalation_reason)
      content += `<p>Chuyển giảng viên: ${h(c.escalation_reason)}</p>`;
    if (c.resolution)
      content += `<div class="feedback"><strong>Kết luận</strong><p>${h(c.resolution)}</p></div>`;
    if (c.status === "open" && c.target_id === me.id)
      content += form(
        area("explanation", "Giải trình của bạn", c.explanation || ""),
        (f) =>
          post("/complaints/" + c.id + "/explain", {
            version: c.version,
            ...payload(f),
          }),
        "Gửi giải trình",
      );
    if (c.status === "open" && isHandler)
      content += form(
        `<fieldset><legend>Tỷ lệ đóng góp sau xử lý</legend>${Object.entries(
          c.shares,
        )
          .map(([uid, percent]) =>
            field(
              "share_" + uid,
              c.participants.find((x) => x.user.id === Number(uid))?.user
                .full_name || uid,
              "number",
              percent,
            ).replace(
              'type="number"',
              'type="number" min="0" max="100" step="0.01"',
            ),
          )
          .join("")}</fieldset>` +
          area("reason", "Kết luận và căn cứ điều chỉnh") +
          (!c.explanation
            ? check(
                "explanation_not_provided",
                "yes",
                "Đã tạo cơ hội giải trình nhưng thành viên chưa phản hồi",
              )
            : ""),
        (f) => {
          const b = payload(f);
          return post("/complaints/" + c.id + "/resolve", {
            version: c.version,
            reason: b.reason,
            explanation_not_provided: b.explanation_not_provided === "yes",
            shares: Object.fromEntries(
              Object.keys(c.shares).map((uid) => [uid, b["share_" + uid]]),
            ),
          });
        },
        "Lưu quyết định",
      );
    if (
      c.status === "open" &&
      c.handler === "leader" &&
      (leader || [c.raised_by, c.target_id].includes(me.id))
    )
      content += `<details><summary>Nhờ giảng viên hỗ trợ giải quyết</summary>${form(area("reason", "Lý do cần giảng viên hỗ trợ"), (f) => post("/complaints/" + c.id + "/escalate", { version: c.version, ...payload(f) }), "Chuyển giảng viên")}</details>`;
    html+=panel(h(c.task_title),`<div class="row-title"><strong>${h(c.target_name)}</strong>${badge(c.status)}</div><p>${h(c.reason)}</p>`,btn('Xem phản ánh',()=>modal('Chi tiết phản ánh đóng góp',content),true));
  }
  const shared = tasks.filter(
    (t) =>
      t.participants.length > 1 &&
      t.latest_submission_id &&
      t.participants.some((x) => x.user_id === me.id),
  );
  if(!shared.length&&!complaints.length)html+=empty('Chưa có phản ánh. Bạn có thể phản ánh khi công việc làm chung đã có bản nộp; phần Tổng hợp vẫn hiển thị toàn bộ số liệu đóng góp.');
  if(shared.length){const compose=form(
        select(
          "task_id",
          "Công việc làm chung",
          shared.map((t) => [t.id, t.title]),
        ).replace('name="task_id"', 'name="task_id" data-complaint-task') +
          select(
            "target_id",
            "Thành viên được phản ánh",
            shared[0].participants
              .filter((m) => m.user_id !== me.id)
              .map((m) => [m.user_id, m.user.full_name]),
          ) +
          area("reason", "Nội dung và căn cứ phản ánh"),
        (f) => {
          const b = payload(f);
          return post("/projects/" + p.id + "/complaints", {
            task_id: Number(b.task_id),
            target_id: Number(b.target_id),
            reason: b.reason,
          });
        },
        "Gửi phản ánh",
      ).replace(
        "<form ",
        `<form data-complaint-choices="${h(JSON.stringify(Object.fromEntries(shared.map((t) => [t.id, t.participants.filter((x) => x.user_id !== me.id).map((x) => ({ id: x.user_id, name: x.user.full_name }))]))))}" `,
      );html+=panel('Phản ánh đóng góp','<p>Gửi căn cứ cho công việc làm chung. Trưởng nhóm hoặc giảng viên hỗ trợ theo thẩm quyền.</p>',btn('Gửi phản ánh',()=>modal('Gửi phản ánh',compose),true));}
  return html;
}
function contributionTable(report) { return contributionMarkup(report); }
async function reportUI(p) {
  const r = await get("/projects/" + p.id + "/report");
  let html = panel(
    "Báo cáo nhóm",
    `${reportSummary(r)}<div class="stack report-actions">${link("/api/v1/projects/" + p.id + "/report/download", "Tải báo cáo / lưu PDF", "button")}${link("/api/v1/projects/" + p.id + "/report/download?format=xlsx", "Tải Excel", "button secondary")}</div>` +
      contributionTable(r),
  );
  html += '<div class="quality-grid">';
  for (const q of r.quality)
    html += panel(
      q.criterion.title,
      `<div class="row-title"><strong>${h(q.level_label)}</strong><span class="meta">Nhóm tự đánh giá</span></div>${q.evaluation ? `<p>${h(q.evaluation.rationale)}</p>` : ""}` +
        (p.my_role === "leader"
          ? `<details><summary>Đánh giá chất lượng</summary>${form(
              select(
                "level_id",
                "Mức chất lượng",
                q.levels.map((l) => [l.id, l.label]),
                q.evaluation?.level_id,
              ) +
                area(
                  "rationale",
                  "Nhận xét và căn cứ",
                  q.evaluation?.rationale || "",
                ),
              (f) =>
                post("/projects/" + p.id + "/quality", {
                  version: p.version,
                  criterion_id: q.criterion.id,
                  level_id: Number(payload(f).level_id),
                  rationale: payload(f).rationale,
                }),
              "Lưu đánh giá",
            )}</details>`
          : ""),
    );
  html += "</div>";
  const changes = r.allocation_history;
  if (changes.length)
    html += panel(
      "Lịch sử điều chỉnh đóng góp",
      list(
        changes.map(
          (x) =>
            `<strong>${h(x.decided_by_name)}</strong><p>${h(x.reason)}</p><small>${dt(x.created_at)}</small>`,
        ),
      ),
    );
  return html;
}
async function helpUI(p,tasks){
 const requests=await all(`/projects/${p.id}/help-requests`),teacher=staff(p.my_role),instructor=p.my_role==='instructor';
 const create=()=>modal('Gửi yêu cầu hỗ trợ',form(field('subject','Tiêu đề')+select('task_id','Phạm vi',[['group','Vấn đề chung của nhóm'],...tasks.map(t=>[t.id,t.title])])+area('content','Khó khăn và đề nghị hỗ trợ'),f=>{const b=payload(f);return post(`/projects/${p.id}/help-requests`,{subject:b.subject,content:b.content,scope:b.task_id==='group'?'group':'task',task_id:b.task_id==='group'?null:Number(b.task_id)});},'Gửi yêu cầu'));
 return panel('Yêu cầu hỗ trợ',`<p class="meta">Trao đổi chính thức với giảng viên. Chat nội bộ của nhóm vẫn được giữ riêng.</p><div class="support-list">${requests.map(x=>`<article><div class="row-title"><div><h3>${h(x.subject)}</h3><small>${dt(x.created_at)}</small></div>${badge(x.status)}</div><p class="preserve">${h(x.content)}</p>${x.response?`<div class="feedback"><strong>Giảng viên phản hồi</strong><p>${h(x.response)}</p></div>`:''}${instructor&&['submitted','under_review'].includes(x.status)?`<div class="section-actions">${btn('Xem & phản hồi',()=>modal(x.subject,`<p class="preserve">${h(x.content)}</p>`+form(area('response','Phản hồi',x.response||'')+check('resolve','yes','Đã hỗ trợ xong'),f=>post(`/help-requests/${x.id}/respond`,{version:x.version,response:payload(f).response,resolve:payload(f).resolve==='yes'}),'Gửi phản hồi')),true)}</div>`:''}</article>`).join('')||empty('Chưa có yêu cầu. Khi cần hỗ trợ, dùng nút Gửi yêu cầu ở góc phải.')}</div>`,!teacher?btn('+ Gửi yêu cầu',create):'');
}
async function changesUI(p, tasks) {
  const changes = await all("/projects/" + p.id + "/change-requests"),
    manage = p.my_role === "leader" || staff(p.my_role);
  let html = panel(
    "Đề nghị thay đổi",
    list(
      changes.map(
        (c) =>
          `<div class="row-title"><strong>${h(c.kind === "deadline" ? "Gia hạn công việc" : "Mở lại công việc")}</strong>${badge(c.status)}</div><p>${h(c.reason)}</p>${c.decision_reason ? `<p>${h(c.decision_reason)}</p>` : ""}${
            manage && c.status === "pending"
              ? form(
                  area("reason", "Lý do quyết định") +
                    select("action", "Quyết định", [
                      ["approve", "Chấp nhận"],
                      ["reject", "Từ chối"],
                    ]),
                  (f) =>
                    post("/change-requests/" + c.id + "/decide", {
                      version: c.version,
                      ...payload(f),
                    }),
                  "Lưu quyết định",
                )
              : ""
          }`,
      ),
    ),
  );
  if (!staff(p.my_role))
    html += panel(
      "Đề nghị mới",
      form(
        select(
          "task_id",
          "Công việc",
          tasks.map((t) => [t.id, t.title]),
        ) +
          select("kind", "Nội dung", [

            ["reopen", "Mở lại công việc"],
          ]) +
          area("reason", "Lý do"),
        (f) => {
          const b = payload(f);
          return post("/projects/" + p.id + "/change-requests", {
            task_id: Number(b.task_id),
            kind: b.kind,
            reason: b.reason,
            proposed: { reopen: true },
          });
        },
        "Gửi đề nghị",
      ),
    );
  return html;
}

function studentTaskEditor(t,p){ const tid=t.id; return modal("Chỉnh sửa công việc",form(
        field("title", "Tên nhiệm vụ", "text", t.title) +
          area("description", "Mô tả yêu cầu", t.description || "", false) +
          (t.status === "todo"
            ? select(
                "responsible",
                "Người chịu trách nhiệm",
                p.members
                  .filter((m) => m.status === "active")
                  .map((m) => [m.user_id, m.user.full_name]),
                t.primary_assignee_id,
              ) +
              `<fieldset><legend>Người cộng tác</legend>${p.members
                .filter((m) => m.status === "active")
                .map((m) =>
                  check(
                    "collaborators",
                    m.user_id,
                    m.user.full_name,
                    t.participants.some(
                      (x) =>
                        x.user_id === m.user_id && x.role === "collaborator",
                    ),
                  ),
                )
                .join(
                  "",
                )}</fieldset><fieldset><legend>Tiêu chí</legend>${p.criteria
                .map((c) =>
                  check(
                    "criteria",
                    c.id,
                    c.title,
                    t.criteria.some((x) => x.id === c.id),
                  ),
                )
                .join("")}</fieldset>` +
              select("priority", "Mức độ ưu tiên", [["low", "Thấp"], ["medium", "Trung bình"], ["high", "Cao"]], t.priority || "medium") +
              select(
                "points",
                "Khối lượng công việc",
                [
                  [1, "1"],
                  [2, "2"],
                  [3, "3"],
                  [5, "5"],
                ],
                t.points,
              )
            : ""),
        (f) => {
          const b = payload(f),
            body = {
              version: t.version,
              title: b.title,
              description: b.description,
            };
          if (t.status === "todo") {
            body.priority = b.priority;
            body.points = Number(b.points);
            const uid = Number(b.responsible);
            body.participants = [
              { user_id: uid, role: "responsible" },
              ...nums(f, "collaborators")
                .filter((x) => x !== uid)
                .map((user_id) => ({ user_id, role: "collaborator" })),
            ];
            body.criterion_ids = nums(f, "criteria");
          }
          return patch("/tasks/" + tid, body);
        },
        "Lưu nội dung nhiệm vụ",'<button type="button" data-cancel-modal class="secondary">Hủy</button>')); }

async function taskPage(tid, section) {
  const t = await get("/tasks/" + tid),
    p = await get("/projects/" + t.project_id);
  const isParticipant = t.participants.some((x) => x.user_id === me.id),
    canManage = p.my_role === "leader",
    mutable = !["finalized", "archived"].includes(p.status);
  let html =
    `<div class="breadcrumbs">${link("/assignments/" + p.assignment_id + "/groups", p.assignment.title)} / ${link("/projects/" + p.id, p.name)} / Nhiệm vụ</div>` +
    heading("Thực hiện dự án", t.title) +
    `<div class="stack">${badge(t.status)}<span class="meta">Hạn ${dt(t.due_at)}${t.due_at !== t.original_due_at ? " · Hạn gốc " + dt(t.original_due_at) : ""}</span></div>`;
  if (section === "submit")
    return html + (await submitUI(t, isParticipant && mutable));
  html +=
    `<div class="grid"><div>` +
    panel(
      "Nội dung công việc",
      `<p class="preserve">${h(t.description)}</p><div class="stack">${t.status === "todo" && isParticipant && mutable ? btn("Bắt đầu", () => post("/tasks/" + tid + "/start", { version: t.version })) : ""}${t.status === "in_progress" && isParticipant && mutable ? link("/tasks/" + tid + "/submit", "Tạo nhánh & gửi Merge Request", "button") : ""}${isParticipant && mutable ? link("/projects/" + p.id + "?tab=contributions", "Đóng góp và phản ánh", "button secondary") : ""}${!staff(p.my_role) ? link("/projects/" + p.id + "?tab=help", "Yêu cầu trợ giúp", "button secondary") : ""}</div>`,
      p.my_role==='leader'&&mutable?btn("Chỉnh sửa",()=>studentTaskEditor(t,p),true):"",
    );
  if (!staff(p.my_role)) html += panel("Bản nộp và kết quả duyệt", submissionRows(t, p, mutable));
  if (isParticipant && mutable && t.status!=="done") html += panel("Yêu cầu gia hạn", form(
    field("due_at","Hạn đề xuất (giờ Việt Nam)","datetime-local",localInput(t.due_at)) + area("reason","Lý do cần gia hạn"),
    f=>post(`/tasks/${tid}/extensions`,{due_at:utc(payload(f).due_at),reason:payload(f).reason}), "Gửi trưởng nhóm"));
  const comments = staff(p.my_role) ? [] : await all("/tasks/" + tid + "/comments");
  html += panel(
    "Trao đổi",
    list(
      comments.map(
        (c) =>
          `<strong>${h(c.user.full_name)}</strong><p>${h(c.content)}</p><small>${dt(c.created_at)}</small>`,
      ),
    ) +
      (mutable && !staff(p.my_role)
        ? form(
            area("content", "Nội dung trao đổi"),
            (f) => post("/tasks/" + tid + "/comments", payload(f)),
            "Gửi trao đổi",
          )
        : ""),
  );
  html += "</div><div>";
  if (isParticipant && mutable && t.status === "in_progress")
    html += panel(
      "Cập nhật tiến độ tự khai",
      form(
        area("content", "Kết quả và trở ngại (ít nhất 10 ký tự)"),
        (f) =>
          post("/tasks/" + tid + "/progress-checkins", {
            version: t.version,
            content: payload(f).content,
          }),
        "Gửi tiến độ",
      ),
    );
  if (canManage && mutable && !staff(p.my_role))
    html += panel(
      "Thay đổi công việc",
      link("/projects/" + p.id + "?tab=changes", "Đề nghị gia hạn hoặc mở lại"),
    );
  html += panel(
    "Diễn biến tiến độ",
    list(
      (t.timeline || []).map(
        (e) =>
          `<strong>${h(e.title)}</strong>${e.content ? `<p class="preserve">${h(e.content)}</p>` : ""}<small>${dt(e.created_at)}</small>`,
      ),
    ),
  );
  return html + "</div></div>";
}
function historyRows(items, row) {
  if (!items.length) return empty();
  const ordered = [...items].reverse();
  if (ordered.length === 1) return row(ordered[0]);
  const id = "history" + ++seq;
  return `${row(ordered[0])}<div class="history" data-history="${id}"><button type="button" class="secondary" data-show-history aria-controls="${id}" aria-expanded="false">Xem bản cũ</button><div id="${id}" hidden>${ordered.slice(1).map(row).join("")}<button type="button" class="secondary" data-hide-history>Ẩn bản cũ</button></div></div>`;
}
function assetLinks(assets) {
  return `<div class="asset-list">${assets.map((x) => link(x.download_url, x.original_filename || x.url, "button secondary")).join("")}</div>`;
}
function submissionRows(t, p, mutable) {
  return historyRows(t.submissions, (s) => {
    const r = t.revisions.find((r) => r.id === s.revision_id);
    const canReview = mutable && s.status === "pending" && p.my_role === "leader";
    return `<article class="submission-card"><div class="row-title"><div class="stack"><strong>Lần nộp ${s.attempt_no}</strong><span class="badge ${s.late ? "late" : "on-time"}">${s.late ? "Quá hạn" : "Đúng hạn"}</span></div>${badge(s.status)}</div><p class="preserve">${h(r?.description)}</p>${assetLinks(r?.assets || [])}${s.review_reason ? `<div class="feedback"><strong>Nhận xét</strong><p class="preserve">${h(s.review_reason)}</p></div>` : ""}${s.participant_names?.length ? `<p class="meta">Ghi nhận chung: ${s.participant_names.map(h).join(", ")}</p>` : ""}${canReview ? reviewForm(t, s) : ""}</article>`;
  });
}
function reviewForm(t, s) {
  const errorId = "review-error" + ++seq;
  return form(
    area("reason", "Nhận xét (bắt buộc khi yêu cầu sửa)", "", false) +
      `<p id="${errorId}" class="field-error" data-review-error role="alert"></p><input type="hidden" name="review_error_id" value="${errorId}">`,
    (f, button) =>
      post("/submissions/" + s.id + "/review", {
        version: t.version,
        action: button?.value || "accept",
        reason: payload(f).reason,
      }),
    "Duyệt hoàn thành",
    '<button type="submit" name="decision" value="return" class="secondary request-changes">Yêu cầu sửa</button>',
  ).replace("<form ", "<form data-review ");
}
function revisionRows(revisions) {
  const groups = new Map();
  for (const r of revisions) {
    if (!groups.has(r.task_id)) groups.set(r.task_id, []);
    groups.get(r.task_id).push(r);
  }
  return (
    [...groups.values()]
      .map((rs) =>
        historyRows(
          rs.sort((a, b) => a.revision_no - b.revision_no),
          (r) =>
            `<article class="submission-card"><strong>Lần nộp ${r.revision_no}</strong><p class="preserve">${h(r.description)}</p>${assetLinks(r.assets)}</article>`,
        ),
      )
      .join("") || empty()
  );
}
async function submitUI(t, allowed) {
  let html = `<div class="stack">${link("/tasks/" + t.id, "Quay lại công việc", "button secondary")}</div>`;
  if (!allowed || t.status !== "in_progress")
    return html + panel("Bản nộp", revisionRows(t.revisions));
  const previous = t.revisions.at(-1);
  const branchList = (await get(`/tasks/${t.id}/branches`)).items.filter(b=>b.author_id===me.id&&b.status==="open");
  return (
    html +
    panel(
      "Tạo nhánh & gửi Merge Request",
      form(
        field("branch_name", "Tên nhánh mới (hoặc chọn nhánh bên dưới)", "text", `work/task-${t.id}-${t.version}`, "Dùng chữ không dấu, số, /, -, _", false) +
        select("branch_id", "Nhánh hiện có", [["", "Tạo nhánh mới"], ...branchList.map(b=>[b.id,b.name])], "", false) +
        area("description", "Nội dung hoàn thành và thay đổi") +
          `<div class="dropzone" data-dropzone><label>File đính kèm<input name="files" type="file" multiple aria-label="File đính kèm"></label><p>Kéo thả file vào đây hoặc bấm để chọn · Tối đa 10 MiB/file</p><div data-file-list aria-live="polite"></div></div><progress max="100" value="0" hidden aria-label="Tiến độ tải file"></progress>` +
          field("url", "Liên kết sản phẩm", "url", "", "", false) +
          (previous
            ? `<fieldset><legend>Dùng lại file của bản gần nhất</legend>${previous.assets.map((x) => check("assets", x.id, x.original_filename || x.url)).join("")}</fieldset>`
            : ""),
        async (f) => {
          const b = payload(f),
            ids = nums(f, "assets");
          const files = Array.from(f.elements.files.files);
          if (!files.length && !b.url && !ids.length)
            throw Error("Bạn cần đính kèm file hoặc liên kết sản phẩm.");
          f.uploadedFiles ??= new Map();
          for (const file of files) {
            if (file.size > 10 * 1024 * 1024)
              throw Error("Mỗi file không được vượt quá 10 MiB.");
            if (!f.uploadedFiles.has(file)) {
              const body = new FormData();
              body.append("file", file);
              const asset = await upload("/tasks/" + t.id + "/assets", f, body);
              f.uploadedFiles.set(file, asset.id);
            }
            ids.push(f.uploadedFiles.get(file));
          }
          if (b.url) {
            if (f.uploadedUrl?.url !== b.url)
              f.uploadedUrl = await post("/tasks/" + t.id + "/assets", {
                url: b.url,
              });
            ids.push(f.uploadedUrl.id);
          }
          const branchId = b.branch_id ? Number(b.branch_id) : (f.createdBranch ||= await post(`/tasks/${t.id}/branches`, {name:b.branch_name})).id;
          await post("/tasks/" + t.id + "/submissions", {
            branch_id: branchId,
            version: t.version,
            description: b.description,
            asset_ids: ids,
          });
          return "/tasks/" + t.id;
        },
        "Gửi Merge Request",
      ).replace("<form ", '<form class="submission-form" '),
    )
  );
}

async function riskPage(rid) {
  const r = await get("/risk-cases/" + rid),
    p = await get("/projects/" + r.project_id);
  let html =
    heading("Cảnh báo và hỗ trợ", r.reason_json.message) +
    `<div class="grid"><div>` +
    panel(
      "Dữ kiện cảnh báo",
      `<p>${badge(r.severity)} ${badge(r.status)} · Đợt ${r.episode_no}</p><p>Người phụ trách: ${h(r.owner?.full_name || "Chưa phân công")}</p><p>Mở ${dt(r.opened_at)} · Xem lại ${dt(r.next_review_at)}</p>${r.task_id ? link("/tasks/" + r.task_id, "Mở nhiệm vụ liên quan") : link("/projects/" + r.project_id, "Mở nhóm")}${r.reason_json.missing_criteria ? `<p>Còn thiếu: ${r.reason_json.missing_criteria.map(h).join(", ")}</p>` : ""}`,
    ) +
    panel(
      "Lịch sử xử lý",
      list(
        r.actions.map(
          (x) =>
            `<strong>${h(x.content)}</strong><p>${h(x.outcome || "")}</p><small>${dt(x.created_at)} · Hạn ${dt(x.due_at)}</small>`,
        ),
      ),
    ) +
    "</div><div>";
  if (
    p.my_role === "leader" &&
    !["resolved", "dismissed"].includes(r.status) &&
    !["finalized", "archived"].includes(p.status)
  )
    html += panel(
      "Ghi hành động",
      form(
        select("action", "Thao tác", [
          ["acknowledge", "Nhận xử lý"],
          ["actions", "Lập kế hoạch"],
          ["resolve", "Kết thúc khi điều kiện đã hết"],
          [["dismiss", "Tạm bỏ qua có lý do"]],
        ]) +
          area("content", "Nội dung và lý do") +
          field(
            "due_at",
            "Hạn hành động / lần xem lại (giờ Việt Nam)",
            "datetime-local",
            "",
            "",
            false,
          ),
        (f) => {
          const b = payload(f);
          return post("/risk-cases/" + rid + "/" + b.action, {
            version: r.version,
            content: b.content,
            due_at: utc(b.due_at),
            next_review_at: utc(b.due_at),
          });
        },
        "Lưu hành động",
      ),
    );
  return html + "</div></div>";
}
async function portfolioPage(aid, uid) {
  const a = await get("/assignments/" + aid);
  if (staff(a.my_role)) return empty("Hồ sơ đóng góp chỉ dành cho sinh viên.");
  const groups = await all("/assignments/" + aid + "/projects");
  let html =
    heading("", "Hồ sơ đóng góp") +
    assignmentNav(a) +
    `<div class="stack">${link("/assignments/" + aid + "/groups", "Quay lại nhóm và công việc", "button secondary")}</div>`;
  for (const p of groups.filter((p) =>
    p.members.some((m) => m.user_id === Number(uid) && m.status === "active"),
  )) {
    const r = await get("/projects/" + p.id + "/report");
    html += panel(
      p.name,
      contributionTable(r) +
        link(
          "/projects/" + p.id + "?tab=studio&pane=summary",
          "Mở báo cáo nhóm",
          "button secondary",
        ),
    );
    for (const t of r.tasks.filter((t) =>
      t.participants.some((x) => x.user_id === Number(uid)),
    ))
      html += panel(t.title, revisionRows(t.revisions));
  }
  return html;
}
async function assignmentIndex(kind) {
  const courses = (await all("/courses")).filter(c => c.my_role === "student");
  if (!courses.length) return empty("Hồ sơ đóng góp chỉ dành cho sinh viên.");
  let html = heading("Cá nhân", "Hồ sơ đóng góp");
  for (const c of courses) {
    const assignments = await all("/courses/" + c.id + "/assignments");
    html += panel(
      c.code + " · " + c.title,
      list(
        assignments.map(
          (a) =>
            `<div class="row-title">${link("/assignments/" + a.id + (staff(c.my_role) ? "/groups" : "/portfolio/" + me.id), a.title)}${badge(a.status)}</div>`,
        ),
      ),
    );
  }
  return html;
}
async function notificationsPage() {
  const ns = await all("/me/notifications"),
    invitations = await all("/me/invitations");
  setNotificationCount(ns.filter((n) => !n.read_at).length);
  return (
    heading("Cập nhật", "Thông báo") +
    panel(
      "Lời mời tham gia",
      list(
        invitations
          .filter((i) => i.status === "pending")
          .map(
            (i) =>
              `<strong>${h(i.project_name)} · ${i.kind === "mentor" ? "Giảng viên hỗ trợ" : "Thành viên"}</strong><div class="stack">${btn("Chấp nhận", () => post("/invitations/" + i.id + "/respond", { version: i.version, action: "accept" }))}${btn("Từ chối", () => post("/invitations/" + i.id + "/respond", { version: i.version, action: "reject" }), true)}</div>`,
          ),
      ),
    ) +
    panel(
      "Thông báo của bạn",
      ns.length
        ? `<p class="notification-hint">Chọn một thông báo để mở nội dung liên quan. Thông báo sẽ tự chuyển sang đã đọc khi được mở.</p>` +
          ns.map((n) => `<a class="notification-card ${n.read_at ? "is-read" : "is-unread"}" href="${h(n.target_path)}" data-notification-id="${n.id}" data-notification-version="${n.version}" data-notification-read="${n.read_at ? "true" : "false"}"><div class="row-title"><strong>${h(n.title)}</strong>${badge(n.read_at ? "Đã đọc" : "Chưa đọc")}</div><p>${h(n.body)}</p><small>${dt(n.created_at)}</small></a>`).join("")
        : empty("Bạn chưa có thông báo nào."),
    )
  );
}

async function operationsPage() {
  const o=await get("/admin/operations");
  const entries=[
    {label:"Tài khoản",desc:"Tạo và quản lý tài khoản hệ thống",href:"/admin/users",icon:"◉"},
    {label:"Mẫu kế hoạch nhóm",desc:"Thiết lập cấu trúc dự án mẫu",href:"/admin/templates",icon:"▦"},
  ];
  return `<div id="modern-home"><div class="home-heading"><div><p class="eyebrow">QUẢN TRỊ KỸ THUẬT</p><h1>Trung tâm vận hành</h1><p>Quản lý cấu hình và theo dõi tình trạng hệ thống.</p></div>${me.demo_clock?'<span class="demo-pill">Dữ liệu minh họa</span>':''}</div><section class="overview-grid ops-metrics"><article class="overview-card"><div class="metric-icon wine">◉</div><span>Đăng nhập trường</span><strong class="metric-text">${o.integrations.identity==="disabled"?"Chưa kết nối":"Đã cấu hình"}</strong></article><article class="overview-card"><div class="metric-icon blue">↗</div><span>Thông báo đang chờ</span><strong>${o.pending_outbox}</strong></article><article class="overview-card"><div class="metric-icon amber">!</div><span>Tác vụ cần thử lại</span><strong>${o.failed_jobs}</strong></article></section><section class="workspace-card"><div class="workspace-card-head"><div><p class="eyebrow">CÔNG CỤ</p><h2>Quản lý hệ thống</h2></div></div><div class="ops-links">${entries.map(x=>`<a class="ops-link" href="${x.href}"><span class="metric-icon wine">${x.icon}</span><span><strong>${x.label}</strong><small>${x.desc}</small></span><span>→</span></a>`).join("")}</div></section></div>`;
}

async function adminUsersPage() {
  const users = await all("/admin/users");
  return (
    heading("Quản trị kỹ thuật", "Tài khoản cục bộ") +
    panel(
      "Danh sách tài khoản",
      list(
        users.map(
          (u) =>
            `<div class="row-title"><strong>${h(u.full_name)}</strong><span>${h(u.email)}</span></div><p class="meta">${h(label(u.role))} · ${u.is_active ? "Đang hoạt động" : "Đã khóa"}</p>`,
        ),
      ),
    ) +
    panel(
      "Tạo tài khoản",
      form(
        field("email", "Email", "email") +
          field("full_name", "Họ tên") +
          field(
            "password",
            me.demo_clock
              ? "Mật khẩu ban đầu (ít nhất 5 ký tự)"
              : "Mật khẩu ban đầu (ít nhất 12 ký tự)",
            "password",
          ) +
          select("role", "Vai trò hệ thống", [
            ["user", "Người dùng · phân công trong lớp riêng"],
            ["instructor", "Giảng viên · khởi tạo và đánh giá lớp"],
          ]),
        (f) => post("/admin/users", payload(f)),
        "Tạo tài khoản",
      ),
    )
  );
}
function modal(title, body) {
  document.querySelector("#ux-modal")?.remove();
  const dialog=document.createElement("dialog");dialog.id="ux-modal";dialog.className="ux-modal";
  dialog.innerHTML=`<div class="modal-head"><h2>${h(title)}</h2><button type="button" data-modal-close aria-label="Đóng">×</button></div>${body}`;
  document.body.append(dialog);dialog.showModal();syncFormationModal();
  dialog.querySelector("[data-modal-close]").onclick=()=>{if(!dirty||confirm("Hủy thay đổi chưa lưu?")){dirty=false;dialog.close();}};
  dialog.addEventListener("cancel",e=>{if(dirty&&!confirm("Hủy thay đổi chưa lưu?"))e.preventDefault();else dirty=false;});
  return false;
}
function templateEditor(t=null) {
  return modal(t?"Chỉnh sửa mẫu":"Tạo mẫu kế hoạch",form(
    field("name","Tên mẫu","text",t?.name||"")+area("description","Mục tiêu & sản phẩm bàn giao",t?.description||"")+
    area("milestones","Cột mốc · tên | ngày kể từ khởi tạo",(t?.milestones||[]).map(x=>`${x.title} | ${x.offset_days||7}`).join("\n"),false)+
    area("tasks","Công việc · tên | ngày | điểm | cột mốc",(t?.tasks||[]).map(x=>`${x.title} | ${x.offset_days||7} | ${x.points||1} | ${x.milestone||""}`).join("\n")),
    f=>{const b=payload(f);const parse=line=>line.split("|").map(x=>x.trim());const data={name:b.name,description:b.description,
      milestones:b.milestones.split("\n").filter(x=>x.trim()).map(x=>{const v=parse(x);return {title:v[0],offset_days:Number(v[1]||7)};}),
      tasks:b.tasks.split("\n").filter(x=>x.trim()).map(x=>{const v=parse(x);return {title:v[0],offset_days:Number(v[1]||7),points:Number(v[2]||1),milestone:v[3]||""};})};
      return t?patch(`/workspace-templates/${t.id}`,data):post("/workspace-templates",data);},"Lưu",`<button type="button" data-cancel-modal class="secondary">Hủy</button>`));
}
async function deleteTemplate(t) {
  if(!confirm(`Chắc chắn xóa mẫu “${t.name}”? Các dự án đã tạo sẽ được giữ lại.`))return false;
  await api("DELETE",`/workspace-templates/${t.id}`);return "/admin/templates";
}
async function templatesPage() {
  const templates=(await get("/workspace-templates")).items;
  const selected=templates.find(t=>String(t.id)===new URLSearchParams(location.search).get("template"));
  if(selected) return heading("M20 · Mẫu kế hoạch nhóm",selected.name)+panel("Mục tiêu & sản phẩm",`<p>${h(selected.description)}</p><div class="stack">${btn("Chỉnh sửa",()=>templateEditor(selected))}${btn("Xóa",()=>deleteTemplate(selected),true)}</div>`)+panel("Cột mốc",list(selected.milestones.map(x=>`<strong>${h(x.title)}</strong><p>Ngày ${h(x.offset_days)}</p>`)))+panel("Kế hoạch công việc",table("Công việc mẫu",["Công việc","Ngày","Điểm","Cột mốc"],selected.tasks.map(x=>[h(x.title),h(x.offset_days),h(x.points||1),h(x.milestone||"—")])));
  return heading("M20 · Danh mục hệ thống","Mẫu kế hoạch nhóm","Ops soạn kế hoạch dùng chung. Trưởng nhóm xem và áp dụng trong Bảng công việc khi nhóm chưa có task.")+panel("Mẫu này được dùng thế nào?",`<p><strong>1. Ops soạn mẫu</strong> gồm công việc, cột mốc và điểm khối lượng. <strong>2. Trưởng nhóm mở Bảng công việc → Xem mẫu kế hoạch.</strong> <strong>3. Áp dụng vào bảng trống</strong> để sinh kế hoạch, rồi phân công lại cho thành viên.</p><p>Mẫu không chứa dữ liệu sinh viên, không tự thêm vào nhóm đang có việc. Đây là khung kế hoạch gợi ý, không thay thế đề bài và tiêu chí chấm của giảng viên.</p>`)+`<section class="catalog-grid">${templates.map(t=>`<article class="catalog-card"><h2>${h(t.name)}</h2><p>${h(t.description)}</p><p>${t.milestones.length} cột mốc · ${t.tasks.length} công việc</p><footer>${link("/admin/templates?template="+t.id,"Xem")}${btn("Chỉnh sửa",()=>templateEditor(t),true)}${btn("Xóa",()=>deleteTemplate(t),true)}</footer></article>`).join("")}</section><div class="create-footer">${btn("+ Tạo mẫu mới",()=>templateEditor())}</div>`;
}
async function accountPage() {
  return heading("M20 · Cá nhân","Tài khoản của tôi")+panel("Thông tin cá nhân",form(field("full_name","Họ tên","text",me.full_name)+`<p>Email đăng nhập: <strong>${h(me.email)}</strong></p>`,async f=>{me={...me,...await patch("/me/profile",payload(f))};document.querySelector("#profile-name").textContent=me.full_name;},"Lưu thông tin"))+panel("Bảo mật",form(field("old_password","Mật khẩu hiện tại","password")+field("new_password","Mật khẩu mới","password"),f=>post("/me/password",payload(f)),"Đổi mật khẩu"));
}
async function breadcrumbs() {
  const parts=location.pathname.split("/").filter(Boolean), crumbs=[["/home","Tổng quan"]];
  if(parts[0]==="courses") {crumbs.push(["/courses","Lớp học phần"]);if(parts[1]){const c=await get("/courses/"+parts[1]);crumbs.push(["/courses/"+c.id,c.code+" · "+c.title]);}}
  if(parts[0]==="assignments"||parts[0]==="projects"||parts[0]==="tasks") {
    let a,p,t;if(parts[0]==="tasks"){t=await get("/tasks/"+parts[1]);p=await get("/projects/"+t.project_id);}else if(parts[0]==="projects")p=await get("/projects/"+parts[1]);
    a=await get("/assignments/"+(p?p.assignment_id:parts[1]));const c=await get("/courses/"+a.course_id);
    crumbs.push(["/courses","Lớp học phần"],["/courses/"+c.id,c.code],["/assignments/"+a.id+"/groups",a.title]);if(p)crumbs.push(["/projects/"+p.id,p.name]);if(t)crumbs.push([location.pathname,t.title]);
  }
  if(parts[0]==="admin")crumbs.push([location.pathname,parts[1]==="templates"?"Mẫu kế hoạch nhóm":"Quản lý tài khoản"]);
  const scope=view.querySelector('#learning-workspace');
  if(scope){const c=scope.querySelector('.scope-courses>a.selected'),a=scope.querySelector('#scope-assignment'),p=scope.querySelector('#scope-project');if(c)crumbs.push(["/courses/"+a.dataset.course,c.querySelector('span').textContent]);else if(scope.querySelector('#task-course'))crumbs.push(["/courses/"+scope.querySelector('#task-course').value,scope.querySelector('#task-course').selectedOptions[0].textContent]);if(a?.value)crumbs.push(["/assignments/"+a.value+"/groups",a.selectedOptions[0].textContent]);if(p?.value)crumbs.push(["/projects/"+p.value,p.selectedOptions[0].textContent]);}
  if(parts[0]==="my-tasks")crumbs.push(["/my-tasks","Công việc của tôi"]);
  if(parts[0]==="account")crumbs.push(["/account","Tài khoản cá nhân"]);
  document.querySelector(".header-location").innerHTML=`<nav aria-label="Đường dẫn" class="ux-breadcrumb">${crumbs.map((x,i)=>i===crumbs.length-1?`<span aria-current="page">${h(x[1])}</span>`:`<a href="${h(x[0])}">${h(x[1])}</a><span aria-hidden="true">/</span>`).join("")}</nav>`;
}
async function route() {
  const path = location.pathname,
    parts = path.split("/").filter(Boolean),
    id = Number(parts[1]);
  if (path === "/login") return loginPage();
  document.body.classList.remove("login-page");
  if (path === "/account") return accountPage();
  if (path === "/home") return home();
  if (path === "/courses") return courseList();
  if (parts[0] === "courses")
    return coursePage(
      id,
      parts[2] === "risk-cases"
        ? "risk"
        : parts[2] === "imports"
          ? "import"
          : null,
    );
  if (parts[0] === "assignments") {
    if (parts[2] === "portfolio") return staff(me?.role) || me?.role === "admin" ? empty("Hồ sơ đóng góp chỉ dành cho sinh viên.") : portfolioPage(id, Number(parts[3]));

    return assignmentPage(id, parts[2]);
  }
  if (parts[0] === "projects") return projectPage(id, parts[2] === "board");
  if (parts[0] === "tasks")
    return taskPage(
      id,
      parts[2] === "submit"
        ? "submit"
        : parts[2] === "claims"
          ? "claim-new"
          : null,
    );
  if (parts[0] === "risk-cases") return riskPage(id);
  if (path === "/notifications") return notificationsPage();
  if (path === "/my-tasks") return personalTasksPage();
  if (path === "/portfolios") return staff(me?.role) || me?.role === "admin" ? empty("Hồ sơ đóng góp chỉ dành cho sinh viên.") : assignmentIndex(parts[0]);
  if (path === "/admin/users") return adminUsersPage();
  if (path === "/admin/templates") return templatesPage();
  if (path === "/admin/operations") return operationsPage();
  return empty("Không tìm thấy trang.");
}
function compactSecondaryActions() {
  if(!/^(\/courses\/\d+|\/assignments\/\d+\/groups)$/.test(location.pathname)) return;
  if(new URLSearchParams(location.search).get("tab")==="roster") return;
  const panels=[...view.querySelectorAll(":scope > .panel")].filter(el=>el.querySelector("form[data-form]"));
  if(!panels.length)return;
  const details=document.createElement("details");details.className="action-shelf";
  const summary=document.createElement("summary");summary.textContent="Tạo mới & thiết lập";details.append(summary);
  const body=document.createElement("div");body.className="action-shelf-body";details.append(body);
  panels[0].before(details);for(const panel of panels)body.append(panel);
}
async function render() {
  cleanupStudio();
  const generation = ++renderId;
  actions = new Map();
  forms = new Map();
  seq = 0;
  view.setAttribute("aria-busy", "true");
  try {
    const html = await route();
    if (generation !== renderId) return;
    view.innerHTML = html;
    view.querySelectorAll(":scope > .breadcrumbs").forEach(el=>el.remove());
    if(!matchMedia("(prefers-reduced-motion: reduce)").matches)view.animate?.([{opacity:.65,transform:"translateY(4px)"},{opacity:1,transform:"none"}],{duration:180,easing:"ease-out"});
    compactSecondaryActions();
    collectionFilters();
    if(view.querySelector("#learning-workspace"))filterScopeTasks();
    if(view.querySelector("#personal-workview"))updatePersonalTasks();
    if(location.pathname!=="/login") await breadcrumbs();
    const studio = view.querySelector("#team-studio");
    if(studio){const pid=studio.dataset.pid;await mountStudio(studio,await get('/projects/'+pid),me,{
      renderReconcile:async()=>{const p=await get('/projects/'+pid);return contributionUI(p,await all('/projects/'+pid+'/tasks'),true);},
      renderQuality:async()=>{const template=document.createElement('template');template.innerHTML=await reportUI(await get('/projects/'+pid));return template.content.querySelector('.quality-grid')?.outerHTML||'';}
    });}
    view.setAttribute("aria-busy", "false");
    dirty = false;
    document
      .querySelectorAll("#sidebar nav a")
      .forEach((a) =>
        a.classList.toggle("active", a.pathname === location.pathname || (a.pathname === "/courses" && /^\/(courses|assignments|projects)(\/|$)/.test(location.pathname)) || (a.pathname === "/my-tasks" && /^\/tasks\//.test(location.pathname))),
      );
  } catch (e) {
    view.innerHTML =
      heading(
        "Truy cập hồ sơ",
        e.status === 404
          ? "Chưa có dữ liệu hoặc không tìm thấy"
          : e.status === 403
            ? "Bạn chưa có quyền xem hồ sơ"
            : "Không thể tải dữ liệu",
      ) +
      panel(
        "Thông báo",
        `<p>${h(e.message)}</p>${link("/courses", "Về lớp học phần", "button secondary")} ${btn("Thử tải lại", () => render(), true)}`,
      );
    view.setAttribute("aria-busy", "false");
  }
}
async function navigate(path) {
  if (dirty && !confirm("Bạn còn nội dung chưa lưu. Rời trang?")) return;
  history.pushState({}, "", path);
  notice.innerHTML = "";
  await render();
  window.scrollTo(0, 0);
  document.querySelector("#sidebar").classList.remove("open");
  syncMenu();
  document.querySelector("#content").focus();
}
document.addEventListener("click", (e) => {
  const show = e.target.closest("[data-show-history]"),
    hide = e.target.closest("[data-hide-history]");
  if (!show && !hide) return;
  const box = e.target.closest("[data-history]"),
    button = box.querySelector("[data-show-history]");
  box.querySelector(":scope > div").hidden = !!hide;
  button.hidden = !!show;
  button.setAttribute("aria-expanded", String(!!show));
  if (hide) {
    button.focus();
    button.scrollIntoView({ block: "nearest" });
  }
});
document.addEventListener("change", (e) => {
  if (!e.target.matches("[data-complaint-task]")) return;
  const f = e.target.closest("form"),
    choices = JSON.parse(f.dataset.complaintChoices)[e.target.value];
  f.elements.target_id.innerHTML = choices
    .map((x) => `<option value="${x.id}">${h(x.name)}</option>`)
    .join("");
});
function showFileList(input) {
  const list = input
    .closest("[data-dropzone]")
    ?.querySelector("[data-file-list]");
  if (list)
    list.textContent = Array.from(input.files)
      .map((f) => f.name)
      .join(" · ");
}
document.addEventListener("change", (e) => {
  if (e.target.matches("#task-status-filter, #task-assignee-filter, #task-priority-filter, #task-due-filter")) { const out=document.querySelector("#dashboard-task-results"); if(out) out.innerHTML=taskRows(filteredDashboardTasks(), dashboardExpanded.tasks); }
  if (e.target.matches("[data-dropzone] input[type=file]"))
    showFileList(e.target);
});
for (const type of ["dragover", "dragleave", "drop"])
  document.addEventListener(type, (e) => {
    const zone = e.target.closest("[data-dropzone]");
    if (!zone) return;
    e.preventDefault();
    zone.classList.toggle("dragging", type === "dragover");
    if (type === "drop") {
      const input = zone.querySelector("input[type=file]");
      input.files = e.dataTransfer.files;
      showFileList(input);
      dirty = true;
    }
  });
document.addEventListener("click", async (e) => {
  const bell = e.target.closest("#notification-bell");
  if (bell) {
    const menu = document.querySelector("#notification-menu");
    menu.hidden = !menu.hidden;
    bell.setAttribute("aria-expanded", String(!menu.hidden));
    if (!menu.hidden) await refreshNotificationMenu();
    return;
  }
  if (!e.target.closest(".header-notifications")) {
    const menu = document.querySelector("#notification-menu");
    if (menu && !menu.hidden) {
      menu.hidden = true;
      document.querySelector("#notification-bell").setAttribute("aria-expanded", "false");
    }
  }
  const target = e.target.closest("[data-action]");
  if (target) {
    e.preventDefault();
    const fn = actions.get(target.dataset.action);
    if (!fn) return;
    target.disabled = true;
    interaction = target;
    view.setAttribute("aria-busy", "true");
    try {
      const next = await fn();
      dirty = false;
      if(next!==false)notice.innerHTML = noticeMarkup("Thao tác đã được xử lý.");
      if (typeof next === "string") { document.querySelector("#ux-modal")?.close(); await navigate(next); }
      else if (next !== false) { document.querySelector("#ux-modal")?.close(); await render(); }
    } catch (err) {
      errorMessage(err);
    } finally {
      target.disabled = false;
      interaction = null;
      view.setAttribute("aria-busy", "false");
    }
    return;
  }
  const expandDashboard = e.target.closest("[data-dashboard-expand]");
  if (expandDashboard) {
    const kind = expandDashboard.dataset.dashboardExpand;
    dashboardExpanded[kind] = !dashboardExpanded[kind];
    if (kind === "tasks") {
      const out = document.querySelector("#dashboard-task-results");
      if (out) out.innerHTML = taskRows(filteredDashboardTasks(), dashboardExpanded.tasks);
    } else {
      const out = document.querySelector("#action-queue .panel");
      if (out) {
        const body = out.querySelector(":scope > :not(.panel-head)");
        if (body) body.innerHTML = actionQueueMarkup(dashboardActionQueue, dashboardExpanded.actions);
      }
    }
    return;
  }
  const calShift = e.target.closest("[data-calendar-shift]");
  if (calShift) {
    calendarMonth = new Date(calendarMonth.getFullYear(), calendarMonth.getMonth() + Number(calShift.dataset.calendarShift), 1);
    const box = document.querySelector("#dashboard-calendar");
    if (box) box.innerHTML = `<div class="panel-head"><h2>${dashboardCalendarMode === "notifications" ? "Lịch công việc và thông báo của tôi" : "Lịch deadline nhóm"}</h2></div>${dashboardCalendarMode === "notifications" ? staffCalendarMarkup(dashboardCalendarItems) : calendarMarkup(dashboardTasks)}`;
    return;
  }
  const notification = e.target.closest("[data-notification-id]");
  if (notification) {
    e.preventDefault();
    try {
      if (notification.dataset.notificationRead !== "true") {
        await post("/notifications/" + notification.dataset.notificationId + "/read", {
          version: Number(notification.dataset.notificationVersion),
        });
        setNotificationCount(notificationUnread - 1);
        await refreshNotificationMenu();
      }
      document.querySelector("#notification-menu").hidden = true;
      document.querySelector("#notification-bell").setAttribute("aria-expanded", "false");
      await navigate(notification.getAttribute("href"));
    } catch (err) {
      errorMessage(err);
    }
    return;
  }
  const a = e.target.closest("a");
  if (
    a &&
    a.origin === location.origin &&
    !a.pathname.startsWith("/api/") &&
    !a.hasAttribute("download") &&
    !["/projects", "/admin/users", "/admin/templates", "/account"].includes(
      a.pathname,
    ) &&
    !e.ctrlKey &&
    !e.metaKey &&
    a.target !== "_blank"
  ) {
    e.preventDefault();
    await navigate(a.pathname + a.search);
  }
});
document.addEventListener("submit", async (e) => {
  const f = e.target;
  if (!f.dataset.form) return;
  e.preventDefault();
  const button = e.submitter || f.querySelector("[type=submit]");
  if (
    f.hasAttribute("data-review") &&
    button.value === "return" &&
    !f.elements.reason.value.trim()
  ) {
    const input = f.elements.reason,
      error = f.querySelector("[data-review-error]");
    error.textContent = "*Bạn cần nhập nhận xét trước khi yêu cầu sửa.";
    input.setAttribute("aria-invalid", "true");
    input.setAttribute("aria-describedby", error.id);
    input.focus();
    return;
  }
  const fn = forms.get(f.dataset.form);
  f.querySelectorAll("[type=submit]").forEach((b) => (b.disabled = true));
  interaction = f;
  view.setAttribute("aria-busy", "true");
  f.querySelector(".form-error").textContent = "";
  try {
    const next = await fn(f, button);
    dirty = false;
    notice.innerHTML = noticeMarkup("Đã lưu dữ liệu.");
    if (typeof next === "string") { document.querySelector("#ux-modal")?.close(); await navigate(next); }
    else if (next !== false) { document.querySelector("#ux-modal")?.close(); await render(); }
  } catch (err) {
    f.querySelector(".form-error").textContent = err.message;
    errorMessage(err);
  } finally {
    f.querySelectorAll("[type=submit]").forEach((b) => (b.disabled = false));
    interaction = null;
    view.setAttribute("aria-busy", "false");
  }
});
document.addEventListener("input", (e) => {
  if (e.target.matches("#task-search")) { const out=document.querySelector("#dashboard-task-results"); if(out) out.innerHTML=taskRows(filteredDashboardTasks(), dashboardExpanded.tasks); }
  if (e.target.closest("form[data-form]")) dirty = true;
  if (e.target.name === "reason" && e.target.closest("[data-review]")) {
    e.target.removeAttribute("aria-invalid");
    e.target.closest("form").querySelector("[data-review-error]").textContent =
      "";
  }
});
window.addEventListener("beforeunload", (e) => {
  if (dirty) {
    e.preventDefault();
    e.returnValue = "";
  }
});
window.addEventListener("popstate", () => render());
document.querySelector("#menu").onclick = () => {
  const open = document.querySelector("#sidebar").classList.toggle("open");
  document.querySelector("#menu").setAttribute("aria-expanded", String(open));
  syncMenu();
};
document.querySelector("#logout").onclick = async () => {
  await post("/auth/logout", {});
  dirty = false;
  location.href = "/login";
};
try {
  token = (await get("/auth/csrf")).token;
  if (location.pathname !== "/login") {
    me = await get("/auth/me");
    if (me.role!=="admin") {
      const unread = await get("/me/notifications?unread_only=true&page_size=1");
      setNotificationCount(unread.total);
      await refreshNotificationMenu();
    }
    document.querySelector("#user-name").textContent = me.full_name;
    document.querySelector("#profile-name").textContent = me.full_name;
    document.querySelector("#profile-email").textContent = me.email;
    document.querySelector("#profile-avatar").textContent = me.full_name
      .split(" ")
      .map((x) => x[0])
      .slice(-2)
      .join("");
    document.querySelector("#user-email").textContent = me.email;
    document.querySelector("#clock").textContent =
      (me.clock_mode === "fixed" ? "Giờ mô phỏng · " : "Giờ hệ thống · ") +
      dt(me.business_time);
    if (me.role === "admin") {
      document.querySelector("#sidebar nav").innerHTML =
        `<a href="/home">Tổng quan vận hành</a><a href="/admin/users">Quản lý tài khoản</a><a href="/admin/templates">Mẫu kế hoạch nhóm</a>`;
      document.querySelector("#ops-nav").innerHTML = "";
    } else {
      const enrolled = await all("/courses");
      const isCoordinator = me.role === "coordinator" || enrolled.some(c => staff(c.my_role));
      const isInstructor = enrolled.some(c => c.my_role === "instructor");
      if (isCoordinator || isInstructor) {
        document.querySelector("#sidebar nav").innerHTML = isCoordinator
          ? `<a href="/home">Tổng quan giảng viên</a><a href="/courses">Quản lý học phần</a><a href="/notifications">Thông báo</a>`
          : `<a href="/home">Tổng quan giảng viên</a><a href="/courses">Lớp học phần</a><a href="/notifications">Thông báo</a>`;
        document.querySelector("#ops-nav").innerHTML = "";
      }
    }
  }
  decorateNavigation();
  await render();
} catch (e) {
  errorMessage(e);
}

function decorateNavigation() {
  const shapes={"/home":"◫","/courses":"▦","/my-tasks":"✓","/portfolios":"▤","/notifications":"◌","/admin/operations":"◇","/admin/users":"♙","/admin/templates":"▦"};
  document.querySelectorAll("#sidebar nav a").forEach(a=>{
    if(a.querySelector(".nav-icon"))return;
    const icon=document.createElement("span");icon.className="nav-icon";icon.setAttribute("aria-hidden","true");icon.textContent=shapes[a.pathname]||"•";a.prepend(icon);
  });
}
function syncMenu() {
  const sidebar = document.querySelector("#sidebar");
  const collapsed =
    matchMedia("(max-width:1199px)").matches &&
    !sidebar.classList.contains("open");
  sidebar.inert = collapsed;
  sidebar.setAttribute("aria-hidden", String(collapsed));
  document
    .querySelector("#menu")
    .setAttribute("aria-expanded", String(!collapsed));
}
window.addEventListener("resize", syncMenu);
document.addEventListener("keydown", (e) => {
  if (
    e.key === "Escape" &&
    document.querySelector("#sidebar").classList.contains("open")
  ) {
    document.querySelector("#sidebar").classList.remove("open");
    syncMenu();
    document.querySelector("#menu").focus();
  }
});
syncMenu();

async function refreshDashboardLive() {
  if (document.hidden || location.pathname !== "/home" || dirty || interaction) return;
  try {
    const data = await get("/me/overview");
    dashboardTasks = data.group_tasks || data.tasks || [];
    dashboardActionQueue = data.action_queue || [];
    if (dashboardCalendarMode === "notifications") dashboardCalendarItems = await all("/me/notifications");
    else dashboardCalendarItems = dashboardTasks;
    setNotificationCount(data.notifications);
    const assigned = document.querySelector("#dashboard-stat-assigned");
    const open = document.querySelector("#dashboard-stat-open");
    const actionsCount = document.querySelector("#dashboard-stat-actions");
    if (assigned) assigned.textContent = data.tasks.length;
    if (open) open.textContent = dashboardTasks.length;
    if (actionsCount) actionsCount.textContent = dashboardActionQueue.length;
    const taskOut = document.querySelector("#dashboard-task-results");
    if (taskOut) taskOut.innerHTML = taskRows(filteredDashboardTasks(), dashboardExpanded.tasks);
    const actionPanel = document.querySelector("#action-queue .panel");
    if (actionPanel) {
      const body = actionPanel.querySelector(":scope > :not(.panel-head)");
      if (body) body.innerHTML = actionQueueMarkup(dashboardActionQueue, dashboardExpanded.actions);
    }
    const calendar = document.querySelector("#dashboard-calendar");
    if (calendar) calendar.innerHTML = `<div class="panel-head"><h2>${dashboardCalendarMode === "notifications" ? "Lịch công việc và thông báo của tôi" : "Lịch deadline nhóm"}</h2></div>${dashboardCalendarMode === "notifications" ? staffCalendarMarkup(dashboardCalendarItems) : calendarMarkup(dashboardTasks)}`;
    const courses = await all("/courses");
    const courseGrid = document.querySelector(".dashboard-course-section .course-card-grid");
    if (courseGrid) courseGrid.innerHTML = courses.map(c => `<a class="course-card" href="/courses/${c.id}" aria-label="Mở lớp ${h(c.code)} - ${h(c.title)}"><div class="course-card-banner banner-${Math.abs(Number(c.id)||0)%6}"><span>${h(c.code)}</span></div><div class="course-card-body"><div class="course-card-meta">${h(c.term || "")}</div><strong>${h(c.code)} · ${h(c.title)}</strong><div class="course-card-footer">${badge(c.my_role)}<span>Mở lớp học phần →</span></div></div></a>`).join("") || empty("Bạn chưa tham gia lớp học phần nào.");
  } catch (_) { /* Keep the last good dashboard snapshot during transient network errors. */ }
}

// Keep the unread badge fresh while the application remains open (Facebook-style polling).
if (me && location.pathname !== "/login" && me.role !== "admin") {
  window.setInterval(async () => {
    if (document.hidden) return;
    try {
      const result = await get("/me/notifications?unread_only=true&page_size=1");
      const nextUnread=Number(result.total || 0);
      if(nextUnread>notificationUnread) {
        const toast=document.createElement('div');toast.className='studio-toast';toast.role='status';
        toast.textContent='Có cập nhật mới từ nhóm. Mở chuông thông báo để xem và xử lý.';
        document.body.append(toast);setTimeout(()=>toast.remove(),5000);
      }
      setNotificationCount(nextUnread);
      if (!document.querySelector("#notification-menu").hidden) await refreshNotificationMenu();
    } catch (_) { /* A transient polling failure must not interrupt the current page. */ }
  }, 10000);
  window.setInterval(refreshDashboardLive, 10000);
}

function filterCatalog(){const q=(document.querySelector("[data-catalog-search]")?.value||"").toLocaleLowerCase("vi"),term=document.querySelector("[data-catalog-term]")?.value;document.querySelectorAll(".catalog-card[data-term]").forEach(c=>c.hidden=!c.textContent.toLocaleLowerCase("vi").includes(q)||!!term&&c.dataset.term!==term);}
document.addEventListener("input",e=>{if(e.target.matches("[data-catalog-search]"))filterCatalog();});
document.addEventListener("change",e=>{if(e.target.matches("[data-catalog-term]"))filterCatalog();});

document.addEventListener("click",e=>{if(e.target.closest("[data-cancel-modal]"))document.querySelector("#ux-modal [data-modal-close]")?.click();});

function collectionFilters(){
  for(const panel of view.querySelectorAll(".panel")) {
    const title=panel.querySelector("h2")?.textContent;
    if(!["Bài tập nhóm trong học phần","Nhóm thực hiện"].includes(title))continue;
    const list=panel.querySelector(".row-list,.assignment-group-grid");if(!list)continue;
    const filter=document.createElement("div");filter.className="catalog-filters";
    filter.innerHTML=`<input placeholder="Tìm ${title=== "Nhóm thực hiện"?"nhóm, sinh viên":"bài tập"}…" aria-label="Tìm trong danh sách"><select aria-label="Trạng thái"><option value="">Tất cả trạng thái</option>${[...new Set([...list.querySelectorAll(".badge")].map(x=>x.textContent))].map(x=>`<option>${h(x)}</option>`).join("")}</select>`;
    const apply=()=>{const q=filter.querySelector("input").value.toLowerCase(),state=filter.querySelector("select").value;for(const row of list.children)row.hidden=!row.textContent.toLowerCase().includes(q)||!!state&&row.querySelector(".badge")?.textContent!==state;};
    filter.addEventListener("input",apply);filter.addEventListener("change",apply);list.before(filter);
  }
}
