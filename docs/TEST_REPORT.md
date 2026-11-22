# Phạm vi xác minh

Bản sửa sử dụng bộ kiểm tra mới, không kế thừa con số 43 test của bản cũ.

- 14 test API/nghiệp vụ: phạm vi nhóm, luồng đã bỏ, lớp một bài tập, rubric tùy chọn, nộp chung, duyệt/sửa, biểu quyết rời, lưu đóng góp người đã rời, lập nhóm và duyệt, tổng hợp đánh giá ẩn danh, hỗ trợ không cần mentor invite, tổng tỷ lệ 100%, chống trùng nhắc hạn, xuất báo cáo/bản lưu/bàn giao, biên bản riêng tư, CSRF và quyền file.
- 2 test trình duyệt: kéo thả thật, nộp/sửa/nộp lại/duyệt, lỗi nhận xét, ẩn/hiện lịch sử, tải XLSX và mở bằng openpyxl, lưu báo cáo, mobile không tràn ngang; mở/đóng đánh giá chéo và tạo lớp.
- Đã xem ảnh desktop/mobile; kiểm tra cú pháp JavaScript và biên dịch Python.

Chưa kiểm thử tải nhiều người dùng, pentest độc lập, tích hợp LMS hoặc chạy trực tiếp trên Windows/PyCharm. Launcher đã chạy trong môi trường Linux Python 3.12; hướng dẫn PyCharm sử dụng cùng entry point. Cảnh báo thư viện migration về get_engine không phải lỗi test.
