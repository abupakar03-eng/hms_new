"""Single source of truth for enumerations used across the API.

Every value that used to be a free-form string (roles, order statuses, payment
modes, ...) lives here so that request validation, CRUD logic and the workflow
guards cannot drift apart.
"""

# ---------------------------------------------------------------------------
# Roles
# ---------------------------------------------------------------------------
# "Patient" is a self-service account: it may only ever see its own records, via
# the /portal/* surface. Every other role is hospital staff with access to the
# shared clinical/billing API.
PATIENT_ROLE = "Patient"

STAFF_ROLES = (
    "Admin",
    "Doctor",
    "Nurse",
    "Receptionist",
    "Pharmacy",
    "Laboratory",
    "Insurance",
    "Billing",
)

ROLES = STAFF_ROLES + (PATIENT_ROLE,)

GENDERS = ("Male", "Female", "Other")

OP_SESSIONS = ("Morning", "Evening")

OP_TOKEN_STATUSES = ("Pending", "In Progress", "Completed", "Cancelled")

APPOINTMENT_STATUSES = ("Scheduled", "Confirmed", "Completed", "Cancelled", "Rescheduled")

APPOINTMENT_SLOTS = (
    "09:00 AM", "09:30 AM", "10:00 AM", "10:30 AM", "11:00 AM", "11:30 AM",
    "12:00 PM", "12:30 PM", "02:00 PM", "02:30 PM", "03:00 PM", "03:30 PM",
    "04:00 PM", "04:30 PM", "05:00 PM", "05:30 PM", "06:00 PM", "06:30 PM",
)

PAYMENT_MODES = ("Cash", "UPI", "Card", "Bank Transfer", "Split", "Insurance", "Cheque", "IP Credit")

# "IP Credit": a pharmacy sale charged to an inpatient admission and settled on
# the final IP bill instead of at the counter.
IP_CREDIT = "IP Credit"

# OP / IP bill settlement. Pending/Partial/Paid are derived from amount_paid;
# Cancelled is set explicitly and removes the bill from revenue.
BILL_PAYMENT_STATUSES = ("Pending", "Partial", "Paid", "Cancelled")

STOCK_CATEGORIES = ("Pharmacy", "Lab", "Consumable")

STOCK_TRANSACTION_TYPES = ("Stock In", "Stock Out", "Sale", "Return", "Adjustment")

LAB_ORDER_STATUSES = ("Pending", "Sample Collected", "Testing", "Completed", "Verified", "Cancelled")

# Legal forward transitions. Note "Cancelled" is reachable from any non-final state.
LAB_ORDER_TRANSITIONS = {
    "Pending": ("Sample Collected", "Testing", "Cancelled"),
    "Sample Collected": ("Testing", "Cancelled"),
    "Testing": ("Completed", "Verified", "Cancelled"),
    "Completed": ("Verified",),
    "Verified": (),
    "Cancelled": (),
}

# Statuses for which the result may no longer be edited.
LAB_ORDER_LOCKED_STATUSES = ("Verified", "Cancelled")

LAB_SAMPLE_STATUSES = ("Pending", "Collected", "Received", "Rejected", "Recollected")

LAB_REPORT_STATUSES = ("Draft", "Final", "Verified")

LAB_PRIORITIES = ("Routine", "Urgent", "STAT")

LAB_BILL_STATUSES = ("Pending", "Paid", "Cancelled")

LAB_TEST_CATEGORIES = (
    "Pathology",
    "Biochemistry",
    "Haematology",
    "Microbiology",
    "Serology",
    "Radiology",
    "Histopathology",
    "Molecular",
)

LAB_PARAMETER_DATA_TYPES = ("Numeric", "Text", "Options")

ABNORMAL_FLAGS = ("Normal", "High", "Low", "Critical High", "Critical Low", "Abnormal")

# ---------------------------------------------------------------------------
# Insurance
# ---------------------------------------------------------------------------
INSURANCE_CLAIM_STATUSES = (
    "Draft",
    "Submitted",
    "Under Review",
    "Approved",
    "Partially Approved",
    "Rejected",
    "Settled",
)

# Claim lifecycle: Approved/Partially Approved can move on to Settled (paid out).
INSURANCE_CLAIM_TRANSITIONS = {
    "Draft": ("Submitted", "Rejected"),
    "Submitted": ("Under Review", "Approved", "Partially Approved", "Rejected"),
    "Under Review": ("Approved", "Partially Approved", "Rejected"),
    "Approved": ("Settled",),
    "Partially Approved": ("Settled",),
    "Rejected": (),
    "Settled": (),
}

INSURANCE_CLAIM_TYPES = ("Cashless", "Reimbursement")

TREATMENT_TYPES = ("OP", "IP", "Pharmacy", "Laboratory", "Other")


def is_valid_transition(current: str, target: str) -> bool:
    """Return True when ``current -> target`` is an allowed lab order transition.

    Re-applying the current status is always allowed so that idempotent updates
    (a double click on "Collect Sample") do not fail.
    """
    if current == target:
        return True
    return target in LAB_ORDER_TRANSITIONS.get(current, ())


def is_valid_claim_transition(current: str, target: str) -> bool:
    if current == target:
        return True
    return target in INSURANCE_CLAIM_TRANSITIONS.get(current, ())


# ---------------------------------------------------------------------------
# Inpatient (IPD)
# ---------------------------------------------------------------------------
DEPARTMENT_TYPES = ("Clinical", "Diagnostic", "Support", "Administrative", "Emergency")

WARD_TYPES = (
    "General",
    "Semi-Private",
    "Private",
    "ICU",
    "HDU",
    "NICU",
    "Maternity",
    "Paediatric",
    "Emergency",
    "Isolation",
    "Day Care",
)

BED_STATUSES = ("Available", "Occupied", "Reserved", "Cleaning", "Maintenance", "Blocked")

# Bed statuses a patient may actually be placed in.
BED_ALLOCATABLE_STATUSES = ("Available", "Reserved")

ADMISSION_TYPES = ("Planned", "Emergency", "Transfer In", "Day Care")

ADMISSION_SOURCES = ("OPD", "Emergency", "Direct", "Referral", "Transfer")

# "Discharged" and friends are terminal for the admission record.
ADMISSION_STATUSES = ("Admitted", "Discharged", "Transferred", "Deceased", "DAMA")

ADMISSION_TERMINAL_STATUSES = ("Discharged", "Transferred", "Deceased", "DAMA")

# Legal admission lifecycle transitions.
ADMISSION_TRANSITIONS = {
    "Admitted": ("Discharged", "Transferred", "Deceased", "DAMA"),
    "Discharged": (),
    "Transferred": (),
    "Deceased": (),
    "DAMA": (),
}

NURSING_SHIFTS = ("Morning", "Evening", "Night")

MEDICATION_ROUTES = ("Oral", "IV", "IM", "SC", "Topical", "Inhalation", "Rectal", "Nasal", "Ophthalmic")

MEDICATION_FREQUENCIES = (
    "OD",   # once daily
    "BD",   # twice daily
    "TDS",  # three times daily
    "QID",  # four times daily
    "HS",   # at bedtime
    "SOS",  # as needed
    "STAT", # immediately, once
    "Weekly",
)

MEDICATION_ORDER_STATUSES = ("Active", "Completed", "Stopped", "On Hold")

MEDICATION_ADMIN_STATUSES = ("Given", "Held", "Refused", "Missed", "Not Required")

DISCHARGE_SUMMARY_STATUSES = ("Draft", "Final", "Approved")

DISCHARGE_TYPES = ("Routine", "Transfer", "Against Medical Advice", "Expired", "Absconded")

DISCHARGE_CONDITIONS = ("Stable", "Improved", "Unchanged", "Deteriorated", "Cured")


def is_valid_admission_transition(current: str, target: str) -> bool:
    if current == target:
        return True
    return target in ADMISSION_TRANSITIONS.get(current, ())


