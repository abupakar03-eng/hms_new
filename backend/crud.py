from sqlalchemy.orm import Session
from sqlalchemy import func, or_, cast, String
from datetime import date, datetime
from . import models, schemas
from fastapi import HTTPException

# ----------------- USER CRUD -----------------
def get_user_by_username(db: Session, username: str):
    return db.query(models.User).filter(models.User.username == username).first()

def get_all_users(db: Session):
    return db.query(models.User).all()

def create_user(db: Session, user: schemas.UserCreate, hashed_password: str):
    db_user = models.User(
        username=user.username,
        hashed_password=hashed_password,
        role=user.role
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def update_user_role(db: Session, user_id: int, role: str):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user:
        user.role = role
        db.commit()
        db.refresh(user)
    return user

def delete_user(db: Session, user_id: int):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user:
        db.delete(user)
        db.commit()
    return user

def update_user_password(db: Session, user_id: int, hashed_password: str):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user:
        user.hashed_password = hashed_password
        db.commit()
        db.refresh(user)
    return user

# ----------------- PATIENT CRUD -----------------
def get_patient(db: Session, patient_id: int):
    return db.query(models.Patient).filter(models.Patient.id == patient_id).first()

def get_patients(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Patient).offset(skip).limit(limit).all()

def create_patient(db: Session, patient: schemas.PatientCreate):
    db_patient = models.Patient(
        name=patient.name,
        age=patient.age,
        gender=patient.gender,
        phone=patient.phone,
        address=patient.address,
        aadhaar=patient.aadhaar,
        blood_group=patient.blood_group,
        details=patient.details
    )
    db.add(db_patient)
    db.commit()
    db.refresh(db_patient)
    return db_patient

# ----------------- OP TOKEN CRUD -----------------
def create_op_token(db: Session, token: schemas.OPTokenCreate):
    last_token = db.query(models.OPToken).filter(
        models.OPToken.date == token.date,
        models.OPToken.session == token.session
    ).order_by(models.OPToken.token_number.desc()).first()

    next_number = 1 if not last_token else last_token.token_number + 1

    db_token = models.OPToken(
        patient_id=token.patient_id,
        token_number=next_number,
        session=token.session,
        date=token.date,
        fee=token.fee,
        status="Pending",
        details=token.details
    )
    db.add(db_token)
    db.commit()
    db.refresh(db_token)
    return db_token

def get_op_tokens(db: Session, target_date: date):
    return db.query(models.OPToken).filter(models.OPToken.date == target_date).all()

def update_op_token_status(db: Session, token_id: int, status: str):
    db_token = db.query(models.OPToken).filter(models.OPToken.id == token_id).first()
    if db_token:
        db_token.status = status
        db.commit()
        db.refresh(db_token)
    return db_token

# ----------------- APPOINTMENTS CRUD -----------------
def create_appointment(db: Session, appointment: schemas.AppointmentCreate):
    db_appointment = models.Appointment(
        patient_id=appointment.patient_id,
        doctor_id=appointment.doctor_id,
        appointment_date=appointment.appointment_date,
        time_slot=appointment.time_slot,
        reason=appointment.reason,
        status=appointment.status,
        details=appointment.details
    )
    db.add(db_appointment)
    db.commit()
    db.refresh(db_appointment)
    return db_appointment

def get_appointments(db: Session, target_date: date):
    return db.query(models.Appointment).filter(models.Appointment.appointment_date >= target_date).all()

def update_appointment_status(db: Session, appointment_id: int, status: str):
    db_appointment = db.query(models.Appointment).filter(models.Appointment.id == appointment_id).first()
    if db_appointment:
        db_appointment.status = status
        db.commit()
        db.refresh(db_appointment)
    return db_appointment

# ----------------- CASESHEET CRUD -----------------
def create_casesheet(db: Session, casesheet: schemas.CasesheetCreate):
    db_casesheet = models.Casesheet(
        patient_id=casesheet.patient_id,
        token_id=casesheet.token_id,
        symptoms=casesheet.symptoms,
        diagnosis=casesheet.diagnosis,
        vitals_bp=casesheet.vitals_bp,
        vitals_pulse=casesheet.vitals_pulse,
        vitals_temp=casesheet.vitals_temp,
        vitals_resp=casesheet.vitals_resp,
        prescribed_medicines=[m.dict() for m in casesheet.prescribed_medicines],
        prescribed_labs=casesheet.prescribed_labs
    )
    db.add(db_casesheet)
    
    if casesheet.token_id:
        db_token = db.query(models.OPToken).filter(models.OPToken.id == casesheet.token_id).first()
        if db_token:
            db_token.status = "Completed"
            db_token.is_billed = True

    db.flush()

    # Automatically create Lab Orders
    if casesheet.prescribed_labs:
        for lab_name in casesheet.prescribed_labs:
            test_master = db.query(models.LabTestMaster).filter(models.LabTestMaster.test_name == lab_name).first()
            if test_master:
                db_lab_order = models.LabOrder(
                    patient_id=casesheet.patient_id,
                    doctor_name="Doctor", # Should be from session ideally
                    test_id=test_master.id,
                    status="Pending"
                )
                db.add(db_lab_order)

    db.commit()
    db.refresh(db_casesheet)
    return db_casesheet

def get_casesheets(db: Session, patient_id: int):
    return db.query(models.Casesheet).filter(models.Casesheet.patient_id == patient_id).order_by(models.Casesheet.date.desc()).all()

# ----------------- STOCK / INVENTORY CRUD -----------------
def create_medicine_stock(db: Session, item: schemas.MedicineStockCreate):
    db_item = models.MedicineStock(**item.dict())
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item

def get_medicine_stocks(db: Session):
    return db.query(models.MedicineStock).all()

def update_medicine_quantity(db: Session, transaction: schemas.StockTransactionCreate):
    db_item = db.query(models.MedicineStock).filter(models.MedicineStock.id == transaction.medicine_id).first()
    if not db_item:
        raise HTTPException(status_code=404, detail="Stock item not found")

    if transaction.type == "Stock In":
        db_item.quantity += transaction.quantity
    elif transaction.type == "Stock Out":
        if db_item.quantity < transaction.quantity:
            raise HTTPException(status_code=400, detail=f"Insufficient stock for {db_item.name}. Remaining: {db_item.quantity}")
        db_item.quantity -= transaction.quantity
    
    db_tx = models.StockTransaction(
        medicine_id=transaction.medicine_id,
        type=transaction.type,
        quantity=transaction.quantity,
        notes=transaction.notes,
        details=transaction.details
    )
    db.add(db_tx)
    db.commit()
    db.refresh(db_item)
    return db_item

# ----------------- PHARMACY BILLING CRUD -----------------
def create_pharmacy_bill(db: Session, bill: schemas.PharmacyBillCreate):
    subtotal = 0.0
    bill_items = []
    
    for item in bill.items:
        db_item = db.query(models.MedicineStock).filter(models.MedicineStock.id == item.medicine_id).first()
        if not db_item:
            raise HTTPException(status_code=404, detail=f"Medicine ID {item.medicine_id} not found")
        if db_item.quantity < item.quantity:
            raise HTTPException(status_code=400, detail=f"Insufficient stock for {db_item.name}. Remaining: {db_item.quantity}, Requested: {item.quantity}")
        
        db_item.quantity -= item.quantity
        item_total = item.quantity * db_item.unit_price
        subtotal += item_total
        
        db_tx = models.StockTransaction(
            medicine_id=db_item.id,
            type="Sale",
            quantity=item.quantity,
            notes=f"Sold in Bill"
        )
        db.add(db_tx)
        
        bill_items.append(models.PharmacyBillItem(
            medicine_id=db_item.id,
            medicine_name=db_item.name,
            quantity=item.quantity,
            unit_price=db_item.unit_price,
            total_price=item_total
        ))
        
    discount_amount = (bill.discount / 100.0) * subtotal
    gst_amount = (bill.gst / 100.0) * (subtotal - discount_amount)
    total = subtotal - discount_amount + gst_amount
    
    db_bill = models.PharmacyBill(
        patient_id=bill.patient_id,
        patient_name=bill.patient_name,
        subtotal=subtotal,
        discount=bill.discount,
        gst=bill.gst,
        total=total,
        payment_mode=bill.payment_mode,
        payment_details=bill.payment_details,
        details=bill.details,
        items=bill_items
    )
    
    db.add(db_bill)
    db.commit()
    db.refresh(db_bill)
    return db_bill

def get_pharmacy_bills(db: Session):
    return db.query(models.PharmacyBill).order_by(models.PharmacyBill.bill_date.desc()).all()

# ----------------- LAB BILLING CRUD -----------------
def create_lab_bill(db: Session, bill: schemas.LabBillCreate):
    subtotal = sum(item.price for item in bill.items)
    discount_amount = (bill.discount / 100.0) * subtotal
    gst_amount = (bill.gst / 100.0) * (subtotal - discount_amount)
    total = subtotal - discount_amount + gst_amount

    bill_items = [models.LabBillItem(test_name=item.test_name, price=item.price) for item in bill.items]
    
    db_bill = models.LabBill(
        patient_id=bill.patient_id,
        total=total,
        discount=bill.discount,
        gst=bill.gst,
        status="Pending",
        payment_mode=bill.payment_mode,
        payment_details=bill.payment_details,
        items=bill_items
    )
    db.add(db_bill)
    db.commit()
    db.refresh(db_bill)
    return db_bill

def get_lab_bills(db: Session):
    return db.query(models.LabBill).order_by(models.LabBill.bill_date.desc()).all()

def update_lab_bill_status(db: Session, bill_id: int, status: str):
    db_bill = db.query(models.LabBill).filter(models.LabBill.id == bill_id).first()
    if db_bill:
        db_bill.status = status
        db.commit()
        db.refresh(db_bill)
    return db_bill

# ----------------- IP ADMISSION CRUD -----------------
def create_ip_admission(db: Session, admission: schemas.IPAdmissionCreate):
    db_admission = models.IPAdmission(
        patient_id=admission.patient_id,
        ward_number=admission.ward_number,
        room_number=admission.room_number,
        doctor_in_charge=admission.doctor_in_charge,
        reason_for_admission=admission.reason_for_admission
    )
    db.add(db_admission)
    db.commit()
    db.refresh(db_admission)
    return db_admission

def get_ip_admissions(db: Session, patient_id: int = None):
    query = db.query(models.IPAdmission)
    if patient_id:
        query = query.filter(models.IPAdmission.patient_id == patient_id)
    return query.order_by(models.IPAdmission.admission_date.desc()).all()

def update_ip_admission_status(db: Session, admission_id: int, status: str, discharge_date: datetime = None):
    db_admission = db.query(models.IPAdmission).filter(models.IPAdmission.id == admission_id).first()
    if db_admission:
        db_admission.status = status
        if discharge_date:
            db_admission.discharge_date = discharge_date
        db.commit()
        db.refresh(db_admission)
    return db_admission

# ----------------- LAB REPORT CRUD -----------------
def create_lab_report(db: Session, report: schemas.LabReportCreate):
    db_report = models.LabReport(
        patient_id=report.patient_id,
        test_name=report.test_name,
        result_value=report.result_value,
        normal_range=report.normal_range,
        units=report.units,
        reported_by=report.reported_by,
        remarks=report.remarks,
        results_data=report.results_data
    )
    db.add(db_report)
    db.commit()
    db.refresh(db_report)
    return db_report

def get_lab_reports(db: Session, patient_id: int = None):
    query = db.query(models.LabReport)
    if patient_id:
        query = query.filter(models.LabReport.patient_id == patient_id)
    return query.order_by(models.LabReport.date_conducted.desc()).all()

# ----------------- NEW LAB MANAGEMENT CRUD -----------------
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException

def create_lab_test_master(db: Session, test: schemas.LabTestMasterCreate):
    db_test = models.LabTestMaster(**test.dict())
    db.add(db_test)
    try:
        db.commit()
        db.refresh(db_test)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Test code already exists.")
    return db_test

def get_lab_test_masters(db: Session):
    return db.query(models.LabTestMaster).filter(models.LabTestMaster.is_active == True).all()

def update_lab_test_master(db: Session, test_id: int, test: schemas.LabTestMasterUpdate):
    db_test = db.query(models.LabTestMaster).filter(models.LabTestMaster.id == test_id).first()
    if not db_test:
        return None
    for var, value in vars(test).items():
        if value is not None:
            setattr(db_test, var, value)
    db.commit()
    db.refresh(db_test)
    return db_test

def delete_lab_test_master(db: Session, test_id: int):
    db_test = db.query(models.LabTestMaster).filter(models.LabTestMaster.id == test_id).first()
    if not db_test:
        return None
    db_test.is_active = False
    db.commit()
    return db_test

def create_lab_order(db: Session, order: schemas.LabOrderCreate):
    db_order = models.LabOrder(**order.dict())
    db.add(db_order)
    db.commit()
    db.refresh(db_order)
    return db_order

def get_lab_orders(db: Session, target_date: datetime = None):
    query = db.query(models.LabOrder)
    if target_date:
        query = query.filter(func.date(models.LabOrder.order_date) == target_date.date())
    return query.order_by(models.LabOrder.order_date.desc()).all()

def update_lab_order_status(db: Session, order_id: int, status: str):
    db_order = db.query(models.LabOrder).filter(models.LabOrder.id == order_id).first()
    if db_order:
        db_order.status = status
        db.commit()
        db.refresh(db_order)
    return db_order

def create_lab_sample(db: Session, sample: schemas.LabSampleCreate):
    db_sample = models.LabSample(**sample.dict())
    db.add(db_sample)
    db.commit()
    db.refresh(db_sample)
    
    # Auto update order status
    update_lab_order_status(db, sample.order_id, "Sample Collected")
    
    return db_sample

def get_lab_samples(db: Session):
    return db.query(models.LabSample).order_by(models.LabSample.id.desc()).all()

def update_lab_sample_status(db: Session, sample_id: int, status: str):
    db_sample = db.query(models.LabSample).filter(models.LabSample.id == sample_id).first()
    if db_sample:
        db_sample.status = status
        if status == "Collected":
            db_sample.collection_date = datetime.utcnow()
        db.commit()
        db.refresh(db_sample)
    return db_sample

# ===========================================
# NEW: OP BILL CRUD
# ===========================================
def create_op_bill(db: Session, bill: schemas.OPBillCreate):
    other_total = sum(c.amount for c in bill.other_charges)
    subtotal = bill.consultation_fee + bill.lab_charges + bill.pharmacy_charges + other_total
    discount_amount = (bill.discount / 100.0) * subtotal
    gst_amount = (bill.gst / 100.0) * (subtotal - discount_amount)
    total = subtotal - discount_amount + gst_amount

    db_bill = models.OPBill(
        patient_id=bill.patient_id,
        token_id=bill.token_id,
        doctor_name=bill.doctor_name,
        department=bill.department,
        consultation_fee=bill.consultation_fee,
        lab_charges=bill.lab_charges,
        pharmacy_charges=bill.pharmacy_charges,
        other_charges=[c.dict() for c in bill.other_charges],
        subtotal=subtotal,
        discount=bill.discount,
        gst=bill.gst,
        total=total,
        payment_mode=bill.payment_mode,
        payment_details=bill.payment_details,
        notes=bill.notes
    )
    db.add(db_bill)
    db.commit()
    db.refresh(db_bill)
    return db_bill

def get_op_bills(db: Session, patient_id: int = None):
    query = db.query(models.OPBill)
    if patient_id:
        query = query.filter(models.OPBill.patient_id == patient_id)
    return query.order_by(models.OPBill.bill_date.desc()).all()

# ===========================================
# NEW: IP BILL CRUD
# ===========================================
def create_ip_bill(db: Session, bill: schemas.IPBillCreate):
    room_charges = bill.room_charge_per_day * bill.days_stayed
    other_total = sum(c.amount for c in bill.other_charges)
    subtotal = room_charges + bill.doctor_charges + bill.nursing_charges + bill.pharmacy_charges + bill.lab_charges + other_total
    discount_amount = (bill.discount / 100.0) * subtotal
    gst_amount = (bill.gst / 100.0) * (subtotal - discount_amount)
    total = subtotal - discount_amount + gst_amount

    db_bill = models.IPBill(
        patient_id=bill.patient_id,
        admission_id=bill.admission_id,
        doctor_name=bill.doctor_name,
        room_charge_per_day=bill.room_charge_per_day,
        days_stayed=bill.days_stayed,
        room_charges=room_charges,
        doctor_charges=bill.doctor_charges,
        nursing_charges=bill.nursing_charges,
        pharmacy_charges=bill.pharmacy_charges,
        lab_charges=bill.lab_charges,
        other_charges=[c.dict() for c in bill.other_charges],
        subtotal=subtotal,
        discount=bill.discount,
        gst=bill.gst,
        total=total,
        payment_mode=bill.payment_mode,
        payment_details=bill.payment_details,
        notes=bill.notes
    )
    db.add(db_bill)
    db.commit()
    db.refresh(db_bill)
    return db_bill

def get_ip_bills(db: Session, patient_id: int = None):
    query = db.query(models.IPBill)
    if patient_id:
        query = query.filter(models.IPBill.patient_id == patient_id)
    return query.order_by(models.IPBill.bill_date.desc()).all()

# ===========================================
# NEW: GLOBAL SEARCH
# ===========================================
def global_search(db: Session, query: str):
    results = []
    q = query.strip().lower()

    # Search patients by name, phone, aadhaar
    patients = db.query(models.Patient).filter(
        or_(
            func.lower(models.Patient.name).contains(q),
            models.Patient.phone.contains(query),
            models.Patient.aadhaar.contains(query),
            cast(models.Patient.id, String) == query
        )
    ).limit(10).all()

    for p in patients:
        results.append({
            "type": "patient",
            "id": p.id,
            "patient_id": p.id,
            "patient_name": p.name,
            "detail": f"Age: {p.age}, Gender: {p.gender}, Phone: {p.phone or '-'}",
            "date": p.created_at.strftime("%Y-%m-%d") if p.created_at else None,
            "amount": None
        })

    # Search OP Tokens by token number
    if query.isdigit():
        tokens = db.query(models.OPToken).filter(
            or_(
                models.OPToken.token_number == int(query),
                models.OPToken.id == int(query)
            )
        ).limit(5).all()
        for t in tokens:
            patient = db.query(models.Patient).filter(models.Patient.id == t.patient_id).first()
            results.append({
                "type": "op_token",
                "id": t.id,
                "patient_id": t.patient_id,
                "patient_name": patient.name if patient else "Unknown",
                "detail": f"Token #{t.token_number} | {t.session} | {t.date} | Status: {t.status}",
                "date": str(t.date),
                "amount": t.fee
            })

    # Search OP Bills by bill id
    if query.isdigit():
        op_bills = db.query(models.OPBill).filter(models.OPBill.id == int(query)).limit(5).all()
        for b in op_bills:
            patient = db.query(models.Patient).filter(models.Patient.id == b.patient_id).first()
            results.append({
                "type": "op_bill",
                "id": b.id,
                "patient_id": b.patient_id,
                "patient_name": patient.name if patient else "Unknown",
                "detail": f"OP Bill #{b.id} | Dr: {b.doctor_name or '-'} | {b.payment_mode}",
                "date": b.bill_date.strftime("%Y-%m-%d"),
                "amount": b.total
            })

        # IP Bills
        ip_bills = db.query(models.IPBill).filter(models.IPBill.id == int(query)).limit(5).all()
        for b in ip_bills:
            patient = db.query(models.Patient).filter(models.Patient.id == b.patient_id).first()
            results.append({
                "type": "ip_bill",
                "id": b.id,
                "patient_id": b.patient_id,
                "patient_name": patient.name if patient else "Unknown",
                "detail": f"IP Bill #{b.id} | Dr: {b.doctor_name or '-'} | Days: {b.days_stayed}",
                "date": b.bill_date.strftime("%Y-%m-%d"),
                "amount": b.total
            })

        # Admissions
        admissions = db.query(models.IPAdmission).filter(models.IPAdmission.id == int(query)).limit(5).all()
        for a in admissions:
            patient = db.query(models.Patient).filter(models.Patient.id == a.patient_id).first()
            results.append({
                "type": "admission",
                "id": a.id,
                "patient_id": a.patient_id,
                "patient_name": patient.name if patient else "Unknown",
                "detail": f"Admission #{a.id} | Ward: {a.ward_number} | Status: {a.status}",
                "date": a.admission_date.strftime("%Y-%m-%d"),
                "amount": None
            })

        # Pharmacy Bills
        pharmacy_bills = db.query(models.PharmacyBill).filter(models.PharmacyBill.id == int(query)).limit(5).all()
        for b in pharmacy_bills:
            patient = db.query(models.Patient).filter(models.Patient.id == b.patient_id).first() if b.patient_id else None
            results.append({
                "type": "pharmacy_bill",
                "id": b.id,
                "patient_id": b.patient_id,
                "patient_name": patient.name if patient else (b.patient_name or "Walk-in"),
                "detail": f"Pharmacy Bill #{b.id} | {b.payment_mode}",
                "date": b.bill_date.strftime("%Y-%m-%d"),
                "amount": b.total
            })

        # Lab Bills
        lab_bills = db.query(models.LabBill).filter(models.LabBill.id == int(query)).limit(5).all()
        for b in lab_bills:
            patient = db.query(models.Patient).filter(models.Patient.id == b.patient_id).first()
            results.append({
                "type": "lab_bill",
                "id": b.id,
                "patient_id": b.patient_id,
                "patient_name": patient.name if patient else "Unknown",
                "detail": f"Lab Bill #{b.id} | Status: {b.status}",
                "date": b.bill_date.strftime("%Y-%m-%d"),
                "amount": b.total
            })

    return results

# ===========================================
# NEW: REPORTS CRUD
# ===========================================
def get_daily_report(db: Session, report_date: date):
    start = datetime.combine(report_date, datetime.min.time())
    end = datetime.combine(report_date, datetime.max.time())

    op_revenue = db.query(func.coalesce(func.sum(models.OPBill.total), 0)).filter(
        models.OPBill.bill_date >= start, models.OPBill.bill_date <= end).scalar()
    ip_revenue = db.query(func.coalesce(func.sum(models.IPBill.total), 0)).filter(
        models.IPBill.bill_date >= start, models.IPBill.bill_date <= end).scalar()
    pharmacy_revenue = db.query(func.coalesce(func.sum(models.PharmacyBill.total), 0)).filter(
        models.PharmacyBill.bill_date >= start, models.PharmacyBill.bill_date <= end).scalar()
    lab_revenue = db.query(func.coalesce(func.sum(models.LabBill.total), 0)).filter(
        models.LabBill.bill_date >= start, models.LabBill.bill_date <= end).scalar()

    op_count = db.query(func.count(models.OPBill.id)).filter(
        models.OPBill.bill_date >= start, models.OPBill.bill_date <= end).scalar()
    ip_count = db.query(func.count(models.IPBill.id)).filter(
        models.IPBill.bill_date >= start, models.IPBill.bill_date <= end).scalar()
    ph_count = db.query(func.count(models.PharmacyBill.id)).filter(
        models.PharmacyBill.bill_date >= start, models.PharmacyBill.bill_date <= end).scalar()
    lab_count = db.query(func.count(models.LabBill.id)).filter(
        models.LabBill.bill_date >= start, models.LabBill.bill_date <= end).scalar()

    # Token-based unique patient count
    patient_tokens = db.query(func.count(func.distinct(models.OPToken.patient_id))).filter(
        models.OPToken.date == report_date).scalar()

    return {
        "date": str(report_date),
        "op_revenue": float(op_revenue),
        "ip_revenue": float(ip_revenue),
        "pharmacy_revenue": float(pharmacy_revenue),
        "lab_revenue": float(lab_revenue),
        "total_revenue": float(op_revenue + ip_revenue + pharmacy_revenue + lab_revenue),
        "total_patients": int(patient_tokens),
        "total_bills": int(op_count + ip_count + ph_count + lab_count)
    }

def update_lab_order(db: Session, order_id: int, order_data: schemas.LabOrderUpdate):
    db_order = db.query(models.LabOrder).filter(models.LabOrder.id == order_id).first()
    if not db_order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order_data.status is not None:
        db_order.status = order_data.status
    if order_data.priority is not None:
        db_order.priority = order_data.priority
    if order_data.remarks is not None:
        db_order.remarks = order_data.remarks
    db.commit()
    db.refresh(db_order)
    return db_order

def update_lab_sample(db: Session, sample_id: int, sample_data: schemas.LabSampleUpdate):
    db_sample = db.query(models.LabSample).filter(models.LabSample.id == sample_id).first()
    if not db_sample:
        raise HTTPException(status_code=404, detail="Sample not found")
    
    for var, value in vars(sample_data).items():
        if value is not None:
            setattr(db_sample, var, value)
            
    db.commit()
    db.refresh(db_sample)
    return db_sample
def get_monthly_report(db: Session, year: int, month: int):
    from calendar import monthrange
    from datetime import timedelta
    _, days_in_month = monthrange(year, month)
    
    daily_data = []
    for d in range(1, days_in_month + 1):
        day_date = date(year, month, d)
        report = get_daily_report(db, day_date)
        if report["total_bills"] > 0 or report["total_revenue"] > 0:
            daily_data.append(report)
    
    return daily_data

def get_yearly_report(db: Session, year: int):
    monthly_data = []
    for month in range(1, 13):
        from calendar import monthrange
        _, days_in_month = monthrange(year, month)
        
        start = datetime(year, month, 1)
        end = datetime(year, month, days_in_month, 23, 59, 59)

        op_rev = db.query(func.coalesce(func.sum(models.OPBill.total), 0)).filter(
            models.OPBill.bill_date >= start, models.OPBill.bill_date <= end).scalar()
        ip_rev = db.query(func.coalesce(func.sum(models.IPBill.total), 0)).filter(
            models.IPBill.bill_date >= start, models.IPBill.bill_date <= end).scalar()
        ph_rev = db.query(func.coalesce(func.sum(models.PharmacyBill.total), 0)).filter(
            models.PharmacyBill.bill_date >= start, models.PharmacyBill.bill_date <= end).scalar()
        lab_rev = db.query(func.coalesce(func.sum(models.LabBill.total), 0)).filter(
            models.LabBill.bill_date >= start, models.LabBill.bill_date <= end).scalar()
        
        bill_count = (
            db.query(func.count(models.OPBill.id)).filter(models.OPBill.bill_date >= start, models.OPBill.bill_date <= end).scalar() +
            db.query(func.count(models.IPBill.id)).filter(models.IPBill.bill_date >= start, models.IPBill.bill_date <= end).scalar() +
            db.query(func.count(models.PharmacyBill.id)).filter(models.PharmacyBill.bill_date >= start, models.PharmacyBill.bill_date <= end).scalar() +
            db.query(func.count(models.LabBill.id)).filter(models.LabBill.bill_date >= start, models.LabBill.bill_date <= end).scalar()
        )

        import calendar
        month_name = calendar.month_name[month]
        monthly_data.append({
            "month": f"{month_name} {year}",
            "op_revenue": float(op_rev),
            "ip_revenue": float(ip_rev),
            "pharmacy_revenue": float(ph_rev),
            "lab_revenue": float(lab_rev),
            "total_revenue": float(op_rev + ip_rev + ph_rev + lab_rev),
            "total_bills": int(bill_count)
        })
    
    return monthly_data

def get_revenue_breakdown(db: Session, start_date: date = None, end_date: date = None):
    filters_op = []
    filters_ip = []
    filters_ph = []
    filters_lab = []
    
    if start_date:
        start_dt = datetime.combine(start_date, datetime.min.time())
        filters_op.append(models.OPBill.bill_date >= start_dt)
        filters_ip.append(models.IPBill.bill_date >= start_dt)
        filters_ph.append(models.PharmacyBill.bill_date >= start_dt)
        filters_lab.append(models.LabBill.bill_date >= start_dt)
    if end_date:
        end_dt = datetime.combine(end_date, datetime.max.time())
        filters_op.append(models.OPBill.bill_date <= end_dt)
        filters_ip.append(models.IPBill.bill_date <= end_dt)
        filters_ph.append(models.PharmacyBill.bill_date <= end_dt)
        filters_lab.append(models.LabBill.bill_date <= end_dt)

    op = float(db.query(func.coalesce(func.sum(models.OPBill.total), 0)).filter(*filters_op).scalar())
    ip = float(db.query(func.coalesce(func.sum(models.IPBill.total), 0)).filter(*filters_ip).scalar())
    ph = float(db.query(func.coalesce(func.sum(models.PharmacyBill.total), 0)).filter(*filters_ph).scalar())
    lab = float(db.query(func.coalesce(func.sum(models.LabBill.total), 0)).filter(*filters_lab).scalar())

    return {"op_total": op, "ip_total": ip, "pharmacy_total": ph, "lab_total": lab, "grand_total": op + ip + ph + lab}

def get_doctor_wise_report(db: Session):
    op_data = db.query(
        models.OPBill.doctor_name,
        func.count(models.OPBill.id).label("op_bills"),
        func.coalesce(func.sum(models.OPBill.total), 0).label("op_revenue")
    ).filter(models.OPBill.doctor_name != None).group_by(models.OPBill.doctor_name).all()
    
    ip_data = db.query(
        models.IPBill.doctor_name,
        func.count(models.IPBill.id).label("ip_bills"),
        func.coalesce(func.sum(models.IPBill.total), 0).label("ip_revenue")
    ).filter(models.IPBill.doctor_name != None).group_by(models.IPBill.doctor_name).all()

    doctors = {}
    for row in op_data:
        name = row.doctor_name or "Unknown"
        if name not in doctors:
            doctors[name] = {"doctor_name": name, "op_bills": 0, "ip_bills": 0, "total_revenue": 0.0}
        doctors[name]["op_bills"] += row.op_bills
        doctors[name]["total_revenue"] += float(row.op_revenue)
    
    for row in ip_data:
        name = row.doctor_name or "Unknown"
        if name not in doctors:
            doctors[name] = {"doctor_name": name, "op_bills": 0, "ip_bills": 0, "total_revenue": 0.0}
        doctors[name]["ip_bills"] += row.ip_bills
        doctors[name]["total_revenue"] += float(row.ip_revenue)

    return list(doctors.values())

def get_medicine_sales_report(db: Session):
    data = db.query(
        models.PharmacyBillItem.medicine_name,
        func.sum(models.PharmacyBillItem.quantity).label("total_quantity"),
        func.sum(models.PharmacyBillItem.total_price).label("total_revenue")
    ).group_by(models.PharmacyBillItem.medicine_name).order_by(
        func.sum(models.PharmacyBillItem.total_price).desc()
    ).all()
    
    return [{"medicine_name": row.medicine_name, "total_quantity_sold": int(row.total_quantity), "total_revenue": float(row.total_revenue)} for row in data]

def get_admission_report(db: Session, status: str = None):
    query = db.query(models.IPAdmission)
    if status:
        query = query.filter(models.IPAdmission.status == status)
    return query.order_by(models.IPAdmission.admission_date.desc()).all()

def get_department_wise_report(db: Session):
    data = db.query(
        models.OPBill.department,
        func.count(models.OPBill.id).label("total_bills"),
        func.coalesce(func.sum(models.OPBill.total), 0).label("total_revenue")
    ).filter(models.OPBill.department != None, models.OPBill.department != "").group_by(models.OPBill.department).all()
    
    return [{"department": row.department, "total_bills": row.total_bills, "total_revenue": float(row.total_revenue)} for row in data]

def get_patient_report(db: Session, patient_id: int):
    patient = db.query(models.Patient).filter(models.Patient.id == patient_id).first()
    if not patient:
        return None
    
    op_visits = db.query(models.OPToken).filter(models.OPToken.patient_id == patient_id).count()
    admissions = db.query(models.IPAdmission).filter(models.IPAdmission.patient_id == patient_id).count()
    
    op_revenue = db.query(func.coalesce(func.sum(models.OPBill.total), 0)).filter(models.OPBill.patient_id == patient_id).scalar()
    ip_revenue = db.query(func.coalesce(func.sum(models.IPBill.total), 0)).filter(models.IPBill.patient_id == patient_id).scalar()
    pharmacy_revenue = db.query(func.coalesce(func.sum(models.PharmacyBill.total), 0)).filter(models.PharmacyBill.patient_id == patient_id).scalar()
    lab_revenue = db.query(func.coalesce(func.sum(models.LabBill.total), 0)).filter(models.LabBill.patient_id == patient_id).scalar()

    total_revenue = float(op_revenue) + float(ip_revenue) + float(pharmacy_revenue) + float(lab_revenue)
    
    return {
        "patient": patient,
        "op_visits": op_visits,
        "admissions": admissions,
        "total_revenue": total_revenue,
        "breakdown": {
            "op": float(op_revenue),
            "ip": float(ip_revenue),
            "pharmacy": float(pharmacy_revenue),
            "lab": float(lab_revenue)
        }
    }

# --- Additional CRUD Operations ---

def update_patient(db: Session, patient_id: int, patient_update: schemas.PatientUpdate):
    db_patient = db.query(models.Patient).filter(models.Patient.id == patient_id).first()
    if db_patient:
        update_data = patient_update.dict(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_patient, key, value)
        db.commit()
        db.refresh(db_patient)
    return db_patient

def delete_patient(db: Session, patient_id: int):
    db_patient = db.query(models.Patient).filter(models.Patient.id == patient_id).first()
    if db_patient:
        db.delete(db_patient)
        db.commit()
    return db_patient

def delete_op_token(db: Session, token_id: int):
    db_token = db.query(models.OPToken).filter(models.OPToken.id == token_id).first()
    if db_token:
        db.delete(db_token)
        db.commit()
    return db_token

def delete_appointment(db: Session, appointment_id: int):
    db_app = db.query(models.Appointment).filter(models.Appointment.id == appointment_id).first()
    if db_app:
        db.delete(db_app)
        db.commit()
    return db_app

def get_casesheet(db: Session, casesheet_id: int):
    return db.query(models.Casesheet).filter(models.Casesheet.id == casesheet_id).first()

def update_casesheet(db: Session, casesheet_id: int, casesheet_update: schemas.CasesheetUpdate):
    db_casesheet = db.query(models.Casesheet).filter(models.Casesheet.id == casesheet_id).first()
    if db_casesheet:
        update_data = casesheet_update.dict(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_casesheet, key, value)
        db.commit()
        db.refresh(db_casesheet)
    return db_casesheet

def delete_casesheet(db: Session, casesheet_id: int):
    db_casesheet = db.query(models.Casesheet).filter(models.Casesheet.id == casesheet_id).first()
    if db_casesheet:
        db.delete(db_casesheet)
        db.commit()
    return db_casesheet

def update_medicine_stock(db: Session, stock_id: int, stock_update: schemas.MedicineStockUpdate):
    db_stock = db.query(models.MedicineStock).filter(models.MedicineStock.id == stock_id).first()
    if db_stock:
        update_data = stock_update.dict(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_stock, key, value)
        db.commit()
        db.refresh(db_stock)
    return db_stock

def delete_medicine_stock(db: Session, stock_id: int):
    db_stock = db.query(models.MedicineStock).filter(models.MedicineStock.id == stock_id).first()
    if db_stock:
        db.delete(db_stock)
        db.commit()
    return db_stock

def update_ip_admission(db: Session, admission_id: int, admission_update: schemas.IPAdmissionUpdate):
    db_admission = db.query(models.IPAdmission).filter(models.IPAdmission.id == admission_id).first()
    if db_admission:
        update_data = admission_update.dict(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_admission, key, value)
        db.commit()
        db.refresh(db_admission)
    return db_admission

def delete_ip_admission(db: Session, admission_id: int):
    db_admission = db.query(models.IPAdmission).filter(models.IPAdmission.id == admission_id).first()
    if db_admission:
        db.delete(db_admission)
        db.commit()
    return db_admission

def update_lab_report(db: Session, report_id: int, report_update: schemas.LabReportUpdate):
    db_report = db.query(models.LabReport).filter(models.LabReport.id == report_id).first()
    if db_report:
        update_data = report_update.dict(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_report, key, value)
        db.commit()
        db.refresh(db_report)
    return db_report

def delete_lab_report(db: Session, report_id: int):
    db_report = db.query(models.LabReport).filter(models.LabReport.id == report_id).first()
    if db_report:
        db.delete(db_report)
        db.commit()
    return db_report

def delete_lab_order(db: Session, order_id: int):
    db_order = db.query(models.LabOrder).filter(models.LabOrder.id == order_id).first()
    if db_order:
        db.delete(db_order)
        db.commit()
    return db_order

def delete_lab_sample(db: Session, sample_id: int):
    db_sample = db.query(models.LabSample).filter(models.LabSample.id == sample_id).first()
    if db_sample:
        db.delete(db_sample)
        db.commit()
    return db_sample
