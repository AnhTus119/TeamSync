"""Deterministic local demo. Runs once; never resets user changes on restart."""
import hashlib
from datetime import timedelta
from werkzeug.security import generate_password_hash
from .core import *
from ..models import Workspace, WorkspaceMember, ProjectMember
from ..models.teamwork import Meeting
from ..models.workflow import GroupDelivery

def seed_demo():
    if db.session.get(RuntimeSetting,'workspace_demo_v2'):return
    need(not CourseOffering.query.first(),message='Dùng database mới cho dữ liệu demo mới; không tự ghi đè dữ liệu cũ')
    password=generate_password_hash('12345')
    def user(email,name,role='user'):
        u=User(email=email,full_name=name,role=role,password_hash=password);db.session.add(u);db.session.flush();return u
    admin=user('admin@gmail.com','Quản trị hệ thống','admin');gv=user('gv1@gmail.com','Giảng viên Nguyễn Minh','instructor')
    students=[user(f'sv{i}@gmail.com',f'Sinh viên {i:02}') for i in range(1,37)]
    courses=[('CNTT1188','Lập trình Web'),('CNTT1117','Phân tích và thiết kế hệ thống'),('CNTT1159','Quản lý dự án Công nghệ thông tin'),('TIKT1130','Cơ sở dữ liệu'),('CNTT1152','Hệ quản trị cơ sở dữ liệu'),('CNTT1180','Lập trình Python'),('CNTT1153','Lập trình Java'),('CNTT1140','Trí tuệ nhân tạo')]
    at=now()
    for ci,(code,title) in enumerate(courses):
        w=Workspace(name=code,description=title,owner_id=gv.id);db.session.add(w);db.session.flush()
        c=CourseOffering(code=code+'-04',title=title,term='HK1 · 2026–2027',status='active',workspace_id=w.id,created_by=gv.id);db.session.add(c);db.session.flush()
        for u in [gv]+students:
            db.session.add(WorkspaceMember(workspace_id=w.id,user_id=u.id,role='owner' if u==gv else 'member'))
            db.session.add(CourseEnrollment(course_id=c.id,user_id=u.id,role='instructor' if u==gv else 'student',student_code=None if u==gv else f'SV{u.id-2:03}'))
        a=Assignment(course_id=c.id,title='Xây dựng website quản lý thư viện' if ci==0 else f'Bài tập nhóm — {title}',brief='Xây dựng sản phẩm hoạt động, kiểm thử các luồng chính và bàn giao mã nguồn kèm báo cáo. Mỗi nhóm phân công rõ đầu ra và hạn hoàn thành.',status='active',is_hidden=False,due_at=at+timedelta(days=40),group_min=3,group_max=12,group_mode='self',formation_due_at=at+timedelta(days=10));db.session.add(a);db.session.flush()
        for gi in range(5):
            users=students[gi*6:gi*6+6]
            p=Project(name=f'Nhóm {gi+1:02}',description='Website quản lý thư viện' if ci==0 else title,workspace_id=w.id,created_by=users[0].id,assignment_id=a.id,mode='academic',status='active');db.session.add(p);db.session.flush()
            for i,u in enumerate(users):
                db.session.add(AssignmentMembership(assignment_id=a.id,project_id=p.id,user_id=u.id,role='leader' if i==0 else 'member'))
                db.session.add(ProjectMember(project_id=p.id,user_id=u.id,project_role='manager' if i==0 else 'member'))
            names=['Thiết kế giao diện đăng nhập','Xây dựng API quản lý sách','Thiết kế cơ sở dữ liệu','Kiểm thử phân quyền','Tổng hợp mã nguồn','Viết báo cáo sản phẩm'] if ci==0 else ['Phân tích yêu cầu','Xây dựng sản phẩm','Kiểm thử','Tổng hợp báo cáo']
            for ti,name in enumerate(names):
                status=['in_progress','todo','done','review','in_progress','todo'][ti]
                due=at+timedelta(days=ti+2)
                if ti==0:due=at+timedelta(hours=20)
                if ti==4:due=at-timedelta(hours=12)
                t=Task(project_id=p.id,title=name,description='Bàn giao tài liệu hoặc mã nguồn có thể mở và kiểm tra; mô tả kết quả và cách sử dụng.',status=status,priority='high' if ti==0 else 'medium',points=[2,3,2,1,3,2][ti],created_by=users[0].id,assignee_id=users[(ti+1)%6].id,primary_assignee_id=users[(ti+1)%6].id,due_at=due,original_due_at=due,created_at=(at-timedelta(days=7)).replace(tzinfo=None));db.session.add(t);db.session.flush()
                people=[users[(ti+1)%6]]+([users[(ti+2)%6]] if ti==0 else [])
                for k,u in enumerate(people):db.session.add(TaskParticipant(task_id=t.id,user_id=u.id,role='responsible' if k==0 else 'collaborator'))
                db.session.add(AuditEvent(action='task.created',entity_type='task',entity_id=t.id,project_id=p.id,actor_id=users[0].id,request_id='seed',created_at=at-timedelta(days=7)))
                if ti in (0,2,3):
                    from ..common.storage import root
                    content=f'# {name}\n\nSản phẩm mẫu để kiểm tra luồng duyệt và bàn giao.\n'.encode();key=hashlib.md5(f'demo-{t.id}'.encode()).hexdigest();dest=root()/key;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(content)
                    asset=EvidenceAsset(task_id=t.id,uploaded_by=people[0].id,kind='file',storage_key=key,original_filename=f'san-pham-{t.id}.txt',sha256=hashlib.sha256(content).hexdigest(),size_bytes=len(content),integrity_status='fixed_file');db.session.add(asset);db.session.flush()
                    r=EvidenceRevision(task_id=t.id,revision_no=1,description='Bản sản phẩm mẫu',created_by=people[0].id);db.session.add(r);db.session.flush();db.session.add(EvidenceRevisionAsset(revision_id=r.id,asset_id=asset.id))
                    s=TaskSubmission(task_id=t.id,revision_id=r.id,attempt_no=1,submitted_by=people[0].id,participant_ids=[u.id for u in people],received_at=at-timedelta(days=1),submitted_due_at=due,status='returned' if ti==0 else 'accepted' if ti==2 else 'pending',review_reason='Bổ sung trạng thái báo lỗi khi nhập sai mật khẩu và kiểm tra trên điện thoại.' if ti==0 else '',reviewed_by=users[0].id if ti!=3 else None,reviewed_at=at if ti!=3 else None);db.session.add(s);db.session.flush();t.latest_submission_id=s.id
                    if ti==2:t.completed_at=at.replace(tzinfo=None)
                    db.session.add(AuditEvent(action='submission.returned' if ti==0 else 'submission.accepted' if ti==2 else 'task.submitted',entity_type='task_submission',entity_id=s.id,project_id=p.id,actor_id=users[0].id,request_id='seed',created_at=at-timedelta(hours=3)))
            if ci==0 and gi==0:db.session.add(Meeting(project_id=p.id,host_id=users[0].id,title='Thống nhất đầu ra tuần 1',room_name='seed-minutes',status='ended',notes='Thành viên tham dự: 6 thành viên.\nKết luận: ưu tiên đăng nhập và API sách; mỗi công việc có file bàn giao và hướng dẫn kiểm thử.\nLink cuộc họp: https://meet.google.com/',ended_at=at))
    db.session.add(RuntimeSetting(key='workspace_demo_v2',value={'version':2}));db.session.add(RuntimeSetting(key='demo_clock',value={}));db.session.commit()
