"""Close old routes that could expose internal evidence after the new RBAC boundary."""
from flask import request
from .services import *


def install_privacy(app):
    @app.before_request
    def academic_boundary():
        path=request.path
        if not current_user():return
        # Academic-only deployment: retired legacy business APIs cannot bypass the new rules.
        if path.startswith('/api/') and not path.startswith(('/api/v1/','/api/auth/')):
            if not path.startswith('/api/admin/templates'):
                need(False,'LEGACY_API_RETIRED','Dùng API học thuật /api/v1',410)
        if not path.startswith('/api/v1/'):return
        if current_user().role=='admin':
            allowed=('/api/v1/auth/','/api/v1/admin/','/api/v1/me/preferences','/api/v1/me/profile','/api/v1/me/password','/api/v1/workspace-templates','/api/v1/workflow/admin')
            need(path.startswith(allowed),'FORBIDDEN','Ops chỉ quản trị kỹ thuật, không truy cập dữ liệu học tập',403)
            if path.endswith('/password'):
                need(False,'SSO_MANAGED','Ops không đặt mật khẩu thay người dùng học thuật',403)
            return
        args=request.view_args or {}
        pid=args.get('pid') if path.startswith('/api/v1/projects/') else None
        tid=args.get('tid')
        if tid:
            pid=get(Task,tid).project_id
        if args.get('sid'):
            pid=get(Task,get(TaskSubmission,args['sid']).task_id).project_id
        if pid:
            p=db.session.get(Project,pid)
            if p and p.mode=='academic':
                e=enrollment(get(Assignment,p.assignment_id).course_id)
                if e and e.role in STAFF:
                    if any(x in path for x in ('/audit','/comments','/claims','/change-requests','/invitations')):
                        need(False,'FORBIDDEN','Nội dung vận hành nội bộ chỉ dành cho nhóm',403)
                    if request.method!='GET' and not any(x in path for x in ('/help-requests',)):
                        need(False,'READ_ONLY','Giảng viên chỉ theo dõi tiến độ và đánh giá học vụ',403)


def authorize_teamwork_replay():
    path=request.path.removeprefix('/api/v1/').split('/')
    if len(path)<2 or not path[1].isdigit():return
    kind,ident=path[0],int(path[1])
    if kind=='projects' and len(path)>2 and path[2] in ('messages','files','final-submissions','meetings','apply-template','peer-matrix'):
        team(ident,leader=path[2] in ('final-submissions','apply-template'))
    if kind=='tasks' and len(path)>2 and path[2] in ('submissions','branches','extensions'):
        team(get(Task,ident).project_id)
    if kind=='meetings':team(get(Meeting,ident).project_id)
    if kind=='task-drafts':team(get(Meeting,get(MeetingTaskDraft,ident).meeting_id).project_id,leader=True)
    if kind=='extensions':team(get(Task,get(DeadlineExtension,ident).task_id).project_id,leader=True)
    if kind=='team-alerts':team(get(TeamAlert,ident).project_id,leader=True)
