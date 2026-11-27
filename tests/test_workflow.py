import io, shutil, uuid
from pathlib import Path
import pytest
from flask_migrate import upgrade
from app import create_app
from app.extensions import db
from app.academic.workflow_seed import seed_demo
from app.models import *
from app.models.academic import *
from app.models.workflow import *
from datetime import datetime, timezone
def now(): return datetime.now(timezone.utc)
from datetime import timedelta

# Demo accounts (see docs/TAI_KHOAN_DEMO.md); all passwords are 12345.
MA, TH, QB, GL, AN = (f'{k}@sv.teamsync.test' for k in ('minhanh', 'thuha', 'quocbao', 'gialinh', 'annhien'))
GV = 'khanhan@gv.teamsync.test'          # Phát triển ứng dụng Web (Free2do)
GV_AI = 'quangminh@gv.teamsync.test'     # Trí tuệ nhân tạo (ChatbotAI)
GV_QLDA = 'thuhang@gv.teamsync.test'     # Quản lý dự án CNTT
ADMIN = 'admin@teamsync.test'
COORD = 'daotao@gv.teamsync.test'

@pytest.fixture(scope='session')
def template(tmp_path_factory):
    root=tmp_path_factory.mktemp('template');database=root/'db.sqlite'
    app=create_app({'TESTING':True,'SQLALCHEMY_DATABASE_URI':'sqlite:///'+str(database),'PRIVATE_STORAGE':str(root/'files'),'DEMO_CLOCK_ENABLED':True})
    with app.app_context():
        upgrade(directory=str(Path(__file__).parents[1]/'migrations'));seed_demo();db.engine.dispose()
    return root

@pytest.fixture
def app(tmp_path,template):
    shutil.copy(template/'db.sqlite',tmp_path/'db.sqlite');shutil.copytree(template/'files',tmp_path/'files')
    app=create_app({'TESTING':True,'SQLALCHEMY_DATABASE_URI':'sqlite:///'+str(tmp_path/'db.sqlite'),'PRIVATE_STORAGE':str(tmp_path/'files'),'DEMO_CLOCK_ENABLED':True,'LOGIN_RATE_LIMIT':1000})
    yield app
    with app.app_context():db.session.remove();db.engine.dispose()

class Client:
    def __init__(self,app,email):
        self.c=app.test_client();token=self.c.get('/api/v1/auth/csrf').json['data']['token']
        r=self.c.post('/api/v1/auth/login',json={'email':email,'password':'12345'},headers={'X-CSRF-Token':token});assert r.status_code==200,r.json
        self.token=self.c.get('/api/v1/auth/csrf').json['data']['token']
    def req(self,path,body=None,method=None,code=200):
        r=self.c.open('/api/v1'+path,method=method or ('POST' if body is not None else 'GET'),json=body,headers={'X-CSRF-Token':self.token,'Idempotency-Key':str(uuid.uuid4())})
        assert r.status_code==code,(path,r.status_code,r.json)
        return r.json['data'] if r.is_json and code<400 else r

def name_of(app,email):
    with app.app_context():return User.query.filter_by(email=email).one().full_name

def uid(app,email):
    with app.app_context():return User.query.filter_by(email=email).one().id

def demo(app):
    """Ids of the fixed demo records: Free2do (Minh Anh leads) and its shared login task."""
    with app.app_context():
        p=Project.query.filter_by(name='Free2do').one();a=db.session.get(Assignment,p.assignment_id)
        t=Task.query.filter_by(project_id=p.id,title='Thiết kế màn hình đăng nhập').one()
        grouped={m.user_id for m in AssignmentMembership.query.filter_by(assignment_id=a.id,status='active')}
        free=[db.session.get(User,e.user_id).email for e in CourseEnrollment.query.filter_by(course_id=a.course_id,role='student') if e.user_id not in grouped]
        outsider=next(u.email for u in User.query.filter(User.email.like('%@sv.teamsync.test')) if not AssignmentMembership.query.filter_by(project_id=p.id,user_id=u.id).first() and u.email!=AN)
        other=Project.query.filter(Project.assignment_id==a.id,Project.id!=p.id).first().id
        accepted=TaskSubmission.query.join(Task,Task.id==TaskSubmission.task_id).filter(Task.project_id==p.id,TaskSubmission.status=='accepted').first().id
        pending=TaskSubmission.query.join(Task,Task.id==TaskSubmission.task_id).filter(Task.project_id==p.id,TaskSubmission.status=='pending').first().id
        return dict(pid=p.id,aid=a.id,cid=a.course_id,tid=t.id,free=free,outsider=outsider,other_pid=other,accepted=accepted,pending=pending)

def test_demo_scope_and_retired_paths(app):
    d=demo(app);c=Client(app,MA);home=c.req('/workflow/home')
    assert home['courses'][0]['title']=='Phát triển ứng dụng Web' and len(home['projects'])==7
    for path in [f'/projects/{d["pid"]}/grades',f'/projects/{d["pid"]}/quality',f'/projects/{d["pid"]}/analytics',f'/projects/{d["pid"]}/peer-matrix',f'/projects/{d["pid"]}/commitment']:
        c.req(path,code=410)
    c.req(f'/projects/{d["other_pid"]}',code=404)
    admin=Client(app,ADMIN);admin.req(f'/workflow/projects/{d["pid"]}/report',code=403)

def test_every_demo_person_has_a_working_account(app):
    with app.app_context():
        emails=[u.email for u in User.query]
        for e in CourseEnrollment.query:assert db.session.get(User,e.user_id) is not None
        for m in AssignmentMembership.query:assert db.session.get(User,m.user_id).is_active
        assert CourseOffering.query.count()==12 and User.query.filter_by(role='instructor').count()==12
    for e in (MA,GV,GV_AI,COORD,ADMIN,emails[-1]):Client(app,e)

def test_teacher_course_single_assignment_and_optional_rubric(app):
    c=Client(app,GV);co=c.req('/courses',{'code':'NEW','title':'Lớp mới','term':'2026'},code=201)
    a=c.req(f'/courses/{co["id"]}/assignments',{'title':'Bài tập','brief':'Xây dựng sản phẩm','due_at':(now()+timedelta(days=40)).isoformat()},code=201)
    a=c.req(f'/workflow/assignments/{a["id"]}/publish',{'version':a['version']});assert a['status']=='active' and a['published_policy_id'] is None
    c.req(f'/courses/{co["id"]}/assignments',{'title':'Bài thứ hai'},code=409)

def test_submission_shared_review_and_repair(app):
    d=demo(app);c=Client(app,TH);t=c.req(f'/tasks/{d["tid"]}');asset=t['assets'][0]['id']
    s=c.req(f'/tasks/{d["tid"]}/submissions',{'version':t['version'],'asset_ids':[asset],'description':'Đã sửa giao diện'},code=201)
    assert len(s['participant_ids'])==2
    c.req('/assets/'+str(asset)+'/download')
    c.req(f'/submissions/{s["id"]}/review',{'version':s['task_version'],'action':'accept'},code=403)
    Client(app,QB).req(f'/submissions/{s["id"]}/review',{'version':s['task_version'],'action':'accept'},code=403)  # collaborator is in the roster
    other=Client(app,GL);t=other.req(f'/tasks/{d["tid"]}')
    other.req(f'/submissions/{s["id"]}/review',{'version':t['version'],'action':'return','reason':''},code=400)
    other.req(f'/submissions/{s["id"]}/review',{'version':t['version'],'action':'return','reason':'Bổ sung kiểm thử','repair_due_at':(now()+timedelta(days=3)).isoformat()})
    after=c.req(f'/tasks/{d["tid"]}');assert after['status']=='in_progress' and len(after['submissions'])==2
    assert after['submissions'][-1]['participant_ids']==s['participant_ids']

def test_task_required_output_and_no_criterion(app):
    d=demo(app);c=Client(app,MA);p=c.req(f'/projects/{d["pid"]}');member=p['members'][0]['user_id']
    body={'title':'Việc mới','participants':[{'user_id':member,'role':'responsible'}],'due_at':(now()+timedelta(days=3)).isoformat()}
    c.req(f'/projects/{d["pid"]}/tasks',body,code=400);body['description']='File bàn giao chạy được'
    t=c.req(f'/projects/{d["pid"]}/tasks',body,code=201);assert t['points']==1 and not t['criteria']

def test_leader_departure_vote_and_access_revocation(app):
    d=demo(app);c=Client(app,MA);x=c.req(f'/workflow/projects/{d["pid"]}/departures',{'reason':'Không tiếp tục học phần'},code=201)
    assert x['threshold']==2 and len(x['electorate'])==3  # ceil(3 remaining / 2)
    for email in (TH,QB):
        x=Client(app,email).req(f'/workflow/departures/{x["id"]}/vote',{'version':x['version'],'agree':True})
    assert x['status']=='approved' and x['successor_id'] in x['electorate'];c.req(f'/projects/{d["pid"]}',code=404)
    c.req(f'/assignments/{d["aid"]}/projects',{'name':'Tự vào lại'},code=409)
    r=Client(app,GV).req(f'/workflow/projects/{d["pid"]}/report');assert r['departures'][0]['successor']

def test_member_departure_requires_leader_and_preserves_work(app):
    d=demo(app);c=Client(app,GL);x=c.req(f'/workflow/projects/{d["pid"]}/departures',{'reason':'Xin rời'},code=201)
    c.req(f'/workflow/departures/{x["id"]}/vote',{'version':x['version'],'agree':True},code=403)
    leader=Client(app,MA);leader.req(f'/workflow/departures/{x["id"]}/vote',{'version':x['version'],'agree':True})
    r=leader.req(f'/workflow/projects/{d["pid"]}/report');name=name_of(app,GL)
    assert any(m['user']['full_name']==name and float(m['accepted_workload'])>0 for m in r['members'])

def test_group_formation_approval_and_teacher_add(app):
    d=demo(app);free=[e for e in d['free'] if e!=AN];assert len(free)>=6
    c=Client(app,free[0]);p=c.req(f'/assignments/{d["aid"]}/projects',{'name':'Nhóm mới'},code=201)
    for email in free[1:3]:
        inv=c.req(f'/projects/{p["id"]}/invitations',{'version':p['version'],'kind':'member','user_id':uid(app,email)},code=201)
        Client(app,email).req(f'/invitations/{inv["id"]}/respond',{'version':inv['version'],'action':'accept'})
        p=c.req('/projects/'+str(p['id']))
    p=c.req(f'/workflow/projects/{p["id"]}/approval',{'version':p['version'],'action':'submit'});assert p['status']=='pending'
    teacher=Client(app,GV);p=teacher.req(f'/workflow/projects/{p["id"]}/approval',{'version':p['version'],'action':'accept'});assert p['status']=='active'
    ids=[uid(app,e) for e in free[3:6]]
    new=teacher.req(f'/workflow/assignments/{d["aid"]}/groups',{'name':'Nhóm xếp sẵn','user_ids':ids,'leader_id':ids[0]},code=201);assert len(new['members'])==3

def test_peer_optional_anonymous_and_closed_aggregate(app):
    d=demo(app);teacher=Client(app,GV);r=teacher.req(f'/assignments/{d["aid"]}/evaluation-rounds',{'title':'Đợt 1','closes_at':(now()+timedelta(days=2)).isoformat()},code=201)
    c=Client(app,TH);c.req(f'/workflow/projects/{d["pid"]}/peer',{'round_id':r['id'],'items':[{'reviewee_id':uid(app,QB),'attitude':8,'quality':6},{'reviewee_id':uid(app,GL),'skip':True}]},method='PUT')
    assert teacher.req(f'/workflow/projects/{d["pid"]}/peer')['results']==[]
    teacher.req(f'/evaluation-rounds/{r["id"]}/close',{'version':r['version']})
    result=teacher.req(f'/workflow/projects/{d["pid"]}/peer')['results'][0]['items'][0]
    assert result['average']==7 and result['count']==1 and 'reviewer_id' not in result
    other=Client(app,QB);assert other.req(f'/workflow/projects/{d["pid"]}/peer')['results'][0]['items'][0]==result

def test_teacher_support_without_invitation_and_required_fields(app):
    d=demo(app);c=Client(app,QB);c.req(f'/projects/{d["pid"]}/help-requests',{'subject':'Lỗi'},code=400)
    h=c.req(f'/projects/{d["pid"]}/help-requests',{'subject':'Nhờ kiểm tra','content':'Nhóm cần hỗ trợ cách kiểm thử','scope':'group','task_id':None},code=201)
    Client(app,GV).req(f'/help-requests/{h["id"]}/respond',{'version':h['version'],'response':'Kiểm tra các vai trò và quyền truy cập.','resolve':True})

def test_complaint_resolution_total_and_teacher_escalation(app):
    d=demo(app);th,qb=str(uid(app,TH)),str(uid(app,QB))
    c=Client(app,TH);case=c.req(f'/projects/{d["pid"]}/complaints',{'task_id':d['tid'],'target_id':int(qb),'reason':'Đề nghị ghi nhận 80/20 theo phần việc thực hiện'},code=201)
    case=Client(app,QB).req(f'/complaints/{case["id"]}/explain',{'version':case['version'],'explanation':'Đồng ý đối chiếu phần việc'})
    leader=Client(app,MA);leader.req(f'/complaints/{case["id"]}/resolve',{'version':case['version'],'reason':'Đối chiếu sản phẩm','shares':{th:'80',qb:'10'}},code=400)
    leader.req(f'/complaints/{case["id"]}/resolve',{'version':case['version'],'reason':'Đối chiếu sản phẩm','shares':{th:'80',qb:'20'}})
    report=leader.req(f'/workflow/projects/{d["pid"]}/report');assert report['allocation_history'][0]['shares']=={th:'80',qb:'20'}

def test_reminders_deduplicated_and_no_teacher(app):
    from app.academic.workflow import deadline_reminders
    teachers={uid(app,GV),uid(app,GV_AI),uid(app,GV_QLDA)}
    with app.app_context():
        deadline_reminders();first=OutboxEvent.query.count();deadline_reminders();assert OutboxEvent.query.count()==first
        events=OutboxEvent.query.filter_by(event_type='deadline.reminder',processed_at=None).all();assert events
        for e in events:assert not teachers & set(e.payload['recipients'])

def test_export_snapshot_and_delivery(app):
    d=demo(app);c=Client(app,MA);s=c.req(f'/workflow/projects/{d["pid"]}/snapshots',{},code=201)
    for fmt in ('xlsx','pdf','html'):
        r=c.req(f'/workflow/projects/{d["pid"]}/export?format={fmt}&snapshot={s["id"]}');assert len(r.data)>1000
    c.req(f'/workflow/projects/{d["pid"]}/deliveries',{'title':'Báo cáo và mã nguồn','submission_ids':[d['accepted']]},code=201)
    c.req(f'/workflow/projects/{d["pid"]}/deliveries',{'title':'Sai','submission_ids':[d['pending']]},code=400)

def test_minute_privacy_and_no_video(app):
    d=demo(app);c=Client(app,TH);c.req(f'/workflow/projects/{d["pid"]}/minutes',{'title':'Họp tuần 2','notes':'Hoàn thiện API trước thứ sáu','link':'https://meet.google.com/'},code=201)
    Client(app,GV).req(f'/workflow/projects/{d["pid"]}/minutes',code=403)
    c.req(f'/projects/{d["pid"]}/meetings',code=410)

def test_csrf_and_upload_scope(app):
    d=demo(app);c=Client(app,TH);r=c.c.post(f'/api/v1/tasks/{d["tid"]}/submissions',json={});assert r.status_code==400
    r=c.c.post(f'/api/v1/tasks/{d["tid"]}/assets',data={'file':(io.BytesIO(b'hello'),'product.txt')},headers={'X-CSRF-Token':c.token});assert r.status_code==201,r.json
    Client(app,d['outsider']).req('/assets/'+str(r.json['data']['id'])+'/download',code=404)
