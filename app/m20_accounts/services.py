"""Hàm M20 cho module khác gọi (interface chéo module). Chủ sở hữu: Thành viên 1."""
from ..extensions import db
from ..models import ProjectMember, WorkspaceMember


def add_member(project_id, user_id, project_role="member"):
    """M06 gọi ngay khi tạo dự án để người tạo thành quản lý. Không commit — người gọi tự commit."""
    m = ProjectMember(project_id=project_id, user_id=user_id, project_role=project_role)
    db.session.add(m)
    return m


def ensure_workspace_member(workspace_id, user_id):
    """Người được mời vào dự án tự động trở thành thành viên workspace chứa dự án đó."""
    if not WorkspaceMember.query.filter_by(workspace_id=workspace_id, user_id=user_id).first():
        db.session.add(WorkspaceMember(workspace_id=workspace_id, user_id=user_id, role="member"))
