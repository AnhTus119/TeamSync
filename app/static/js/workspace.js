// TeamSync workspace UI. Every number, list and chart is built from /api/v1 data.
// Each page: load data (async) -> build markup -> bind() interactions.

// ------------------------------------------------------------------ helpers
const $ = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];
const h = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
const VN = 'vi-VN';
let clockOffset = 0;
const nowMs = () => Date.now() + clockOffset;
const dt = v => v ? new Date(v).toLocaleString(VN, {hour: '2-digit', minute: '2-digit', day: '2-digit', month: '2-digit', year: 'numeric'}) : '—';
const hm = v => new Date(v).toLocaleTimeString(VN, {hour: '2-digit', minute: '2-digit'});
const dm = v => { const d = v instanceof Date ? v : new Date(v); return `${String(d.getDate()).padStart(2, '0')}/${String(d.getMonth() + 1).padStart(2, '0')}`; };
const dmy = v => new Date(v).toLocaleDateString(VN, {day: '2-digit', month: '2-digit', year: '2-digit'});
const num = (v, d = 0) => Number(v).toLocaleString(VN, {minimumFractionDigits: d, maximumFractionDigits: d});
const ago = v => {
  const m = Math.round((nowMs() - new Date(v)) / 60000);
  if (m < 1) return 'Vừa xong';
  if (m < 60) return m + ' phút trước';
  if (m < 1440) return Math.round(m / 60) + ' giờ trước';
  return Math.round(m / 1440) + ' ngày trước';
};
const initials = name => String(name || '?').replace(/^Giảng viên\s+/i, '').split(/\s+/).filter(Boolean).slice(-2).map(x => x[0]).join('').toUpperCase();
const toLocalInput = ms => { const d = new Date(ms); return new Date(d - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16); };
const iso = v => new Date(v).toISOString();
const store = {get(k, d) { try { return localStorage.getItem(k) ?? d; } catch { return d; } }, set(k, v) { try { localStorage.setItem(k, v); } catch { /* private mode */ } }};

const labels = {todo: 'Cần làm', in_progress: 'Đang làm', review: 'Chờ duyệt', done: 'Hoàn thành', draft: 'Đang lập nhóm', pending: 'Chờ duyệt',
  active: 'Đang hoạt động', returned: 'Cần sửa', accepted: 'Đã duyệt', approved: 'Đã đồng ý', rejected: 'Không đồng ý', open: 'Đang mở',
  closed: 'Đã đóng', submitted: 'Đã gửi', under_review: 'Đang hỗ trợ', resolved: 'Đã xử lý', left: 'Đã rời', archived: 'Đã lưu trữ',
  leader: 'Trưởng nhóm', member: 'Thành viên', instructor: 'Giảng viên', coordinator: 'Quản lý học phần', student: 'Sinh viên', withdrawn: 'Đã rút'};
const STATUS = ['todo', 'in_progress', 'review', 'done'];
const badgeClass = v => ['returned', 'rejected'].includes(v) ? 'bad' : ['done', 'accepted', 'approved'].includes(v) ? 'good' : ['left', 'withdrawn', 'archived'].includes(v) ? 'neutral' : '';
const badge = (v, cls) => `<span class="badge ${cls ?? badgeClass(v)}">${h(labels[v] || v)}</span>`;
const lateBadge = () => `<span class="badge bad pill"><span class="bullet"></span>Quá hạn</span>`;
const soonBadge = () => `<span class="badge good pill" style="background:var(--good-bg);color:var(--good)"><span class="bullet"></span>Sắp đến hạn</span>`;
const button = (text, act, cls = '', extra = '') => `<button type="button" data-action="${h(act)}" class="${cls}" ${extra}>${h(text)}</button>`;
const link = (text, url, cls = 'button secondary', extra = '') => `<a class="${cls}" href="${h(url)}" ${extra}>${h(text)}</a>`;
const field = (name, title, type = 'text', value = '', required = true, extra = '') => `<label>${h(title)}<input name="${name}" type="${type}" value="${h(value)}" ${required ? 'required' : ''} ${extra}></label>`;
const area = (name, title, value = '', required = true) => `<label>${h(title)}<textarea name="${name}" ${required ? 'required' : ''}>${h(value)}</textarea></label>`;
const select = (name, title, items, value = '') => `<label>${h(title)}<select name="${name}">${items.map(([id, t]) => `<option value="${h(id)}" ${String(id) === String(value) ? 'selected' : ''}>${h(t)}</option>`).join('')}</select></label>`;
const empty = t => `<div class="empty">${h(t)}</div>`;
const panel = (title, body, extra = '') => `<section class="panel" ${extra}>${title ? `<h2>${h(title)}</h2>` : ''}${body}</section>`;
const pageHead = (title, sub = '', actions = '', crumb = '', cls = 'page-title') => `<section class="page-head"><div>${crumb}<h1 class="${cls}">${h(title)}</h1>${sub ? `<p>${h(sub)}</p>` : ''}</div><div class="actions">${actions}</div></section>`;
const table = (heads, rows, rowAttr = () => '') => `<div class="table-wrap"><table><thead><tr>${heads.map(x => `<th scope="col">${h(x)}</th>`).join('')}</tr></thead><tbody>${rows.map((r, i) => `<tr ${rowAttr(i)}>${r.map(c => `<td>${c ?? '—'}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
const ROBOT = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3v3"/><circle cx="12" cy="2.6" r=".6"/><rect x="4.5" y="9" width="15" height="10" rx="5"/><path d="M9.5 13.2v1.6M14.5 13.2v1.6"/><path d="M8 9l1.2-3h5.6L16 9"/></svg>';
const robot = (big = false) => `<span class="robot ${big ? 'big' : ''}">${ROBOT}</span>`;
const NAV_ICONS = {
  home: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3.5 10.5 12 4l8.5 6.5"/><path d="M5.5 9.5V19a1 1 0 0 0 1 1h4v-5.5h3V20h4a1 1 0 0 0 1-1V9.5"/></svg>',
  folder: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3.5 7.5a2 2 0 0 1 2-2h4l2 2h7a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2z"/><path d="M3.5 10.5h17"/></svg>',
  kanban: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3.5" y="4" width="17" height="16" rx="2"/><path d="M9.2 4v16M14.8 4v16"/><path d="M5.6 7.5h1.6M11.2 7.5h1.6M16.8 7.5h1.6M5.6 10.5h1.6M11.2 10.5h1.6"/></svg>',
  calendar: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3.5" y="5" width="17" height="15" rx="2"/><path d="M3.5 9.5h17M8 3v4M16 3v4"/><path d="M7 13h4M7 16.5h7M14 13h3"/></svg>',
  inbox: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 13.5 6.3 6a1.5 1.5 0 0 1 1.4-1h8.6a1.5 1.5 0 0 1 1.4 1L20 13.5V18a1.5 1.5 0 0 1-1.5 1.5h-13A1.5 1.5 0 0 1 4 18z"/><path d="M4 13.5h4.5l1.2 2h4.6l1.2-2H20"/><path d="M12 7.5v4.5M10 10l2 2 2-2"/></svg>',
  book: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 6.5C10.3 5.2 8 4.6 4.5 4.6V18c3.5 0 5.8.6 7.5 1.9 1.7-1.3 4-1.9 7.5-1.9V4.6c-3.5 0-5.8.6-7.5 1.9z"/><path d="M12 6.5v13.4"/></svg>',
  users: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="9" cy="8.5" r="3.2"/><path d="M3.5 19c.6-3.2 2.8-5 5.5-5s4.9 1.8 5.5 5"/><circle cx="16.5" cy="9" r="2.6"/><path d="M15.6 14.1c2.6-.3 4.5 1.4 4.9 4.4"/></svg>',
};
const CAL_ICON = '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="4" y="5.5" width="16" height="14.5" rx="2"/><path d="M4 10h16M8.5 3.5v4M15.5 3.5v4"/></svg>';
const SEARCH_ICON = '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="6"/><path d="m20 20-4.5-4.5"/></svg>';
const AI_ICON = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3.5l1.6 4.2 4.2 1.6-4.2 1.6L12 15.1l-1.6-4.2-4.2-1.6 4.2-1.6z"/><path d="M18.5 14.5l.8 2 2 .8-2 .8-.8 2-.8-2-2-.8 2-.8zM6 15.5l.6 1.4 1.4.6-1.4.6L6 19.5l-.6-1.4-1.4-.6 1.4-.6z"/></svg>';
const BOOK = '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="6" y="3.5" width="12" height="17" rx="2"/><path d="M9 8h6M9 11h6M9 14h6"/></svg>';

// ------------------------------------------------------------------ state
let me, csrf, homeData, projectData, taskData, criteriaData = [], charts = [];
const isTeacher = () => me.role === 'instructor' || me.enrollments?.some(e => e.role === 'instructor');
const isStaff = () => isTeacher() || me.enrollments?.some(e => e.role === 'coordinator');
const isLeader = () => projectData?.my_role === 'leader';
const roleLabel = () => me.role === 'admin' ? 'Quản trị hệ thống' : isTeacher() ? 'Giảng viên' : me.enrollments?.some(e => e.role === 'coordinator') ? 'Quản lý học phần' : 'Sinh viên';

// ------------------------------------------------------------------ API
// GET responses are kept for 5 minutes (or until F5). Any change made by this user (POST/PUT/PATCH/DELETE)
// clears the cache, so every page shows the result of the user's own action immediately and stays consistent.
const CACHE_TTL = 5 * 60 * 1000;
const cache = new Map();
const cacheable = path => !path.startsWith('/auth/') && !path.includes('unread_only');
function clearCache() { cache.clear(); }
async function api(path, body, method = body === undefined ? 'GET' : 'POST') {
  if (method === 'GET' && cacheable(path)) {
    const hit = cache.get(path);
    if (hit && Date.now() - hit.at < CACHE_TTL) return structuredClone(hit.data);
  }
  const headers = {'X-CSRF-Token': csrf || '', 'Idempotency-Key': crypto.randomUUID()};
  if (!(body instanceof FormData)) headers['Content-Type'] = 'application/json';
  const res = await fetch('/api/v1' + path, {method, headers, body: body === undefined ? undefined : body instanceof FormData ? body : JSON.stringify(body)});
  let data = {};
  try { data = await res.json(); } catch { /* non-JSON error page */ }
  if (method !== 'GET') clearCache();
  if (res.status === 401 && me) { store.set('ts-expired', '1'); location.href = '/login?expired=1'; throw Error('Phiên đăng nhập đã hết hạn'); }
  if (!res.ok) { const e = Error(data.error?.message || 'Không xử lý được yêu cầu'); e.code = data.error?.code; e.status = res.status; throw e; }
  if (method === 'GET' && cacheable(path)) cache.set(path, {at: Date.now(), data: structuredClone(data.data)});
  return data.data;
}
async function all(path) {
  const sep = path.includes('?') ? '&' : '?';
  const d = await api(path + sep + 'page_size=100'), r = d.items || [];
  for (let n = 2; r.length < d.total; n++) r.push(...(await api(path + sep + 'page_size=100&page=' + n)).items);
  return r;
}
function notify(text, isError = false) {
  const n = $('#notice'); n.textContent = text; n.classList.toggle('error', isError);
  clearTimeout(notify.timer); notify.timer = setTimeout(() => { n.textContent = ''; }, 6000);
}
function friendly(e) {
  if (e.code === 'VERSION_CONFLICT') return e.message + ' — trang sẽ hiển thị dữ liệu mới nhất.';
  return e.message;
}
async function attempt(fn) {
  try { await fn(); } catch (e) { notify(friendly(e), true); if (e.code === 'VERSION_CONFLICT') await render(); }
}
// Modal keeps the typed values when saving fails; Esc closes (native dialog).
function modal(title, markup, save, label = 'Lưu', opts = {}) {
  const d = document.createElement('dialog');
  if (opts.wide) d.classList.add('wide');
  d.setAttribute('aria-labelledby', 'dlg-title');
  d.innerHTML = `<div class="dialog-head"><h2 id="dlg-title">${h(title)}</h2><button type="button" class="secondary" data-close>Đóng</button></div><form novalidate>${markup}<p class="error" role="alert"></p>${save ? `<div class="form-end"><button type="submit">${h(label)}</button></div>` : ''}</form>`;
  document.body.append(d); d.showModal();
  d.querySelector('[data-close]').onclick = () => d.close();
  d.onclose = () => d.remove();
  const form = d.querySelector('form');
  form.onsubmit = async e => {
    e.preventDefault();
    if (!save) return;
    const b = e.submitter || form.querySelector('[type=submit]');
    const bad = [...form.elements].find(x => x.required && !String(x.value).trim());
    if (bad) { form.querySelector('.error').textContent = 'Cần nhập: ' + (bad.closest('label')?.firstChild?.textContent || bad.name); bad.focus(); return; }
    b.disabled = true;
    try { const msg = await save(new FormData(form), d); d.close(); await render(); notify(typeof msg === 'string' ? msg : 'Đã lưu'); }
    catch (err) { form.querySelector('.error').textContent = friendly(err); }
    finally { b.disabled = false; }
  };
  opts.onOpen?.(d);
  return d;
}
// Guards a button against double submission while the request is in flight.
async function busy(btn, fn) {
  if (btn?.disabled) return;
  if (btn) btn.disabled = true;
  try { return await fn(); } finally { if (btn) btn.disabled = false; }
}

// ------------------------------------------------------------------ chrome
function chrome() {
  $('#topbar-user').hidden = false;
  $('#user-name').textContent = me.full_name;
  $('#avatar').textContent = initials(me.full_name);
  $('#menu-name').textContent = me.full_name;
  $('#menu-role').textContent = 'Vai trò: ' + roleLabel();
  const code = me.enrollments?.find(e => e.student_code)?.student_code;
  $('#menu-code').textContent = code ? 'Mã sinh viên: ' + code : '';
  $('#menu-code').hidden = !code;
  $('#menu-email').textContent = me.email;
  $('#menu-settings').innerHTML = ICONS.settings + '<span>Cài đặt</span>';
  $('#logout').innerHTML = ICONS.logout + '<span>Đăng xuất</span>';
  // Giảng viên / quản lý học phần: chỉ Tổng quan, Timeline, Học phần; nhóm mở từ Học phần.
  const nav = me.role === 'admin' ? [['/home', 'Quản lý tài khoản', 'users']] : isStaff() ?
    [['/home', 'Tổng quan', 'home'], ['/timeline', 'Timeline', 'calendar'], ['/courses', 'Học phần', 'book']] :
    [['/home', 'Tổng quan', 'home'], ['/projects', 'Dự án của tôi', 'folder'], ['/kanban', 'Bảng Kanban', 'kanban'], ['/timeline', 'Timeline', 'calendar'], ['/submissions', 'Bài nộp', 'inbox'], ['/courses', 'Học phần', 'book']];
  const navKey = nav.map(x => x[0]).join();
  if ($('#main-nav').dataset.key !== navKey) {
    $('#main-nav').innerHTML = nav.map(([href, text, icon]) => `<a href="${href}"><span class="nav-icon">${NAV_ICONS[icon]}</span><span>${h(text)}</span></a>`).join('');
    $('#main-nav').dataset.key = navKey;
  }
  const path = location.pathname;
  const staffGroup = isStaff() && /^\/(projects|tasks)\//.test(path);
  $$('#main-nav a').forEach(a => {
    const p = a.getAttribute('href');
    const on = path === p || (p === '/courses' && (path.startsWith('/courses/') || staffGroup)) || (p === '/home' && path === '/');
    a.classList.toggle('active', on);
    if (on) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current');
  });
  const ps = isStaff() ? [] : homeData?.projects || [];
  const projKey = ps.map(p => p.id + ':' + p.name + ':' + p.team_name).join('|');
  if ($('#project-nav').dataset.key !== projKey) {
    $('#project-nav').innerHTML = ps.map(p => `<a href="/projects/${p.id}" data-pid="${p.id}">${robot()}<span>${h(p.name)}${p.team_name ? ' · ' + h(p.team_name) : ''}</span></a>`).join('');
    $('#project-nav').dataset.key = projKey;
  }
  const pid = projectData?.id;
  $$('#project-nav a').forEach(a => a.classList.toggle('active', Number(a.dataset.pid) === pid && /^\/(projects|tasks)\//.test(path)));
  document.querySelector('.nav-divider').hidden = !ps.length;
  $('#project-nav').hidden = !ps.length;
}
function setupChrome() {
  const mobile = () => matchMedia('(max-width:900px)').matches;
  const menu = $('#menu'), scrim = $('#scrim');
  const sync = () => {
    const open = mobile() ? document.body.classList.contains('side-open') : !document.body.classList.contains('side-closed');
    menu.setAttribute('aria-expanded', String(open)); scrim.hidden = !(mobile() && open);
  };
  if (store.get('ts-side', 'open') === 'closed') document.body.classList.add('side-closed');
  menu.onclick = () => {
    if (mobile()) { document.body.classList.remove('side-closed'); document.body.classList.toggle('side-open'); }
    else { document.body.classList.toggle('side-closed'); store.set('ts-side', document.body.classList.contains('side-closed') ? 'closed' : 'open'); }
    sync();
  };
  scrim.onclick = () => { document.body.classList.remove('side-open'); sync(); };
  addEventListener('resize', sync); sync();
  const av = $('#avatar'), am = $('#account-menu');
  const close = () => { am.hidden = true; av.setAttribute('aria-expanded', 'false'); };
  av.onclick = e => { e.stopPropagation(); am.hidden = !am.hidden; av.setAttribute('aria-expanded', String(!am.hidden)); if (!am.hidden) am.querySelector('a')?.focus(); };
  document.addEventListener('click', e => { if (!am.contains(e.target)) close(); });
  document.addEventListener('keydown', e => { if (e.key === 'Escape' && !am.hidden) { close(); av.focus(); } });
  $('#logout').onclick = () => attempt(async () => { await api('/auth/logout', {}); location.href = '/login'; });
  $('#contact').onclick = () => contactModal();
}
function contactModal() {
  const people = homeData?.contacts || [];
  modal('Liên hệ', people.length ? table(['Họ tên', 'Vai trò', 'Email'], people.map(p => [h(p.full_name), h(p.role), `<a href="mailto:${h(p.email)}">${h(p.email)}</a>`]))
    : empty('Chưa có liên hệ trong các dự án của bạn.'), null);
}

// ------------------------------------------------------------------ shared components
const progressRatio = p => p.total ? p.done / p.total : 0;
// Tiến độ = hoàn thành / tổng; chưa có task = 0%; 100% chỉ khi tổng > 0 và xong hết.
const progressTier = p => p.total > 0 && p.done === p.total ? 'p100' : progressRatio(p) >= .5 ? 'p50' : progressRatio(p) >= .25 ? 'p25' : progressRatio(p) > 0 ? 'p1' : 'p0';
function projectCard(p, index = 0) {
  const pct = p.total ? Math.round(p.done / p.total * 100) : 0;
  return `<a class="project-card tier-${progressTier(p)}" href="/projects/${p.id}" data-search="${h((p.name + ' ' + p.team_name + ' ' + p.course_title + ' ' + p.assignment_title).toLowerCase())}" data-lead="${p.my_role === 'leader'}" data-progress="${progressRatio(p)}" data-created="${h(p.created_at || '')}" data-index="${index}">
    <div class="pc-top">${robot(true)}<div><h3>${h(p.name)}</h3><div class="team">${h(p.team_name || p.assignment_title)}</div><div class="team pc-course" title="${h(p.course_title + ' · Đề bài: ' + p.assignment_title)}">${h(p.course_title)}</div></div><span aria-hidden="true">→</span></div>
    <div class="pc-mid"><span>${h(labels[p.my_role] || p.my_role)}</span>${badge(p.status)}</div>
    <div><div class="pc-progress"><span>${p.done}/${p.total} công việc hoàn thành</span><b>${pct === 100 && p.done !== p.total ? 99 : pct}%</b></div><div class="progress" role="img" aria-label="Tiến độ ${pct}%"><span style="width:${pct}%"></span></div></div></a>`;
}
const isRepair = t => t.status === 'in_progress' && t.latest_submission_status === 'returned';
const isDue = t => ['todo', 'in_progress'].includes(t.status) && new Date(t.due_at) <= nowMs() + 86400000;
const isMine = t => t.participants?.some(x => x.user_id === me.id);
function taskCard(t, context = 'global') {
  const sub = context === 'global' ? t.project_name : t.participants.map(x => x.user.full_name).join(', ');
  return `<a class="task-card ${t.overdue ? 'late' : ''}" href="/tasks/${t.id}" data-search="${h(t.title.toLowerCase())}">
    <h3>${h(t.title)}</h3><small>${h(sub)}</small>
    <div class="tc-foot"><span>Hạn ${h(hm(t.due_at))} · ${h(new Date(t.due_at).toLocaleDateString(VN, {day: '2-digit', month: '2-digit', year: '2-digit'}))}</span>${t.overdue ? lateBadge() : isRepair(t) ? badge('returned') : ''}</div></a>`;
}
// One Kanban component for the global board and the project board.
function kanban(tasks, context, filters) {
  const shown = tasks.filter(t => (!filters.project || t.project_id === filters.project) && (!filters.q || t.title.toLowerCase().includes(filters.q))
    && (!filters.mine || isMine(t)) && (!filters.late || t.overdue) && (!filters.repair || isRepair(t)) && (!filters.due || isDue(t)) && (!filters.review || t.status === 'review'));
  return `<div class="board">${STATUS.map(s => { const col = shown.filter(t => t.status === s);
    return `<section class="column" aria-label="${labels[s]}"><h2><span class="status-dot dot-${s}" aria-hidden="true"></span>${labels[s]}<span class="count" aria-label="${col.length} công việc">${col.length}</span></h2>${col.map(t => taskCard(t, context)).join('') || empty('Không có công việc')}</section>`; }).join('')}</div>`;
}
function kanbanControls(filters, projects, personal = false) {
  // Personal board: search, project, Quá hạn, Cần sửa on one row (no "Việc của tôi": the board is already personal).
  const chips = [...(personal ? [] : [['mine', 'Việc của tôi']]), ['late', 'Quá hạn'], ['repair', 'Cần sửa']];
  if (filters.due) chips.push(['due', 'Đến hạn / quá hạn']);
  if (filters.review) chips.push(['review', 'Chờ duyệt']);
  const chipRow = `<div class="chips ${personal ? 'pk-chips' : ''}" role="group" aria-label="Lọc nhanh">${chips.map(([k, t]) => `<button type="button" class="chip" data-filter="${k}" aria-pressed="${!!filters[k]}">${h(t)}</button>`).join('')}</div>`;
  const search = `<input type="search" class="search" id="kanban-q" value="${h(filters.q || '')}" placeholder="Tìm công việc…" aria-label="Tìm công việc">`;
  const proj = projects ? `<select id="kanban-project" aria-label="Lọc theo dự án"><option value="">Tất cả dự án</option>${projects.map(p => `<option value="${p.id}" ${filters.project === p.id ? 'selected' : ''}>${h(p.name + (p.team_name ? ' · ' + p.team_name : ''))}</option>`).join('')}</select>` : '';
  if (personal) return `<div class="toolbar pk-toolbar">${search}${proj}${chipRow}</div>`;
  return `<div class="toolbar">${search}${proj || filters.actions || ''}</div>${chipRow}`;
}
function bindKanban(tasks, context, filters, holder) {
  const redraw = () => {
    holder.innerHTML = context === 'personal' ? personalBoard(tasks, filters) : kanban(tasks, context, filters);
    const u = new URL(location.href);
    for (const k of ['mine', 'late', 'repair', 'due', 'review']) filters[k] ? u.searchParams.set(k, '1') : u.searchParams.delete(k);
    filters.q ? u.searchParams.set('q', filters.q) : u.searchParams.delete('q');
    if (context !== 'project') filters.project ? u.searchParams.set('project', filters.project) : u.searchParams.delete('project');
    u.searchParams.delete('filter');
    history.replaceState(null, '', u);
  };
  $('#kanban-q').oninput = e => { filters.q = e.target.value.trim().toLowerCase(); redraw(); };
  const sel = $('#kanban-project'); if (sel) sel.onchange = e => { filters.project = Number(e.target.value) || null; redraw(); };
  $$('[data-filter]').forEach(b => b.onclick = () => { const k = b.dataset.filter; filters[k] = !filters[k]; b.setAttribute('aria-pressed', String(filters[k])); redraw(); });
  redraw();
}
const readFilters = () => { const q = new URLSearchParams(location.search), f = q.get('filter'); return {q: (q.get('q') || '').toLowerCase(), project: Number(q.get('project')) || null, mine: q.has('mine'), late: q.has('late') || f === 'late', repair: q.has('repair') || f === 'repair', due: q.has('due') || f === 'due', review: q.has('review') || f === 'review'}; };

// ------------------------------------------------------------------ Tổng quan
const COLORS = {repair: '#4F6D8F', due: '#8EA39D', review: '#B0C0CC', projects: '#B0C0CC', lead: '#6E877F', score: '#363E4F', other: '#D9DFE3', overlap: '#2E4A66'};
function metric(key, label, value, unit, pct, href, aside = '') {
  const shown = value === null || value === undefined ? '—' : value;
  const height = pct > 0 ? Math.max(6, Math.min(100, pct)) : 0;
  return `<article class="metric" data-metric="${key}"><div class="metric-head"><span><span class="legend-dot" style="background:${COLORS[key]}"></span>${h(label)}</span><a href="${h(href)}" aria-label="Xem danh sách: ${h(label)}">→</a></div>
    <div class="bar-box" role="img" aria-label="${h(label)}: ${pct === null ? 'chưa có dữ liệu' : num(pct) + '%'}"><div class="bar-fill" style="height:${height}%;background-color:${COLORS[key]}"></div>${pct === null ? '' : `<span class="bar-pct">${num(pct)}%</span>`}</div>
    <div class="metric-value"><strong>${h(shown)}</strong><small>${h(unit)}</small>${aside ? `<small class="aside">${h(aside)}</small>` : ''}</div></article>`;
}
function pie(title, unit, slices, total) {
  let acc = 0;
  const sum = slices.reduce((s, x) => s + x.value, 0) || 1;
  const stops = slices.map(x => { const a = acc / sum * 360; acc += x.value; return `${x.color} ${a}deg ${acc / sum * 360}deg`; }).join(',');
  return `<article class="pie-card"><div class="pie" role="img" aria-label="${h(title)}" style="background:conic-gradient(${stops || '#D9DFE3 0 360deg'})"></div><div><h3>${h(title)}</h3><p class="small muted" style="margin:0 0 6px">Tổng: ${h(total)} ${h(unit)}</p><ul class="pie-legend">${slices.map(x => `<li><i style="background:${x.color}"></i>${h(x.label)}: <b>${h(num(x.value, x.decimals || 0))}</b> ${h(unit)}</li>`).join('')}</ul></div></article>`;
}
function metricsBlock(s, mode) {
  const total = s.task_total || 0, pct = v => total ? v / total * 100 : 0;
  if (mode === 'pie') {
    const only = (a, b) => Math.max(0, a - b);
    const union = s.repair + s.due - s.repair_due_overlap;
    const score = s.peer_score;
    return `<div class="pies">${pie('Công việc', 'task', [
      {label: 'Chỉ cần sửa', value: only(s.repair, s.repair_due_overlap), color: COLORS.repair},
      {label: 'Cần sửa và đến hạn', value: s.repair_due_overlap, color: COLORS.overlap},
      {label: 'Chỉ đến hạn / quá hạn', value: only(s.due, s.repair_due_overlap), color: COLORS.due},
      {label: 'Chờ duyệt', value: s.review, color: COLORS.review},
      {label: 'Việc còn lại', value: Math.max(0, total - union - s.review), color: COLORS.other}], total)}
      ${pie('Vai trò trong dự án', 'dự án', [{label: 'Làm lead', value: s.lead, color: COLORS.lead}, {label: 'Thành viên', value: s.projects - s.lead, color: COLORS.other}], s.projects)}
      ${score === null ? `<article class="pie-card"><div class="pie" role="img" aria-label="Chưa có đánh giá" style="background:#D9DFE3"></div><div><h3>Điểm đánh giá</h3><p class="muted">Chưa có đánh giá</p></div></article>`
        : pie('Điểm đánh giá', 'điểm', [{label: 'Điểm trung bình', value: score, color: COLORS.score, decimals: 2}, {label: 'Còn lại tới 10', value: 10 - score, color: COLORS.other, decimals: 2}], '10')}</div>`;
  }
  return `<div class="metrics">
    ${metric('repair', 'Cần sửa', s.repair, 'task', pct(s.repair), '/kanban?filter=repair')}
    ${metric('due', 'Đến hạn / quá hạn', s.due, 'task', pct(s.due), '/kanban?filter=due')}
    ${metric('review', 'Chờ duyệt', s.review, 'task', pct(s.review), '/kanban?filter=review')}
    ${metric('projects', 'Dự án tham gia', s.projects, 'dự án', s.projects ? 100 : 0, '/projects')}
    ${metric('lead', 'Dự án làm lead', s.lead, 'dự án', s.projects ? s.lead / s.projects * 100 : 0, '/projects?lead=1')}
    ${metric('score', 'Điểm đánh giá chéo', s.peer_score === null ? null : num(s.peer_score, 2), s.peer_score === null ? 'Chưa có đánh giá' : '/ 10', s.peer_score === null ? null : s.peer_score * 10, '/projects', s.peer_score === null ? '' : s.peer_projects + ' dự án')}
  </div>`;
}
// Line icons for the overview panels (stroke style, inherit currentColor).
const ICONS = {
  task: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2V6z"/><path d="M14 3v3h3"/><path d="M8 9h4M8 12.5h6M8 16h3.5"/><path d="M20.3 11.2l-5.6 6.9-1.9.6.3-2 5.6-6.9a.9.9 0 0 1 1.3-.1l.2.2a.9.9 0 0 1 .1 1.3z"/></svg>',
  update: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M13 5H4a1 1 0 0 0-1 1v10a1 1 0 0 0 1 1h15a1 1 0 0 0 1-1v-4"/><path d="M9 21h6M12 17v4"/><path d="M8.5 9.5 6.8 11l1.7 1.5M13.5 9.5l1.7 1.5-1.7 1.5M11.6 8.6l-1.2 4.8"/><circle cx="18.5" cy="5.5" r="1.8"/><path d="M18.5 2.6v1.1M18.5 7.3v1.1M15.6 5.5h1.1M20.3 5.5h1.1M16.5 3.5l.7.7M19.8 6.8l.7.7M20.5 3.5l-.7.7M17.2 6.8l-.7.7"/></svg>',
  alert: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7.5 17l1-7.5A2 2 0 0 1 10.5 8h3a2 2 0 0 1 2 1.5l1 7.5"/><rect x="5" y="17" width="14" height="3.5" rx="1.5"/><path d="M11.2 11l-.4 4.5M12 3v2.2M6.3 5.3l1.5 1.4M17.7 5.3l-1.5 1.4"/></svg>',
  bell: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 4.5V3.6M7 15V10.5a5 5 0 0 1 10 0V15l1.6 1.6a.8.8 0 0 1-.6 1.4H6a.8.8 0 0 1-.6-1.4z"/><path d="M9.5 19.5a2.5 2.5 0 0 0 5 0z"/></svg>',
  settings: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/></svg>',
  logout: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M15 7V5.5A1.5 1.5 0 0 0 13.5 4h-6A1.5 1.5 0 0 0 6 5.5v13A1.5 1.5 0 0 0 7.5 20h6a1.5 1.5 0 0 0 1.5-1.5V17"/><path d="M10.5 12H20M17 9l3 3-3 3"/></svg>',
};
const panelHead = (id, icon, title, linkHtml = '') => `<div class="col-head"><h2 id="${id}"><span class="panel-icon">${ICONS[icon]}</span>${h(title)}</h2>${linkHtml}</div>`;
const ALERT_LIMIT = 4;
// Cảnh báo cần xử lý: one panel inside the overview grid; hidden when the API returns no alert.
function attentionPanel(alerts) {
  if (!alerts?.length) return '';
  const item = (a, i) => `<a class="alert-item" href="${h(a.link)}" data-alert="${h(a.kind)}" ${i >= ALERT_LIMIT ? 'data-extra hidden' : ''}><span class="badge warn">${h(a.label)}</span><strong>${h(a.task_title)}</strong><small class="muted">${h(a.project_name)}${a.received_at ? ' · Nộp ' + h(dt(a.received_at)) : ''}</small></a>`;
  const more = alerts.length > ALERT_LIMIT ? `<button type="button" class="link-btn more-btn" data-action="more-alerts" aria-expanded="false" aria-controls="attention-list">Xem thêm (${alerts.length - ALERT_LIMIT})</button>` : '';
  return `<section class="col attention-panel" aria-labelledby="alerts-title">${panelHead('alerts-title', 'alert', 'Cảnh báo cần xử lý')}<div class="attention-list" id="attention-list">${alerts.map(item).join('')}</div>${more}</section>`;
}
// Overview row: Task sắp hết hạn → Cập nhật dự án → Cảnh báo cần xử lý → Thông báo gần đây.
function dashboardColumns(d, withUpcoming = true) {
  const up = withUpcoming ? `<section class="col" aria-labelledby="upcoming-title">${panelHead('upcoming-title', 'task', 'Task sắp hết hạn', '<a href="/kanban">Xem Kanban</a>')}${(d.upcoming || []).map(t => `<a class="due-row" href="/tasks/${t.id}"><span class="time"><strong>${h(hm(t.due_at))}</strong><small>${h(dmy(t.due_at))}</small></span><span class="what"><strong>${h(t.title)}</strong><small>${h(t.project_name)}</small></span>${t.overdue ? lateBadge() : soonBadge()}</a>`).join('') || empty('Không có việc sắp đến hạn.')}</section>` : '';
  const act = `<section class="col" aria-labelledby="activity-title">${panelHead('activity-title', 'update', 'Cập nhật dự án', '<a href="/projects">Xem dự án</a>')}${(d.activity || []).map(a => `<div class="activity"><span class="initials" aria-hidden="true">${h(initials(a.actor))}</span><div><div class="top"><strong>${h(a.title)}</strong><small>${h(ago(a.created_at))}</small></div><div class="meta"><b>${h(a.actor)}</b> · ${h(a.project_name)}</div><p>${h(a.subject)}</p></div></div>`).join('') || empty('Chưa có cập nhật.')}</section>`;
  const notes = `<section class="col" aria-labelledby="notes-title">${panelHead('notes-title', 'bell', 'Thông báo gần đây', '<a href="/notifications">Xem tất cả thông báo</a>')}${(d.notifications || []).length ? `<ul class="timeline">${d.notifications.map(n => `<li><small>${h(ago(n.created_at))}</small><a href="${h(n.path || '/notifications')}" data-notification="${n.id}">${h(n.body || n.title)}</a></li>`).join('')}</ul>` : empty('Chưa có thông báo.')}</section>`;
  const panels = [up, act, attentionPanel(d.alerts), notes].filter(Boolean);
  return `<div class="dashboard-columns" data-count="${panels.length}">${panels.join('')}</div>`;
}
async function dashboardPage() {
  const d = homeData;
  if (isStaff()) return teacherHome(d);
  const s = d.stats || {task_total: 0, repair: 0, due: 0, review: 0, repair_due_overlap: 0, projects: 0, lead: 0, peer_score: null, peer_projects: 0};
  const invs = (await api('/me/invitations')).items.filter(i => i.status === 'pending');
  window.invites = invs;
  const mode = store.get('ts-chart', 'bar');
  return `<section class="attention" aria-labelledby="att-title"><div class="attention-head"><div><h1 id="att-title" class="page-title">Việc cần chú ý</h1><p>Theo dõi công việc của bạn trong các dự án</p></div>
      <div class="actions"><a class="button review-btn" href="/submissions?tab=review" id="review-link">Bài cần tôi duyệt · ${d.review_queue}</a>
      <div class="segmented" role="group" aria-label="Kiểu biểu đồ"><button type="button" data-chart="bar" aria-pressed="${mode === 'bar'}">▮ Cột</button><button type="button" data-chart="pie" aria-pressed="${mode === 'pie'}">◔ Tròn</button></div></div></div>
      <div id="metrics">${metricsBlock(s, mode)}</div><p class="small muted" style="margin:10px 2px 0">Chờ duyệt: số task đang ở trạng thái Chờ duyệt trong các dự án. Bài cần tôi duyệt: lần nộp bạn được phép quyết định.</p></section>
    ${invs.length ? panel('Lời mời vào nhóm', invs.map(i => `<div class="history-row"><strong>${h(i.project_name)}</strong><div class="actions">${button('Tham gia', 'invite:' + i.id)}${button('Từ chối', 'reject-invite:' + i.id, 'secondary')}</div></div>`).join('')) : ''}
    ${dashboardColumns(d)}
    <div class="toolbar"><h2 class="section-title" style="margin:0">Dự án của tôi</h2><div class="actions"><input type="search" class="search" data-search-input placeholder="Tìm dự án…" aria-label="Tìm dự án">${isStaff() ? '' : button('Tạo dự án', 'create-project', 'secondary')}</div></div>
    <div class="project-grid">${d.projects.map(projectCard).join('') || empty('Bạn chưa tham gia dự án nào.')}</div>`;
}
dashboardPage.bind = () => {
  $$('[data-chart]').forEach(b => b.onclick = () => {
    store.set('ts-chart', b.dataset.chart);
    $$('[data-chart]').forEach(x => x.setAttribute('aria-pressed', String(x === b)));
    $('#metrics').innerHTML = metricsBlock(homeData.stats, b.dataset.chart);
  });
};
function teacherHome(d) {
  const help = d.projects.reduce((n, p) => n + p.help, 0);
  const courses = d.courses.filter(c => ['instructor', 'coordinator'].includes(c.my_role));
  const rows = d.review_rows || [];
  const reviewPanel = panel(`Bài được chuyển cho tôi · ${rows.length}`, rows.length ? submissionTable(rows) : empty('Không có bài nào được chuyển cho bạn duyệt.'), 'id="review-list"');
  return pageHead('Tổng quan giảng viên', 'Theo dõi học phần phụ trách, nhóm chờ duyệt, bài được chuyển và yêu cầu hỗ trợ', `<a class="button review-btn" href="#review-list" id="review-link">Bài được chuyển cho tôi · ${d.review_queue}</a>${isTeacher() ? button('Tạo lớp', 'create-course') : ''}`) +
    `<div class="stats"><a class="stat" href="/courses"><span>Học phần phụ trách</span><strong>${courses.length}</strong></a><a class="stat" href="#pending-groups"><span>Nhóm chờ duyệt</span><strong>${d.pending_groups.length}</strong></a><a class="stat" href="#help-list"><span>Yêu cầu hỗ trợ</span><strong>${help}</strong></a><a class="stat" href="#review-list"><span>Bài được chuyển</span><strong>${d.review_queue}</strong></a></div>` +
    reviewPanel +
    `<div class="grid2">${panel('Nhóm chờ duyệt', d.pending_groups.map(g => `<div class="history-row"><div><strong>${h(g.name)}</strong><p class="small muted" style="margin:0">${h(g.course_title)}</p></div>${link('Xem nhóm', '/projects/' + g.id)}</div>`).join('') || empty('Không có nhóm chờ duyệt.'), 'id="pending-groups"')}
    ${panel('Yêu cầu hỗ trợ', d.projects.filter(p => p.help).map(p => `<div class="history-row"><div><strong>${h(p.name)}</strong><p class="small muted" style="margin:0">${h(p.course_title)} · ${p.help} yêu cầu</p></div>${link('Hỗ trợ', '/projects/' + p.id + '?tab=help')}</div>`).join('') || empty('Không có yêu cầu hỗ trợ đang mở.'), 'id="help-list"')}</div>` +
    panel('Học phần phụ trách', courses.map(courseRow).join('') || empty('Chưa có học phần.')) + dashboardColumns(d, false);
}

// ------------------------------------------------------------------ Dự án của tôi
const PROJECT_SORTS = [['progress-desc', 'Tiến độ giảm dần'], ['progress-asc', 'Tiến độ tăng dần'], ['created-desc', 'Ngày tạo mới nhất']];
async function projectsPage() {
  const q = new URLSearchParams(location.search), lead = q.has('lead');
  const sort = PROJECT_SORTS.some(([k]) => k === q.get('sort')) ? q.get('sort') : 'progress-desc';
  const ps = homeData.projects, leads = ps.filter(p => p.my_role === 'leader').length;
  return `<div class="toolbar projects-toolbar"><div class="segmented" role="group" aria-label="Lọc dự án"><button type="button" data-plist="all" aria-pressed="${!lead}">Tất cả<span class="count">${ps.length}</span></button>${isStaff() ? '' : `<button type="button" data-plist="lead" aria-pressed="${lead}">Tôi làm lead<span class="count">${leads}</span></button>`}</div>
    <div class="toolbar-right"><label class="search-box"><span class="sr-only">Tìm dự án</span>${SEARCH_ICON}<input type="search" id="project-q" placeholder="Tìm dự án…"></label>
    <select id="project-sort" aria-label="Sắp xếp dự án">${PROJECT_SORTS.map(([k, t]) => `<option value="${k}" ${k === sort ? 'selected' : ''}>${t}</option>`).join('')}</select>
    <button type="button" data-action="create-project" class="create-btn"><span aria-hidden="true">+</span> Tạo dự án</button></div></div>
    <div class="project-grid tinted" id="project-grid">${ps.map(projectCard).join('')}</div><div id="project-empty" hidden>${empty('Không có dự án phù hợp.')}</div>`;
}
projectsPage.bind = () => {
  let lead = new URLSearchParams(location.search).has('lead'), q = '', sort = $('#project-sort').value;
  const grid = $('#project-grid');
  const value = (c, key) => key === 'created' ? Date.parse(c.dataset.created) || 0 : Number(c.dataset.progress);
  const apply = () => {
    const cards = [...grid.children];
    const [key, dir] = sort.split('-');
    // Filter (tab + search) first, then sort the visible set; ties keep the API order (stable).
    cards.sort((a, b) => (dir === 'asc' ? value(a, key) - value(b, key) : value(b, key) - value(a, key)) || a.dataset.index - b.dataset.index);
    let n = 0;
    cards.forEach(c => { const ok = (!lead || c.dataset.lead === 'true') && c.dataset.search.includes(q); c.hidden = !ok; n += ok; grid.append(c); });
    $('#project-empty').hidden = n > 0;
    const u = new URL(location.href); lead ? u.searchParams.set('lead', '1') : u.searchParams.delete('lead');
    sort === 'progress-desc' ? u.searchParams.delete('sort') : u.searchParams.set('sort', sort); history.replaceState(null, '', u);
  };
  $$('[data-plist]').forEach(b => b.onclick = () => { lead = b.dataset.plist === 'lead'; $$('[data-plist]').forEach(x => x.setAttribute('aria-pressed', String(x === b))); apply(); });
  $('#project-q').oninput = e => { q = e.target.value.trim().toLowerCase(); apply(); };
  $('#project-sort').onchange = e => { sort = e.target.value; apply(); };
  apply();
};
// Tạo dự án: dự án nhóm thuộc một đề bài; máy chủ kiểm tra quyền và điều kiện lập nhóm.
function createProjectModal() {
  const staff = homeData.courses.filter(c => ['instructor', 'coordinator'].includes(c.my_role) && c.assignment);
  if (staff.length) {
    return modal('Tạo dự án', select('assignment', 'Học phần', staff.map(c => [c.assignment.id, `${c.title} · ${c.code}`])) + '<p class="small muted">Bước tiếp theo: đặt tên nhóm, chọn trưởng nhóm và thành viên.</p>',
      async f => { setTimeout(() => attempt(() => action('teacher-group:' + f.get('assignment'))), 0); return 'Chọn thành viên cho nhóm mới'; }, 'Tiếp tục');
  }
  const open = homeData.courses.filter(c => c.my_role === 'student' && c.assignment && c.assignment.group_mode === 'self' && c.assignment.status === 'active' && !c.groups.length);
  if (!open.length) return modal('Tạo dự án', empty('Hiện không có học phần nào đang mở cho bạn tự lập nhóm. Bạn đã có nhóm ở các học phần tự lập, hoặc người phụ trách sẽ xếp nhóm.'), null);
  return modal('Tạo dự án', select('assignment', 'Học phần (đề bài nhóm)', open.map(c => [c.assignment.id, `${c.title} · ${c.assignment.title}`])) + field('name', 'Tên nhóm dự án', 'text', '', true, 'maxlength="200"') +
    '<p class="small muted">Nhóm được tạo ở trạng thái nháp, bạn là trưởng nhóm. Mời thành viên rồi gửi giảng viên duyệt.</p>',
    async f => { const p = await api(`/assignments/${f.get('assignment')}/projects`, {name: f.get('name')}); history.pushState({}, '', '/projects/' + p.id + '?tab=members'); return 'Đã tạo dự án'; }, 'Tạo dự án');
}

// ------------------------------------------------------------------ Kanban cá nhân
// Chỉ task có người đăng nhập trong danh sách phân công (phụ trách hoặc cùng làm); việc chỉ cần duyệt nằm ở Bài nộp.
let kanbanTasks = [];
const PRIORITY_RANK = {high: 0, medium: 1, low: 2};
async function kanbanPage() {
  const d = await api('/workflow/tasks?scope=mine');
  kanbanTasks = d.items;
  return `<section class="kanban-personal">${kanbanControls(readFilters(), d.projects, true)}<div id="board"></div></section>`;
}
kanbanPage.bind = () => bindKanban(kanbanTasks, 'personal', readFilters(), $('#board'));
function personalBoard(tasks, f) {
  const shown = tasks.map((t, i) => ({t, i})).filter(({t}) => (!f.project || t.project_id === f.project) && (!f.q || t.title.toLowerCase().includes(f.q))
    && (!f.late || t.overdue) && (!f.repair || isRepair(t)) && (!f.due || isDue(t)) && (!f.review || t.status === 'review'));
  // Ưu tiên cao → vừa → thấp, cùng mức thì hạn sớm trước, không có hạn xếp sau; giữ thứ tự gốc khi bằng nhau.
  const order = (a, b) => (PRIORITY_RANK[a.t.priority] ?? 1) - (PRIORITY_RANK[b.t.priority] ?? 1)
    || (a.t.due_at ? Date.parse(a.t.due_at) : Infinity) - (b.t.due_at ? Date.parse(b.t.due_at) : Infinity) || a.i - b.i;
  return `<div class="board pk-board">${STATUS.map(s => { const col = shown.filter(x => x.t.status === s).sort(order);
    return `<section class="pk-column pk-${s}" aria-labelledby="pk-h-${s}"><h2 class="pk-head" id="pk-h-${s}"><span>${labels[s]}</span><span class="pk-count" aria-label="${col.length} công việc">${col.length}</span></h2>
      <div class="pk-list">${col.map(({t}) => personalCard(t)).join('') || '<p class="pk-empty">Không có công việc</p>'}</div></section>`; }).join('')}</div>`;
}
function personalCard(t) {
  const tags = (t.overdue ? '<span class="pk-tag late">Quá hạn</span>' : '') + (isRepair(t) ? '<span class="pk-tag repair">Cần sửa</span>' : '');
  const due = t.due_at ? `${hm(t.due_at)} · ${dm(t.due_at)}` : 'Chưa có hạn';
  return `<a class="pk-card" href="/tasks/${t.id}" data-priority="${h(t.priority)}"><div class="pk-top"><span class="pk-tags">${tags}</span><span class="pk-due ${t.overdue ? 'late' : ''}" title="Hạn nộp">${CAL_ICON}${h(due)}</span></div>
    <h3>${h(t.title)}</h3><small>${h(t.project_name)}${t.team_name ? ' · ' + h(t.team_name) : ''}</small></a>`;
}

// ------------------------------------------------------------------ chi tiết dự án
const TABS = [['board', 'Công việc'], ['members', 'Thành viên'], ['submissions', 'Bài nộp'], ['minutes', 'Biên bản họp'], ['report', 'Báo cáo & sản phẩm'], ['peer', 'Đánh giá chéo'], ['help', 'Hỗ trợ']];
const TAB_ICONS = {
  board: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 6.5h11M9 12h11M9 17.5h11"/><path d="M4 6.5l1 1 2-2M4 12l1 1 2-2M4 17.5l1 1 2-2"/></svg>',
  members: NAV_ICONS.users,
  submissions: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M14 3.5H7.5a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2h9a2 2 0 0 0 2-2V8z"/><path d="M14 3.5V8h4.5M9 12.5h6M9 16h6"/></svg>',
  minutes: CAL_ICON,
  report: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3.5 20 7.5v9L12 20.5 4 16.5v-9z"/><path d="M4 7.5l8 4 8-4M12 11.5v9"/></svg>',
  peer: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m12 3.8 2.5 5.1 5.6.8-4 3.9 1 5.6L12 16.6l-5 2.6 1-5.6-4-3.9 5.5-.8z"/></svg>',
  help: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="8.5"/><path d="M9.6 9.5a2.5 2.5 0 1 1 3.4 2.3c-.7.3-1 .8-1 1.5v.5M12 16.8v.2"/></svg>',
};
const HEAD_ICONS = {
  project: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3.5 21 8l-9 4.5L3 8z"/><path d="m3 12 9 4.5 9-4.5M3 16l9 4.5 9-4.5"/></svg>',
  check: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="8.5"/><path d="m8.3 12.2 2.5 2.5 4.9-5"/></svg>',
  course: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M2.5 9 12 4.5 21.5 9 12 13.5z"/><path d="M6.5 11v4.5c1.5 1.5 3.5 2.2 5.5 2.2s4-.7 5.5-2.2V11M21.5 9v5"/></svg>',
};
function projectTabs(p, current) {
  const items = TABS.filter(([k]) => !(k === 'minutes' && p.my_role in {instructor: 1, coordinator: 1}));
  return `<nav class="tabs project-tabs" aria-label="Mục dự án">${items.map(([k, t]) => `<a href="/projects/${p.id}?tab=${k}" ${current === k ? 'aria-current="page"' : ''}><span class="tab-icon">${TAB_ICONS[k]}</span>${h(t)}</a>`).join('')}</nav>`;
}
// Project header: one row — icon | name + team | status | members | progress | Học phần (wraps on narrow screens).
function projectHead(p) {
  const active = p.members.filter(m => m.status === 'active').length, pct = p.progress.total ? Math.round(p.progress.done / p.progress.total * 100) : 0;
  const shown = pct === 100 && p.progress.done !== p.progress.total ? 99 : pct;
  return `${isStaff() ? `<a class="crumb ph-crumb" href="/courses/${p.course_id}?tab=groups">← Các nhóm của học phần</a>` : '<a class="crumb ph-crumb" href="/projects">← Dự án của tôi</a>'}
    <section class="project-head ph-row" aria-label="Thông tin dự án">
      <span class="ph-icon">${HEAD_ICONS.project}</span>
      <div class="ph-name"><h1 class="page-title">${h(p.name)}</h1><div class="team">${h(p.team_name || p.assignment.title)} · ${h(labels[p.my_role] || p.my_role)}</div></div>
      <div class="ph-meta">
        <span class="ph-status st-${h(p.status)}"><i aria-hidden="true"></i>${h(labels[p.status] || p.status)}</span>
        <span class="ph-item"><span class="ph-ic">${NAV_ICONS.users}</span>${active} thành viên</span>
        <span class="ph-item ph-progress"><span class="ph-ic">${HEAD_ICONS.check}</span>${p.progress.done}/${p.progress.total} công việc hoàn thành<span class="progress" role="img" aria-label="Tiến độ ${shown}%"><span style="width:${shown}%"></span></span><b>${shown}%</b></span>
      </div>
      <a class="button outline-btn ph-course" href="/courses/${p.course_id}"><span class="ph-ic">${HEAD_ICONS.course}</span>Học phần</a>
    </section>`;
}
let groupTasks = [], groupTab = 'board';
async function groupPage(id) {
  projectData = await api('/projects/' + id);
  const p = projectData;
  groupTab = new URLSearchParams(location.search).get('tab') || 'board';
  if (!TABS.some(([k]) => k === groupTab)) groupTab = 'board';
  groupTasks = await all('/projects/' + id + '/tasks');
  let top = projectHead(p) + projectTabs(p, groupTab);
  if (p.status !== 'active') top += panel(labels[p.status] || p.status, `<p>${p.members.filter(m => m.status === 'active').length}/${p.assignment.group_min} thành viên tối thiểu · tối đa ${p.assignment.group_max}</p><div class="actions">${isLeader() && p.status === 'draft' ? button('Gửi giảng viên duyệt', 'submit-group') : ''}${isTeacher() && p.status === 'pending' ? button('Duyệt nhóm', 'approve-group') + button('Yêu cầu bổ sung', 'return-group', 'secondary') : ''}</div>`);
  if (groupTab === 'board') return top + kanbanControls({...readFilters(), actions: !isStaff() && p.status === 'active' ? `<div class="actions">${isLeader() ? `<button type="button" data-action="ai-plan" class="secondary ai-btn">${AI_ICON}<span>AI lập kế hoạch</span></button>` : ''}${button('Tạo công việc', 'new-task')}</div>` : ''}) + '<div id="board"></div>';
  if (groupTab === 'members') return top + await membersTab(p);
  if (groupTab === 'submissions') return top + await projectSubmissionsTab(p);
  if (groupTab === 'minutes') return top + await minutesTab(p);
  if (groupTab === 'report') return top + await reportTab(p);
  if (groupTab === 'peer') return top + await peerTab(p);
  return top + await helpTab(p);
}
groupPage.bind = () => { if (groupTab === 'members') bindAvatars(); if (groupTab === 'board') bindKanban(groupTasks, 'project', readFilters(), $('#board')); if (groupTab === 'report') drawCharts(); };
// ------------------------------------------------------------------ Thành viên (thẻ poster)
// Ảnh mặc định: app/static/img/avatars/*.svg — thay bằng bộ ảnh gốc cùng tên để đổi hình.
const AVATARS = ['smile', 'crown', 'headband', 'pixel', 'blush', 'tongue'];
const avatarFor = uid => `/static/img/avatars/${AVATARS[(Math.imul(Number(uid) || 0, 2654435761) >>> 0) % AVATARS.length]}.svg`;
const MAIL_ICON = '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3.5" y="5.5" width="17" height="13" rx="2"/><path d="m4 7 8 6 8-6"/></svg>';
const USER_ICON = '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="8.5" r="3.6"/><path d="M5 20c.8-3.8 3.6-6 7-6s6.2 2.2 7 6"/></svg>';
const ID_ICON = '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="5.5" width="18" height="13" rx="2"/><circle cx="8.5" cy="11" r="2"/><path d="M5.8 15.5c.5-1.3 1.5-2 2.7-2s2.2.7 2.7 2M14 10h4.5M14 13.5h4.5"/></svg>';
function memberCard(m) {
  const leader = m.role === 'leader', score = m.peer_score;
  const pct = score === null || score === undefined ? 0 : Math.max(0, Math.min(100, score * 10));
  const fallback = avatarFor(m.user.id);
  return `<article class="member-card" aria-label="${h(m.user.full_name)}">
    <h3 class="member-name">${h(m.user.full_name)}</h3>
    <div class="member-photo"><img src="${h(m.user.avatar_url || fallback)}" data-fallback="${h(fallback)}" alt="Ảnh đại diện của ${h(m.user.full_name)}" width="210" height="210" loading="lazy"></div>
    <ul class="member-info">
      <li><span class="mi-ic">${MAIL_ICON}</span><span class="mi-label">Email:</span><span class="mi-value">${m.user.email ? h(m.user.email) : '—'}</span></li>
      <li><span class="mi-ic">${USER_ICON}</span><span class="mi-label">Vai trò:</span><span class="mi-value">${leader ? '<span class="role-pill">Trưởng nhóm</span>' : 'Thành viên'}</span></li>
      <li><span class="mi-ic">${ID_ICON}</span><span class="mi-label">Mã sinh viên:</span><span class="mi-value">${h(m.student_code || '—')}</span></li>
    </ul>
    <div class="member-score">
      <div class="ms-row"><b>Điểm hiện tại</b><span>${score === null || score === undefined ? 'Chưa có điểm' : num(score, score % 1 ? (Math.round(score * 10) === score * 10 ? 1 : 2) : 0) + ' / 10'}</span></div>
      <div class="ms-bar" role="meter" aria-valuemin="0" aria-valuemax="10" aria-valuenow="${score ?? 0}" aria-label="Điểm đánh giá chéo của ${h(m.user.full_name)}: ${score === null || score === undefined ? 'chưa có điểm' : num(score, 2) + ' trên 10'}"><span style="width:${pct}%"></span></div>
    </div></article>`;
}
async function membersTab(p) {
  const ds = (await api(`/workflow/projects/${p.id}/departures`)).items;
  window.departuresData = ds;
  let candidates = [];
  if (isLeader() && p.status === 'draft') candidates = (await api(`/assignments/${p.assignment_id}/invite-candidates`)).students;
  window.candidates = candidates;
  // Leader first, then API order (stable).
  const active = p.members.map((m, i) => ({m, i})).filter(x => x.m.status === 'active').sort((a, b) => (b.m.role === 'leader') - (a.m.role === 'leader') || a.i - b.i).map(x => x.m);
  const left = p.members.filter(m => m.status !== 'active');
  const actions = `${candidates.length ? button('Mời thành viên', 'invite-member') : ''}${!isStaff() ? `<button type="button" class="secondary icon-text" data-action="leave-group">${ICONS.logout}<span>Xin rời nhóm</span></button>` : isTeacher() ? button('Xếp thêm / tiếp nhận lại', 'readmit', 'secondary') : ''}`;
  return `<section class="members-section" aria-labelledby="members-title"><h2 id="members-title" class="members-title">Thành viên</h2>
    ${active.length ? `<div class="member-grid">${active.map(memberCard).join('')}</div>` : panel('', empty('Nhóm chưa có thành viên đang tham gia.'))}
    ${left.length ? `<div class="members-left"><h3>Đã rời nhóm</h3><ul>${left.map(m => `<li><span>${h(m.user.full_name)}</span><small class="muted">${h(m.user.email)}</small>${badge('left')}</li>`).join('')}</ul></div>` : ''}
    ${actions ? `<div class="actions members-actions">${actions}</div>` : ''}</section>` +
    ds.map(x => panel('Yêu cầu rời · ' + x.user.full_name, `<p class="preserve">${h(x.reason)}</p>${badge(x.status)}${x.leader_exit ? `<p>${x.yes}/${x.threshold} phiếu đồng ý cần thiết (ceil(số thành viên còn lại / 2))</p>` : ''}${x.successor ? `<p>Trưởng nhóm kế nhiệm: ${h(x.successor.full_name)}</p>` : ''}${x.status === 'pending' && !isStaff() && ((x.leader_exit && x.electorate.includes(me.id) && !(String(me.id) in x.votes)) || (!x.leader_exit && isLeader())) ? `<div class="actions" style="margin-top:10px">${button('Đồng ý', 'vote-yes:' + x.id)}${button('Không đồng ý', 'vote-no:' + x.id, 'secondary')}</div>` : ''}`)).join('');
}
function bindAvatars() {
  // Missing or broken profile photo → stable default avatar for that user.
  $$('.member-photo img').forEach(img => { const swap = () => { if (img.src.endsWith(img.dataset.fallback)) return; img.src = img.dataset.fallback; }; img.addEventListener('error', swap, {once: true}); if (img.complete && !img.naturalWidth) swap(); });
}
async function projectSubmissionsTab(p) {
  const q = await api('/workflow/submissions');
  const rows = [...q.to_review, ...q.mine].filter(r => r.project_id === p.id);
  const latest = groupTasks.filter(t => t.latest_submission_id);
  return panel('Bài liên quan tới bạn', rows.length ? submissionTable(rows) : empty('Chưa có bài nộp liên quan tới bạn trong dự án này.')) +
    panel('Lần nộp mới nhất của từng công việc', latest.length ? table(['Công việc', 'Trạng thái', ''], latest.map(t => [`<strong>${h(t.title)}</strong>`, badge(t.latest_submission_status), link('Xem bản nộp', `/tasks/${t.id}?submission=${t.latest_submission_id}#submission-${t.latest_submission_id}`, 'button secondary')])) : empty('Nhóm chưa có bài nộp.'));
}
async function minutesTab(p) {
  const ms = (await api(`/workflow/projects/${p.id}/minutes`)).items;
  window.minutesData = ms;
  return `<div class="toolbar"><h2 class="section-title" style="margin:0">Biên bản họp</h2>${button('Thêm biên bản', 'new-minutes')}</div>` +
    (ms.map(m => panel(m.title, `<small class="muted">${dt(m.created_at)}</small><p class="preserve">${h(m.notes)}</p>${p.status === 'active' ? button('Tạo việc từ kết luận', 'minute-task:' + m.id, 'secondary') : ''}`)).join('') || empty('Chưa có biên bản họp.'));
}
// ------------------------------------------------------------------ Đánh giá chéo theo công việc
const score1 = v => v === null || v === undefined ? '—' : num(v, 2);
const peerMemberTable = rows => table(['Thành viên', 'Số công việc', 'Số phiếu', 'Hợp tác /10', 'Chất lượng /10', 'Trung bình /10'],
  rows.map(x => [h(x.user.full_name), x.tasks, x.count, score1(x.attitude), score1(x.quality), `<strong>${score1(x.average)}</strong>`]));
const peerTaskTable = rows => table(['Công việc', 'Người làm', 'Số phiếu', 'Hợp tác /10', 'Chất lượng /10', 'Trung bình /10'],
  rows.map(x => [h(x.task_title), h(x.user.full_name), x.count, score1(x.attitude), score1(x.quality), `<strong>${score1(x.average)}</strong>`]));
function peerTaskCard(t) {
  const who = t.workers.map(u => h(u.full_name)).join(', ') || '—';
  const state = t.open ? `<span class="badge">Đang mở · đến ${dt(t.closes_at)}</span>` : badge('Đã công bố', 'good');
  let body = '';
  if (t.open) {
    body = t.can_review
      ? `<p class="small muted">Bạn đã trả lời ${t.reviewed}/${t.expected} người làm (gồm cả bỏ qua). Có thể sửa tới khi đóng.</p><div class="actions">${button(t.reviewed ? 'Sửa đánh giá' : 'Đánh giá người làm', 'peer-task:' + t.id, t.reviewed ? 'secondary' : '')}</div>`
      : `<p class="small muted">${t.i_worked ? 'Bạn là người làm công việc này nên không tự đánh giá.' : isStaff() ? 'Thành viên nhóm đang đánh giá.' : 'Bạn không thuộc nhóm người được đánh giá công việc này.'} Đã nhận ${t.received} phiếu; kết quả công bố sau khi đóng.</p>`;
  } else {
    body = (t.results || []).map(r => `<div class="peer-result"><div class="pr-head"><strong>${h(r.user.full_name)}</strong><span>${r.count ? `${r.count} phiếu · Hợp tác ${score1(r.attitude)} · Chất lượng ${score1(r.quality)} · <b>Trung bình ${score1(r.average)}/10</b>` : '<span class="muted">Không có phiếu</span>'}</span></div>${r.comments.length ? `<ul class="peer-comments">${r.comments.map(c => `<li>${h(c)}</li>`).join('')}</ul>` : ''}</div>`).join('') || empty('Không có người làm.');
  }
  return `<article class="panel peer-task ${t.can_review && t.reviewed < t.expected ? 'needs' : ''}" id="peer-task-${t.id}"><div class="toolbar" style="margin-bottom:6px"><div><h3 style="margin:0">${link(t.title, '/tasks/' + t.id, 'plain-link')}</h3><small class="muted">Người làm: ${who} · Hoàn thành ${dt(t.completed_at)}</small></div>${state}</div>${body}</article>`;
}
async function peerTab(p) {
  const d = await api(`/workflow/projects/${p.id}/peer`);
  window.peerData = d;
  const mine = d.tasks.filter(t => t.can_review), others = d.tasks.filter(t => !t.can_review);
  return (d.pending ? `<p><span class="badge warn">${d.pending} công việc chờ bạn đánh giá</span></p>` : '') +
    (d.members.length ? panel('Tổng hợp theo thành viên (đã công bố)', peerMemberTable(d.members)) : '') +
    (mine.length ? `<h2 class="section-title">Chờ bạn đánh giá</h2>${mine.map(peerTaskCard).join('')}` : '') +
    (others.length ? `<h2 class="section-title">${mine.length ? 'Các công việc khác' : 'Công việc đã hoàn thành'}</h2>${others.map(peerTaskCard).join('')}` : '') +
    (!d.tasks.length ? empty('Chưa có công việc hoàn thành để đánh giá.') : '');
}
function peerTaskForm(t) {
  const range = Array.from({length: 10}, (_, i) => [i + 1, i + 1]);
  const body = `<p class="small muted">${h(t.title)} · đóng lúc ${dt(t.closes_at)}. Người được đánh giá không thấy bạn là ai.</p>` + t.workers.map(u => {
    const x = t.own.find(o => o.reviewee_id === u.id);
    return `<fieldset><legend>${h(u.full_name)}</legend><label class="check"><input type="checkbox" name="skip_${u.id}" ${x?.skipped ? 'checked' : ''}>Chưa đủ cơ sở / bỏ qua</label><div class="grid2">${select('at_' + u.id, 'Hợp tác', range, x?.attitude || 8)}${select('qu_' + u.id, 'Chất lượng', range, x?.quality || 8)}</div><label>Nhận xét (tùy chọn)<textarea name="cm_${u.id}" maxlength="1000">${h(x?.comment || '')}</textarea></label></fieldset>`;
  }).join('');
  return modal('Đánh giá người làm', body, async f => {
    await api(`/workflow/tasks/${t.id}/peer`, {items: t.workers.map(u => ({reviewee_id: u.id, skip: f.has('skip_' + u.id), attitude: Number(f.get('at_' + u.id)), quality: Number(f.get('qu_' + u.id)), comment: f.get('cm_' + u.id) || ''}))}, 'PUT');
    return 'Đã lưu đánh giá chéo';
  });
}
let reportData = null;
async function reportTab(p) {
  const d = await api(`/workflow/projects/${p.id}/report`);
  reportData = d;
  const ex = fmt => `/api/v1/workflow/projects/${p.id}/export?format=${fmt}`;
  return `<div class="toolbar"><div><h2 class="section-title" style="font-size:28px;margin:0">Báo cáo &amp; sản phẩm</h2><p class="muted" style="margin:4px 0 0">Dữ liệu mới nhất của nhóm</p></div><div class="actions">${link('Excel', ex('xlsx'))}${link('PDF', ex('pdf'))}${link('Bản in', ex('html'), 'button secondary', 'target="_blank" rel="noopener"')}</div></div>` +
    panel('Minh chứng theo tiêu chí', `<p class="muted">Tổng hợp lần nộp mới nhất của mỗi công việc.</p>${d.evidence.length ? table(['Tiêu chí', 'Bản đã duyệt', 'Bản chờ duyệt', 'Bản cần sửa'], d.evidence.map(e => [h(e.title) + (e.is_active ? '' : ' ' + badge('Đã ẩn', 'neutral')), e.accepted, e.pending, e.returned])) : empty('Đề bài chưa có tiêu chí minh chứng.')}`) +
    `<div class="grid2">${panel('Trạng thái công việc', '<div class="chart"><canvas id="status-chart" aria-label="Biểu đồ trạng thái công việc" role="img"></canvas></div>')}${panel('Khối lượng ghi nhận', '<div class="chart"><canvas id="contribution-chart" aria-label="Biểu đồ khối lượng ghi nhận" role="img"></canvas></div>')}</div>` +
    panel('Đóng góp', table(['Thành viên', 'Khối lượng đã duyệt', 'Tỷ trọng %'], d.members.map(m => [h(m.user.full_name), num(m.accepted_workload, 2), num(m.percent, 2)])) + `<details><summary>Cách tính</summary><p>${h(d.formula)}</p></details>`) +
    panel('Đánh giá chéo theo công việc (đã công bố)', d.peer.length ? peerMemberTable(d.peer) + `<details><summary>Chi tiết theo từng công việc</summary>${peerTaskTable(d.peer_tasks)}</details>` : empty('Chưa có kết quả đánh giá chéo được công bố.')) +
    panel('Sản phẩm bàn giao', `${isLeader() ? button('Chọn bài đã duyệt để bàn giao', 'deliver') : ''}${d.deliveries.map(x => `<div class="history-row"><div><strong>${h(x.title)}</strong><p class="small muted" style="margin:0">${dt(x.created_at)}</p><div class="actions">${x.submission_ids.map(sid => { const t = d.tasks.find(t => t.submissions?.some(s => s.id === sid)); return t ? link(t.title, `/tasks/${t.id}?submission=${sid}#submission-${sid}`, 'attempt') : ''; }).join('')}</div></div></div>`).join('') || empty('Chưa bàn giao sản phẩm nhóm')}`);
}
function drawCharts() {
  if (!window.Chart || !reportData) return;
  const d = reportData;
  for (const [id, lbl, values, color] of [['status-chart', STATUS.map(s => labels[s]), STATUS.map(s => d.tasks.filter(t => t.status === s).length), '#8EA39D'], ['contribution-chart', d.members.map(m => m.user.full_name), d.members.map(m => Number(m.accepted_workload)), '#363E4F']]) {
    const el = document.getElementById(id);
    if (el) charts.push(new Chart(el, {type: 'bar', data: {labels: lbl, datasets: [{label: 'Giá trị', data: values, backgroundColor: color, borderRadius: 5}]}, options: {responsive: true, maintainAspectRatio: false, plugins: {legend: {display: false}}, scales: {y: {beginAtZero: true, ticks: {precision: 0}}}}}));
  }
}
async function helpTab(p) {
  const hs = await all(`/projects/${p.id}/help-requests`);
  window.helpData = hs;
  const cs = (await api(`/workflow/projects/${p.id}/complaints`)).items;
  window.casesData = cs;
  return `<div class="toolbar"><h2 class="section-title" style="margin:0">Hỗ trợ từ giảng viên</h2>${!isStaff() ? button('Gửi yêu cầu hỗ trợ', 'new-help') : ''}</div>` +
    hs.map(x => panel(x.subject, `${badge(x.status)}<p class="preserve">${h(x.content)}</p>${x.response ? `<div class="feedback">${h(x.response)}</div>` : ''}${isTeacher() && x.status !== 'resolved' ? button('Phản hồi', 'help-response:' + x.id) : ''}`)).join('') +
    cs.filter(x => isStaff() ? x.handler === 'instructor' : x.status === 'open').map(caseCard).join('') + (!hs.length && !cs.length ? empty('Chưa có yêu cầu hỗ trợ') : '');
}
function caseCard(c) {
  const handler = c.handler === 'instructor' ? isTeacher() : isLeader() && ![c.raised_by, c.target_id].includes(me.id);
  return panel('Điều chỉnh đóng góp · ' + c.target_name, `${badge(c.status)}<p class="preserve">${h(c.reason)}</p>${c.explanation ? `<div class="feedback">${h(c.explanation)}</div>` : ''}${c.resolution ? `<p>${h(c.resolution)}</p>` : ''}<div class="actions">${c.status === 'open' && c.target_id === me.id ? button('Gửi giải trình', 'explain:' + c.id, 'secondary') : ''}${c.status === 'open' && handler ? button('Xử lý đề nghị', 'resolve:' + c.id) : ''}${c.status === 'open' && c.handler === 'leader' && isLeader() ? button('Nhờ giảng viên hỗ trợ', 'escalate:' + c.id, 'secondary') : ''}</div>`);
}

// ------------------------------------------------------------------ chi tiết task
let taskFocus = null;
async function taskPage(id) {
  taskData = await api('/tasks/' + id);
  const t = taskData;
  projectData = await api('/projects/' + t.project_id);
  const p = projectData;
  criteriaData = (await api(`/workflow/assignments/${p.assignment_id}/evidence-criteria`)).items;
  const can = t.participants.some(x => x.user_id === me.id) && !isStaff();
  const subs = [...t.submissions].reverse();
  const want = Number(new URLSearchParams(location.search).get('submission')) || null;
  const focus = subs.find(s => s.id === want) || subs[0];
  taskFocus = focus?.id || null;
  const reviewable = subs.find(s => s.can_review);
  const resp = t.participants.find(x => x.role === 'responsible'), collab = t.participants.filter(x => x.role === 'collaborator');
  let html = pageHead(t.title, p.name + (p.team_name ? ' · ' + p.team_name : ''), link('Về bảng công việc', '/projects/' + p.id) +
    (reviewable ? link('Đến phần duyệt', `?submission=${reviewable.id}#review-form`, 'button') : can && t.status === 'in_progress' ? link('Nộp sản phẩm', '#submit-form', 'button') : ''), `<a class="crumb" href="/projects/${p.id}">← ${h(p.name)}</a>`, 'task-title') + projectTabs(p, '');
  html += panel('Đầu ra & phân công', `<p class="preserve">${h(t.description)}</p><div class="meta-strip">${badge(t.status)}<span>Phụ trách <b>${h(resp?.user.full_name || '—')}</b></span>${collab.length ? `<span>Cùng làm <b>${h(collab.map(x => x.user.full_name).join(', '))}</b></span>` : ''}<span>Hạn <b>${dt(t.due_at)}</b></span>${t.original_due_at !== t.due_at ? `<span>Hạn ban đầu ${dt(t.original_due_at)}</span>` : ''}<span>Khối lượng <b>${t.points}</b></span><span>Ưu tiên <b>${h({low: 'Thấp', medium: 'Vừa', high: 'Cao'}[t.priority] || t.priority)}</b></span></div>
    <div class="actions" style="margin-top:14px">${isLeader() && !['done', 'review'].includes(t.status) ? button('Sửa phân công', 'edit-task', 'secondary') : ''}${can && t.status === 'todo' ? button('Bắt đầu', 'start-task') : ''}${can && ['todo', 'in_progress'].includes(t.status) ? button('Xin gia hạn', 'extend-task', 'secondary') : ''}</div>`);
  if (subs.length) {
    html += `<nav class="actions" aria-label="Các lần nộp" style="margin-bottom:12px">${[...t.submissions].map(s => `<a class="attempt ${s.id === focus.id ? 'current' : ''}" href="?submission=${s.id}#submission-${s.id}" ${s.id === focus.id ? 'aria-current="true"' : ''}>Lần ${s.attempt_no}</a>`).join('')}</nav>`;
    html += submissionCard(focus, t, p);
    const others = subs.filter(s => s.id !== focus.id);
    if (others.length) html += `<button type="button" class="secondary" data-action="toggle-history" aria-expanded="false" aria-controls="history">Xem bản cũ</button><div id="history" hidden style="margin-top:14px">${others.map(s => submissionCard(s, t, p)).join('')}</div>`;
  }
  if (can && t.status === 'in_progress') html += submitForm(t, subs);
  if (t.latest_submission_id && t.participants.length > 1 && can) html += panel('Đóng góp công việc chung', `<p>Mặc định chia đều cho những người được ghi nhận trong lần nộp. Có tranh chấp thì gửi đề nghị kèm lý do.</p>${button('Đề nghị điều chỉnh đóng góp', 'new-complaint', 'secondary')}`);
  if (!isStaff()) {
    const es = (await api(`/projects/${p.id}/extensions`)).items.filter(x => x.task_id === t.id);
    window.extensionsData = es;
    html += es.map(x => panel('Đề nghị gia hạn', `<p>${h(x.reason)}</p><p>Hạn đề nghị: ${dt(x.requested_due_at)}</p>${badge(x.status)}${isLeader() && x.status === 'pending' ? button('Xử lý gia hạn', 'decide-extension:' + x.id) : ''}`)).join('');
  }
  const cases = (await api(`/workflow/projects/${p.id}/complaints`)).items.filter(c => c.task_id === t.id);
  window.casesData = cases;
  html += cases.map(caseCard).join('');
  html += panel('Diễn biến', t.timeline?.map(e => `<div class="history-row"><div>${h(e.title)}${e.content ? `<p class="small muted" style="margin:2px 0 0">${h(e.content)}</p>` : ''}</div><small class="muted">${dt(e.created_at)}</small></div>`).join('') || empty('Chưa có cập nhật'));
  return html;
}
function submissionCard(s, t, p) {
  const r = t.revisions.find(r => r.id === s.revision_id);
  const files = (r?.assets || []).map(a => link(a.original_filename || a.url, a.kind === 'link' ? a.url : a.download_url, 'file-chip', a.kind === 'link' ? 'target="_blank" rel="noopener noreferrer"' : '')).join('');
  const assignmentDue = new Date(p.assignment.due_at).getTime();
  const def = Math.min(nowMs() + 2 * 86400000, assignmentDue);
  return `<article class="panel submission-card ${s.id === taskFocus ? 'focus' : ''}" id="submission-${s.id}" aria-labelledby="sub-h-${s.id}">
    <div class="toolbar" style="margin-bottom:6px"><div><h2 id="sub-h-${s.id}" style="margin:0">Lần nộp ${s.attempt_no}</h2><small class="muted">${h(s.submitted_by_name)} · ${dt(s.received_at)}${s.participant_names.length > 1 ? ' · Ghi nhận: ' + h(s.participant_names.join(', ')) : ''}</small></div><div class="actions">${s.late ? badge('Quá hạn', 'bad') : badge('Đúng hạn', 'good')}${badge(s.status)}</div></div>
    <p class="preserve">${h(r?.description)}</p><div class="actions">${files || '<span class="muted">Không có tệp hiển thị.</span>'}</div>
    <p class="small muted">Hạn tại thời điểm nộp: ${dt(s.submitted_due_at)}</p>
    ${s.evidence.length ? `<h3 style="font-size:15px;margin:16px 0 8px">Minh chứng theo tiêu chí</h3>${table(['Tiêu chí', 'Tệp hoặc liên kết'], s.evidence.map(e => [h(e.criterion_title) + (e.criterion_active ? '' : ' ' + badge('Đã ẩn', 'neutral')), e.asset ? link(e.asset.original_filename || e.asset.url, e.asset.download_url, 'file-chip') : '—']))}` : ''}
    ${s.referral ? `<div class="referral"><strong>Chuyển cho ${h(s.referral.instructor_name)}</strong><br><small>${h(s.referral.referred_by_name)} · ${dt(s.referral.created_at)}</small><p class="preserve" style="margin:6px 0 0">${h(s.referral.reason)}</p></div>` : ''}
    ${s.review_reason ? `<div class="feedback ${s.status === 'returned' ? 'bad' : ''}"><strong>${s.status === 'returned' ? 'Yêu cầu sửa' : 'Nhận xét'}${s.reviewed_by_name ? ' · ' + h(s.reviewed_by_name) : ''}</strong>${s.reviewed_at ? ` <small class="muted">${dt(s.reviewed_at)}</small>` : ''}<p class="preserve" style="margin:4px 0 0">${h(s.review_reason)}</p></div>` : ''}
    ${s.can_review ? `<form id="review-form" data-sid="${s.id}" novalidate><label for="review-reason">Nhận xét (bắt buộc khi yêu cầu sửa)</label><textarea id="review-reason" name="reason" aria-describedby="review-error"></textarea><p class="error" id="review-error" role="alert"></p>
      <label>Hạn sửa nếu yêu cầu sửa<input type="datetime-local" name="repair_due_at" value="${toLocalInput(def)}" max="${toLocalInput(assignmentDue)}" aria-describedby="due-error"></label><p class="error" id="due-error" role="alert"></p>
      <div class="form-end"><button name="decision" value="return" class="danger">Yêu cầu sửa</button><button name="decision" value="accept">Duyệt hoàn thành</button></div></form>` : ''}
    ${s.can_refer ? `<div class="actions" style="margin-top:12px">${button('Chuyển giảng viên duyệt', 'refer:' + s.id, 'secondary')}</div>` : ''}
    ${!s.can_review && s.review_block_reason && !isStaff() ? `<p class="block-note">${h(s.review_block_reason)}</p>` : ''}</article>`;
}
function submitForm(t, subs) {
  const crit = criteriaData.filter(c => c.is_active);
  return panel('Nộp sản phẩm', `<form id="submit-form" novalidate>${area('description', 'Nội dung bàn giao')}
    <div class="dropzone" id="dropzone"><label>Kéo thả tệp vào đây hoặc chọn từ máy<input type="file" name="files" multiple></label><div id="file-names" class="small muted"></div></div>
    ${field('url', 'Hoặc liên kết sản phẩm (http/https)', 'url', '', false)}
    ${subs.length ? '<label class="check"><input type="checkbox" name="reuse">Dùng lại tệp của lần nộp gần nhất</label>' : ''}
    ${crit.length ? `<fieldset><legend>Gắn minh chứng với tiêu chí (tùy chọn)</legend>${crit.map(c => `<label>${h(c.title)}<select name="crit_${c.id}" data-criterion="${c.id}"><option value="">Không gắn</option></select></label>`).join('')}</fieldset>` : ''}
    <p class="error" id="submit-error" role="alert"></p><div class="form-end"><button type="submit">Gửi duyệt</button></div></form>`);
}
taskPage.bind = () => {
  const target = location.hash && document.getElementById(location.hash.slice(1));
  if (target) {
    const hist = $('#history');
    if (hist && hist.contains(target)) { hist.hidden = false; $('[data-action="toggle-history"]')?.setAttribute('aria-expanded', 'true'); }
    target.scrollIntoView({block: 'start'});
  }
  bindReview(); bindSubmit();
};
function bindReview() {
  const f = $('#review-form');
  if (!f) return;
  f.onsubmit = async e => {
    e.preventDefault();
    const fd = new FormData(f), act = e.submitter?.value, reason = String(fd.get('reason')).trim();
    $('#review-error').textContent = ''; $('#due-error').textContent = '';
    f.elements.reason.classList.remove('invalid'); f.elements.repair_due_at.classList.remove('invalid');
    if (act === 'return') {
      if (!reason) { $('#review-error').textContent = 'Bạn cần bổ sung nhận xét trước khi yêu cầu sửa.'; f.elements.reason.classList.add('invalid'); f.elements.reason.focus(); return; }
      const due = new Date(fd.get('repair_due_at')).getTime();
      if (!due || due <= nowMs() || due > new Date(projectData.assignment.due_at).getTime()) { $('#due-error').textContent = 'Hạn sửa phải sau thời điểm hiện tại và trong hạn đề bài.'; f.elements.repair_due_at.classList.add('invalid'); f.elements.repair_due_at.focus(); return; }
    }
    await busy(e.submitter, async () => {
      try {
        await api(`/submissions/${f.dataset.sid}/review`, {version: taskData.version, action: act, reason, repair_due_at: act === 'return' ? iso(fd.get('repair_due_at')) : null});
        await render(); notify(act === 'accept' ? 'Đã duyệt hoàn thành' : 'Đã gửi yêu cầu sửa');
      } catch (err) {
        $('#review-error').textContent = friendly(err);
        if (err.code === 'VERSION_CONFLICT') { await render(); notify(friendly(err), true); }
      }
    });
  };
}
function bindSubmit() {
  const form = $('#submit-form');
  if (!form) return;
  let files = [], uploaded = [];
  const input = form.elements.files, zone = $('#dropzone');
  const last = taskData.revisions.at(-1);
  const refreshCriteria = () => {
    const opts = [['', 'Không gắn'], ...files.map((f, i) => ['file:' + i, 'Tệp mới: ' + f.name])];
    if (form.elements.url.value.trim()) opts.push(['url', 'Liên kết: ' + form.elements.url.value.trim()]);
    if (form.elements.reuse?.checked) (last?.assets || []).forEach(a => opts.push(['asset:' + a.id, 'Tệp cũ: ' + (a.original_filename || a.url)]));
    $$('[data-criterion]').forEach(sel => { const v = sel.value; sel.innerHTML = opts.map(([k, t]) => `<option value="${h(k)}">${h(t)}</option>`).join(''); if (opts.some(([k]) => k === v)) sel.value = v; });
  };
  const show = () => { $('#file-names').textContent = files.map(f => f.name).join(' · '); refreshCriteria(); };
  input.onchange = () => { files = [...input.files]; uploaded = []; show(); };
  zone.ondragover = e => { e.preventDefault(); zone.classList.add('over'); };
  zone.ondragleave = () => zone.classList.remove('over');
  zone.ondrop = e => { e.preventDefault(); zone.classList.remove('over'); files = [...e.dataTransfer.files]; uploaded = []; show(); };
  form.elements.url.oninput = refreshCriteria;
  if (form.elements.reuse) form.elements.reuse.onchange = refreshCriteria;
  form.onsubmit = async e => {
    e.preventDefault();
    const err = $('#submit-error'); err.textContent = '';
    const fd = new FormData(form);
    if (!String(fd.get('description')).trim()) { err.textContent = 'Cần nhập nội dung bàn giao.'; form.elements.description.focus(); return; }
    await busy(e.submitter, async () => {
      try {
        for (let i = uploaded.length; i < files.length; i++) { const data = new FormData(); data.append('file', files[i]); uploaded.push((await api(`/tasks/${taskData.id}/assets`, data)).id); }
        const ids = [...uploaded];
        let urlId = null;
        if (fd.get('url')) { urlId = (await api(`/tasks/${taskData.id}/assets`, {url: fd.get('url')})).id; ids.push(urlId); }
        if (fd.has('reuse')) ids.push(...(last?.assets || []).map(a => a.id));
        if (!ids.length) throw Error('Cần chọn tệp hoặc liên kết sản phẩm');
        const evidence_links = $$('[data-criterion]').map(sel => {
          const v = sel.value; if (!v) return null;
          const asset = v.startsWith('file:') ? uploaded[Number(v.slice(5))] : v === 'url' ? urlId : Number(v.slice(6));
          return asset ? {criterion_id: Number(sel.dataset.criterion), asset_id: asset} : null;
        }).filter(Boolean);
        await api(`/tasks/${taskData.id}/submissions`, {version: taskData.version, description: fd.get('description'), asset_ids: [...new Set(ids)], evidence_links});
        history.replaceState(null, '', location.pathname);
        await render(); notify('Đã gửi duyệt');
      } catch (x) { err.textContent = friendly(x); }
    });
  };
}

// ------------------------------------------------------------------ Timeline
// Lịch của tôi: task được giao (theo hạn) + mục lịch mình thấy được; chỉ xem.
// Lịch tôi tạo: mục lịch của chính mình; kéo thả đổi ngày, sửa loại và nội dung trực tiếp.
let tlData = null, tlView = 'mine';
const ymd = d => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
const parseDay = v => { const [y, m, d] = v.slice(0, 10).split('-').map(Number); return new Date(y, m - 1, d); };
const addDays = (v, n) => { const d = parseDay(v); d.setDate(d.getDate() + n); return ymd(d); };
const dayDiff = (a, b) => Math.round((parseDay(b) - parseDay(a)) / 86400000);
const WEEKDAY = ['CN', 'T2', 'T3', 'T4', 'T5', 'T6', 'T7'];
async function timelinePage() {
  const q = new URLSearchParams(location.search);
  tlView = q.get('view') === 'created' ? 'created' : 'mine';
  tlData = await api(`/workflow/schedule?view=${tlView}${q.get('from') ? '&from=' + encodeURIComponent(q.get('from')) : ''}`);
  const d = tlData, days = dayDiff(d.from, d.to) + 1;
  const range = `${dm(parseDay(d.from))} – ${dm(parseDay(d.to))}/${parseDay(d.to).getFullYear()}`;
  const cats = d.categories.filter(c => tlView === 'mine' ? !(d.is_staff && c.key === 'task') : c.key !== 'task');
  // Giảng viên: lọc theo học phần / nhóm (lọc tại trình duyệt, giữ trong URL).
  tlFilter = {course: Number(q.get('course')) || null, project: Number(q.get('project')) || null};
  const filters = d.is_staff && tlView === 'mine' ? `<div class="tl-filters"><select id="tl-course" aria-label="Lọc theo học phần"><option value="">Tất cả học phần</option>${d.courses.map(c => `<option value="${c.id}" ${tlFilter.course === c.id ? 'selected' : ''}>${h(c.title)}</option>`).join('')}</select><select id="tl-project" aria-label="Lọc theo nhóm"><option value="">Tất cả nhóm</option>${d.projects.filter(p => !tlFilter.course || p.course_id === tlFilter.course).map(p => `<option value="${p.id}" ${tlFilter.project === p.id ? 'selected' : ''}>${h(p.name)}</option>`).join('')}</select></div>` : '';
  return `<div class="toolbar tl-toolbar"><nav class="segmented" aria-label="Loại lịch"><a href="/timeline?view=mine" class="seg-link" ${tlView === 'mine' ? 'aria-current="page"' : ''}>Lịch của tôi</a><a href="/timeline?view=created" class="seg-link" ${tlView === 'created' ? 'aria-current="page"' : ''}>Lịch tôi tạo</a></nav>
    <div class="toolbar-right"><div class="tl-nav" role="group" aria-label="Chuyển khoảng ngày">${button('‹ Trước', 'tl-shift:-7', 'secondary')}${button('Hôm nay', 'tl-today', 'secondary')}${button('Sau ›', 'tl-shift:7', 'secondary')}</div><strong class="tl-range">${range}</strong>
    ${aiHistoryBar()}<button type="button" data-action="ai-schedule" class="secondary ai-btn">${AI_ICON}<span>AI sắp lịch</span></button>
    ${tlView === 'created' ? `<button type="button" data-action="tl-add" class="create-btn"><span aria-hidden="true">+</span> Thêm lịch</button>` : ''}</div></div>${filters}
    <ul class="tl-legend" aria-label="Chú giải loại lịch">${cats.map(c => `<li><i class="cat-${c.key}"></i>${h(c.label)}</li>`).join('')}</ul>
    <p class="small muted tl-hint">${tlView === 'mine' && d.is_staff ? 'Mốc nộp của các lớp, lịch các nhóm chia sẻ và lịch bạn tạo, chỉ xem. Sửa lịch của bạn ở tab Lịch tôi tạo.' : tlView === 'mine' ? 'Lịch tổng hợp việc được giao, mốc nộp đề bài và lịch được chia sẻ, chỉ xem. Bấm một mục để mở chi tiết; sửa lịch của bạn ở tab Lịch tôi tạo.' : 'Kéo thả để đổi ngày (giữ độ dài), bấm để sửa nội dung và loại. Bấm đúp vào một ngày để thêm lịch. Bàn phím: chọn mục rồi Alt + ←/→ để dời một ngày.'}</p>
    <div class="tl-scroll"><div class="tl-grid ${tlView === 'created' ? 'editable' : ''}" id="tl-grid" style="--days:${days}">${timelineCells(d, days)}</div></div>`;
}
let tlFilter = {course: null, project: null};
const tlVisible = x => (!tlFilter.course || x.course_id === tlFilter.course) && (!tlFilter.project || x.project_id === tlFilter.project || (x.kind === 'milestone' && !x.project_id && (!tlFilter.course || x.course_id === tlFilter.course) && tlData.projects.find(p => p.id === tlFilter.project)?.course_id === x.course_id));
function timelineCells(d, days) {
  // Each entry spans its days; lanes are packed greedily so one day's work stacks top-down in the same column.
  const entries = d.items.filter(tlVisible).map(x => {
    const point = x.kind === 'task' || x.kind === 'milestone';
    const start = point ? ymd(new Date(x.due_at)) : x.start, end = point ? start : x.end;
    return {x, start, end, s: Math.max(0, dayDiff(d.from, start)), e: Math.min(days - 1, dayDiff(d.from, end))};
  }).filter(r => r.e >= 0 && r.s <= days - 1).sort((a, b) => a.s - b.s || (b.e - b.s) - (a.e - a.s) || (a.x.kind === 'task') - (b.x.kind === 'task'));
  const lanes = [];
  for (const r of entries) { let k = lanes.findIndex(end => end < r.s); if (k < 0) { k = lanes.length; lanes.push(-1); } lanes[k] = r.e; r.lane = k; }
  const rows = Math.max(lanes.length, 3) + 1;
  let html = '';
  for (let i = 0; i < days; i++) {
    const v = addDays(d.from, i), dt0 = parseDay(v), today = v === d.today;
    html += `<div class="tl-day ${today ? 'today' : ''} ${[0, 6].includes(dt0.getDay()) ? 'weekend' : ''}" style="grid-column:${i + 1};grid-row:1"><span>${WEEKDAY[dt0.getDay()]}</span><b>${dm(dt0)}</b>${today ? '<em>Hôm nay</em>' : ''}</div>`;
    html += `<div class="tl-col ${today ? 'today' : ''}" data-day="${v}" style="grid-column:${i + 1};grid-row:2 / span ${rows}"></div>`;
  }
  for (const r of entries) {
    const x = r.x, pos = `grid-column:${r.s + 1} / ${r.e + 2};grid-row:${r.lane + 2}`;
    const cut = (r.s > 0 || dayDiff(d.from, r.start) >= 0 ? '' : ' cut-start') + (dayDiff(d.from, r.end) > days - 1 ? ' cut-end' : '');
    if (x.kind === 'milestone') {
      html += `<a class="tl-item cat-deadline milestone" href="${h(x.link)}" style="${pos}" title="${h(x.title)}"><b>${h(x.title)}</b><small>${h(hm(x.due_at))} · ${h(x.project_name)}</small></a>`;
    } else if (x.kind === 'task') {
      html += `<a class="tl-item cat-task${x.overdue ? ' late' : ''}${x.status === 'done' ? ' done' : ''}" href="${h(x.link)}" style="${pos}" title="${h(x.title)}"><b>${h(x.title)}</b><small>${h(hm(x.due_at))} · ${h(x.project_name)}${x.overdue ? ' · Quá hạn' : x.status === 'done' ? ' · Hoàn thành' : ''}</small></a>`;
    } else {
      const meta = [x.project_name, tlView === 'mine' && x.owner_name !== me.full_name ? x.owner_name : ''].filter(Boolean).join(' · ');
      html += `<button type="button" class="tl-item cat-${h(x.category)}${cut}" style="${pos}" data-action="${x.editable ? 'tl-edit' : 'tl-view'}:${x.id}" data-item="${x.id}" ${x.editable ? 'draggable="true" aria-keyshortcuts="Alt+ArrowLeft Alt+ArrowRight"' : ''} title="${h(x.title)}"><b>${h(x.title)}</b>${meta ? `<small>${h(meta)}</small>` : ''}</button>`;
    }
  }
  if (!entries.length) html += `<div class="tl-empty" style="grid-column:1 / -1;grid-row:2">${tlView === 'created' ? 'Chưa có mục lịch nào trong khoảng này. Bấm “Thêm lịch” hoặc bấm đúp vào một ngày.' : 'Không có việc nào trong khoảng này.'}</div>`;
  return html;
}
timelinePage.bind = () => {
  const setFilter = (k, v) => {
    const u = new URL(location.href);
    v ? u.searchParams.set(k, v) : u.searchParams.delete(k);
    if (k === 'course') u.searchParams.delete('project');
    history.replaceState(null, '', u); attempt(() => render());
  };
  if ($('#tl-course')) $('#tl-course').onchange = e => setFilter('course', e.target.value);
  if ($('#tl-project')) $('#tl-project').onchange = e => setFilter('project', e.target.value);
  const grid = $('#tl-grid');
  if (!grid || tlView !== 'created') return;
  const days = dayDiff(tlData.from, tlData.to) + 1;
  const colAt = x => { const r = grid.getBoundingClientRect(); return Math.max(0, Math.min(days - 1, Math.floor((x - r.left) / (r.width / days)))); };
  let drag = null;
  const move = async (item, delta) => {
    if (!delta) return;
    await attempt(async () => { await api('/workflow/schedule/' + item.id, {version: item.version, start: addDays(item.start, delta), end: addDays(item.end, delta)}, 'PATCH'); await render(); notify('Đã dời lịch'); });
  };
  grid.querySelectorAll('[data-item]').forEach(el => {
    el.ondragstart = e => {
      const item = tlData.items.find(x => x.kind === 'item' && x.id === Number(el.dataset.item));
      drag = {item, grab: colAt(e.clientX) - Math.max(0, dayDiff(tlData.from, item.start))};
      e.dataTransfer.effectAllowed = 'move'; e.dataTransfer.setData('text/plain', String(item.id)); el.classList.add('dragging');
    };
    el.ondragend = () => { el.classList.remove('dragging'); grid.querySelectorAll('.tl-col.over').forEach(c => c.classList.remove('over')); };
    el.onkeydown = e => {
      if (!e.altKey || !['ArrowLeft', 'ArrowRight'].includes(e.key)) return;
      e.preventDefault(); move(tlData.items.find(x => x.kind === 'item' && x.id === Number(el.dataset.item)), e.key === 'ArrowLeft' ? -1 : 1);
    };
  });
  grid.ondragover = e => {
    if (!drag) return; e.preventDefault();
    const c = colAt(e.clientX); grid.querySelectorAll('.tl-col').forEach((el, i) => el.classList.toggle('over', i === c));
  };
  grid.ondrop = e => {
    if (!drag) return; e.preventDefault();
    const target = colAt(e.clientX) - drag.grab, from = dayDiff(tlData.from, drag.item.start);
    const item = drag.item; drag = null; move(item, target - from);
  };
  grid.querySelectorAll('.tl-col').forEach(c => c.ondblclick = () => scheduleForm(null, c.dataset.day));
};
function timelineShift(n) {
  const u = new URL(location.href);
  n ? u.searchParams.set('from', addDays(tlData.from, n)) : u.searchParams.delete('from');
  history.pushState(null, '', u); return render();
}
function scheduleForm(x = null, dayValue = '') {
  const cats = tlData.categories.filter(c => c.key !== 'task');
  const start = x?.start || dayValue || tlData.today;
  const body = field('title', 'Tiêu đề', 'text', x?.title || '', true, 'maxlength="200"') +
    `<div class="grid2">${select('category', 'Loại', cats.map(c => [c.key, c.label]), x?.category || 'study')}${select('project_id', 'Chia sẻ với dự án (chỉ xem)', [['', 'Không chia sẻ'], ...tlData.projects.map(p => [p.id, p.name])], x?.project_id || '')}</div>` +
    `<div class="grid2">${field('start', 'Từ ngày', 'date', start)}${field('end', 'Đến ngày', 'date', x?.end || start)}</div>` + area('note', 'Ghi chú', x?.note || '', false) +
    (x ? `<div class="actions">${button('Xóa mục lịch', 'tl-delete:' + x.id, 'danger')}</div>` : '');
  return modal(x ? 'Sửa lịch' : 'Thêm lịch', body, async f => {
    const b = {title: f.get('title'), category: f.get('category'), start: f.get('start'), end: f.get('end') || f.get('start'), note: f.get('note') || '', project_id: f.get('project_id') ? Number(f.get('project_id')) : null};
    if (b.end < b.start) throw Error('Ngày kết thúc phải từ ngày bắt đầu trở đi');
    if (x) await api('/workflow/schedule/' + x.id, {...b, version: x.version}, 'PATCH'); else await api('/workflow/schedule', b);
    return x ? 'Đã cập nhật lịch' : 'Đã thêm lịch';
  }, x ? 'Lưu' : 'Thêm');
}
function scheduleView(x) {
  const cat = tlData.categories.find(c => c.key === x.category)?.label || x.category;
  const span = x.start === x.end ? parseDay(x.start).toLocaleDateString(VN) : `${parseDay(x.start).toLocaleDateString(VN)} – ${parseDay(x.end).toLocaleDateString(VN)}`;
  modal(x.title, `<p><span class="tl-dot cat-${h(x.category)}"></span> ${h(cat)} · ${h(span)}</p>${x.project_name ? `<p class="muted">Dự án: ${h(x.project_name)}</p>` : ''}<p class="muted">Người tạo: ${h(x.owner_name)}</p>${x.note ? `<p class="preserve">${h(x.note)}</p>` : ''}${x.owner_name === me.full_name ? `<p class="small muted">Sửa mục này ở tab <a href="/timeline?view=created">Lịch tôi tạo</a>.</p>` : ''}`, null);
}


// ------------------------------------------------------------------ AI hỗ trợ tạo timeline
// Bước 1: nhập mong muốn → máy chủ trả đề xuất (Gemini nếu có key, không thì bộ sinh theo quy tắc).
// Bước 2: người dùng sửa / bỏ chọn từng dòng → tạo task hoặc mục lịch qua API thông thường.
const tzOffset = () => new Date().getTimezoneOffset();
const sourceNote = r => `<p class="small ai-source">${r.source === 'gemini' ? `${AI_ICON} Đề xuất bởi Gemini` : `${AI_ICON} Đề xuất theo quy tắc (chia giai đoạn theo hạn và khối lượng)`}${r.notice ? ' · ' + h(r.notice) : ''}</p>`;
function aiDialog(title, intro, placeholder, generate, renderRows, commit) {
  const d = modal(title, `<p class="small muted">${intro}</p><label>Mong muốn / ghi chú (tùy chọn)<textarea name="note" maxlength="1000" placeholder="${h(placeholder)}"></textarea></label>
    <div class="form-end"><button type="button" data-ai="generate">${AI_ICON}<span>Tạo đề xuất</span></button></div><div id="ai-result" aria-live="polite"></div>`, null, '', {wide: true});
  const out = d.querySelector('#ai-result'), err = d.querySelector('.error'), gen = d.querySelector('[data-ai="generate"]');
  let result = null;
  gen.onclick = () => busy(gen, async () => {
    err.textContent = ''; out.innerHTML = '<p class="muted">Đang tạo đề xuất…</p>';
    try {
      result = await generate(d.querySelector('[name=note]').value.trim());
      out.innerHTML = sourceNote(result) + (result.items.length ? renderRows(result) + `<div class="form-end"><button type="button" data-ai="commit">Lưu các dòng đã chọn</button></div>` : empty(result.notice || 'Không có đề xuất nào.'));
      gen.lastElementChild.textContent = 'Tạo lại đề xuất';
      const save = out.querySelector('[data-ai="commit"]');
      if (save) save.onclick = () => busy(save, async () => {
        err.textContent = '';
        const rows = [...out.querySelectorAll('[data-ai-row]')].filter(r => r.querySelector('[data-f=use]').checked);
        if (!rows.length) { err.textContent = 'Chọn ít nhất một dòng.'; return; }
        let ok = 0; const fails = [];
        for (const r of rows) {
          try { await commit(r, result); ok++; r.querySelector('[data-f=use]').checked = false; r.classList.add('saved'); }
          catch (x) { fails.push(`${r.querySelector('[data-f=title]').value}: ${friendly(x)}`); r.classList.add('failed'); }
        }
        if (fails.length) { err.textContent = `Đã lưu ${ok}, lỗi ${fails.length}: ` + fails.join('; '); await render(); return; }
        d.close(); await render(); notify(`Đã lưu ${ok} mục từ đề xuất`);
      });
    } catch (x) { out.innerHTML = ''; err.textContent = friendly(x); }
  });
  return d;
}
const dateOnly = v => ymd(new Date(v));
function aiPlanModal() {
  const p = projectData;
  const people = p.members.filter(m => m.status === 'active');
  const last = dateOnly(p.assignment.due_at);
  return aiDialog('AI lập kế hoạch nhóm', `AI đọc đề bài “${h(p.assignment.title)}”, hạn nộp ${dt(p.assignment.due_at)} và ${people.length} thành viên để đề xuất các giai đoạn, công việc, hạn và người phụ trách. Bạn sửa rồi mới tạo công việc.`,
    'Ví dụ: ưu tiên làm giao diện trước, Bảo mạnh backend, tuần sau nhóm bận thi giữa kỳ…',
    note => api(`/workflow/projects/${p.id}/ai-plan`, {note, tz_offset: tzOffset()}),
    r => `<div class="table-wrap ai-table"><table><thead><tr><th scope="col"><span class="sr-only">Chọn</span></th><th scope="col">Giai đoạn</th><th scope="col">Công việc · đầu ra</th><th scope="col">Phụ trách</th><th scope="col">Hạn</th><th scope="col">KL</th><th scope="col">Ưu tiên</th></tr></thead><tbody>${r.items.map((x, i) => `<tr data-ai-row="${i}">
      <td><input type="checkbox" data-f="use" checked aria-label="Chọn dòng ${i + 1}"></td><td><small>${h(x.phase)}</small></td>
      <td><input data-f="title" value="${h(x.title)}" maxlength="200" aria-label="Tên công việc"><textarea data-f="description" aria-label="Đầu ra cần bàn giao">${h(x.description)}</textarea></td>
      <td><select data-f="responsible" aria-label="Người phụ trách">${people.map(m => `<option value="${m.user_id}" ${m.user_id === x.responsible_id ? 'selected' : ''}>${h(m.user.full_name)}</option>`).join('')}</select></td>
      <td><input type="date" data-f="due" value="${dateOnly(x.due_at)}" max="${last}" aria-label="Hạn"></td>
      <td><select data-f="points" aria-label="Khối lượng">${[1, 2, 3, 5].map(v => `<option ${v === x.points ? 'selected' : ''}>${v}</option>`).join('')}</select></td>
      <td><select data-f="priority" aria-label="Ưu tiên">${[['low', 'Thấp'], ['medium', 'Vừa'], ['high', 'Cao']].map(([k, t]) => `<option value="${k}" ${k === x.priority ? 'selected' : ''}>${t}</option>`).join('')}</select></td></tr>`).join('')}</tbody></table></div>`,
    async row => {
      const v = k => row.querySelector(`[data-f=${k}]`).value;
      const day = v('due');
      if (!v('title').trim() || !v('description').trim() || !day) throw Error('Cần tên, đầu ra và hạn');
      let due = new Date(day + 'T23:00');
      const max = new Date(p.assignment.due_at);
      if (due > max) due = max;
      await api(`/projects/${p.id}/tasks`, {title: v('title').trim(), description: v('description').trim(), due_at: due.toISOString(), points: Number(v('points')), priority: v('priority'),
        participants: [{user_id: Number(v('responsible')), role: 'responsible'}]});
    });
}
// AI sắp lịch: bấm nút → Xác nhận là lịch được thêm ngay vào khoảng ngày đang xem.
// Hoàn tác xóa đúng các mục vừa thêm; mũi tên → thêm lại (làm lại) nếu muốn quay về lịch AI.
const AI_HIST = 'ts-ai-history';
const aiHistory = () => { try { return JSON.parse(sessionStorage.getItem(AI_HIST)) || {undo: [], redo: []}; } catch { return {undo: [], redo: []}; } };
const saveAiHistory = x => { try { sessionStorage.setItem(AI_HIST, JSON.stringify(x)); } catch { /* private mode */ } };
async function createItems(payloads) {
  const ids = [];
  try { for (const b of payloads) ids.push((await api('/workflow/schedule', b)).id); }
  catch (e) { if (ids.length) { const x = aiHistory(); x.undo.push({ids, payloads: payloads.slice(0, ids.length)}); saveAiHistory(x); } throw e; }  // partial batch stays undoable
  return ids;
}
async function deleteItems(ids) {
  for (const id of ids) {
    try { await api('/workflow/schedule/' + id, {}, 'DELETE'); } catch (e) { if (e.status !== 404) throw e; }
  }
}
function aiHistoryBar() {
  const x = aiHistory();
  if (!x.undo.length && !x.redo.length) return '';
  const last = x.undo.at(-1), next = x.redo.at(-1);
  return `<div class="ai-history" role="group" aria-label="Lịch do AI sắp">${last ? `<button type="button" class="secondary" data-action="ai-undo" title="Xóa ${last.ids.length} mục AI vừa thêm">↶ Hoàn tác</button>` : ''}${next ? `<button type="button" class="secondary icon-only" data-action="ai-redo" aria-label="Làm lại: thêm lại ${next.payloads.length} mục AI" title="Làm lại: thêm lại ${next.payloads.length} mục AI">→</button>` : ''}</div>`;
}
async function aiUndo(btn) {
  const x = aiHistory(), batch = x.undo.pop();
  if (!batch) return;
  await busy(btn, () => deleteItems(batch.ids));
  x.redo.push({payloads: batch.payloads}); saveAiHistory(x);
  await render(); notify(`Đã hoàn tác ${batch.ids.length} mục lịch AI. Bấm → để thêm lại.`);
}
async function aiRedo(btn) {
  const x = aiHistory(), batch = x.redo.pop();
  if (!batch) return;
  const ids = await busy(btn, () => createItems(batch.payloads));
  x.undo.push({ids, payloads: batch.payloads}); saveAiHistory(x);
  await render(); notify(`Đã thêm lại ${ids.length} mục lịch AI`);
}
function aiScheduleModal() {
  const range = `${dm(parseDay(tlData.from))} – ${dm(parseDay(tlData.to))}`;
  return modal('AI sắp lịch', `<p class="small muted">AI xếp lịch cá nhân cho khoảng <b>${h(range)}</b> đang xem (từ hôm nay trở đi): công việc được giao, bài chờ bạn duyệt, phiếu đánh giá chéo, hạn nộp đề bài và buổi rà soát tiến độ hằng tuần, tránh trùng lịch đã có. Bấm Xác nhận là lịch được thêm ngay; không ưng thì bấm Hoàn tác.</p>
    <label>Mong muốn / ghi chú (tùy chọn)<textarea name="note" maxlength="1000" placeholder="Ví dụ: tối thứ 3 và thứ 5 đi làm thêm, muốn ôn thi Cơ sở dữ liệu vào cuối tuần…"></textarea></label>`,
    async f => {
      const r = await api('/workflow/ai-schedule', {note: String(f.get('note') || '').trim(), tz_offset: tzOffset(), from: tlData.from, to: tlData.to});
      if (!r.items.length) throw Error(r.notice || 'Không có việc mới cần xếp trong khoảng này.');
      const payloads = r.items.map(x => ({title: x.title, category: x.category, start: x.start, end: x.end, note: x.note || '', project_id: x.project_id || null}));
      const ids = await createItems(payloads);
      const x = aiHistory(); x.undo.push({ids, payloads}); x.redo = []; saveAiHistory(x);
      return `Đã thêm ${ids.length} mục lịch (${r.source === 'gemini' ? 'Gemini sắp' : 'sắp theo quy tắc'})${r.notice ? ' · ' + r.notice : ''}. Không ưng thì bấm Hoàn tác.`;
    }, 'Xác nhận');
}

// ------------------------------------------------------------------ Bài nộp
function submissionTable(rows, reviewTab = false) {
  return `<div class="table-wrap"><table><thead><tr><th scope="col">Công việc</th><th scope="col">Người nộp</th><th scope="col">Trạng thái</th><th scope="col"><span class="sr-only">Hành động</span></th></tr></thead><tbody>${rows.map(r => `<tr class="sub-row" data-search="${h((r.task_title + ' ' + r.project_name + ' ' + r.submitted_by_name).toLowerCase())}">
    <td><div class="sub-title">${h(r.task_title)} <a class="attempt" href="${h(r.link)}" aria-label="Mở lần nộp ${r.attempt_no} của ${h(r.task_title)}">Lần ${r.attempt_no}</a>${r.referred ? badge('Đã chuyển GV', 'warn') : ''}</div><small class="muted">${h(r.project_name)}${r.team_name ? ' · ' + h(r.team_name) : ''}</small></td>
    <td><strong>${h(r.submitted_by_name)}</strong><br><small class="muted">${dt(r.received_at)}</small></td>
    <td>${badge(r.status)}${!r.is_latest ? ' ' + badge('Bản cũ', 'neutral') : ''}</td>
    <td>${r.can_review ? link('Xem để duyệt', r.link, 'button') : link('Xem bản nộp', r.link, 'link-btn')}</td></tr>`).join('')}</tbody></table></div>`;
}
let queueData = null;
async function submissionsPage() {
  queueData = await api('/workflow/submissions');
  const teacher = isStaff();
  const want = new URLSearchParams(location.search).get('tab');
  const tab = want === 'review' || (teacher && want !== 'mine') ? 'review' : want === 'repair' && !teacher ? 'repair' : 'mine';
  queueData.repair = queueData.mine.filter(r => r.status === 'returned' && r.is_latest);
  const mineLabel = teacher ? 'Đã xử lý' : 'Bài của tôi', reviewLabel = teacher ? 'Được chuyển cho tôi' : 'Cần tôi duyệt';
  return `<div class="toolbar"><div class="segmented" role="tablist" aria-label="Danh sách bài nộp"><button type="button" role="tab" data-subtab="mine" aria-selected="${tab === 'mine'}">${mineLabel}<span class="count">${queueData.counts.mine}</span></button>${teacher ? '' : `<button type="button" role="tab" data-subtab="repair" aria-selected="${tab === 'repair'}">Cần sửa<span class="count" id="repair-count">${queueData.repair.length}</span></button>`}<button type="button" role="tab" data-subtab="review" aria-selected="${tab === 'review'}">${reviewLabel}<span class="count" id="review-count">${queueData.counts.to_review}</span></button></div><input type="search" class="search" id="sub-q" placeholder="Tìm bài nộp…" aria-label="Tìm bài nộp"></div>
    <section class="panel" id="sub-list"></section>`;
}
submissionsPage.bind = () => {
  let tab = $('[data-subtab][aria-selected="true"]').dataset.subtab, q = '';
  const draw = () => {
    const rows = tab === 'review' ? queueData.to_review : tab === 'repair' ? queueData.repair : queueData.mine;
    $('#sub-list').innerHTML = rows.length ? submissionTable(rows, tab === 'review') : empty(tab === 'review' ? 'Không có bài nào chờ bạn duyệt.' : tab === 'repair' ? 'Không có bài nào cần sửa.' : 'Chưa có bài nộp.');
    $$('#sub-list [data-search]').forEach(r => r.hidden = !r.dataset.search.includes(q));
    const u = new URL(location.href); u.searchParams.set('tab', tab); history.replaceState(null, '', u);
  };
  $$('[data-subtab]').forEach(b => b.onclick = () => { tab = b.dataset.subtab; $$('[data-subtab]').forEach(x => x.setAttribute('aria-selected', String(x === b))); draw(); });
  $('#sub-q').oninput = e => { q = e.target.value.trim().toLowerCase(); draw(); };
  draw();
};

// ------------------------------------------------------------------ Học phần
function courseRow(c) {
  return `<a class="course-row" href="/courses/${c.id}" data-search="${h((c.title + ' ' + c.code).toLowerCase())}"><span class="course-icon">${BOOK}</span><span><h3>${h(c.title)}</h3><small>${h(c.code)} · ${h(c.term)}</small></span><span class="cr-assign">${c.assignment ? h(c.assignment.title) : '<span class="muted">Chưa có đề bài</span>'}</span>${badge(c.status === 'archived' ? 'archived' : 'active')}<span aria-hidden="true">→</span></a>`;
}
async function coursesPage() {
  const cs = homeData.courses;
  return `<div class="toolbar"><strong>${cs.length} học phần</strong><div class="toolbar-right"><input type="search" class="search" data-search-input placeholder="Tìm tên hoặc mã lớp…" aria-label="Tìm học phần">${isTeacher() ? button('Tạo lớp', 'create-course') : ''}</div></div><section class="panel" style="padding:8px 16px">${cs.map(courseRow).join('') || empty('Chưa có học phần.')}</section>`;
}
let courseTab = 'brief', currentCourse = null, enrollmentData = [];
async function coursePage(id) {
  const c = homeData.courses.find(c => c.id === id);
  if (!c) throw Error('Không tìm thấy học phần hoặc bạn không thuộc học phần này');
  currentCourse = c;
  const staff = ['instructor', 'coordinator'].includes(c.my_role), teacher = c.my_role === 'instructor';
  // Người phụ trách: mở lớp là thấy ngay các nhóm dự án; đề bài và sinh viên ở tab bên cạnh.
  courseTab = new URLSearchParams(location.search).get('tab') || (staff ? 'groups' : 'brief');
  if (!staff || !['brief', 'students', 'groups'].includes(courseTab)) courseTab = staff ? 'groups' : 'brief';
  const a = c.assignment;
  let html = pageHead(c.title, c.code + ' · ' + c.term + (a ? ' · ' + a.title : ''), link('Tất cả học phần', '/courses'));
  if (staff) html += `<nav class="tabs" aria-label="Mục học phần">${[['groups', `Nhóm dự án · ${c.groups.length}`], ['brief', 'Đề bài & tiêu chí'], ['students', 'Sinh viên']].map(([k, t]) => `<a href="/courses/${id}?tab=${k}" ${courseTab === k ? 'aria-current="page"' : ''}>${t}</a>`).join('')}</nav>`;
  if (courseTab === 'students') return html + await studentsTab(c);
  if (courseTab === 'groups') return html + groupsTab(c);
  if (!a) return html + panel('Đề bài nhóm', empty('Chưa có đề bài được công bố.') + (teacher ? `<div class="actions" style="margin-top:12px">${button('Tạo đề bài', 'create-assignment:' + id)}</div>` : ''));
  const files = (await api('/assignments/' + a.id + '/files')).items;
  const cr = await api(`/workflow/assignments/${a.id}/evidence-criteria`);
  criteriaData = cr.items;
  html += panel(a.title, `<p class="preserve">${h(a.brief)}</p><p>Hạn nộp: ${dt(a.due_at)} · Nhóm ${a.group_min}–${a.group_max} người · ${a.group_mode === 'self' ? 'Sinh viên tự lập nhóm' : 'Xếp nhóm'}</p><div class="actions">${files.map(f => link(f.name || f.original_filename, f.download_url)).join('')}${teacher ? button('Tải đề bài / tiêu chí', 'assignment-files:' + a.id, 'secondary') + button('Sửa đề bài', 'edit-assignment', 'secondary') : ''}</div>`);
  html += `<section class="panel"><div class="toolbar"><h2 style="margin:0">Tiêu chí minh chứng</h2>${cr.can_manage ? button('Thêm tiêu chí', 'add-criterion:' + a.id) : ''}</div>${criteriaData.length ? table(['Tiêu chí', 'Trạng thái', ...(cr.can_manage ? ['Thao tác'] : [])], criteriaData.map(x => [`<strong>${h(x.title)}</strong>${x.description ? `<br><small class="muted">${h(x.description)}</small>` : ''}`, x.is_active ? badge('Đang dùng', 'good') : badge('Đã ẩn', 'neutral'), ...(cr.can_manage ? [button(x.is_active ? 'Ẩn tiêu chí' : 'Bật lại', 'toggle-criterion:' + x.id, 'secondary')] : [])])) : empty('Chưa có tiêu chí minh chứng.')}</section>`;
  if (!staff) {
    html += panel('Nhóm của bạn', c.groups.length ? c.groups.map(g => `<div class="history-row"><div><strong>${h(g.name)}</strong> ${badge(g.status)}</div>${link('Vào nhóm', '/projects/' + g.id, 'button')}</div>`).join('') : a.group_mode === 'self' ? `<p>Tạo nhóm nháp, mời thành viên; khi đủ người trưởng nhóm gửi giảng viên duyệt.</p>${button('Tạo nhóm', 'create-group:' + a.id)}` : empty('Người phụ trách học phần sẽ xếp nhóm cho bạn.'));
  }
  return html;
}
async function studentsTab(c) {
  enrollmentData = await all('/courses/' + c.id + '/enrollments');
  const st = enrollmentData.filter(e => e.role === 'student');
  return `<section class="panel"><div class="toolbar"><h2 style="margin:0">Sinh viên trong lớp · ${st.length}</h2><div class="actions">${button('Nhập CSV / Excel', 'import:' + c.id, 'secondary')}${button('Thêm sinh viên', 'enroll:' + c.id)}</div></div>
    ${st.length ? table(['Họ tên', 'Mã sinh viên', 'Trạng thái'], st.map(e => [h(e.user.full_name), h(e.student_code || '—'), badge(e.status === 'active' ? 'active' : e.status)])) : empty('Chưa có sinh viên.')}</section>`;
}
// Các nhóm dự án của lớp: thẻ theo dõi tiến độ; nhóm cần chú ý (chờ duyệt, hỗ trợ, quá hạn) lên đầu.
function groupCard(g) {
  const pct = g.total ? Math.round(g.done / g.total * 100) : 0;
  const shown = pct === 100 && g.done !== g.total ? 99 : pct;
  const flags = [g.status === 'pending' ? badge('Chờ duyệt nhóm', 'warn') : g.status === 'draft' ? badge('draft') : '',
    g.help ? badge(g.help + ' yêu cầu hỗ trợ', 'warn') : '', g.late ? badge(g.late + ' việc quá hạn', 'bad') : '',
    g.pending_review ? badge(g.pending_review + ' việc chờ duyệt', 'neutral') : ''].join('');
  const names = g.member_names || [];
  return `<a class="group-card tier-${progressTier(g)}" href="/projects/${g.id}" data-search="${h((g.name + ' ' + (g.team_name || '') + ' ' + names.join(' ')).toLowerCase())}">
    <div class="gc-top">${robot(true)}<div><h3>${h(g.name)}</h3><div class="team">${h(g.team_name || '—')}</div></div>${g.status === 'active' ? '' : badge(g.status)}</div>
    <p class="gc-people"><span class="gc-ic">${NAV_ICONS.users}</span><span><b>${h(g.leader?.full_name || 'Chưa có trưởng nhóm')}</b>${names.length > 1 ? ' · ' + h(names.slice(1).join(', ')) : ''}</span></p>
    <div class="pc-progress"><span>${g.done}/${g.total} công việc hoàn thành · ${g.members} thành viên</span><b>${shown}%</b></div>
    <div class="progress" role="img" aria-label="Tiến độ ${shown}%"><span style="width:${shown}%"></span></div>
    <div class="gc-flags">${flags || '<span class="muted small">Không có vấn đề cần chú ý</span>'}</div></a>`;
}
function groupsTab(c) {
  const rank = g => (g.status === 'pending' ? 0 : g.help ? 1 : g.late ? 2 : 3);
  const gs = [...c.groups].sort((a, b) => rank(a) - rank(b) || a.id - b.id);
  const att = gs.filter(g => rank(g) < 3).length;
  return `<div class="toolbar"><strong>${gs.length} nhóm${att ? ` · ${att} nhóm cần chú ý` : ''}</strong><div class="toolbar-right"><input type="search" class="search" data-search-input placeholder="Tìm nhóm, đội hoặc thành viên…" aria-label="Tìm nhóm">${c.assignment && c.my_role === 'instructor' || c.assignment && c.my_role === 'coordinator' ? button('Xếp nhóm', 'teacher-group:' + c.assignment.id) : ''}</div></div>
    ${gs.length ? `<div class="group-grid">${gs.map(groupCard).join('')}</div>` : panel('', empty(c.assignment ? 'Chưa có nhóm nào trong lớp này.' : 'Lớp chưa có đề bài nhóm. Tạo đề bài ở tab Đề bài & tiêu chí.'))}`;
}
function importModal(cid) {
  const d = modal('Nhập danh sách sinh viên', `<p class="small muted">Tệp CSV UTF-8 hoặc Excel .xlsx có các cột <b>student_code, full_name, email</b>. Bước 1: xem trước. Bước 2: xác nhận khi tất cả dòng hợp lệ.</p>
    <label>Chọn tệp<input type="file" name="file" accept=".csv,.xlsx" id="import-file"></label><div id="import-status" role="status" class="small"></div><div id="import-preview"></div>
    <div class="form-end"><button type="button" class="secondary" id="import-again" hidden>Chọn tệp khác</button><button type="button" id="import-commit" disabled>Xác nhận nhập</button></div>`, null, '', {wide: true});
  let batch = null;
  const status = d.querySelector('#import-status'), preview = d.querySelector('#import-preview'), commit = d.querySelector('#import-commit'), again = d.querySelector('#import-again'), input = d.querySelector('#import-file'), err = d.querySelector('.error');
  input.onchange = async () => {
    const f = input.files[0]; if (!f) return;
    batch = null; commit.disabled = true; preview.innerHTML = ''; err.textContent = ''; status.textContent = 'Đang tải lên và kiểm tra…';
    const data = new FormData(); data.append('file', f);
    try {
      batch = await api(`/courses/${cid}/imports/preview`, data);
      const rows = [...batch.rows].sort((a, b) => (b.errors_json.length > 0) - (a.errors_json.length > 0) || a.row_no - b.row_no);
      const bad = batch.counts.errors;
      status.innerHTML = `<b>${batch.counts.total} dòng · ${bad ? bad + ' dòng cần sửa' : 'tất cả hợp lệ'}</b>`;
      preview.innerHTML = table(['Dòng', 'Mã sinh viên', 'Họ tên', 'Email', 'Kiểm tra'], rows.map(r => [r.row_no, h(r.normalized_json.student_code), h(r.normalized_json.full_name), h(r.normalized_json.email), r.errors_json.length ? `<span class="error" style="margin:0">${h(r.errors_json.join('; '))}</span>` : badge('Hợp lệ', 'good')]), i => rows[i].errors_json.length ? 'class="row-error"' : '');
      commit.disabled = bad > 0;
      commit.title = bad ? 'Sửa các dòng lỗi trong tệp rồi chọn lại tệp' : '';
      again.hidden = false;
    } catch (x) { status.textContent = ''; err.textContent = friendly(x); again.hidden = false; }
    input.value = ''; // the corrected file can be picked again even with the same name
  };
  again.onclick = () => { input.value = ''; batch = null; preview.innerHTML = ''; status.textContent = ''; commit.disabled = true; input.click(); };
  commit.onclick = () => busy(commit, async () => {
    try { const r = await api(`/imports/${batch.id}/commit`, {version: batch.version}); d.close(); await render(); notify(`Đã nhập ${batch.counts.total} sinh viên vào học phần`); return r; }
    catch (x) { err.textContent = friendly(x); }
  });
}

// ------------------------------------------------------------------ khác
async function notificationsPage() {
  const ns = await all('/me/notifications');
  window.notificationData = ns;
  return panel('Thông báo', ns.length ? `<ul class="timeline">${ns.map(n => `<li><small>${dt(n.created_at)} · ${h(n.title)}${n.read_at ? '' : ' · <b>Chưa đọc</b>'}</small><a href="${h(n.target_path || '/home')}" data-notification="${n.id}">${h(n.body || n.title)}</a></li>`).join('')}</ul>` : empty('Chưa có thông báo'));
}
async function adminPage() {
  const us = (await api('/workflow/admin/users')).items;
  window.usersData = us;
  return `<div class="toolbar"><strong>${us.length} tài khoản</strong>${button('Tạo tài khoản', 'create-user')}</div>` + panel('Tài khoản', table(['Họ tên', 'Email', 'Vai trò', 'Trạng thái', 'Thao tác'], us.map(u => [h(u.full_name), h(u.email), h(u.role), u.is_active ? 'Hoạt động' : 'Đã khóa', u.id !== me.id ? button(u.is_active ? 'Khóa' : 'Mở khóa', 'toggle-user:' + u.id, 'secondary') + ' ' + button('Đặt mật khẩu', 'reset-user:' + u.id, 'secondary') : ''])));
}
function accountPage() {
  return panel('Cài đặt tài khoản · ' + me.full_name, `<p>${h(me.email)}</p><p>Vai trò: ${h(roleLabel())}</p>${button('Đổi mật khẩu', 'change-password')}`);
}

// ------------------------------------------------------------------ router
// Client-side navigation: the top bar and sidebar stay in place, only #view changes.
const STAFF_HIDDEN = ['/projects', '/kanban', '/my-tasks', '/submissions'];
let renderSeq = 0;
function navigate(url, {replace = false} = {}) {
  const u = new URL(url, location.href);
  if (!replace) history.replaceState({...(history.state || {}), y: scrollY}, '');
  history[replace ? 'replaceState' : 'pushState']({}, '', u.pathname + u.search + u.hash);
  return render({scroll: 'top'});
}
function progress(on) {
  clearTimeout(progress.timer);
  // While a page is loading the old content cannot be clicked (avoids acting on stale data).
  if (on) $('#view').setAttribute('aria-busy', 'true'); else $('#view').removeAttribute('aria-busy');
  if (on) progress.timer = setTimeout(() => document.body.classList.add('routing'), 120);
  else document.body.classList.remove('routing');
}
// Page loads run one at a time, in order. Each page keeps its data in module variables, so a slower,
// older load must never finish after a newer one; loads superseded while waiting are skipped.
let renderQueue = Promise.resolve();
function render(opts = {}) {
  const seq = ++renderSeq;
  const run = renderQueue.then(() => (seq === renderSeq ? renderNow(opts) : undefined));
  renderQueue = run.catch(() => {});
  return run;
}
async function renderNow({scroll = 'keep', quiet = false} = {}) {
  let path = location.pathname;
  if (me.role !== 'admin' && isStaff() && STAFF_HIDDEN.includes(path)) { history.replaceState({}, '', '/home'); path = '/home'; scroll = 'top'; }
  let page, arg;
  if (!quiet) progress(true);
  try {
    if (me.role === 'admin') page = adminPage;
    else {
      homeData = await api('/workflow/home');
      if (path === '/projects') page = projectsPage;
      else if (path === '/kanban' || path === '/my-tasks') page = kanbanPage;
      else if (path === '/submissions') page = submissionsPage;
      else if (path === '/timeline') page = timelinePage;
      else if (path === '/courses') page = coursesPage;
      else if (/^\/courses\/\d+/.test(path)) { page = coursePage; arg = Number(path.split('/')[2]); }
      else if (/^\/projects\/\d+/.test(path)) { page = groupPage; arg = Number(path.split('/')[2]); }
      else if (/^\/tasks\/\d+/.test(path)) { page = taskPage; arg = Number(path.split('/')[2]); }
      else if (path === '/notifications') page = notificationsPage;
      else if (path === '/account') page = accountPage;
      else page = dashboardPage;
    }
    if (!['/projects', '/tasks'].some(p => path.startsWith(p + '/'))) projectData = null;
    const html = await page(arg);
    const y = scrollY;
    charts.forEach(c => c.destroy()); charts = []; if (page !== groupPage) reportData = null;
    $('#view').innerHTML = html;
    chrome();
    page.bind?.();
    bindSearch();
    const target = location.hash && document.getElementById(decodeURIComponent(location.hash.slice(1)));
    if (target && page !== taskPage) target.scrollIntoView({block: 'start'});
    else if (scroll === 'top') scrollTo(0, 0);
    else if (typeof scroll === 'number') scrollTo(0, scroll);
    else scrollTo(0, y);
    lastRender = Date.now();
  } finally { progress(false); }
  updateUnread();
}
let lastRender = Date.now();
// Same-origin links open inside the app shell; downloads, API files and new tabs keep the browser default.
document.addEventListener('click', e => {
  if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || !me) return;
  const a = e.target.closest('a[href]');
  if (!a || a.target || a.hasAttribute('download') || a.closest('[data-action]')) return;
  const u = new URL(a.href, location.href);
  if (u.origin !== location.origin || u.pathname.startsWith('/api/') || u.pathname.startsWith('/static/') || u.pathname === '/login') return;
  if (u.pathname === location.pathname && u.search === location.search && u.hash) return; // in-page anchor
  e.preventDefault();
  document.body.classList.remove('side-open'); $('#scrim').hidden = true;
  attempt(() => navigate(u.href));
});
function bindSearch() {
  $$('[data-search-input]').forEach(i => i.oninput = () => { const q = i.value.trim().toLowerCase(); $$('[data-search]').forEach(el => { el.hidden = !el.dataset.search.includes(q); }); });
}
async function updateUnread() {
  try { const n = (await api('/me/notifications?unread_only=true&page_size=1')).total; $('#unread-dot').hidden = !n; $('#unread').textContent = n ? n + ' thông báo chưa đọc' : 'Không có thông báo mới'; } catch { /* ignore */ }
}

// ------------------------------------------------------------------ actions
function taskForm(t = null, notes = '') {
  const p = projectData, ms = p.members.filter(m => m.status === 'active'), assigned = t?.participants || [];
  const due = Math.min(nowMs() + 3 * 86400000, new Date(p.assignment.due_at).getTime());
  const content = field('title', 'Tên công việc', 'text', t?.title || '') + area('description', 'Đầu ra cần bàn giao', t?.description || notes) +
    select('responsible', 'Người phụ trách', ms.map(m => [m.user_id, m.user.full_name]), assigned.find(x => x.role === 'responsible')?.user_id) +
    `<fieldset><legend>Người cùng làm (nếu có)</legend>${ms.map(m => `<label class="check"><input type="checkbox" name="collaborators" value="${m.user_id}" ${assigned.some(x => x.role === 'collaborator' && x.user_id === m.user_id) ? 'checked' : ''}>${h(m.user.full_name)}</label>`).join('')}</fieldset>` +
    (t ? '' : field('due_at', 'Hạn', 'datetime-local', toLocalInput(due))) +
    select('points', 'Khối lượng', [[1, '1'], [2, '2'], [3, '3'], [5, '5']], t?.points || 1) + select('priority', 'Mức ưu tiên', [['low', 'Thấp'], ['medium', 'Vừa'], ['high', 'Cao']], t?.priority || 'medium');
  modal(t ? 'Sửa phân công' : 'Tạo công việc', content, async f => {
    const responsible = Number(f.get('responsible'));
    const participants = [{user_id: responsible, role: 'responsible'}, ...f.getAll('collaborators').map(Number).filter(id => id !== responsible).map(id => ({user_id: id, role: 'collaborator'}))];
    const b = {title: f.get('title'), description: f.get('description'), participants, points: Number(f.get('points')), priority: f.get('priority')};
    if (t) { b.version = t.version; await api('/workflow/tasks/' + t.id + '/assignment', b); }
    else { b.due_at = iso(f.get('due_at')); await api('/projects/' + p.id + '/tasks', b); }
  });
}
async function action(a, btn) {
  const [key, idText] = a.split(':'), id = Number(idText), p = projectData, t = taskData;
  if (key === 'create-project') return createProjectModal();
  if (key === 'tl-shift') return timelineShift(id);
  if (key === 'tl-today') return timelineShift(0);
  if (key === 'tl-add') return scheduleForm(null, idText || '');
  if (key === 'ai-schedule') return aiScheduleModal();
  if (key === 'ai-undo') return aiUndo(btn);
  if (key === 'ai-redo') return aiRedo(btn);
  if (key === 'ai-plan') return aiPlanModal();
  if (key === 'tl-edit') return scheduleForm(tlData.items.find(x => x.kind === 'item' && x.id === id));
  if (key === 'tl-view') return scheduleView(tlData.items.find(x => x.kind === 'item' && x.id === id));
  if (key === 'tl-delete') { if (!confirm('Xóa mục lịch này?')) return; await api('/workflow/schedule/' + id, {}, 'DELETE'); document.querySelector('dialog[open]')?.close(); await render(); return notify('Đã xóa mục lịch'); }
  if (key === 'more-alerts') { const open = btn.getAttribute('aria-expanded') !== 'true'; $$('#attention-list [data-extra]').forEach(x => { x.hidden = !open; }); btn.setAttribute('aria-expanded', String(open)); btn.textContent = open ? 'Thu gọn' : `Xem thêm (${$$('#attention-list [data-extra]').length})`; return; }
  if (key === 'toggle-history') { const el = $('#history'); el.hidden = !el.hidden; btn.setAttribute('aria-expanded', String(!el.hidden)); btn.textContent = el.hidden ? 'Xem bản cũ' : 'Ẩn bản cũ'; return; }
  if (key === 'create-course') return modal('Tạo lớp học phần', field('code', 'Mã lớp') + field('title', 'Tên học phần') + field('term', 'Học kỳ', 'text', 'HK1 · 2026–2027'), f => api('/courses', Object.fromEntries(f)));
  if (key === 'create-assignment') return modal('Đề bài nhóm', field('title', 'Tên đề bài') + area('brief', 'Mô tả') + field('due_at', 'Hạn nộp', 'datetime-local', toLocalInput(nowMs() + 40 * 86400000)) + field('group_min', 'Số thành viên tối thiểu', 'number', 3) + field('group_max', 'Số thành viên tối đa', 'number', 6) + select('group_mode', 'Cách lập nhóm', [['self', 'Sinh viên tự lập, giảng viên duyệt'], ['teacher', 'Xếp nhóm']]), async f => {
    const b = Object.fromEntries(f); b.due_at = iso(b.due_at); b.formation_due_at = iso(toLocalInput(nowMs() + 7 * 86400000)); b.group_min = Number(b.group_min); b.group_max = Number(b.group_max);
    const x = await api(`/courses/${id}/assignments`, b); await api(`/workflow/assignments/${x.id}/publish`, {version: x.version}); return 'Đã tạo và công bố đề bài';
  });
  if (key === 'edit-assignment') { const x = currentCourse.assignment; return modal('Sửa đề bài', field('title', 'Tên đề bài', 'text', x.title) + area('brief', 'Mô tả', x.brief) + field('due_at', 'Hạn nộp', 'datetime-local', toLocalInput(new Date(x.due_at).getTime())), f => api('/assignments/' + x.id, {version: x.version, title: f.get('title'), brief: f.get('brief'), due_at: iso(f.get('due_at'))}, 'PATCH')); }
  if (key === 'assignment-files') return modal('Tài liệu đề bài / tiêu chí', `<label>Tài liệu<input type="file" name="files" multiple required></label>`, f => api('/assignments/' + id + '/files', f));
  if (key === 'add-criterion') return modal('Thêm tiêu chí minh chứng', field('title', 'Tên tiêu chí') + area('description', 'Mô tả (tùy chọn)', '', false), f => api(`/workflow/assignments/${id}/evidence-criteria`, {title: f.get('title'), description: f.get('description')}).then(() => 'Đã thêm tiêu chí'));
  if (key === 'toggle-criterion') { const c = criteriaData.find(x => x.id === id); await busy(btn, () => api(`/workflow/evidence-criteria/${id}`, {version: c.version, is_active: !c.is_active}, 'PATCH')); await render(); return notify(c.is_active ? 'Đã ẩn tiêu chí. Các lần nộp cũ vẫn giữ liên kết.' : 'Đã bật lại tiêu chí'); }
  if (key === 'import') return importModal(id);
  if (key === 'create-group') return modal('Tạo nhóm', field('name', 'Tên nhóm'), f => api('/assignments/' + id + '/projects', {name: f.get('name')}));
  if (key === 'teacher-group') { const people = (await api('/assignments/' + id + '/invite-candidates')).students; return modal('Xếp nhóm', field('name', 'Tên nhóm') + select('leader_id', 'Trưởng nhóm', people.map(x => [x.id, x.full_name])) + `<fieldset><legend>Thành viên</legend>${people.map(x => `<label class="check"><input type="checkbox" name="members" value="${x.id}">${h(x.full_name)}</label>`).join('')}</fieldset>`, f => { const lid = Number(f.get('leader_id')); return api(`/workflow/assignments/${id}/groups`, {name: f.get('name'), leader_id: lid, user_ids: [...new Set([lid, ...f.getAll('members').map(Number)])]}); }); }
  if (key === 'enroll') return modal('Thêm sinh viên vào lớp', field('email', 'Email tài khoản', 'email') + field('student_code', 'Mã sinh viên'), f => api(`/courses/${id}/enrollments`, {...Object.fromEntries(f), role: 'student'}));
  if (key === 'submit-group' || key === 'approve-group') { await busy(btn, () => api(`/workflow/projects/${p.id}/approval`, {version: p.version, action: key === 'submit-group' ? 'submit' : 'accept'})); return render(); }
  if (key === 'return-group') return modal('Yêu cầu bổ sung', area('reason', 'Lý do'), f => api(`/workflow/projects/${p.id}/approval`, {version: p.version, action: 'return', reason: f.get('reason')}));
  if (key === 'invite-member') return modal('Mời thành viên', select('user_id', 'Sinh viên', window.candidates.map(u => [u.id, u.full_name + ' · ' + u.email])), f => api(`/projects/${p.id}/invitations`, {version: p.version, kind: 'member', user_id: Number(f.get('user_id'))}));
  if (key === 'invite' || key === 'reject-invite') { const i = window.invites.find(x => x.id === id); await busy(btn, () => api(`/invitations/${id}/respond`, {version: i.version, action: key === 'invite' ? 'accept' : 'reject'})); return render(); }
  if (key === 'readmit') { const cs = (await api(`/assignments/${p.assignment_id}/invite-candidates`)).students; return modal('Xếp thêm / tiếp nhận lại thành viên', select('user_id', 'Sinh viên', cs.map(x => [x.id, x.full_name])) + area('reason', 'Lý do'), f => api(`/workflow/projects/${p.id}/readmit`, {version: p.version, user_id: Number(f.get('user_id')), reason: f.get('reason')})); }
  if (key === 'leave-group') return modal('Xin rời nhóm', area('reason', 'Lý do'), f => api(`/workflow/projects/${p.id}/departures`, {reason: f.get('reason')}));
  if (key === 'vote-yes' || key === 'vote-no') { const x = window.departuresData.find(x => x.id === id); await busy(btn, () => api(`/workflow/departures/${id}/vote`, {version: x.version, agree: key === 'vote-yes'})); return render(); }
  if (key === 'new-task') return taskForm();
  if (key === 'edit-task') return taskForm(t);
  if (key === 'start-task') { await busy(btn, () => api(`/tasks/${t.id}/start`, {version: t.version})); return render(); }
  if (key === 'refer') return modal('Chuyển giảng viên duyệt', `<p class="small muted">Chỉ chuyển đúng lần nộp này. Nếu sinh viên nộp lại, lần mới sẽ được xét quyền duyệt lại.</p>` + area('reason', 'Lý do chuyển'), f => api(`/submissions/${id}/refer`, {reason: f.get('reason')}).then(() => 'Đã chuyển bản nộp cho giảng viên'));
  if (key === 'extend-task') return modal('Đề nghị gia hạn', field('requested_due_at', 'Hạn đề nghị', 'datetime-local', toLocalInput(nowMs() + 3 * 86400000)) + area('reason', 'Lý do'), f => api(`/tasks/${t.id}/extensions`, {version: t.version, due_at: iso(f.get('requested_due_at')), reason: f.get('reason')}));
  if (key === 'decide-extension') { const x = window.extensionsData.find(x => x.id === id); return modal('Xử lý gia hạn', select('action', 'Quyết định', [['approve', 'Đồng ý'], ['reject', 'Từ chối']]) + area('reason', 'Nhận xét'), f => api(`/extensions/${id}/decide`, {version: x.version, ...Object.fromEntries(f)})); }
  if (key === 'new-minutes') return modal('Biên bản họp', field('title', 'Chủ đề') + area('notes', 'Kết luận và đầu việc') + field('link', 'Link cuộc họp', 'url', '', false), f => api(`/workflow/projects/${p.id}/minutes`, Object.fromEntries(f)));
  if (key === 'minute-task') return taskForm(null, window.minutesData.find(x => x.id === id).notes);
  if (key === 'new-complaint') return modal('Đề nghị điều chỉnh đóng góp', select('target_id', 'Thành viên liên quan', t.participants.filter(x => x.user_id !== me.id).map(x => [x.user_id, x.user.full_name])) + area('reason', 'Nội dung và căn cứ đề nghị'), f => api(`/projects/${p.id}/complaints`, {task_id: t.id, target_id: Number(f.get('target_id')), reason: f.get('reason')}));
  if (key === 'explain') { const c = window.casesData.find(c => c.id === id); return modal('Giải trình', area('explanation', 'Nội dung giải trình', c.explanation || ''), f => api(`/complaints/${id}/explain`, {version: c.version, explanation: f.get('explanation')})); }
  if (key === 'resolve') { const c = window.casesData.find(c => c.id === id); return modal('Xử lý đề nghị', Object.entries(c.shares).map(([uid, v]) => field('share_' + uid, (c.participants.find(x => x.user.id === Number(uid))?.user.full_name || uid) + ' (%)', 'number', v)).join('') + area('reason', 'Kết luận và căn cứ') + (!c.explanation ? '<label class="check"><input type="checkbox" name="opportunity" required>Đã tạo cơ hội giải trình nhưng chưa nhận phản hồi</label>' : ''), f => { const shares = Object.fromEntries(Object.keys(c.shares).map(uid => [uid, f.get('share_' + uid)])); const total = Object.values(shares).reduce((s, v) => s + Number(v), 0); if (Math.abs(total - 100) > 0.001) throw Error('Tổng tỷ lệ phải đúng 100% (hiện ' + total + '%)'); return api(`/complaints/${id}/resolve`, {version: c.version, reason: f.get('reason'), explanation_not_provided: f.has('opportunity'), shares}); }); }
  if (key === 'escalate') { const c = window.casesData.find(c => c.id === id); return modal('Nhờ giảng viên hỗ trợ', area('reason', 'Lý do'), f => api(`/complaints/${id}/escalate`, {version: c.version, reason: f.get('reason')})); }
  if (key === 'peer-task') return peerTaskForm(window.peerData.tasks.find(x => x.id === id));
  if (key === 'deliver') { const ts = groupTasks.filter(t => t.status === 'done'); return modal('Bàn giao sản phẩm nhóm', field('title', 'Tên bản bàn giao', 'text', 'Sản phẩm nhóm') + (ts.map(t => `<label class="check"><input type="checkbox" name="submissions" value="${t.latest_submission_id}">${h(t.title)}</label>`).join('') || empty('Chưa có bài đã duyệt.')), f => api(`/workflow/projects/${p.id}/deliveries`, {title: f.get('title'), submission_ids: f.getAll('submissions').map(Number)})); }
  if (key === 'new-help') return modal('Yêu cầu hỗ trợ', field('subject', 'Tiêu đề') + select('task_id', 'Phạm vi', [['', 'Chọn phạm vi'], ['group', 'Vấn đề chung của dự án'], ...groupTasks.map(t => [t.id, t.title])]) + area('content', 'Khó khăn và đề nghị hỗ trợ'), f => { const scope = f.get('task_id'); if (!scope) throw Error('Cần chọn phạm vi hỗ trợ'); return api(`/projects/${p.id}/help-requests`, {subject: f.get('subject'), content: f.get('content'), scope: scope === 'group' ? 'group' : 'task', task_id: scope === 'group' ? null : Number(scope)}); });
  if (key === 'help-response') { const x = window.helpData.find(x => x.id === id); return modal('Phản hồi hỗ trợ', area('response', 'Nội dung', x.response || '') + '<label class="check"><input type="checkbox" name="resolve">Đã hỗ trợ xong</label>', f => api(`/help-requests/${id}/respond`, {version: x.version, response: f.get('response'), resolve: f.has('resolve')})); }
  if (key === 'create-user') return modal('Tạo tài khoản', field('full_name', 'Họ tên') + field('email', 'Email', 'email') + select('role', 'Vai trò', [['user', 'Sinh viên'], ['instructor', 'Giảng viên'], ['admin', 'Quản trị hệ thống']]) + field('password', 'Mật khẩu', 'password', '12345'), f => api('/workflow/admin/users', Object.fromEntries(f)));
  if (key === 'toggle-user') { const u = window.usersData.find(u => u.id === id); await busy(btn, () => api('/workflow/admin/users/' + id, {is_active: !u.is_active}, 'PATCH')); return render(); }
  if (key === 'reset-user') return modal('Đặt mật khẩu', field('password', 'Mật khẩu mới', 'password'), f => api('/workflow/admin/users/' + id, Object.fromEntries(f), 'PATCH'));
  if (key === 'change-password') return modal('Đổi mật khẩu', field('old_password', 'Mật khẩu hiện tại', 'password') + field('new_password', 'Mật khẩu mới', 'password'), f => api('/me/password', Object.fromEntries(f)));
}
document.addEventListener('click', e => {
  const b = e.target.closest('[data-action]');
  if (b) { e.preventDefault(); attempt(() => action(b.dataset.action, b)); return; }
  const n = e.target.closest('[data-notification]');
  if (n) { api(`/notifications/${n.dataset.notification}/read`, {}).catch(() => {}); }
});

// ------------------------------------------------------------------ boot
async function loginPage() {
  document.body.classList.add('auth');
  const expired = new URLSearchParams(location.search).has('expired');
  $('#view').innerHTML = `<section class="login"><h1>TeamSync</h1><p class="muted">Đăng nhập vào không gian làm việc nhóm</p>${expired ? '<p class="block-note" role="alert">Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.</p>' : ''}<form id="login-form" novalidate>${field('email', 'Email', 'email', '', true, 'autocomplete="username"')}${field('password', 'Mật khẩu', 'password', '', true, 'autocomplete="current-password"')}<p class="error" role="alert"></p><button type="submit">Đăng nhập</button></form></section>`;
  $('#login-form').onsubmit = async e => {
    e.preventDefault();
    await busy(e.submitter, async () => {
      try { await api('/auth/login', Object.fromEntries(new FormData(e.target))); location.href = '/home'; }
      catch (err) { e.target.querySelector('.error').textContent = err.message; }
    });
  };
}
async function boot() {
  csrf = (await api('/auth/csrf')).token;
  if (location.pathname === '/login') return loginPage();
  try { me = await api('/auth/me'); } catch { location.href = '/login'; return; }
  clockOffset = new Date(me.business_time).getTime() - Date.now();
  if (Math.abs(clockOffset) < 120000) clockOffset = 0;
  setupChrome();
  await render();
}
addEventListener('popstate', e => { if (me) attempt(() => render({scroll: e.state?.y ?? 'top'})); });
boot().catch(e => { $('#view').innerHTML = panel('Không tải được nội dung', `<p>${h(e.message)}</p>${link('Về tổng quan', '/home')}`); });

setInterval(() => {
  if (!me || document.hidden) return;
  updateUnread();
}, 30000);
// Every 5 minutes: drop cached data and quietly redraw the current page with fresh data,
// unless the user is in the middle of something (open dialog, focused field, unsent form).
setInterval(() => {
  if (!me || document.hidden) return;
  clearCache();
  const busyUser = document.querySelector('dialog[open]') || document.activeElement?.matches?.('input,textarea,select') ||
    [...document.querySelectorAll('#view textarea, #view input[type=text], #view input[type=file]')].some(x => x.value);
  if (!busyUser && Date.now() - lastRender >= CACHE_TTL - 1000) attempt(() => render({quiet: true}));
}, CACHE_TTL);
