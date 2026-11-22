# TeamSync — quản lý nhóm học phần

Ứng dụng Flask chạy trực tiếp trên PyCharm. Mỗi lớp có một giảng viên, một bài tập nhóm lớn. Sinh viên theo dõi công việc, deadline, bài nộp và đóng góp; giảng viên duyệt nhóm và hỗ trợ.

## Chạy trên PyCharm

1. Giải nén ZIP. Mở thư mục `TeamSync` có `run.py` trong PyCharm.
2. Chọn Python 3.12, tạo virtual environment riêng cho dự án.
3. Mở Terminal của PyCharm: `python -m pip install -r requirements.txt`.
4. Nhấn Run trên `run.py`.
5. Mở http://127.0.0.1:5000. Lần đầu chương trình chạy migrations và tạo dữ liệu demo.

Không cần Docker, Node, Redis hoặc dịch vụ ngoài. File `.env` không bắt buộc. Cổng khác: đặt `PORT=5001` trong Environment variables của Run Configuration.

## Tài khoản demo

Mật khẩu tất cả: **12345**.

| Email | Vai trò |
|---|---|
| admin@gmail.com | Quản trị tài khoản |
| gv1@gmail.com | Giảng viên 8 lớp |
| sv1@gmail.com | Trưởng nhóm 01 |
| sv2@gmail.com, sv3@gmail.com | Cùng làm task Thiết kế giao diện đăng nhập |
| sv4@gmail.com … sv6@gmail.com | Thành viên nhóm 01 |
| sv7@gmail.com … sv30@gmail.com | Thành viên các nhóm 02–05 |
| sv31@gmail.com … sv36@gmail.com | Sinh viên chưa có nhóm, dùng thử lập nhóm |

Lớp đầu: **Lập trình Web**. Các lớp còn lại: Phân tích và thiết kế hệ thống, Quản lý dự án CNTT, Cơ sở dữ liệu, Hệ quản trị CSDL, Python, Java, Trí tuệ nhân tạo. Mỗi lớp có 5 nhóm mẫu × 6 người, 6 sinh viên chưa có nhóm. Đây là dữ liệu mô phỏng, không kết nối LMS NEU.

## Dữ liệu và thời gian

Dữ liệu mới nằm tại `instance/teamsync-workspace.db`, file tải lên tại `instance/private/`. Dừng/chạy lại giữ nguyên dữ liệu. Bản này sử dụng tên database mới, không tự chuyển hoặc xóa database bản trước. Không trỏ `TEAMSYNC_DATA_DIR` vào dữ liệu cá nhân cũ khi chưa sao lưu.

Muốn bắt đầu lại demo: dừng ứng dụng, **sao lưu rồi đổi tên** thư mục `instance`, chạy lại. Chỉ làm khi muốn bỏ trạng thái demo đã thao tác. Deadline được tạo tương đối tại lần chạy đầu, sau đó dùng thời gian thực. Nhắc trước hạn 24 giờ; quá hạn gom nhắc theo ngày. Worker kiểm tra mỗi 15 phút, phát thông báo trong ứng dụng. Phải mở ứng dụng để xem; chưa có email/push bên ngoài.

## Quy tắc chính

- Nhóm sinh viên tự lập: mời và nhận xác nhận → đủ người → gửi giảng viên duyệt. Giảng viên xếp nhóm trực tiếp không cần sinh viên chấp nhận.
- Giảng viên phụ trách lớp tự có quyền quan sát/hỗ trợ. Không cần lời mời mentor.
- Không tự chuyển nhóm. Rời nhóm được duyệt; giảng viên xếp lại khi có lý do.
- Trưởng nhóm rời: lấy ceil(số thành viên còn lại / 2) phiếu đồng ý. Danh sách cử tri lưu khi yêu cầu; mỗi người một phiếu. Đủ phiếu thì hệ thống chọn ngẫu nhiên trưởng nhóm mới. Giữ lịch sử và đóng góp cũ.
- Task bắt buộc tên, người làm, đầu ra, hạn; khối lượng mặc định 1 (có thể chọn 1/2/3/5), ưu tiên mặc định vừa.
- Một người nộp thay các thành viên cùng phân công; roster lưu theo lần nộp. Thành viên duyệt bài người khác, trưởng nhóm được tự duyệt.
- Yêu cầu sửa cần nhận xét và hạn sửa. Lần nộp cũ giữ thời hạn cũ; lần sửa dùng hạn mới.
- Điều chỉnh đóng góp bắt đầu tại task, cần lý do, giải trình/cơ hội giải trình và tổng 100%. Liên quan trưởng nhóm chuyển giảng viên; trường hợp thường do trưởng nhóm xử lý.
- Đánh giá chéo tùy chọn, được bỏ qua và sửa trước hạn. Chỉ công bố tổng hợp sau khi đóng. Không đưa danh tính người đánh giá lên UI/API báo cáo. Trong nhóm nhỏ vẫn có thể suy đoán; dữ liệu nguồn có liên kết người gửi trong DB để chống gửi trùng, không phải ẩn danh với người có toàn quyền database.
- Đánh giá chéo không tự đổi đóng góp; trưởng nhóm dùng làm căn cứ xử lý trên task cụ thể.
- Bộ tiêu chí chỉ là tài liệu giảng viên tải lên cùng đề bài, không bắt buộc. Không chấm điểm học phần, không tự đánh giá rubric, không Commitment Index.
- Biên bản họp lưu chủ đề/kết luận/link; có thể tạo task từ kết luận. Trao đổi ngoài qua Zalo, không tích hợp tài khoản Zalo. Không video/AI nhúng.
- Bàn giao sản phẩm nhóm chọn các bài đã duyệt, không tải lại file. Báo cáo XLSX/PDF/HTML và bản lưu tại thời điểm chốt.

## Source

`app/academic/workflow.py`: nghiệp vụ mới; `workflow_reports.py`: xuất báo cáo; `workflow_seed.py`: demo.
`app/static/js/workspace.js`, `app/static/css/workspace.css`, `app/templates/academic/workspace.html`: giao diện chính.
`app/models/workflow.py`: biểu quyết, bản báo cáo, bàn giao, chống trùng nhắc hạn.
Các module tài khoản/dự án dùng chung và migrations được giữ để tạo database và bảo toàn quan hệ. API nghiệp vụ cũ đã nghỉ được chặn, không chỉ ẩn UI.

## Kiểm thử

`python -m pip install -r requirements-dev.txt`

`python -m playwright install chromium`

`python -m pytest -q tests`

Browser tests dùng Chromium hệ thống nếu có, nếu không dùng Chromium của Playwright. Tests tạo database tạm, không sửa database demo. Xem `docs/UAT.md` để test thủ công A–Z và `docs/TEST_REPORT.md` để biết phạm vi đã xác minh.

`run.py` là launcher local/demo. Triển khai thật cần cấu hình server, HTTPS, sao lưu và xác thực thích hợp. Chưa có tích hợp LMS hay kiểm thử tải diện rộng.
