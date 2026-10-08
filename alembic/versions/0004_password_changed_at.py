"""users.password_changed_at

Tokens issued before a user's last password change/reset are rejected, so
rotating a password signs out every existing session, refresh tokens included.

Revision ID: 0004_password_changed_at
Revises: 0003_clinical_audit
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004_password_changed_at"
down_revision: Union[str, None] = "0003_clinical_audit"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("password_changed_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_column("password_changed_at")
