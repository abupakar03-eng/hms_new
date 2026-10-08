"""clinical audit trail

Extends `audit_logs` with the clinical linkage and before/after state needed to
reconstruct what changed, and adds `created_by` / `updated_by` to the clinical
record tables.

Revision ID: 0003_clinical_audit
Revises: 0002_ipd_module
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_clinical_audit"
down_revision: Union[str, None] = "0002_ipd_module"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Tables where knowing the author matters clinically or medico-legally.
AUDITED_TABLES = (
    "patients",
    "casesheets",
    "ip_admissions",
    "nursing_notes",
    "medication_orders",
    "medication_administrations",
    "discharge_summaries",
    "lab_orders",
    "lab_reports",
)


def upgrade() -> None:
    # --- audit_logs: clinical linkage + before/after state -------------------
    with op.batch_alter_table("audit_logs") as batch:
        batch.add_column(sa.Column("actor_role", sa.String(length=50), nullable=True))
        batch.add_column(sa.Column("entity_type", sa.String(length=50), nullable=True))
        batch.add_column(sa.Column("entity_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("patient_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("before_state", sa.Text(), nullable=True))
        batch.add_column(sa.Column("after_state", sa.Text(), nullable=True))
        batch.create_index("ix_audit_logs_entity_type", ["entity_type"])
        batch.create_index("ix_audit_logs_entity_id", ["entity_id"])
        batch.create_index("ix_audit_logs_patient_id", ["patient_id"])

    op.create_index("ix_audit_logs_entity", "audit_logs", ["entity_type", "entity_id"])

    # --- clinical tables: record authorship ---------------------------------
    for table in AUDITED_TABLES:
        with op.batch_alter_table(table) as batch:
            batch.add_column(sa.Column("created_by", sa.String(length=100), nullable=True))
            batch.add_column(sa.Column("updated_by", sa.String(length=100), nullable=True))

    # Backfill: the earliest audit entry for a patient is the best available
    # evidence of who registered it. Existing rows stay NULL rather than being
    # given a fabricated author.
    op.execute(
        """
        UPDATE patients
           SET created_by = (
               SELECT a.username FROM audit_logs a
                WHERE a.details LIKE '%/patients/%' OR a.action LIKE '%PATIENTS%'
                ORDER BY a.timestamp ASC LIMIT 1
           )
         WHERE created_by IS NULL
        """
    )


def downgrade() -> None:
    for table in AUDITED_TABLES:
        with op.batch_alter_table(table) as batch:
            batch.drop_column("updated_by")
            batch.drop_column("created_by")

    op.drop_index("ix_audit_logs_entity", table_name="audit_logs")
    with op.batch_alter_table("audit_logs") as batch:
        batch.drop_index("ix_audit_logs_patient_id")
        batch.drop_index("ix_audit_logs_entity_id")
        batch.drop_index("ix_audit_logs_entity_type")
        batch.drop_column("after_state")
        batch.drop_column("before_state")
        batch.drop_column("patient_id")
        batch.drop_column("entity_id")
        batch.drop_column("entity_type")
        batch.drop_column("actor_role")
