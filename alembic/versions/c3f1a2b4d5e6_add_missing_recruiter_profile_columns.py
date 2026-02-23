"""Add missing columns to recruiter_profiles

Revision ID: c3f1a2b4d5e6
Revises: a82288bbb529
Create Date: 2026-02-23 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3f1a2b4d5e6'
down_revision: Union[str, Sequence[str], None] = 'a82288bbb529'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add company-related columns that were added to the model but never migrated."""
    op.add_column('recruiter_profiles', sa.Column('company_name', sa.String(length=255), nullable=True))
    op.add_column('recruiter_profiles', sa.Column('company_logo', sa.String(length=500), nullable=True))
    op.add_column('recruiter_profiles', sa.Column('company_website', sa.String(length=255), nullable=True))
    op.add_column('recruiter_profiles', sa.Column('industry', sa.String(length=255), nullable=True))
    op.add_column('recruiter_profiles', sa.Column('company_size', sa.String(length=100), nullable=True))
    op.add_column('recruiter_profiles', sa.Column('company_description', sa.String(length=1000), nullable=True))
    op.add_column('recruiter_profiles', sa.Column('location', sa.String(length=255), nullable=True))
    op.add_column('recruiter_profiles', sa.Column('is_verified_company', sa.Boolean(), nullable=False, server_default=sa.text('false')))


def downgrade() -> None:
    """Remove the added columns."""
    op.drop_column('recruiter_profiles', 'is_verified_company')
    op.drop_column('recruiter_profiles', 'location')
    op.drop_column('recruiter_profiles', 'company_description')
    op.drop_column('recruiter_profiles', 'company_size')
    op.drop_column('recruiter_profiles', 'industry')
    op.drop_column('recruiter_profiles', 'company_website')
    op.drop_column('recruiter_profiles', 'company_logo')
    op.drop_column('recruiter_profiles', 'company_name')
