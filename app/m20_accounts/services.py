"""Hàm M20 cho module khác gọi (interface chéo module). Chủ sở hữu: Thành viên 1."""
from ..extensions import db
from ..models import ProjectMember


def add_member(project_id, user_id, project_role="member"):
    """M10 gọi hàm này ngay khi tạo dự án để thêm người tạo làm trưởng nhóm.
    Không commit — người gọi tự commit cùng giao dịch của mình."""
    m = ProjectMember(project_id=project_id, user_id=user_id, project_role=project_role)
    db.session.add(m)
    return m
