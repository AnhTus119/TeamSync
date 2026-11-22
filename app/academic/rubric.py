"""An editable example for the survey project, never a required global rubric."""


def criterion(code, title, weight, description, evidence, levels):
    return {
        "code": code,
        "title": title,
        "weight": weight,
        "description": description,
        "evidence_requirement": evidence,
        "levels": [
            {"label": label, "score": score, "description": content}
            for (label, score), content in zip(
                [("Chưa đạt", 0), ("Đạt", 5), ("Tốt", 8), ("Xuất sắc", 10)], levels
            )
        ],
    }


DEMO_CRITERIA = [
    criterion(
        "C1",
        "Độ tin cậy của dữ liệu",
        40,
        "Dữ liệu khảo sát có cấu trúc nhất quán, xử lý giá trị thiếu và bản ghi trùng; các thay đổi có thể đối chiếu với dữ liệu gốc.",
        "Dữ liệu gốc và sau xử lý, từ điển dữ liệu, bảng kiểm tra thiếu/trùng và nhật ký làm sạch.",
        [
            "Không có dữ liệu gốc để đối chiếu hoặc còn lỗi thiếu/trùng làm sai kết quả.",
            "Định dạng thống nhất; đã xử lý lỗi chính nhưng chưa giải thích đầy đủ cách loại bỏ hoặc thay thế dữ liệu.",
            "Có quy tắc làm sạch và số liệu trước/sau; kiểm tra được giá trị thiếu, trùng và phạm vi hợp lệ.",
            "Mọi thay đổi truy vết được; kiểm tra tự động phát hiện dữ liệu bất thường và giải thích ảnh hưởng của từng quyết định xử lý.",
        ],
    ),
    criterion(
        "C2",
        "Phân tích và diễn giải kết quả",
        30,
        "Phương pháp phân tích trả lời câu hỏi khảo sát; biểu đồ và kết luận phù hợp với mẫu dữ liệu, không suy diễn quan hệ nhân quả.",
        "Bảng thống kê, biểu đồ có nhãn/đơn vị, phép tính hoặc mã phân tích và giải thích giới hạn của mẫu.",
        [
            "Phép tính sai hoặc kết luận không được dữ liệu hỗ trợ; biểu đồ thiếu nhãn cần thiết.",
            "Thống kê cơ bản đúng và trả lời được câu hỏi chính; còn thiếu kiểm tra giả định hoặc giải thích giới hạn.",
            "Lựa chọn phương pháp có lý do; kết quả kiểm tra chéo được; kết luận nêu rõ phạm vi và hạn chế.",
            "Phân tích thêm nhóm đối chiếu hoặc độ nhạy; kiểm tra các cách giải thích khác và chỉ ra giới hạn suy luận cụ thể.",
        ],
    ),
    criterion(
        "C3",
        "Khả năng chạy lại và kiểm chứng",
        20,
        "Người khác có thể tái tạo kết quả từ dữ liệu đầu vào bằng các bước và môi trường đã mô tả.",
        "Mã hoặc workbook tính toán, phiên bản thư viện, hướng dẫn chạy và kết quả kiểm thử với dữ liệu mẫu.",
        [
            "Thiếu mã/công thức hoặc không thể tạo lại kết quả từ tài liệu đã nộp.",
            "Chạy lại được luồng chính sau một số thao tác thủ công đã ghi rõ.",
            "Có hướng dẫn cài đặt và chạy từ đầu; kết quả lặp lại nhất quán và có kiểm tra trường hợp dữ liệu lỗi.",
            "Quy trình tái tạo được kiểm chứng trên môi trường sạch; có kiểm thử hồi quy và thông báo rõ khi đầu vào không hợp lệ.",
        ],
    ),
    criterion(
        "C4",
        "Báo cáo và khả năng bàn giao",
        10,
        "Báo cáo kết nối yêu cầu, phương pháp, kết quả và kết luận; người tiếp nhận tìm được đúng file, nguồn và hướng dẫn sử dụng.",
        "Báo cáo cuối, danh mục tệp, bảng liên kết yêu cầu–kết quả và nguồn tham khảo.",
        [
            "Báo cáo thiếu phần kết quả hoặc không xác định được file sản phẩm cuối.",
            "Có đủ mục chính và file bàn giao; còn chỗ trích dẫn hoặc liên kết minh chứng chưa rõ.",
            "Bố cục nhất quán; mọi kết luận chính có minh chứng và nguồn; danh mục tệp giúp tiếp nhận nhanh.",
            "Báo cáo cô đọng, đối chiếu được toàn bộ yêu cầu; có hạn chế, hướng phát triển và hướng dẫn tiếp quản rõ ràng.",
        ],
    ),
]
