"""Toàn bộ schema của hệ thống. FILE DÙNG CHUNG.

Mỗi module sở hữu một file model riêng → không ai cùng sửa một file.
Đổi cột/bảng = PR riêng có tiền tố "schema:" và cả nhóm duyệt (xem CONTRIBUTING.md).
"""
from .m20 import (User, Workspace, WorkspaceMember, ProjectMember, Invitation,  # noqa: F401
                  ROLES, PROJECT_ROLES, WORKSPACE_ROLES)
from .m06 import (ProjectTemplate, Project, Milestone, Task, TaskDependency, Comment,  # noqa: F401
                  Attachment, TaskHistory, TASK_STATUSES, PRIORITIES, POINTS, MILESTONE_STATUSES)
from .m17 import PeerReview  # noqa: F401
