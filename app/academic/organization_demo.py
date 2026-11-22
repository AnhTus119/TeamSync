"""One-time local examples for assignment resources and assessment rounds."""
from datetime import timedelta
from io import BytesIO
from flask import current_app
from werkzeug.datastructures import FileStorage
from ..extensions import db
from ..models import Project
from ..models.academic import Assignment,AssignmentFile,AssignmentMembership,PeerRound,RuntimeSetting
from ..models.teamwork import MatrixReview
from ..common.clock import now
from ..common.storage import save_upload


def seed_organization_demo():
    if current_app.config.get('APP_ENV') not in ('development','test') or not current_app.config.get('DEMO_CLOCK_ENABLED'):
        raise RuntimeError('Chỉ nạp vào demo')
    if db.session.get(RuntimeSetting,'organization_demo_v1'):return False
    fixture=db.session.get(RuntimeSetting,'demo_fixture')
    if not fixture:return False
    a=db.session.get(Assignment,fixture.value['assignment_id']);at=now()
    if a.group_mode=='self' and not a.formation_due_at and a.due_at>at+timedelta(hours=2):a.formation_due_at=min(at+timedelta(days=5),a.due_at-timedelta(hours=1))
    teacher=db.session.get(Project,1).created_by
    # Use the course's actual instructor, rather than attributing files to a student leader.
    from ..models.academic import CourseEnrollment
    instructor=CourseEnrollment.query.filter_by(course_id=a.course_id,role='instructor',status='active').first()
    if instructor:teacher=instructor.user_id
    for title,content in [('yeu-cau-bai-tap.txt','ĐỀ BÀI MINH HỌA\nPhân tích khảo sát trải nghiệm học tập. Nộp báo cáo, dữ liệu và slide; ghi rõ đóng góp cá nhân.'),('huong-dan-nop-bai.txt','PHỤ LỤC MINH HỌA\nTrưởng nhóm nộp bản hoàn thiện vào Final Vault. Minh chứng nội bộ chỉ thành viên trong nhóm xem.')]:
        meta=save_upload(FileStorage(stream=BytesIO(content.encode()),filename=title))
        db.session.add(AssignmentFile(assignment_id=a.id,uploaded_by=teacher,**meta))
    project=Project.query.filter_by(assignment_id=a.id).order_by(Project.id).first()
    members=AssignmentMembership.query.filter_by(project_id=project.id,status='active').all()
    for i,title in enumerate(['Mốc 01 · Đề cương (minh họa)','Mốc 02 · Bản nháp (minh họa)']):
        r=PeerRound(assignment_id=a.id,title=title,opens_at=at-timedelta(days=10-i*3),closes_at=at-timedelta(days=8-i*3),status='closed',criteria_json=[{'code':'attitude','max':10},{'code':'quality','max':10}])
        db.session.add(r);db.session.flush()
        for sender in members:
            for receiver in members:
                if sender.user_id==receiver.user_id:continue
                db.session.add(MatrixReview(round_id=r.id,project_id=project.id,reviewer_id=sender.user_id,reviewee_id=receiver.user_id,attitude=4,quality=4,attitude10=8+i,quality10=7+i,comment='Phản hồi minh họa của đợt đánh giá.'))
    campus=db.session.get(RuntimeSetting,'campus_demo_v2')
    if campus and campus.value['assignment_ids']:
        sample=db.session.get(Assignment,campus.value['assignment_ids'][0]);sample.group_mode='teacher'
    db.session.add(RuntimeSetting(key='organization_demo_v1',value={'assignment_id':a.id}))
    db.session.commit();return True
