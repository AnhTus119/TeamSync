"""Personal task inbox: only explicitly assigned work in active memberships."""
from flask import request
from sqlalchemy import or_
from . import bp
from .services import *
from ..models import TaskDependency


@bp.get('/me/tasks')
@command()
def personal_tasks():
    uid=current_user().id
    need(current_user().role!='admin','FORBIDDEN','Ops không có công việc học tập',403)
    memberships=AssignmentMembership.query.join(Assignment,Assignment.id==AssignmentMembership.assignment_id).join(
        CourseEnrollment,db.and_(CourseEnrollment.course_id==Assignment.course_id,CourseEnrollment.user_id==uid)).filter(
        AssignmentMembership.user_id==uid,AssignmentMembership.status=='active',CourseEnrollment.role=='student',CourseEnrollment.status=='active',Assignment.is_hidden.is_(False),Assignment.status.in_(['published','active','submitted'])).all()
    pids={m.project_id for m in memberships}
    part={r.task_id:r.role for r in TaskParticipant.query.filter_by(user_id=uid).all()}
    tasks=Task.query.filter(Task.project_id.in_(pids),Task.archived_at.is_(None),or_(Task.id.in_(part),Task.primary_assignee_id==uid,Task.assignee_id==uid)).order_by(Task.due_at.asc().nullslast(),Task.id).all() if pids else []
    deps={}
    for d in TaskDependency.query.filter(TaskDependency.task_id.in_([t.id for t in tasks])).all():
        previous=db.session.get(Task,d.depends_on_id)
        if previous and previous.status!='done':deps.setdefault(d.task_id,[]).append({'id':previous.id,'title':previous.title})
    items=[];counts={k:0 for k in ('ready','in_progress','later','review','done')}
    for t in tasks:
        p=get(Project,t.project_id);a=get(Assignment,p.assignment_id);c=get(CourseOffering,a.course_id)
        if p.status in ('archived','finalized'):continue
        before_open=bool(a.opens_at and a.opens_at>now())
        bucket=('later' if t.status=='todo' and (before_open or deps.get(t.id)) else 'ready' if t.status=='todo' else t.status)
        counts[bucket]=counts.get(bucket,0)+1
        items.append({'id':t.id,'title':t.title,'status':t.status,'bucket':bucket,'version':t.version,'priority':t.priority,'due_at':iso(t.due_at),
            'course':{'id':c.id,'code':c.code,'title':c.title},'assignment':{'id':a.id,'title':a.title,'opens_at':iso(a.opens_at)},'project':{'id':p.id,'name':p.name},
            'participation':part.get(t.id,'responsible'),'blocked_by':deps.get(t.id,[]),'before_open':before_open,
            'is_overdue':bool(t.due_at and t.due_at<now() and t.status not in ('done','review'))})
    try:page=max(1,int(request.args.get('page',1)));size=max(1,min(100,int(request.args.get('page_size',100))))
    except ValueError:need(False,message='Phân trang không hợp lệ')
    return {'items':items[(page-1)*size:page*size],'total':len(items),'page':page,'page_size':size,'counts':counts,'generated_at':iso(now())}
