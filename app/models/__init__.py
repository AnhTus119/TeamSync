"""Toàn bộ schema của hệ thống. FILE DÙNG CHUNG.

Mỗi module sở hữu một file model riêng → 3 người không bao giờ cùng sửa một file.
Đổi cột/bảng = PR riêng có tiền tố "schema:" và cả nhóm duyệt (xem CONTRIBUTING.md).
"""
from .m20 import User, ProjectMember, Invitation, ROLES, PROJECT_ROLES  # noqa: F401
from .m10 import Course, Project, Task, Comment, Attachment, TaskHistory, TASK_STATUSES, PRIORITIES  # noqa: F401
from .m11 import PeerReview  # noqa: F401
