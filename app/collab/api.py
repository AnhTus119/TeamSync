"""REST contract for the three modules, using existing transactional commands."""
import io, csv, json, re, secrets
from flask import request, current_app, send_file
from . import bp
from .services import *
from ..models import ProjectTemplate, TaskDependency, Milestone, POINTS
from ..m06_projects.academic_api import add_group_member, set_task_relations
from ..common.storage import save_upload, download, root


@bp.route('/me/preferences', methods=['GET', 'PATCH'])
@command()
def preferences():
    # Kept for API compatibility: the product now uses a fixed light NEU theme.
    if request.method == 'PATCH':
        b = json_body()
        need(b.get('theme') == 'light' and b.get('accent', '#C8102E').upper() == '#C8102E',
             message='Giao diện chỉ hỗ trợ nền sáng và màu đỏ NEU')
    return {'theme':'light','accent':'#C8102E'}


@bp.route('/workspace-templates', methods=['GET', 'POST'])
@command()
def templates():
    if request.method == 'GET':
        return {'items': [x.to_dict() for x in ProjectTemplate.query.order_by(ProjectTemplate.id)]}
    need(current_user().role == 'admin', 'FORBIDDEN', 'Ops quản lý mẫu hệ thống', 403)
    b = json_body()
    items = b.get('tasks', [])
    need(isinstance(items, list) and len(items) <= 40)
    validate_template_tasks(items, b.get('milestones', []))
    p = ProjectTemplate(name=textval(b, 'name'), description=textval(b, 'description', default='Mẫu dự án'),
                        milestones_json=json.dumps(validate_milestones(b.get('milestones', [])), ensure_ascii=False), tasks_json=json.dumps(items, ensure_ascii=False))
    db.session.add(p)
    db.session.flush()
    return p.to_dict(), 201


@bp.patch('/workspace-templates/<int:tid>')
@command()
def template_update(tid):
    need(current_user().role == 'admin', 'FORBIDDEN', 'Ops quản lý mẫu hệ thống', 403)
    t = get(ProjectTemplate, tid)
    b = json_body()
    if 'name' in b:
        t.name = textval(b, 'name')
    if 'description' in b:
        t.description = textval(b, 'description')
    if 'tasks' in b:
        need(isinstance(b['tasks'], list) and len(b['tasks']) <= 40)
        validate_template_tasks(b['tasks'], b.get('milestones', t.milestones))
        t.tasks_json = json.dumps(b['tasks'], ensure_ascii=False)
    if 'milestones' in b:
        validate_template_tasks(b.get('tasks', t.tasks), b['milestones'])
        t.milestones_json = json.dumps(validate_milestones(b['milestones']), ensure_ascii=False)
    return t.to_dict()


@bp.post('/assignments/<int:aid>/teams/generate')
@command(idempotent=True)
def generate_teams(aid):
    a = assignment(aid, staff=True)
    state(a, ['draft','published','active'])
    from .organization import allocate_groups
    return allocate_groups(a,json_body())


@bp.post('/projects/<int:pid>/apply-template')
@command(idempotent=True)
def apply_template(pid):
    p = team(pid, leader=True, mutable=True)
    version(p)
    need(not Task.query.filter_by(project_id=pid).first(), 'TEMPLATE_ALREADY_APPLIED', 'Chỉ áp dụng mẫu khi nhóm chưa có công việc', 409)
    a = get(Assignment, p.assignment_id)
    t = get(ProjectTemplate, integer(json_body().get('template_id')))
    criterion = Criterion.query.filter_by(policy_id=a.published_policy_id).first()
    need(criterion, message='Cần công bố tiêu chí trước')
    need(a.due_at > now(), message='Bài tập đã hết hạn, không thể khởi tạo mẫu')
    milestones = {}
    for item in t.milestones:
        due = min(now()+timedelta(days=integer(item.get('offset_days',7),1,365)), a.due_at)
        m = Milestone(project_id=pid,title=item['title'][:200],due_at=due,due_date=due.date(),status='open')
        db.session.add(m)
        db.session.flush()
        milestones[item['title']] = m.id
    for item in t.tasks:
        points = integer(item.get('points',1))
        need(points in POINTS, message='Điểm khối lượng mẫu phải là 1, 2, 3 hoặc 5')
        milestone = item.get('milestone','')
        need(not milestone or milestone in milestones, message='Cột mốc công việc không có trong mẫu')
        due = min(now()+timedelta(days=integer(item.get('offset_days',7),1,365)), a.due_at)
        task = Task(project_id=pid, title=item['title'][:200], status='todo', due_at=due,
                    original_due_at=due, created_by=current_user().id, points=points, milestone_id=milestones.get(milestone))
        db.session.add(task)
        db.session.flush()
        set_task_relations(task, {'participants':[{'user_id':current_user().id, 'role':'responsible'}],
                                  'criterion_ids':[criterion.id]})
    p.template_id = t.id
    audit('template.applied',p,pid=pid)
    return {'created_tasks': len(t.tasks), 'created_milestones': len(milestones), 'version': p.version}


@bp.get('/projects/<int:pid>/gantt')
@command()
def gantt(pid):
    project(pid)
    tasks = Task.query.filter_by(project_id=pid).order_by(Task.id).all()
    return {'items': [{**task_summary(t), 'start_at':iso(t.created_at),
                      'dependencies':[d.depends_on_id for d in TaskDependency.query.filter_by(task_id=t.id)]} for t in tasks]}


@bp.post('/tasks/<int:tid>/move')
@command()
def move_task(tid):
    t = task(tid, mutable=True)
    team(t.project_id)
    participant(t)
    version(t)
    target = json_body().get('status')
    need(target in ('todo','in_progress') and t.status in ('todo','in_progress'),
         'MR_REQUIRED', 'Gửi Merge Request và chờ trưởng nhóm duyệt để hoàn thành',409)
    need(not BranchMergeRequest.query.join(TaskBranch).filter(TaskBranch.task_id==tid).first(),
         'INVALID_TRANSITION','Công việc đã có bản nộp, tiếp tục sửa trên nhánh',409)
    t.status = target
    audit('task.moved',t,pid=t.project_id)
    return task_summary(t)


@bp.route('/tasks/<int:tid>/branches', methods=['GET','POST'])
@command()
def branches(tid):
    t = task(tid, mutable=request.method=='POST')
    team(t.project_id)
    if request.method == 'GET':
        return {'items': rows(TaskBranch, task_id=tid)}
    participant(t)
    need(t.status in ('todo','in_progress'), 'INVALID_TRANSITION','Task đang duyệt hoặc đã hoàn thành',409)
    b = json_body()
    name = textval(b,'name')
    need(re.fullmatch(r'[a-zA-Z0-9/_-]{2,100}',name),message='Tên nhánh 2–100 ký tự: chữ, số, /, -, _')
    branch = TaskBranch(task_id=tid, author_id=current_user().id, name=name)
    db.session.add(branch)
    db.session.flush()
    audit('branch.created',branch,pid=t.project_id)
    return dto(branch),201


@bp.get('/projects/<int:pid>/merge-requests')
@command()
def merge_requests(pid):
    team(pid)
    pairs = db.session.query(BranchMergeRequest,TaskBranch,TaskSubmission).join(
        TaskBranch,TaskBranch.id==BranchMergeRequest.branch_id).join(
        TaskSubmission,TaskSubmission.id==BranchMergeRequest.submission_id).join(Task,Task.id==TaskBranch.task_id).filter(Task.project_id==pid).all()
    return {'items':[{'id':s.id,'branch':dto(b),'submission':dto(s),'task':task_summary(get(Task,s.task_id))} for mr,b,s in pairs]}


@bp.route('/projects/<int:pid>/messages', methods=['GET','POST'])
@command()
def messages(pid):
    team(pid,mutable=request.method=='POST')
    if request.method=='GET':
        after = request.args.get('after',0,type=int)
        need(after is not None and after >= 0)
        entries = Message.query.filter(Message.project_id==pid, Message.id>after).order_by(Message.id).limit(100).all()
        return {'items':[message_dto(m) for m in entries], 'next_cursor':entries[-1].id if entries else after}
    return message_dto(send_message(pid,json_body())),201


@bp.post('/projects/<int:pid>/files')
@command()
def upload_file(pid):
    team(pid,mutable=True)
    used = db.session.query(db.func.coalesce(db.func.sum(StoredFile.size_bytes),0)).filter_by(project_id=pid).scalar()
    limit = current_app.config['MAX_PROJECT_BYTES']
    need(used < limit,'QUOTA_EXCEEDED','Kho nhóm đã đầy',413)
    if 'file' in request.files:
        info = save_upload(request.files['file'])
        if used+info['size_bytes'] > limit:
            (root()/info['storage_key']).unlink(missing_ok=True)
            need(False,'QUOTA_EXCEEDED','Vượt dung lượng nhóm',413)
        f = StoredFile(project_id=pid,uploaded_by=current_user().id,kind='file',**info)
    else:
        url = textval(json_body(),'url')
        need(valid_url(url),message='Chỉ hỗ trợ link HTTP/HTTPS không chứa mật khẩu')
        f = StoredFile(project_id=pid,uploaded_by=current_user().id,kind='link',url=url)
    db.session.add(f)
    db.session.flush()
    e = add_entry(pid,f)
    return {**entry_dto(e),'file_id':f.id},201


@bp.get('/projects/<int:pid>/vaults/<kind>')
@command()
def list_vault(pid,kind):
    project(pid)
    need(kind in ('internal','final'))
    if kind=='internal':
        team(pid)
    v = Vault.query.filter_by(project_id=pid,kind=kind).first()
    return {'kind':kind,'items':[entry_dto(e) for e in VaultEntry.query.filter_by(vault_id=v.id).order_by(VaultEntry.id.desc())] if v else []}


@bp.post('/projects/<int:pid>/final-submissions')
@command(idempotent=True)
def final_submit(pid):
    p = team(pid,leader=True,mutable=True)
    b = json_body()
    source = get(VaultEntry,integer(b.get('entry_id')))
    v = get(Vault,source.vault_id)
    need(v.project_id==pid and v.kind=='internal','INVALID_FILE_SCOPE','Chọn tài liệu nội bộ của nhóm',403)
    e = add_entry(pid,get(StoredFile,source.file_id),'final',textval(b,'title'),textval(b,'note',default='Nộp bài hoàn thiện'))
    audit('vault.final_submitted',e,pid=pid)
    # Final submission notification is deliberately visible to instructors.
    recipients = [x.user_id for x in CourseEnrollment.query.filter(
        CourseEnrollment.course_id==get(Assignment,p.assignment_id).course_id,
        CourseEnrollment.role.in_(STAFF),CourseEnrollment.status=='active')]
    db.session.add(OutboxEvent(event_type='vault.final',aggregate_id=e.id,
        payload={'recipients':recipients,'path':f'/projects/{pid}?tab=studio&pane=final','subject':e.title}))
    return entry_dto(e),201


@bp.get('/vault-entries/<int:eid>/download')
def vault_download(eid):
    need(current_user() is not None,'UNAUTHORIZED','Bạn cần đăng nhập',401)
    e = get(VaultEntry,eid)
    v = get(Vault,e.vault_id)
    project(v.project_id)
    if v.kind=='internal':
        team(v.project_id)
    f = get(StoredFile,e.file_id)
    if f.kind=='link':
        return {'data':{'url':f.url}}
    return download(f.storage_key,f.original_filename,f.sha256)


@bp.route('/projects/<int:pid>/meetings',methods=['GET','POST'])
@command()
def meetings(pid):
    team(pid,leader=request.method=='POST',mutable=request.method=='POST')
    if request.method=='GET':
        return {'items':rows(Meeting,project_id=pid)}
    m = Meeting(project_id=pid,host_id=current_user().id,title=textval(json_body(),'title'),room_name='ts-'+secrets.token_hex(20))
    db.session.add(m)
    db.session.flush()
    audit('meeting.created',m,pid=pid)
    return dto(m),201


@bp.route('/meetings/<int:mid>',methods=['GET','PATCH'])
@command()
def meeting_detail(mid):
    m = get(Meeting,mid,lock=request.method!='GET')
    team(m.project_id,mutable=request.method!='GET')
    if request.method=='PATCH':
        state(m,['open'])
        version(m)
        m.notes = textval(json_body(),'notes',minimum=0)
    return dto(m)


@bp.post('/meetings/<int:mid>/join')
@command()
def meeting_join(mid):
    m = get(Meeting,mid)
    team(m.project_id,mutable=True)
    state(m,['open'])
    from .identity import meeting_credentials
    return meeting_credentials(m)


@bp.post('/meetings/<int:mid>/heartbeat')
@command()
def heartbeat(mid):
    m = get(Meeting,mid)
    team(m.project_id,mutable=True)
    state(m,['open'])
    a = MeetingAttendance.query.filter_by(meeting_id=mid,user_id=current_user().id).first()
    at = now()
    if not a:
        a = MeetingAttendance(meeting_id=mid,user_id=current_user().id,joined_at=at,last_seen_at=at)
        db.session.add(a)
    else:
        gap = max(0,(at-a.last_seen_at).total_seconds())
        a.active_seconds += int(min(45,gap)) if gap <= 90 else 0
        a.last_seen_at = at
    return {'active_seconds':a.active_seconds or 0}


@bp.post('/meetings/<int:mid>/end')
@command()
def meeting_end(mid):
    m = get(Meeting,mid,lock=True)
    team(m.project_id,leader=True,mutable=True)
    version(m)
    state(m,['open'])
    m.status,m.ended_at = 'ended',now()
    return {**dto(m),'drafts':extract_drafts(m)}


@bp.get('/meetings/<int:mid>/task-drafts')
@command()
def meeting_drafts(mid):
    m = get(Meeting,mid)
    team(m.project_id)
    return {'items':rows(MeetingTaskDraft,meeting_id=mid),'provider':'local-rule-based','ai_enabled':False}


@bp.post('/task-drafts/<int:did>/accept')
@command(idempotent=True)
def accept_draft(did):
    d = get(MeetingTaskDraft,did,lock=True)
    m = get(Meeting,d.meeting_id)
    p = team(m.project_id,leader=True,mutable=True)
    version(d)
    state(d,['draft'])
    b = json_body()
    uid = integer(b.get('assignee_id'))
    need(membership(p.id,uid),'INVALID_PARTICIPANT','Người làm phải thuộc nhóm')
    due = timestamp(b.get('due_at'))
    need(now() < due <= get(Assignment,p.assignment_id).due_at,message='Hạn task phải nằm trong thời hạn đề bài')
    t = Task(project_id=p.id,title=d.title,description=d.source_line,created_by=current_user().id,
             status='todo',due_at=due,original_due_at=due,points=1)
    db.session.add(t)
    db.session.flush()
    criteria = b.get('criterion_ids') or [c.id for c in Criterion.query.filter_by(policy_id=get(Assignment,p.assignment_id).published_policy_id).limit(1)]
    set_task_relations(t,{'participants':[{'user_id':uid,'role':'responsible'}],'criterion_ids':criteria})
    d.status,d.task_id = 'accepted',t.id
    audit('meeting.task_accepted',d,pid=p.id)
    return task_summary(t),201


@bp.post('/tasks/<int:tid>/extensions')
@command(idempotent=True)
def request_extension(tid):
    t = task(tid,mutable=True)
    team(t.project_id)
    participant(t)
    need(t.status!='done','INVALID_TRANSITION','Công việc đã hoàn thành',409)
    need(not DeadlineExtension.query.filter_by(task_id=tid,requested_by=current_user().id,status='pending').first(),
         'EXTENSION_EXISTS','Đã có yêu cầu đang chờ',409)
    b=json_body()
    due=timestamp(b.get('due_at'))
    a=get(Assignment,get(Project,t.project_id).assignment_id)
    need(t.due_at < due <= a.due_at,message='Hạn mới phải sau hạn hiện tại và không vượt hạn đề bài')
    x=DeadlineExtension(task_id=tid,requested_by=current_user().id,reason=textval(b,'reason'),old_due_at=t.due_at,requested_due_at=due)
    db.session.add(x)
    db.session.flush()
    audit('extension.requested',x,pid=t.project_id,reason=x.reason)
    return dto(x),201


@bp.get('/projects/<int:pid>/extensions')
@command()
def list_extensions(pid):
    team(pid)
    return {'items':[dto(x) for x in DeadlineExtension.query.join(Task).filter(Task.project_id==pid).order_by(DeadlineExtension.id.desc())]}


@bp.post('/extensions/<int:eid>/decide')
@command()
def decide_extension(eid):
    e=get(DeadlineExtension,eid,lock=True)
    t=task(e.task_id,mutable=True)
    team(t.project_id,leader=True)
    version(e)
    state(e,['pending'])
    b=json_body()
    need(b.get('action') in ('approve','reject'))
    need(t.status!='done','INVALID_TRANSITION','Task đã hoàn thành',409)
    e.status='approved' if b['action']=='approve' else 'rejected'
    e.decided_by,e.decided_at,e.decision_reason=current_user().id,now(),textval(b,'reason')
    if e.status=='approved':
        need(t.due_at==e.old_due_at,'VERSION_CONFLICT','Hạn công việc đã đổi',409)
        t.due_at=e.requested_due_at
        t.version+=1
    audit('extension.'+e.status,e,pid=t.project_id,reason=e.decision_reason)
    return dto(e)


@bp.get('/projects/<int:pid>/commitment')
@command()
def commitment_index(pid):
    p=project(pid)
    values=[commitment(pid,m.user_id) for m in AssignmentMembership.query.filter_by(project_id=pid,status='active')]
    return {'items':values,'generated_at':iso(now()),'grade_automation':False}


@bp.get('/projects/<int:pid>/team-alerts')
@command()
def alerts(pid):
    team(pid,leader=True)
    return {'items':rows(TeamAlert,project_id=pid)}


@bp.post('/team-alerts/<int:aid>/act')
@command()
def alert_action(aid):
    a=get(TeamAlert,aid,lock=True)
    team(a.project_id,leader=True,mutable=True)
    state(a,['open'])
    version(a)
    b=json_body()
    if b.get('action')=='ping':
        need(not a.last_ping_at or now()-a.last_ping_at>=timedelta(hours=1),'RATE_LIMITED','Chỉ nhắc một lần mỗi giờ',429)
        send_message(a.project_id,{'content':f'Nhắc tiến độ: {a.message}', 'client_key':uuid.uuid4().hex},system=True)
        a.last_ping_at=now()
    elif b.get('action')=='extend':
        need(a.task_id,'TASK_REQUIRED','Cảnh báo này cần xem công việc cụ thể')
        t=task(a.task_id,mutable=True)
        need(t.status!='done','INVALID_TRANSITION','Task đã hoàn thành',409)
        due=timestamp(b.get('due_at'))
        need(t.due_at < due <= get(Assignment,get(Project,a.project_id).assignment_id).due_at)
        reason=textval(b,'reason')
        db.session.add(DeadlineExtension(task_id=t.id,requested_by=current_user().id,reason=reason,
            old_due_at=t.due_at,requested_due_at=due,status='approved',decided_by=current_user().id,
            decided_at=now(),decision_reason=reason))
        t.due_at=due
        t.version+=1
    else:
        need(False,message='Hành động không hợp lệ')
    audit('alert.acted',a,pid=a.project_id)
    return dto(a)


def matrix_dto(row):
    result=dto(row,omit=('attitude10','quality10'))
    result['attitude']=row.attitude10 or row.attitude*2
    result['quality']=row.quality10 or row.quality*2
    return result


@bp.route('/projects/<int:pid>/peer-matrix',methods=['GET','PUT'])
@command()
def peer_matrix(pid):
    p=project(pid)
    rounds=PeerRound.query.filter_by(assignment_id=p.assignment_id,status='open').order_by(PeerRound.id.desc()).all()
    r=next((x for x in rounds if x.opens_at<=now()<=x.closes_at),None)
    members=AssignmentMembership.query.filter_by(project_id=pid,status='active').all()
    if request.method=='GET':
        team(pid)
        return {'round':dto(r) if r else None,'members':[user_brief(x.user_id) for x in members if x.user_id!=current_user().id],
            'items':[matrix_dto(x) for x in MatrixReview.query.filter_by(project_id=pid,round_id=r.id,reviewer_id=current_user().id)] if r else [], 'scale_max':10}
    team(pid,mutable=True)
    need(r,'ROUND_CLOSED','Không có đợt đánh giá đang mở',409)
    b=json_body()
    need(b.get('round_id')==r.id,'ROUND_CLOSED','Đợt đánh giá đã thay đổi',409)
    items=b.get('items')
    expected={x.user_id for x in members if x.user_id!=current_user().id}
    need(isinstance(items,list) and len(items)==len(expected))
    need({x.get('reviewee_id') for x in items if isinstance(x,dict)}==expected,'INVALID_PARTICIPANT','Cần đánh giá đủ các thành viên khác')
    for item in items:
        uid=integer(item.get('reviewee_id'))
        row=MatrixReview.query.filter_by(round_id=r.id,project_id=pid,reviewer_id=current_user().id,reviewee_id=uid).first()
        if not row:
            row=MatrixReview(round_id=r.id,project_id=pid,reviewer_id=current_user().id,reviewee_id=uid)
            db.session.add(row)
        row.attitude10=integer(item.get('attitude'),1,10)
        row.quality10=integer(item.get('quality'),1,10)
        # Retain legacy columns for older reporting consumers, without losing 10-point precision.
        row.attitude=max(1,min(5,(row.attitude10+1)//2))
        row.quality=max(1,min(5,(row.quality10+1)//2))
        row.comment=textval(item,'comment',minimum=0,default='')
    audit('peer.matrix_saved',p,pid=pid)
    return {'saved':len(items)}


@bp.post('/assignments/<int:aid>/peer-matrix/open')
@command(idempotent=True)
def open_matrix(aid):
    a=assignment(aid,staff=True)
    b=json_body()
    end=timestamp(b.get('closes_at'))
    need(now()<end,message='Thời điểm đóng phải sau hiện tại')
    need(not PeerRound.query.filter_by(assignment_id=aid,status='open').filter(PeerRound.closes_at>now()).first(),
         'ROUND_EXISTS','Đã có đợt đánh giá đang mở',409)
    r=PeerRound(assignment_id=aid,title='Đánh giá thái độ và chất lượng',opens_at=now(),closes_at=end,status='open',
                criteria_json=[{'code':'attitude','max':10},{'code':'quality','max':10}])
    db.session.add(r)
    db.session.flush()
    return dto(r),201


def analytics_data(pid):
    p=project(pid,staff=True)
    latest=PeerRound.query.filter_by(assignment_id=p.assignment_id).order_by(PeerRound.id.desc()).first()
    peers=MatrixReview.query.filter_by(project_id=pid,round_id=latest.id).all() if latest else []
    result=[]
    for m in AssignmentMembership.query.filter_by(project_id=pid,status='active'):
        ci=commitment(pid,m.user_id)
        received=[x for x in peers if x.reviewee_id==m.user_id]
        peer=round(sum(((x.attitude10 or x.attitude*2)+(x.quality10 or x.quality*2))/2 for x in received)/len(received),2) if received else None
        grade=AcademicGrade.query.filter_by(project_id=pid,student_id=m.user_id).order_by(AcademicGrade.revision.desc()).first()
        result.append({**ci,'peer_average':peer,'peer_count':len(received),'grade':dto(grade) if grade else None})
    return {'project':{'id':p.id,'name':p.name},'items':result,'round':dto(latest) if latest else None,
            'peer_responses':[matrix_dto(x) for x in peers], 'grade_automation':False}


@bp.get('/projects/<int:pid>/analytics')
@command()
def analytics(pid):
    return analytics_data(pid)


@bp.get('/projects/<int:pid>/analytics/export')
def analytics_export(pid):
    need(current_user() is not None,'UNAUTHORIZED','Bạn cần đăng nhập',401)
    data=analytics_data(pid)
    fmt=request.args.get('format','xlsx')
    need(fmt in ('csv','xlsx','pdf'))
    headers=['Thành viên','Commitment Index','Dữ liệu tạm tính','Số việc đánh giá','Đánh giá chéo / 10','Số lượt đánh giá','Điểm học phần / 10','Nhận xét giảng viên']
    def safe(v):
        s=str(v) if v is not None else ''
        return "'"+s if s.startswith(('=','+','-','@','\t','\r','\n')) else s
    values=[[safe(x['user']['full_name']),x['score'],'Có' if x['provisional'] else 'Không',x['metrics']['eligible_tasks'],x['peer_average'],x['peer_count'],float(x['grade']['score']) if x['grade'] else None,safe(x['grade']['rationale']) if x['grade'] else ''] for x in data['items']]
    out=io.BytesIO()
    if fmt=='csv':
        s=io.StringIO()
        w=csv.writer(s)
        w.writerow(headers)
        w.writerows(values)
        out.write(s.getvalue().encode('utf-8-sig'))
        mime='text/csv'
    elif fmt=='xlsx':
        from openpyxl import Workbook
        from openpyxl.styles import Font,PatternFill
        wb=Workbook(); ws=wb.active; ws.title='Cam kết và đánh giá'
        ws.append(headers)
        for row in values: ws.append(row)
        for c in ws[1]: c.font=Font(bold=True,color='FFFFFF'); c.fill=PatternFill('solid',fgColor='C8102E')
        ws.freeze_panes='A2'; ws.auto_filter.ref=ws.dimensions
        for col in ws.columns: ws.column_dimensions[col[0].column_letter].width=26
        ws.append(['Chỉ số hỗ trợ phản hồi, không tự động quy đổi thành điểm học phần.'])
        wb.save(out); mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    else:
        from .reports import render_pdf
        render_pdf(out,data,headers,values)
        mime='application/pdf'
    out.seek(0)
    return send_file(out,as_attachment=True,download_name=f'TeamSync-{pid}.{fmt}',mimetype=mime)


@bp.post('/meetings/<int:mid>/extract-tasks')
@command(idempotent=True)
def ai_meeting_tasks(mid):
    m=get(Meeting,mid,lock=True)
    team(m.project_id,leader=True,mutable=True)
    need(m.status=='ended','MEETING_OPEN','Kết thúc cuộc họp trước khi trích xuất bằng AI',409)
    from .meeting_ai import extract_with_ai
    return extract_with_ai(m)


@bp.post('/projects/<int:pid>/grades')
@command(idempotent=True)
def save_grade(pid):
    p=project(pid,staff=True,mutable=True)
    b=json_body()
    uid=integer(b.get('student_id'))
    need(membership(pid,uid),'INVALID_PARTICIPANT','Sinh viên phải đang thuộc nhóm')
    latest=AcademicGrade.query.filter_by(project_id=pid,student_id=uid).order_by(AcademicGrade.revision.desc()).first()
    previous=latest.revision if latest else 0
    need(b.get('expected_revision')==previous,'VERSION_CONFLICT','Điểm đã thay đổi, tải lại trước khi lưu',409)
    final=Vault.query.filter_by(project_id=pid,kind='final').first()
    need(final and VaultEntry.query.filter_by(vault_id=final.id).first(),
         'FINAL_REQUIRED','Cần bản nộp Final làm căn cứ trước khi chấm điểm',409)
    grade=AcademicGrade(project_id=pid,student_id=uid,assessor_id=current_user().id,
        revision=previous+1,score=decimal(b.get('score'),0,10),rationale=textval(b,'rationale',minimum=10),
        context_json={'commitment':commitment(pid,uid),'final_entry_ids':[e.id for e in VaultEntry.query.filter_by(vault_id=final.id)]})
    db.session.add(grade)
    db.session.flush()
    audit('grade.recorded',grade,pid=pid)
    return dto(grade),201


def validate_template_tasks(items, milestones):
    validate_milestones(milestones)
    names={m['title'] for m in milestones}
    need(len(names)==len(milestones), message='Tên cột mốc trong mẫu không được trùng')
    need(isinstance(items,list) and len(items)<=40)
    for item in items:
        need(isinstance(item,dict))
        textval(item,'title')
        integer(item.get('offset_days',7),1,365)
        need(integer(item.get('points',1)) in POINTS, message='Điểm khối lượng phải là 1, 2, 3 hoặc 5')
        need(not item.get('milestone') or item['milestone'] in names, message='Tên cột mốc của công việc phải có trong danh sách cột mốc')


def validate_milestones(items):
    need(isinstance(items, list) and len(items) <= 40)
    for item in items:
        need(isinstance(item, dict))
        textval(item, 'title')
        integer(item.get('offset_days', 7), 1, 365)
    return items


@bp.delete('/workspace-templates/<int:tid>')
@command()
def template_delete(tid):
    need(current_user().role == 'admin', 'FORBIDDEN', 'Ops quản lý mẫu hệ thống', 403)
    t = get(ProjectTemplate, tid)
    # Detach the reusable definition; preserve all existing project data.
    Project.query.filter_by(template_id=tid).update({'template_id': None})
    db.session.delete(t)
    return {'deleted': True}


@bp.patch('/me/profile')
@command()
def update_profile():
    u = current_user()
    u.full_name = textval(json_body(), 'full_name')
    return u.to_dict()


@bp.post('/me/password')
@command()
def update_password():
    from ..m20_accounts.api import _check_password
    u = current_user()
    b = json_body()
    need(u.check_password(textval(b, 'old_password')), message='Mật khẩu hiện tại chưa đúng')
    raw = textval(b, 'new_password')
    _check_password(raw)
    u.set_password(raw)
    return {'saved': True}
