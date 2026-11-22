const h=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export function groupHeader(p,stats={}){
 return `<div class="group-context"><div><p class="eyebrow">KHÔNG GIAN NHÓM</p><h1>${h(p.name)}</h1><p>${h(p.assignment?.title||'')}</p></div>${stats.total!==undefined?`<div class="group-progress"><strong>${stats.done||0}/${stats.total} việc hoàn thành</strong><progress max="${stats.total||1}" value="${stats.done||0}"></progress></div>`:''}</div>`;
}
export function groupNavigation(p,active='board',discussion='',interactive=false){
 const teacher=['instructor','coordinator'].includes(p.my_role),base=`/projects/${p.id}`;
 if(['report','insights','contributions','changes'].includes(active))active='summary';
 const items=[['settings','Thành viên',`${base}?tab=settings`],['board','Bảng công việc',`${base}?tab=studio&pane=board`],...(!teacher?[['meeting','Cuộc họp',`${base}?tab=studio&pane=meeting`]]:[]),['summary','Tiến độ & đóng góp',`${base}?tab=studio&pane=summary`],['help','Yêu cầu hỗ trợ',`${base}?tab=help`],...(!teacher?[['peer','Đánh giá chéo',`${base}?tab=studio&pane=peer`]]:[]),['final','Bài nộp Final',`${base}?tab=studio&pane=final`]];
 return `<div class="group-navigation-row"><nav class="group-tabs" aria-label="Các mục trong nhóm">${items.map(([key,title,url])=>`<a href="${url}" data-group-tab="${key}" class="${active===key?'selected':''}" ${active===key?'aria-current="page"':''} ${interactive&&['board','meeting','final','summary','peer'].includes(key)?`data-do="pane:${key}"`:''}>${title}</a>`).join('')}</nav>${discussion}</div>`;
}
