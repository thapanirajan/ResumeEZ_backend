"""Make users.role nullable to support role selection after signup

Revision ID: d7e8f9a0b1c2
Revises: c3f1a2b4d5e6
Create Date: 2026-02-23 01:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'd7e8f9a0b1c2'
down_revision: Union[str, Sequence[str], None] = 'c3f1a2b4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Allow users.role to be NULL so new users can pick their role after signup."""
    op.alter_column(
        'users',
        'role',
        existing_type=postgresql.ENUM('JOB_SEEKER', 'RECRUITER', 'ADMIN', name='user_role'),
        nullable=True,
    )


def downgrade() -> None:
    """Revert users.role to NOT NULL (set any NULLs to JOB_SEEKER first)."""
    op.execute("UPDATE users SET role = 'JOB_SEEKER' WHERE role IS NULL")
    op.alter_column(
        'users',
        'role',
        existing_type=postgresql.ENUM('JOB_SEEKER', 'RECRUITER', 'ADMIN', name='user_role'),
        nullable=False,
    )
