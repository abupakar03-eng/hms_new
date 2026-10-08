"""users.must_change_password

Forces the bootstrap administrator (created with a well-known default
password) and users whose password an admin reset to choose their own at the
next login.

Revision ID: 0006_must_change_password
Revises: 0005_billing_discharge_batches
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006_must_change_password"
down_revision: Union[str, None] = "0005_billing_discharge_batches"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(
            sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default=sa.false())
        )


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_column("must_change_password")
