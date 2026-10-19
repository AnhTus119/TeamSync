# TeamSync

Hệ thống Web hỗ trợ quản lý bài tập nhóm trong học phần: giao nhiệm vụ, theo dõi tiến độ và đánh giá đóng góp của thành viên.
Bài tập nhóm môn **Lập trình Web** — Đại học Kinh tế Quốc dân.

## Thành viên và module

| Thành viên | Module | Phạm vi |
|---|---|---|
| Thành viên 1 | M20 — Tài khoản, SSO và phân quyền | Đăng nhập, vai trò, mời thành viên, quản trị người dùng |
| Thành viên 2 | M10 — LMS/LCMS và tài nguyên học tập | Lớp học phần, dự án nhóm, nhiệm vụ, Kanban, minh chứng, duyệt/trả lại |
| Thành viên 3 | M11 — Phân tích học tập | Thống kê tiến độ, cảnh báo trễ hạn, đánh giá chéo, dashboard, Postman |

## Công nghệ

- Backend: Python 3.11+, Flask (mỗi module một Blueprint), Flask-SQLAlchemy, SQLite
- Frontend: HTML, CSS, JavaScript (`fetch()`), Bootstrap 5, Chart.js
- Kiểm thử: Postman, `tests/smoke.py`

## Cài đặt và chạy

Windows:
```bat
git clone https://github.com/<username>/teamsync.git
cd teamsync
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
flask --app run seed
flask --app run run --debug
```

macOS/Linux: dùng `source .venv/bin/activate` và `cp .env.example .env`.

Mở http://127.0.0.1:5000. Mỗi lần pull code có thay đổi trong `app/models/`, chạy lại `flask --app run seed` (lệnh này xóa và tạo lại database).

## Tài khoản mẫu (mật khẩu `123456`)

| Email | Vai trò | Trong dự án demo |
|---|---|---|
| admin@teamsync.local | Quản trị viên | — |
| gv@teamsync.local | Giảng viên | Phụ trách lớp |
| sv1@teamsync.local | Sinh viên | Trưởng nhóm |
| sv2@teamsync.local, sv3@teamsync.local | Sinh viên | Thành viên |
| sv4@teamsync.local | Sinh viên | Ngoài nhóm |

## Kiểm thử

- `python tests/smoke.py` — bắt buộc chạy trước mỗi Pull Request
- `python tests/test_m20.py` — kiểm thử module M20
- Postman: import các file trong `tests/postman/`. Chạy request đăng nhập trước, Postman tự giữ cookie

## Cấu trúc thư mục

```
app/
├── __init__.py        # tạo app, đăng ký 3 module
├── config.py          # cấu hình đọc từ .env
├── common/            # định dạng JSON, xử lý lỗi (dùng chung)
├── models/            # m20.py · m10.py · m11.py
├── m20_accounts/      # Thành viên 1
├── m10_lms/           # Thành viên 2
├── m11_analytics/     # Thành viên 3
├── templates/         # base.html + m20/ m10/ m11/
└── static/            # js/api.js + js/m20.js m10.js m11.js
tests/
scripts/
```

## Quy tắc làm việc

Đọc `CONTRIBUTING.md` trước khi code: ai sửa file nào, định dạng API, quy trình Git.
