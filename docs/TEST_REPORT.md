# Phạm vi xác minh

Lệnh: `python -m pytest -q tests` (dữ liệu demo khoa KHMT; test dò bản ghi theo tên, không phụ thuộc id) (Python 3.12, Chromium/Playwright) → **36 passed**.

- `tests/test_workflow.py` (14 test): phạm vi nhóm, luồng đã bỏ, lớp một đề bài, nộp chung, duyệt/sửa, biểu quyết rời, lập nhóm, đánh giá chéo ẩn danh, hỗ trợ, tổng tỷ lệ 100%, chống trùng nhắc hạn, báo cáo/bản lưu/bàn giao, biên bản riêng tư, CSRF và quyền tệp.
- `tests/test_evidence_review.py` (7 test): luồng chuyển giảng viên đầy đủ (Lần 1 giữ nguyên, bản cũ không nhận quyết định, quyết định thứ hai bị 409), trưởng nhóm có tên trong lần nộp bị chặn, phạm vi tiêu chí/tệp và tiêu chí ẩn, quyền âm cho người ngoài nhóm và giảng viên lớp khác, nhập CSV có dòng lỗi rồi nhập lại, số liệu Tổng quan và cảnh báo theo quyền, seed chạy lặp an toàn và migration nâng cấp DB cũ.
- Bổ sung: phạm vi Kanban cá nhân, API Timeline (chủ sở hữu, chia sẻ chỉ xem, xung đột phiên bản), Dự án theo tiến độ/sắp xếp/tạo dự án (cả trường hợp API từ chối), Kanban cá nhân (ưu tiên, lọc, trạng thái trống), tab Cần sửa, icon sidebar, font tiêu đề, Timeline kéo thả thật và phím tắt, Tổng quan 4 cột.
- `tests/test_browser.py` (5 test gốc): kéo thả nộp/sửa/duyệt, xuất XLSX, mobile; đánh giá chéo và tạo lớp; luồng demo tiêu chí → chuyển GV → yêu cầu sửa → nộp lại → duyệt → mở lại Lần 1; điều hướng sáu thẻ Tổng quan, công tắc Cột/Tròn, cảnh báo, Kanban, menu avatar/đăng xuất; ba tab Học phần, modal nhập CSV và màn hình 390 px không tràn ngang.

Đã chạy `run.py` với thư mục dữ liệu riêng, dừng và chạy lại: số bài nộp và dự án giữ nguyên. Chưa kiểm thử tải nhiều người dùng, pentest độc lập hoặc chạy trực tiếp trên Windows/PyCharm.
