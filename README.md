# TeamSync

Hệ thống Web quản lý dự án cho nhóm làm việc: giao việc có minh chứng, cảnh báo rủi ro trễ hạn có giải thích và đánh giá đóng góp minh bạch.
Bài tập nhóm môn **Lập trình Web** — Đại học Kinh tế Quốc dân.

## Thành viên và module

| Thành viên | Module | Phạm vi | Tài liệu |
|---|---|---|---|
| Đoàn Anh Tú | M20 — Tài khoản, SSO và phân quyền | Tài khoản, không gian làm việc, vai trò, lời mời, quản trị | [docs/M20.md](docs/M20.md) |
| Dương Khánh Duy | M06 — Quản lý khoa học (quản lý dự án) | Dự án từ mẫu, cột mốc, nhiệm vụ, phụ thuộc, Kanban, minh chứng, duyệt, nghiệm thu | [docs/M06.md](docs/M06.md) |
| Phạm Phương Anh | M17 — Dashboard, báo cáo và đánh giá | Thống kê, cảnh báo rủi ro, đèn sức khỏe, sổ đóng góp, đánh giá chéo, CSV | [docs/M17.md](docs/M17.md) |

Luồng chính: tạo dự án → mời thành viên → lập cột mốc, giao việc → nộp minh chứng → duyệt/trả lại → nghiệm thu cột mốc → xem dashboard và sổ đóng góp.

## Công nghệ

- Backend: Python 3.11+, Flask (mỗi module một Blueprint), Flask-SQLAlchemy, SQLite, Flask Session
- Frontend: HTML, JavaScript (`fetch()` qua `static/js/api.js`), Bootstrap 5, Chart.js
- Kiểm thử: test tự động trong `tests/`, Postman

## Cài đặt và chạy

Windows (PowerShell hoặc Terminal của PyCharm):
```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
flask --app run seed
flask --app run run --debug
```
macOS/Linux: `source .venv/bin/activate` và `cp .env.example .env`.

Mở http://127.0.0.1:5000. Database ở `instance/teamsync.db`, file minh chứng ở `instance/uploads/` (đều không commit).
`flask --app run seed` **xóa sạch và tạo lại** database — chạy lại mỗi khi pull code có thay đổi trong `app/models/`.

## Tài khoản mẫu (mật khẩu `123456`)

| Email | Vai trò | Trong dự án "TeamSync demo" |
|---|---|---|
| admin@teamsync.local | Quản trị viên | — |
| gv@teamsync.local | Người dùng, chủ workspace "Lớp Lập trình Web 01" | Giám sát |
| sv1@teamsync.local | Người dùng | Quản lý dự án |
| sv2@teamsync.local, sv3@teamsync.local | Người dùng | Thành viên |
| sv4@teamsync.local | Người dùng | Ngoài dự án (để thử bị chặn quyền) |

Dự án demo có sẵn đủ tình huống: việc đã duyệt, việc bị trả lại, việc lâu không cập nhật, việc sắp tới hạn chưa bắt đầu, việc quá hạn, việc bị chặn bởi phụ thuộc, cột mốc đã nghiệm thu.

## Kiểm thử

```bat
python tests/smoke.py        :: bắt buộc trước mỗi Pull Request
python tests/test_m20.py
:: TV2 thêm tests/test_m06.py, TV3 thêm tests/test_m17.py khi làm module
```
Postman: import `tests/postman/TeamSync.skeleton.postman_collection.json` + `TeamSync.postman_environment.json` (mỗi endpoint một request). Endpoint chưa cài đặt trả 501.
TV3 xây collection luồng nghiệp vụ đầy đủ có kiểm tra tự động.

## Cấu trúc thư mục

```
app/
├── __init__.py          # tạo app, đăng ký 3 module, lệnh seed (dùng chung)
├── config.py            # cấu hình đọc từ .env (ngưỡng cảnh báo ở đây)
├── common/              # responses.py (ok/fail/require_json), errors.py, utils.py
├── models/              # m20.py · m06.py · m17.py — mỗi module một file schema
├── m20_accounts/        # TV1: api.py, pages.py, permissions.py, services.py, seed.py
├── m06_projects/        # TV2: api.py, pages.py, services.py, seed.py
├── m17_reports/         # TV3: api.py, pages.py, seed.py
├── templates/           # base.html, _project_nav.html + m20/ m06/ m17/
└── static/              # css/app.css, js/api.js + js/m20.js m06.js m17.js
docs/                    # tài liệu từng module
scripts/                 # gen_postman.py
tests/                   # smoke.py, test_m20/m06/m17.py, postman/
```
