from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, date

from pydantic import BaseModel, Field, validator
import re

# ----------------- USER SCHEMAS -----------------
class UserBase(BaseModel):
    username: str = Field(..., min_length=2, max_length=50)
    role: str

    @validator('username')
    def validate_username_chars(cls, v):
        if not re.match(r'^[a-zA-Z0-9_]+$', v):
            raise ValueError('Username must contain only alphanumeric characters and underscores')
        return v

class UserCreate(UserBase):
    password: str = Field(..., min_length=6)

class UserResponse(UserBase):
    id: int
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str
    refresh_token: Optional[str] = None
    expires_in: Optional[int] = None
    role: Optional[str] = None

class TokenData(BaseModel):
    username: Optional[str] = None

class PatientBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    age: int = Field(..., ge=0, le=150)
    gender: str = Field(..., pattern="^(Male|Female|Other)$")
    phone: Optional[str] = None
    address: Optional[str] = None
    aadhaar: Optional[str] = None
    blood_group: Optional[str] = None
    details: Optional[Dict[str, Any]] = {}

    @validator('phone')
    def validate_phone_number(cls, v):
        if v:
            clean = v.replace(' ', '').replace('-', '')
            if not re.match(r'^[6-9]\d{9}$', clean):
                raise ValueError('Invalid Indian Phone Number (10 digits starting with 6-9)')
        return v

    @validator('aadhaar')
    def validate_aadhaar_number(cls, v):
        if v:
            clean = v.replace(' ', '')
            if not re.match(r'^\d{12}$', clean):
                raise ValueError('Aadhaar card must contain exactly 12 digits')
        return v

class PatientCreate(PatientBase):
    pass

class Patient(PatientBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

# ----------------- OP TOKEN SCHEMAS -----------------
class OPTokenBase(BaseModel):
    patient_id: int
    session: str # "Morning" or "Evening"
    date: date
    fee: float = 0.0
    details: Optional[Dict[str, Any]] = {}

class OPTokenCreate(OPTokenBase):
    pass

class OPToken(OPTokenBase):
    id: int
    token_number: int
    status: str
    is_billed: bool
    details: Optional[Dict[str, Any]] = {}
    patient: Optional[Patient] = None

    class Config:
        from_attributes = True

# ----------------- APPOINTMENT SCHEMAS -----------------
class AppointmentBase(BaseModel):
    patient_id: int
    doctor_id: Optional[int] = None
    appointment_date: date
    time_slot: Optional[str] = None
    reason: Optional[str] = None
    status: str = "Scheduled"
    details: Optional[Dict[str, Any]] = {}

class AppointmentCreate(AppointmentBase):
    pass

class AppointmentResponse(AppointmentBase):
    id: int
    patient: Optional[Patient] = None
    
    class Config:
        from_attributes = True

# ----------------- CASESHEET SCHEMAS -----------------
class PrescribedMedicine(BaseModel):
    name: str
    quantity: int
    dosage: Optional[str] = None
    duration: Optional[str] = None
    instructions: Optional[str] = None
    timing_morning: Optional[bool] = None
    timing_afternoon: Optional[bool] = None
    timing_night: Optional[bool] = None
    timing_relation: Optional[str] = None # Before/After food

class CasesheetBase(BaseModel):
    patient_id: int
    token_id: Optional[int] = None
    symptoms: Optional[str] = None
    diagnosis: Optional[str] = None
    vitals_bp: Optional[str] = None
    vitals_pulse: Optional[str] = None
    vitals_temp: Optional[str] = None
    vitals_resp: Optional[str] = None
    prescribed_medicines: List[PrescribedMedicine] = []
    prescribed_labs: List[str] = []

class CasesheetCreate(CasesheetBase):
    pass

class Casesheet(CasesheetBase):
    id: int
    date: date

    class Config:
        from_attributes = True

# ----------------- INVENTORY SCHEMAS -----------------
class MedicineStockBase(BaseModel):
    name: str
    category: str # "Pharmacy", "Lab", "Consumable"
    batch_no: Optional[str] = None
    expiry_date: Optional[date] = None
    quantity: int = 0
    unit_price: float = 0.0
    min_stock_level: int = 10
    details: Optional[Dict[str, Any]] = {}

class MedicineStockCreate(MedicineStockBase):
    pass

class MedicineStock(MedicineStockBase):
    id: int

    class Config:
        from_attributes = True

class StockTransactionCreate(BaseModel):
    medicine_id: int
    type: str # "Stock In", "Stock Out"
    quantity: int
    notes: Optional[str] = None
    details: Optional[Dict[str, Any]] = {}

# ----------------- PHARMACY BILL SCHEMAS -----------------
class PharmacyBillItemBase(BaseModel):
    medicine_id: int
    quantity: int

class PharmacyBillItemCreate(PharmacyBillItemBase):
    pass

class PharmacyBillItemResponse(BaseModel):
    id: int
    medicine_name: str
    quantity: int
    unit_price: float
    total_price: float

    class Config:
        from_attributes = True

class PharmacyBillCreate(BaseModel):
    patient_id: Optional[int] = None
    patient_name: Optional[str] = None # For walk-ins
    discount: float = 0.0
    gst: float = 0.0
    payment_mode: str = "Cash"
    payment_details: Optional[Dict[str, float]] = None
    details: Optional[Dict[str, Any]] = {}
    items: List[PharmacyBillItemCreate]

class PharmacyBillResponse(BaseModel):
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
    details: Optional[Dict[str, Any]] = {}
    items: List[PharmacyBillItemResponse] = []

    class Config:
        from_attributes = True

# ----------------- LAB BILL SCHEMAS -----------------
class LabBillItemCreate(BaseModel):
    test_name: str
    price: float

class LabBillItemResponse(BaseModel):
    id: int
    test_name: str
    price: float

    class Config:
        from_attributes = True

class LabBillCreate(BaseModel):
    patient_id: int
    discount: float = 0.0
    gst: float = 0.0
    payment_mode: str = "Cash"
    payment_details: Optional[Dict[str, float]] = None
    items: List[LabBillItemCreate]

class LabBillResponse(BaseModel):
    id: int
    patient_id: int
    bill_date: datetime
    total: float
    discount: float = 0.0
    gst: float = 0.0
    status: str
    payment_mode: str = "Cash"
    payment_details: Optional[Any] = None
    items: List[LabBillItemResponse] = []

    class Config:
        from_attributes = True

# ----------------- IP ADMISSION SCHEMAS -----------------
class IPAdmissionBase(BaseModel):
    patient_id: int
    ward_number: Optional[str] = None
    room_number: Optional[str] = None
    doctor_in_charge: Optional[str] = None
    reason_for_admission: Optional[str] = None

class IPAdmissionCreate(IPAdmissionBase):
    pass

class IPAdmission(IPAdmissionBase):
    id: int
    admission_date: datetime
    discharge_date: Optional[datetime] = None
    status: str
    patient: Optional[Patient] = None

    class Config:
        from_attributes = True

# ----------------- LAB REPORT SCHEMAS -----------------
class LabReportBase(BaseModel):
    patient_id: int
    test_name: str
    result_value: Optional[str] = None
    normal_range: Optional[str] = None
    units: Optional[str] = None
    reported_by: Optional[str] = None
    remarks: Optional[str] = None
    results_data: Optional[Any] = None

class LabReportCreate(LabReportBase):
    pass

class LabReport(LabReportBase):
    id: int
    date_conducted: datetime
    patient: Optional[Patient] = None

    class Config:
        from_attributes = True

# ----------------- NEW LAB MANAGEMENT SCHEMAS -----------------
class LabTestMasterBase(BaseModel):
    test_code: str
    test_name: str
    category: Optional[str] = None
    department: Optional[str] = None
    sample_type: Optional[str] = None
    unit: Optional[str] = None
    reference_range: Optional[str] = None
    normal_range_male: Optional[str] = None
    normal_range_female: Optional[str] = None
    normal_range_child: Optional[str] = None
    price: float = 0.0
    tat_hours: int = 24
    is_active: bool = True

class LabTestMasterCreate(LabTestMasterBase):
    pass

class LabTestMasterUpdate(BaseModel):
    test_code: Optional[str] = None
    test_name: Optional[str] = None
    category: Optional[str] = None
    department: Optional[str] = None
    sample_type: Optional[str] = None
    unit: Optional[str] = None
    reference_range: Optional[str] = None
    normal_range_male: Optional[str] = None
    normal_range_female: Optional[str] = None
    normal_range_child: Optional[str] = None
    price: Optional[float] = None
    tat_hours: Optional[int] = None
    is_active: Optional[bool] = None

class LabTestMaster(LabTestMasterBase):
    id: int

    class Config:
        from_attributes = True

class LabOrderBase(BaseModel):
    patient_id: int
    doctor_name: Optional[str] = None
    test_id: int
    status: str = "Pending"
    priority: str = "Routine"
    remarks: Optional[str] = None

class LabOrderCreate(LabOrderBase):
    pass

class LabOrderUpdate(BaseModel):
    status: Optional[str] = None
    priority: Optional[str] = None
    remarks: Optional[str] = None

class LabOrder(LabOrderBase):
    id: int
    order_date: datetime
    patient: Optional[Patient] = None
    test: Optional[LabTestMaster] = None

    class Config:
        from_attributes = True

class LabSampleBase(BaseModel):
    order_id: int
    sample_type: str
    collected_by: Optional[str] = None
    container_type: Optional[str] = None
    barcode: Optional[str] = None
    remarks: Optional[str] = None
    status: str = "Pending"

class LabSampleCreate(LabSampleBase):
    pass

class LabSampleUpdate(BaseModel):
    sample_type: Optional[str] = None
    collected_by: Optional[str] = None
    container_type: Optional[str] = None
    barcode: Optional[str] = None
    remarks: Optional[str] = None
    status: Optional[str] = None

class LabSample(LabSampleBase):
    id: int
    collection_date: Optional[datetime] = None
    order: Optional[LabOrder] = None

    class Config:
        from_attributes = True

# ===========================================
# NEW: OP BILL SCHEMAS (Consolidated OP Bill)
# ===========================================
class OtherCharge(BaseModel):
    name: str
    amount: float

class OPBillCreate(BaseModel):
    patient_id: int
    token_id: Optional[int] = None
    doctor_name: Optional[str] = None
    department: Optional[str] = None
    consultation_fee: float = 0.0
    lab_charges: float = 0.0
    pharmacy_charges: float = 0.0
    other_charges: List[OtherCharge] = []
    discount: float = 0.0
    gst: float = 0.0
    payment_mode: str = "Cash"
    payment_details: Optional[Dict[str, float]] = None
    notes: Optional[str] = None

class OPBillResponse(BaseModel):
    id: int
    patient_id: int
    token_id: Optional[int] = None
    bill_date: datetime
    doctor_name: Optional[str] = None
    department: Optional[str] = None
    consultation_fee: float
    lab_charges: float
    pharmacy_charges: float
    other_charges: List[OtherCharge] = []
    subtotal: float
    discount: float
    gst: float
    total: float
    payment_mode: str
    payment_details: Optional[Dict[str, float]] = None
    notes: Optional[str] = None
    patient: Optional[Patient] = None

    class Config:
        from_attributes = True

# ===========================================
# NEW: IP BILL SCHEMAS (Inpatient Bill)
# ===========================================
class IPBillCreate(BaseModel):
    patient_id: int
    admission_id: Optional[int] = None
    doctor_name: Optional[str] = None
    room_charge_per_day: float = 0.0
    days_stayed: int = 1
    doctor_charges: float = 0.0
    nursing_charges: float = 0.0
    pharmacy_charges: float = 0.0
    lab_charges: float = 0.0
    other_charges: List[OtherCharge] = []
    discount: float = 0.0
    gst: float = 0.0
    payment_mode: str = "Cash"
    payment_details: Optional[Dict[str, float]] = None
    notes: Optional[str] = None

class IPBillResponse(BaseModel):
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
    other_charges: List[OtherCharge] = []
    subtotal: float
    discount: float
    gst: float
    total: float
    payment_mode: str
    payment_details: Optional[Dict[str, float]] = None
    notes: Optional[str] = None
    patient: Optional[Patient] = None

    class Config:
        from_attributes = True

# ===========================================
# NEW: REPORTS SCHEMAS
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

# ===========================================
# NEW: GLOBAL SEARCH SCHEMAS
# ===========================================
class SearchResult(BaseModel):
    type: str  # "patient", "token", "op_bill", "ip_bill", "pharmacy_bill", "lab_bill", "admission"
    id: int
    patient_id: Optional[int] = None
    patient_name: Optional[str] = None
    detail: str  # Short description
    date: Optional[str] = None
    amount: Optional[float] = None

# ===========================================
# HOSPITAL SETTINGS SCHEMAS
# ===========================================
class HospitalSettingItem(BaseModel):
    key: str
    value: Optional[str] = None

class HospitalSettingsUpdate(BaseModel):
    settings: List[HospitalSettingItem]

class HospitalSettingResponse(BaseModel):
    id: int
    key: str
    value: Optional[str] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# ===========================================
# AUDIT LOG SCHEMAS
# ===========================================
class AuditLogResponse(BaseModel):
    id: int
    user_id: Optional[int] = None
    username: Optional[str] = None
    action: str
    details: Optional[str] = None
    timestamp: datetime
    ip_address: Optional[str] = None

    class Config:
        from_attributes = True

# ===========================================
# DASHBOARD SCHEMAS
# ===========================================
class DashboardStats(BaseModel):
    today_patients: int
    today_revenue: float
    op_count: int
    ip_count: int
    lab_count: int
    medicine_sales: float
    total_patients: int
    active_ip: int
    low_stock_count: int

class ChartDataPoint(BaseModel):
    label: str
    value: float

class DashboardCharts(BaseModel):
    daily_revenue: List[ChartDataPoint]
    monthly_revenue: List[ChartDataPoint]
    patient_growth: List[ChartDataPoint]
    medicine_sales: List[ChartDataPoint]


from typing import Any

# --- Additional Update Schemas ---
class PatientUpdate(BaseModel):
    name: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    aadhaar: Optional[str] = None
    blood_group: Optional[str] = None
    details: Optional[Dict[str, Any]] = None

class CasesheetUpdate(BaseModel):
    vitals: Optional[Dict[str, Any]] = None
    chief_complaint: Optional[str] = None
    hpi: Optional[str] = None
    pmh: Optional[str] = None
    family_history: Optional[str] = None
    allergies: Optional[str] = None
    clinical_findings: Optional[str] = None
    diagnosis: Optional[str] = None
    icd_code: Optional[str] = None
    treatment_plan: Optional[str] = None
    prescribed_medicines: Optional[List[Any]] = None
    prescribed_labs: Optional[List[str]] = None
    advice: Optional[str] = None
    follow_up_date: Optional[date] = None

class MedicineStockUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    batch_no: Optional[str] = None
    expiry_date: Optional[date] = None
    quantity: Optional[int] = None
    unit_price: Optional[float] = None
    min_stock_level: Optional[int] = None
    details: Optional[Dict[str, Any]] = None

class IPAdmissionUpdate(BaseModel):
    ward_number: Optional[str] = None
    room_number: Optional[str] = None
    doctor_in_charge: Optional[str] = None
    reason_for_admission: Optional[str] = None
    status: Optional[str] = None
    discharge_date: Optional[datetime] = None

class LabReportUpdate(BaseModel):
    test_name: Optional[str] = None
    result_value: Optional[str] = None
    normal_range: Optional[str] = None
    units: Optional[str] = None
    reported_by: Optional[str] = None
    remarks: Optional[str] = None
    results_data: Optional[Any] = None
