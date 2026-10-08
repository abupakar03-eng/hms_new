"""Pydantic request/response models.

All enumerations are validated here against :mod:`backend.constants` so that
nonsense values (``status="Bogus"``, ``role="Wizard"``) are rejected with a 422
instead of being persisted and silently breaking the UI.
"""

from datetime import date, datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from . import constants

# Literal types generated from the shared constants module.
Role = Literal[constants.ROLES]  # type: ignore[valid-type]
Gender = Literal[constants.GENDERS]  # type: ignore[valid-type]
OPTokenStatus = Literal[constants.OP_TOKEN_STATUSES]  # type: ignore[valid-type]
AppointmentStatus = Literal[constants.APPOINTMENT_STATUSES]  # type: ignore[valid-type]
PaymentMode = Literal[constants.PAYMENT_MODES]  # type: ignore[valid-type]
StockCategory = Literal[constants.STOCK_CATEGORIES]  # type: ignore[valid-type]
StockTransactionType = Literal[constants.STOCK_TRANSACTION_TYPES]  # type: ignore[valid-type]
LabOrderStatus = Literal[constants.LAB_ORDER_STATUSES]  # type: ignore[valid-type]
LabSampleStatus = Literal[constants.LAB_SAMPLE_STATUSES]  # type: ignore[valid-type]
LabReportStatus = Literal[constants.LAB_REPORT_STATUSES]  # type: ignore[valid-type]
LabPriority = Literal[constants.LAB_PRIORITIES]  # type: ignore[valid-type]
LabBillStatus = Literal[constants.LAB_BILL_STATUSES]  # type: ignore[valid-type]
LabParameterDataType = Literal[constants.LAB_PARAMETER_DATA_TYPES]  # type: ignore[valid-type]


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ----------------- USER SCHEMAS -----------------
class UserBase(BaseModel):
    username: str = Field(..., min_length=2, max_length=50)
    role: Role = "Receptionist"

    @field_validator("username")
    @classmethod
    def validate_username_chars(cls, v: str) -> str:
        import re

        if not re.match(r"^[a-zA-Z0-9_.-]+$", v):
            raise ValueError("Username may contain only letters, digits, underscore, dot and dash")
        return v


class UserCreate(UserBase):
    password: str = Field(..., min_length=6, max_length=128)


class UserUpdate(BaseModel):
    role: Optional[Role] = None
    is_active: Optional[bool] = None


class PasswordReset(BaseModel):
    new_password: str = Field(..., min_length=6, max_length=128)


class PasswordChange(BaseModel):
    """Self-service change: the caller must prove they know the current password.

    Without this, anyone holding a borrowed or stolen token could silently take
    over the account.
    """

    current_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=6, max_length=128)


class UserResponse(ORMModel):
    id: int
    username: str
    role: str
    is_active: bool
    created_at: datetime
    # Populated for self-service patient accounts so the UI can route to the portal.
    patient_id: Optional[int] = None
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None


# ----------------- PATIENT SELF-REGISTRATION -----------------
class PatientRegister(BaseModel):
    """Public self-signup: creates the Patient record and its login together."""

    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6, max_length=128)
    name: str = Field(..., min_length=2, max_length=100)
    age: int = Field(..., ge=0, le=150)
    gender: Gender
    phone: str
    email: Optional[str] = Field(None, max_length=150)
    address: Optional[str] = Field(None, max_length=255)
    blood_group: Optional[str] = None

    @field_validator("username")
    @classmethod
    def validate_username_chars(cls, v: str) -> str:
        import re

        if not re.match(r"^[a-zA-Z0-9_.-]+$", v):
            raise ValueError("Username may contain only letters, digits, underscore, dot and dash")
        return v

    @field_validator("phone")
    @classmethod
    def validate_phone_number(cls, v: str) -> str:
        import re

        clean = (v or "").replace(" ", "").replace("-", "")
        if not re.match(r"^[6-9]\d{9}$", clean):
            raise ValueError("Invalid Indian phone number (10 digits starting with 6-9)")
        return clean

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: Optional[str]) -> Optional[str]:
        import re

        if v and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", v):
            raise ValueError("Invalid email address")
        return v.lower() if v else v


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    refresh_token: Optional[str] = None
    expires_in: Optional[int] = None
    role: Optional[str] = None


class RefreshRequest(BaseModel):
    refresh_token: str


class PasswordChangeResponse(Token):
    """A password change revokes every earlier token, the caller's included, so the
    caller's session continues on the fresh pair returned here."""

    message: str


class LogoutRequest(BaseModel):
    refresh_token: Optional[str] = None


# ----------------- PATIENT SCHEMAS -----------------
class PatientBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    age: int = Field(..., ge=0, le=150)
    gender: Gender
    phone: Optional[str] = None
    address: Optional[str] = Field(None, max_length=255)
    aadhaar: Optional[str] = None
    blood_group: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("phone")
    @classmethod
    def validate_phone_number(cls, v: Optional[str]) -> Optional[str]:
        import re

        if v:
            clean = v.replace(" ", "").replace("-", "")
            if not re.match(r"^[6-9]\d{9}$", clean):
                raise ValueError("Invalid Indian phone number (10 digits starting with 6-9)")
            return clean
        return v

    @field_validator("aadhaar")
    @classmethod
    def validate_aadhaar_number(cls, v: Optional[str]) -> Optional[str]:
        import re

        if v:
            clean = v.replace(" ", "")
            if not re.match(r"^\d{12}$", clean):
                raise ValueError("Aadhaar card must contain exactly 12 digits")
            return clean
        return v


class PatientCreate(PatientBase):
    pass


class PatientUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    age: Optional[int] = Field(None, ge=0, le=150)
    gender: Optional[Gender] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    aadhaar: Optional[str] = None
    blood_group: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class Patient(PatientBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


class PatientBrief(ORMModel):
    """Compact patient representation embedded in list responses."""

    id: int
    name: str
    age: int
    gender: str
    phone: Optional[str] = None
    aadhaar: Optional[str] = None
    blood_group: Optional[str] = None


# ----------------- OP TOKEN SCHEMAS -----------------
class OPTokenBase(BaseModel):
    patient_id: int
    session: Literal["Morning", "Evening"]
    date: date
    fee: float = Field(0.0, ge=0)
    doctor_id: Optional[int] = None
    doctor_name: Optional[str] = None
    department: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)


class OPTokenCreate(OPTokenBase):
    pass


class OPTokenUpdate(BaseModel):
    status: Optional[OPTokenStatus] = None
    doctor_id: Optional[int] = None
    doctor_name: Optional[str] = None
    department: Optional[str] = None
    fee: Optional[float] = Field(None, ge=0)
    details: Optional[Dict[str, Any]] = None


class OPToken(OPTokenBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    token_number: int
    status: str
    is_billed: bool
    created_at: Optional[datetime] = None
    patient: Optional[PatientBrief] = None


# ----------------- APPOINTMENT SCHEMAS -----------------
class AppointmentBase(BaseModel):
    patient_id: int
    doctor_id: Optional[int] = None
    doctor_name: Optional[str] = None
    appointment_date: date
    time_slot: Optional[str] = None
    reason: Optional[str] = None
    status: AppointmentStatus = "Scheduled"
    details: Dict[str, Any] = Field(default_factory=dict)


class AppointmentCreate(AppointmentBase):
    pass


class AppointmentUpdate(BaseModel):
    status: Optional[AppointmentStatus] = None
    time_slot: Optional[str] = None
    reason: Optional[str] = None
    doctor_id: Optional[int] = None
    doctor_name: Optional[str] = None
    appointment_date: Optional[date] = None


class AppointmentResponse(AppointmentBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient: Optional[PatientBrief] = None


# ----------------- CASESHEET SCHEMAS -----------------
class PrescribedMedicine(BaseModel):
    name: str
    quantity: int = Field(1, ge=1)
    dosage: Optional[str] = None
    duration: Optional[str] = None
    instructions: Optional[str] = None
    timing_morning: Optional[bool] = None
    timing_afternoon: Optional[bool] = None
    timing_night: Optional[bool] = None
    timing_relation: Optional[str] = None


class CasesheetBase(BaseModel):
    patient_id: int
    token_id: Optional[int] = None
    doctor_name: Optional[str] = None
    vitals_bp: Optional[str] = None
    vitals_pulse: Optional[str] = None
    vitals_temp: Optional[str] = None
    vitals_resp: Optional[str] = None
    vitals_spo2: Optional[str] = None
    vitals_weight: Optional[str] = None
    chief_complaint: Optional[str] = None
    symptoms: Optional[str] = None
    hpi: Optional[str] = None
    pmh: Optional[str] = None
    family_history: Optional[str] = None
    allergies: Optional[str] = None
    clinical_findings: Optional[str] = None
    diagnosis: Optional[str] = None
    icd_code: Optional[str] = None
    treatment_plan: Optional[str] = None
    advice: Optional[str] = None
    follow_up_date: Optional[date] = None
    prescribed_medicines: List[PrescribedMedicine] = Field(default_factory=list)
    prescribed_labs: List[str] = Field(default_factory=list)


class CasesheetCreate(CasesheetBase):
    auto_order_labs: bool = True


class CasesheetUpdate(BaseModel):
    """Editable fields of a casesheet.

    The previous revision declared fields such as ``vitals`` and ``hpi`` that did
    not exist on the ORM model, so edits were silently discarded and *no* real
    field could ever be updated.
    """

    doctor_name: Optional[str] = None
    vitals_bp: Optional[str] = None
    vitals_pulse: Optional[str] = None
    vitals_temp: Optional[str] = None
    vitals_resp: Optional[str] = None
    vitals_spo2: Optional[str] = None
    vitals_weight: Optional[str] = None
    chief_complaint: Optional[str] = None
    symptoms: Optional[str] = None
    hpi: Optional[str] = None
    pmh: Optional[str] = None
    family_history: Optional[str] = None
    allergies: Optional[str] = None
    clinical_findings: Optional[str] = None
    diagnosis: Optional[str] = None
    icd_code: Optional[str] = None
    treatment_plan: Optional[str] = None
    advice: Optional[str] = None
    follow_up_date: Optional[date] = None
    prescribed_medicines: Optional[List[PrescribedMedicine]] = None
    prescribed_labs: Optional[List[str]] = None


class Casesheet(CasesheetBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    date: date


# ----------------- INVENTORY SCHEMAS -----------------
class MedicineStockBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=150)
    category: StockCategory
    batch_no: Optional[str] = None
    expiry_date: Optional[date] = None
    quantity: int = Field(0, ge=0)
    unit_price: float = Field(0.0, ge=0)
    min_stock_level: int = Field(10, ge=0)
    details: Dict[str, Any] = Field(default_factory=dict)


class MedicineStockCreate(MedicineStockBase):
    pass


class MedicineStockUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[StockCategory] = None
    batch_no: Optional[str] = None
    expiry_date: Optional[date] = None
    quantity: Optional[int] = Field(None, ge=0)
    unit_price: Optional[float] = Field(None, ge=0)
    min_stock_level: Optional[int] = Field(None, ge=0)
    details: Optional[Dict[str, Any]] = None


class MedicineStock(MedicineStockBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    # Units that may be dispensed today (excludes expired batches).
    sellable_quantity: Optional[int] = None


class StockTransactionCreate(BaseModel):
    medicine_id: int
    type: StockTransactionType
    quantity: int = Field(..., gt=0)
    notes: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)
    # Stock In: receive into this batch (created if new). Return/Adjustment/Stock
    # Out: act on a specific existing batch.
    batch_number: Optional[str] = Field(None, min_length=1, max_length=60)
    expiry_date: Optional[date] = None
    batch_id: Optional[int] = None


class MedicineBatchCreate(BaseModel):
    batch_number: str = Field(..., min_length=1, max_length=60)
    expiry_date: Optional[date] = None
    quantity: int = Field(..., gt=0)
    notes: Optional[str] = None


class MedicineBatchResponse(ORMModel):
    id: int
    medicine_id: int
    batch_number: str
    expiry_date: Optional[date] = None
    quantity: int
    received_at: datetime
    notes: Optional[str] = None


# ----------------- PHARMACY BILL SCHEMAS -----------------
class PharmacyBillItemCreate(BaseModel):
    medicine_id: int
    quantity: int = Field(..., gt=0)


class PharmacyBillItemResponse(ORMModel):
    id: int
    medicine_id: Optional[int] = None
    medicine_name: str
    quantity: int
    unit_price: float
    total_price: float
    batches: Optional[List[Dict[str, Any]]] = None


class PharmacyBillCreate(BaseModel):
    patient_id: Optional[int] = None
    patient_name: Optional[str] = None
    # Charge the sale to this current admission (settled on the final IP bill).
    admission_id: Optional[int] = None
    discount: float = Field(0.0, ge=0, le=100)
    gst: float = Field(0.0, ge=0, le=100)
    payment_mode: PaymentMode = "Cash"
    payment_details: Optional[Dict[str, float]] = None
    details: Dict[str, Any] = Field(default_factory=dict)
    items: List[PharmacyBillItemCreate] = Field(..., min_length=1)


class PharmacyBillResponse(ORMModel):
    id: int
    patient_id: Optional[int] = None
    patient_name: Optional[str] = None
    bill_date: datetime
    subtotal: float
    discount: float
    gst: float
    total: float
    payment_mode: str = "Cash"
    payment_details: Optional[Any] = None
    details: Dict[str, Any] = Field(default_factory=dict)
    admission_id: Optional[int] = None
    ip_bill_id: Optional[int] = None
    items: List[PharmacyBillItemResponse] = Field(default_factory=list)
    patient: Optional[PatientBrief] = None


# ----------------- LAB BILL SCHEMAS -----------------
class LabBillItemCreate(BaseModel):
    test_id: Optional[int] = None
    test_name: str
    price: float = Field(..., ge=0)


class LabBillItemResponse(ORMModel):
    id: int
    test_id: Optional[int] = None
    test_name: str
    price: float


class LabBillCreate(BaseModel):
    patient_id: Optional[int] = None
    patient_name: Optional[str] = None
    discount: float = Field(0.0, ge=0, le=100)
    gst: float = Field(0.0, ge=0, le=100)
    payment_mode: PaymentMode = "Cash"
    payment_details: Optional[Dict[str, float]] = None
    notes: Optional[str] = None
    items: List[LabBillItemCreate] = Field(..., min_length=1)


class LabBillFromOrders(BaseModel):
    """Generate a lab bill directly from one or more pending lab orders."""

    order_ids: List[int] = Field(..., min_length=1)
    discount: float = Field(0.0, ge=0, le=100)
    gst: float = Field(0.0, ge=0, le=100)
    payment_mode: PaymentMode = "Cash"
    payment_details: Optional[Dict[str, float]] = None
    notes: Optional[str] = None
    mark_paid: bool = True


class LabBillResponse(ORMModel):
    id: int
    patient_id: Optional[int] = None
    patient_name: Optional[str] = None
    bill_date: datetime
    subtotal: float
    total: float
    discount: float = 0.0
    gst: float = 0.0
    status: str
    payment_mode: str = "Cash"
    payment_details: Optional[Any] = None
    notes: Optional[str] = None
    items: List[LabBillItemResponse] = Field(default_factory=list)
    patient: Optional[PatientBrief] = None


# ----------------- IP ADMISSION SCHEMAS -----------------
class IPAdmissionBase(BaseModel):
    patient_id: int
    ward_number: Optional[str] = None
    room_number: Optional[str] = None
    doctor_in_charge: Optional[str] = None
    reason_for_admission: Optional[str] = None


class IPAdmissionCreate(IPAdmissionBase):
    pass


class IPAdmissionUpdate(BaseModel):
    ward_number: Optional[str] = None
    room_number: Optional[str] = None
    doctor_in_charge: Optional[str] = None
    reason_for_admission: Optional[str] = None
    status: Optional[Literal["Admitted", "Discharged", "Transferred"]] = None
    discharge_date: Optional[datetime] = None


class IPAdmission(IPAdmissionBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    admission_date: datetime
    discharge_date: Optional[datetime] = None
    status: str
    patient: Optional[PatientBrief] = None


# ----------------- LAB REPORT SCHEMAS -----------------
class LabResultRow(BaseModel):
    parameter: str
    result: Optional[str] = None
    unit: Optional[str] = None
    range: Optional[str] = None
    flag: str = "Normal"
    remarks: Optional[str] = None


class LabReportBase(BaseModel):
    patient_id: int
    order_id: Optional[int] = None
    test_id: Optional[int] = None
    test_name: str
    result_value: Optional[str] = None
    normal_range: Optional[str] = None
    units: Optional[str] = None
    reported_by: Optional[str] = None
    verified_by: Optional[str] = None
    status: LabReportStatus = "Final"
    is_abnormal: bool = False
    interpretation: Optional[str] = None
    remarks: Optional[str] = None
    results_data: Optional[List[LabResultRow]] = None


class LabReportCreate(LabReportBase):
    pass


class LabReportUpdate(BaseModel):
    test_name: Optional[str] = None
    result_value: Optional[str] = None
    normal_range: Optional[str] = None
    units: Optional[str] = None
    reported_by: Optional[str] = None
    status: Optional[LabReportStatus] = None
    interpretation: Optional[str] = None
    remarks: Optional[str] = None
    results_data: Optional[List[LabResultRow]] = None


class LabReport(LabReportBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    date_conducted: datetime
    verified_at: Optional[datetime] = None
    patient: Optional[PatientBrief] = None


# ----------------- LAB TEST MASTER SCHEMAS -----------------
class LabTestParameterBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    data_type: LabParameterDataType = "Numeric"
    options: Optional[str] = None
    unit: Optional[str] = None
    reference_range: Optional[str] = None
    normal_range_male: Optional[str] = None
    normal_range_female: Optional[str] = None
    normal_range_child: Optional[str] = None
    critical_low: Optional[float] = None
    critical_high: Optional[float] = None
    display_order: int = 0


class LabTestParameterCreate(LabTestParameterBase):
    pass


class LabTestParameterUpdate(BaseModel):
    name: Optional[str] = None
    data_type: Optional[LabParameterDataType] = None
    options: Optional[str] = None
    unit: Optional[str] = None
    reference_range: Optional[str] = None
    normal_range_male: Optional[str] = None
    normal_range_female: Optional[str] = None
    normal_range_child: Optional[str] = None
    critical_low: Optional[float] = None
    critical_high: Optional[float] = None
    display_order: Optional[int] = None


class LabTestParameter(LabTestParameterBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    test_id: int


class LabTestMasterBase(BaseModel):
    test_code: str = Field(..., min_length=1, max_length=30)
    test_name: str = Field(..., min_length=1, max_length=150)
    category: Optional[str] = None
    department: Optional[str] = None
    sample_type: Optional[str] = None
    container_type: Optional[str] = None
    method: Optional[str] = None
    unit: Optional[str] = None
    reference_range: Optional[str] = None
    normal_range_male: Optional[str] = None
    normal_range_female: Optional[str] = None
    normal_range_child: Optional[str] = None
    price: float = Field(0.0, ge=0)
    tat_hours: int = Field(24, ge=0, le=8760)
    is_panel: bool = False
    is_active: bool = True


class LabTestMasterCreate(LabTestMasterBase):
    parameters: List[LabTestParameterCreate] = Field(default_factory=list)
    panel_test_ids: List[int] = Field(default_factory=list)


class LabTestMasterUpdate(BaseModel):
    test_code: Optional[str] = None
    test_name: Optional[str] = None
    category: Optional[str] = None
    department: Optional[str] = None
    sample_type: Optional[str] = None
    container_type: Optional[str] = None
    method: Optional[str] = None
    unit: Optional[str] = None
    reference_range: Optional[str] = None
    normal_range_male: Optional[str] = None
    normal_range_female: Optional[str] = None
    normal_range_child: Optional[str] = None
    price: Optional[float] = Field(None, ge=0)
    tat_hours: Optional[int] = Field(None, ge=0)
    is_panel: Optional[bool] = None
    is_active: Optional[bool] = None
    parameters: Optional[List[LabTestParameterCreate]] = None
    panel_test_ids: Optional[List[int]] = None


class LabTestMaster(LabTestMasterBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    parameters: List[LabTestParameter] = Field(default_factory=list)


# ----------------- LAB ORDER / SAMPLE SCHEMAS -----------------
class LabOrderBase(BaseModel):
    patient_id: int
    doctor_name: Optional[str] = None
    test_id: int
    status: LabOrderStatus = "Pending"
    priority: LabPriority = "Routine"
    remarks: Optional[str] = None


class LabOrderCreate(LabOrderBase):
    pass


class LabOrderBulkCreate(BaseModel):
    """Order several tests at once (multi-select or panel expansion)."""

    patient_id: int
    test_ids: List[int] = Field(..., min_length=1)
    doctor_name: Optional[str] = None
    priority: LabPriority = "Routine"
    remarks: Optional[str] = None
    panel_id: Optional[int] = None


class LabOrderUpdate(BaseModel):
    status: Optional[LabOrderStatus] = None
    priority: Optional[LabPriority] = None
    remarks: Optional[str] = None
    interpretation: Optional[str] = None
    doctor_name: Optional[str] = None


class LabOrder(ORMModel):
    id: int
    patient_id: int
    doctor_name: Optional[str] = None
    test_id: int
    panel_id: Optional[int] = None
    bill_id: Optional[int] = None
    order_date: datetime
    status: str
    priority: str
    tat_hours: int
    due_at: Optional[datetime] = None
    sample_collected_at: Optional[datetime] = None
    result_entered_at: Optional[datetime] = None
    verified_by: Optional[str] = None
    verified_at: Optional[datetime] = None
    remarks: Optional[str] = None
    interpretation: Optional[str] = None
    patient: Optional[PatientBrief] = None
    test: Optional[LabTestMaster] = None


class LabSampleBase(BaseModel):
    order_id: int
    sample_type: str
    collected_by: Optional[str] = None
    container_type: Optional[str] = None
    barcode: Optional[str] = None
    volume: Optional[str] = None
    remarks: Optional[str] = None
    status: LabSampleStatus = "Pending"


class LabSampleCreate(LabSampleBase):
    pass


class LabSampleUpdate(BaseModel):
    sample_type: Optional[str] = None
    collected_by: Optional[str] = None
    container_type: Optional[str] = None
    barcode: Optional[str] = None
    volume: Optional[str] = None
    remarks: Optional[str] = None
    status: Optional[LabSampleStatus] = None
    rejection_reason: Optional[str] = None


class LabSample(ORMModel):
    id: int
    order_id: int
    sample_type: str
    collection_date: Optional[datetime] = None
    received_at: Optional[datetime] = None
    collected_by: Optional[str] = None
    container_type: Optional[str] = None
    barcode: Optional[str] = None
    volume: Optional[str] = None
    rejection_reason: Optional[str] = None
    remarks: Optional[str] = None
    status: str


class LabResultSubmit(BaseModel):
    """Submit/verify results for a lab order."""

    results: List[LabResultRow] = Field(..., min_length=1)
    interpretation: Optional[str] = None
    verify: bool = True


class LabStats(BaseModel):
    pending: int
    sample_collected: int
    testing: int
    ready_to_report: int
    verified_today: int
    overdue: int
    stat_pending: int
    samples_pending: int
    rejected_samples: int
    total_tests: int
    active_tests: int
    panels: int
    today_orders: int
    today_revenue: float
    pending_billing: int
    tat_compliance_percent: float


# ===========================================
# OP / IP BILL SCHEMAS
# ===========================================
class OtherCharge(BaseModel):
    name: str
    amount: float


class OPBillCreate(BaseModel):
    patient_id: int
    token_id: Optional[int] = None
    doctor_name: Optional[str] = None
    department: Optional[str] = None
    consultation_fee: float = Field(0.0, ge=0)
    lab_charges: float = Field(0.0, ge=0)
    pharmacy_charges: float = Field(0.0, ge=0)
    other_charges: List[OtherCharge] = Field(default_factory=list)
    discount: float = Field(0.0, ge=0, le=100)
    gst: float = Field(0.0, ge=0, le=100)
    payment_mode: PaymentMode = "Cash"
    payment_details: Optional[Dict[str, float]] = None
    notes: Optional[str] = None
    # Collected now. Omitted = paid in full at the counter (the previous behaviour).
    amount_paid: Optional[float] = Field(None, ge=0)


class OPBillResponse(ORMModel):
    id: int
    patient_id: int
    token_id: Optional[int] = None
    bill_date: datetime
    doctor_name: Optional[str] = None
    department: Optional[str] = None
    consultation_fee: float
    lab_charges: float
    pharmacy_charges: float
    other_charges: List[OtherCharge] = Field(default_factory=list)
    subtotal: float
    discount: float
    gst: float
    total: float
    payment_mode: str
    payment_details: Optional[Dict[str, float]] = None
    notes: Optional[str] = None
    payment_status: str = "Paid"
    amount_paid: float = 0.0
    amount_due: float = 0.0
    payment_history: List[Dict[str, Any]] = Field(default_factory=list)
    cancelled_reason: Optional[str] = None
    patient: Optional[PatientBrief] = None


class IPBillCreate(BaseModel):
    patient_id: int
    admission_id: Optional[int] = None
    doctor_name: Optional[str] = None
    room_charge_per_day: float = Field(0.0, ge=0)
    days_stayed: int = Field(1, ge=0)
    doctor_charges: float = Field(0.0, ge=0)
    nursing_charges: float = Field(0.0, ge=0)
    pharmacy_charges: float = Field(0.0, ge=0)
    lab_charges: float = Field(0.0, ge=0)
    other_charges: List[OtherCharge] = Field(default_factory=list)
    discount: float = Field(0.0, ge=0, le=100)
    gst: float = Field(0.0, ge=0, le=100)
    payment_mode: PaymentMode = "Cash"
    payment_details: Optional[Dict[str, float]] = None
    notes: Optional[str] = None
    # Collected now. Omitted = paid in full at the counter (the previous behaviour).
    amount_paid: Optional[float] = Field(None, ge=0)
    # Charges raised during the stay that this bill includes (see GET .../bill-preview).
    lab_order_ids: List[int] = Field(default_factory=list)
    pharmacy_bill_ids: List[int] = Field(default_factory=list)


class IPBillResponse(ORMModel):
    id: int
    patient_id: int
    admission_id: Optional[int] = None
    bill_date: datetime
    doctor_name: Optional[str] = None
    room_charge_per_day: float
    days_stayed: int
    room_charges: float
    doctor_charges: float
    nursing_charges: float
    pharmacy_charges: float
    lab_charges: float
    other_charges: List[OtherCharge] = Field(default_factory=list)
    subtotal: float
    discount: float
    gst: float
    total: float
    payment_mode: str
    payment_details: Optional[Dict[str, float]] = None
    notes: Optional[str] = None
    payment_status: str = "Paid"
    amount_paid: float = 0.0
    amount_due: float = 0.0
    payment_history: List[Dict[str, Any]] = Field(default_factory=list)
    cancelled_reason: Optional[str] = None
    patient: Optional[PatientBrief] = None


# ===========================================
# REPORTS
# ===========================================
class DailyReportResponse(BaseModel):
    date: str
    op_revenue: float
    ip_revenue: float
    pharmacy_revenue: float
    lab_revenue: float
    total_revenue: float
    total_patients: int
    total_bills: int


class MonthlyReportItem(BaseModel):
    month: str
    op_revenue: float
    ip_revenue: float
    pharmacy_revenue: float
    lab_revenue: float
    total_revenue: float
    total_bills: int


class RevenueBreakdown(BaseModel):
    op_total: float
    ip_total: float
    pharmacy_total: float
    lab_total: float
    grand_total: float


class DoctorWiseReport(BaseModel):
    doctor_name: str
    op_bills: int
    ip_bills: int
    total_revenue: float


class DepartmentWiseReport(BaseModel):
    department: str
    total_bills: int
    total_revenue: float


class MedicineSalesReport(BaseModel):
    medicine_name: str
    total_quantity_sold: int
    total_revenue: float


class LabSummaryItem(BaseModel):
    test_name: str
    total_orders: int
    verified: int
    pending: int
    revenue: float


# ===========================================
# GLOBAL SEARCH
# ===========================================
class SearchResult(BaseModel):
    type: str
    id: int
    patient_id: Optional[int] = None
    patient_name: Optional[str] = None
    detail: str
    date: Optional[str] = None
    amount: Optional[float] = None


# ===========================================
# HOSPITAL SETTINGS / AUDIT
# ===========================================
class HospitalSettingItem(BaseModel):
    key: str = Field(..., min_length=1, max_length=100)
    value: Optional[str] = None


class HospitalSettingsUpdate(BaseModel):
    settings: List[HospitalSettingItem]


class AuditLogResponse(ORMModel):
    id: int
    user_id: Optional[int] = None
    username: Optional[str] = None
    actor_role: Optional[str] = None
    action: str
    details: Optional[str] = None
    timestamp: datetime
    ip_address: Optional[str] = None
    entity_type: Optional[str] = None
    entity_id: Optional[int] = None
    patient_id: Optional[int] = None
    before_state: Optional[str] = None
    after_state: Optional[str] = None


# ===========================================
# DASHBOARD
# ===========================================
class DashboardStats(BaseModel):
    today_patients: int
    today_revenue: float
    op_count: int
    ip_count: int
    lab_count: int
    medicine_sales: float
    lab_revenue: float
    total_patients: int
    active_ip: int
    low_stock_count: int
    outstanding_dues: float = 0.0


class ChartDataPoint(BaseModel):
    label: str
    value: float


class DashboardCharts(BaseModel):
    daily_revenue: List[ChartDataPoint]
    monthly_revenue: List[ChartDataPoint]
    patient_growth: List[ChartDataPoint]
    medicine_sales: List[ChartDataPoint]
    lab_volume: List[ChartDataPoint] = Field(default_factory=list)


class MessageResponse(BaseModel):
    message: str
    detail: Optional[str] = None


# ===========================================
# PATIENT PORTAL
# ===========================================
class PortalProfile(BaseModel):
    """The patient's own demographic record."""

    id: int
    name: str
    age: int
    gender: str
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    aadhaar_masked: Optional[str] = None
    blood_group: Optional[str] = None
    username: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime] = None


class PortalProfileUpdate(BaseModel):
    """Self-service edits. Clinical identity fields (name/age) are intentionally
    not self-editable; the hospital must correct those at the desk."""

    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    blood_group: Optional[str] = None

    @field_validator("phone")
    @classmethod
    def validate_phone_number(cls, v: Optional[str]) -> Optional[str]:
        import re

        if v:
            clean = v.replace(" ", "").replace("-", "")
            if not re.match(r"^[6-9]\d{9}$", clean):
                raise ValueError("Invalid Indian phone number (10 digits starting with 6-9)")
            return clean
        return v


class PortalDoctor(BaseModel):
    """A bookable doctor."""

    id: int
    name: str
    department: Optional[str] = None
    specialization: Optional[str] = None
    consultation_fee: Optional[float] = None


class PortalAppointmentCreate(BaseModel):
    doctor_id: Optional[int] = None
    appointment_date: date
    time_slot: str
    reason: Optional[str] = Field(None, max_length=500)

    @field_validator("appointment_date")
    @classmethod
    def not_in_the_past(cls, v: date) -> date:
        if v < date.today():
            raise ValueError("Appointment date cannot be in the past")
        return v


class PortalAppointment(BaseModel):
    id: int
    doctor_id: Optional[int] = None
    doctor_name: Optional[str] = None
    appointment_date: date
    time_slot: Optional[str] = None
    reason: Optional[str] = None
    status: str
    created_at: Optional[datetime] = None


class PortalPrescriptionMedicine(BaseModel):
    name: str
    quantity: Optional[int] = None
    dosage: Optional[str] = None
    duration: Optional[str] = None
    instructions: Optional[str] = None
    timing_morning: Optional[bool] = None
    timing_afternoon: Optional[bool] = None
    timing_night: Optional[bool] = None
    timing_relation: Optional[str] = None


class PortalPrescription(BaseModel):
    id: int
    date: date
    doctor_name: Optional[str] = None
    diagnosis: Optional[str] = None
    symptoms: Optional[str] = None
    advice: Optional[str] = None
    follow_up_date: Optional[date] = None
    vitals_bp: Optional[str] = None
    vitals_pulse: Optional[str] = None
    vitals_temp: Optional[str] = None
    vitals_resp: Optional[str] = None
    medicines: List[PortalPrescriptionMedicine] = Field(default_factory=list)
    advised_labs: List[str] = Field(default_factory=list)


class PortalLabOrder(BaseModel):
    """Progress tracker for a test the patient is waiting on."""

    id: int
    test_name: str
    order_date: datetime
    status: str
    priority: str = "Routine"
    due_at: Optional[datetime] = None
    report_ready: bool = False
    report_id: Optional[int] = None


class PortalLabReport(BaseModel):
    id: int
    order_id: Optional[int] = None
    test_name: str
    date_conducted: datetime
    status: str = "Final"
    is_abnormal: bool = False
    reported_by: Optional[str] = None
    verified_by: Optional[str] = None
    verified_at: Optional[datetime] = None
    interpretation: Optional[str] = None
    results: List[LabResultRow] = Field(default_factory=list)


class PortalBill(BaseModel):
    id: int
    bill_type: str            # OP | IP | Pharmacy | Laboratory
    bill_date: datetime
    description: str
    subtotal: float = 0.0
    discount: float = 0.0
    gst: float = 0.0
    total: float
    payment_mode: Optional[str] = None
    status: Optional[str] = None
    items: List[Dict[str, Any]] = Field(default_factory=list)


class PortalDocument(BaseModel):
    """A single row in the patient's document wallet."""

    type: str                 # prescription | lab_report | bill | discharge | insurance
    id: int
    title: str
    date: Optional[datetime] = None
    subtitle: Optional[str] = None
    downloadable: bool = True


class PortalDashboard(BaseModel):
    profile: PortalProfile
    next_appointment: Optional[PortalAppointment] = None
    upcoming_appointments: int = 0
    pending_lab_tests: int = 0
    ready_reports: int = 0
    abnormal_reports: int = 0
    prescriptions: int = 0
    outstanding_bills: int = 0
    total_billed: float = 0.0
    active_insurance: int = 0
    recent_lab_orders: List[PortalLabOrder] = Field(default_factory=list)
    recent_documents: List[PortalDocument] = Field(default_factory=list)


# ===========================================
# INSURANCE
# ===========================================
class InsurancePolicyBase(BaseModel):
    patient_id: int
    provider: str = Field(..., min_length=1, max_length=120)
    policy_number: str = Field(..., min_length=1, max_length=80)
    member_id: Optional[str] = None
    plan_name: Optional[str] = None
    sum_insured: float = Field(0.0, ge=0)
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None
    tpa_name: Optional[str] = None
    tpa_contact: Optional[str] = None
    is_active: bool = True
    notes: Optional[str] = None


class InsurancePolicyCreate(InsurancePolicyBase):
    pass


class InsurancePolicyUpdate(BaseModel):
    provider: Optional[str] = None
    policy_number: Optional[str] = None
    member_id: Optional[str] = None
    plan_name: Optional[str] = None
    sum_insured: Optional[float] = Field(None, ge=0)
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None
    tpa_name: Optional[str] = None
    tpa_contact: Optional[str] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = None


class InsurancePolicy(InsurancePolicyBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: Optional[datetime] = None
    patient: Optional[PatientBrief] = None


class InsuranceClaimCreate(BaseModel):
    patient_id: int
    policy_id: Optional[int] = None
    bill_type: Optional[Literal["OP", "IP", "Pharmacy", "Laboratory"]] = None
    bill_id: Optional[int] = None
    claim_type: Literal[constants.INSURANCE_CLAIM_TYPES] = "Reimbursement"  # type: ignore[valid-type]
    treatment_type: Optional[Literal[constants.TREATMENT_TYPES]] = None  # type: ignore[valid-type]
    diagnosis: Optional[str] = None
    hospital_name: Optional[str] = None
    admission_date: Optional[date] = None
    discharge_date: Optional[date] = None
    claimed_amount: float = Field(0.0, ge=0)
    remarks: Optional[str] = None


class InsuranceClaimUpdate(BaseModel):
    policy_id: Optional[int] = None
    claim_type: Optional[Literal[constants.INSURANCE_CLAIM_TYPES]] = None  # type: ignore[valid-type]
    treatment_type: Optional[Literal[constants.TREATMENT_TYPES]] = None  # type: ignore[valid-type]
    diagnosis: Optional[str] = None
    hospital_name: Optional[str] = None
    admission_date: Optional[date] = None
    discharge_date: Optional[date] = None
    claimed_amount: Optional[float] = Field(None, ge=0)
    approved_amount: Optional[float] = Field(None, ge=0)
    patient_payable: Optional[float] = Field(None, ge=0)
    remarks: Optional[str] = None


class InsuranceClaimStatusUpdate(BaseModel):
    status: Literal[constants.INSURANCE_CLAIM_STATUSES]  # type: ignore[valid-type]
    approved_amount: Optional[float] = Field(None, ge=0)
    patient_payable: Optional[float] = Field(None, ge=0)
    rejection_reason: Optional[str] = None
    remarks: Optional[str] = None


class InsuranceClaim(ORMModel):
    id: int
    claim_number: str
    patient_id: int
    policy_id: Optional[int] = None
    bill_type: Optional[str] = None
    bill_id: Optional[int] = None
    claim_type: str = "Reimbursement"
    treatment_type: Optional[str] = None
    diagnosis: Optional[str] = None
    hospital_name: Optional[str] = None
    admission_date: Optional[date] = None
    discharge_date: Optional[date] = None
    claimed_amount: float = 0.0
    approved_amount: float = 0.0
    patient_payable: float = 0.0
    status: str
    rejection_reason: Optional[str] = None
    remarks: Optional[str] = None
    submitted_at: Optional[datetime] = None
    settled_at: Optional[datetime] = None
    created_by: Optional[str] = None
    updated_by: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    patient: Optional[PatientBrief] = None
    policy: Optional[InsurancePolicy] = None


class InsuranceStats(BaseModel):
    total_claims: int
    draft: int
    submitted: int
    under_review: int
    approved: int
    rejected: int
    settled: int
    claimed_amount: float
    approved_amount: float
    settled_amount: float
    pending_amount: float
    active_policies: int


# ===========================================
# HOSPITAL STRUCTURE (departments → wards → rooms → beds)
# ===========================================
class DepartmentBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    code: str = Field(..., min_length=1, max_length=20)
    department_type: Literal[constants.DEPARTMENT_TYPES] = "Clinical"  # type: ignore[valid-type]
    description: Optional[str] = None
    head_doctor_id: Optional[int] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    is_active: bool = True

    @field_validator("code")
    @classmethod
    def upper_code(cls, v: str) -> str:
        return v.strip().upper()


class DepartmentCreate(DepartmentBase):
    pass


class DepartmentUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    department_type: Optional[Literal[constants.DEPARTMENT_TYPES]] = None  # type: ignore[valid-type]
    description: Optional[str] = None
    head_doctor_id: Optional[int] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    is_active: Optional[bool] = None


class Department(DepartmentBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    head_doctor: Optional[PatientBrief] = None


class WardBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    code: str = Field(..., min_length=1, max_length=20)
    ward_type: Literal[constants.WARD_TYPES] = "General"  # type: ignore[valid-type]
    department_id: Optional[int] = None
    floor: Optional[str] = None
    building: Optional[str] = None
    daily_charge: float = Field(0.0, ge=0)
    is_active: bool = True
    notes: Optional[str] = None

    @field_validator("code")
    @classmethod
    def upper_code(cls, v: str) -> str:
        return v.strip().upper()


class WardCreate(WardBase):
    pass


class WardUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    ward_type: Optional[Literal[constants.WARD_TYPES]] = None  # type: ignore[valid-type]
    department_id: Optional[int] = None
    floor: Optional[str] = None
    building: Optional[str] = None
    daily_charge: Optional[float] = Field(None, ge=0)
    is_active: Optional[bool] = None
    notes: Optional[str] = None


class Ward(WardBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: Optional[datetime] = None
    department: Optional[Department] = None


class RoomBase(BaseModel):
    ward_id: int
    room_number: str = Field(..., min_length=1, max_length=30)
    room_type: Optional[str] = None
    floor: Optional[str] = None
    daily_charge: Optional[float] = Field(None, ge=0)
    is_active: bool = True


class RoomCreate(RoomBase):
    pass


class RoomUpdate(BaseModel):
    room_number: Optional[str] = None
    room_type: Optional[str] = None
    floor: Optional[str] = None
    daily_charge: Optional[float] = Field(None, ge=0)
    is_active: Optional[bool] = None


class Room(RoomBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: Optional[datetime] = None


class BedBase(BaseModel):
    room_id: int
    bed_code: str = Field(..., min_length=1, max_length=30)
    bed_type: Optional[str] = None
    status: Literal[constants.BED_STATUSES] = "Available"  # type: ignore[valid-type]
    daily_charge: Optional[float] = Field(None, ge=0)
    is_active: bool = True
    notes: Optional[str] = None


class BedCreate(BedBase):
    pass


class BedUpdate(BaseModel):
    bed_code: Optional[str] = None
    bed_type: Optional[str] = None
    status: Optional[Literal[constants.BED_STATUSES]] = None  # type: ignore[valid-type]
    daily_charge: Optional[float] = Field(None, ge=0)
    is_active: Optional[bool] = None
    notes: Optional[str] = None


class Bed(BedBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    room: Optional[Room] = None


class BedBoardItem(BaseModel):
    """One tile on the bed board: the bed plus who is in it."""

    bed_id: int
    bed_code: str
    bed_type: Optional[str] = None
    status: str
    is_active: bool = True
    ward_id: Optional[int] = None
    ward_name: Optional[str] = None
    ward_type: Optional[str] = None
    room_id: Optional[int] = None
    room_number: Optional[str] = None
    daily_charge: float = 0.0
    admission_id: Optional[int] = None
    patient_id: Optional[int] = None
    patient_name: Optional[str] = None
    patient_uhid: Optional[str] = None
    admitted_at: Optional[datetime] = None
    attending_doctor: Optional[str] = None


class BedBoardSummary(BaseModel):
    total_beds: int
    available: int
    occupied: int
    reserved: int
    cleaning: int
    maintenance: int
    blocked: int
    occupancy_percent: float
    by_ward: List[Dict[str, Any]] = Field(default_factory=list)


# ===========================================
# IPD — admission, transfer, discharge
# ===========================================
class IPAdmissionBase(BaseModel):
    patient_id: int
    doctor_in_charge: Optional[str] = None
    attending_doctor_id: Optional[int] = None
    department_id: Optional[int] = None
    ward_number: Optional[str] = None
    room_number: Optional[str] = None
    reason_for_admission: Optional[str] = None
    admission_type: Literal[constants.ADMISSION_TYPES] = "Planned"  # type: ignore[valid-type]
    admission_source: Optional[Literal[constants.ADMISSION_SOURCES]] = "OPD"  # type: ignore[valid-type]
    provisional_diagnosis: Optional[str] = None
    admission_notes: Optional[str] = None
    expected_discharge_date: Optional[date] = None


class IPAdmissionCreate(IPAdmissionBase):
    # Optional at creation: a patient can be admitted before a bed is free.
    bed_id: Optional[int] = None


class IPAdmissionUpdate(BaseModel):
    doctor_in_charge: Optional[str] = None
    attending_doctor_id: Optional[int] = None
    department_id: Optional[int] = None
    provisional_diagnosis: Optional[str] = None
    admission_notes: Optional[str] = None
    reason_for_admission: Optional[str] = None
    expected_discharge_date: Optional[date] = None
    status: Optional[Literal[constants.ADMISSION_STATUSES]] = None  # type: ignore[valid-type]
    discharge_date: Optional[datetime] = None


class BedAssignRequest(BaseModel):
    bed_id: int
    reason: Optional[str] = None


class PatientTransferRequest(BaseModel):
    to_bed_id: int
    reason: str = Field(..., min_length=3, max_length=500)


class DischargeRequest(BaseModel):
    discharge_type: Literal[constants.DISCHARGE_TYPES] = "Routine"  # type: ignore[valid-type]
    discharge_date: Optional[datetime] = None
    summary: Optional["DischargeSummaryCreate"] = None
    require_summary: bool = True
    # When true, refuse while the clearance checklist has open (warning) items.
    # Either way the open items are written to the audit trail.
    require_clearance: bool = False


class ClearanceCheck(BaseModel):
    key: str
    label: str
    status: Literal["ok", "warning", "info"]
    detail: str


class DischargeClearance(BaseModel):
    admission_id: int
    status: str
    ready: bool
    outstanding_amount: float
    unbilled_amount: float
    checks: List[ClearanceCheck]


class IPBillPreview(BaseModel):
    admission_id: int
    patient_id: int
    days_stayed: int
    room_charge_per_day: float
    room_charges: float
    lab_charges: float
    lab_order_ids: List[int]
    lab_lines: List[Dict[str, Any]]
    pharmacy_charges: float
    pharmacy_bill_ids: List[int]
    pharmacy_lines: List[Dict[str, Any]]
    existing_ip_bills: List[int]


class BillPaymentCreate(BaseModel):
    amount: float = Field(..., gt=0)
    payment_mode: PaymentMode = "Cash"
    notes: Optional[str] = None


class BillCancelRequest(BaseModel):
    reason: str = Field(..., min_length=3, max_length=300)


class IPAdmission(IPAdmissionBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    admission_date: datetime
    bed_id: Optional[int] = None
    bed_code: Optional[str] = None
    discharge_date: Optional[datetime] = None
    discharged_by: Optional[str] = None
    discharge_type: Optional[str] = None
    status: str
    created_at: Optional[datetime] = None
    patient: Optional[PatientBrief] = None
    bed: Optional[Bed] = None
    department: Optional[Department] = None


class BedAllocationInfo(ORMModel):
    """One row of a bed's occupancy history."""

    id: int
    admission_id: int
    bed_id: int
    allocated_at: datetime
    released_at: Optional[datetime] = None
    allocated_by: Optional[str] = None
    released_by: Optional[str] = None
    release_reason: Optional[str] = None
    bed: Optional["Bed"] = None


class PatientTransferInfo(ORMModel):
    id: int
    from_bed_id: Optional[int] = None
    to_bed_id: int
    from_ward: Optional[str] = None
    to_ward: Optional[str] = None
    reason: Optional[str] = None
    transferred_by: Optional[str] = None
    transferred_at: datetime


class IPAdmissionDetail(IPAdmission):
    """Admission plus its clinical record, for the IPD workspace.

    The nested collections are typed as real models (not ``Dict[str, Any]``) so the
    OpenAPI contract is accurate and ORM objects serialise correctly.
    """

    allocations: List[BedAllocationInfo] = Field(default_factory=list)
    transfers: List[PatientTransferInfo] = Field(default_factory=list)
    nursing_notes: List["NursingNote"] = Field(default_factory=list)
    medication_orders: List["MedicationOrder"] = Field(default_factory=list)
    discharge_summary: Optional["DischargeSummary"] = None
    length_of_stay_days: int = 0
    billable_room_charge: float = 0.0


# ===========================================
# IPD — nursing
# ===========================================
class NursingNoteBase(BaseModel):
    shift: Literal[constants.NURSING_SHIFTS] = "Morning"  # type: ignore[valid-type]
    recorded_at: Optional[datetime] = None
    temperature: Optional[float] = Field(None, ge=25, le=45)
    pulse: Optional[int] = Field(None, ge=0, le=400)
    respiratory_rate: Optional[int] = Field(None, ge=0, le=100)
    bp_systolic: Optional[int] = Field(None, ge=0, le=400)
    bp_diastolic: Optional[int] = Field(None, ge=0, le=300)
    spo2: Optional[int] = Field(None, ge=0, le=100)
    pain_score: Optional[int] = Field(None, ge=0, le=10)
    blood_sugar: Optional[float] = Field(None, ge=0, le=2000)
    intake_ml: Optional[int] = Field(None, ge=0, le=100000)
    output_ml: Optional[int] = Field(None, ge=0, le=100000)
    notes: Optional[str] = None
    is_critical: bool = False

    @field_validator("bp_diastolic")
    @classmethod
    def diastolic_below_systolic(cls, v: Optional[int], info) -> Optional[int]:
        systolic = info.data.get("bp_systolic")
        if v is not None and systolic is not None and v >= systolic:
            raise ValueError("Diastolic pressure must be lower than systolic")
        return v


class NursingNoteCreate(NursingNoteBase):
    pass


class NursingNote(NursingNoteBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    admission_id: int
    recorded_at: datetime
    recorded_by: Optional[str] = None


# ===========================================
# IPD — medication
# ===========================================
class MedicationOrderBase(BaseModel):
    medicine_id: Optional[int] = None
    medicine_name: str = Field(..., min_length=1, max_length=150)
    dose: Optional[str] = None
    route: Literal[constants.MEDICATION_ROUTES] = "Oral"  # type: ignore[valid-type]
    frequency: Literal[constants.MEDICATION_FREQUENCIES] = "BD"  # type: ignore[valid-type]
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    notes: Optional[str] = None


class MedicationOrderCreate(MedicationOrderBase):
    pass


class MedicationOrderUpdate(BaseModel):
    dose: Optional[str] = None
    route: Optional[Literal[constants.MEDICATION_ROUTES]] = None  # type: ignore[valid-type]
    frequency: Optional[Literal[constants.MEDICATION_FREQUENCIES]] = None  # type: ignore[valid-type]
    end_date: Optional[datetime] = None
    status: Optional[Literal[constants.MEDICATION_ORDER_STATUSES]] = None  # type: ignore[valid-type]
    stop_reason: Optional[str] = None
    notes: Optional[str] = None


class MedicationAdministrationCreate(BaseModel):
    status: Literal[constants.MEDICATION_ADMIN_STATUSES] = "Given"  # type: ignore[valid-type]
    dose_given: Optional[str] = None
    administered_at: Optional[datetime] = None
    remarks: Optional[str] = None


class MedicationAdministration(ORMModel):
    id: int
    order_id: int
    administered_at: datetime
    administered_by: Optional[str] = None
    dose_given: Optional[str] = None
    status: str
    remarks: Optional[str] = None


class MedicationOrder(MedicationOrderBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    admission_id: int
    status: str
    prescribed_by: Optional[str] = None
    stop_reason: Optional[str] = None
    created_at: Optional[datetime] = None
    administrations: List[MedicationAdministration] = Field(default_factory=list)


# ===========================================
# IPD — discharge summary
# ===========================================
class DischargeSummaryBase(BaseModel):
    discharge_type: Literal[constants.DISCHARGE_TYPES] = "Routine"  # type: ignore[valid-type]
    final_diagnosis: Optional[str] = None
    procedures_performed: Optional[str] = None
    investigations: Optional[str] = None
    condition_at_discharge: Optional[Literal[constants.DISCHARGE_CONDITIONS]] = None  # type: ignore[valid-type]
    medication_summary: Optional[str] = None
    diet_advice: Optional[str] = None
    activity_advice: Optional[str] = None
    follow_up_instructions: Optional[str] = None
    follow_up_date: Optional[date] = None


class DischargeSummaryCreate(DischargeSummaryBase):
    pass


class DischargeSummaryUpdate(BaseModel):
    discharge_type: Optional[Literal[constants.DISCHARGE_TYPES]] = None  # type: ignore[valid-type]
    final_diagnosis: Optional[str] = None
    procedures_performed: Optional[str] = None
    investigations: Optional[str] = None
    condition_at_discharge: Optional[Literal[constants.DISCHARGE_CONDITIONS]] = None  # type: ignore[valid-type]
    medication_summary: Optional[str] = None
    diet_advice: Optional[str] = None
    activity_advice: Optional[str] = None
    follow_up_instructions: Optional[str] = None
    follow_up_date: Optional[date] = None
    status: Optional[Literal[constants.DISCHARGE_SUMMARY_STATUSES]] = None  # type: ignore[valid-type]


class DischargeSummary(DischargeSummaryBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    admission_id: int
    patient_id: int
    status: str
    prepared_by: Optional[str] = None
    prepared_at: Optional[datetime] = None
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


DischargeRequest.model_rebuild()


# ===========================================
# IPD — dashboard
# ===========================================
class IPDStats(BaseModel):
    total_beds: int
    available_beds: int
    occupied_beds: int
    occupancy_percent: float
    current_admissions: int
    admissions_today: int
    discharges_today: int
    average_length_of_stay: float
    critical_patients: int          # admissions with a critical nursing note in 24h
    pending_discharge_summaries: int
    active_medication_orders: int


class StaffMemberCreate(BaseModel):
    """Create a hospital staff account (doctor, nurse, technician, desk)."""

    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6, max_length=128)
    role: Literal[constants.STAFF_ROLES]  # type: ignore[valid-type]
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    employee_code: Optional[str] = None
    designation: Optional[str] = None
    specialization: Optional[str] = None
    license_number: Optional[str] = None
    department_id: Optional[int] = None
    joining_date: Optional[date] = None
    consultation_fee: Optional[float] = Field(None, ge=0)


class StaffMemberUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    employee_code: Optional[str] = None
    designation: Optional[str] = None
    specialization: Optional[str] = None
    license_number: Optional[str] = None
    department_id: Optional[int] = None
    joining_date: Optional[date] = None
    consultation_fee: Optional[float] = Field(None, ge=0)


class StaffMember(UserResponse):
    employee_code: Optional[str] = None
    designation: Optional[str] = None
    specialization: Optional[str] = None
    license_number: Optional[str] = None
    department_id: Optional[int] = None
    joining_date: Optional[date] = None
    consultation_fee: Optional[float] = None
    last_login_at: Optional[datetime] = None
