"""Idempotent periodic alerts and daily, append-only Commitment snapshots."""
from celery import Celery,Task as CeleryTask
from flask import current_app
from .services import *


def evaluate_teamwork():
    from ..common.jobs import risk_lock,dispatch_outbox
    count=0
    with risk_lock() as acquired:
        if not acquired:return 0
        for p in Project.query.filter_by(mode='academic',status='active').all():
            leaders=[x.user_id for x in AssignmentMembership.query.filter_by(project_id=p.id,status='active',role='leader')]
            expected={}
            for m in AssignmentMembership.query.filter_by(project_id=p.id,status='active'):
                ci=commitment(p.id,m.user_id)
                day=now().date().isoformat()
                if not CommitmentLog.query.filter_by(project_id=p.id,user_id=m.user_id,period=day,algorithm='ci-v1').first():
                    db.session.add(CommitmentLog(project_id=p.id,user_id=m.user_id,period=day,score=ci['score'],metrics=ci['metrics']))
                if ci['score'] is not None and ci['score']<60 and not ci['provisional']:
                    expected[f'ci:{p.id}:{m.user_id}']={'rule':'low_commitment','user_id':m.user_id,
                        'message':f"{ci['user']['full_name']}: chỉ số cam kết {ci['score']}/100"}
            for s in TaskSubmission.query.join(Task,Task.id==TaskSubmission.task_id).filter(Task.project_id==p.id,
                    TaskSubmission.status=='pending',TaskSubmission.received_at<now()-timedelta(hours=48)):
                expected[f'mr:{s.id}']={'rule':'stale_mr','task_id':s.task_id,'user_id':s.submitted_by,
                    'message':f'Merge Request #{s.id} đã chờ duyệt hơn 48 giờ'}
            existing={x.subject_key:x for x in TeamAlert.query.filter_by(project_id=p.id)}
            for key,data in expected.items():
                alert=existing.get(key)
                fresh=not alert or alert.status=='resolved'
                if not alert:
                    alert=TeamAlert(project_id=p.id,subject_key=key,**data)
                    db.session.add(alert)
                    db.session.flush()
                alert.status='open';alert.message=data['message']
                if fresh:
                    db.session.add(OutboxEvent(event_type='team.alert',aggregate_id=alert.id,
                        payload={'recipients':leaders,'path':f'/projects/{p.id}?tab=studio&pane=insights','subject':alert.message}))
                    count+=1
            for key,alert in existing.items():
                if key not in expected:alert.status='resolved'
        db.session.commit()
    dispatch_outbox()
    return count


def init_celery(app):
    class FlaskTask(CeleryTask):
        def __call__(self,*args,**kwargs):
            with app.app_context():return self.run(*args,**kwargs)
    celery=Celery(app.name,task_cls=FlaskTask)
    celery.conf.update(broker_url=app.config.get('CELERY_BROKER_URL','redis://localhost:6379/0'),
        result_backend=app.config.get('CELERY_RESULT_BACKEND','redis://localhost:6379/1'),
        task_ignore_result=True,timezone='UTC',beat_schedule={
            'teamwork-every-15m':{'task':'teamsync.evaluate_teamwork','schedule':900},
            'outbox-every-30s':{'task':'teamsync.dispatch_outbox','schedule':30}})
    celery.task(name='teamsync.evaluate_teamwork')(evaluate_teamwork)
    from ..common.jobs import dispatch_outbox
    celery.task(name='teamsync.dispatch_outbox')(dispatch_outbox)
    app.extensions['celery']=celery
    @app.cli.command('teamwork-evaluate')
    def run_evaluation():
        print(f'Đã mở {evaluate_teamwork()} cảnh báo mới')
