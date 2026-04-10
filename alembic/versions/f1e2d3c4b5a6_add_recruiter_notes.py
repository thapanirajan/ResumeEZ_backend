"""add recruiter_notes to job_applications and external_applications

Revision ID: f1e2d3c4b5a6
Revises: a1b2c3d4e5f6
Create Date: 2026-04-06 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f1e2d3c4b5a6'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('job_applications', sa.Column('recruiter_notes', sa.Text(), nullable=True))
    op.add_column('external_applications', sa.Column('recruiter_notes', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('external_applications', 'recruiter_notes')
    op.drop_column('job_applications', 'recruiter_notes')
