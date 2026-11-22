import {groupHeader,groupNavigation} from "./group-navigation.js?v=9";
import {contributionMarkup,reportSummary} from "./report-components.js?v=9";
/* Framework-free components, isolated lifecycle and durable REST replay. */
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const date = v => v ? new Date(v).toLocaleString('vi-VN') : 'Chưa có hạn';
const statuses = {todo:'Cần làm',in_progress:'Đang làm',review:'Merge Request',done:'Hoàn thành'};
let csrf, socket, timer, jitsi, attendanceTimer, aborter, refreshTimer;
let root, state;
const api = async (path, body, method='POST') => {
  const headers = {'X-CSRF-Token':csrf,'Idempotency-Key':crypto.randomUUID()};
  if (!(body instanceof FormData)) headers['Content-Type']='application/json';
  const response=await fetch('/api/v1'+path,{method,headers,body:body===undefined?undefined:body instanceof FormData?body:JSON.stringify(body)});
  const data=await response.json();
  if(!response.ok) throw Error(data.error?.message || 'Không xử lý được yêu cầu');
  return data.data;
};
const get = path => api(path,undefined,'GET');
const button = (label,action,cls='') => `<button type="button" class="${cls}" data-do="${action}">${label}</button>`;
const field = (name,label,type='text',value='',extra='') => `<label>${label}<input name="${name}" type="${type}" value="${esc(value)}" ${extra} required></label>`;
const info = text => `<div class="studio-empty">${text}</div>`;
const options = (items,id='id',title='full_name') => items.map(x=>`<option value="${x[id]}">${esc(x[title])}</option>`).join('');
const activeMembers = () => state.p.members.filter(m=>m.status==='active').map(m=>m.user);
const teacher = () => ['instructor','coordinator'].includes(state.p.my_role);
const leader = () => state.p.my_role==='leader';
function toast(message,error=false) {
  const el=document.createElement('div');el.className='studio-toast'+(error?' error':'');el.role=error?'alert':'status';const text=document.createElement('span');text.textContent=message;const close=document.createElement('button');close.type='button';close.textContent='×';close.setAttribute('aria-label','Đóng thông báo');close.onclick=()=>el.remove();el.append(text,close);
  document.body.append(el);setTimeout(()=>el.remove(),4500);
}
export function cleanupStudio() {
  aborter?.abort(); clearInterval(timer);clearInterval(attendanceTimer);clearTimeout(refreshTimer);
  socket?.disconnect();socket=null;jitsi?.dispose();jitsi=null;
  document.querySelectorAll('.studio-dialog,.task-overlay').forEach(e=>e.remove());
}
function dialog(title,content,onSubmit,submitLabel='Lưu') {
  const d=document.createElement('dialog');d.className='studio-dialog';
  d.innerHTML=`<form><div class="dialog-heading"><h2>${esc(title)}</h2><button type="button" class="secondary close-dialog" aria-label="Đóng">×</button></div>${content}<p class="dialog-error" role="alert"></p><div class="dialog-actions"><button type="button" class="secondary close-dialog">Hủy</button><button type="submit">${submitLabel}</button></div></form>`;
  document.body.append(d);d.showModal();
  d.querySelectorAll('.close-dialog').forEach(b=>b.onclick=()=>d.close());
  d.addEventListener('close',()=>d.remove());
  d.querySelectorAll('input[type=range]').forEach(input=>input.oninput=()=>input.nextElementSibling.textContent=input.value);
  d.querySelector('form').onsubmit=async e=>{
    e.preventDefault();const btn=e.submitter;btn.disabled=true;
    try{await onSubmit(new FormData(e.target),d);d.close();toast('Đã lưu thay đổi');await refresh();}
    catch(err){d.querySelector('.dialog-error').textContent=err.message;}finally{btn.disabled=false;}
  };
  return d;
}
const localDue = value => {const d=new Date((value?new Date(value).getTime():Date.now())+86400000);return new Date(d.getTime()-d.getTimezoneOffset()*60000).toISOString().slice(0,16);};
const isoDue = data => new Date(data.get('due_at')).toISOString();
export async function mountStudio(element,p,me,options={}) {
  cleanupStudio();root=element;aborter=new AbortController();
  const requested=new URLSearchParams(location.search).get('pane')||'board';
  const selected=element.dataset.startPane||requested;
  const initial=selected==='gantt'?'board':['report','insights','summary'].includes(selected)?'summary':selected;
  const reconcile=element.querySelector('[data-summary-reconcile]')?.innerHTML||'',quality=element.querySelector('[data-summary-quality]')?.innerHTML||'';
  state={...options,reconcile,quality,summarySection:element.dataset.summarySection||new URLSearchParams(location.search).get('section')||(requested==='insights'?'commitment':'progress'),p,me,pane:['chat','internal'].includes(initial)?'board':initial,drawer:['chat','internal'].includes(initial),drawerPane:initial==='internal'?'internal':'chat',tasks:[],meeting:null};
  csrf=(await get('/auth/csrf')).token;
  if(teacher() && !['board','final','summary'].includes(state.pane))state.pane='board';
  root.addEventListener('click',handleClick,{signal:aborter.signal});
  root.addEventListener('keydown',e=>{const c=e.target.closest('[data-open-task]');if(c&&(e.key==='Enter'||e.key===' ')){e.preventDefault();openTask(Number(c.dataset.openTask),c);}}, {signal:aborter.signal});
  root.addEventListener('dragstart',e=>{const card=e.target.closest('[data-task]');if(card){e.dataTransfer.setData('text/task',card.dataset.task);card.classList.add('dragging');} const draft=e.target.closest('[data-draft]');if(draft)e.dataTransfer.setData('text/draft',draft.dataset.draft);},{signal:aborter.signal});
  root.addEventListener('dragend',()=>root.querySelectorAll('.dragging,.drag-over').forEach(e=>e.classList.remove('dragging','drag-over')),{signal:aborter.signal});
  root.addEventListener('dragover',e=>{const col=e.target.closest('[data-status]');if(col&&!teacher()){e.preventDefault();col.classList.add('drag-over');}},{signal:aborter.signal});
  root.addEventListener('dragleave',e=>e.target.closest('[data-status]')?.classList.remove('drag-over'),{signal:aborter.signal});
  root.addEventListener('drop',async e=>{
    const col=e.target.closest('[data-status]');if(!col||teacher())return;e.preventDefault();col.classList.remove('drag-over');
    const did=Number(e.dataTransfer.getData('text/draft'));
    if(did){if(col.dataset.status==='todo'&&leader())acceptDraft(did);return;}
    const tid=Number(e.dataTransfer.getData('text/task'));const t=state.tasks.find(t=>t.id===tid);if(!t||t.status===col.dataset.status)return;
    await attempt(async()=>{
      await api(`/tasks/${tid}/move`,{version:t.version,status:col.dataset.status});await refresh();
    });
  },{signal:aborter.signal});
  await refresh();
  if(window.io&&!teacher()){
    socket=window.io({auth:{csrf}});
    socket.on('connect',()=>socket.emit('team:join',{project_id:p.id}));
    ['chat:changed','kanban:changed'].forEach(event=>socket.on(event,()=>{
      if((!['chat','board','insights'].includes(state.pane)&&!state.drawer)||root.querySelector('textarea:focus,input:focus')||document.querySelector('.task-overlay[open]'))return;
      clearTimeout(refreshTimer);refreshTimer=setTimeout(()=>(state.drawer?updateDrawer():refresh()).catch(()=>{}),250);
    }));
  }
  timer=setInterval(()=>{
    if(document.hidden||!root.isConnected||root.querySelector('textarea:focus,input:focus')||document.querySelector('dialog[open]'))return;
    if(['chat','board','insights'].includes(state.pane))refresh().catch(()=>{});
  },15000);
}
async function attempt(fn){try{await fn();}catch(e){toast(e.message,true);}}
async function refresh(){
  if(!root?.isConnected)return;
  let data=await get(`/projects/${state.p.id}/tasks?page_size=100`);state.tasks=data.items;
  for(let page=2;state.tasks.length<data.total;page++)state.tasks.push(...(await get(`/projects/${state.p.id}/tasks?page_size=100&page=${page}`)).items);
  const done=state.tasks.filter(t=>t.status==='done').length;
  let body='';
  if(state.pane==='board')body=await board();

  if(state.pane==='chat')body=await chat();
  if(['internal','final'].includes(state.pane))body=await vaultUI(state.pane);
  if(state.pane==='meeting')body=await meetingsUI();
  if(state.pane==='summary')body=await unifiedSummary();
  if(state.pane==='peer')body=await peerUI();

  // Keep the live iframe mounted while working with meeting notes.
  if(state.pane==='meeting'&&jitsi&&root.querySelector('#meeting-layout'))return;
  const drawer=state.drawer&&!teacher()?await drawerMarkup():'';
  const discussion=!teacher()?button(state.drawer?'Đóng trao đổi':'Thảo luận & tài liệu','drawer-toggle','secondary drawer-toggle discussion-launch'):'';
  root.innerHTML=`${groupHeader(state.p,{done,total:state.tasks.length})}${groupNavigation(state.p,state.pane,discussion,true)}<div class="studio-body group-content">${body}</div>${drawer}`;

  const log=root.querySelector('.chat-log');if(log)log.scrollTop=log.scrollHeight;
}
async function drawerMarkup(){
  return `<aside class="team-drawer" aria-label="Thảo luận và tài liệu"><div class="drawer-head"><div><span class="overline">KHÔNG GIAN NHÓM</span><h3>Trao đổi & tài liệu</h3></div><button class="icon-button" data-do="drawer-close" aria-label="Thu gọn">×</button></div><nav class="drawer-tabs" aria-label="Nội dung nhóm">${button('Thảo luận','drawer-tab:chat',state.drawerPane==='chat'?'selected':'secondary')}${button('Kho Tài liệu','drawer-tab:internal',state.drawerPane==='internal'?'selected':'secondary')}</nav><div class="drawer-content">${state.drawerPane==='chat'?await chat():await vaultUI('internal')}</div></aside>`;
}
async function updateDrawer(){
  const previous=root.querySelector('.team-drawer');
  if(state.drawer){const markup=await drawerMarkup();if(previous)previous.outerHTML=markup;else root.insertAdjacentHTML('beforeend',markup);}
  else previous?.remove();
  const toggle=root.querySelector('[data-do="drawer-toggle"]');if(toggle)toggle.textContent=state.drawer?'Đóng trao đổi':'Thảo luận & tài liệu';
  const log=root.querySelector('.team-drawer .chat-log');if(log)log.scrollTop=log.scrollHeight;
}
const editable = () => !['archived','finalized'].includes(state.p.status);
async function board(){
  const isTeacher=teacher();
  const cols=Object.entries(statuses).map(([status,label])=>{
    const ts=state.tasks.filter(t=>t.status===status);
    return `<section class="kanban-column ${status}" data-status="${status}" aria-label="${label}"><h3><span class="status-dot"></span>${label}<small>${ts.length}</small></h3>${ts.map(t=>`<article class="kanban-card" role="button" tabindex="0" aria-label="Mở công việc: ${esc(t.title)}" draggable="${!isTeacher&&editable()&&['todo','in_progress'].includes(t.status)}" data-task="${t.id}" data-open-task="${t.id}"><strong>${esc(t.title)}</strong><footer><span class="member-dot" title="${esc(t.participants[0]?.user.full_name||'Chưa giao')}">${esc((t.participants[0]?.user.full_name||'?').slice(0,1))}</span><time class="${t.due_at&&new Date(t.due_at)<new Date()&&t.status!=='done'?'overdue':''}">${t.due_at?new Date(t.due_at).toLocaleDateString('vi-VN',{day:'2-digit',month:'2-digit',year:'numeric'}):'Chưa có hạn'}</time></footer></article>`).join('')||'<p class="empty-column">Chưa có công việc</p>'}</section>`;
  }).join('');
  return `<div class="studio-toolbar"><p>${isTeacher?'Chế độ theo dõi':'Chọn thẻ để xem chi tiết. Kéo thả để cập nhật tiến độ.'}</p><div class="toolbar-actions">${leader()?button('Xem mẫu kế hoạch','template','secondary'):''}${!isTeacher&&editable()?button('+ Tạo công việc','new-task'):''}</div></div><div class="kanban-grid">${cols}</div>`;
}
async function openTask(id, trigger){
  await attempt(async()=>{
    const t=await get(`/tasks/${id}`);
    const comments=teacher()?[]:(await get(`/tasks/${id}/comments?page_size=100`)).items;
    const participant=t.participants.some(x=>x.user_id===state.me.id);
    const pending=leader()?(await get(`/projects/${state.p.id}/merge-requests`)).items.find(x=>x.task.id===id&&x.submission.status==='pending'):null;
    document.querySelector('.task-overlay')?.remove();
    const panel=document.createElement('dialog');panel.className='task-overlay';panel.setAttribute('aria-labelledby','task-panel-title');
    panel.innerHTML=`<div class="task-panel"><div class="task-panel-head"><div><span class="overline">CHI TIẾT CÔNG VIỆC</span><h2 id="task-panel-title">${esc(t.title)}</h2></div><button class="icon-button panel-close" aria-label="Đóng chi tiết">×</button></div><div class="task-panel-content"><span class="task-state">${esc(statuses[t.status])}</span><dl class="task-facts"><div><dt>Phụ trách</dt><dd>${t.participants.map(x=>esc(x.user.full_name)).join(', ')||'Chưa giao'}</dd></div><div><dt>Hạn chót</dt><dd>${date(t.due_at)}</dd></div></dl><section><h3>Mô tả</h3><p class="task-description">${esc(t.description||'Chưa có mô tả.')}</p></section>${!teacher()?`<section><h3>Tài liệu đính kèm</h3><div class="task-attachments">${(t.assets||[]).map(a=>`<a href="${esc(a.download_url||a.url)}" target="_blank" rel="noopener noreferrer">↗ ${esc(a.original_filename||a.url||'Tài liệu')}</a>`).join('')||'<p>Chưa có tài liệu.</p>'}</div></section><section><h3>Thảo luận công việc</h3><div class="task-comments">${comments.map(c=>`<p><strong>${esc(c.user.full_name)}</strong><br>${esc(c.content)}</p>`).join('')||'<p>Chưa có trao đổi.</p>'}</div>${editable()?'<form class="task-comment-form"><label class="sr-only" for="task-comment-input">Nội dung thảo luận</label><textarea id="task-comment-input" name="content" rows="2" placeholder="Viết trao đổi…" required></textarea><button type="submit" class="secondary">Gửi trao đổi</button></form>':''}</section>`:''}</div><footer class="task-panel-footer"><a class="secondary button" href="/tasks/${id}">Chi tiết đầy đủ</a>${!teacher()&&editable()&&participant&&t.status==='todo'?'<button class="task-start">Bắt đầu</button>':''}${!teacher()&&editable()&&participant&&t.status==='in_progress'?`<a class="button" href="/tasks/${id}/submit">Gửi Review</a>`:''}${pending?'<button class="task-review">Review bản nộp</button>':''}</footer></div>`;
    document.body.append(panel);panel.showModal();
    const close=()=>panel.close();panel.querySelector('.panel-close').onclick=close;
    panel.addEventListener('click',e=>{if(e.target===panel)close()});
    panel.addEventListener('close',()=>{panel.remove();(root?.querySelector(`[data-open-task="${id}"]`)||trigger)?.focus();});
    panel.querySelector('.task-start')?.addEventListener('click',async()=>attempt(async()=>{await api(`/tasks/${id}/start`,{version:t.version});close();await refresh();await openTask(id,trigger)}));
    panel.querySelector('.task-review')?.addEventListener('click',()=>{close();dialog(`Review: ${t.title}`,`<p>Nhánh <strong>${esc(pending.branch.name)}</strong></p><label>Kết quả<select name="action"><option value="accept">Merge & Pass</option><option value="return">Yêu cầu sửa</option></select></label>${field('reason','Nhận xét review')}`,async f=>api(`/submissions/${pending.id}/review`,{version:t.version,action:f.get('action'),reason:f.get('reason')}),'Xác nhận review');});
    panel.querySelector('.task-comment-form')?.addEventListener('submit',async e=>{e.preventDefault();const form=e.currentTarget;await attempt(async()=>{await api(`/tasks/${id}/comments`,{content:form.elements.content.value});close();await openTask(id,trigger);});});
  });
}
async function chat(){
  let cursor=0,items=[];
  for(let i=0;i<20;i++){
    const data=await get(`/projects/${state.p.id}/messages?after=${cursor}`);items.push(...data.items);cursor=data.next_cursor;if(data.items.length<100)break;
  }
  return `<div class="chat-vault-layout"><section class="studio-panel chat-panel"><div class="chat-heading"><h3>Cuộc trò chuyện nhóm</h3><span class="privacy-chip">Chỉ Leader & Member</span></div><div class="chat-log" role="log" aria-label="Tin nhắn nhóm">${items.map(m=>`<article class="chat-message ${m.sender_id===state.me.id?'mine':''} ${m.kind==='ping'?'system-ping':''}"><small>${esc(m.sender.full_name)} · ${date(m.created_at)}</small><p>${esc(m.content)}</p>${m.files.map(f=>`<a href="${esc(f.url||f.download_url)}" target="_blank" rel="noopener noreferrer">↗ ${esc(f.filename||f.title)}</a>`).join('')}</article>`).join('')||info('Bắt đầu cuộc trò chuyện đầu tiên của nhóm.')}</div><form id="chat-compose"><label class="sr-only" for="chat-text">Tin nhắn</label><textarea id="chat-text" name="content" placeholder="Chia sẻ cập nhật, câu hỏi hoặc liên kết…" maxlength="4000" rows="2"></textarea><div class="compose-actions"><label class="file-button">Đính kèm<input name="file" type="file" aria-label="Đính kèm file"></label><button type="submit">Gửi tin nhắn ↗</button></div></form></section><aside class="studio-panel"><div class="vault-icon">▤</div><h3>Tài liệu tự sắp xếp</h3><p>File, ảnh và liên kết gửi trong chat được thêm vào Kho nháp của nhóm.</p><p>Giảng viên chỉ xem được những tài liệu trưởng nhóm chủ động nộp Final.</p>${button('Mở kho nháp','pane:internal','secondary')}</aside></div>`;
}
async function vaultUI(kind){
  const data=await get(`/projects/${state.p.id}/vaults/${kind}`);
  const groups={file:[],image:[],link:[]};
  data.items.forEach(f=>groups[f.kind==='link'?'link':/\.(png|jpe?g)$/i.test(f.filename||'')?'image':'file'].push(f));
  return `<div class="studio-toolbar"><div><h3>${kind==='final'?'Bài nộp hoàn thiện':'Tài liệu nội bộ'}</h3><p>${kind==='final'?'Các bản nộp được giữ nguyên để đối chiếu.':'Không gian riêng của nhóm. Chỉ trưởng nhóm được công bố tài liệu sang kho Final.'}</p></div>${kind==='internal'&&editable()?button('+ Thêm tài liệu','upload-file'):''}</div>${Object.entries(groups).map(([k,files])=>`<section class="studio-panel"><h3>${({file:'Tệp tài liệu',image:'Hình ảnh',link:'Liên kết'})[k]} <small>${files.length}</small></h3><div class="vault-grid">${files.map(f=>`<article class="vault-card"><div class="file-type">${k==='link'?'↗':k==='image'?'▧':'▤'}</div><div><strong>${esc(f.title)}</strong><small>${esc(f.filename||'Liên kết ngoài')} · ${Math.ceil(f.size_bytes/1024)} KB</small><small>${date(f.created_at)}</small>${f.note?`<p>${esc(f.note)}</p>`:''}</div><a href="${esc(f.url||f.download_url)}" target="_blank" rel="noopener noreferrer">${k==='link'?'Mở liên kết':'Tải xuống'}</a>${kind==='internal'&&leader()?button('Nộp Final','final:'+f.id,'secondary'):''}</article>`).join('')||'<p class="muted">Chưa có tài liệu.</p>'}</div></section>`).join('')}`;
}
async function meetingsUI(){
  const meetings=(await get(`/projects/${state.p.id}/meetings`)).items;
  if(!state.meeting){return `<div class="studio-toolbar"><div><h3>Gặp nhau ngay trong TeamSync</h3><p>Mở phòng để họp, hoặc xem ghi chú và công việc của những phiên đã kết thúc.</p></div>${leader()?button('+ Mở cuộc họp','new-meeting'):''}</div><div class="meeting-cards">${meetings.map(m=>`<article class="studio-panel"><span class="privacy-chip">${m.status==='open'?'Đang mở':'Đã kết thúc'}</span><h3>${esc(m.title)}</h3><p>${date(m.created_at)}</p>${button(m.status==='open'?'Vào phòng họp':'Xem ghi chú','meeting:'+m.id,'secondary')}</article>`).join('')||info('Trưởng nhóm có thể tạo cuộc họp đầu tiên.')}</div>`;}
  const m=await get(`/meetings/${state.meeting}`);state.meetingData=m;
  const drafts=(await get(`/meetings/${m.id}/task-drafts`)).items;state.drafts=drafts;
  return `<div class="studio-toolbar"><div><h3>${esc(m.title)}</h3><p>${m.status==='open'?'Phòng họp nội bộ nhóm':'Cuộc họp đã kết thúc'}</p></div>${button('Danh sách cuộc họp','meeting-back','secondary')}${leader()&&m.status==='open'?button('Kết thúc & trích việc','end-meeting'):''}${leader()&&m.status==='ended'?button('Trích xuất bằng AI','extract-ai','secondary'):''}</div><div id="meeting-layout" class="${m.status==='ended'?'meeting-ended':'meeting-split'}">${m.status==='open'?`<section class="video-pane"><div id="jitsi-video"><div class="video-placeholder"><div class="camera-symbol">◉</div><h3>Sẵn sàng kết nối?</h3><p>Cho phép camera và micro sau khi tham gia.</p>${button('Tham gia video','join-video')}</div></div><p id="video-status" role="status"></p></section>`:''}<section class="studio-panel meeting-notes"><h3>Ghi chú chung</h3><p>Mỗi dòng ghi một việc cụ thể, sau đó trưởng nhóm xác nhận người làm và hạn hoàn thành.</p>${m.status==='open'?`<form id="meeting-notes-form"><label class="sr-only" for="meeting-notes">Ghi chú cuộc họp</label><textarea id="meeting-notes" name="notes" rows="10" ${m.status==='ended'?'readonly':''}>${esc(m.notes)}</textarea>${m.status==='open'?'<button type="submit">Lưu ghi chú</button>':''}</form>`:`<div class="meeting-record"><p class="preserve">${esc(m.notes||'Chưa có ghi chú được lưu.')}</p></div>`}<h3>Công việc đề xuất</h3><p class="muted">Mặc định trích theo dòng. Nút AI gửi ghi chú đã lưu đến dịch vụ AI nếu được cấu hình; mọi thẻ đều cần trưởng nhóm xác nhận.</p><div class="draft-tray">${drafts.filter(d=>d.status==='draft').map(d=>`<article class="draft-card" draggable="${leader()}" data-draft="${d.id}"><strong>${esc(d.title)}</strong>${leader()?button('Xác nhận thành task','draft:'+d.id,'secondary'):''}</article>`).join('')||'<p>Đề xuất sẽ xuất hiện sau khi kết thúc cuộc họp.</p>'}</div>${leader()&&drafts.some(d=>d.status==='draft')?'<div class="draft-drop" data-status="todo">Kéo thẻ vào đây để tạo task và gán người làm</div>':''}</section></div>`;
}
async function unifiedSummary(){
 const sections=[['progress','Tổng hợp'],['commitment','Cam kết & cảnh báo'],...(!teacher()?[['reconcile','Đối soát & phản ánh']]:[]),...(leader()?[['quality','Tự đánh giá chất lượng']]:[])];
 if(!sections.some(([key])=>key===state.summarySection))state.summarySection='progress';
 const content=state.summarySection==='commitment'?await insights():state.summarySection==='reconcile'?(state.renderReconcile?await state.renderReconcile():state.reconcile):state.summarySection==='quality'?(state.renderQuality?await state.renderQuality():state.quality):await groupReportUI();
 return `<div class="unified-summary"><nav class="summary-tabs" aria-label="Nội dung tiến độ và đóng góp">${sections.map(([key,name])=>button(name,'summary-section:'+key,state.summarySection===key?'selected':'secondary')).join('')}</nav><div class="summary-content">${content||info('Chưa có dữ liệu trong phần này.')}</div></div>`;
}
async function groupReportUI(){
 const r=await get(`/projects/${state.p.id}/report`);
 return `<div class="report-overview"><div class="report-toolbar"><div><h3>${esc(r.project.name)} · ${esc(r.assignment.title)}</h3><p>Tiến độ và đóng góp đã ghi nhận · ${date(r.generated_at)}</p></div><div class="report-exports"><a class="button" href="/api/v1/projects/${state.p.id}/report/download?format=xlsx">Xuất Excel</a><a class="button secondary" href="/api/v1/projects/${state.p.id}/report/download">Bản in / PDF</a></div></div>${reportSummary(r)}${contributionMarkup(r)}<section class="report-quality"><h3>Chất lượng theo tiêu chí</h3><div class="quality-grid">${r.quality.map(q=>`<article class="studio-panel"><h4>${esc(q.criterion.title)}</h4><span class="privacy-chip">Nhóm tự đánh giá</span><p><strong>${esc(q.level_label)}</strong></p><p>${esc(q.evaluation?.rationale||'Chưa có nhận xét chất lượng.')}</p></article>`).join('')}</div>${leader()?button('Cập nhật tự đánh giá chất lượng →','summary-section:quality','secondary'):''}</section></div>`;
}
async function insights(){
  const data=await get(`/projects/${state.p.id}/${teacher()?'analytics':'commitment'}`);
  let alerts=[],extensions=[];
  if(leader()){
    alerts=(await get(`/projects/${state.p.id}/team-alerts`)).items.filter(a=>a.status==='open');
    extensions=(await get(`/projects/${state.p.id}/extensions`)).items.filter(a=>a.status==='pending');
  }
  state.analytics=data;
  return `<div class="studio-toolbar"><div><h3>Nhìn thấy đóng góp. Chủ động hỗ trợ.</h3><p>Chỉ số hỗ trợ trao đổi trong nhóm, không tự động quy đổi thành điểm học phần.</p></div>${teacher()?`<details class="export-menu"><summary>Xuất báo cáo ↓</summary><div class="export-options">${['xlsx','csv','pdf'].map(f=>`<a href="/api/v1/projects/${state.p.id}/analytics/export?format=${f}">${f.toUpperCase()}</a>`).join('')}</div></details>`:leader()?`<a class="button" href="/api/v1/projects/${state.p.id}/report/download?format=xlsx">Xuất báo cáo ↓</a>`:''}</div><div class="metric-overview"><article><span>Thành viên</span><strong>${data.items.length}</strong></article><article><span>Công việc hoàn thành</span><strong>${state.tasks.filter(t=>t.status==='done').length}/${state.tasks.length}</strong></article><article><span>Đang chờ review</span><strong>${state.tasks.filter(t=>t.status==='review').length}</strong></article><article><span>Cam kết trung bình</span><strong>${data.items.filter(x=>x.score!==null).length?Math.round(data.items.filter(x=>x.score!==null).reduce((sum,x)=>sum+x.score,0)/data.items.filter(x=>x.score!==null).length):'—'}</strong></article></div><div class="commitment-cards">${data.items.map(x=>`<article class="studio-panel commitment-card"><div class="score-ring ${x.score<60?'low':''}"><strong>${x.score??'—'}</strong><span>/ 100</span></div><h3>${esc(x.user.full_name)}</h3><span class="privacy-chip">${x.provisional?'Chưa đủ 3 việc · tạm tính':'Đủ dữ liệu cơ bản'}</span><dl><div><dt>Đúng hạn</dt><dd>${x.metrics.on_time}/${x.metrics.eligible_tasks}</dd></div><div><dt>Yêu cầu gia hạn</dt><dd>${x.metrics.extension_requests}</dd></div><div><dt>Ngày tương tác</dt><dd>${x.metrics.chat_days+x.metrics.meeting_days}</dd></div>${teacher()?`<div><dt>Đánh giá chéo</dt><dd>${x.peer_average??'—'} / 10 (${x.peer_count} lượt)</dd></div><div><dt>Điểm học phần</dt><dd>${x.grade?.score??'Chưa chấm'} / 10</dd></div>`:''}</dl>${teacher()?`<details class="more-actions"><summary aria-label="Tùy chọn chấm điểm ${esc(x.user.full_name)}">⋯</summary><div>${button(x.grade?'Cập nhật điểm':'Chấm điểm','grade:'+x.user.id,'secondary')}</div></details>`:''}</article>`).join('')}</div><details class="studio-panel"><summary>Cách tính Commitment Index</summary><p>65 × tỷ lệ đúng hạn + 20 × max(0, 1 − số lần xin hoãn / 5) + 15 × mức tương tác.</p><p>Công việc được xét trong 90 ngày; tương tác trong 14 ngày, tối đa 5 ngày hoạt động để đạt đủ phần tương tác. Bản nộp đúng hạn đang chờ review không bị tính trễ vì hàng đợi của trưởng nhóm. Chưa có việc đủ điều kiện thì hiển thị “—”.</p></details>${alerts.length?`<section class="studio-panel"><h3>Cần gỡ rối</h3>${alerts.map(a=>`<div class="mr-row"><p>${esc(a.message)}</p>${button('Xem chi tiết','alert-view:'+a.id,'secondary')}<div class="request-actions">${button('Ping nhóm','ping:'+a.id,'secondary')}${a.task_id?button('Gia hạn','alert-extend:'+a.id,'secondary'):''}</div></div>`).join('')}</section>`:''}${extensions.length?`<section class="studio-panel"><h3>Yêu cầu gia hạn</h3>${extensions.map(e=>`<div class="mr-row"><div><strong>${esc(state.tasks.find(t=>t.id===e.task_id)?.title||("Công việc #"+e.task_id))}</strong><p>${esc(e.reason)} · ${date(e.requested_due_at)}</p></div><div class="request-actions">${button('Xem yêu cầu','extension:'+e.id,'secondary')}</div></div>`).join('')}</section>`:''}`;
}
async function peerUI(){
  const data=await get(`/projects/${state.p.id}/peer-matrix`);
  state.peer=data;
  return `<section class="peer-hero studio-panel"><span class="studio-kicker">CÙNG NHAU TỐT HƠN</span><h3>Góp ý công bằng, cụ thể.</h3><p>Đánh giá thái độ hợp tác và chất lượng sản phẩm trên thang 1–10. Giảng viên được xem kết quả; nhóm không xem được đánh giá cá nhân của nhau.</p>${data.round?`<p>Đóng lúc ${date(data.round.closes_at)}</p>${button('Mở ma trận đánh giá','open-matrix')}`:info('Chưa có đợt đánh giá đang mở. Giảng viên sẽ mở đợt vào thời điểm phù hợp.')}</section>`;
}
async function handleClick(e){
  const card=e.target.closest('[data-open-task]');
  if(card){await openTask(Number(card.dataset.openTask),card);return;}
  const target=e.target.closest('[data-do]');if(!target)return;
  const [action,value]=target.dataset.do.split(':');
  if(target.tagName==='A'&&action==='pane'){e.preventDefault();e.stopPropagation();}
  await attempt(async()=>{
    if(action==='drawer-toggle'){state.drawer=!state.drawer;await updateDrawer();}
    if(action==='drawer-close'){state.drawer=false;await updateDrawer();root.querySelector('[data-do="drawer-toggle"]')?.focus();}
    if(action==='drawer-tab'){state.drawer=true;state.drawerPane=value;await updateDrawer();root.querySelector(`[data-do="drawer-tab:${value}"]`)?.focus();}
    if(action==='pane' && ['chat','internal'].includes(value)){state.drawer=true;state.drawerPane=value;await updateDrawer();return;}
    if(action==='summary-section'){state.summarySection=value;const url=new URL(location.href);url.searchParams.set('section',value);history.replaceState({},'',url);await refresh();}
    if(action==='pane'){if(jitsi){jitsi.dispose();jitsi=null;clearInterval(attendanceTimer);}state.pane=value;const url=new URL(location.href);url.searchParams.set('pane',value);history.replaceState({},'',url);await refresh();}
    if(action==='new-task')newTask();
    if(action==='start'){const t=state.tasks.find(t=>t.id===Number(value));await api(`/tasks/${value}/start`,{version:t.version});await refresh();}
    if(action==='template'){
      const ts=(await get('/workspace-templates')).items;
      if(!ts.length){toast('Ops chưa tạo mẫu kế hoạch');return;}
      const d=dialog('Mẫu kế hoạch nhóm',`<p>Khởi tạo nhanh công việc và cột mốc từ kế hoạch do Ops chuẩn bị. Sau khi áp dụng, bạn phân công lại cho các thành viên.</p><label>Chọn mẫu<select name="template_id">${options(ts,'id','name')}</select></label><div data-template-preview></div>`,async f=>{const p=await get(`/projects/${state.p.id}`);await api(`/projects/${p.id}/apply-template`,{version:p.version,template_id:Number(f.get('template_id'))});},'Áp dụng vào bảng trống');
      const draw=()=>{const t=ts.find(x=>x.id===Number(d.querySelector('select').value));d.querySelector('[data-template-preview]').innerHTML=`<p>${esc(t.description)}</p><p><strong>${t.tasks.length} công việc · ${t.milestones.length} cột mốc</strong></p><ul>${t.milestones.map(m=>`<li>${esc(m.title)} · sau ${esc(m.offset_days)} ngày</li>`).join('')}</ul><div class="template-task-preview">${t.tasks.map(x=>`<article><strong>${esc(x.title)}</strong><span>Ngày ${esc(x.offset_days)} · ${esc(x.points||1)} điểm khối lượng · ${esc(x.milestone||'Chưa gắn cột mốc')}</span></article>`).join('')}</div><p>Hạn được tính từ ngày áp dụng và không vượt hạn bài tập. Trưởng nhóm phụ trách ban đầu, sau đó có thể phân công lại. Điểm khối lượng thể hiện độ lớn công việc, không phải điểm học tập.</p>${state.tasks.length?'<p class="task-blocked">Nhóm đang có công việc: chỉ xem mẫu. Áp dụng dành cho nhóm chưa có task để tránh trùng kế hoạch.</p>':''}`;d.querySelector('[type=submit]').disabled=!!state.tasks.length||!editable();};d.querySelector('select').onchange=draw;draw();
    }
    if(action==='upload-file')uploadDialog();
    if(action==='final')dialog('Công bố bài nộp Final',`${field('title','Tên bản nộp')}${field('note','Ghi chú')}`,async f=>api(`/projects/${state.p.id}/final-submissions`,{entry_id:Number(value),title:f.get('title'),note:f.get('note')}),'Nộp cho giảng viên');
    if(action==='review'){
      const s=(await get(`/projects/${state.p.id}/merge-requests`)).items.find(x=>x.id===Number(value));
      dialog(`Review: ${s.task.title}`,`<p>Nhánh <strong>${esc(s.branch.name)}</strong></p><a href="/tasks/${s.task.id}" target="_blank">Xem sản phẩm và lịch sử ↗</a><label>Kết quả<select name="action"><option value="accept">Merge & Pass</option><option value="return">Yêu cầu sửa</option></select></label>${field('reason','Nhận xét review')}`,async f=>api(`/submissions/${value}/review`,{version:s.task.version,action:f.get('action'),reason:f.get('reason')}),'Xác nhận review');
    }
    if(action==='new-meeting')dialog('Mở cuộc họp',field('title','Chủ đề cuộc họp'),async f=>{const m=await api(`/projects/${state.p.id}/meetings`,{title:f.get('title')});state.meeting=m.id;},'Tạo phòng');
    if(action==='meeting'){state.meeting=Number(value);await refresh();}
    if(action==='meeting-back'){jitsi?.dispose();jitsi=null;clearInterval(attendanceTimer);state.meeting=null;await refresh();}
    if(action==='join-video')await joinVideo();
    if(action==='end-meeting'){
      const notes=root.querySelector('#meeting-notes').value;
      await api(`/meetings/${state.meeting}`,{version:state.meetingData.version,notes},'PATCH');
      const latest=await get(`/meetings/${state.meeting}`);
      await api(`/meetings/${state.meeting}/end`,{version:latest.version});jitsi?.dispose();jitsi=null;clearInterval(attendanceTimer);await refresh();
    }
    if(action==='extract-ai'){await api(`/meetings/${state.meeting}/extract-tasks`,{});toast('AI đã tạo đề xuất; hãy kiểm tra trước khi xác nhận');await refresh();}
    if(action==='draft')acceptDraft(Number(value));
    if(['alert-view','ping','alert-extend'].includes(action)){
      const alert=(await get(`/projects/${state.p.id}/team-alerts`)).items.find(x=>x.id===Number(value));
      if(!alert)throw Error('Cảnh báo không còn tồn tại.');
      const task=alert.task_id?await get(`/tasks/${alert.task_id}`):null;
      const detail=`<dl class="request-detail"><div><dt>Cảnh báo</dt><dd>${esc(alert.message)}</dd></div><div><dt>Công việc</dt><dd>${esc(task?.title||'Cam kết thành viên')}</dd></div><div><dt>Phát sinh</dt><dd>${date(alert.created_at)}</dd></div>${task?`<div><dt>Hạn hiện tại</dt><dd>${date(task.due_at)}</dd></div>`:''}</dl>`;
      const actions=`<label>Hành động<select name="action" required><option value="" disabled>Chọn cách xử lý</option><option value="ping">Ping nhóm</option>${task?'<option value="extend">Gia hạn công việc</option>':''}</select></label>${task?field('due_at','Hạn mới (chỉ khi gia hạn)','datetime-local',localDue(task.due_at)):''}<label>Lý do / ghi chú<textarea name="reason" rows="3"></textarea></label>`;
      dialog('Xem cảnh báo và cách xử lý',detail+actions,async f=>{const act=f.get('action');const b={version:alert.version,action:act};if(act==='extend'){b.due_at=isoDue(f);b.reason=f.get('reason');}await api(`/team-alerts/${alert.id}/act`,b);},'Xác nhận xử lý');
      const d=document.querySelector('.studio-dialog:last-of-type'),select=d.querySelector('[name=action]');select.value=action==='alert-view'?'':action==='alert-extend'?'extend':'ping';
      const update=()=>{const due=d.querySelector('[name=due_at]'),reason=d.querySelector('[name=reason]');if(due){due.disabled=select.value!=='extend';due.required=select.value==='extend';due.closest('label').hidden=due.disabled;}reason.required=select.value==='extend';};select.onchange=update;update();
    }
    if(action==='extension'){
      const x=(await get(`/projects/${state.p.id}/extensions`)).items.find(x=>x.id===Number(value));
      if(!x)throw Error('Yêu cầu không còn tồn tại.');
      const task=await get(`/tasks/${x.task_id}`),person=activeMembers().find(m=>m.id===x.requested_by);
      dialog('Xem và quyết định gia hạn',`<dl class="request-detail"><div><dt>Công việc</dt><dd>${esc(task.title)}</dd></div><div><dt>Người đề nghị</dt><dd>${esc(person?.full_name||'Thành viên')}</dd></div><div><dt>Hạn cũ</dt><dd>${date(x.old_due_at)}</dd></div><div><dt>Hạn đề xuất</dt><dd>${date(x.requested_due_at)}</dd></div></dl><div class="request-reason"><strong>Lý do xin gia hạn</strong><p>${esc(x.reason)}</p></div><label>Quyết định<select name="action"><option value="approve">Đồng ý</option><option value="reject">Từ chối</option></select></label>${field('reason','Lý do quyết định')}`,f=>api(`/extensions/${x.id}/decide`,{version:x.version,action:f.get('action'),reason:f.get('reason')}),'Lưu quyết định');
    }
    if(action==='grade'){
      const row=state.analytics.items.find(x=>x.user.id===Number(value));
      dialog('Chấm điểm: '+row.user.full_name,`${field('score','Điểm học phần / 10','number',row.grade?.score??'', 'min="0" max="10" step="0.01"')}<label>Nhận xét và căn cứ (ít nhất 10 ký tự)<textarea name="rationale" required minlength="10">${esc(row.grade?.rationale||'')}</textarea></label><p>Giảng viên quyết định dựa trên rubric và bản Final; chỉ số cam kết không tự động quy thành điểm.</p>`,async f=>api(`/projects/${state.p.id}/grades`,{student_id:row.user.id,expected_revision:row.grade?.revision||0,score:f.get('score'),rationale:f.get('rationale')}),'Lưu quyết định');
    }
    if(action==='open-matrix')matrixDialog();
  });
}
function newTask(){
  dialog('Tạo công việc',`${field('title','Tên công việc')}<label>Mô tả<textarea name="description" rows="3"></textarea></label><label>Người phụ trách<select name="assignee_id">${options(activeMembers())}</select></label>${field('due_at','Hạn hoàn thành','datetime-local',localDue())}<label>Tiêu chí<select name="criterion_id">${options(state.p.criteria,'id','title')}</select></label>`,async f=>api(`/projects/${state.p.id}/tasks`,{title:f.get('title'),description:f.get('description'),due_at:isoDue(f),participants:[{user_id:Number(f.get('assignee_id')),role:'responsible'}],criterion_ids:[Number(f.get('criterion_id'))],points:1}),'Tạo task');
}
function uploadDialog(){
  dialog('Thêm tài liệu vào kho nháp','<label>Tệp tài liệu<input type="file" name="file"></label><label>Hoặc liên kết<input type="url" name="url" placeholder="https://…"></label>',async f=>{
    const file=f.get('file');if(file?.size){const body=new FormData();body.append('file',file);await api(`/projects/${state.p.id}/files`,body);}
    else if(f.get('url'))await api(`/projects/${state.p.id}/files`,{url:f.get('url')});else throw Error('Chọn tệp hoặc nhập liên kết');
  },'Thêm tài liệu');
}
function acceptDraft(id){
  const d=state.drafts.find(x=>x.id===id);
  dialog('Xác nhận công việc đề xuất',`<p>${esc(d.title)}</p><label>Người phụ trách<select name="assignee_id">${options(activeMembers())}</select></label>${field('due_at','Hạn hoàn thành','datetime-local',localDue())}`,async f=>api(`/task-drafts/${id}/accept`,{version:d.version,assignee_id:Number(f.get('assignee_id')),due_at:isoDue(f)}),'Thêm vào Kanban');
}
function matrixDialog(){
  const {members,items,round}=state.peer;
  dialog('Ma trận đánh giá chéo',`<div class="slider-matrix"><div class="matrix-head"><span>Thành viên</span><span>Thái độ</span><span>Chất lượng</span></div>${members.map(m=>{const value=items.find(x=>x.reviewee_id===m.id);return `<div class="matrix-row"><strong>${esc(m.full_name)}</strong>${['attitude','quality'].map(k=>`<label><span class="sr-only">${esc(m.full_name)} · ${k==='attitude'?'Thái độ':'Chất lượng'}</span><input type="range" min="1" max="10" step="1" value="${value?.[k]||5}" name="${k}_${m.id}"><output>${value?.[k]||5}</output></label>`).join('')}<label class="matrix-comment">Góp ý cụ thể<input name="comment_${m.id}" value="${esc(value?.comment||'')}"></label></div>`;}).join('')}</div>`,async f=>api(`/projects/${state.p.id}/peer-matrix`,{round_id:round.id,items:members.map(m=>({reviewee_id:m.id,attitude:Number(f.get('attitude_'+m.id)),quality:Number(f.get('quality_'+m.id)),comment:f.get('comment_'+m.id)}))},'PUT'),'Gửi đánh giá');
}
async function joinVideo(){
  const credentials=await api(`/meetings/${state.meeting}/join`,{});
  if(!window.JitsiMeetExternalAPI)await new Promise((resolve,reject)=>{
    const script=document.createElement('script');script.src=`https://${credentials.domain}/external_api.js`;script.onload=resolve;script.onerror=()=>reject(Error('Không tải được máy chủ họp. Kiểm tra kết nối hoặc cấu hình Jitsi.'));document.head.append(script);
  });
  root.querySelector('#jitsi-video').innerHTML='';
  jitsi=new window.JitsiMeetExternalAPI(credentials.domain,{roomName:credentials.room_name,parentNode:root.querySelector('#jitsi-video'),width:'100%',height:'100%',jwt:credentials.jwt||undefined,userInfo:{displayName:credentials.display_name},configOverwrite:{prejoinConfig:{enabled:true},startWithAudioMuted:true}});
  root.querySelector('#video-status').textContent=credentials.demo_public_server?'Máy chủ công khai: việc xác thực host do Jitsi quản lý.':'Phòng được xác thực bằng token có thời hạn.';
  jitsi.addListener('videoConferenceJoined',()=>{
    const pulse=()=>api(`/meetings/${state.meeting}/heartbeat`,{}).catch(()=>{});pulse();attendanceTimer=setInterval(pulse,30000);
  });
  jitsi.addListener('videoConferenceLeft',()=>{clearInterval(attendanceTimer);jitsi?.dispose();jitsi=null;});
}
// Delegated forms preserve drafts when unrelated real-time events arrive.
document.addEventListener('submit',async e=>{
  if(!root?.contains(e.target))return;
  if(e.target.id==='chat-compose'){
    e.preventDefault();const f=e.target;const send=f.querySelector('button');send.disabled=true;
    await attempt(async()=>{
      const ids=[];const file=f.elements.file.files[0];
      if(file){const body=new FormData();body.append('file',file);ids.push((await api(`/projects/${state.p.id}/files`,body)).file_id);}
      await api(`/projects/${state.p.id}/messages`,{content:f.elements.content.value,file_ids:ids,client_key:crypto.randomUUID()});if(state.drawer)await updateDrawer();else await refresh();
    });send.disabled=false;
  }
  if(e.target.id==='meeting-notes-form'){
    e.preventDefault();await attempt(async()=>{state.meetingData=await api(`/meetings/${state.meeting}`,{version:state.meetingData.version,notes:e.target.elements.notes.value},'PATCH');toast('Đã lưu ghi chú');});
  }
});
document.addEventListener('input',e=>{

});
