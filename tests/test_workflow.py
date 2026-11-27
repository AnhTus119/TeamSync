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

def test_demo_scope_and_retired_paths(app):
    c=Client(app,'sv1@gmail.com');home=c.req('/workflow/home');assert len(home['courses'])==8;assert home['courses'][0]['title']=='Lập trình Web'
    for path in ['/projects/1/grades','/projects/1/quality','/projects/1/analytics','/projects/1/peer-matrix','/projects/1/commitment']:
        c.req(path,code=410)
    c.req('/projects/2',code=404)
    admin=Client(app,'admin@gmail.com');admin.req('/workflow/projects/1/report',code=403)

def test_teacher_course_single_assignment_and_optional_rubric(app):
    c=Client(app,'gv1@gmail.com');co=c.req('/courses',{'code':'NEW','title':'Lớp mới','term':'2026'},code=201)
    a=c.req(f'/courses/{co["id"]}/assignments',{'title':'Bài tập','brief':'Xây dựng sản phẩm','due_at':(now()+timedelta(days=40)).isoformat()},code=201)
    a=c.req(f'/workflow/assignments/{a["id"]}/publish',{'version':a['version']});assert a['status']=='active' and a['published_policy_id'] is None
    c.req(f'/courses/{co["id"]}/assignments',{'title':'Bài thứ hai'},code=409)

def test_submission_shared_review_and_repair(app):
    c=Client(app,'sv2@gmail.com');t=c.req('/tasks/1');asset=t['assets'][0]['id']
    s=c.req('/tasks/1/submissions',{'version':t['version'],'asset_ids':[asset],'description':'Đã sửa giao diện'},code=201)
    assert len(s['participant_ids'])==2
    c.req('/assets/'+str(asset)+'/download')
    c.req(f'/submissions/{s["id"]}/review',{'version':s['task_version'],'action':'accept'},code=403)
    other=Client(app,'sv4@gmail.com');t=other.req('/tasks/1')
    other.req(f'/submissions/{s["id"]}/review',{'version':t['version'],'action':'return','reason':''},code=400)
    other.req(f'/submissions/{s["id"]}/review',{'version':t['version'],'action':'return','reason':'Bổ sung kiểm thử','repair_due_at':(now()+timedelta(days=3)).isoformat()})
    after=c.req('/tasks/1');assert after['status']=='in_progress' and len(after['submissions'])==2
    assert after['submissions'][-1]['participant_ids']==s['participant_ids']

def test_task_required_output_and_no_criterion(app):
    c=Client(app,'sv1@gmail.com');p=c.req('/projects/1');uid=p['members'][0]['user_id']
    body={'title':'Việc mới','participants':[{'user_id':uid,'role':'responsible'}],'due_at':(now()+timedelta(days=3)).isoformat()}
    c.req('/projects/1/tasks',body,code=400);body['description']='File bàn giao chạy được'
    t=c.req('/projects/1/tasks',body,code=201);assert t['points']==1 and not t['criteria']

def test_leader_departure_vote_and_access_revocation(app):
    c=Client(app,'sv1@gmail.com');x=c.req('/workflow/projects/1/departures',{'reason':'Không tiếp tục học phần'},code=201);assert x['threshold']==3 and len(x['electorate'])==5
    for n in (2,3,4):
        member=Client(app,f'sv{n}@gmail.com');x=member.req(f'/workflow/departures/{x["id"]}/vote',{'version':x['version'],'agree':True})
    assert x['status']=='approved' and x['successor_id'] in x['electorate'];c.req('/projects/1',code=404)
    c.req('/assignments/1/projects',{'name':'Tự vào lại'},code=409)
    teacher=Client(app,'gv1@gmail.com');r=teacher.req('/workflow/projects/1/report');assert r['departures'][0]['successor']

def test_member_departure_requires_leader_and_preserves_work(app):
    c=Client(app,'sv4@gmail.com');x=c.req('/workflow/projects/1/departures',{'reason':'Xin rời'},code=201)
    c.req(f'/workflow/departures/{x["id"]}/vote',{'version':x['version'],'agree':True},code=403)
    leader=Client(app,'sv1@gmail.com');leader.req(f'/workflow/departures/{x["id"]}/vote',{'version':x['version'],'agree':True})
    r=leader.req('/workflow/projects/1/report');name=name_of(app,'sv4@gmail.com');assert any(m['user']['full_name']==name and float(m['accepted_workload'])>0 for m in r['members'])

def test_group_formation_approval_and_teacher_add(app):
    c=Client(app,'sv31@gmail.com');p=c.req('/assignments/1/projects',{'name':'Nhóm mới'},code=201)
    for n in (32,33):
        uid=n+2;inv=c.req(f'/projects/{p["id"]}/invitations',{'version':p['version'],'kind':'member','user_id':uid},code=201)
        other=Client(app,f'sv{n}@gmail.com');other.req(f'/invitations/{inv["id"]}/respond',{'version':inv['version'],'action':'accept'})
        p=c.req('/projects/'+str(p['id']))
    p=c.req(f'/workflow/projects/{p["id"]}/approval',{'version':p['version'],'action':'submit'});assert p['status']=='pending'
    teacher=Client(app,'gv1@gmail.com');p=teacher.req(f'/workflow/projects/{p["id"]}/approval',{'version':p['version'],'action':'accept'});assert p['status']=='active'
    new=teacher.req('/workflow/assignments/1/groups',{'name':'Nhóm xếp sẵn','user_ids':[36,37,38],'leader_id':36},code=201);assert len(new['members'])==3

def test_peer_optional_anonymous_and_closed_aggregate(app):
    teacher=Client(app,'gv1@gmail.com');r=teacher.req('/assignments/1/evaluation-rounds',{'title':'Đợt 1','closes_at':(now()+timedelta(days=2)).isoformat()},code=201)
    c=Client(app,'sv2@gmail.com');c.req('/workflow/projects/1/peer',{'round_id':r['id'],'items':[{'reviewee_id':5,'attitude':8,'quality':6},{'reviewee_id':3,'skip':True}]},method='PUT')
    assert teacher.req('/workflow/projects/1/peer')['results']==[]
    teacher.req(f'/evaluation-rounds/{r["id"]}/close',{'version':r['version']})
    result=teacher.req('/workflow/projects/1/peer')['results'][0]['items'][0]
    assert result['average']==7 and result['count']==1 and 'reviewer_id' not in result
    other=Client(app,'sv3@gmail.com');assert other.req('/workflow/projects/1/peer')['results'][0]['items'][0]==result

def test_teacher_support_without_invitation_and_required_fields(app):
    c=Client(app,'sv3@gmail.com');c.req('/projects/1/help-requests',{'subject':'Lỗi'},code=400)
    h=c.req('/projects/1/help-requests',{'subject':'Nhờ kiểm tra','content':'Nhóm cần hỗ trợ cách kiểm thử','scope':'group','task_id':None},code=201)
    teacher=Client(app,'gv1@gmail.com');teacher.req(f'/help-requests/{h["id"]}/respond',{'version':h['version'],'response':'Kiểm tra các vai trò và quyền truy cập.','resolve':True})

def test_complaint_resolution_total_and_teacher_escalation(app):
    c=Client(app,'sv2@gmail.com');case=c.req('/projects/1/complaints',{'task_id':1,'target_id':5,'reason':'Đề nghị ghi nhận 80/20 theo phần việc thực hiện'},code=201)
    target=Client(app,'sv3@gmail.com');case=target.req(f'/complaints/{case["id"]}/explain',{'version':case['version'],'explanation':'Đồng ý đối chiếu phần việc'})
    leader=Client(app,'sv1@gmail.com');leader.req(f'/complaints/{case["id"]}/resolve',{'version':case['version'],'reason':'Đối chiếu sản phẩm','shares':{'4':'80','5':'10'}},code=400)
    leader.req(f'/complaints/{case["id"]}/resolve',{'version':case['version'],'reason':'Đối chiếu sản phẩm','shares':{'4':'80','5':'20'}})
    report=leader.req('/workflow/projects/1/report');assert report['allocation_history'][0]['shares']=={'4':'80','5':'20'}

def test_reminders_deduplicated_and_no_teacher(app):
    from app.academic.workflow import deadline_reminders
    with app.app_context():
        deadline_reminders();first=OutboxEvent.query.count();deadline_reminders();assert OutboxEvent.query.count()==first and first>0
        for e in OutboxEvent.query.filter_by(event_type='deadline.reminder'):assert 2 not in e.payload['recipients']

def test_export_snapshot_and_delivery(app):
    c=Client(app,'sv1@gmail.com');s=c.req('/workflow/projects/1/snapshots',{},code=201)
    for fmt in ('xlsx','pdf','html'):
        r=c.req(f'/workflow/projects/1/export?format={fmt}&snapshot={s["id"]}');assert len(r.data)>1000
    c.req('/workflow/projects/1/deliveries',{'title':'Báo cáo và mã nguồn','submission_ids':[2]},code=201)
    c.req('/workflow/projects/1/deliveries',{'title':'Sai','submission_ids':[3]},code=400)

def test_minute_privacy_and_no_video(app):
    c=Client(app,'sv2@gmail.com');c.req('/workflow/projects/1/minutes',{'title':'Họp tuần 2','notes':'Hoàn thiện API trước thứ sáu','link':'https://meet.google.com/'},code=201)
    teacher=Client(app,'gv1@gmail.com');teacher.req('/workflow/projects/1/minutes',code=403)
    c.req('/projects/1/meetings',code=410)

def test_csrf_and_upload_scope(app):
    c=Client(app,'sv2@gmail.com');r=c.c.post('/api/v1/tasks/1/submissions',json={});assert r.status_code==400
    r=c.c.post('/api/v1/tasks/1/assets',data={'file':(io.BytesIO(b'hello'),'product.txt')},headers={'X-CSRF-Token':c.token});assert r.status_code==201,r.json
    other=Client(app,'sv7@gmail.com');other.req('/assets/'+str(r.json['data']['id'])+'/download',code=404)
