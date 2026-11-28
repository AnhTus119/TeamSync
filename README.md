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

Không cần Docker, Node, Redis hoặc dịch vụ ngoài. File `.env` không bắt buộc (chỉ cần nếu muốn dùng AI Gemini miễn phí, xem mục AI hỗ trợ tạo timeline). Cổng khác: đặt `PORT=5001` trong Environment variables của Run Configuration.

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

- **Sidebar**: sinh viên có Tổng quan, Dự án của tôi, Bảng Kanban, Timeline, Bài nộp, Học phần; giảng viên và quản lý học phần chỉ có **Tổng quan, Timeline, Học phần** (không có danh sách dự án ở sidebar; bài được chuyển duyệt nằm ở panel *Bài được chuyển cho tôi* trên Tổng quan). Mỗi mục có icon. Chỉ Tổng quan còn khối tiêu đề lớn; các trang danh sách bắt đầu ngay bằng hàng công cụ.
- **Tiêu đề trang** dùng font nội dung (chữ hoa). Chữ TeamSync trên thanh đầu trang dùng Audiowide.
- **Chi tiết dự án**: thanh đầu một hàng (icon · tên + đội · trạng thái · số thành viên · tiến độ · Học phần), tab có icon. Tab **Thành viên** hiển thị thẻ dọc: họ tên (font Electrolize, OFL; chữ có dấu tiếng Việt lấy glyph của font nội dung vì Electrolize chỉ có bộ Latin), ảnh đại diện, Email / Vai trò / Mã sinh viên và Điểm hiện tại = trung bình đánh giá chéo đã công bố (đợt đã đóng) trong dự án đó. Chưa có điểm thì hiện "Chưa có điểm". Người đã rời liệt kê riêng dưới lưới.
- **Ảnh đại diện mặc định** nằm ở `app/static/img/avatars/` (smile, crown, headband, pixel, blush, tongue `.svg`), chọn ổn định theo `user.id`. Muốn dùng bộ ảnh gốc, thay các tệp cùng tên (có thể đổi đuôi và sửa danh sách `AVATARS` trong `workspace.js`). Nếu API trả `avatar_url` thì ưu tiên ảnh đó, ảnh lỗi tự quay về ảnh mặc định.
- **Dự án của tôi**: hàng công cụ gồm Tất cả / Tôi làm lead, tìm kiếm, sắp xếp (Tiến độ giảm dần mặc định, Tiến độ tăng dần, Ngày tạo mới nhất) và nút Tạo dự án. Màu nền thẻ theo tiến độ (hoàn thành / tổng): 0% `#FCFAF9`, 1–24% `#E7EFF6`, 25–49% `#E0EFED`, 50–99% `#DCE9E0`, 100% `#CFE5D1`. Tạo dự án: sinh viên chọn học phần đang mở tự lập nhóm và nhập tên (POST `/api/v1/assignments/{id}/projects`); giảng viên chọn học phần rồi xếp nhóm.
- **Bảng Kanban** (`/kanban`, `/my-tasks`) là bảng cá nhân: chỉ task bạn phụ trách hoặc cùng làm (`GET /api/v1/workflow/tasks?scope=mine`). Việc của đồng đội đang chờ bạn duyệt nằm ở Bài nộp → Cần tôi duyệt. Bộ lọc: tìm kiếm, dự án, Quá hạn, Cần sửa; vẫn nhận `?filter=repair|due|review`. Trong mỗi cột, thẻ xếp theo ưu tiên cao → vừa → thấp rồi hạn sớm trước. Các thẻ số trên Tổng quan đếm trên cùng tập task cá nhân này.
- **Bài nộp**: ba tab Bài của tôi / Cần sửa / Cần tôi duyệt (giảng viên: Đã xử lý / Được chuyển cho tôi).
- **Chuyển trang**: thanh trên và sidebar đứng yên, chỉ phần nội dung đổi (không tải lại trang; Back/Forward và link trực tiếp vẫn dùng được). Dữ liệu đọc được giữ tạm **5 phút** rồi tự làm mới (bỏ qua khi đang mở hộp thoại hoặc đang nhập), hoặc khi bấm F5. Mọi thao tác ghi của chính người dùng xóa bộ nhớ tạm nên kết quả hiện ngay ở mọi trang; thay đổi của người khác hiện sau tối đa 5 phút hoặc khi F5.
- **Học phần (giảng viên/quản lý)**: mở một lớp là thấy ngay tab **Nhóm dự án**: lưới thẻ mọi nhóm (đội, trưởng nhóm, thành viên, tiến độ, chờ duyệt / hỗ trợ / quá hạn / việc chờ duyệt), nhóm cần chú ý lên đầu, có ô tìm. Tab *Đề bài & tiêu chí* và *Sinh viên* giữ nguyên.
- **Timeline** (`/timeline`): lịch theo ngày, việc trong cùng ngày xếp chồng trong một cột, mục nhiều ngày trải ngang, mỗi loại một màu (Công việc nhóm, Họp nhóm, Mốc nộp, Học tập, Rà soát, Cá nhân, Khác). Tab **Lịch của tôi** chỉ xem: task được giao (theo hạn), mốc của đề bài (hạn nộp, hạn lập nhóm) và mục lịch được chia sẻ với dự án của bạn. Giảng viên thấy mốc các lớp, lịch các nhóm chia sẻ và lịch tự tạo (không có task), lọc theo học phần / nhóm. Tab **Lịch tôi tạo** sửa trực tiếp: kéo thả đổi ngày (giữ độ dài), Alt + ←/→ dời một ngày, bấm để sửa tiêu đề/loại/ngày/ghi chú/chia sẻ, bấm đúp vào một ngày để thêm. API: `GET/POST /api/v1/workflow/schedule`, `PATCH/DELETE /api/v1/workflow/schedule/{id}` (chỉ người tạo được sửa).

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
- Đánh giá chéo **theo từng công việc** (thay cho đợt đánh giá; API đợt cũ trả 410): khi task được duyệt hoàn thành, mọi thành viên không làm task đó đánh giá người làm (theo roster của lần nộp được duyệt) với Hợp tác và Chất lượng thang 1–10, kèm nhận xét tùy chọn. Phiếu mở **7 ngày** sau khi hoàn thành, tùy chọn, được bỏ qua (không tính là 0) và sửa trước hạn. Hết hạn mới công bố trung bình, số phiếu và nhận xét. Điểm hiện tại trên thẻ thành viên, ô điểm ở Tổng quan, tab Đánh giá chéo và báo cáo/XLSX/PDF dùng cùng một công thức: trung bình (Hợp tác + Chất lượng)/2 của các phiếu đã công bố. Không đưa danh tính người đánh giá lên UI/API báo cáo. Trong nhóm nhỏ vẫn có thể suy đoán; dữ liệu nguồn có liên kết người gửi trong DB để chống gửi trùng, không phải ẩn danh với người có toàn quyền database.
- Đánh giá chéo không tự đổi đóng góp; trưởng nhóm dùng làm căn cứ xử lý trên task cụ thể.
- Bộ tiêu chí chỉ là tài liệu giảng viên tải lên cùng đề bài, không bắt buộc. Không chấm điểm học phần, không tự đánh giá rubric, không Commitment Index.
- Biên bản họp lưu chủ đề/kết luận/link; có thể tạo task từ kết luận. Trao đổi ngoài qua Zalo, không tích hợp tài khoản Zalo. Không video nhúng.
- Bàn giao sản phẩm nhóm chọn các bài đã duyệt, không tải lại file. Báo cáo XLSX/PDF/HTML luôn lấy dữ liệu mới nhất (đã bỏ mục Báo cáo đã lưu).

## AI hỗ trợ tạo timeline

- **Trưởng nhóm** (Bảng công việc của nhóm → *AI lập kế hoạch*): AI đọc đề bài, hạn nộp, thành viên và khối lượng đang mở, đề xuất giai đoạn + công việc có hạn, người phụ trách, khối lượng, ưu tiên. Sửa / bỏ chọn từng dòng rồi mới tạo task (qua API tạo công việc thông thường, không vượt hạn đề bài, không lặp task đã có).
- **Mọi người** (Timeline → *AI sắp lịch* → *Xác nhận*): lịch được thêm ngay cho khoảng ngày đang xem (từ hôm nay trở đi) từ task được giao, bài chờ mình duyệt, phiếu đánh giá chéo, hạn nộp đề bài và buổi rà soát tiến độ hằng tuần, không trùng mục đã có. Nút *↶ Hoàn tác* xóa đúng các mục vừa thêm; sau khi hoàn tác, nút *→* thêm lại lịch AI đó.
- Nguồn: **Google Gemini gói miễn phí** nếu đặt `GEMINI_API_KEY` trong `.env` (tạo key tại https://aistudio.google.com/apikey; tùy chọn `GEMINI_MODEL`, mặc định `gemini-2.5-flash`). Không có key, hết lượt miễn phí hoặc lỗi mạng thì tự dùng bộ sinh theo quy tắc nên demo luôn chạy. Đầu ra AI được kiểm tra (thành viên hợp lệ, ngày trong hạn, khối lượng 1/2/3/5) trước khi hiển thị.

## Source

`app/academic/workflow.py`: nghiệp vụ mới; `task_review.py`: đánh giá chéo theo công việc; `ai_plan.py`: AI lập kế hoạch / sắp lịch; `evidence.py`: quyền duyệt độc lập, chuyển giảng viên, tiêu chí minh chứng, hàng đợi Bài nộp và dữ liệu Tổng quan; `showcase_seed.py`: bộ demo Free2do; `workflow_reports.py`: xuất báo cáo; `workflow_seed.py`: demo.
`app/static/js/workspace.js`, `app/static/css/workspace.css`, `app/templates/academic/workspace.html`: giao diện chính.
`app/models/workflow.py`: biểu quyết, bản báo cáo, bàn giao, chống trùng nhắc hạn.
Các module tài khoản/dự án dùng chung và migrations được giữ để tạo database và bảo toàn quan hệ. API nghiệp vụ cũ đã nghỉ được chặn, không chỉ ẩn UI.

## Kiểm thử

`python -m pip install -r requirements-dev.txt`

`python -m playwright install chromium`

`python -m pytest -q tests`

Browser tests dùng Chromium hệ thống nếu có, nếu không dùng Chromium của Playwright. Tests tạo database tạm, không sửa database demo. Xem `docs/UAT.md` để test thủ công A–Z và `docs/TEST_REPORT.md` để biết phạm vi đã xác minh.

`run.py` là launcher local/demo. Triển khai thật cần cấu hình server, HTTPS, sao lưu và xác thực thích hợp. Chưa có tích hợp LMS hay kiểm thử tải diện rộng.
