"""add refund statuses to order_status_enum

Revision ID: 1c464d6aad31
Revises: 6d4d313a2a09
Create Date: 2026-01-26 03:49:47.075343

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1c464d6aad31'
down_revision: Union[str, Sequence[str], None] = '6d4d313a2a09'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        "ALTER TYPE order_status_enum ADD VALUE IF NOT EXISTS 'refund_pending'"
    )
    op.execute(
        "ALTER TYPE order_status_enum ADD VALUE IF NOT EXISTS 'refunded'"
    )



def downgrade() -> None:
    """Downgrade schema."""
    pass
