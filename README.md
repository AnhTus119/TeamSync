# TeamSync — quản lý nhóm học phần

Ứng dụng Flask chạy trực tiếp trên PyCharm. Mỗi lớp có một giảng viên, một bài tập nhóm lớn. Sinh viên theo dõi công việc, deadline, bài nộp và đóng góp; giảng viên duyệt nhóm và hỗ trợ.

## Chạy trên VS Code

1. Giải nén ZIP, mở thư mục `TeamSync` (có `run.py`) bằng **File → Open Folder**. Cài extension Python khi VS Code gợi ý.
2. Mở Terminal (Ctrl+`) và tạo môi trường ảo Python 3.12:
   - Windows: `py -3.12 -m venv .venv` rồi `.venv\Scripts\activate`
   - macOS/Linux: `python3.12 -m venv .venv` rồi `source .venv/bin/activate`
3. `python -m pip install -r requirements-dev.txt`
4. Ctrl+Shift+P → **Python: Select Interpreter** → chọn `.venv`.
5. Vào Run and Debug (Ctrl+Shift+D) → chọn **TeamSync: chạy ứng dụng (run.py)** → F5. Hoặc gõ `python run.py`.
6. Mở http://127.0.0.1:5000 và đăng nhập bằng tài khoản demo bên dưới.

Chạy test: cấu hình **TeamSync: chạy toàn bộ test** hoặc `python -m pytest -q tests`. Browser test cần Chromium: `python -m playwright install chromium`.

## Chạy trên PyCharm

1. Giải nén ZIP. Mở thư mục `TeamSync` có `run.py` trong PyCharm.
2. Chọn Python 3.12, tạo virtual environment riêng cho dự án.
3. Mở Terminal của PyCharm: `python -m pip install -r requirements.txt`.
4. Nhấn Run trên `run.py`.
5. Mở http://127.0.0.1:5000. Lần đầu chương trình chạy migrations và tạo dữ liệu demo.

Không cần Docker, Node, Redis hoặc dịch vụ ngoài. File `.env` không bắt buộc. Cổng khác: đặt `PORT=5001` trong Environment variables của Run Configuration.

## Tài khoản demo

Dữ liệu demo là một khoa **Khoa học máy tính**: 12 học phần, 12 giảng viên, 1 quản lý học phần, 72 sinh viên, 46 dự án (khoảng 275 công việc, 217 lần nộp, 200 mục lịch). Ai trong dữ liệu cũng có tài khoản, mật khẩu chung **12345**. Danh sách đầy đủ (học phần, dự án, thành viên, mã sinh viên): [docs/TAI_KHOAN_DEMO.md](docs/TAI_KHOAN_DEMO.md).

| Email | Vai trò |
|---|---|
| minhanh@sv.teamsync.test | Nguyễn Minh Anh: trưởng nhóm Free2do và Theo dõi chi tiêu sinh viên; thành viên ChatbotAI, Dự án Quản lý CNTT và 3 dự án khác |
| thuha@sv.teamsync.test | Trần Thu Hà: trưởng nhóm ChatbotAI, thành viên Free2do (cùng Quốc Bảo làm task Thiết kế màn hình đăng nhập) |
| quocbao@sv.teamsync.test, gialinh@sv.teamsync.test | Thành viên Free2do |
| annhien@sv.teamsync.test | Sinh viên Phát triển ứng dụng Web chưa có nhóm (thử tạo dự án) |
| khanhan@gv.teamsync.test | TS. Nguyễn Khánh An, Phát triển ứng dụng Web (Free2do) |
| quangminh@gv.teamsync.test | PGS.TS. Phạm Quang Minh, Trí tuệ nhân tạo (ChatbotAI) |
| thuhang@gv.teamsync.test | TS. Đỗ Thu Hằng, Quản lý dự án CNTT (có bài được chuyển duyệt) |
| daotao@gv.teamsync.test | Quản lý học phần (nhập danh sách, xếp nhóm ở tất cả học phần) |
| admin@teamsync.test | Quản trị tài khoản |

Email dùng đuôi `.test` (tên miền dành riêng cho thử nghiệm) nên không trùng địa chỉ thật. Dữ liệu được tạo khi chạy `run.py` lần đầu với database mới; muốn xem dữ liệu mới thì dừng ứng dụng, sao lưu rồi xóa thư mục `instance`. Database đã có dữ liệu khác sẽ không bị nạp chồng. Tạo lại danh sách tài khoản: `python tools/tai_khoan_demo.py`.

## Dữ liệu và thời gian

Dữ liệu mới nằm tại `instance/teamsync-workspace.db`, file tải lên tại `instance/private/`. Dừng/chạy lại giữ nguyên dữ liệu. Bản này sử dụng tên database mới, không tự chuyển hoặc xóa database bản trước. Không trỏ `TEAMSYNC_DATA_DIR` vào dữ liệu cá nhân cũ khi chưa sao lưu.

Muốn bắt đầu lại demo: dừng ứng dụng, **sao lưu rồi đổi tên** thư mục `instance`, chạy lại. Chỉ làm khi muốn bỏ trạng thái demo đã thao tác. Deadline được tạo tương đối tại lần chạy đầu, sau đó dùng thời gian thực. Nhắc trước hạn 24 giờ; quá hạn gom nhắc theo ngày. Worker kiểm tra mỗi 15 phút, phát thông báo trong ứng dụng. Phải mở ứng dụng để xem; chưa có email/push bên ngoài.

## Bố cục Tổng quan

Khối trên: Việc cần chú ý với sáu chỉ số và công tắc Cột / Tròn. Ngay dưới là một hàng panel cùng chiều rộng, theo thứ tự **Task sắp hết hạn → Cập nhật dự án → Cảnh báo cần xử lý → Thông báo gần đây** (giảng viên không có panel Task sắp hết hạn). Cảnh báo không còn là dải ngang riêng: panel chỉ hiện khi API trả về cảnh báo, hiện tối đa 4 thẻ kèm nút Xem thêm; khi không có cảnh báo, các panel còn lại chia hết chiều ngang. Số cột theo chiều rộng nội dung còn lại sau sidebar: 4 cột trên desktop, 2 cột ở màn vừa, 1 cột trên điện thoại. Phần Dự án của tôi (sinh viên) hoặc Học phần phụ trách (giảng viên) đi sau hàng panel.

## Các trang chính

- **Sidebar**: Tổng quan, Dự án của tôi, Bảng Kanban, Timeline, Bài nộp, Học phần, mỗi mục có icon. Chỉ Tổng quan còn khối tiêu đề lớn; các trang danh sách bắt đầu ngay bằng hàng công cụ.
- **Tiêu đề trang** dùng font nội dung (chữ hoa). Chữ TeamSync trên thanh đầu trang dùng Audiowide.
- **Chi tiết dự án**: thanh đầu một hàng (icon · tên + đội · trạng thái · số thành viên · tiến độ · Học phần), tab có icon. Tab **Thành viên** hiển thị thẻ dọc: họ tên (font Electrolize, OFL; chữ có dấu tiếng Việt lấy glyph của font nội dung vì Electrolize chỉ có bộ Latin), ảnh đại diện, Email / Vai trò / Mã sinh viên và Điểm hiện tại = trung bình đánh giá chéo đã công bố (đợt đã đóng) trong dự án đó. Chưa có điểm thì hiện "Chưa có điểm". Người đã rời liệt kê riêng dưới lưới.
- **Ảnh đại diện mặc định** nằm ở `app/static/img/avatars/` (smile, crown, headband, pixel, blush, tongue `.svg`), chọn ổn định theo `user.id`. Muốn dùng bộ ảnh gốc, thay các tệp cùng tên (có thể đổi đuôi và sửa danh sách `AVATARS` trong `workspace.js`). Nếu API trả `avatar_url` thì ưu tiên ảnh đó, ảnh lỗi tự quay về ảnh mặc định.
- **Dự án của tôi**: hàng công cụ gồm Tất cả / Tôi làm lead, tìm kiếm, sắp xếp (Tiến độ giảm dần mặc định, Tiến độ tăng dần, Ngày tạo mới nhất) và nút Tạo dự án. Màu nền thẻ theo tiến độ (hoàn thành / tổng): 0% `#FCFAF9`, 1–24% `#E7EFF6`, 25–49% `#E0EFED`, 50–99% `#DCE9E0`, 100% `#CFE5D1`. Tạo dự án: sinh viên chọn học phần đang mở tự lập nhóm và nhập tên (POST `/api/v1/assignments/{id}/projects`); giảng viên chọn học phần rồi xếp nhóm.
- **Bảng Kanban** (`/kanban`, `/my-tasks`) là bảng cá nhân: chỉ task bạn phụ trách hoặc cùng làm (`GET /api/v1/workflow/tasks?scope=mine`). Việc của đồng đội đang chờ bạn duyệt nằm ở Bài nộp → Cần tôi duyệt. Bộ lọc: tìm kiếm, dự án, Quá hạn, Cần sửa; vẫn nhận `?filter=repair|due|review`. Trong mỗi cột, thẻ xếp theo ưu tiên cao → vừa → thấp rồi hạn sớm trước. Các thẻ số trên Tổng quan đếm trên cùng tập task cá nhân này.
- **Bài nộp**: ba tab Bài của tôi / Cần sửa / Cần tôi duyệt (giảng viên: Đã xử lý / Được chuyển cho tôi).
- **Timeline** (`/timeline`): lịch theo ngày, việc trong cùng ngày xếp chồng trong một cột, mục nhiều ngày trải ngang, mỗi loại một màu (Công việc nhóm, Họp nhóm, Mốc nộp, Học tập, Rà soát, Cá nhân, Khác). Tab **Lịch của tôi** chỉ xem: task được giao (theo hạn) và mục lịch được chia sẻ với dự án của bạn. Tab **Lịch tôi tạo** sửa trực tiếp: kéo thả đổi ngày (giữ độ dài), Alt + ←/→ dời một ngày, bấm để sửa tiêu đề/loại/ngày/ghi chú/chia sẻ, bấm đúp vào một ngày để thêm. API: `GET/POST /api/v1/workflow/schedule`, `PATCH/DELETE /api/v1/workflow/schedule/{id}` (chỉ người tạo được sửa).

## Quy tắc chính

- Nhóm sinh viên tự lập: mời và nhận xác nhận → đủ người → gửi giảng viên duyệt. Giảng viên xếp nhóm trực tiếp không cần sinh viên chấp nhận.
- Giảng viên phụ trách lớp tự có quyền quan sát/hỗ trợ. Không cần lời mời mentor.
- Không tự chuyển nhóm. Rời nhóm được duyệt; giảng viên xếp lại khi có lý do.
- Trưởng nhóm rời: lấy ceil(số thành viên còn lại / 2) phiếu đồng ý. Danh sách cử tri lưu khi yêu cầu; mỗi người một phiếu. Đủ phiếu thì hệ thống chọn ngẫu nhiên trưởng nhóm mới. Giữ lịch sử và đóng góp cũ.
- Task bắt buộc tên, người làm, đầu ra, hạn; khối lượng mặc định 1 (có thể chọn 1/2/3/5), ưu tiên mặc định vừa.
- Một người nộp thay các thành viên cùng phân công; roster lưu theo lần nộp. Thành viên đang hoạt động duyệt được lần nộp mới nhất đang chờ nếu không phải người nộp và không có tên trong danh sách người làm lưu ở lần đó. Quy tắc này áp dụng cả với trưởng nhóm.
- Trưởng nhóm có thể **Chuyển giảng viên duyệt** đúng một lần nộp (kèm lý do). Giảng viên chỉ duyệt được lần nộp đã được chuyển cho mình; nộp lại là lần mới, quyền duyệt được xét lại. Hai người quyết định cùng lúc: chỉ quyết định hợp lệ đầu tiên được lưu.
- Tiêu chí minh chứng do giảng viên thêm/ẩn/bật lại tại Đề bài & tiêu chí. Khi nộp có thể gắn tệp/link của chính lần nộp với tiêu chí (tùy chọn). Tiêu chí ẩn không nhận minh chứng mới nhưng lịch sử vẫn giữ. Báo cáo đếm Đã duyệt / Chờ duyệt / Cần sửa theo lần nộp mới nhất của từng task.
- Yêu cầu sửa cần nhận xét và hạn sửa. Lần nộp cũ giữ thời hạn cũ; lần sửa dùng hạn mới.
- Điều chỉnh đóng góp bắt đầu tại task, cần lý do, giải trình/cơ hội giải trình và tổng 100%. Liên quan trưởng nhóm chuyển giảng viên; trường hợp thường do trưởng nhóm xử lý.
- Đánh giá chéo tùy chọn, được bỏ qua và sửa trước hạn. Chỉ công bố tổng hợp sau khi đóng. Không đưa danh tính người đánh giá lên UI/API báo cáo. Trong nhóm nhỏ vẫn có thể suy đoán; dữ liệu nguồn có liên kết người gửi trong DB để chống gửi trùng, không phải ẩn danh với người có toàn quyền database.
- Đánh giá chéo không tự đổi đóng góp; trưởng nhóm dùng làm căn cứ xử lý trên task cụ thể.
- Bộ tiêu chí chỉ là tài liệu giảng viên tải lên cùng đề bài, không bắt buộc. Không chấm điểm học phần, không tự đánh giá rubric, không Commitment Index.
- Biên bản họp lưu chủ đề/kết luận/link; có thể tạo task từ kết luận. Trao đổi ngoài qua Zalo, không tích hợp tài khoản Zalo. Không video/AI nhúng.
- Bàn giao sản phẩm nhóm chọn các bài đã duyệt, không tải lại file. Báo cáo XLSX/PDF/HTML và bản lưu tại thời điểm chốt.

## Source

`app/academic/workflow.py`: nghiệp vụ mới; `evidence.py`: quyền duyệt độc lập, chuyển giảng viên, tiêu chí minh chứng, hàng đợi Bài nộp và dữ liệu Tổng quan; `showcase_seed.py`: bộ demo Free2do; `workflow_reports.py`: xuất báo cáo; `workflow_seed.py`: demo.
`app/static/js/workspace.js`, `app/static/css/workspace.css`, `app/templates/academic/workspace.html`: giao diện chính.
`app/models/workflow.py`: biểu quyết, bản báo cáo, bàn giao, chống trùng nhắc hạn.
Các module tài khoản/dự án dùng chung và migrations được giữ để tạo database và bảo toàn quan hệ. API nghiệp vụ cũ đã nghỉ được chặn, không chỉ ẩn UI.

## Kiểm thử

`python -m pip install -r requirements-dev.txt`

`python -m playwright install chromium`

`python -m pytest -q tests`

Browser tests dùng Chromium hệ thống nếu có, nếu không dùng Chromium của Playwright. Tests tạo database tạm, không sửa database demo. Xem `docs/UAT.md` để test thủ công A–Z và `docs/TEST_REPORT.md` để biết phạm vi đã xác minh.

`run.py` là launcher local/demo. Triển khai thật cần cấu hình server, HTTPS, sao lưu và xác thực thích hợp. Chưa có tích hợp LMS hay kiểm thử tải diện rộng.
