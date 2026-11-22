"""Add explicitly labelled, reproducible demo content to the separate demo DB only."""
from datetime import timedelta
from decimal import Decimal
import hashlib, secrets
from io import BytesIO
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from flask import current_app
from ..extensions import db
from ..common.clock import utcnow
from ..common.storage import root
from ..models import User,Project,Task
from ..models.academic import (RuntimeSetting,Assignment,Criterion,TaskParticipant,TaskCriterion,
    EvidenceAsset,EvidenceRevision,EvidenceRevisionAsset,TaskSubmission,PeerRound)
from ..models.teamwork import (TaskBranch,BranchMergeRequest,Vault,StoredFile,VaultEntry,Message,
    Meeting,MeetingAttendance,MeetingTaskDraft,DeadlineExtension,MatrixReview,AcademicGrade)


def seed_showcase():
    if current_app.config.get('APP_ENV') not in ('development','test') or not current_app.config.get('DEMO_CLOCK_ENABLED'):
        raise RuntimeError('Chỉ nạp dữ liệu minh họa vào môi trường demo')
    if not db.session.get(RuntimeSetting,'demo_fixture'):
        raise RuntimeError('Chạy seed-demo trước')
    if db.session.get(RuntimeSetting,'ui_showcase_v1'):
        return False
    users={k:User.query.filter_by(email=k+'@gmail.com').one() for k in ('sv1','sv2','sv3','gv1')}
    leader,teacher=users['sv1'],users['gv1']
    p=Project.query.filter_by(name='G01',mode='academic',assignment_id=db.session.get(RuntimeSetting,'demo_fixture').value['assignment_id']).one()
    assignment=db.session.get(Assignment,p.assignment_id)
    criterion=Criterion.query.filter_by(policy_id=assignment.published_policy_id).order_by(Criterion.id).first()
    if not criterion:raise RuntimeError('Demo cần rubric đã công bố')
    at=utcnow().replace(second=0,microsecond=0)
    # Scenarios use real task/submission models so every number in the UI is computed.
    plans=[
        ('Xác định mục tiêu khảo sát','sv1','done',-9),
        ('Thiết kế câu hỏi nghiên cứu','sv2','done',-8),
        ('Tổng hợp nguồn tham khảo','sv3','done',-7),
        ('Kiểm tra biểu mẫu khảo sát','sv1','done',-6),
        ('Chuẩn hóa dữ liệu đầu vào','sv2','done',-5),
        ('Phân nhóm dữ liệu phản hồi','sv3','done',-4),
        ('Rà soát cấu trúc báo cáo','sv1','done',-3),
        ('Trực quan hóa kết quả','sv2','done',-2),
        ('Xây dựng bảng kết quả','sv3','done',-1),
        ('Kiểm tra kết quả phân tích','sv2','review',2),
        ('Hoàn thiện bản trình bày','sv3','review',4),
        ('Viết phần kết luận và kiến nghị','sv1','in_progress',5),
        ('Đối chiếu minh chứng nhóm','sv2','in_progress',6),
        ('Chuẩn bị tài liệu thuyết trình','sv3','in_progress',7),
        ('Tổng duyệt báo cáo cuối kỳ','sv1','todo',10),
        ('Nộp báo cáo hoàn thiện','sv2','todo',14),
    ]
    tasks={}
    for i,(title,key,status,offset) in enumerate(plans):
        actor=users[key]; due=at+timedelta(days=offset)
        task=Task(project_id=p.id,title=title,description='Dữ liệu minh họa: '+title+'.',
                  created_by=leader.id,assignee_id=actor.id,primary_assignee_id=actor.id,
                  status=status,due_at=due,original_due_at=due,points=2,priority='medium',
                  created_at=(at-timedelta(days=14)).replace(tzinfo=None),
                  updated_at=(at-timedelta(days=1)).replace(tzinfo=None))
        db.session.add(task);db.session.flush();tasks[title]=task
        db.session.add_all([TaskParticipant(task_id=task.id,user_id=actor.id,role='responsible'),
                            TaskCriterion(task_id=task.id,criterion_id=criterion.id)])
        if status not in ('done','review'):continue
        submitted=due-timedelta(hours=12) if status=='done' else at-timedelta(days=3 if i==9 else 1)
        asset=EvidenceAsset(task_id=task.id,uploaded_by=actor.id,kind='link',
            url='https://example.org/teamsync-demo',size_bytes=0,integrity_status='external_mutable',created_at=submitted)
        db.session.add(asset);db.session.flush()
        rev=EvidenceRevision(task_id=task.id,revision_no=1,description='Minh chứng minh họa cho '+title,created_by=actor.id,created_at=submitted)
        db.session.add(rev);db.session.flush();db.session.add(EvidenceRevisionAsset(revision_id=rev.id,asset_id=asset.id))
        submission=TaskSubmission(task_id=task.id,revision_id=rev.id,attempt_no=1,submitted_by=actor.id,
            participant_ids=[actor.id],received_at=submitted,submitted_due_at=due,
            status='accepted' if status=='done' else 'pending',
            reviewed_by=leader.id if status=='done' else None,
            reviewed_at=submitted+timedelta(hours=2) if status=='done' else None,
            review_reason='Đã kiểm tra kết quả minh họa.' if status=='done' else None)
        db.session.add(submission);db.session.flush();task.latest_submission_id=submission.id
        if status=='done':task.completed_at=(submitted+timedelta(hours=2)).replace(tzinfo=None)
        branch=TaskBranch(task_id=task.id,author_id=actor.id,name=f'demo/task-{task.id}',status='merged' if status=='done' else 'open')
        db.session.add(branch);db.session.flush();db.session.add(BranchMergeRequest(branch_id=branch.id,submission_id=submission.id))
    internal=Vault.query.filter_by(project_id=p.id,kind='internal').first() or Vault(project_id=p.id,kind='internal')
    final=Vault.query.filter_by(project_id=p.id,kind='final').first() or Vault(project_id=p.id,kind='final')
    db.session.add_all([internal,final]);db.session.flush()
    raw='DỮ LIỆU MINH HỌA — Tóm tắt báo cáo khảo sát TeamSync.\n'.encode()
    key=secrets.token_hex(16);(root()/key).write_bytes(raw)
    doc=StoredFile(project_id=p.id,uploaded_by=leader.id,kind='file',storage_key=key,
                   original_filename='bao-cao-minh-hoa.txt',mime_type='text/plain',size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
    link=StoredFile(project_id=p.id,uploaded_by=users['sv2'].id,kind='link',url='https://example.org/teamsync-demo',size_bytes=0)
    image=Image.new('RGB',(720,400),'#f8f9fb');draw=ImageDraw.Draw(image)
    font_path=Path(__file__).resolve().parents[1]/'static'/'fonts'/'DejaVuSans.ttf'
    font=ImageFont.truetype(str(font_path),22);small=ImageFont.truetype(str(font_path),16)
    draw.text((40,28),'Kết quả khảo sát · Dữ liệu minh họa',font=font,fill='#293244')
    for i,(label,value,color) in enumerate([('Hài lòng',64,'#c8102e'),('Bình thường',22,'#d98b99'),('Cần cải thiện',14,'#e5c1c8')]):
        y=100+i*84
        draw.text((42,y),label,font=small,fill='#596579')
        draw.rounded_rectangle((210,y,210+value*6,y+28),radius=8,fill=color)
        draw.text((225+value*6,y+3),str(value)+'%',font=small,fill='#293244')
    buffer=BytesIO();image.save(buffer,format='PNG');raw_image=buffer.getvalue()
    image_key=secrets.token_hex(16);(root()/image_key).write_bytes(raw_image)
    picture=StoredFile(project_id=p.id,uploaded_by=users['sv3'].id,kind='file',storage_key=image_key,
                       original_filename='bieu-do-minh-hoa.png',mime_type='image/png',size_bytes=len(raw_image),sha256=hashlib.sha256(raw_image).hexdigest())
    db.session.add_all([doc,link,picture]);db.session.flush()
    db.session.add_all([VaultEntry(vault_id=internal.id,file_id=doc.id,submitted_by=leader.id,title='Bản thảo báo cáo minh họa'),
        VaultEntry(vault_id=internal.id,file_id=link.id,submitted_by=users['sv2'].id,title='Tài liệu tham khảo minh họa'),
        VaultEntry(vault_id=internal.id,file_id=picture.id,submitted_by=users['sv3'].id,title='Biểu đồ khảo sát minh họa'),
        VaultEntry(vault_id=final.id,file_id=doc.id,submitted_by=leader.id,title='Báo cáo kết quả minh họa',note='Bản nộp mẫu để thử quyền truy cập.')])
    for i,(key,content,file_ids) in enumerate([
        ('sv1','Mình đã cập nhật kế hoạch. Cả nhóm xem phần việc được phân công nhé.',[]),
        ('sv2','Mình gửi tài liệu tham khảo để cả nhóm đối chiếu.',[link.id]),
        ('sv3','Mình gửi biểu đồ minh họa để cả nhóm cùng xem.',[picture.id]),
        ('sv1','Cảm ơn mọi người, hãy gửi review khi sản phẩm sẵn sàng.',[]) ]):
        db.session.add(Message(project_id=p.id,sender_id=users[key].id,content=content,file_ids=file_ids,
                               client_key=f'demo-message-{i}',created_at=at-timedelta(days=3-i//2)))
    meeting=Meeting(project_id=p.id,host_id=leader.id,title='Họp tiến độ hàng tuần (minh họa)',
        room_name='teamsync-demo-'+secrets.token_hex(12),status='ended',
        notes='- Hoàn thiện kết luận báo cáo\n- Rà soát tài liệu trình bày',ended_at=at-timedelta(days=1))
    db.session.add(meeting);db.session.flush()
    for u in (users['sv1'],users['sv2'],users['sv3']):
        db.session.add(MeetingAttendance(meeting_id=meeting.id,user_id=u.id,joined_at=at-timedelta(days=1),
                                         last_seen_at=at-timedelta(days=1)+timedelta(minutes=20),active_seconds=1200))
    line='Hoàn thiện kết luận báo cáo'
    db.session.add(MeetingTaskDraft(meeting_id=meeting.id,title=line,source_line=line,source_hash=hashlib.sha256(line.casefold().encode()).hexdigest()))
    t=tasks['Đối chiếu minh chứng nhóm']
    db.session.add(DeadlineExtension(task_id=t.id,requested_by=users['sv2'].id,reason='Cần thêm thời gian đối chiếu các nguồn.',
        old_due_at=t.due_at,requested_due_at=min(t.due_at+timedelta(days=1),assignment.due_at),status='pending'))
    if not PeerRound.query.filter_by(assignment_id=assignment.id,status='open').first():
        r=PeerRound(assignment_id=assignment.id,title='Đánh giá cộng tác cuối kỳ (minh họa)',opens_at=at-timedelta(days=1),
                    closes_at=at+timedelta(days=14),status='open',criteria_json=[{'code':'attitude','max':10},{'code':'quality','max':10}])
        db.session.add(r);db.session.flush()
        for reviewer,reviewee in [('sv2','sv1'),('sv3','sv1'),('sv1','sv2'),('sv3','sv2'),('sv1','sv3'),('sv2','sv3')]:
            db.session.add(MatrixReview(round_id=r.id,project_id=p.id,reviewer_id=users[reviewer].id,reviewee_id=users[reviewee].id,
                attitude=4,quality=4,attitude10=8,quality10=9,comment='Phản hồi minh họa.'))
    if not AcademicGrade.query.filter_by(project_id=p.id,student_id=users['sv1'].id).first():
        db.session.add(AcademicGrade(project_id=p.id,student_id=leader.id,assessor_id=teacher.id,revision=1,
            score=Decimal('8.50'),rationale='Điểm minh họa dựa trên bản nộp và rubric.',context_json={'demo':True}))
    db.session.add(RuntimeSetting(key='ui_showcase_v1',value={'project_id':p.id,'description':'Dữ liệu minh họa để trải nghiệm giao diện'}))
    db.session.commit()
    return True
