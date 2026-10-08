"""receipt numbers, document sequences and day closings

* ``receipt_no`` on OP/IP/pharmacy/lab bills: financial-year series such as
  OP/2026-27/000042. Existing bills are numbered in date order so printed
  history stays consistent, and the sequences continue from there.
* ``document_sequences``: one counter per series and financial year.
* ``day_closings``: the cashier's frozen end-of-day count.

Revision ID: 0007_receipts_day_close
Revises: 0006_must_change_password
"""
from datetime import datetime
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007_receipts_day_close"
down_revision: Union[str, None] = "0006_must_change_password"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

BILL_TABLES = {"op_bills": "OP", "ip_bills": "IP", "pharmacy_bills": "PH", "lab_bills": "LB"}


def _fy(value) -> str:
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", ""))
    value = value or datetime.utcnow()
    start = value.year if value.month >= 4 else value.year - 1
    return f"{start}-{str(start + 1)[-2:]}"


def upgrade() -> None:
    op.create_table(
        "document_sequences",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("series", sa.String(), nullable=False),
        sa.Column("financial_year", sa.String(), nullable=False),
        sa.Column("last_value", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("series", "financial_year", name="uq_document_sequences_series_fy"),
    )
    op.create_table(
        "day_closings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("business_date", sa.Date(), nullable=False),
        sa.Column("expected_cash", sa.Float(), nullable=False, server_default="0"),
        sa.Column("counted_cash", sa.Float(), nullable=False, server_default="0"),
        sa.Column("variance", sa.Float(), nullable=False, server_default="0"),
        sa.Column("summary", sa.JSON(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("closed_by", sa.String(), nullable=True),
        sa.Column("closed_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_day_closings_business_date", "day_closings", ["business_date"], unique=True)

    conn = op.get_bind()
    counters: dict = {}
    for table, series in BILL_TABLES.items():
        with op.batch_alter_table(table) as batch:
            batch.add_column(sa.Column("receipt_no", sa.String(), nullable=True))
        rows = conn.execute(sa.text(f"SELECT id, bill_date FROM {table} ORDER BY bill_date, id")).fetchall()
        for bill_id, bill_date in rows:
            fy = _fy(bill_date)
            counters[(series, fy)] = counters.get((series, fy), 0) + 1
            conn.execute(
                sa.text(f"UPDATE {table} SET receipt_no = :no WHERE id = :id"),
                {"no": f"{series}/{fy}/{counters[(series, fy)]:06d}", "id": bill_id},
            )
        op.create_index(f"ix_{table}_receipt_no", table, ["receipt_no"], unique=True)

    for (series, fy), value in counters.items():
        conn.execute(
            sa.text("INSERT INTO document_sequences (series, financial_year, last_value) VALUES (:s, :f, :v)"),
            {"s": series, "f": fy, "v": value},
        )


def downgrade() -> None:
    for table in BILL_TABLES:
        op.drop_index(f"ix_{table}_receipt_no", table_name=table)
        with op.batch_alter_table(table) as batch:
            batch.drop_column("receipt_no")
    op.drop_index("ix_day_closings_business_date", table_name="day_closings")
    op.drop_table("day_closings")
    op.drop_table("document_sequences")
