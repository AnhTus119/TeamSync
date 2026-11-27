"""Thêm dữ liệu ngẫu nhiên vào database demo của run.py (instance/teamsync-workspace.db).

Cách dùng (dừng run.py trước rồi chạy, sau đó chạy lại run.py):
    python seed_random.py                      # 6 dự án, mỗi dự án 8 task
    python seed_random.py --projects 10 --tasks 12
    python seed_random.py --seed 42            # cùng seed => cùng kiểu dữ liệu

Mỗi lần chạy thêm một đợt mới (mã lớp RND-<đợt>-<số>), không xóa dữ liệu cũ.
Muốn làm lại từ đầu: dừng ứng dụng, sao lưu rồi xóa/đổi tên thư mục instance.
"""
import argparse

parser = argparse.ArgumentParser(description='Sinh dữ liệu ngẫu nhiên cho TeamSync')
parser.add_argument('--projects', type=int, default=6, help='số học phần/dự án mới (mặc định 6)')
parser.add_argument('--tasks', type=int, default=8, help='số task mỗi dự án (mặc định 8)')
parser.add_argument('--students', type=int, default=12, help='số sinh viên ngẫu nhiên mới (mặc định 12)')
parser.add_argument('--seed', type=int, default=None, help='hạt giống ngẫu nhiên để tái lập')
args = parser.parse_args()

from run import app, prepare  # noqa: E402  (dùng chung cấu hình và database với run.py)

prepare()
with app.app_context():
    from app.academic.random_seed import seed_random
    r = seed_random(projects=max(1, args.projects), tasks=max(1, args.tasks), seed=args.seed, students=max(6, args.students))
print(f"Đã thêm đợt {r['batch']}: {r['courses']} học phần, {r['projects']} dự án, {r['tasks']} task, {r['submissions']} lần nộp.")
print('Đăng nhập (mật khẩu 12345): minhanh@sv.teamsync.test, khanhan@gv.teamsync.test hoặc', ', '.join(r['students'][:3]), '…')
