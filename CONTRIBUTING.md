# Quy tắc phối hợp: làm sao để merge không bị conflict

Conflict xảy ra khi 2 người cùng sửa một file, hoặc khi người này đổi thứ mà người kia đang dùng (tên bảng, tên cột, đường dẫn API, định dạng JSON).
Repo này đã chốt sẵn cả hai thứ đó. Chỉ cần giữ 6 quy tắc dưới đây.

## 1. Mỗi người chỉ sửa file của mình

| Người | Được sửa tự do |
|---|---|
| TV1 — M20 | `app/m20_accounts/`, `app/models/m20.py`, `app/templates/m20/`, `app/static/js/m20.js` |
| TV2 — M10 | `app/m10_lms/`, `app/models/m10.py`, `app/templates/m10/`, `app/static/js/m10.js` |
| TV3 — M11 | `app/m11_analytics/`, `app/models/m11.py`, `app/templates/m11/`, `app/static/js/m11.js`, `tests/postman/` |

**File dùng chung**, chỉ sửa bằng một PR riêng và cả nhóm phải biết:
`app/__init__.py`, `app/config.py`, `app/common/*`, `app/models/__init__.py`, `app/templates/base.html`, `app/static/js/api.js`, `app/static/css/app.css`, `requirements.txt`, `.env.example`, `tests/smoke.py`.

CSS riêng của module: dùng class có tiền tố `m10-`, `m11-`, `m20-`, viết trong `<style>` của template module mình.

## 2. Contract đã chốt, không tự đổi

- **Đường dẫn và method API**: đúng như các hàm trong `api.py` của từng module. Chỉ thay phần thân `return not_implemented()` bằng code thật.
- **Định dạng JSON**: luôn dùng `ok(data, status)` hoặc `fail(status, CODE, message)` trong `app/common/responses.py`.
  - Thành công: `{"data": ...}`
  - Lỗi: `{"error": {"code": "TASK_NOT_FOUND", "message": "..."}}`
- **Mã HTTP**: 200 đọc/sửa · 201 tạo mới · 400 `VALIDATION_ERROR` · 401 `UNAUTHORIZED` · 403 `FORBIDDEN` · 404 `<THING>_NOT_FOUND` · 409 xung đột nghiệp vụ (`EMAIL_EXISTS`, `INVALID_TRANSITION`…).
- **Quy ước dữ liệu**: tên trường `snake_case`; id là số nguyên; ngày `"YYYY-MM-DD"`; thời gian `"YYYY-MM-DDTHH:MM:SS"`.
- **Giá trị cố định**: `status ∈ todo | in_progress | review | done`, `priority ∈ low | medium | high`, `role ∈ admin | lecturer | student`, `project_role ∈ leader | member`. Đọc từ hằng số trong `app/models`, không gõ tay chuỗi khác.
- **Phân quyền**: luôn dùng `login_required`, `role_required`, `check_project_access` trong `app/m20_accounts/permissions.py`. Không tự viết lại.
- **Gọi chéo module** (chỉ được gọi những hàm này):
  - M10 → M20: `services.add_member(project_id, user_id, "leader")` khi tạo dự án.
  - M10: gọi `log_history(...)` mỗi khi đổi trạng thái, người nhận, deadline, duyệt/trả lại hay nộp minh chứng.
  - M11: chỉ **đọc** bảng của M10, không ghi. Riêng seed được ghi.

Muốn đổi contract: mở PR tiêu đề `contract: ...`, nhắn nhóm và chờ 2 người kia đồng ý.

## 3. Đổi database

- Không dùng migration. Schema được tạo lại bằng `flask --app run seed`.
- Thêm cột: chỉ thêm cột có `default` hoặc `nullable`. Không đổi tên hay xóa cột/bảng đang có trừ khi cả nhóm đồng ý.
- PR có sửa `app/models/` phải đặt tiêu đề bắt đầu bằng `schema:` và nhắn lên nhóm. Sau khi merge, mọi người pull rồi chạy lại seed.

## 4. Git workflow

```
main           ← luôn chạy được, KHÔNG push thẳng (bật branch protection trên GitHub)
└── feature/m10-kanban, feature/m20-invitations, feature/m11-risks ...   ← mỗi việc một nhánh
```

Mỗi ngày trước khi code:
```bash
git checkout main && git pull
git checkout feature/m10-kanban && git rebase main
```

Trước khi mở Pull Request:
```bash
git rebase main               # tự giải quyết conflict trên máy mình
python tests/smoke.py         # phải in "SMOKE OK"
```
- PR nhỏ, tối đa khoảng 1 ngày làm việc. PR to mới là nguồn conflict chính.
- Commit dạng `m10: thêm API tạo task`, `m20: trang quản trị user`, `shared: ...`, `schema: ...`.
- Cần 1 người khác duyệt mới được merge. Dùng **Squash and merge**.
- Gặp conflict: người merge sau tự giải quyết. Nếu conflict nằm trong file của người khác, hỏi chủ file, không tự quyết.
- Có endpoint mới hoặc đổi body/response: ghi ví dụ request/response vào mô tả PR để TV3 đưa vào Postman.

## 5. Postman

- `tests/postman/TeamSync.postman_collection.json` là file chính, **do TV3 quản lý**. Người khác không export đè lên.
- Thêm route thì chạy `python scripts/gen_postman.py` để xem trong file skeleton, rồi báo TV3.

## 6. Họp 10 phút mỗi ngày

Hôm qua merge được gì · hôm nay làm nhánh nào · đang chờ ai. Ai sắp sửa file dùng chung thì báo ở đây trước.
