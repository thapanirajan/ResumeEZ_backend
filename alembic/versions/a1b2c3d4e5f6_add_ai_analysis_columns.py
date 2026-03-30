"""add ai analysis columns to job_applications and external_applications

Revision ID: a1b2c3d4e5f6
Revises: 08973ba6996a
Create Date: 2026-03-21 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '08973ba6996a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('job_applications', sa.Column('ai_score', sa.Integer(), nullable=True))
    op.add_column('job_applications', sa.Column('ai_analysis', JSONB(), nullable=True))
    op.add_column('job_applications', sa.Column('ai_scored_at', sa.DateTime(timezone=True), nullable=True))

    op.add_column('external_applications', sa.Column('ai_score', sa.Integer(), nullable=True))
    op.add_column('external_applications', sa.Column('ai_analysis', JSONB(), nullable=True))
    op.add_column('external_applications', sa.Column('ai_scored_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('external_applications', 'ai_scored_at')
    op.drop_column('external_applications', 'ai_analysis')
    op.drop_column('external_applications', 'ai_score')

    op.drop_column('job_applications', 'ai_scored_at')
    op.drop_column('job_applications', 'ai_analysis')
    op.drop_column('job_applications', 'ai_score')
