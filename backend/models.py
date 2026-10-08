"""SQLAlchemy ORM models for the Hospital Management & Billing system.

Notes on conventions used here:
  * JSON columns always use a callable default (``default=dict`` / ``default=list``)
    rather than a literal. A literal mutable default is shared by every instance
    that never sets the column, which silently corrupts unrelated rows.
  * Timestamps that are compared across rows use ``utcnow`` (naive UTC) so that
    SQLite comparisons stay consistent.
  * Business-status columns are plain strings, but the set of legal values lives
    in ``backend.constants`` and is enforced at the API boundary.
"""

from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    DateTime,
    Date,
    Boolean,
    ForeignKey,
    JSON,
    Text,
    Index,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from datetime import datetime, timezone

from .database import Base


def utcnow() -> datetime:
    """Naive UTC timestamp (matches the values historically stored in the DB)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ============================
# Identity & Audit
# ============================
class User(Base):
    """A login account.

    ``role == "Patient"`` accounts carry a ``patient_id`` link and are confined to
    the ``/portal/*`` surface, where every query is scoped to that patient. All
    other roles are hospital staff.
    """

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, nullable=False)  # see constants.ROLES
    is_active = Column(Boolean, default=True, nullable=False)

    # Self-service patient accounts only.
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=True, index=True)

    full_name = Column(String, nullable=True)
    email = Column(String, nullable=True, index=True)
    phone = Column(String, nullable=True)
    last_login_at = Column(DateTime, nullable=True)
    # Tokens issued before this instant are rejected, so a password change or
    # reset signs out every existing session (including refresh tokens).
    password_changed_at = Column(DateTime, nullable=True)

    # Staff master (doctors, nurses, technicians, desk staff).
    employee_code = Column(String, unique=True, nullable=True, index=True)
    designation = Column(String, nullable=True)
    specialization = Column(String, nullable=True)
    license_number = Column(String, nullable=True)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True, index=True)
    joining_date = Column(Date, nullable=True)
    consultation_fee = Column(Float, nullable=True)  # doctors only

    created_at = Column(DateTime, default=utcnow, nullable=False)

    patient = relationship("Patient", foreign_keys=[patient_id])
    # Two FKs exist between users and departments (department.head_doctor_id and
    # users.department_id), so the join column must be stated explicitly.
    department = relationship("Department", foreign_keys=[department_id])


# ============================
# Hospital structure (departments → wards → rooms → beds)
# ============================
class Department(Base):
    """A clinical, diagnostic or administrative department."""

    __tablename__ = "departments"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True, index=True)
    code = Column(String, nullable=False, unique=True, index=True)
    department_type = Column(String, default="Clinical", nullable=False)
    description = Column(Text, nullable=True)
    # A department is headed by a doctor, and a user belongs to a department:
    # that is a genuine cycle, so this side is created by ALTER after both tables
    # exist (use_alter), which keeps create_all and migrations orderable.
    head_doctor_id = Column(
        Integer,
        ForeignKey("users.id", name="fk_departments_head_doctor_id_users", use_alter=True),
        nullable=True,
    )
    phone = Column(String, nullable=True)
    location = Column(String, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    head_doctor = relationship("User", foreign_keys=[head_doctor_id])
    wards = relationship("Ward", back_populates="department")


class Ward(Base):
    __tablename__ = "wards"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, index=True)
    code = Column(String, nullable=False, unique=True, index=True)
    ward_type = Column(String, default="General", nullable=False)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True, index=True)
    floor = Column(String, nullable=True)
    building = Column(String, nullable=True)
    # Charged per night to the IP bill when no room/bed overrides it.
    daily_charge = Column(Float, default=0.0)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    department = relationship("Department", back_populates="wards")
    rooms = relationship("Room", back_populates="ward", cascade="all, delete-orphan")


class Room(Base):
    __tablename__ = "rooms"

    id = Column(Integer, primary_key=True, index=True)
    ward_id = Column(Integer, ForeignKey("wards.id"), nullable=False, index=True)
    room_number = Column(String, nullable=False)
    room_type = Column(String, nullable=True)
    floor = Column(String, nullable=True)
    # Null means "inherit the ward's daily charge".
    daily_charge = Column(Float, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=utcnow)

    ward = relationship("Ward", back_populates="rooms")
    beds = relationship("Bed", back_populates="room", cascade="all, delete-orphan")

    __table_args__ = (UniqueConstraint("ward_id", "room_number", name="uq_room_per_ward"),)


class Bed(Base):
    """A physically allocatable bed. Occupancy is derived from open allocations."""

    __tablename__ = "beds"

    id = Column(Integer, primary_key=True, index=True)
    room_id = Column(Integer, ForeignKey("rooms.id"), nullable=False, index=True)
    bed_code = Column(String, nullable=False)
    bed_type = Column(String, nullable=True)
    status = Column(String, default="Available", nullable=False, index=True)
    # Null means "inherit the room, then the ward".
    daily_charge = Column(Float, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    room = relationship("Room", back_populates="beds")

    __table_args__ = (UniqueConstraint("room_id", "bed_code", name="uq_bed_per_room"),)



class ClinicalAuditMixin:
    """Records who created and who last changed a clinical record.

    Applied to the tables where knowing the author matters clinically or
    medico-legally (who documented the vitals, who ordered the drug, who signed
    the discharge summary).
    """

    created_by = Column(String(100), nullable=True)
    updated_by = Column(String(100), nullable=True)


class AuditLog(Base):
    """Append-only record of who did what.

    `before_state` / `after_state` make clinical edits reconstructible after the
    fact — for a regulated record it is not enough to know that something
    changed, the values matter too.
    """

    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=True)
    username = Column(String, nullable=True)
    actor_role = Column(String(50), nullable=True)
    action = Column(String, nullable=False)
    details = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=utcnow, index=True)
    ip_address = Column(String, nullable=True)

    # Clinical linkage: which record this entry belongs to.
    entity_type = Column(String(50), nullable=True, index=True)
    entity_id = Column(Integer, nullable=True, index=True)
    patient_id = Column(Integer, nullable=True, index=True)
    before_state = Column(Text, nullable=True)
    after_state = Column(Text, nullable=True)

    __table_args__ = (
        Index("ix_audit_logs_entity", "entity_type", "entity_id"),
    )


class TokenBlacklist(Base):
    """Persisted JWT revocation list.

    The previous in-memory set was lost on every restart and grew without bound,
    which meant a logout was purely cosmetic after a deploy.
    """

    __tablename__ = "token_blacklist"

    id = Column(Integer, primary_key=True, index=True)
    token = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, nullable=True)
    expires_at = Column(DateTime, nullable=False, index=True)
    revoked_at = Column(DateTime, default=utcnow, nullable=False)


class HospitalSettings(Base):
    __tablename__ = "hospital_settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, nullable=False, index=True)
    value = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)


# ============================
# Patients & OP
# ============================
class Patient(ClinicalAuditMixin, Base):
    __tablename__ = "patients"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, index=True)
    age = Column(Integer, nullable=False)
    gender = Column(String, nullable=False)
    phone = Column(String, nullable=True, index=True)
    address = Column(String, nullable=True)
    aadhaar = Column(String, nullable=True, index=True)
    blood_group = Column(String, nullable=True)
    details = Column(JSON, default=dict)
    created_at = Column(DateTime, default=utcnow, index=True)

    tokens = relationship("OPToken", back_populates="patient")
    casesheets = relationship("Casesheet", back_populates="patient")
    pharmacy_bills = relationship("PharmacyBill", back_populates="patient")
    lab_bills = relationship("LabBill", back_populates="patient")
    ip_admissions = relationship("IPAdmission", back_populates="patient")
    lab_reports = relationship("LabReport", back_populates="patient")
    op_bills = relationship("OPBill", back_populates="patient")
    ip_bills = relationship("IPBill", back_populates="patient")
    lab_orders = relationship("LabOrder", back_populates="patient")
    appointments = relationship("Appointment", back_populates="patient")
    insurance_claims = relationship("InsuranceClaim", back_populates="patient")


class OPToken(Base):
    __tablename__ = "op_tokens"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False, index=True)
    token_number = Column(Integer, nullable=False)
    session = Column(String, nullable=False)  # "Morning" | "Evening"
    date = Column(Date, nullable=False, index=True)
    status = Column(String, default="Pending", nullable=False)
    fee = Column(Float, default=0.0)
    is_billed = Column(Boolean, default=False)
    doctor_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    doctor_name = Column(String, nullable=True)
    department = Column(String, nullable=True)
    details = Column(JSON, default=dict)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    patient = relationship("Patient", back_populates="tokens")
    doctor = relationship("User")

    __table_args__ = (
        Index("ix_op_tokens_date_session", "date", "session"),
    )


class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False, index=True)
    doctor_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    doctor_name = Column(String, nullable=True)
    appointment_date = Column(Date, nullable=False, index=True)
    time_slot = Column(String, nullable=True)
    reason = Column(String, nullable=True)
    status = Column(String, default="Scheduled")
    details = Column(JSON, default=dict)
    created_at = Column(DateTime, default=utcnow)
    # Who booked it: "Patient" for self-service, otherwise the staff username.
    booked_by = Column(String, nullable=True)
    cancelled_reason = Column(String, nullable=True)

    patient = relationship("Patient", back_populates="appointments")
    doctor = relationship("User", foreign_keys=[doctor_id])


class Casesheet(ClinicalAuditMixin, Base):
    __tablename__ = "casesheets"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False, index=True)
    token_id = Column(Integer, ForeignKey("op_tokens.id"), nullable=True)
    doctor_name = Column(String, nullable=True)
    date = Column(Date, default=lambda: utcnow().date(), index=True)

    # Vitals
    vitals_bp = Column(String, nullable=True)
    vitals_pulse = Column(String, nullable=True)
    vitals_temp = Column(String, nullable=True)
    vitals_resp = Column(String, nullable=True)
    vitals_spo2 = Column(String, nullable=True)
    vitals_weight = Column(String, nullable=True)

    # Clinical narrative
    chief_complaint = Column(Text, nullable=True)
    symptoms = Column(Text, nullable=True)
    hpi = Column(Text, nullable=True)
    pmh = Column(Text, nullable=True)
    family_history = Column(Text, nullable=True)
    allergies = Column(Text, nullable=True)
    clinical_findings = Column(Text, nullable=True)
    diagnosis = Column(Text, nullable=True)
    icd_code = Column(String, nullable=True)
    treatment_plan = Column(Text, nullable=True)
    advice = Column(Text, nullable=True)
    follow_up_date = Column(Date, nullable=True)

    prescribed_medicines = Column(JSON, default=list)  # [{name, quantity, dosage, duration}]
    prescribed_labs = Column(JSON, default=list)       # [test_name]

    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    patient = relationship("Patient", back_populates="casesheets")
    token = relationship("OPToken")


# ============================
# Inventory & Pharmacy
# ============================
class MedicineStock(Base):
    __tablename__ = "medicine_stocks"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    category = Column(String, nullable=False)  # "Pharmacy" | "Lab" | "Consumable"
    batch_no = Column(String, nullable=True)
    expiry_date = Column(Date, nullable=True, index=True)
    quantity = Column(Integer, default=0)
    unit_price = Column(Float, default=0.0)
    min_stock_level = Column(Integer, default=10)
    details = Column(JSON, default=dict)

    # ``quantity`` stays the item total. Batches account for part (or, for stock
    # received after batch tracking, all) of it; any remainder is legacy
    # "unbatched" stock governed by the item-level ``expiry_date``.
    batches = relationship(
        "MedicineBatch", back_populates="medicine", cascade="all, delete-orphan",
        order_by="MedicineBatch.expiry_date",
    )

    @property
    def sellable_quantity(self) -> int:
        """Units that may be dispensed today: everything except expired lots."""
        from datetime import date

        today = date.today()
        batched = sum(b.quantity or 0 for b in self.batches)
        sellable = sum(
            b.quantity or 0 for b in self.batches if b.expiry_date is None or b.expiry_date >= today
        )
        unbatched = max((self.quantity or 0) - batched, 0)
        if self.expiry_date is None or self.expiry_date >= today:
            sellable += unbatched
        return sellable


class MedicineBatch(Base):
    """One received lot of a stock item, sold first-expiry-first-out."""

    __tablename__ = "medicine_batches"

    id = Column(Integer, primary_key=True, index=True)
    medicine_id = Column(Integer, ForeignKey("medicine_stocks.id"), nullable=False, index=True)
    batch_number = Column(String, nullable=False)
    expiry_date = Column(Date, nullable=True, index=True)
    quantity = Column(Integer, nullable=False, default=0)
    received_at = Column(DateTime, default=utcnow, nullable=False)
    notes = Column(String, nullable=True)

    medicine = relationship("MedicineStock", back_populates="batches")


class StockTransaction(Base):
    __tablename__ = "stock_transactions"

    id = Column(Integer, primary_key=True, index=True)
    medicine_id = Column(Integer, ForeignKey("medicine_stocks.id"), index=True)
    type = Column(String, nullable=False)  # "Stock In" | "Stock Out" | "Sale"
    quantity = Column(Integer, nullable=False)
    date = Column(DateTime, default=utcnow, index=True)
    notes = Column(String, nullable=True)
    details = Column(JSON, default=dict)


class PharmacyBill(Base):
    __tablename__ = "pharmacy_bills"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=True, index=True)
    patient_name = Column(String, nullable=True)  # walk-in patients
    bill_date = Column(DateTime, default=utcnow, index=True)
    subtotal = Column(Float, nullable=False)
    discount = Column(Float, default=0.0)   # percent
    gst = Column(Float, default=0.0)        # percent
    total = Column(Float, nullable=False)
    payment_mode = Column(String, default="Cash")
    payment_details = Column(JSON, nullable=True)
    details = Column(JSON, default=dict)

    # Set when the sale is charged to an inpatient stay (payment_mode "IP Credit");
    # ``ip_bill_id`` is filled once the final IP bill includes it.
    admission_id = Column(Integer, ForeignKey("ip_admissions.id"), nullable=True, index=True)
    ip_bill_id = Column(Integer, ForeignKey("ip_bills.id"), nullable=True, index=True)

    patient = relationship("Patient", back_populates="pharmacy_bills")
    items = relationship("PharmacyBillItem", back_populates="bill", cascade="all, delete-orphan")


class PharmacyBillItem(Base):
    __tablename__ = "pharmacy_bill_items"

    id = Column(Integer, primary_key=True, index=True)
    bill_id = Column(Integer, ForeignKey("pharmacy_bills.id"), index=True)
    medicine_id = Column(Integer, ForeignKey("medicine_stocks.id"))
    medicine_name = Column(String, nullable=False)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Float, nullable=False)
    total_price = Column(Float, nullable=False)
    # Which batches the units came from: [{batch_id, batch_number, expiry_date, quantity}]
    batches = Column(JSON, nullable=True)

    bill = relationship("PharmacyBill", back_populates="items")


class LabBill(Base):
    __tablename__ = "lab_bills"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=True, index=True)
    patient_name = Column(String, nullable=True)
    bill_date = Column(DateTime, default=utcnow, index=True)
    subtotal = Column(Float, default=0.0)
    total = Column(Float, nullable=False)
    discount = Column(Float, default=0.0)  # percent
    gst = Column(Float, default=0.0)       # percent
    status = Column(String, default="Pending")  # Pending | Paid | Cancelled
    payment_mode = Column(String, default="Cash")
    payment_details = Column(JSON, nullable=True)
    notes = Column(Text, nullable=True)

    patient = relationship("Patient", back_populates="lab_bills")
    items = relationship("LabBillItem", back_populates="bill", cascade="all, delete-orphan")
    orders = relationship("LabOrder", back_populates="bill")


class LabBillItem(Base):
    __tablename__ = "lab_bill_items"

    id = Column(Integer, primary_key=True, index=True)
    bill_id = Column(Integer, ForeignKey("lab_bills.id"), index=True)
    test_id = Column(Integer, ForeignKey("lab_test_master.id"), nullable=True)
    test_name = Column(String, nullable=False)
    price = Column(Float, nullable=False)

    bill = relationship("LabBill", back_populates="items")


# ============================
# Inpatient
# ============================
class IPAdmission(ClinicalAuditMixin, Base):
    __tablename__ = "ip_admissions"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False, index=True)
    admission_date = Column(DateTime, default=utcnow, index=True)

    # Location: bed is the source of truth; ward/room are denormalised for
    # historical bills so an old invoice still shows where the patient stayed.
    bed_id = Column(Integer, ForeignKey("beds.id"), nullable=True, index=True)
    ward_number = Column(String, nullable=True)
    room_number = Column(String, nullable=True)
    bed_code = Column(String, nullable=True)

    doctor_in_charge = Column(String, nullable=True)
    attending_doctor_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True, index=True)

    admission_type = Column(String, default="Planned", nullable=False)
    admission_source = Column(String, default="OPD", nullable=True)
    reason_for_admission = Column(Text, nullable=True)
    provisional_diagnosis = Column(Text, nullable=True)
    admission_notes = Column(Text, nullable=True)

    expected_discharge_date = Column(Date, nullable=True)
    discharge_date = Column(DateTime, nullable=True)
    discharged_by = Column(String, nullable=True)
    discharge_type = Column(String, nullable=True)
    status = Column(String, default="Admitted", nullable=False, index=True)

    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    patient = relationship("Patient", back_populates="ip_admissions")
    ip_bills = relationship("IPBill", back_populates="admission")
    bed = relationship("Bed")
    attending_doctor = relationship("User", foreign_keys=[attending_doctor_id])
    department = relationship("Department")
    allocations = relationship(
        "BedAllocation", back_populates="admission", cascade="all, delete-orphan",
        order_by="BedAllocation.allocated_at",
    )
    transfers = relationship(
        "PatientTransfer", back_populates="admission", cascade="all, delete-orphan",
        order_by="PatientTransfer.transferred_at",
    )
    nursing_notes = relationship(
        "NursingNote", back_populates="admission", cascade="all, delete-orphan",
        order_by="NursingNote.recorded_at.desc()",
    )
    medication_orders = relationship(
        "MedicationOrder", back_populates="admission", cascade="all, delete-orphan",
    )
    discharge_summary = relationship(
        "DischargeSummary", back_populates="admission", uselist=False,
        cascade="all, delete-orphan",
    )


class BedAllocation(Base):
    """History of which bed an admission held, and when.

    A row is opened on allocation and closed (``released_at``) on transfer or
    discharge, so occupancy can always be reconstructed for any point in time.
    """

    __tablename__ = "bed_allocations"

    id = Column(Integer, primary_key=True, index=True)
    admission_id = Column(Integer, ForeignKey("ip_admissions.id"), nullable=False, index=True)
    bed_id = Column(Integer, ForeignKey("beds.id"), nullable=False, index=True)
    allocated_at = Column(DateTime, default=utcnow, nullable=False, index=True)
    released_at = Column(DateTime, nullable=True, index=True)
    allocated_by = Column(String, nullable=True)
    released_by = Column(String, nullable=True)
    release_reason = Column(String, nullable=True)

    admission = relationship("IPAdmission", back_populates="allocations")
    bed = relationship("Bed")


class PatientTransfer(Base):
    """A bed-to-bed move within (or between) wards."""

    __tablename__ = "patient_transfers"

    id = Column(Integer, primary_key=True, index=True)
    admission_id = Column(Integer, ForeignKey("ip_admissions.id"), nullable=False, index=True)
    from_bed_id = Column(Integer, ForeignKey("beds.id"), nullable=True)
    to_bed_id = Column(Integer, ForeignKey("beds.id"), nullable=False)
    from_ward = Column(String, nullable=True)
    to_ward = Column(String, nullable=True)
    reason = Column(Text, nullable=True)
    transferred_by = Column(String, nullable=True)
    transferred_at = Column(DateTime, default=utcnow, nullable=False, index=True)

    admission = relationship("IPAdmission", back_populates="transfers")
    from_bed = relationship("Bed", foreign_keys=[from_bed_id])
    to_bed = relationship("Bed", foreign_keys=[to_bed_id])


class NursingNote(ClinicalAuditMixin, Base):
    """Shift observation chart entry."""

    __tablename__ = "nursing_notes"

    id = Column(Integer, primary_key=True, index=True)
    admission_id = Column(Integer, ForeignKey("ip_admissions.id"), nullable=False, index=True)
    shift = Column(String, default="Morning", nullable=False)
    recorded_at = Column(DateTime, default=utcnow, nullable=False, index=True)
    recorded_by = Column(String, nullable=True)

    temperature = Column(Float, nullable=True)        # Celsius
    pulse = Column(Integer, nullable=True)            # bpm
    respiratory_rate = Column(Integer, nullable=True)  # per minute
    bp_systolic = Column(Integer, nullable=True)
    bp_diastolic = Column(Integer, nullable=True)
    spo2 = Column(Integer, nullable=True)             # %
    pain_score = Column(Integer, nullable=True)       # 0-10
    blood_sugar = Column(Float, nullable=True)        # mg/dL
    intake_ml = Column(Integer, nullable=True)
    output_ml = Column(Integer, nullable=True)

    notes = Column(Text, nullable=True)
    is_critical = Column(Boolean, default=False, nullable=False)

    admission = relationship("IPAdmission", back_populates="nursing_notes")


class MedicationOrder(ClinicalAuditMixin, Base):
    """A drug prescribed to an inpatient (the order, not the administration)."""

    __tablename__ = "medication_orders"

    id = Column(Integer, primary_key=True, index=True)
    admission_id = Column(Integer, ForeignKey("ip_admissions.id"), nullable=False, index=True)
    medicine_id = Column(Integer, ForeignKey("medicine_stocks.id"), nullable=True)
    medicine_name = Column(String, nullable=False)
    dose = Column(String, nullable=True)
    route = Column(String, default="Oral", nullable=True)
    frequency = Column(String, default="BD", nullable=True)
    start_date = Column(DateTime, default=utcnow, nullable=False)
    end_date = Column(DateTime, nullable=True)
    status = Column(String, default="Active", nullable=False, index=True)
    prescribed_by = Column(String, nullable=True)
    stop_reason = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    admission = relationship("IPAdmission", back_populates="medication_orders")
    medicine = relationship("MedicineStock")
    administrations = relationship(
        "MedicationAdministration", back_populates="order", cascade="all, delete-orphan",
        order_by="MedicationAdministration.administered_at.desc()",
    )


class MedicationAdministration(ClinicalAuditMixin, Base):
    """The medication administration record (MAR) — what was actually given."""

    __tablename__ = "medication_administrations"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("medication_orders.id"), nullable=False, index=True)
    administered_at = Column(DateTime, default=utcnow, nullable=False, index=True)
    administered_by = Column(String, nullable=True)
    dose_given = Column(String, nullable=True)
    status = Column(String, default="Given", nullable=False)
    remarks = Column(Text, nullable=True)

    order = relationship("MedicationOrder", back_populates="administrations")


class DischargeSummary(ClinicalAuditMixin, Base):
    """The clinical document produced at the end of an admission."""

    __tablename__ = "discharge_summaries"

    id = Column(Integer, primary_key=True, index=True)
    admission_id = Column(
        Integer, ForeignKey("ip_admissions.id"), nullable=False, unique=True, index=True
    )
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False, index=True)

    discharge_type = Column(String, default="Routine", nullable=False)
    final_diagnosis = Column(Text, nullable=True)
    procedures_performed = Column(Text, nullable=True)
    investigations = Column(Text, nullable=True)
    condition_at_discharge = Column(String, nullable=True)
    medication_summary = Column(Text, nullable=True)
    diet_advice = Column(Text, nullable=True)
    activity_advice = Column(Text, nullable=True)
    follow_up_instructions = Column(Text, nullable=True)
    follow_up_date = Column(Date, nullable=True)

    status = Column(String, default="Draft", nullable=False, index=True)
    prepared_by = Column(String, nullable=True)
    prepared_at = Column(DateTime, nullable=True)
    approved_by = Column(String, nullable=True)
    approved_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    admission = relationship("IPAdmission", back_populates="discharge_summary")
    patient = relationship("Patient")



# ============================
# Laboratory
# ============================
class LabTestMaster(Base):
    """Catalogue of orderable lab tests *and* multi-test panels/profiles."""

    __tablename__ = "lab_test_master"

    id = Column(Integer, primary_key=True, index=True)
    test_code = Column(String, unique=True, index=True, nullable=False)
    test_name = Column(String, nullable=False, index=True)
    category = Column(String, nullable=True)
    department = Column(String, nullable=True)
    sample_type = Column(String, nullable=True)
    container_type = Column(String, nullable=True)
    method = Column(String, nullable=True)
    unit = Column(String, nullable=True)
    reference_range = Column(String, nullable=True)
    normal_range_male = Column(String, nullable=True)
    normal_range_female = Column(String, nullable=True)
    normal_range_child = Column(String, nullable=True)
    price = Column(Float, default=0.0)
    tat_hours = Column(Integer, default=24)
    is_panel = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    created_at = Column(DateTime, default=utcnow)

    parameters = relationship(
        "LabTestParameter",
        back_populates="test",
        cascade="all, delete-orphan",
        order_by="LabTestParameter.display_order",
    )
    panel_items = relationship(
        "LabPanelItem",
        foreign_keys="LabPanelItem.panel_id",
        back_populates="panel",
        cascade="all, delete-orphan",
    )


class LabTestParameter(Base):
    """A single measurable parameter of a test (e.g. Haemoglobin of a CBC)."""

    __tablename__ = "lab_test_parameters"

    id = Column(Integer, primary_key=True, index=True)
    test_id = Column(Integer, ForeignKey("lab_test_master.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    data_type = Column(String, default="Numeric")  # Numeric | Text | Options
    options = Column(Text, nullable=True)          # comma separated, for Options
    unit = Column(String, nullable=True)
    reference_range = Column(String, nullable=True)
    normal_range_male = Column(String, nullable=True)
    normal_range_female = Column(String, nullable=True)
    normal_range_child = Column(String, nullable=True)
    critical_low = Column(Float, nullable=True)
    critical_high = Column(Float, nullable=True)
    display_order = Column(Integer, default=0)

    test = relationship("LabTestMaster", back_populates="parameters")


class LabPanelItem(Base):
    """Membership of a test inside a panel/profile."""

    __tablename__ = "lab_panel_items"

    id = Column(Integer, primary_key=True, index=True)
    panel_id = Column(Integer, ForeignKey("lab_test_master.id"), nullable=False, index=True)
    test_id = Column(Integer, ForeignKey("lab_test_master.id"), nullable=False, index=True)
    display_order = Column(Integer, default=0)

    panel = relationship("LabTestMaster", foreign_keys=[panel_id], back_populates="panel_items")
    test = relationship("LabTestMaster", foreign_keys=[test_id])


class LabOrder(ClinicalAuditMixin, Base):
    __tablename__ = "lab_orders"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False, index=True)
    doctor_name = Column(String, nullable=True)
    test_id = Column(Integer, ForeignKey("lab_test_master.id"), nullable=False, index=True)
    bill_id = Column(Integer, ForeignKey("lab_bills.id"), nullable=True, index=True)
    # Billed on an inpatient's final bill instead of a separate lab bill.
    ip_bill_id = Column(Integer, ForeignKey("ip_bills.id"), nullable=True, index=True)
    panel_id = Column(Integer, ForeignKey("lab_test_master.id"), nullable=True)
    order_date = Column(DateTime, default=utcnow, index=True)
    status = Column(String, default="Pending", nullable=False, index=True)
    priority = Column(String, default="Routine")
    tat_hours = Column(Integer, default=24)
    due_at = Column(DateTime, nullable=True, index=True)
    sample_collected_at = Column(DateTime, nullable=True)
    result_entered_at = Column(DateTime, nullable=True)
    verified_by = Column(String, nullable=True)
    verified_at = Column(DateTime, nullable=True)
    remarks = Column(Text, nullable=True)
    interpretation = Column(Text, nullable=True)

    patient = relationship("Patient", back_populates="lab_orders")
    test = relationship("LabTestMaster", foreign_keys=[test_id])
    panel = relationship("LabTestMaster", foreign_keys=[panel_id])
    bill = relationship("LabBill", back_populates="orders")
    samples = relationship("LabSample", back_populates="order", cascade="all, delete-orphan")
    reports = relationship("LabReport", back_populates="order")

    __table_args__ = (
        Index("ix_lab_orders_patient_status", "patient_id", "status"),
    )


class LabSample(Base):
    __tablename__ = "lab_samples"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("lab_orders.id"), nullable=False, index=True)
    sample_type = Column(String, nullable=False)
    collection_date = Column(DateTime, nullable=True)
    received_at = Column(DateTime, nullable=True)
    collected_by = Column(String, nullable=True)
    container_type = Column(String, nullable=True)
    barcode = Column(String, nullable=True, index=True)
    volume = Column(String, nullable=True)
    rejection_reason = Column(String, nullable=True)
    remarks = Column(Text, nullable=True)
    status = Column(String, default="Pending")  # Pending|Collected|Received|Rejected|Recollected

    order = relationship("LabOrder", back_populates="samples")


class LabReport(ClinicalAuditMixin, Base):
    __tablename__ = "lab_reports"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False, index=True)
    order_id = Column(Integer, ForeignKey("lab_orders.id"), nullable=True, index=True)
    test_id = Column(Integer, ForeignKey("lab_test_master.id"), nullable=True)
    test_name = Column(String, nullable=False)
    result_value = Column(String, nullable=True)
    normal_range = Column(String, nullable=True)
    units = Column(String, nullable=True)
    date_conducted = Column(DateTime, default=utcnow, index=True)
    reported_by = Column(String, nullable=True)
    verified_by = Column(String, nullable=True)
    verified_at = Column(DateTime, nullable=True)
    status = Column(String, default="Final")  # Draft | Final | Verified
    is_abnormal = Column(Boolean, default=False)
    interpretation = Column(Text, nullable=True)
    remarks = Column(Text, nullable=True)
    results_data = Column(JSON, nullable=True)  # [{parameter, result, unit, range, flag, remarks}]

    patient = relationship("Patient", back_populates="lab_reports")
    order = relationship("LabOrder", back_populates="reports")


# ============================
# Consolidated OP / IP billing
# ============================
class OPBill(Base):
    __tablename__ = "op_bills"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False, index=True)
    token_id = Column(Integer, ForeignKey("op_tokens.id"), nullable=True)
    bill_date = Column(DateTime, default=utcnow, index=True)
    doctor_name = Column(String, nullable=True)
    department = Column(String, nullable=True)

    consultation_fee = Column(Float, default=0.0)
    lab_charges = Column(Float, default=0.0)
    pharmacy_charges = Column(Float, default=0.0)
    other_charges = Column(JSON, default=list)  # [{name, amount}]

    subtotal = Column(Float, default=0.0)
    discount = Column(Float, default=0.0)  # percent
    gst = Column(Float, default=0.0)       # percent
    total = Column(Float, default=0.0)

    payment_mode = Column(String, default="Cash")
    payment_details = Column(JSON, nullable=True)
    notes = Column(Text, nullable=True)

    # Settlement. Bills created before payment tracking were collected at the
    # counter, so the migration backfills them as Paid in full.
    payment_status = Column(String, default="Paid", nullable=False, index=True)
    amount_paid = Column(Float, default=0.0, nullable=False)
    payment_history = Column(JSON, default=list)  # [{amount, payment_mode, at, by}]
    cancelled_reason = Column(String, nullable=True)

    @property
    def amount_due(self) -> float:
        if self.payment_status == "Cancelled":
            return 0.0
        return round(max((self.total or 0.0) - (self.amount_paid or 0.0), 0.0), 2)

    patient = relationship("Patient", back_populates="op_bills")


class IPBill(Base):
    __tablename__ = "ip_bills"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False, index=True)
    admission_id = Column(Integer, ForeignKey("ip_admissions.id"), nullable=True)
    bill_date = Column(DateTime, default=utcnow, index=True)
    doctor_name = Column(String, nullable=True)

    room_charge_per_day = Column(Float, default=0.0)
    days_stayed = Column(Integer, default=1)
    room_charges = Column(Float, default=0.0)
    doctor_charges = Column(Float, default=0.0)
    nursing_charges = Column(Float, default=0.0)
    pharmacy_charges = Column(Float, default=0.0)
    lab_charges = Column(Float, default=0.0)
    other_charges = Column(JSON, default=list)  # [{name, amount}]

    subtotal = Column(Float, default=0.0)
    discount = Column(Float, default=0.0)  # percent
    gst = Column(Float, default=0.0)       # percent
    total = Column(Float, default=0.0)

    payment_mode = Column(String, default="Cash")
    payment_details = Column(JSON, nullable=True)
    notes = Column(Text, nullable=True)

    # Settlement. Bills created before payment tracking were collected at the
    # counter, so the migration backfills them as Paid in full.
    payment_status = Column(String, default="Paid", nullable=False, index=True)
    amount_paid = Column(Float, default=0.0, nullable=False)
    payment_history = Column(JSON, default=list)  # [{amount, payment_mode, at, by}]
    cancelled_reason = Column(String, nullable=True)

    @property
    def amount_due(self) -> float:
        if self.payment_status == "Cancelled":
            return 0.0
        return round(max((self.total or 0.0) - (self.amount_paid or 0.0), 0.0), 2)

    patient = relationship("Patient", back_populates="ip_bills")
    admission = relationship("IPAdmission", back_populates="ip_bills")


# ============================
# Insurance
# ============================
class InsurancePolicy(Base):
    """An insurance policy a patient is covered by."""

    __tablename__ = "insurance_policies"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False, index=True)
    provider = Column(String, nullable=False)          # e.g. "Star Health"
    policy_number = Column(String, nullable=False, index=True)
    member_id = Column(String, nullable=True)
    plan_name = Column(String, nullable=True)
    sum_insured = Column(Float, default=0.0)
    valid_from = Column(Date, nullable=True)
    valid_to = Column(Date, nullable=True)
    tpa_name = Column(String, nullable=True)           # third-party administrator
    tpa_contact = Column(String, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)

    patient = relationship("Patient")


class InsuranceClaim(Base):
    """A claim raised against a hospital bill."""

    __tablename__ = "insurance_claims"

    id = Column(Integer, primary_key=True, index=True)
    claim_number = Column(String, unique=True, index=True, nullable=False)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False, index=True)
    policy_id = Column(Integer, ForeignKey("insurance_policies.id"), nullable=True, index=True)

    # The bill being claimed against (any of the four bill tables).
    bill_type = Column(String, nullable=True)   # OP | IP | Pharmacy | Laboratory
    bill_id = Column(Integer, nullable=True, index=True)

    claim_type = Column(String, default="Reimbursement")  # Cashless | Reimbursement
    treatment_type = Column(String, nullable=True)        # OP | IP | Pharmacy | Laboratory | Other
    diagnosis = Column(String, nullable=True)
    hospital_name = Column(String, nullable=True)
    admission_date = Column(Date, nullable=True)
    discharge_date = Column(Date, nullable=True)

    claimed_amount = Column(Float, default=0.0)
    approved_amount = Column(Float, default=0.0)
    patient_payable = Column(Float, default=0.0)
    status = Column(String, default="Draft", nullable=False, index=True)
    rejection_reason = Column(Text, nullable=True)
    remarks = Column(Text, nullable=True)

    submitted_at = Column(DateTime, nullable=True)
    settled_at = Column(DateTime, nullable=True)
    created_by = Column(String, nullable=True)
    updated_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=utcnow, index=True)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    patient = relationship("Patient", back_populates="insurance_claims")
    policy = relationship("InsurancePolicy")
