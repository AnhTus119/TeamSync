"""Session/CSRF-authenticated Socket.IO events; targeted delivery rechecks membership."""
import secrets, time
from collections import defaultdict,deque
from flask import request,session
from flask_socketio import SocketIO,join_room,disconnect
from werkzeug.exceptions import HTTPException
from .services import *

socketio=SocketIO()
connections={}
rate=defaultdict(deque)


def init_realtime(app):
    socketio.init_app(app,async_mode='threading',message_queue=app.config.get('SOCKETIO_MESSAGE_QUEUE') or None,
                     manage_session=False)
    app.extensions['team_socketio']=socketio


def authorize_socket():
    u=current_user()
    if not u or u.role=='admin':
        disconnect()
        return False
    return True


@socketio.on('connect')
def connect(auth):
    auth=auth if isinstance(auth,dict) else {}
    supplied=auth.get('csrf','')
    if not isinstance(supplied,str) or not session.get('csrf') or not secrets.compare_digest(supplied,session['csrf']):
        return False
    if not current_user() or current_user().role=='admin':
        return False
    connections[request.sid]={'uid':current_user().id,'pid':None}
    return True


@socketio.on('disconnect')
def on_disconnect(reason=None):
    connections.pop(request.sid,None)
    rate.pop(request.sid,None)


def socket_command(fn):
    def wrapped(body):
        if not authorize_socket():return {'error':'UNAUTHORIZED'}
        try:
            need(isinstance(body,dict))
            value=fn(body)
            db.session.commit()
            return {'data':value}
        except HTTPException as e:
            db.session.rollback()
            if e.response is not None:
                return {'error':e.response.get_json()['error'],'status':e.response.status_code}
            return {'error':str(e.description),'status':e.code}
        except Exception:
            db.session.rollback()
            return {'error':'Không thể xử lý yêu cầu','status':409}
    return wrapped


@socketio.on('team:join')
@socket_command
def join_team(body):
    pid=integer(body.get('project_id'))
    team(pid)
    connections[request.sid]['pid']=pid
    return {'project_id':pid}


@socketio.on('chat:send')
@socket_command
def chat_send(body):
    pid=integer(body.get('project_id'))
    team(pid,mutable=True)
    q=rate[request.sid]
    while q and q[0]<time.monotonic()-60:q.popleft()
    need(len(q)<30,'RATE_LIMITED','Gửi tin quá nhanh',429)
    q.append(time.monotonic())
    m=send_message(pid,body)
    return message_dto(m)


def publish_team(pid,event,payload):
    """No persistent private room: revalidate scope before each payload is delivered.
    Multi-process fanout uses Redis through SocketIO plus per-process listeners;
    HTTP polling remains the durable replay source.
    """
    a=get(Assignment,get(Project,pid).assignment_id)
    active={m.user_id for m in AssignmentMembership.query.filter_by(project_id=pid,status='active')
            if enrollment(a.course_id,m.user_id) and enrollment(a.course_id,m.user_id).role=='student'
            and get(User,m.user_id).is_active}
    for sid,c in list(connections.items()):
        if c['pid']==pid and c['uid'] in active:
            socketio.emit(event,payload,to=sid)


# Events emit after the HTTP transaction has committed. A missing event can always be replayed by cursor.
from sqlalchemy import event
from sqlalchemy.orm import Session

@event.listens_for(Session,'before_flush')
def collect_events(s,ctx,instances):
    from ..models import Task
    from flask import has_app_context
    if not has_app_context():return
    targets=s.info.setdefault('team_changes',set())
    for x in list(s.new)+list(s.dirty):
        if isinstance(x,Message):targets.add((x.project_id,'chat:changed'))
        elif isinstance(x,Task):targets.add((x.project_id,'kanban:changed'))


@event.listens_for(Session,'after_commit')
def commit_events(s):
    from flask import has_app_context
    targets=s.info.pop('team_changes',set())
    if not has_app_context() or s.in_nested_transaction():return
    # No DB reads are allowed from after_commit. Only an opaque invalidation is broadcast;
    # clients re-fetch through authorization-protected REST endpoints.
    for pid,name in targets:
        for sid,c in list(connections.items()):
            if c['pid']==pid:socketio.emit(name,{'project_id':pid},to=sid)


@event.listens_for(Session,'after_rollback')
def rollback_events(s):s.info.pop('team_changes',None)
