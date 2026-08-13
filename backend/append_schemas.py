
with open('f:\\\\Hospital Soft\\\\backend\\\\schemas.py', 'a') as f:
    f.write('''
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
''')

