import json
from ..extensions import db
from ..models import ProjectTemplate,Task
from ..models.academic import TaskSubmission,RuntimeSetting
from ..models.teamwork import TaskBranch,BranchMergeRequest


def setup_teamwork():
    if not db.session.get(RuntimeSetting, 'template_catalog_seeded'):
        for name,titles in [('Đồ án CNTT',['Khảo sát và phân tích yêu cầu','Thiết kế cơ sở dữ liệu','Phát triển chức năng','Kiểm thử và hoàn thiện báo cáo']),
                            ('Nghiên cứu khoa học',['Xác định câu hỏi nghiên cứu','Tổng quan tài liệu','Thu thập và phân tích dữ liệu','Viết báo cáo kết quả'])]:
            existing = ProjectTemplate.query.filter_by(name=name).first()
            if not existing or existing.description == 'Cột chuẩn: Cần làm → Đang làm → Merge Request → Hoàn thành':
                sample = ProjectTemplate(name=name,description='Kế hoạch 4 tuần. Nhóm trưởng phân công, thành viên triển khai và gửi review; nghiệm thu sản phẩm trước khi hoàn thành. Bàn giao: báo cáo, minh chứng và bản trình bày.',
                    milestones_json=json.dumps([{'title':'Đề cương','offset_days':7},{'title':'Bản nháp','offset_days':21},{'title':'Bàn giao','offset_days':28}],ensure_ascii=False),tasks_json=json.dumps([{'title':t,'offset_days':7*(i+1),'points':3 if i<2 else 5,'milestone':'Đề cương' if i==0 else 'Bản nháp' if i<3 else 'Bàn giao'} for i,t in enumerate(titles)],ensure_ascii=False))
                if existing:
                    existing.description = sample.description
                    existing.milestones_json = sample.milestones_json
                    existing.tasks_json = sample.tasks_json
                else:
                    db.session.add(sample)
        db.session.add(RuntimeSetting(key='template_catalog_seeded',value={'ready':True}))
    for s in TaskSubmission.query.all():
        if not BranchMergeRequest.query.filter_by(submission_id=s.id).first():
            b=TaskBranch(task_id=s.task_id,author_id=s.submitted_by,name=f'legacy/submission-{s.id}',
                         status='merged' if s.status=='accepted' else 'open')
            db.session.add(b);db.session.flush()
            db.session.add(BranchMergeRequest(branch_id=b.id,submission_id=s.id))
    db.session.commit()
