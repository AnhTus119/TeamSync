# Kiểm thử thủ công A–Z

Chạy theo README với database mới. Mật khẩu mọi tài khoản: `12345` (danh sách đầy đủ ở [TAI_KHOAN_DEMO.md](TAI_KHOAN_DEMO.md)). Dùng cửa sổ/profile trình duyệt riêng cho mỗi vai trò. Các bước làm thay đổi dữ liệu; muốn chạy lại từ đầu thì dừng ứng dụng, sao lưu rồi xóa thư mục `instance`.

Viết tắt: **MA** = minhanh@sv.teamsync.test (trưởng nhóm Free2do), **TH** = thuha@sv.teamsync.test, **QB** = quocbao@sv.teamsync.test, **GL** = gialinh@sv.teamsync.test, **AN** = annhien@sv.teamsync.test (chưa có nhóm), **GV-Web** = khanhan@gv.teamsync.test, **GV-AI** = quangminh@gv.teamsync.test, **GV-QLDA** = thuhang@gv.teamsync.test, **ĐT** = daotao@gv.teamsync.test, **Admin** = admin@teamsync.test.

## Tổng quan, dự án, Kanban

| Bước | Tài khoản và thao tác | Kết quả |
|---|---|---|
| 1 | MA → Tổng quan | Sáu thẻ chỉ số, công tắc Cột / Tròn, hàng 4 panel (Task sắp hết hạn, Cập nhật dự án, Cảnh báo, Thông báo), lưới 7 dự án |
| 2 | Bấm từng mũi tên trên sáu thẻ | Mở Kanban/Dự án đã lọc đúng; số trên thẻ = số thẻ hiển thị |
| 3 | MA → Dự án của tôi → đổi sắp xếp, Tôi làm lead, tìm “free” | Màu nền theo tiến độ; thứ tự đổi đúng; còn Free2do |
| 4 | MA → Bảng Kanban → chọn Free2do, bấm Quá hạn, Cần sửa | Chỉ việc MA phụ trách/cùng làm; số đếm cột cập nhật |
| 5 | AN → Dự án của tôi → Tạo dự án → Phát triển ứng dụng Web + tên nhóm | Mở nhóm nháp vừa tạo, AN là trưởng nhóm |

## Nộp, duyệt độc lập, chuyển giảng viên

| Bước | Tài khoản và thao tác | Kết quả |
|---|---|---|
| 6 | TH → Free2do → Thiết kế màn hình đăng nhập | Thấy Lần 1 bị yêu cầu sửa và nhận xét |
| 7 | Kéo thả tệp, nhập nội dung, Gửi duyệt | Lần nộp 2; TH và QB cùng được ghi nhận |
| 8 | TH hoặc QB mở bài vừa nộp | Không có nút duyệt (có tên trong lần nộp); API trả 403 |
| 9 | GL → Yêu cầu sửa khi chưa nhập nhận xét | Báo lỗi đỏ dưới ô nhận xét |
| 10 | GL nhập nhận xét + hạn sửa hợp lệ → Yêu cầu sửa; TH nộp lại; GL hoặc MA duyệt hoàn thành | Lần 3 Đã duyệt; bấm “Lần 1” mở đúng nội dung cũ |
| 11 | GV-AI → Học phần → Trí tuệ nhân tạo → Thêm tiêu chí | Tiêu chí mới “Đang dùng”; Ẩn/Bật lại được |
| 12 | MA → ChatbotAI → Cập nhật ước tính đầu việc tích hợp → nộp tệp, gắn tiêu chí | Lần 2 có bảng Minh chứng theo tiêu chí; MA bị chặn duyệt |
| 13 | TH → Chuyển giảng viên duyệt + lý do | GV-AI nhận thông báo và thấy bài ở Bài nộp → Được chuyển cho tôi |
| 14 | GV-AI → Yêu cầu sửa; MA nộp lại; một thành viên khác duyệt | GV-AI không duyệt được Lần 3 (chưa được chuyển) |
| 15 | GV-QLDA → Bài nộp | Có “Nộp báo cáo đối chiếu phiên bản” được chuyển sẵn |

## Thành viên, đánh giá, báo cáo, Timeline

| Bước | Tài khoản và thao tác | Kết quả |
|---|---|---|
| 16 | MA → Free2do → Thành viên | Thẻ dọc: tên, ảnh, email, vai trò, mã SV, Điểm hiện tại |
| 17 | GL → Xin rời nhóm; MA đồng ý | GL ra khỏi lưới, nằm ở “Đã rời nhóm”; đóng góp cũ vẫn tính |
| 18 | MA → Xin rời nhóm | Cần ceil(số người còn lại / 2) phiếu; đủ phiếu chọn trưởng nhóm mới |
| 19 | GV-Web → Free2do → Đánh giá chéo → Mở đợt; TH đánh giá; GV-Web đóng đợt | Chỉ hiện tổng hợp, không hiện người đánh giá |
| 20 | MA → Báo cáo & sản phẩm → Excel / PDF / Bản in, Lưu bản báo cáo, Chọn bài đã duyệt để bàn giao | Tệp tải được; bản lưu giữ dữ liệu lúc chốt |
| 21 | MA → Timeline → Lịch tôi tạo → Thêm lịch, kéo sang ngày khác, Alt+←, sửa loại | Mục đổi ngày/màu ngay; TH thấy mục được chia sẻ ở Lịch của tôi nhưng không sửa được |
| 22 | MA → Bài nộp → Cần sửa | Chỉ các lần nộp mới nhất đang bị yêu cầu sửa |

## Học phần, phân quyền, hệ thống

| Bước | Tài khoản và thao tác | Kết quả |
|---|---|---|
| 23 | GV-Web → Học phần → Phát triển ứng dụng Web → Sinh viên → Nhập CSV / Excel với một dòng sai email | Dòng lỗi tô đỏ, Xác nhận nhập bị khóa; Chọn tệp khác với tệp đã sửa → nhập thành công |
| 24 | GV-Web → tab Nhóm → Xếp nhóm | Thêm nhóm từ sinh viên chưa có nhóm |
| 25 | ĐT → Học phần bất kỳ | Xem danh sách, nhập sinh viên, xếp nhóm; không có nút tạo đề bài/tiêu chí |
| 26 | Admin → tạo/khóa tài khoản | Quản lý tài khoản; không mở được dữ liệu học phần/nhóm |
| 27 | Một sinh viên ngoài Free2do mở URL dự án/task/tệp của Free2do | Bị từ chối (404), không chỉ ẩn nút |
| 28 | Mở Thông báo sau khi worker chạy | Nhắc trước hạn 24h, quá hạn theo ngày; giảng viên không nhận nhắc hạn task |
| 29 | Dừng/chạy lại run.py | Dữ liệu đã thao tác được giữ |
| 30 | Màn hình điện thoại ~390 px | Không tràn ngang; menu mở dạng overlay; Kanban/Timeline cuộn trong khung |

Đánh giá chéo ẩn danh trên UI và báo cáo, không bảo đảm không suy đoán trong nhóm nhỏ. Hệ thống chưa kết nối LMS, Zalo, email hoặc push ngoài trình duyệt.
