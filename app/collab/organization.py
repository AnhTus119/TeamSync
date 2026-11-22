"""Assignment resources, formation rules and per-round evaluation reporting."""
import secrets
from flask import request
from . import bp
from .services import *
from ..models.academic import AssignmentFile
from ..common.storage import save_upload,download,root


def require_self_formation(a):
    need(a.group_mode == 'self','FORMATION_LOCKED','Bài tập do giảng viên xếp nhóm; sinh viên không được tự lập hoặc đổi nhóm',409)
    need(not a.formation_due_at or now() < a.formation_due_at,'FORMATION_CLOSED','Đã hết thời hạn lập nhóm; liên hệ giảng viên để được xếp nhóm',409)


def configure_formation(a,b):
    if 'method' in b:
        need(b['method'] in ('random','roster_cycle'))
        a.group_method=b['method']
    if 'group_mode' in b:
        need(b['group_mode'] in ('self','teacher'))
        if a.id and a.group_mode != b['group_mode']:
            need(not AssignmentMembership.query.filter_by(assignment_id=a.id,status='active').first(),'FORMATION_STARTED','Không đổi cơ chế sau khi đã có thành viên trong nhóm',409)
        a.group_mode=b['group_mode']
    if a.group_mode=='teacher':
        a.formation_due_at=None
    elif 'formation_due_at' in b:
        previous=a.formation_due_at
        a.formation_due_at=timestamp(b.get('formation_due_at'),True)
        if a.formation_due_at and a.formation_due_at != previous:
            need(now()<a.formation_due_at<=a.due_at,message='Hạn lập nhóm phải sau hiện tại và không vượt hạn nộp bài')
    if a.group_mode=='self' and 'group_mode' in b:
        need(a.formation_due_at,message='Cần đặt thời hạn lập nhóm tự do')


@bp.patch('/assignments/<int:aid>/organization')
@command()
def update_organization(aid):
    a=assignment(aid,staff=True);state(a,['draft','published','active'])
    need(enrollment(a.course_id).role=='instructor','FORBIDDEN','Giảng viên phụ trách tổ chức nhóm',403)
    b=json_body();version(a,b)
    size=integer(b.get('team_size',a.group_max),a.group_min,50)
    groups=Project.query.filter_by(assignment_id=aid).all()
    need(all(AssignmentMembership.query.filter_by(project_id=p.id,status='active').count()<=size for p in groups),message='Giới hạn mới nhỏ hơn số thành viên của nhóm hiện tại')
    a.group_max=size
    configure_formation(a,b)
    audit('assignment.organization_updated',a,cid=a.course_id)
    count=materialize_teacher_groups(a)
    return {**dto(a),'new_group_count':count}


def allocate_groups(a,b):
    from ..m06_projects.academic_api import add_group_member,project_dto
    need(enrollment(a.course_id).role=='instructor','FORBIDDEN','Giảng viên phụ trách tổ chức nhóm',403)
    size=integer(b.get('team_size',a.group_max),a.group_min,a.group_max)
    if a.group_mode=='self' and a.formation_due_at:
        need(now()>=a.formation_due_at,'FORMATION_STILL_OPEN','Sinh viên còn thời gian tự lập nhóm',409)
    assigned={m.user_id for m in AssignmentMembership.query.filter_by(assignment_id=a.id,status='active')}
    available={e.user_id for e in CourseEnrollment.query.filter_by(course_id=a.course_id,role='student',status='active') if e.user_id not in assigned and get(User,e.user_id).is_active}
    groups=b.get('groups')
    if groups is None:
        method=b.get('method',a.group_method or 'random')
        need(method in ('random','roster_cycle'),message='Cách xếp nhóm không hợp lệ')
        # Roster cycling: 1,2,…,N,1,2,…,N from top to bottom in student-code order.
        roster=CourseEnrollment.query.filter_by(course_id=a.course_id,role='student',status='active').order_by(CourseEnrollment.student_code,CourseEnrollment.id).all()
        ids=[e.user_id for e in roster if e.user_id in available]
        if method=='random':secrets.SystemRandom().shuffle(ids)
        need(ids,message='Không còn sinh viên chưa được xếp nhóm')
        count=(len(ids)+size-1)//size
        groups=[ids[i::count] for i in range(count)]
    need(isinstance(groups,list) and 0<len(groups)<=200)
    flat=[]
    for ids in groups:
        need(isinstance(ids,list) and 1<=len(ids)<=size,'GROUP_SIZE_INVALID','Số thành viên không hợp lệ')
        for uid in ids:integer(uid)
        flat.extend(ids)
    need(len(set(flat))==len(flat) and set(flat).issubset(available),'INVALID_PARTICIPANT','Sinh viên trùng, đã có nhóm hoặc không thuộc lớp')
    a.version += 1
    created=[]
    for ids in groups:
        number=Project.query.filter_by(assignment_id=a.id).count()+1
        p=Project(workspace_id=get(CourseOffering,a.course_id).workspace_id,name=f'G{number:02}',description='Nhóm được giảng viên phân công',created_by=current_user().id,assignment_id=a.id,mode='academic',status='active')
        db.session.add(p);db.session.flush()
        for i,uid in enumerate(ids):
            add_group_member(p,uid,'leader' if i==0 else 'member');db.session.flush()
        audit('team.allocated',p,cid=a.course_id,pid=p.id)
        created.append(project_dto(p))
    # Legacy assignments have no formation window: a first full allocation locks self creation.
    if not a.formation_due_at and not assigned:a.group_mode='teacher'
    return {'items':created,'underfilled_ids':[p['id'] for p in created if len(p['members'])<a.group_min]},201



def materialize_teacher_groups(a):
    """Save formation and memberships together; a hidden draft remains teacher-only."""
    if a.group_mode!='teacher':return 0
    db.session.flush()
    assigned={m.user_id for m in AssignmentMembership.query.filter_by(assignment_id=a.id,status='active')}
    roster=CourseEnrollment.query.filter_by(course_id=a.course_id,role='student',status='active').all()
    if not any(e.user_id not in assigned and get(User,e.user_id).is_active for e in roster):return 0
    result,_=allocate_groups(a,{'team_size':a.group_max,'method':a.group_method or 'random'})
    return len(result['items'])

def file_dto(f):
    return {'id':f.id,'name':f.original_filename,'size_bytes':f.size_bytes,'download_url':f'/api/v1/assignment-files/{f.id}/download'}


@bp.route('/assignments/<int:aid>/files',methods=['GET','POST'])
@command()
def assignment_files(aid):
    a=assignment(aid,staff=request.method=='POST')
    if request.method=='GET':return {'items':[file_dto(f) for f in AssignmentFile.query.filter_by(assignment_id=aid).order_by(AssignmentFile.id)]}
    need(enrollment(a.course_id).role=='instructor','FORBIDDEN','Giảng viên đính kèm đề bài',403)
    state(a,['draft','published','active'])
    uploads=request.files.getlist('files');need(0<len(uploads)<=10,message='Chọn từ 1 đến 10 file')
    need(AssignmentFile.query.filter_by(assignment_id=aid).count()+len(uploads)<=30,message='Tối đa 30 file mỗi đề bài')
    saved=[]
    try:
        for f in uploads:saved.append(save_upload(f))
        rows=[]
        for meta in saved:
            row=AssignmentFile(assignment_id=aid,uploaded_by=current_user().id,**meta);db.session.add(row);db.session.flush();rows.append(file_dto(row))
        return {'items':rows},201
    except BaseException:
        for meta in saved:(root()/meta['storage_key']).unlink(missing_ok=True)
        raise


@bp.get('/assignment-files/<int:fid>/download')
def download_assignment_file(fid):
    need(current_user() is not None,'UNAUTHORIZED','Bạn cần đăng nhập',401)
    f=get(AssignmentFile,fid);assignment(f.assignment_id)
    return download(f.storage_key,f.original_filename,f.sha256)


@bp.route('/assignments/<int:aid>/evaluation-rounds',methods=['GET','POST'])
@command()
def evaluation_rounds(aid):
    a=assignment(aid,staff=True)
    if request.method=='GET':
        return {'items':[round_report(r,a) for r in PeerRound.query.filter_by(assignment_id=aid).order_by(PeerRound.id.desc())]}
    state(a,['published','active','assessment'])
    b=json_body();start=timestamp(b.get('opens_at')) if b.get('opens_at') else now();end=timestamp(b.get('closes_at'))
    need(start<end and end>now(),message='Thời gian đợt đánh giá không hợp lệ')
    need(not PeerRound.query.filter(PeerRound.assignment_id==aid,PeerRound.status=='open',PeerRound.opens_at<end,PeerRound.closes_at>start).first(),'ROUND_EXISTS','Thời gian trùng với đợt đánh giá khác; đóng đợt cũ hoặc chọn khoảng khác',409)
    r=PeerRound(assignment_id=aid,title=textval(b,'title'),opens_at=start,closes_at=end,status='open',criteria_json=[{'code':'attitude','max':10},{'code':'quality','max':10}])
    db.session.add(r);db.session.flush();audit('evaluation.round_created',r,cid=a.course_id)
    return round_report(r,a),201


@bp.post('/evaluation-rounds/<int:rid>/close')
@command()
def close_evaluation(rid):
    r=get(PeerRound,rid);a=assignment(r.assignment_id,staff=True);version(r)
    r.status='closed';audit('evaluation.round_closed',r,cid=a.course_id)
    return round_report(r,a)


def round_report(r,a):
    reviews=MatrixReview.query.filter_by(round_id=r.id).all() if r.status=='closed' or r.closes_at<now() else []
    groups=Project.query.filter_by(assignment_id=a.id).all()
    expected=0;members={}
    for p in groups:
        ids=[m.user_id for m in AssignmentMembership.query.filter_by(project_id=p.id,status='active')]
        expected+=len(ids)*max(0,len(ids)-1)
        for uid in ids:members[(p.id,uid)]=p.name
    items=[]
    for (pid,uid),name in members.items():
        received=[x for x in reviews if x.project_id==pid and x.reviewee_id==uid]
        sent=[x for x in reviews if x.project_id==pid and x.reviewer_id==uid]
        attitude=[x.attitude10 or x.attitude*2 for x in received];quality=[x.quality10 or x.quality*2 for x in received]
        items.append({'user':user_brief(uid),'project_id':pid,'group_name':name,'received':len(received),'attitude':round(sum(attitude)/len(attitude),2) if attitude else None,'quality':round(sum(quality)/len(quality),2) if quality else None})
    return {**dto(r),'phase':'closed' if r.status=='closed' or r.closes_at<now() else 'scheduled' if r.opens_at>now() else 'open','response_count':len(reviews),'expected_count':expected,'items':items}


@bp.post('/assignments/<int:aid>/visibility')
@command()
def assignment_visibility(aid):
    a=assignment(aid,staff=True)
    need(enrollment(a.course_id).role=='instructor','FORBIDDEN','Giảng viên phụ trách công bố đề bài',403)
    state(a,['draft','published','active','assessment'])
    b=json_body();version(a,b)
    visible=b.get('visible');need(isinstance(visible,bool))
    if visible and a.status=='draft':
        need(a.brief and a.due_at>now(),'POLICY_REQUIRED','Cần yêu cầu, hạn hợp lệ và bộ tiêu chí đã công bố. Mở tab Bộ tiêu chí để hoàn thiện.',409)
        a.status='published'
        if a.group_mode=='teacher':
            assigned={m.user_id for m in AssignmentMembership.query.filter_by(assignment_id=aid,status='active')}
            remaining=CourseEnrollment.query.filter_by(course_id=a.course_id,role='student',status='active').all()
            if any(e.user_id not in assigned and get(User,e.user_id).is_active for e in remaining):
                allocate_groups(a,{'team_size':a.group_max,'method':a.group_method})
    a.is_hidden=not visible
    audit('assignment.shown' if visible else 'assignment.hidden',a,cid=a.course_id)
    return dto(a)
