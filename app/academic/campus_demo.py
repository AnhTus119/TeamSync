"""Additional opt-in local-demo scenarios for navigating multiple assignments."""
from datetime import timedelta
from flask import current_app
from ..extensions import db
from ..models import User,Project,ProjectMember,Task
from ..models.academic import (RuntimeSetting,CourseOffering,CourseEnrollment,Assignment,
    AssessmentPolicy,Criterion,CriterionLevel,AssignmentMembership,TaskParticipant,TaskCriterion,
    EvidenceAsset,EvidenceRevision,EvidenceRevisionAsset,TaskSubmission)
from ..models.teamwork import TaskBranch,BranchMergeRequest,Message,Vault,StoredFile,VaultEntry,Meeting
from ..common.clock import utcnow


def seed_campus_demo():
    if current_app.config.get('APP_ENV') not in ('development','test') or not current_app.config.get('DEMO_CLOCK_ENABLED'):
        raise RuntimeError('Dữ liệu campus chỉ dùng trong demo')
    if db.session.get(RuntimeSetting,'campus_demo_v2'):
        return False
    if not db.session.get(RuntimeSetting,'demo_fixture'):
        raise RuntimeError('Cần khởi tạo demo trước')
    at=utcnow().replace(second=0,microsecond=0)
    created=[]
    for course in CourseOffering.query.order_by(CourseOffering.id).all():
        # Only the built-in sample courses; do not insert content into user-created classes.
        if course.code not in ('WEB01','WEB02','WEB03','WEB04'):
            continue
        roster=CourseEnrollment.query.join(User,User.id==CourseEnrollment.user_id).filter(
            CourseEnrollment.course_id==course.id,CourseEnrollment.role=='student',
            CourseEnrollment.status=='active',User.email.in_([f'sv{i}@gmail.com' for i in range(1,5)])).order_by(CourseEnrollment.user_id).all()
        teacher=CourseEnrollment.query.filter_by(course_id=course.id,role='instructor',status='active').first()
        if not roster or not teacher:continue
        title={'WEB01':'Bài tập 02 · Phân tích và trực quan hóa dữ liệu','WEB02':'Bài tập 02 · Thiết kế trải nghiệm ứng dụng','WEB03':'Bài tập 02 · Kiểm thử và tối ưu truy vấn','WEB04':'Bài tập 02 · Xây dựng website quản lý học tập'}[course.code]
        a=Assignment(course_id=course.id,title=title,brief='Dữ liệu minh họa: làm việc theo nhóm, nộp minh chứng, review và hoàn thiện sản phẩm. Bàn giao báo cáo, sản phẩm và bản trình bày.',status='active',opens_at=at-timedelta(days=10),due_at=at+timedelta(days=21),group_min=1,group_max=5)
        db.session.add(a);db.session.flush();created.append(a.id)
        policy=AssessmentPolicy(assignment_id=a.id,revision=1,status='published',published_at=at-timedelta(days=10))
        db.session.add(policy);db.session.flush();a.published_policy_id=policy.id
        criterion=Criterion(policy_id=policy.id,code='PRODUCT',title='Chất lượng sản phẩm và minh chứng',weight=100,max_score=10,description='Sản phẩm đúng yêu cầu, có kiểm thử và minh chứng rõ ràng.')
        db.session.add(criterion);db.session.flush()
        for ordinal,(label,score) in enumerate([('Cần bổ sung',2),('Đạt yêu cầu',6),('Tốt',8),('Xuất sắc',10)]):
            db.session.add(CriterionLevel(criterion_id=criterion.id,label=label,score=score,description=label,ordinal=ordinal))
        # Two independently scoped teams per assignment whenever the roster permits.
        chunks=[roster[::2],roster[1::2]]
        for number,members in enumerate(chunks,1):
            if not members:continue
            leader=members[0].user_id
            p=Project(workspace_id=course.workspace_id,name=f'G{number:02} · {"Aurora" if number==1 else "Orbit"}',description='Nhóm minh họa bài tập 02',created_by=leader,assignment_id=a.id,mode='academic',status='active')
            db.session.add(p);db.session.flush()
            for i,e in enumerate(members):
                db.session.add(AssignmentMembership(assignment_id=a.id,project_id=p.id,user_id=e.user_id,role='leader' if i==0 else 'member',status='active'))
                db.session.add(ProjectMember(project_id=p.id,user_id=e.user_id,project_role='manager' if i==0 else 'member'))
            plans=[('Khảo sát yêu cầu và phân công','done',-5),('Thiết kế cấu trúc sản phẩm','done',-3),('Phát triển bản thử nghiệm','in_progress',3),('Kiểm tra bộ dữ liệu đầu vào','in_progress',5),('Review sản phẩm vòng 1','review',7),('Hoàn thiện báo cáo nhóm','todo',10),('Tổng duyệt bài trình bày','todo',14),('Nộp bài cuối kỳ','todo',18)]
            for i,(name,status,days) in enumerate(plans):
                uid=members[i%len(members)].user_id;due=at+timedelta(days=days)
                task=Task(project_id=p.id,title=name,description='Minh họa có thể thao tác: '+name,status=status,priority='high' if i==4 else 'medium',points=2,created_by=leader,assignee_id=uid,primary_assignee_id=uid,due_at=due,original_due_at=due,created_at=(at-timedelta(days=10)).replace(tzinfo=None))
                db.session.add(task);db.session.flush()
                db.session.add(TaskParticipant(task_id=task.id,user_id=uid,role='responsible'))
                db.session.add(TaskCriterion(task_id=task.id,criterion_id=criterion.id))
                if status in ('done','review'):
                    sent=due-timedelta(hours=12) if status=='done' else at-timedelta(hours=4)
                    asset=EvidenceAsset(task_id=task.id,uploaded_by=uid,kind='link',url='https://example.org/teamsync-demo',size_bytes=0,integrity_status='external_mutable',created_at=sent)
                    db.session.add(asset);db.session.flush()
                    rev=EvidenceRevision(task_id=task.id,revision_no=1,description='Minh chứng minh họa',created_by=uid,created_at=sent)
                    db.session.add(rev);db.session.flush();db.session.add(EvidenceRevisionAsset(revision_id=rev.id,asset_id=asset.id))
                    submission=TaskSubmission(task_id=task.id,revision_id=rev.id,attempt_no=1,submitted_by=uid,participant_ids=[uid],received_at=sent,submitted_due_at=due,status='accepted' if status=='done' else 'pending',reviewed_by=leader if status=='done' else None,reviewed_at=sent+timedelta(hours=2) if status=='done' else None,review_reason='Đã kiểm tra minh họa.' if status=='done' else None)
                    db.session.add(submission);db.session.flush();task.latest_submission_id=submission.id
                    if status=='done':task.completed_at=(sent+timedelta(hours=2)).replace(tzinfo=None)
                    branch=TaskBranch(task_id=task.id,author_id=uid,name=f'demo/campus-{task.id}',status='merged' if status=='done' else 'open')
                    db.session.add(branch);db.session.flush();db.session.add(BranchMergeRequest(branch_id=branch.id,submission_id=submission.id))
            internal=Vault(project_id=p.id,kind='internal');final=Vault(project_id=p.id,kind='final')
            db.session.add_all([internal,final]);db.session.flush()
            file=StoredFile(project_id=p.id,uploaded_by=leader,kind='link',url='https://example.org/teamsync-demo',size_bytes=0)
            db.session.add(file);db.session.flush()
            db.session.add(VaultEntry(vault_id=internal.id,file_id=file.id,submitted_by=leader,title='Đề cương tham khảo (minh họa)'))
            db.session.add(VaultEntry(vault_id=final.id,file_id=file.id,submitted_by=leader,title='Sản phẩm bàn giao mẫu',note='Liên kết minh họa để thử luồng nộp bài.'))
            db.session.add(Meeting(project_id=p.id,host_id=leader,title='Tổng kết sprint (minh họa)',room_name=f'teamsync-campus-demo-{p.id}',status='ended',notes='Đã phân công phát triển và kiểm thử. Cần hoàn thiện báo cáo trước hạn.',ended_at=at-timedelta(days=1)))
            db.session.add(Message(project_id=p.id,sender_id=leader,client_key='campus-welcome',content='Dữ liệu demo: nhóm đã chốt phân công. Mở Kanban để xem việc đang làm và yêu cầu review.'))
    db.session.add(RuntimeSetting(key='campus_demo_v2',value={'assignment_ids':created}))
    db.session.commit()
    return True
