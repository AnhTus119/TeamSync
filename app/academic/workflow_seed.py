"""Demo data: a Computer Science faculty (Khoa học máy tính), created once per database.

Every instructor, coordinator and student has a real login (password 12345). The data is
varied but reproducible (fixed random seed) and keeps the business rules: task status
matches its submissions, reviewers are never in the submission roster, referrals only
target the latest pending submission. Deadlines are relative to the first run.
The full account list is in docs/TAI_KHOAN_DEMO.md.
"""
import hashlib
import logging
import random
import unicodedata
from datetime import timedelta
from werkzeug.security import generate_password_hash
from .core import *
from ..models import Workspace, WorkspaceMember, ProjectMember
from ..models.teamwork import Meeting, MatrixReview
from ..models.workflow import EvidenceCriterion, SubmissionEvidence, SubmissionReferral, ScheduleItem

KEY = 'khmt_demo_v1'
SEED = 20261128
STUDENT_DOMAIN = 'sv.teamsync.test'
STAFF_DOMAIN = 'gv.teamsync.test'
PASSWORD = '12345'

ADMIN = ('admin@teamsync.test', 'Quản trị hệ thống')
COORDINATOR = ('daotao', 'Nguyễn Thị Hạnh (Phòng Đào tạo)')
INSTRUCTORS = [
    ('khanhan', 'TS. Nguyễn Khánh An'), ('quangminh', 'PGS.TS. Phạm Quang Minh'), ('thuhang', 'TS. Đỗ Thu Hằng'),
    ('vanhung', 'TS. Trần Văn Hùng'), ('thimai', 'ThS. Lê Thị Mai'), ('ducanh', 'ThS. Vũ Đức Anh'),
    ('hoangnam', 'TS. Hoàng Văn Nam'), ('thanhhuong', 'ThS. Bùi Thanh Hương'), ('minhtuan', 'TS. Đặng Minh Tuấn'),
    ('ngoclan', 'ThS. Ngô Ngọc Lan'), ('quocviet', 'TS. Phan Quốc Việt'), ('phuongthao', 'ThS. Mai Phương Thảo'),
]
# Named demo students (short emails); the rest get generated names.
PERSONAS = [('minhanh', 'Nguyễn Minh Anh'), ('thuha', 'Trần Thu Hà'), ('quocbao', 'Lê Quốc Bảo'),
            ('gialinh', 'Phạm Gia Linh'), ('annhien', 'Võ An Nhiên')]
STUDENTS = 72

HO = ['Nguyễn', 'Trần', 'Lê', 'Phạm', 'Hoàng', 'Vũ', 'Đặng', 'Bùi', 'Đỗ', 'Ngô', 'Dương', 'Lý', 'Phan', 'Võ', 'Trịnh', 'Đinh', 'Mai', 'Tạ', 'Hồ', 'Lương']
DEM = ['Văn', 'Thị', 'Minh', 'Ngọc', 'Gia', 'Thanh', 'Quốc', 'Hải', 'Thu', 'Đức', 'Khánh', 'Bảo', 'Phương', 'Tuấn', 'Hoài', 'Diệu', 'Nhật', 'Anh']
TEN = ['An', 'Bình', 'Chi', 'Dũng', 'Giang', 'Hà', 'Hiếu', 'Khoa', 'Lan', 'Linh', 'Long', 'Mai', 'Nam', 'Nhung', 'Phong', 'Quân',
       'Sơn', 'Tâm', 'Trang', 'Tú', 'Uyên', 'Vy', 'Yến', 'Hưng', 'Thảo', 'Huy', 'Ngân', 'Đạt', 'Hằng', 'Kiên', 'Oanh', 'Phúc',
       'Quyên', 'Thắng', 'Vân', 'Duy', 'Hạnh', 'Trung', 'Khải', 'Minh', 'Tuệ', 'Hiền']
TEAMS = ['Đội Hỗ trợ', 'Đội Atlas', 'Đội Tài liệu', 'Đội Sao Mai', 'Đội Bình Minh', 'Đội Tia Chớp', 'Đội Hải Đăng', 'Đội Phượng Hoàng',
         'Đội Cánh Diều', 'Đội Mặt Trời', 'Đội Gió Bắc', 'Đội Thủy Tinh', 'Đội Hoa Sen', 'Đội Đại Bàng', 'Đội Ánh Dương', 'Đội Lục Bảo',
         'Đội Sông Hồng', 'Đội Trúc Xanh', 'Đội Kim Cương', 'Đội Thiên Hà', 'Đội Sóng Biển', 'Đội Ngân Hà', 'Đội Cầu Vồng', 'Đội Bit Byte',
         'Đội Null Pointer', 'Đội Lambda', 'Đội Kernel', 'Đội Pixel', 'Đội Tensor', 'Đội Docker', 'Đội Git Flow', 'Đội Async',
         'Đội Big O', 'Đội Recursion', 'Đội Stack', 'Đội Commit', 'Đội Cache Hit', 'Đội Deploy', 'Đội Sprint', 'Đội Merge',
         'Đội Neuron', 'Đội Vector', 'Đội Packet', 'Đội Firewall', 'Đội Cluster', 'Đội Query', 'Đội Schema', 'Đội Agile']

# code, title, instructor, assignment, brief, group mode, peer round closed?, [(project, team)], task pool, evidence criteria
COURSES = [
    ('INT3306', 'Phát triển ứng dụng Web', 'khanhan', 'Ứng dụng web quản lý công việc nhóm',
     'Xây dựng ứng dụng web có đăng nhập, phân quyền, quản lý công việc và báo cáo. Bàn giao mã nguồn, tài liệu triển khai và kịch bản kiểm thử.',
     'self', False, [('Free2do', 'Đội Hỗ trợ'), ('Kanbanly', None), ('StudySpace', None), ('CampusEvents', None), ('BookShelf Online', None)],
     ['Thiết kế cơ sở dữ liệu người dùng', 'Xây dựng API xác thực JWT', 'Trang quản trị phân quyền', 'Giao diện bảng Kanban kéo thả',
      'Tích hợp thông báo realtime', 'Viết kịch bản kiểm thử E2E', 'Tối ưu hiệu năng tải trang', 'Triển khai lên Render', 'Viết tài liệu API',
      'Giao diện responsive trên điện thoại', 'Xuất báo cáo Excel', 'Chức năng tìm kiếm và lọc'],
     ['Kiểm thử luồng tạo phiếu hỗ trợ', 'Tài liệu hướng dẫn sử dụng']),
    ('INT3401', 'Trí tuệ nhân tạo', 'quangminh', 'Ứng dụng AI hỗ trợ sinh viên',
     'Xây dựng ứng dụng sử dụng kỹ thuật AI giải quyết một nhu cầu thực tế của sinh viên. Nộp mã nguồn, mô hình, báo cáo thực nghiệm.',
     'self', True, [('ChatbotAI', 'Đội Atlas'), ('Trợ lý học tập AI', None), ('Gợi ý môn học thông minh', None), ('Nhận diện biển số xe', None)],
     ['Khảo sát bài toán và dữ liệu', 'Thu thập dữ liệu hội thoại', 'Tiền xử lý dữ liệu', 'Huấn luyện mô hình cơ sở', 'Tinh chỉnh siêu tham số',
      'Đánh giá mô hình', 'Xây dựng API suy luận', 'Giao diện demo', 'Viết báo cáo phương pháp', 'Chuẩn bị slide thuyết trình', 'Kiểm thử câu trả lời mẫu'],
     ['Bộ câu hỏi kiểm thử chatbot', 'Báo cáo đánh giá mô hình']),
    ('INT3110', 'Quản lý dự án Công nghệ thông tin', 'thuhang', 'Lập kế hoạch và quản lý dự án phần mềm',
     'Lập kế hoạch, theo dõi và báo cáo một dự án phần mềm giả định theo quy trình quản lý dự án. Nộp WBS, kế hoạch, báo cáo tiến độ và biên bản họp.',
     'self', True, [('Dự án Quản lý công nghệ thông tin', 'Đội Tài liệu'), ('Dự án ERP mini cho cửa hàng', None),
                    ('Dự án số hóa thư viện trường', None), ('Dự án app đặt lịch khám', None)],
     ['Lập bảng phân rã công việc WBS', 'Ước lượng chi phí dự án', 'Lập biểu đồ Gantt', 'Phân tích rủi ro', 'Kế hoạch truyền thông',
      'Biên bản họp khởi động', 'Báo cáo tiến độ giữa kỳ', 'Kế hoạch quản lý chất lượng', 'Đối chiếu mã SHA-256 của hồ sơ bàn giao', 'Nộp báo cáo đối chiếu phiên bản'],
     ['Kế hoạch dự án', 'Đối chiếu phiên bản tài liệu']),
    ('INT3405', 'Học máy', 'vanhung', 'Bài toán học máy với dữ liệu thực',
     'Chọn một bộ dữ liệu thực, xây dựng quy trình học máy hoàn chỉnh và so sánh tối thiểu ba mô hình.',
     'self', True, [('Dự đoán giá nhà Hà Nội', None), ('Phân loại email rác', None), ('Phát hiện gian lận thẻ', None), ('Dự báo nhu cầu xe đạp', None)],
     ['Phân tích khám phá dữ liệu', 'Xử lý giá trị thiếu', 'Chọn đặc trưng', 'Huấn luyện hồi quy tuyến tính', 'Huấn luyện Random Forest',
      'Huấn luyện XGBoost', 'So sánh mô hình bằng cross-validation', 'Giải thích mô hình bằng SHAP', 'Viết báo cáo thực nghiệm'],
     ['Notebook kết quả', 'Báo cáo thực nghiệm']),
    ('INT3406', 'Xử lý ngôn ngữ tự nhiên', 'thimai', 'Ứng dụng NLP cho tiếng Việt',
     'Xây dựng ứng dụng xử lý tiếng Việt, có bộ dữ liệu, mô hình và giao diện minh họa.',
     'self', True, [('Tóm tắt tin tức tiếng Việt', None), ('Phân tích cảm xúc đánh giá sản phẩm', None), ('Sửa lỗi chính tả tiếng Việt', None),
                    ('Hỏi đáp luật giao thông', None)],
     ['Thu thập corpus', 'Gán nhãn dữ liệu', 'Tách từ tiếng Việt', 'Huấn luyện PhoBERT', 'Đánh giá ROUGE', 'Xây dựng giao diện thử nghiệm',
      'Phân tích lỗi mô hình', 'Viết báo cáo'],
     ['Bộ dữ liệu đã gán nhãn', 'Báo cáo đánh giá']),
    ('INT3404', 'Thị giác máy tính', 'ducanh', 'Ứng dụng thị giác máy tính',
     'Xây dựng hệ thống nhận dạng hoặc phát hiện đối tượng chạy được trên video thực tế.',
     'teacher', False, [('Điểm danh bằng khuôn mặt', None), ('Đếm phương tiện giao thông', None), ('Phát hiện khẩu trang', None), ('Nhận dạng chữ viết tay', None)],
     ['Thu thập ảnh huấn luyện', 'Gán nhãn bounding box', 'Huấn luyện YOLO', 'Đánh giá mAP', 'Tối ưu tốc độ suy luận', 'Viết module camera', 'Viết báo cáo'],
     ['Video demo', 'Báo cáo đánh giá']),
    ('INT3120', 'Phát triển ứng dụng di động', 'hoangnam', 'Ứng dụng di động phục vụ sinh viên',
     'Xây dựng ứng dụng Android hoặc Flutter có đồng bộ dữ liệu, thông báo và kiểm thử trên thiết bị thật.',
     'self', True, [('Học từ vựng mỗi ngày', None), ('Đặt đồ ăn căng tin', None), ('Theo dõi chi tiêu sinh viên', None), ('Tìm phòng trọ quanh trường', None)],
     ['Thiết kế giao diện Figma', 'Dựng màn hình đăng nhập', 'Kết nối Firebase', 'Chức năng thông báo đẩy', 'Lưu trữ offline', 'Kiểm thử trên thiết bị thật',
      'Đóng gói APK', 'Viết hướng dẫn cài đặt'],
     ['Ảnh chụp giao diện', 'Bản cài đặt']),
    ('INT2208', 'Công nghệ phần mềm', 'thanhhuong', 'Quy trình phát triển phần mềm Scrum',
     'Áp dụng Scrum qua ba sprint để phát triển một hệ thống phục vụ khoa, có user story, backlog và retrospective.',
     'self', False, [('Quản lý phòng lab', None), ('Cổng đăng ký đề tài', None), ('Ứng dụng chấm công', None), ('Quản lý câu lạc bộ', None)],
     ['Viết user story', 'Lập product backlog', 'Sprint planning 1', 'Thiết kế kiến trúc', 'Viết unit test', 'Thiết lập CI GitHub Actions',
      'Sprint review 1', 'Retrospective', 'Tài liệu đặc tả yêu cầu'],
     ['Tài liệu đặc tả', 'Báo cáo sprint']),
    ('INT2211', 'Cơ sở dữ liệu', 'minhtuan', 'Thiết kế và cài đặt cơ sở dữ liệu',
     'Phân tích yêu cầu, thiết kế ERD, chuẩn hóa và cài đặt CSDL kèm truy vấn báo cáo.',
     'teacher', True, [('CSDL quản lý ký túc xá', None), ('CSDL bệnh viện', None), ('CSDL thương mại điện tử', None), ('CSDL rạp chiếu phim', None)],
     ['Xác định thực thể', 'Vẽ sơ đồ ERD', 'Chuẩn hóa 3NF', 'Viết script tạo bảng', 'Nhập dữ liệu mẫu', 'Viết 20 câu truy vấn báo cáo',
      'Tạo view và chỉ mục', 'Viết thủ tục lưu trữ'],
     ['Sơ đồ ERD', 'Script SQL']),
    ('INT2213', 'Mạng máy tính', 'ngoclan', 'Thiết kế và mô phỏng hệ thống mạng',
     'Thiết kế, mô phỏng và kiểm thử một hệ thống mạng hoặc ứng dụng mạng.',
     'self', False, [('Mô phỏng mạng doanh nghiệp', None), ('Ứng dụng chat qua socket', None), ('Giám sát lưu lượng mạng', None)],
     ['Vẽ sơ đồ topology', 'Cấu hình VLAN', 'Cấu hình định tuyến OSPF', 'Viết server socket', 'Bắt gói tin bằng Wireshark', 'Kiểm thử tải', 'Viết báo cáo'],
     ['File Packet Tracer', 'Báo cáo kiểm thử']),
    ('INT3307', 'An toàn và bảo mật thông tin', 'quocviet', 'Đánh giá an toàn ứng dụng',
     'Thực hiện kiểm thử bảo mật có kiểm soát trên ứng dụng thử nghiệm và đề xuất biện pháp khắc phục.',
     'self', True, [('Quét lỗ hổng ứng dụng web', None), ('Hệ thống phát hiện xâm nhập', None), ('Trình quản lý mật khẩu', None)],
     ['Lập phạm vi kiểm thử', 'Quét bằng OWASP ZAP', 'Kiểm thử SQL injection', 'Kiểm thử XSS', 'Viết luật Snort', 'Mã hóa dữ liệu AES', 'Viết báo cáo lỗ hổng'],
     ['Báo cáo lỗ hổng', 'Bằng chứng khắc phục']),
    ('INT3319', 'Điện toán đám mây', 'phuongthao', 'Triển khai ứng dụng trên đám mây',
     'Thiết kế và triển khai ứng dụng trên nền tảng đám mây, có giám sát và CI/CD.',
     'self', False, [('Microservices trên Kubernetes', None), ('Serverless xử lý ảnh', None), ('CI/CD cho ứng dụng web', None)],
     ['Viết Dockerfile', 'Viết manifest Kubernetes', 'Cấu hình Ingress', 'Thiết lập Prometheus', 'Dashboard Grafana', 'Pipeline GitHub Actions',
      'Kiểm thử tự động mở rộng', 'Viết tài liệu vận hành'],
     ['Sơ đồ kiến trúc', 'Tài liệu vận hành']),
]
# Minh Anh's projects (besides Free2do and ChatbotAI): course index → project index.
MINH_ANH_EXTRA = {2: 0, 3: 1, 6: 2, 7: 0, 8: 2}

NOTES = ['Đã hoàn thành phần chính, kèm tệp kết quả và cách kiểm tra.', 'Bổ sung theo góp ý lần trước, đã chạy lại toàn bộ.',
         'Đã kiểm tra trên máy tính và điện thoại.', 'Gửi bản hoàn chỉnh, có hướng dẫn sử dụng ngắn.', 'Đính kèm ảnh chụp kết quả chạy thử.']
RETURNS = ['Thiếu ảnh chụp màn hình kết quả.', 'Cần bổ sung trường hợp lỗi khi nhập sai dữ liệu.', 'Tài liệu chưa khớp phiên bản mã nguồn.',
           'Chưa ghi rõ cách chạy chương trình.', 'Số liệu ở bảng tổng hợp chưa khớp dữ liệu gốc.']
OUTPUTS = ['Tệp kết quả có thể mở và kiểm tra, kèm mô tả ngắn cách dùng.', 'Mã nguồn hoặc tài liệu đã rà soát, kèm ảnh chụp kết quả.',
           'Bản báo cáo ngắn nêu kết quả, vấn đề còn lại và cách kiểm tra.']


def slug(text):
    s = unicodedata.normalize('NFKD', text.replace('đ', 'd').replace('Đ', 'D')).encode('ascii', 'ignore').decode().lower()
    return '-'.join(''.join(ch if ch.isalnum() else ' ' for ch in s).split())[:40] or 'san-pham'


def seed_demo():
    if db.session.get(RuntimeSetting, KEY):
        return
    if CourseOffering.query.first():
        logging.getLogger(__name__).warning('Database đã có dữ liệu khác; không nạp dữ liệu demo KHMT. Sao lưu rồi xóa thư mục instance để dùng dữ liệu mới.')
        return
    Builder().run()


class Builder:
    def __init__(self):
        self.rnd = random.Random(SEED)
        self.at = now().replace(second=0, microsecond=0)
        self.password = generate_password_hash(PASSWORD)

    # ------------------------------------------------------------ helpers
    def naive(self, d):
        return d.replace(tzinfo=None)

    def user(self, email, name, role='user'):
        u = User(email=email, full_name=name, role=role, password_hash=self.password)
        db.session.add(u)
        db.session.flush()
        return u

    def event(self, action, etype, eid, pid, actor, when, reason=None):
        db.session.add(AuditEvent(action=action, entity_type=etype, entity_id=eid, project_id=pid, actor_id=actor.id,
                                  request_id='seed', reason=reason, created_at=when))

    def notification(self, u, kind, title, body, path, when):
        e = OutboxEvent(event_type=kind, aggregate_id=0, payload={'recipients': [u.id], 'subject': body, 'path': path},
                        processed_at=when, created_at=when)
        db.session.add(e)
        db.session.flush()
        db.session.add(Notification(recipient_id=u.id, event_id=e.id, title=title, body=body, target_path=path, created_at=when))

    def store(self, task, owner, name, text):
        from ..common.storage import root
        content = text.encode()
        key = hashlib.md5(f'khmt-{task.id}-{name}'.encode()).hexdigest()
        (root() / key).parent.mkdir(parents=True, exist_ok=True)
        (root() / key).write_bytes(content)
        a = EvidenceAsset(task_id=task.id, uploaded_by=owner.id, kind='file', storage_key=key, original_filename=name,
                          mime_type='text/plain', sha256=hashlib.sha256(content).hexdigest(), size_bytes=len(content),
                          integrity_status='fixed_file')
        db.session.add(a)
        db.session.flush()
        return a

    def submission(self, t, p, people, by, n, status, when, due, reviewer=None, reason=None, crit=None, filename=None, note=None):
        asset = self.store(t, by, filename or f'{slug(t.title)}-lan-{n}.txt', f'# {t.title}\n\nLần nộp {n} · {p.name}.\n')
        rev = EvidenceRevision(task_id=t.id, revision_no=n, description=note or self.rnd.choice(NOTES), created_by=by.id, created_at=when)
        db.session.add(rev)
        db.session.flush()
        db.session.add(EvidenceRevisionAsset(revision_id=rev.id, asset_id=asset.id))
        reviewed = when + timedelta(hours=self.rnd.randint(1, 9)) if reviewer else None
        s = TaskSubmission(task_id=t.id, revision_id=rev.id, attempt_no=n, submitted_by=by.id, participant_ids=sorted(u.id for u in people),
                           received_at=when, submitted_due_at=due, status=status, created_at=when,
                           reviewed_by=reviewer.id if reviewer else None, reviewed_at=reviewed, review_reason=reason)
        db.session.add(s)
        db.session.flush()
        if crit:
            db.session.add(SubmissionEvidence(submission_id=s.id, criterion_id=crit.id, asset_id=asset.id))
        t.latest_submission_id = s.id
        self.event('task.submitted', 'task_submission', s.id, p.id, by, when)
        if reviewer:
            self.event('submission.' + status, 'task_submission', s.id, p.id, reviewer, reviewed, reason)
        if status == 'accepted':
            t.completed_at = self.naive(reviewed)
        return s

    def task(self, p, leader, title, status, resp, collab, due, priority=None, points=None):
        created = self.at - timedelta(days=self.rnd.randint(8, 18), hours=self.rnd.randint(0, 22))
        t = Task(project_id=p.id, title=title, description=f'Hoàn thành và bàn giao kết quả: {title}. ' + self.rnd.choice(OUTPUTS), status=status,
                 priority=priority or self.rnd.choices(['low', 'medium', 'high'], weights=[2, 5, 3])[0],
                 points=points or self.rnd.choice([1, 1, 2, 2, 3, 5]), created_by=leader.id, assignee_id=resp.id, primary_assignee_id=resp.id,
                 due_at=due, original_due_at=due, created_at=self.naive(created), updated_at=self.naive(created))
        db.session.add(t)
        db.session.flush()
        for k, u in enumerate([resp] + collab):
            db.session.add(TaskParticipant(task_id=t.id, user_id=u.id, role='responsible' if k == 0 else 'collaborator'))
        self.event('task.created', 'task', t.id, p.id, leader, created)
        if status != 'todo':
            self.event('task.started', 'task', t.id, p.id, resp, created + timedelta(hours=self.rnd.randint(2, 30)))
        t._created = created
        return t

    def random_task(self, p, a, team, leader, title, crits):
        rnd = self.rnd
        st = rnd.choices(['todo', 'in_progress', 'review', 'done'], weights=[3, 4, 2, 3])[0]
        due = self.at + timedelta(hours=rnd.randint(-110, 260)) if st != 'done' else self.at - timedelta(hours=rnd.randint(5, 150))
        due = min(due, a.due_at - timedelta(hours=1))
        resp = rnd.choice(team)
        collab = rnd.sample([x for x in team if x != resp], k=rnd.choices([0, 1, 2], weights=[6, 3, 1])[0])
        people = [resp] + collab
        t = self.task(p, leader, title, st, resp, collab, due)
        if st == 'todo':
            return t
        reviewers = [u for u in team if u not in people]
        plan = {'in_progress': ['returned'] * rnd.choice([0, 0, 0, 1, 1, 2]),
                'review': ['returned'] * rnd.choice([0, 0, 1]) + ['pending'],
                'done': ['returned'] * rnd.choice([0, 0, 1]) + ['accepted']}[st]
        if not reviewers:
            plan = [x for x in plan if x == 'pending']
            if st == 'done':
                t.status, plan = 'review', ['pending']
        for n, sst in enumerate(plan, 1):
            when = min(t._created + timedelta(days=n * rnd.uniform(1, 2.4)), self.at - timedelta(hours=(len(plan) - n) * 5 + rnd.randint(1, 4)))
            if sst == 'pending':  # waiting submissions are recent; only some pass the 48-hour alert
                when = self.at - timedelta(hours=rnd.randint(2, 70))
            sub_due = due if n == len(plan) else when + timedelta(hours=rnd.choice([-8, 6, 20]))
            reviewer = None if sst == 'pending' else (leader if leader in reviewers and rnd.random() < 0.5 else rnd.choice(reviewers))
            reason = rnd.choice(RETURNS) if sst == 'returned' else ('Đạt yêu cầu.' if sst == 'accepted' else None)
            crit = rnd.choice(crits) if crits and rnd.random() < 0.55 else None
            self.submission(t, p, people, rnd.choice(people), n, sst, when, sub_due, reviewer, reason, crit)
        return t

    # ------------------------------------------------------------ data
    def run(self):
        rnd, at = self.rnd, self.at
        self.user(*ADMIN, role='admin')
        coordinator = self.user(f'{COORDINATOR[0]}@{STAFF_DOMAIN}', COORDINATOR[1])
        teachers = {k: self.user(f'{k}@{STAFF_DOMAIN}', name, 'instructor') for k, name in INSTRUCTORS}
        personas = {k: self.user(f'{k}@{STUDENT_DOMAIN}', name) for k, name in PERSONAS}
        names, seen = [], {n for _, n in PERSONAS}
        while len(names) < STUDENTS - len(PERSONAS):
            n = f'{rnd.choice(HO)} {rnd.choice(DEM)} {rnd.choice(TEN)}'
            if n not in seen:
                seen.add(n)
                names.append(n)
        others = []
        for i, n in enumerate(names, len(PERSONAS) + 1):
            parts = slug(n).split('-')
            others.append(self.user(f'{parts[-1]}.{"".join(x[0] for x in parts[:-1])}{i:02}@{STUDENT_DOMAIN}', n))
        students = list(personas.values()) + others
        codes = {u.id: f'2221{1000 + i:04}' for i, u in enumerate(students, 1)}
        ma, th, qb, gl, an = (personas[k] for k in ('minhanh', 'thuha', 'quocbao', 'gialinh', 'annhien'))
        team_pool = TEAMS[3:]
        rnd.shuffle(team_pool)
        self.courses = []
        for ci, (code, title, tkey, atitle, brief, mode, peer_closed, projects, pool, crit_titles) in enumerate(COURSES):
            teacher = teachers[tkey]
            w = Workspace(name=code, description=title, owner_id=teacher.id)
            db.session.add(w)
            db.session.flush()
            c = CourseOffering(code=f'{code} 1', title=title, term='HK1 · 2026–2027', status='active', workspace_id=w.id, created_by=teacher.id)
            db.session.add(c)
            db.session.flush()
            # Enrolment: personas where they have projects, plus a random cohort.
            sizes = [0 if (ci == 0 and pi == 0) else 2 if (ci == 1 and pi == 0) else rnd.randint(4, 6) for pi in range(len(projects))]
            cohort = rnd.sample(others, k=sum(sizes) + rnd.randint(6, 9))  # a few students stay without a group
            fixed = {0: [ma, th, qb, gl, an], 1: [th, ma]}.get(ci, [])
            if ci in MINH_ANH_EXTRA and ma not in fixed:
                fixed = fixed + [ma]
            enrolled = list(dict.fromkeys(fixed + cohort))
            db.session.add(WorkspaceMember(workspace_id=w.id, user_id=teacher.id, role='owner'))
            db.session.add(CourseEnrollment(course_id=c.id, user_id=teacher.id, role='instructor'))
            db.session.add(WorkspaceMember(workspace_id=w.id, user_id=coordinator.id, role='member'))
            db.session.add(CourseEnrollment(course_id=c.id, user_id=coordinator.id, role='coordinator'))
            for u in enrolled:
                db.session.add(WorkspaceMember(workspace_id=w.id, user_id=u.id, role='member'))
                db.session.add(CourseEnrollment(course_id=c.id, user_id=u.id, role='student', student_code=codes[u.id]))
            a = Assignment(course_id=c.id, title=atitle, brief=brief, status='active', is_hidden=False, due_at=at + timedelta(days=rnd.randint(28, 45)),
                           group_min=3, group_max=7, group_mode=mode, formation_due_at=at + timedelta(days=7))
            db.session.add(a)
            db.session.flush()
            crits = []
            for k, ct in enumerate(crit_titles):
                cr = EvidenceCriterion(assignment_id=a.id, title=ct, created_by=teacher.id, is_active=not (ci == 3 and k == 1))
                db.session.add(cr)
                db.session.flush()
                crits.append(cr)
            free = [u for u in enrolled if u not in (ma, th, qb, gl, an)]
            groups = []
            for pi, (pname, team) in enumerate(projects):
                if ci == 0 and pi == 0:
                    members, leader = [ma, th, qb, gl], ma
                elif ci == 1 and pi == 0:
                    members = [th, ma] + [free.pop() for _ in range(2)]
                    leader = th
                else:
                    members = [free.pop() for _ in range(sizes[pi])]
                    leader = rnd.choice(members)
                    if MINH_ANH_EXTRA.get(ci) == pi:
                        if leader is members[0]:
                            leader = ma
                        members[0] = ma
                        if ci == 6:  # Minh Anh also leads "Theo dõi chi tiêu sinh viên"
                            leader = ma
                status = 'active'
                if pi == len(projects) - 1 and ci in (4, 9):
                    status = 'pending'
                p = Project(name=pname, team_name=team or team_pool.pop(), description=atitle, workspace_id=w.id, created_by=leader.id,
                            assignment_id=a.id, mode='academic', status=status, created_at=self.naive(at - timedelta(days=rnd.randint(16, 26))))
                db.session.add(p)
                db.session.flush()
                for u in members:
                    role = 'leader' if u == leader else 'member'
                    db.session.add(AssignmentMembership(assignment_id=a.id, project_id=p.id, user_id=u.id, role=role))
                    db.session.add(ProjectMember(project_id=p.id, user_id=u.id, project_role='manager' if role == 'leader' else 'member'))
                self.event('group.assigned', 'project', p.id, p.id, leader, at - timedelta(days=15, hours=rnd.randint(0, 20)))
                groups.append((p, members, leader))
                if status != 'active':
                    continue
                active = [x for x in crits if x.is_active]
                if ci == 0 and pi == 0:
                    self.free2do(p, a, members, crits)
                    extra = rnd.sample(pool, 3)
                elif ci == 1 and pi == 0:
                    self.chatbot(p, a, members, crits)
                    extra = rnd.sample([x for x in pool if x not in ('Kiểm thử câu trả lời mẫu',)], 4)
                elif ci == 2 and pi == 0:
                    self.qlda(p, a, members, leader, teacher, crits)
                    extra = rnd.sample(pool[:8], 3)
                else:
                    extra = rnd.sample(pool, min(len(pool), rnd.randint(5, 8)))
                for title_ in extra:
                    self.random_task(p, a, members, leader, title_, active)
            self.courses.append((c, a, teacher, groups, peer_closed))
        self.extras(personas, students, teachers)
        db.session.add(RuntimeSetting(key=KEY, value={'version': 1}))
        db.session.add(RuntimeSetting(key='demo_clock', value={}))
        db.session.commit()

    def free2do(self, p, a, team, crits):
        """Fixed records the docs and tests use (Minh Anh leads; Thu Hà + Quốc Bảo share the login task)."""
        ma, th, qb, gl = team
        at = self.at
        t = self.task(p, ma, 'Thiết kế màn hình đăng nhập', 'in_progress', th, [qb], at + timedelta(hours=20), 'high', 3)
        self.submission(t, p, [th, qb], th, 1, 'returned', at - timedelta(hours=30), at - timedelta(hours=22), ma,
                        'Bổ sung trạng thái báo lỗi khi nhập sai mật khẩu và kiểm tra trên điện thoại.', None, 'man-hinh-dang-nhap.txt')
        self.task(p, ma, 'Gắn tag khẩn cho lỗi đồng bộ', 'todo', ma, [], at - timedelta(hours=6), 'high', 2)
        t = self.task(p, ma, 'Sửa lỗi tạo phiếu hỗ trợ', 'in_progress', ma, [], at + timedelta(hours=20), 'high', 5)
        self.submission(t, p, [ma], ma, 1, 'returned', at - timedelta(hours=30), at - timedelta(hours=22), gl,
                        'Phiếu vẫn mất tệp đính kèm khi tải lại trang.', crits[0], 'bao-cao-kiem-thu.txt', 'Đã sửa lỗi lưu phiếu khi thiếu mô tả.')
        self.submission(t, p, [ma], ma, 2, 'returned', at - timedelta(hours=6), at + timedelta(hours=20), gl,
                        'Cần kiểm thử thêm với khách chưa đăng nhập.', crits[0], 'bao-cao-kiem-thu.txt', 'Đã giữ tệp đính kèm khi tải lại và bổ sung kiểm thử.')
        t = self.task(p, ma, 'Nộp kịch bản kiểm thử luồng tiếp nhận', 'review', ma, [], at + timedelta(hours=30), 'medium', 3)
        self.submission(t, p, [ma], ma, 1, 'pending', at - timedelta(hours=50), at + timedelta(hours=30), None, None, None,
                        'kich-ban-kiem-thu.txt', 'Kịch bản gồm 12 trường hợp tiếp nhận phiếu, kèm dữ liệu mẫu.')
        t = self.task(p, ma, 'Chuẩn hóa mẫu phản hồi khách hàng', 'done', gl, [ma], at - timedelta(hours=70), 'medium', 2)
        self.submission(t, p, [gl, ma], gl, 1, 'accepted', at - timedelta(hours=80), at - timedelta(hours=70), th, 'Đạt yêu cầu.', crits[1],
                        'mau-phan-hoi.txt', 'Bộ mẫu phản hồi đã thống nhất giọng văn.')

    def chatbot(self, p, a, team, crits):
        th, ma, x1, x2 = team
        at = self.at
        t = self.task(p, th, 'Cập nhật ước tính đầu việc tích hợp', 'in_progress', ma, [], at + timedelta(hours=60), 'medium', 2)
        self.submission(t, p, [ma], ma, 1, 'returned', at - timedelta(hours=28), at - timedelta(hours=20), th,
                        'Thiếu ước tính cho phần xác thực.', None, 'uoc-tinh.txt', 'Bảng ước tính cho 8 đầu việc tích hợp.')
        t = self.task(p, th, 'Kiểm thử câu trả lời mẫu', 'review', x1, [], at + timedelta(hours=50), 'high', 3)
        self.submission(t, p, [x1], x1, 1, 'pending', at - timedelta(hours=3), at + timedelta(hours=50), None, None, crits[0],
                        'cau-hoi-mau.txt', 'Đã chạy 40 câu hỏi mẫu, ghi lại câu trả lời sai.')
        self.task(p, th, 'Đặt lịch tổng duyệt Sprint Atlas', 'todo', x2, [], at - timedelta(hours=14), 'low', 1)

    def qlda(self, p, a, team, leader, teacher, crits):
        at = self.at
        ma = next(u for u in team if u.email.startswith('minhanh@'))
        t = self.task(p, leader, 'Nộp báo cáo đối chiếu phiên bản', 'review', ma, [], at + timedelta(hours=70), 'medium', 3)
        s = self.submission(t, p, [ma], ma, 1, 'pending', at - timedelta(hours=5), at + timedelta(hours=70), None, None, crits[1],
                            'doi-chieu-phien-ban.txt', 'Báo cáo đối chiếu 5 phiên bản tài liệu.')
        if leader is not ma:
            reason = 'Nhờ giảng viên xác nhận cách đối chiếu phiên bản tài liệu.'
            db.session.add(SubmissionReferral(submission_id=s.id, project_id=p.id, referred_by=leader.id, instructor_id=teacher.id, reason=reason))
            self.event('submission.referred', 'task_submission', s.id, p.id, leader, at - timedelta(hours=4), reason)
            self.notification(teacher, 'submission.referred', 'Bài được chuyển cho bạn duyệt', f'{t.title} · {p.name} · Lần 1',
                              f'/tasks/{t.id}?submission={s.id}#submission-{s.id}', at - timedelta(hours=4))
        self.task(p, leader, 'Đối chiếu mã SHA-256 của hồ sơ bàn giao', 'todo', ma, [], at - timedelta(hours=9), 'high', 2)

    def extras(self, personas, students, teachers):
        rnd, at = self.rnd, self.at
        helps = ['Xin hướng dẫn phạm vi chức năng bắt buộc', 'Nhóm chưa thống nhất cách chia khối lượng', 'Cần góp ý cấu trúc báo cáo',
                 'Lỗi môi trường khi chạy trên máy phòng thực hành', 'Xin xác nhận bộ dữ liệu được phép dùng']
        for c, a, teacher, groups, peer_closed in self.courses:
            if peer_closed:
                r = PeerRound(assignment_id=a.id, title='Đánh giá giữa kỳ', opens_at=at - timedelta(days=12), closes_at=at - timedelta(days=4),
                              status='closed', criteria_json=[], roster_json={})
                db.session.add(r)
                db.session.flush()
            for p, members, leader in groups:
                if p.status != 'active':
                    continue
                if peer_closed:
                    for rv in members:
                        for re_ in members:
                            if rv != re_ and rnd.random() < 0.8:
                                a10, q10 = rnd.randint(6, 10), rnd.randint(5, 10)
                                db.session.add(MatrixReview(round_id=r.id, project_id=p.id, reviewer_id=rv.id, reviewee_id=re_.id, attitude10=a10,
                                                            quality10=q10, attitude=(a10 + 1) // 2, quality=(q10 + 1) // 2, comment=''))
                if rnd.random() < 0.3:
                    db.session.add(HelpRequest(project_id=p.id, requested_by=rnd.choice(members).id, assigned_to=teacher.id, subject=rnd.choice(helps),
                                               content='Nhóm mô tả khó khăn và mong giảng viên góp ý hướng xử lý.',
                                               created_at=at - timedelta(hours=rnd.randint(2, 60))))
                if rnd.random() < 0.5:
                    db.session.add(Meeting(project_id=p.id, host_id=leader.id, title=rnd.choice(['Họp khởi động dự án', 'Họp chốt phân công tuần', 'Rà soát tiến độ giữa kỳ']),
                                           room_name=f'seed-minutes-{p.id}', status='ended', ended_at=at - timedelta(days=rnd.randint(1, 8)),
                                           notes=f'Thành viên tham dự: {len(members)} thành viên.\nKết luận: ưu tiên các đầu việc sắp đến hạn; mỗi công việc có tệp bàn giao '
                                                 'và hướng dẫn kiểm tra.\nLink cuộc họp: https://meet.google.com/'))
                pending = Task.query.filter_by(project_id=p.id, status='review').all()
                if pending and rnd.random() < 0.15 and not SubmissionReferral.query.filter_by(project_id=p.id).first():
                    t = pending[-1]
                    s = db.session.get(TaskSubmission, t.latest_submission_id)
                    if leader.id not in s.participant_ids:
                        reason = 'Nhóm chưa thống nhất đánh giá, nhờ giảng viên xem giúp lần nộp này.'
                        db.session.add(SubmissionReferral(submission_id=s.id, project_id=p.id, referred_by=leader.id, instructor_id=teacher.id, reason=reason))
                        when = at - timedelta(hours=rnd.randint(1, 20))
                        self.event('submission.referred', 'task_submission', s.id, p.id, leader, when, reason)
                        self.notification(teacher, 'submission.referred', 'Bài được chuyển cho bạn duyệt', f'{t.title} · {p.name} · Lần {s.attempt_no}',
                                          f'/tasks/{t.id}?submission={s.id}#submission-{s.id}', when)
                for t in Task.query.filter_by(project_id=p.id).filter(Task.status.in_(['todo', 'in_progress'])):
                    if t.due_at < at + timedelta(hours=24):
                        late = t.due_at < at
                        for x in TaskParticipant.query.filter_by(task_id=t.id):
                            self.notification(db.session.get(User, x.user_id), 'deadline.reminder', 'Nhắc hạn công việc',
                                              ('Quá hạn: ' if late else 'Sắp đến hạn: ') + t.title, f'/tasks/{t.id}', at - timedelta(minutes=rnd.randint(5, 600)))
        # Timeline entries for students (personal ones and some shared with a project).
        plans = [('meeting', 'Họp nhóm chốt phân công tuần', 0, 1, True), ('study', 'Ôn lại kiến thức nền cho phần việc được giao', -1, 2, False),
                 ('deadline', 'Mốc nộp bản nháp báo cáo', 3, 1, True), ('review', 'Rà soát chéo bài nộp của nhóm', 4, 2, True),
                 ('personal', 'Lịch thi giữa kỳ', 6, 1, False), ('study', 'Đọc tài liệu tham khảo và ghi chú', 2, 4, False),
                 ('meeting', 'Họp với giảng viên hướng dẫn', 8, 1, True), ('deadline', 'Chốt bản bàn giao sản phẩm', 10, 1, True),
                 ('other', 'Chuẩn bị slide thuyết trình', 7, 3, False), ('personal', 'Đi làm thêm ca tối', 1, 1, False)]
        today = at.date()
        for u in list(personas.values()) + rnd.sample(students[len(personas):], 30):
            pids = [m.project_id for m in AssignmentMembership.query.filter_by(user_id=u.id, status='active')]
            for cat, title, off, length, shared in rnd.sample(plans, rnd.randint(4, 7)):
                start = today + timedelta(days=off + rnd.choice([0, 0, 1, 2]))
                db.session.add(ScheduleItem(owner_id=u.id, project_id=rnd.choice(pids) if shared and pids else None, title=title, category=cat,
                                            start_date=start, end_date=start + timedelta(days=length - 1),
                                            note='Có thể kéo thả sang ngày khác hoặc sửa nội dung ở tab Lịch tôi tạo.'))
