# Kiểm thử hệ thống A–Z

Chạy theo README. Mọi tài khoản dưới đây có mật khẩu `12345`. Dùng cửa sổ/profile trình duyệt riêng để tránh đổi phiên đăng nhập giữa các vai trò. Các tình huống làm thay đổi dữ liệu; nếu cần chạy lại từ đầu, dừng ứng dụng và sao lưu/đổi tên thư mục instance rồi chạy lại.

| Bước | Tài khoản và thao tác | Kết quả và ý nghĩa |
|---|---|---|
| 1 | sv1@gmail.com → Tổng quan → tìm “Web” | Lập trình Web đứng đầu; tìm kiếm thu gọn danh sách lớp |
| 2 | Bấm Lập trình Web | Vào thẳng Kanban Nhóm 01, không chọn lại nhóm/bài tập |
| 3 | sv2@gmail.com → Công việc của tôi → lọc lớp | Chỉ thấy công việc của mình; deadline và trạng thái rõ |
| 4 | sv1 → Nhóm 01 → Tạo công việc | Bỏ trống đầu ra/hạn/người làm bị chặn; không cần rubric; khối lượng mặc định 1 |
| 5 | sv2 → Thiết kế giao diện đăng nhập | Thấy bản bị yêu cầu sửa và nhận xét mẫu đầy đủ |
| 6 | Kéo thả file TXT/ZIP hợp lệ, nhập nội dung, Gửi duyệt | Tạo lần nộp mới; sv2 và sv3 cùng được ghi nhận |
| 7 | sv2 mở bài vừa nộp | Không có quyền tự duyệt; API cũng kiểm tra quyền |
| 8 | sv1 → mở bài → Yêu cầu sửa khi chưa nhận xét | Báo lỗi đỏ; chưa gửi quyết định |
| 9 | Nhập nhận xét, hạn sửa rồi Yêu cầu sửa | Thành viên thấy feedback và hạn chỉnh sửa; bản cũ giữ hạn cũ |
| 10 | sv2 sửa/nộp lại; sv4 hoặc sv1 duyệt hoàn thành | Thành viên được duyệt bài người khác; trưởng nhóm cũng được tự duyệt bài mình |
| 11 | Xem bản cũ → Ẩn bản cũ | Mặc định chỉ bản mới nhất; lịch sử vẫn còn |
| 12 | sv2 → công việc chung → Đề nghị điều chỉnh đóng góp → chọn sv3 | Yêu cầu bắt đầu ngay tại công việc, chưa tự thay đổi tỷ lệ |
| 13 | sv3 → mở công việc → Gửi giải trình | Người liên quan được phản hồi |
| 14 | sv1 → Xử lý đề nghị, nhập 80/10 | Bị chặn vì tổng khác 100; 80/20 và lý do hợp lệ mới lưu |
| 15 | Đối chiếu Báo cáo & sản phẩm | Công việc đã duyệt × tỷ lệ đóng góp; lịch sử quyết định được giữ |
| 16 | sv1 tạo công việc chung có bản thân và sv2, nộp; sv2 phản ánh sv1 | Trường hợp liên quan trưởng nhóm chuyển giảng viên, trưởng nhóm không tự quyết |
| 17 | sv2 → Hỗ trợ → thử gửi thiếu phạm vi/nội dung | Không gửi được; điền đầy đủ thì gv1 nhận yêu cầu |
| 18 | gv1 → lớp → Nhóm 01 → Hỗ trợ → Phản hồi | Giảng viên hỗ trợ mà không cần được nhóm mời; không sửa task thường ngày |
| 19 | gv1 → lớp → Mở đợt đánh giá chéo | Đặt thời gian kết thúc; sinh viên được đánh giá hoặc bỏ qua từng người |
| 20 | sv2 → Đánh giá chéo → bỏ chọn “Chưa đủ cơ sở” ở người muốn đánh giá | Nhập hai tiêu chí 1–10; được sửa trước khi đóng; phiếu bỏ qua không thành 0 |
| 21 | gv1 → nhóm → Đánh giá chéo → Đóng đợt | Các thành viên thấy trung bình và số phiếu, không thấy người gửi; không tự đổi đóng góp |
| 22 | sv1 → Biên bản họp → thêm chủ đề, kết luận, link Meet | Lưu biên bản; Tạo việc từ kết luận mở form để xác nhận người làm/hạn; không gọi AI/video |
| 23 | sv1 → Báo cáo & sản phẩm → chọn bài đã duyệt để bàn giao | Dùng lại bản nộp, không upload lại mã nguồn/báo cáo |
| 24 | Tải Excel, PDF, Bản in | Đối chiếu đóng góp, đánh giá chéo, công việc, lịch sử nhân sự; Excel có biểu đồ |
| 25 | Lưu bản báo cáo hiện tại; làm thêm công việc; tải bản đã lưu | Bản lưu giữ dữ liệu tại thời điểm chốt; báo cáo hiện tại tiếp tục cập nhật |
| 26 | sv31 → Lập trình Web → Tạo nhóm → mời sv32 và sv33 | Hai người nhận chấp nhận ở Tổng quan; đủ ba người mới gửi duyệt |
| 27 | sv31 gửi giảng viên duyệt; gv1 vào nhóm duyệt | Trước khi duyệt không tạo task; sau duyệt nhóm hoạt động |
| 28 | gv1 → lớp → Xếp nhóm → chọn sv34–sv36 | Sinh viên được thêm ngay, không cần chấp nhận |
| 29 | sv6 → Thành viên → Xin rời nhóm; sv1 đồng ý | sv6 mất quyền nhóm, lịch sử vẫn có; không được tự lập nhóm khác trong lớp |
| 30 | gv1 → nhóm → Xếp thêm/tiếp nhận lại → sv6 và lý do | Giảng viên được xếp lại người đã rời |
| 31 | sv1 → Xin rời nhóm khi nhóm có sáu người | Năm người còn lại có quyền bỏ phiếu; cần ba đồng ý |
| 32 | sv2, sv3, sv4 lần lượt bỏ phiếu đồng ý | Chỉ đủ ba phiếu mới rời; chọn ngẫu nhiên trưởng nhóm mới; ghi báo cáo |
| 33 | gv1 → Tạo lớp → thêm sinh viên đã có tài khoản → tạo bài tập | Mỗi lớp một bài tập; chọn tự lập hoặc giảng viên xếp nhóm |
| 34 | gv1 tải tài liệu tiêu chí tại đề bài | Sinh viên xem/tải được; không có tài liệu vẫn làm việc bình thường |
| 35 | admin@gmail.com → tạo/khóa tài khoản | Quản lý tài khoản; không được mở dữ liệu nhóm/học phần |
| 36 | sv7 thử URL Nhóm 01 hoặc file của nhóm đó | Truy cập bị từ chối, không chỉ ẩn nút |
| 37 | Mở Thông báo sau worker chạy | Có nhắc trước hạn 24h, quá hạn theo ngày; không gửi deadline task tới giảng viên |
| 38 | Dừng/chạy run.py, đăng nhập lại | Dữ liệu đã thao tác được giữ; không nạp lại đè lên |
| 39 | Kiểm tra màn hình điện thoại | Không tràn ngang toàn trang; Menu mở được, nút thao tác còn truy cập được |

Đánh giá chéo ẩn danh trên UI và báo cáo, không bảo đảm không suy đoán trong nhóm nhỏ. Hệ thống chưa kết nối LMS, Zalo, email hoặc push ngoài trình duyệt. Deadline dựa thời gian thực; ứng dụng cần đang chạy để worker phát thông báo.
