"""Focused student workspace: group decisions, anonymous aggregates and reports."""
import math, secrets
from flask import Blueprint, request, send_file, render_template, redirect
from .core import *
from .collaboration import group_report, mentor_ids, complaint_dto
from ..models.workflow import GroupDeparture, ReportSnapshot, DeadlineReminder, GroupDelivery
from ..models.teamwork import Meeting, MatrixReview
from ..m06_projects.academic_api import project_dto, add_group_member
bp=Blueprint('workflow',__name__,url_prefix='/api/v1/workflow')
from . import evidence as _evidence
_evidence.register(bp)
from . import schedule as _schedule
_schedule.register(bp)

def members(pid):
    return AssignmentMembership.query.filter_by(project_id=pid,status='active').all()

def teacher(p):
    need(current_user().id in mentor_ids(p.id),'FORBIDDEN','Cần giảng viên phụ trách lớp',403)

def leader(p):
    m=membership(p.id)
    need(m and m.role=='leader','FORBIDDEN','Cần quyền trưởng nhóm',403)

def announce(p,event,subject,recipients=None,path=None):
    db.session.add(OutboxEvent(event_type=event,aggregate_id=p.id,payload={'recipients':recipients if recipients is not None else [m.user_id for m in members(p.id)],'subject':subject,'path':path or f'/projects/{p.id}'}))

@bp.get('/home')
@command()
def home():
    es=CourseEnrollment.query.filter_by(user_id=current_user().id,status='active').all()
    courses=[]; tasks=[]; pending=[]
    for e in es:
        c=get(CourseOffering,e.course_id)
        a=Assignment.query.filter_by(course_id=c.id).first()
        ps=Project.query.filter_by(assignment_id=a.id).all() if a and (not a.is_hidden or e.role in STAFF) else []
        if e.role=='student':ps=[p for p in ps if membership(p.id)]
        cards=[]
        for p in ps:
            ts=Task.query.filter_by(project_id=p.id).all()
            cards.append({'id':p.id,'name':p.name,'status':p.status,'total':len(ts),'done':sum(t.status=='done' for t in ts),'late':sum(t.status not in ('done','review') and t.due_at<now() for t in ts),'help':HelpRequest.query.filter(HelpRequest.project_id==p.id,HelpRequest.status.in_(['submitted','under_review'])).count()})
            if e.role=='student':
                tasks.extend([{**task_summary(t),'project_name':p.name,'course_title':c.title,'course_id':c.id} for t in ts if TaskParticipant.query.filter_by(task_id=t.id,user_id=current_user().id).first() or (membership(p.id).role=='leader' and t.status=='review')])
            elif p.status=='pending':pending.append({'id':p.id,'name':p.name,'course_title':c.title})
        courses.append({**dto(c),'my_role':e.role,'assignment':dto(a) if a and (not a.is_hidden or e.role in STAFF) else None,'groups':cards})
    return {'courses':courses,'tasks':tasks,'pending_groups':pending,**_evidence.dashboard_data()}

@bp.post('/projects/<int:pid>/approval')
@command(idempotent=True)
def approval(pid):
    p=project(pid,mutable=True);b=json_body();version(p)
    action=b.get('action')
    if action=='submit':
        leader(p);state(p,['draft']);a=get(Assignment,p.assignment_id)
        need(a.status=='active',message='Bài tập chưa được công bố')
        need(a.group_min<=len(members(pid))<=a.group_max,message='Chưa đủ thành viên xác nhận')
        p.status='pending';announce(p,'group.approval','Nhóm đang chờ phê duyệt',mentor_ids(pid))
    else:
        teacher(p);state(p,['pending']);need(action in ('accept','return'))
        p.status='active' if action=='accept' else 'draft'
        reason=textval(b,'reason') if action=='return' else 'Nhóm đã được phê duyệt'
        announce(p,'group.approved',reason)
    audit('group.approval',p,pid=pid,reason=b.get('reason',action));return project_dto(p)

@bp.post('/assignments/<int:aid>/groups')
@command(idempotent=True)
def teacher_group(aid):
    a=assignment(aid,staff=True);b=json_body()
    ids=b.get('user_ids');need(isinstance(ids,list) and a.group_min<=len(ids)<=a.group_max)
    need(len(set(ids))==len(ids));[integer(uid) for uid in ids]
    lid=integer(b.get('leader_id'));need(lid in ids)
    p=Project(workspace_id=get(CourseOffering,a.course_id).workspace_id,name=textval(b,'name'),description='',created_by=current_user().id,assignment_id=aid,mode='academic',status='active')
    db.session.add(p);db.session.flush()
    for uid in ids:add_group_member(p,uid,'leader' if uid==lid else 'member');db.session.flush()
    audit('group.assigned',p,pid=p.id);return project_dto(p),201

@bp.post('/projects/<int:pid>/readmit')
@command(idempotent=True)
def readmit(pid):
    p=project(pid,mutable=True);teacher(p);version(p);b=json_body()
    reason=textval(b,'reason');add_group_member(p,integer(b.get('user_id')),'member')
    audit('group.readmitted',p,pid=pid,reason=reason);return project_dto(p)

def departure_dto(x):
    return {**dto(x),'user':user_brief(x.user_id),'successor':user_brief(x.successor_id) if x.successor_id else None,'yes':sum(v is True for v in x.votes.values())}

def finish_departure(p,x):
    m=membership(p.id,x.user_id);need(m,'MEMBERSHIP_CHANGED','Thành viên không còn trong nhóm',409)
    remaining=[v for v in members(p.id) if v.user_id!=x.user_id]
    m.status='left';m.left_at=now()
    if x.leader_exit:
        if remaining:
            successor=secrets.choice(remaining);successor.role='leader';x.successor_id=successor.user_id
        else:p.status='archived'
    x.status='approved';x.resolved_at=now();p.version+=1
    # Open work stays visible; reassignment is explicit, submitted rosters stay unchanged.
    audit('group.departure_approved',x,pid=p.id,reason=x.reason)
    announce(p,'group.departure',f'{user_brief(x.user_id)["full_name"]} đã rời nhóm')

@bp.route('/projects/<int:pid>/departures',methods=['GET','POST'])
@command(idempotent=True)
def departures(pid):
    p=project(pid,mutable=request.method=='POST')
    if request.method=='GET':return {'items':[departure_dto(x) for x in GroupDeparture.query.filter_by(project_id=pid).order_by(GroupDeparture.id.desc())]}
    m=membership(pid);need(m,'FORBIDDEN','Chỉ thành viên nhóm gửi yêu cầu',403)
    need(not GroupDeparture.query.filter_by(project_id=pid,status='pending').first(),'PENDING_REQUEST','Nhóm đang có yêu cầu rời cần xử lý',409)
    others=[v.user_id for v in members(pid) if v.user_id!=m.user_id]
    x=GroupDeparture(project_id=pid,user_id=m.user_id,reason=textval(json_body(),'reason'),leader_exit=m.role=='leader',electorate=others,votes={},threshold=math.ceil(len(others)/2))
    db.session.add(x);db.session.flush();audit('group.departure_requested',x,pid=pid,reason=x.reason)
    if x.leader_exit and not others:finish_departure(p,x)
    else:announce(p,'group.departure','Có yêu cầu rời nhóm cần xử lý')
    return departure_dto(x),201

@bp.post('/departures/<int:did>/vote')
@command(idempotent=True)
def vote(did):
    x=get(GroupDeparture,did,lock=True);p=project(x.project_id,mutable=True);state(x,['pending']);version(x)
    b=json_body();need(type(b.get('agree')) is bool)
    if x.leader_exit:
        need(membership(p.id) and current_user().id in x.electorate,'FORBIDDEN','Bạn không có quyền biểu quyết',403)
        key=str(current_user().id);need(key not in x.votes,'ALREADY_VOTED','Bạn đã biểu quyết',409)
        x.votes={**x.votes,key:b['agree']}
        if sum(v is True for v in x.votes.values())>=x.threshold:finish_departure(p,x)
        elif len(x.votes)==len(x.electorate):x.status='rejected';x.resolved_at=now()
    else:
        leader(p)
        if b['agree']:finish_departure(p,x)
        else:x.status='rejected';x.resolved_at=now()
    audit('group.departure_vote',x,pid=p.id);return departure_dto(x)

@bp.post('/assignments/<int:aid>/publish')
@command()
def publish(aid):
    a=assignment(aid,staff=True);version(a);need(a.due_at>now(),message='Hạn bài tập phải sau hiện tại')
    a.is_hidden=False;a.status='active';audit('assignment.published',a,cid=a.course_id);return dto(a)

@bp.route('/projects/<int:pid>/minutes',methods=['GET','POST'])
@command()
def minutes(pid):
    p=project(pid,mutable=request.method=='POST');need(membership(pid),'FORBIDDEN','Biên bản nội bộ nhóm',403)
    if request.method=='GET':return {'items':[dto(m) for m in Meeting.query.filter_by(project_id=pid).order_by(Meeting.id.desc())]}
    b=json_body();link=b.get('link','').strip()
    from ..collab.services import valid_url
    need(not link or valid_url(link),message='Link họp phải là http/https')
    m=Meeting(project_id=pid,host_id=current_user().id,title=textval(b,'title'),room_name='minutes-'+secrets.token_hex(12),notes=textval(b,'notes')+('\nLink cuộc họp: '+link if link else ''),status='ended',ended_at=now())
    db.session.add(m);audit('minutes.saved',m,pid=pid);return dto(m),201

@bp.get('/projects/<int:pid>/peer')
@command()
def peer(pid):
    p=project(pid);r=PeerRound.query.filter_by(assignment_id=p.assignment_id).order_by(PeerRound.id.desc()).first()
    opened=bool(r and r.status=='open' and r.opens_at<=now()<=r.closes_at)
    own=MatrixReview.query.filter_by(project_id=pid,round_id=r.id,reviewer_id=current_user().id).all() if r and membership(pid) else []
    return {'round':dto(r) if r else None,'open':opened,'members':[user_brief(m.user_id) for m in members(pid) if m.user_id!=current_user().id], 'own':[{'reviewee_id':x.reviewee_id,'attitude':x.attitude10,'quality':x.quality10} for x in own], 'results':peer_results(p)}

def peer_results(p):
    rounds=PeerRound.query.filter_by(assignment_id=p.assignment_id).order_by(PeerRound.id.desc()).all()
    out=[]
    for r in rounds:
        if r.status=='open' and now()<=r.closes_at:continue
        responses=MatrixReview.query.filter_by(project_id=p.id,round_id=r.id).all()
        ids={x.reviewee_id for x in responses}
        items=[]
        for uid in sorted(ids):
            rs=[x for x in responses if x.reviewee_id==uid]
            attitude=round(sum(x.attitude10 or x.attitude*2 for x in rs)/len(rs),2)
            quality=round(sum(x.quality10 or x.quality*2 for x in rs)/len(rs),2)
            items.append({'user':user_brief(uid),'count':len(rs),'attitude':attitude,'quality':quality,'average':round((attitude+quality)/2,2)})
        out.append({'title':r.title,'items':items})
    return out

@bp.put('/projects/<int:pid>/peer')
@command()
def peer_save(pid):
    p=project(pid,mutable=True);need(membership(pid),'FORBIDDEN','Chỉ thành viên đánh giá',403)
    b=json_body();r=get(PeerRound,integer(b.get('round_id')))
    need(r.assignment_id==p.assignment_id and r.status=='open' and r.opens_at<=now()<=r.closes_at,'ROUND_CLOSED','Đợt đánh giá đã đóng',409)
    items=b.get('items');need(isinstance(items,list))
    allowed={m.user_id for m in members(pid)}-{current_user().id};seen=set()
    for i in items:
        uid=integer(i.get('reviewee_id'));need(uid in allowed and uid not in seen);seen.add(uid)
        row=MatrixReview.query.filter_by(project_id=pid,round_id=r.id,reviewer_id=current_user().id,reviewee_id=uid).first()
        if i.get('skip'):
            if row:db.session.delete(row)
            continue
        at=integer(i.get('attitude'),1,10);qu=integer(i.get('quality'),1,10)
        if not row:
            row=MatrixReview(project_id=pid,round_id=r.id,reviewer_id=current_user().id,reviewee_id=uid);db.session.add(row)
        row.attitude10=at;row.quality10=qu;row.attitude=(at+1)//2;row.quality=(qu+1)//2;row.comment=''
    return {'saved':True}

@bp.get('/projects/<int:pid>/report')
@command()
def report(pid):return report_data(project(pid))

def report_data(p):
    d=group_report(p);d.pop('quality',None)
    d['course']=dto(get(CourseOffering,get(Assignment,p.assignment_id).course_id))
    d['peer']=peer_results(p)
    d['evidence']=_evidence.evidence_summary(p)
    d['departures']=[departure_dto(x) for x in GroupDeparture.query.filter_by(project_id=p.id)]
    d['deliveries']=[dto(x) for x in GroupDelivery.query.filter_by(project_id=p.id).order_by(GroupDelivery.id.desc())]
    d['documents']=rows(AssignmentFile,assignment_id=p.assignment_id)
    # Contribution decisions are reportable; raw allegations remain scoped to the case.
    d['complaints']=[]
    d['allocation_history']=[{**dto(x),'decided_by_name':user_brief(x.decided_by)['full_name']} for x in AllocationChange.query.join(Task).filter(Task.project_id==p.id)]
    events=AuditEvent.query.filter_by(project_id=p.id).filter(AuditEvent.action.in_(['task.created','task.started','task.submitted','submission.accepted','submission.returned','submission.referred'])).order_by(AuditEvent.created_at,AuditEvent.id).all()
    d['timeline']=[{'at':iso(e.created_at),'action':e.action,'reason':e.reason or ''} for e in events]
    d['formula']='Khối lượng đã duyệt × tỷ lệ đóng góp của từng công việc. Tỷ trọng = khối lượng ghi nhận cá nhân / tổng khối lượng ghi nhận × 100. Đánh giá chéo: trung bình các phiếu hợp lệ theo từng tiêu chí; không tính phiếu bỏ qua là 0.'
    return d

@bp.route('/projects/<int:pid>/snapshots',methods=['GET','POST'])
@command(idempotent=True)
def snapshots(pid):
    p=project(pid)
    if request.method=='GET':return {'items':[dto(x,omit=('content',)) for x in ReportSnapshot.query.filter_by(project_id=pid).order_by(ReportSnapshot.id.desc())]}
    leader(p);x=ReportSnapshot(project_id=pid,created_by=current_user().id,content=report_data(p));db.session.add(x);db.session.flush();return dto(x,omit=('content',)),201

@bp.get('/projects/<int:pid>/export')
def export(pid):
    need(current_user(),'UNAUTHORIZED','Cần đăng nhập',401);p=project(pid)
    sid=request.args.get('snapshot',type=int)
    if sid:
        snap=get(ReportSnapshot,sid);need(snap.project_id==pid,'NOT_FOUND','Không tìm thấy báo cáo',404);data=snap.content
    else:data=report_data(p)
    from .workflow_reports import export_report
    return export_report(data,request.args.get('format','html'))

@bp.route('/projects/<int:pid>/deliveries',methods=['GET','POST'])
@command(idempotent=True)
def deliveries(pid):
    p=project(pid,mutable=request.method=='POST')
    if request.method=='GET':return {'items':[dto(x) for x in GroupDelivery.query.filter_by(project_id=pid).order_by(GroupDelivery.id.desc())]}
    leader(p);b=json_body();ids=b.get('submission_ids');need(isinstance(ids,list) and ids)
    for sid in ids:
        s=get(TaskSubmission,integer(sid));need(get(Task,s.task_id).project_id==pid and s.status=='accepted',message='Chỉ chọn bài đã duyệt trong nhóm')
    x=GroupDelivery(project_id=pid,submitted_by=current_user().id,title=textval(b,'title'),submission_ids=sorted(set(ids)))
    db.session.add(x);audit('group.delivered',x,pid=pid);return dto(x),201

@bp.get('/projects/<int:pid>/complaints')
@command()
def cases(pid):
    p=project(pid);q=WorkComplaint.query.join(Task).filter(Task.project_id==pid)
    if is_staff(p):q=q.filter(WorkComplaint.handler=='instructor')
    return {'items':[complaint_dto(c) for c in q.order_by(WorkComplaint.id.desc())]}

@bp.route('/admin/users',methods=['GET','POST'])
@command()
def users():
    need(current_user().role=='admin','FORBIDDEN','Cần quản trị hệ thống',403)
    if request.method=='GET':return {'items':[u.to_dict() for u in User.query.order_by(User.id)]}
    b=json_body();email=textval(b,'email').lower();need('@' in email);need(not User.query.filter_by(email=email).first(),message='Email đã tồn tại')
    role=b.get('role');need(role in ('user','instructor','admin'))
    password=textval(b,'password');need(len(password)>=5,message='Mật khẩu tối thiểu 5 ký tự')
    u=User(email=email,full_name=textval(b,'full_name'),role=role);u.set_password(password);db.session.add(u);db.session.flush();return u.to_dict(),201

@bp.patch('/admin/users/<int:uid>')
@command()
def user_update(uid):
    need(current_user().role=='admin','FORBIDDEN','Cần quản trị hệ thống',403);u=get(User,uid);b=json_body()
    need(uid!=current_user().id,message='Không khóa chính tài khoản đang dùng')
    if 'is_active' in b:need(type(b['is_active']) is bool);u.is_active=b['is_active']
    if b.get('password'):need(len(b['password'])>=5);u.set_password(b['password'])
    return u.to_dict()

def deadline_reminders():
    for t in Task.query.filter(Task.status.in_(['todo','in_progress']),Task.due_at<=now()+timedelta(hours=24)).all():
        p=get(Project,t.project_id)
        if p.status!='active':continue
        late=t.due_at<now();key=f'{t.id}:{iso(t.due_at)}:{now().date() if late else "soon"}'
        if db.session.get(DeadlineReminder,key):continue
        recipients={x.user_id for x in TaskParticipant.query.filter_by(task_id=t.id) if membership(p.id,x.user_id)}
        if late:recipients|={x.user_id for x in members(p.id) if x.role=='leader'}
        announce(p,'deadline.reminder',('Quá hạn: ' if late else 'Sắp đến hạn: ')+t.title,sorted(recipients),f'/tasks/{t.id}')
        db.session.add(DeadlineReminder(key=key))
    db.session.commit()

@bp.before_app_request
def retired_workflows():
    path=request.path
    if not path.startswith('/api/v1/'):return
    if path.endswith('/report/download') and '/workflow/' not in path:
        pid=request.view_args.get('pid');return redirect(f'/api/v1/workflow/projects/{pid}/export?format='+request.args.get('format','html'))
    blocked=('/grades','/quality','/commitment','/analytics','/peer-matrix','/policies','/policy','/branches','/merge-requests','/extract-tasks','/heartbeat','/task-drafts','/workspace-templates','/apply-template')
    if '/workflow/' not in path and (any(x in path for x in blocked) or path.endswith('/activate') and '/projects/' in path or path.endswith('/members') and request.method!='GET' or '/change-requests' in path or '/meetings' in path or '/final-submissions' in path or '/rubric' in path):
        need(False,'RETIRED','Chức năng đã được thay bằng luồng mới',410)

@bp.post('/tasks/<int:tid>/assignment')
@command()
def task_assignment(tid):
    t=task(tid,mutable=True);p=get(Project,t.project_id);leader(p);version(t)
    need(t.status not in ('done','review'),'TASK_LOCKED','Chỉ sửa công việc chưa hoàn thành hoặc chưa chờ duyệt',409)
    b=json_body();t.title=textval(b,'title');t.description=textval(b,'description')
    need(b.get('points') in (1,2,3,5));t.points=b['points']
    need(b.get('priority') in ('low','medium','high'));t.priority=b['priority']
    from ..m06_projects.academic_api import set_task_relations
    set_task_relations(t,{'participants':b.get('participants')})
    audit('task.updated',t,pid=p.id,reason='Cập nhật phân công và đầu ra');return task_dto(t)
