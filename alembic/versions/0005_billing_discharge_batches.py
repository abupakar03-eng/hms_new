"""bill settlement, IP charge linkage and medicine batches

* ``op_bills`` / ``ip_bills``: payment_status, amount_paid, payment_history,
  cancelled_reason. Existing bills were collected at the counter, so they are
  backfilled as Paid in full.
* ``pharmacy_bills.admission_id`` / ``ip_bill_id`` and ``lab_orders.ip_bill_id``
  let the final IP bill pick up (and lock) charges raised during the stay.
* ``medicine_batches`` for first-expiry-first-out dispensing, and
  ``pharmacy_bill_items.batches`` recording which lots a sale drew from.

Revision ID: 0005_billing_discharge_batches
Revises: 0004_password_changed_at
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005_billing_discharge_batches"
down_revision: Union[str, None] = "0004_password_changed_at"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

BILL_TABLES = ("op_bills", "ip_bills")


def upgrade() -> None:
    for table in BILL_TABLES:
        with op.batch_alter_table(table) as batch:
            batch.add_column(sa.Column("payment_status", sa.String(), nullable=False, server_default="Paid"))
            batch.add_column(sa.Column("amount_paid", sa.Float(), nullable=False, server_default="0"))
            batch.add_column(sa.Column("payment_history", sa.JSON(), nullable=True))
            batch.add_column(sa.Column("cancelled_reason", sa.String(), nullable=True))
            batch.create_index(f"ix_{table}_payment_status", ["payment_status"])
        op.execute(f"UPDATE {table} SET amount_paid = COALESCE(total, 0), payment_status = 'Paid'")

    with op.batch_alter_table("pharmacy_bills") as batch:
        batch.add_column(sa.Column("admission_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("ip_bill_id", sa.Integer(), nullable=True))
        batch.create_index("ix_pharmacy_bills_admission_id", ["admission_id"])
        batch.create_index("ix_pharmacy_bills_ip_bill_id", ["ip_bill_id"])
        batch.create_foreign_key("fk_pharmacy_bills_admission", "ip_admissions", ["admission_id"], ["id"])
        batch.create_foreign_key("fk_pharmacy_bills_ip_bill", "ip_bills", ["ip_bill_id"], ["id"])

    with op.batch_alter_table("pharmacy_bill_items") as batch:
        batch.add_column(sa.Column("batches", sa.JSON(), nullable=True))

    with op.batch_alter_table("lab_orders") as batch:
        batch.add_column(sa.Column("ip_bill_id", sa.Integer(), nullable=True))
        batch.create_index("ix_lab_orders_ip_bill_id", ["ip_bill_id"])
        batch.create_foreign_key("fk_lab_orders_ip_bill", "ip_bills", ["ip_bill_id"], ["id"])

    op.create_table(
        "medicine_batches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("medicine_id", sa.Integer(), sa.ForeignKey("medicine_stocks.id"), nullable=False),
        sa.Column("batch_number", sa.String(), nullable=False),
        sa.Column("expiry_date", sa.Date(), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("received_at", sa.DateTime(), nullable=False),
        sa.Column("notes", sa.String(), nullable=True),
    )
    op.create_index("ix_medicine_batches_id", "medicine_batches", ["id"])
    op.create_index("ix_medicine_batches_medicine_id", "medicine_batches", ["medicine_id"])
    op.create_index("ix_medicine_batches_expiry_date", "medicine_batches", ["expiry_date"])


def downgrade() -> None:
    op.drop_table("medicine_batches")
    with op.batch_alter_table("lab_orders") as batch:
        batch.drop_constraint("fk_lab_orders_ip_bill", type_="foreignkey")
        batch.drop_index("ix_lab_orders_ip_bill_id")
        batch.drop_column("ip_bill_id")
    with op.batch_alter_table("pharmacy_bill_items") as batch:
        batch.drop_column("batches")
    with op.batch_alter_table("pharmacy_bills") as batch:
        batch.drop_constraint("fk_pharmacy_bills_ip_bill", type_="foreignkey")
        batch.drop_constraint("fk_pharmacy_bills_admission", type_="foreignkey")
        batch.drop_index("ix_pharmacy_bills_ip_bill_id")
        batch.drop_index("ix_pharmacy_bills_admission_id")
        batch.drop_column("ip_bill_id")
        batch.drop_column("admission_id")
    for table in BILL_TABLES:
        with op.batch_alter_table(table) as batch:
            batch.drop_index(f"ix_{table}_payment_status")
            batch.drop_column("cancelled_reason")
            batch.drop_column("payment_history")
            batch.drop_column("amount_paid")
            batch.drop_column("payment_status")
