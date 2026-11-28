"""Kiểm tra (và sửa) tài khoản demo trong database mà run.py đang dùng.

    python tools/kiem_tra_tai_khoan.py          # chỉ kiểm tra, không sửa gì
    python tools/kiem_tra_tai_khoan.py --sua    # đặt lại mật khẩu 12345 và mở khóa các tài khoản demo có trong database

Database được tìm giống run.py: thư mục TEAMSYNC_DATA_DIR nếu có, không thì instance/ cạnh run.py.
Nếu database không có dữ liệu demo (ví dụ chép từ bản cũ), công cụ hướng dẫn tạo lại; nó không xóa dữ liệu.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
INSTANCE = Path(os.environ.get('TEAMSYNC_DATA_DIR', str(ROOT / 'instance'))).resolve()
DB = INSTANCE / 'teamsync-workspace.db'
DEMO = ['minhanh@sv.teamsync.test', 'thuha@sv.teamsync.test', 'quocbao@sv.teamsync.test', 'gialinh@sv.teamsync.test',
        'annhien@sv.teamsync.test', 'khanhan@gv.teamsync.test', 'quangminh@gv.teamsync.test', 'thuhang@gv.teamsync.test',
        'daotao@gv.teamsync.test', 'admin@teamsync.test']
PASSWORD = '12345'


def main():
    fix = '--sua' in sys.argv
    print(f'Database: {DB}')
    if not DB.exists():
        print('-> Chưa có database. Chạy "python run.py" một lần để tạo database và dữ liệu demo.')
        return 1
    os.environ['DATABASE_URL'] = 'sqlite:///' + str(DB).replace('\\', '/')
    os.environ.setdefault('PRIVATE_STORAGE', str(INSTANCE / 'private'))
    from app import create_app
    app = create_app()
    with app.app_context():
        from flask_migrate import upgrade
        from app.extensions import db
        from app.models import User
        from app.models.academic import RuntimeSetting
        from app.academic.workflow_seed import KEY
        upgrade(directory=str(ROOT / 'migrations'))
        total = User.query.count()
        demo = db.session.get(RuntimeSetting, KEY) is not None
        print(f'Số tài khoản: {total} · Dữ liệu demo Khoa học máy tính: {"CÓ" if demo else "KHÔNG"}')
        missing, bad = [], []
        for email in DEMO:
            u = User.query.filter(db.func.lower(User.email) == email).first()
            if not u:
                missing.append(email)
                print(f'  [THIẾU]  {email}')
                continue
            ok = u.check_password(PASSWORD)
            state = 'OK' if ok and u.is_active else ('SAI MẬT KHẨU' if not ok else 'ĐANG BỊ KHÓA')
            print(f'  [{state}]  {email}')
            if state != 'OK':
                bad.append(u)
        if bad and fix:
            for u in bad:
                u.set_password(PASSWORD)
                u.is_active = True
            db.session.commit()
            print(f'-> Đã đặt lại mật khẩu {PASSWORD} và mở khóa {len(bad)} tài khoản.')
        elif bad:
            print(f'-> {len(bad)} tài khoản sai mật khẩu hoặc bị khóa. Chạy lại với --sua để đặt lại mật khẩu {PASSWORD}.')
        if missing:
            print('-> Database này không phải dữ liệu demo hiện tại (thường do chép thư mục instance từ bản cũ).')
            print('   Muốn có đúng các tài khoản trong README: tắt run.py, đổi tên thư mục instance (ví dụ instance-cu) để sao lưu,')
            print('   rồi chạy lại "python run.py": database mới và dữ liệu demo được tạo tự động.')
        if not missing and not bad:
            print('-> Tất cả tài khoản demo đăng nhập được với mật khẩu 12345.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
