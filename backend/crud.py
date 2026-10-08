"""Data-access layer.

Every function that mutates state raises ``HTTPException`` with a meaningful
status code on invalid input (missing foreign keys, illegal workflow
transitions, insufficient stock) instead of silently writing inconsistent rows.
"""

from datetime import date, datetime, timedelta
from typing import Iterable, List, Optional

from fastapi import HTTPException, status as http_status
from sqlalchemy import String, case, cast, func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from . import audit, constants, lab_utils, models, schemas


def _utcnow() -> datetime:
    return datetime.utcnow()


def _day_bounds(target: date):
    return (
        datetime.combine(target, datetime.min.time()),
        datetime.combine(target, datetime.max.time()),
    )


def _month_bounds(year: int, month: int):
    from calendar import monthrange

    last_day = monthrange(year, month)[1]
    return datetime(year, month, 1), datetime(year, month, last_day, 23, 59, 59, 999999)


def _get_or_404(db: Session, model, obj_id: int, label: str):
    obj = db.query(model).filter(model.id == obj_id).first()
    if obj is None:
        raise HTTPException(status_code=404, detail=f"{label} not found")
    return obj


def _require_patient(db: Session, patient_id: int) -> models.Patient:
    return _get_or_404(db, models.Patient, patient_id, "Patient")


# ============================
# Users
# ============================
def get_user_by_username(db: Session, username: str):
    return db.query(models.User).filter(models.User.username == username).first()


def get_all_users(db: Session):
    return db.query(models.User).order_by(models.User.id).all()


def count_active_admins(db: Session, exclude_user_id: Optional[int] = None) -> int:
    query = db.query(models.User).filter(models.User.role == "Admin", models.User.is_active.is_(True))
    if exclude_user_id is not None:
        query = query.filter(models.User.id != exclude_user_id)
    return query.count()


def create_user(db: Session, user: schemas.UserCreate, hashed_password: str):
    db_user = models.User(username=user.username, hashed_password=hashed_password, role=user.role)
    db.add(db_user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Username already registered")
    db.refresh(db_user)
    return db_user


def update_user_role(db: Session, user_id: int, role: str):
    if role not in constants.ROLES:
        raise HTTPException(status_code=422, detail=f"Unknown role '{role}'. Valid roles: {', '.join(constants.ROLES)}")
    db_user = _get_or_404(db, models.User, user_id, "User")
    # Never allow the system to lose its last administrator.
    if db_user.role == "Admin" and role != "Admin" and count_active_admins(db, exclude_user_id=user_id) == 0:
        raise HTTPException(status_code=400, detail="Cannot remove the last active administrator.")
    db_user.role = role
    db.commit()
    db.refresh(db_user)
    return db_user


def set_user_active(db: Session, user_id: int, is_active: bool):
    db_user = _get_or_404(db, models.User, user_id, "User")
    if not is_active and db_user.role == "Admin" and count_active_admins(db, exclude_user_id=user_id) == 0:
        raise HTTPException(status_code=400, detail="Cannot disable the last active administrator.")
    db_user.is_active = is_active
    db.commit()
    db.refresh(db_user)
    return db_user


def delete_user(db: Session, user_id: int, acting_user_id: Optional[int] = None):
    db_user = _get_or_404(db, models.User, user_id, "User")
    if acting_user_id is not None and db_user.id == acting_user_id:
        raise HTTPException(status_code=400, detail="You cannot delete your own account.")
    if db_user.role == "Admin" and count_active_admins(db, exclude_user_id=user_id) == 0:
        raise HTTPException(status_code=400, detail="Cannot delete the last active administrator.")
    db.delete(db_user)
    db.commit()
    return db_user


def update_user_password(db: Session, user_id: int, hashed_password: str):
    db_user = _get_or_404(db, models.User, user_id, "User")
    db_user.hashed_password = hashed_password
    db_user.password_changed_at = _utcnow()
    db.commit()
    db.refresh(db_user)
    return db_user


def change_own_password(db: Session, user: models.User, current_password: str, new_password: str, hasher, verifier):
    if not verifier(current_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect.")
    user.hashed_password = hasher(new_password)
    user.password_changed_at = _utcnow()
    db.commit()
    db.refresh(user)
    return user


# ============================
# Patients
# ============================
def get_patient(db: Session, patient_id: int):
    return db.query(models.Patient).filter(models.Patient.id == patient_id).first()


def get_patients(db: Session, skip: int = 0, limit: int = 100, search: Optional[str] = None):
    query = db.query(models.Patient)
    if search:
        term = f"%{search.strip().lower()}%"
        query = query.filter(
            or_(
                func.lower(models.Patient.name).like(term),
                models.Patient.phone.like(term),
                models.Patient.aadhaar.like(term),
            )
        )
    return query.order_by(models.Patient.id.desc()).offset(skip).limit(limit).all()


def create_patient(db: Session, patient: schemas.PatientCreate):
    db_patient = models.Patient(
        name=patient.name,
        age=patient.age,
        gender=patient.gender,
        phone=patient.phone,
        address=patient.address,
        aadhaar=patient.aadhaar,
        blood_group=patient.blood_group,
        details=patient.details or {},
    )
    db.add(db_patient)
    db.commit()
    db.refresh(db_patient)
    return db_patient


def update_patient(db: Session, patient_id: int, patient_update: schemas.PatientUpdate):
    db_patient = _get_or_404(db, models.Patient, patient_id, "Patient")
    for key, value in patient_update.model_dump(exclude_unset=True).items():
        setattr(db_patient, key, value)
    db.commit()
    db.refresh(db_patient)
    return db_patient


def delete_patient(db: Session, patient_id: int):
    db_patient = _get_or_404(db, models.Patient, patient_id, "Patient")
    db.delete(db_patient)
    db.commit()
    return db_patient


def patient_has_records(db: Session, patient_id: int) -> bool:
    checks = (
        (models.OPToken, models.OPToken.patient_id),
        (models.Casesheet, models.Casesheet.patient_id),
        (models.LabOrder, models.LabOrder.patient_id),
        (models.LabReport, models.LabReport.patient_id),
        (models.LabBill, models.LabBill.patient_id),
        (models.OPBill, models.OPBill.patient_id),
        (models.IPBill, models.IPBill.patient_id),
        (models.IPAdmission, models.IPAdmission.patient_id),
    )
    for model, column in checks:
        if db.query(model.id).filter(column == patient_id).first():
            return True
    return False


# ============================
# OP Tokens
# ============================
def create_op_token(db: Session, token: schemas.OPTokenCreate):
    _require_patient(db, token.patient_id)

    last_token = (
        db.query(models.OPToken)
        .filter(models.OPToken.date == token.date, models.OPToken.session == token.session)
        .order_by(models.OPToken.token_number.desc())
        .first()
    )
    next_number = 1 if not last_token else last_token.token_number + 1

    db_token = models.OPToken(
        patient_id=token.patient_id,
        token_number=next_number,
        session=token.session,
        date=token.date,
        fee=token.fee,
        status="Pending",
        doctor_id=token.doctor_id,
        doctor_name=token.doctor_name,
        department=token.department,
        details=token.details or {},
    )
    db.add(db_token)
    db.commit()
    db.refresh(db_token)
    return db_token


def get_op_tokens(db: Session, target_date: date, session: Optional[str] = None):
    query = db.query(models.OPToken).filter(models.OPToken.date == target_date)
    if session:
        query = query.filter(models.OPToken.session == session)
    return query.order_by(models.OPToken.token_number).all()


def get_op_token(db: Session, token_id: int):
    return db.query(models.OPToken).filter(models.OPToken.id == token_id).first()


def update_op_token(db: Session, token_id: int, payload: schemas.OPTokenUpdate):
    db_token = _get_or_404(db, models.OPToken, token_id, "Token")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(db_token, key, value)
    db.commit()
    db.refresh(db_token)
    return db_token


def update_op_token_status(db: Session, token_id: int, status: str):
    if status not in constants.OP_TOKEN_STATUSES:
        raise HTTPException(
            status_code=422, detail=f"Invalid token status. Valid: {', '.join(constants.OP_TOKEN_STATUSES)}"
        )
    db_token = _get_or_404(db, models.OPToken, token_id, "Token")
    db_token.status = status
    db.commit()
    db.refresh(db_token)
    return db_token


def delete_op_token(db: Session, token_id: int):
    db_token = _get_or_404(db, models.OPToken, token_id, "Token")
    db.delete(db_token)
    db.commit()
    return db_token


# ============================
# Appointments
# ============================
def _assert_slot_free(
    db: Session,
    patient_id: int,
    doctor_id: Optional[int],
    appointment_date,
    time_slot: Optional[str],
    exclude_id: Optional[int] = None,
) -> None:
    """Reject a booking that clashes with the doctor's or the patient's active slots.

    The portal already enforced this; staff bookings did not, so the front desk
    could give one doctor two patients in the same slot.
    """
    if not appointment_date or not time_slot:
        return
    active = db.query(models.Appointment).filter(
        models.Appointment.appointment_date == appointment_date,
        models.Appointment.time_slot == time_slot,
        models.Appointment.status.notin_(("Cancelled", "Completed")),
    )
    if exclude_id is not None:
        active = active.filter(models.Appointment.id != exclude_id)
    if doctor_id is not None and active.filter(models.Appointment.doctor_id == doctor_id).first():
        raise HTTPException(status_code=409, detail="The doctor already has an appointment in that slot.")
    if active.filter(models.Appointment.patient_id == patient_id).first():
        raise HTTPException(status_code=409, detail="The patient already has an appointment in that slot.")


def create_appointment(db: Session, appointment: schemas.AppointmentCreate):
    _require_patient(db, appointment.patient_id)
    if appointment.doctor_id is not None:
        _get_or_404(db, models.User, appointment.doctor_id, "Doctor")
    _assert_slot_free(
        db, appointment.patient_id, appointment.doctor_id, appointment.appointment_date, appointment.time_slot
    )
    db_appointment = models.Appointment(**appointment.model_dump())
    db.add(db_appointment)
    db.commit()
    db.refresh(db_appointment)
    return db_appointment


def get_appointments(db: Session, target_date: Optional[date] = None, include_upcoming: bool = False):
    """Return appointments for ``target_date``.

    The previous implementation filtered ``>= target_date``, so "today's
    appointments" silently included every future booking.
    """
    query = db.query(models.Appointment)
    if target_date:
        query = query.filter(models.Appointment.appointment_date == target_date) if not include_upcoming else query.filter(
            models.Appointment.appointment_date >= target_date
        )
    return query.order_by(models.Appointment.appointment_date, models.Appointment.time_slot).all()


def update_appointment(db: Session, appointment_id: int, payload: schemas.AppointmentUpdate):
    db_appointment = _get_or_404(db, models.Appointment, appointment_id, "Appointment")
    data = payload.model_dump(exclude_unset=True)
    if {"appointment_date", "time_slot", "doctor_id", "patient_id"} & data.keys():
        _assert_slot_free(
            db,
            data.get("patient_id", db_appointment.patient_id),
            data.get("doctor_id", db_appointment.doctor_id),
            data.get("appointment_date", db_appointment.appointment_date),
            data.get("time_slot", db_appointment.time_slot),
            exclude_id=db_appointment.id,
        )
    for key, value in data.items():
        setattr(db_appointment, key, value)
    db.commit()
    db.refresh(db_appointment)
    return db_appointment


def update_appointment_status(db: Session, appointment_id: int, status: str):
    if status not in constants.APPOINTMENT_STATUSES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid appointment status. Valid: {', '.join(constants.APPOINTMENT_STATUSES)}",
        )
    db_appointment = _get_or_404(db, models.Appointment, appointment_id, "Appointment")
    db_appointment.status = status
    db.commit()
    db.refresh(db_appointment)
    return db_appointment


def delete_appointment(db: Session, appointment_id: int):
    db_appointment = _get_or_404(db, models.Appointment, appointment_id, "Appointment")
    db.delete(db_appointment)
    db.commit()
    return db_appointment


# ============================
# Casesheets
# ============================
def create_casesheet(db: Session, casesheet: schemas.CasesheetCreate):
    _require_patient(db, casesheet.patient_id)
    if casesheet.token_id is not None:
        token = _get_or_404(db, models.OPToken, casesheet.token_id, "Token")
        if token.patient_id != casesheet.patient_id:
            raise HTTPException(status_code=422, detail="That OP token belongs to a different patient.")

    payload = casesheet.model_dump(exclude={"auto_order_labs"})

    db_casesheet = models.Casesheet(**payload)
    db.add(db_casesheet)

    if casesheet.token_id:
        db_token = db.query(models.OPToken).filter(models.OPToken.id == casesheet.token_id).first()
        if db_token:
            db_token.status = "Completed"
            # ``is_billed`` is set by the billing module once a bill actually
            # exists; setting it here marked tokens as billed with no bill.

    db.flush()

    created_orders = []
    if casesheet.auto_order_labs and casesheet.prescribed_labs:
        created_orders = _create_orders_for_test_names(
            db,
            patient_id=casesheet.patient_id,
            test_names=casesheet.prescribed_labs,
            doctor_name=casesheet.doctor_name,
            priority="Routine",
        )

    db.commit()
    db.refresh(db_casesheet)
    return db_casesheet, created_orders


def _create_orders_for_test_names(
    db: Session, patient_id: int, test_names: Iterable[str], doctor_name: Optional[str], priority: str
) -> List[models.LabOrder]:
    """Create lab orders for prescribed test names, expanding panels.

    Panels are expanded into their member tests so the lab worklist shows one row
    per measurable test, while the billing side keeps the panel price.
    """
    created: List[models.LabOrder] = []
    for raw_name in test_names:
        name = (raw_name or "").strip()
        if not name:
            continue
        test = (
            db.query(models.LabTestMaster)
            .filter(func.lower(models.LabTestMaster.test_name) == name.lower())
            .first()
        )
        if not test:
            # Also allow prescribing by code, e.g. "CBC".
            test = (
                db.query(models.LabTestMaster)
                .filter(func.lower(models.LabTestMaster.test_code) == name.lower())
                .first()
            )
        if not test:
            continue
        created.extend(
            _create_orders_for_test_ids(
                db,
                patient_id=patient_id,
                test_ids=[test.id],
                doctor_name=doctor_name,
                priority=priority,
                panel_id=test.id if test.is_panel else None,
            )
        )
    return created


def get_casesheets(db: Session, patient_id: int):
    return (
        db.query(models.Casesheet)
        .filter(models.Casesheet.patient_id == patient_id)
        .order_by(models.Casesheet.date.desc(), models.Casesheet.id.desc())
        .all()
    )


def get_casesheet(db: Session, casesheet_id: int):
    return db.query(models.Casesheet).filter(models.Casesheet.id == casesheet_id).first()


def update_casesheet(db: Session, casesheet_id: int, casesheet_update: schemas.CasesheetUpdate):
    db_casesheet = _get_or_404(db, models.Casesheet, casesheet_id, "Casesheet")
    data = casesheet_update.model_dump(exclude_unset=True)
    if "prescribed_medicines" in data and data["prescribed_medicines"] is not None:
        data["prescribed_medicines"] = [
            m if isinstance(m, dict) else m.model_dump() for m in data["prescribed_medicines"]
        ]
    for key, value in data.items():
        setattr(db_casesheet, key, value)
    db.commit()
    db.refresh(db_casesheet)
    return db_casesheet


def delete_casesheet(db: Session, casesheet_id: int):
    db_casesheet = _get_or_404(db, models.Casesheet, casesheet_id, "Casesheet")
    db.delete(db_casesheet)
    db.commit()
    return db_casesheet


# ============================
# Inventory
# ============================
def create_medicine_stock(db: Session, item: schemas.MedicineStockCreate):
    db_item = models.MedicineStock(**item.model_dump())
    db.add(db_item)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"A stock item named '{item.name}' already exists.")
    db.refresh(db_item)
    return db_item


def get_medicine_stocks(db: Session, category: Optional[str] = None):
    query = db.query(models.MedicineStock)
    if category:
        query = query.filter(models.MedicineStock.category == category)
    return query.order_by(models.MedicineStock.name).all()


def update_medicine_quantity(db: Session, transaction: schemas.StockTransactionCreate):
    db_item = _get_or_404(db, models.MedicineStock, transaction.medicine_id, "Stock item")

    if transaction.type in ("Stock In", "Return"):
        db_item.quantity += transaction.quantity
    elif transaction.type in ("Stock Out", "Sale"):
        if db_item.quantity < transaction.quantity:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient stock for {db_item.name}. Remaining: {db_item.quantity}",
            )
        db_item.quantity -= transaction.quantity
    elif transaction.type == "Adjustment":
        db_item.quantity = transaction.quantity

    db.add(
        models.StockTransaction(
            medicine_id=transaction.medicine_id,
            type=transaction.type,
            quantity=transaction.quantity,
            notes=transaction.notes,
            details=transaction.details or {},
        )
    )
    db.commit()
    db.refresh(db_item)
    return db_item


def update_medicine_stock(db: Session, stock_id: int, stock_update: schemas.MedicineStockUpdate):
    db_stock = _get_or_404(db, models.MedicineStock, stock_id, "Medicine stock")
    for key, value in stock_update.model_dump(exclude_unset=True).items():
        setattr(db_stock, key, value)
    db.commit()
    db.refresh(db_stock)
    return db_stock


def delete_medicine_stock(db: Session, stock_id: int):
    db_stock = _get_or_404(db, models.MedicineStock, stock_id, "Medicine stock")
    db.query(models.PharmacyBillItem).filter(models.PharmacyBillItem.medicine_id == stock_id).update(
        {models.PharmacyBillItem.medicine_id: None}, synchronize_session=False
    )
    db.delete(db_stock)
    db.commit()
    return db_stock


def low_stock_items(db: Session):
    return (
        db.query(models.MedicineStock)
        .filter(models.MedicineStock.quantity <= models.MedicineStock.min_stock_level)
        .all()
    )


def expiring_items(db: Session, within_days: int = 90):
    cutoff = (datetime.utcnow() + timedelta(days=within_days)).date()
    return (
        db.query(models.MedicineStock)
        .filter(models.MedicineStock.expiry_date.isnot(None), models.MedicineStock.expiry_date <= cutoff)
        .order_by(models.MedicineStock.expiry_date)
        .all()
    )


# ============================
# Pharmacy billing
# ============================
def _apply_percentage_totals(subtotal: float, discount_pct: float, gst_pct: float):
    discount_amount = (discount_pct / 100.0) * subtotal
    taxable = subtotal - discount_amount
    gst_amount = (gst_pct / 100.0) * taxable
    return subtotal, discount_amount, gst_amount, taxable + gst_amount


def create_pharmacy_bill(db: Session, bill: schemas.PharmacyBillCreate):
    if bill.patient_id is not None:
        _require_patient(db, bill.patient_id)
    if bill.patient_id is None and not (bill.patient_name or "").strip():
        raise HTTPException(status_code=422, detail="Provide either a registered patient or a walk-in patient name.")

    subtotal = 0.0
    bill_items = []

    for item in bill.items:
        db_item = _get_or_404(db, models.MedicineStock, item.medicine_id, "Medicine")
        if db_item.expiry_date is not None and db_item.expiry_date < date.today():
            raise HTTPException(
                status_code=409,
                detail=f"{db_item.name} expired on {db_item.expiry_date.isoformat()} and cannot be dispensed.",
            )
        if db_item.quantity < item.quantity:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Insufficient stock for {db_item.name}. "
                    f"Remaining: {db_item.quantity}, Requested: {item.quantity}"
                ),
            )
        db_item.quantity -= item.quantity
        item_total = round(item.quantity * db_item.unit_price, 2)
        subtotal += item_total

        db.add(
            models.StockTransaction(
                medicine_id=db_item.id, type="Sale", quantity=item.quantity, notes="Sold via pharmacy bill"
            )
        )
        bill_items.append(
            models.PharmacyBillItem(
                medicine_id=db_item.id,
                medicine_name=db_item.name,
                quantity=item.quantity,
                unit_price=db_item.unit_price,
                total_price=item_total,
            )
        )

    subtotal, _, _, total = _apply_percentage_totals(subtotal, bill.discount, bill.gst)

    db_bill = models.PharmacyBill(
        patient_id=bill.patient_id,
        patient_name=bill.patient_name,
        subtotal=round(subtotal, 2),
        discount=bill.discount,
        gst=bill.gst,
        total=round(total, 2),
        payment_mode=bill.payment_mode,
        payment_details=bill.payment_details,
        details=bill.details or {},
        items=bill_items,
    )
    db.add(db_bill)
    db.commit()
    db.refresh(db_bill)
    return db_bill


def get_pharmacy_bills(db: Session, skip: int = 0, limit: int = 500):
    return (
        db.query(models.PharmacyBill)
        .order_by(models.PharmacyBill.bill_date.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


# ============================
# Lab test master (tests + panels + parameters)
# ============================
def get_lab_test_masters(db: Session, include_inactive: bool = False):
    query = db.query(models.LabTestMaster)
    if not include_inactive:
        query = query.filter(models.LabTestMaster.is_active.is_(True))
    return query.order_by(models.LabTestMaster.test_name).all()


def get_lab_test(db: Session, test_id: int) -> models.LabTestMaster:
    return _get_or_404(db, models.LabTestMaster, test_id, "Lab test")


def _replace_parameters(db: Session, test: models.LabTestMaster, parameters: List[schemas.LabTestParameterCreate]):
    test.parameters.clear()
    db.flush()
    for index, param in enumerate(parameters or []):
        data = param.model_dump() if hasattr(param, "model_dump") else dict(param)
        data["display_order"] = data.get("display_order") or index
        test.parameters.append(models.LabTestParameter(**data))


def _replace_panel_items(db: Session, panel: models.LabTestMaster, test_ids: List[int]):
    panel.panel_items.clear()
    db.flush()
    for index, test_id in enumerate(test_ids or []):
        if test_id == panel.id:
            raise HTTPException(status_code=422, detail="A panel cannot contain itself.")
        _get_or_404(db, models.LabTestMaster, test_id, "Panel member test")
        panel.panel_items.append(models.LabPanelItem(panel_id=panel.id, test_id=test_id, display_order=index))


def create_lab_test_master(db: Session, test: schemas.LabTestMasterCreate):
    data = test.model_dump(exclude={"parameters", "panel_test_ids"})
    try:
        db_test = models.LabTestMaster(**data)
        db.add(db_test)
        db.flush()

        _replace_parameters(db, db_test, test.parameters)
        if test.is_panel:
            _replace_panel_items(db, db_test, test.panel_test_ids)

        db.commit()
    except IntegrityError:
        # Covers the unique test_code constraint, which can trip on flush() as
        # well as on commit() -- the previous code only guarded commit().
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Test code '{test.test_code}' already exists.")
    db.refresh(db_test)
    return db_test


def update_lab_test_master(db: Session, test_id: int, test: schemas.LabTestMasterUpdate):
    db_test = _get_or_404(db, models.LabTestMaster, test_id, "Lab test")
    data = test.model_dump(exclude_unset=True, exclude={"parameters", "panel_test_ids"})
    try:
        for key, value in data.items():
            setattr(db_test, key, value)

        if test.parameters is not None:
            _replace_parameters(db, db_test, test.parameters)
        if test.panel_test_ids is not None:
            _replace_panel_items(db, db_test, test.panel_test_ids)

        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Test code '{data.get('test_code')}' already exists.")
    db.refresh(db_test)
    return db_test


def set_lab_test_active(db: Session, test_id: int, is_active: bool):
    db_test = _get_or_404(db, models.LabTestMaster, test_id, "Lab test")
    db_test.is_active = is_active
    db.commit()
    db.refresh(db_test)
    return db_test


def delete_lab_test_master(db: Session, test_id: int):
    """Soft delete: the test is referenced by historical orders and reports."""
    db_test = _get_or_404(db, models.LabTestMaster, test_id, "Lab test")
    db_test.is_active = False
    db.commit()
    return db_test


# ============================
# Lab orders
# ============================
def _expand_test_ids(db: Session, test_ids: Iterable[int]):
    """Expand panels into their members, preserving the originating panel id.

    Returns a list of ``(test_id, panel_id, panel_price)`` tuples.
    """
    expanded = []
    for test_id in test_ids:
        test = _get_or_404(db, models.LabTestMaster, test_id, "Lab test")
        if test.is_panel:
            members = [item.test_id for item in sorted(test.panel_items, key=lambda i: i.display_order)]
            if not members:
                raise HTTPException(status_code=422, detail=f"Panel '{test.test_name}' has no member tests.")
            for member_id in members:
                expanded.append((member_id, test.id, test.price))
        else:
            expanded.append((test.id, None, test.price))
    return expanded


def _create_orders_for_test_ids(
    db: Session,
    patient_id: int,
    test_ids: List[int],
    doctor_name: Optional[str],
    priority: str,
    panel_id: Optional[int] = None,
    remarks: Optional[str] = None,
) -> List[models.LabOrder]:
    _require_patient(db, patient_id)
    if priority not in constants.LAB_PRIORITIES:
        raise HTTPException(status_code=422, detail=f"Invalid priority. Valid: {', '.join(constants.LAB_PRIORITIES)}")

    now = _utcnow()
    orders: List[models.LabOrder] = []
    skip_ids = set()
    for test_id, expanded_panel_id, _price in _expand_test_ids(db, test_ids):
        if test_id in skip_ids:
            continue
        skip_ids.add(test_id)
        test = db.query(models.LabTestMaster).filter(models.LabTestMaster.id == test_id).first()
        due = now + timedelta(hours=test.tat_hours if test and test.tat_hours else 24)
        order = models.LabOrder(
            patient_id=patient_id,
            doctor_name=doctor_name,
            test_id=test_id,
            panel_id=panel_id or expanded_panel_id,
            status="Pending",
            priority=priority,
            tat_hours=test.tat_hours if test else 24,
            due_at=due,
            remarks=remarks,
        )
        db.add(order)
        orders.append(order)
    db.flush()
    return orders


def create_lab_order(db: Session, order: schemas.LabOrderCreate):
    orders = _create_orders_for_test_ids(
        db,
        patient_id=order.patient_id,
        test_ids=[order.test_id],
        doctor_name=order.doctor_name,
        priority=order.priority,
        remarks=order.remarks,
    )
    db.commit()
    db.refresh(orders[0])
    return orders[0]


def create_lab_orders_bulk(db: Session, payload: schemas.LabOrderBulkCreate):
    orders = _create_orders_for_test_ids(
        db,
        patient_id=payload.patient_id,
        test_ids=payload.test_ids,
        doctor_name=payload.doctor_name,
        priority=payload.priority,
        panel_id=payload.panel_id,
        remarks=payload.remarks,
    )
    db.commit()
    for order in orders:
        db.refresh(order)
    return orders


def get_lab_orders(
    db: Session,
    target_date: Optional[date] = None,
    patient_id: Optional[int] = None,
    order_status: Optional[str] = None,
    priority: Optional[str] = None,
    overdue_only: bool = False,
):
    query = db.query(models.LabOrder)
    if target_date:
        # ``target_date`` is a ``date``; the previous code called ``.date()`` on it
        # and raised AttributeError -> HTTP 500.
        start, end = _day_bounds(target_date)
        query = query.filter(models.LabOrder.order_date >= start, models.LabOrder.order_date <= end)
    if patient_id:
        query = query.filter(models.LabOrder.patient_id == patient_id)
    if order_status:
        query = query.filter(models.LabOrder.status == order_status)
    if priority:
        query = query.filter(models.LabOrder.priority == priority)
    if overdue_only:
        query = query.filter(
            models.LabOrder.due_at.isnot(None),
            models.LabOrder.due_at < _utcnow(),
            models.LabOrder.status.notin_(("Verified", "Cancelled")),
        )
    return (
        query.options(
            joinedload(models.LabOrder.test).joinedload(models.LabTestMaster.parameters),
            joinedload(models.LabOrder.patient),
        )
        .order_by(models.LabOrder.order_date.desc())
        .all()
    )


def get_lab_order(db: Session, order_id: int) -> models.LabOrder:
    return _get_or_404(db, models.LabOrder, order_id, "Lab order")


def update_lab_order_status(db: Session, order_id: int, status: str):
    db_order = _get_or_404(db, models.LabOrder, order_id, "Lab order")
    if status not in constants.LAB_ORDER_STATUSES:
        raise HTTPException(
            status_code=422, detail=f"Invalid lab order status. Valid: {', '.join(constants.LAB_ORDER_STATUSES)}"
        )
    if not constants.is_valid_transition(db_order.status, status):
        raise HTTPException(
            status_code=409,
            detail=f"Illegal status transition {db_order.status} -> {status}.",
        )
    if status == "Verified" and not db_order.reports:
        raise HTTPException(
            status_code=409,
            detail="Cannot verify an order that has no result. Enter and save results first.",
        )
    db_order.status = status
    if status == "Sample Collected" and not db_order.sample_collected_at:
        db_order.sample_collected_at = _utcnow()
    if status == "Verified":
        db_order.verified_at = _utcnow()
    db.commit()
    db.refresh(db_order)
    return db_order


def update_lab_order(db: Session, order_id: int, order_data: schemas.LabOrderUpdate):
    db_order = _get_or_404(db, models.LabOrder, order_id, "Lab order")
    data = order_data.model_dump(exclude_unset=True)

    if "status" in data and data["status"] and data["status"] != db_order.status:
        if not constants.is_valid_transition(db_order.status, data["status"]):
            raise HTTPException(
                status_code=409, detail=f"Illegal status transition {db_order.status} -> {data['status']}."
            )
        if data["status"] == "Sample Collected" and not db_order.sample_collected_at:
            db_order.sample_collected_at = _utcnow()
        if data["status"] == "Verified":
            db_order.verified_at = _utcnow()
        if data["status"] == "Verified" and not db_order.reports:
            raise HTTPException(
                status_code=409,
                detail="Cannot verify an order that has no result. Enter and save results first.",
            )

    for key, value in data.items():
        setattr(db_order, key, value)
    db.commit()
    db.refresh(db_order)
    return db_order


def delete_lab_order(db: Session, order_id: int):
    db_order = _get_or_404(db, models.LabOrder, order_id, "Lab order")
    if db_order.reports:
        raise HTTPException(
            status_code=409, detail="Cannot delete an order that already has a reported result."
        )
    db.delete(db_order)
    db.commit()
    return db_order


def submit_lab_results(db: Session, order_id: int, payload: schemas.LabResultSubmit, actor: str):
    """Persist result rows for an order, auto-flag them and optionally verify."""
    db_order = _get_or_404(db, models.LabOrder, order_id, "Lab order")
    if db_order.status in constants.LAB_ORDER_LOCKED_STATUSES:
        raise HTTPException(status_code=409, detail=f"Order is {db_order.status} and can no longer be edited.")

    test = db.query(models.LabTestMaster).filter(models.LabTestMaster.id == db_order.test_id).first()
    # Critical limits live on the parameter definition, so look them up by name to
    # turn "out of range" into "critically out of range".
    parameter_limits = {
        p.name.strip().lower(): (p.critical_low, p.critical_high)
        for p in (test.parameters if test else [])
    }

    rows = []
    any_abnormal = False
    for row in payload.results:
        data = row.model_dump()
        if not (data.get("parameter") or "").strip():
            raise HTTPException(status_code=422, detail="Each result row needs a parameter name.")

        # Recompute the flag server-side; never trust the client's flag.
        critical_low, critical_high = parameter_limits.get(data["parameter"].strip().lower(), (None, None))
        data["flag"] = lab_utils.compute_flag(
            data.get("result"),
            data.get("range") or (test.reference_range if test else None),
            critical_low,
            critical_high,
        )
        if lab_utils.is_abnormal(data["flag"]):
            any_abnormal = True
        rows.append(data)

    if not rows:
        raise HTTPException(status_code=422, detail="At least one result row is required.")

    report = (
        db.query(models.LabReport)
        .filter(models.LabReport.order_id == db_order.id)
        .order_by(models.LabReport.id.desc())
        .first()
    )
    target_status = "Verified" if payload.verify else "Draft"

    if report is None:
        report = models.LabReport(
            patient_id=db_order.patient_id,
            order_id=db_order.id,
            test_id=db_order.test_id,
            test_name=test.test_name if test else "Unknown",
        )
        db.add(report)

    report.results_data = rows
    report.result_value = ", ".join(f"{r['parameter']}: {r.get('result') or '-'}" for r in rows)[:500]
    report.normal_range = rows[0].get("range")
    report.units = rows[0].get("unit")
    report.reported_by = report.reported_by or actor
    report.status = target_status
    report.is_abnormal = any_abnormal
    report.interpretation = payload.interpretation
    report.date_conducted = _utcnow()
    if payload.verify:
        report.verified_by = actor
        report.verified_at = _utcnow()
    db.add(report)

    db_order.result_entered_at = _utcnow()
    db_order.interpretation = payload.interpretation
    if payload.verify:
        db_order.status = "Verified"
        db_order.verified_by = actor
        db_order.verified_at = _utcnow()
    else:
        db_order.status = "Testing"

    db.commit()
    db.refresh(report)
    db.refresh(db_order)
    return report


# ============================
# Lab samples
# ============================
def create_lab_sample(db: Session, sample: schemas.LabSampleCreate):
    order = _get_or_404(db, models.LabOrder, sample.order_id, "Lab order")
    if sample.status not in constants.LAB_SAMPLE_STATUSES:
        raise HTTPException(
            status_code=422, detail=f"Invalid sample status. Valid: {', '.join(constants.LAB_SAMPLE_STATUSES)}"
        )

    data = sample.model_dump()
    data["barcode"] = data.get("barcode") or lab_utils.generate_barcode(order.id, data.get("sample_type"))
    # The collection timestamp was previously only set by the separate status
    # endpoint, so samples created directly as "Collected" always had a NULL
    # collection date.
    if data["status"] in ("Collected", "Received"):
        data["collection_date"] = _utcnow()
    if data["status"] == "Received":
        data["received_at"] = _utcnow()

    db_sample = models.LabSample(**data)
    db.add(db_sample)
    db.flush()

    if data["status"] in ("Collected", "Received") and constants.is_valid_transition(
        order.status, "Sample Collected"
    ):
        order.status = "Sample Collected"
        order.sample_collected_at = order.sample_collected_at or _utcnow()

    db.commit()
    db.refresh(db_sample)
    return db_sample


def get_lab_samples(db: Session, order_id: Optional[int] = None, sample_status: Optional[str] = None):
    query = db.query(models.LabSample)
    if order_id:
        query = query.filter(models.LabSample.order_id == order_id)
    if sample_status:
        query = query.filter(models.LabSample.status == sample_status)
    return query.order_by(models.LabSample.id.desc()).all()


def update_lab_sample_status(db: Session, sample_id: int, status: str):
    if status not in constants.LAB_SAMPLE_STATUSES:
        raise HTTPException(
            status_code=422, detail=f"Invalid sample status. Valid: {', '.join(constants.LAB_SAMPLE_STATUSES)}"
        )
    db_sample = _get_or_404(db, models.LabSample, sample_id, "Lab sample")
    db_sample.status = status
    if status in ("Collected", "Received") and not db_sample.collection_date:
        db_sample.collection_date = _utcnow()
    if status == "Received":
        db_sample.received_at = _utcnow()
    if status == "Rejected" and not db_sample.rejection_reason:
        db_sample.rejection_reason = "Not specified"
    db.commit()
    db.refresh(db_sample)
    return db_sample


def update_lab_sample(db: Session, sample_id: int, sample_data: schemas.LabSampleUpdate):
    db_sample = _get_or_404(db, models.LabSample, sample_id, "Lab sample")
    data = sample_data.model_dump(exclude_unset=True)
    if data.get("status") in ("Collected", "Received") and not db_sample.collection_date:
        db_sample.collection_date = _utcnow()
    if data.get("status") == "Received":
        db_sample.received_at = _utcnow()
    for key, value in data.items():
        setattr(db_sample, key, value)
    db.commit()
    db.refresh(db_sample)
    return db_sample


def delete_lab_sample(db: Session, sample_id: int):
    db_sample = _get_or_404(db, models.LabSample, sample_id, "Lab sample")
    db.delete(db_sample)
    db.commit()
    return db_sample


# ============================
# Lab billing
# ============================
def create_lab_bill(db: Session, bill: schemas.LabBillCreate):
    if bill.patient_id is not None:
        _require_patient(db, bill.patient_id)
    if bill.patient_id is None and not (bill.patient_name or "").strip():
        raise HTTPException(status_code=422, detail="Provide either a registered patient or a walk-in patient name.")

    subtotal = sum(item.price for item in bill.items)
    subtotal, _, _, total = _apply_percentage_totals(subtotal, bill.discount, bill.gst)

    db_bill = models.LabBill(
        patient_id=bill.patient_id,
        patient_name=bill.patient_name,
        subtotal=round(subtotal, 2),
        total=round(total, 2),
        discount=bill.discount,
        gst=bill.gst,
        status="Pending",
        payment_mode=bill.payment_mode,
        payment_details=bill.payment_details,
        notes=bill.notes,
        items=[
            models.LabBillItem(test_id=item.test_id, test_name=item.test_name, price=item.price)
            for item in bill.items
        ],
    )
    db.add(db_bill)
    db.commit()
    db.refresh(db_bill)
    return db_bill


def create_lab_bill_from_orders(db: Session, payload: schemas.LabBillFromOrders):
    """Bill one or more lab orders and link the orders to the new bill."""
    orders = []
    for order_id in payload.order_ids:
        order = _get_or_404(db, models.LabOrder, order_id, "Lab order")
        if order.bill_id:
            raise HTTPException(status_code=409, detail=f"Order #{order_id} is already billed.")
        orders.append(order)

    patient_ids = {o.patient_id for o in orders}
    if len(patient_ids) > 1:
        raise HTTPException(status_code=422, detail="All orders on a single bill must belong to the same patient.")

    items, seen_panels, subtotal = [], set(), 0.0
    for order in orders:
        # A panel is charged once even though it produces several member orders.
        if order.panel_id:
            if order.panel_id in seen_panels:
                continue
            seen_panels.add(order.panel_id)
            panel = db.query(models.LabTestMaster).filter(models.LabTestMaster.id == order.panel_id).first()
            if panel is None:
                continue
            price = panel.price or 0.0
            items.append(models.LabBillItem(test_id=panel.id, test_name=panel.test_name, price=price))
            subtotal += price
            continue

        test = db.query(models.LabTestMaster).filter(models.LabTestMaster.id == order.test_id).first()
        price = (test.price if test else 0.0) or 0.0
        items.append(
            models.LabBillItem(
                test_id=order.test_id, test_name=test.test_name if test else "Unknown test", price=price
            )
        )
        subtotal += price

    subtotal, _, _, total = _apply_percentage_totals(subtotal, payload.discount, payload.gst)

    db_bill = models.LabBill(
        patient_id=orders[0].patient_id,
        subtotal=round(subtotal, 2),
        total=round(total, 2),
        discount=payload.discount,
        gst=payload.gst,
        status="Paid" if payload.mark_paid else "Pending",
        payment_mode=payload.payment_mode,
        payment_details=payload.payment_details,
        notes=payload.notes,
        items=items,
    )
    db.add(db_bill)
    db.flush()

    for order in orders:
        order.bill_id = db_bill.id

    db.commit()
    db.refresh(db_bill)
    return db_bill


def get_lab_bills(db: Session, patient_id: Optional[int] = None, bill_status: Optional[str] = None):
    query = db.query(models.LabBill)
    if patient_id:
        query = query.filter(models.LabBill.patient_id == patient_id)
    if bill_status:
        query = query.filter(models.LabBill.status == bill_status)
    return query.order_by(models.LabBill.bill_date.desc()).all()


def update_lab_bill_status(db: Session, bill_id: int, status: str):
    if status not in constants.LAB_BILL_STATUSES:
        raise HTTPException(
            status_code=422, detail=f"Invalid lab bill status. Valid: {', '.join(constants.LAB_BILL_STATUSES)}"
        )
    db_bill = _get_or_404(db, models.LabBill, bill_id, "Lab bill")
    if db_bill.status == "Cancelled" and status != "Cancelled":
        # Its orders were released for re-billing; reviving it would bill them twice.
        raise HTTPException(status_code=409, detail="A cancelled bill cannot be reopened. Raise a new bill instead.")
    if status == "Cancelled":
        db.query(models.LabOrder).filter(models.LabOrder.bill_id == db_bill.id).update(
            {models.LabOrder.bill_id: None}, synchronize_session=False
        )
    db_bill.status = status
    db.commit()
    db.refresh(db_bill)
    return db_bill


# ============================
# Lab reports
# ============================
def create_lab_report(db: Session, report: schemas.LabReportCreate):
    _require_patient(db, report.patient_id)
    data = report.model_dump()
    if data.get("order_id"):
        _get_or_404(db, models.LabOrder, data["order_id"], "Lab order")
    data["results_data"] = [r if isinstance(r, dict) else r for r in (data.get("results_data") or [])] or None
    if data["results_data"]:
        data["is_abnormal"] = any(lab_utils.is_abnormal(r.get("flag")) for r in data["results_data"])
    if data.get("status") == "Verified" and not data.get("verified_at"):
        data["verified_at"] = _utcnow()
    db_report = models.LabReport(**data)
    db.add(db_report)
    db.commit()
    db.refresh(db_report)
    return db_report


def get_lab_reports(
    db: Session,
    patient_id: Optional[int] = None,
    order_id: Optional[int] = None,
    abnormal_only: bool = False,
    skip: int = 0,
    limit: int = 500,
):
    query = db.query(models.LabReport)
    if patient_id:
        query = query.filter(models.LabReport.patient_id == patient_id)
    if order_id:
        query = query.filter(models.LabReport.order_id == order_id)
    if abnormal_only:
        query = query.filter(models.LabReport.is_abnormal.is_(True))
    return (
        query.options(joinedload(models.LabReport.patient))
        .order_by(models.LabReport.date_conducted.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def update_lab_report(db: Session, report_id: int, report_update: schemas.LabReportUpdate):
    db_report = _get_or_404(db, models.LabReport, report_id, "Lab report")
    if db_report.status == "Verified":
        raise HTTPException(status_code=409, detail="A verified report cannot be edited.")
    data = report_update.model_dump(exclude_unset=True)
    if data.get("results_data") is not None:
        data["is_abnormal"] = any(lab_utils.is_abnormal(r.get("flag")) for r in data["results_data"])
    for key, value in data.items():
        setattr(db_report, key, value)
    db.commit()
    db.refresh(db_report)
    return db_report


def delete_lab_report(db: Session, report_id: int):
    db_report = _get_or_404(db, models.LabReport, report_id, "Lab report")
    if db_report.status == "Verified":
        raise HTTPException(status_code=409, detail="A verified report cannot be deleted.")
    db.delete(db_report)
    db.commit()
    return db_report


# ============================
# Lab statistics
# ============================
def get_lab_stats(db: Session) -> dict:
    today = date.today()
    start, end = _day_bounds(today)
    now = _utcnow()

    def count_orders(*filters):
        return db.query(func.count(models.LabOrder.id)).filter(*filters).scalar() or 0

    verified_today = count_orders(
        models.LabOrder.status == "Verified",
        models.LabOrder.verified_at >= start,
        models.LabOrder.verified_at <= end,
    )
    finished = count_orders(models.LabOrder.verified_at.isnot(None))
    overdue = count_orders(
        models.LabOrder.due_at.isnot(None),
        models.LabOrder.due_at < now,
        models.LabOrder.status.notin_(("Verified", "Cancelled")),
    )
    on_time = count_orders(
        models.LabOrder.verified_at.isnot(None),
        models.LabOrder.due_at.isnot(None),
        models.LabOrder.verified_at <= models.LabOrder.due_at,
    )

    today_revenue = _sum_between(
        db, models.LabBill.total, models.LabBill.bill_date, start, end, *_LAB_BILL_COUNTS
    )

    return {
        "pending": count_orders(models.LabOrder.status == "Pending"),
        "sample_collected": count_orders(models.LabOrder.status == "Sample Collected"),
        "testing": count_orders(models.LabOrder.status == "Testing"),
        "ready_to_report": count_orders(models.LabOrder.status == "Completed"),
        "verified_today": verified_today,
        "overdue": overdue,
        "stat_pending": count_orders(
            models.LabOrder.priority == "STAT", models.LabOrder.status.notin_(("Verified", "Cancelled"))
        ),
        "samples_pending": db.query(func.count(models.LabSample.id))
        .filter(models.LabSample.status.in_(("Pending", "Collected")))
        .scalar()
        or 0,
        "rejected_samples": db.query(func.count(models.LabSample.id))
        .filter(models.LabSample.status == "Rejected")
        .scalar()
        or 0,
        "total_tests": db.query(func.count(models.LabTestMaster.id)).scalar() or 0,
        "active_tests": db.query(func.count(models.LabTestMaster.id))
        .filter(models.LabTestMaster.is_active.is_(True), models.LabTestMaster.is_panel.is_(False))
        .scalar()
        or 0,
        "panels": db.query(func.count(models.LabTestMaster.id))
        .filter(models.LabTestMaster.is_active.is_(True), models.LabTestMaster.is_panel.is_(True))
        .scalar()
        or 0,
        "today_orders": count_orders(models.LabOrder.order_date >= start, models.LabOrder.order_date <= end),
        "today_revenue": round(float(today_revenue), 2),
        "pending_billing": count_orders(models.LabOrder.bill_id.is_(None)),
        "tat_compliance_percent": round((on_time / finished) * 100, 1) if finished else 100.0,
    }


# ============================
# OP / IP bills
# ============================
def create_op_bill(db: Session, bill: schemas.OPBillCreate):
    _require_patient(db, bill.patient_id)
    db_token = None
    if bill.token_id:
        db_token = _get_or_404(db, models.OPToken, bill.token_id, "Token")
        if db_token.patient_id != bill.patient_id:
            raise HTTPException(status_code=422, detail="That OP token belongs to a different patient.")
        if db_token.is_billed:
            raise HTTPException(status_code=409, detail="This OP token has already been billed.")
    other_total = sum(c.amount for c in bill.other_charges)
    subtotal = bill.consultation_fee + bill.lab_charges + bill.pharmacy_charges + other_total
    subtotal, _, _, total = _apply_percentage_totals(subtotal, bill.discount, bill.gst)

    db_bill = models.OPBill(
        **bill.model_dump(exclude={"other_charges"}),
        other_charges=[c.model_dump() for c in bill.other_charges],
        subtotal=round(subtotal, 2),
        total=round(total, 2),
    )
    db.add(db_bill)

    if db_token is not None:
        db_token.is_billed = True

    db.commit()
    db.refresh(db_bill)
    return db_bill


def get_op_bills(db: Session, patient_id: Optional[int] = None, skip: int = 0, limit: int = 500):
    query = db.query(models.OPBill)
    if patient_id:
        query = query.filter(models.OPBill.patient_id == patient_id)
    return query.order_by(models.OPBill.bill_date.desc()).offset(skip).limit(limit).all()


def create_ip_bill(db: Session, bill: schemas.IPBillCreate):
    _require_patient(db, bill.patient_id)
    room_charges = bill.room_charge_per_day * bill.days_stayed
    other_total = sum(c.amount for c in bill.other_charges)
    subtotal = (
        room_charges
        + bill.doctor_charges
        + bill.nursing_charges
        + bill.pharmacy_charges
        + bill.lab_charges
        + other_total
    )
    subtotal, _, _, total = _apply_percentage_totals(subtotal, bill.discount, bill.gst)

    db_bill = models.IPBill(
        **bill.model_dump(exclude={"other_charges"}),
        room_charges=room_charges,
        other_charges=[c.model_dump() for c in bill.other_charges],
        subtotal=round(subtotal, 2),
        total=round(total, 2),
    )
    db.add(db_bill)
    db.commit()
    db.refresh(db_bill)
    return db_bill


def get_ip_bills(db: Session, patient_id: Optional[int] = None, skip: int = 0, limit: int = 500):
    query = db.query(models.IPBill)
    if patient_id:
        query = query.filter(models.IPBill.patient_id == patient_id)
    return query.order_by(models.IPBill.bill_date.desc()).offset(skip).limit(limit).all()


# ============================
# Hospital structure: departments → wards → rooms → beds
# ============================
def _stamp_create(instance, actor: Optional[str]):
    """Attribute a new clinical record to its author."""
    if actor and hasattr(instance, "created_by"):
        instance.created_by = actor


def _stamp_update(instance, actor: Optional[str]):
    if actor and hasattr(instance, "updated_by"):
        instance.updated_by = actor


def _audit_change(
    db: Session,
    instance,
    *,
    action: str,
    entity_type: str,
    actor: Optional[str],
    actor_role: Optional[str],
    patient_id: Optional[int] = None,
    before: Optional[dict] = None,
    details: Optional[str] = None,
):
    """Append a clinical audit entry. Caller owns the transaction."""
    return audit.record_change(
        db,
        instance,
        action=action,
        entity_type=entity_type,
        actor=actor,
        actor_role=actor_role,
        patient_id=patient_id,
        before=before,
        details=details,
    )


def create_department(db: Session, payload: schemas.DepartmentCreate):
    if payload.head_doctor_id is not None:
        _get_or_404(db, models.User, payload.head_doctor_id, "Head doctor")
    db_dept = models.Department(**payload.model_dump())
    db.add(db_dept)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Department '{payload.name}' or code '{payload.code}' already exists.")
    db.refresh(db_dept)
    return db_dept


def get_departments(db: Session, active_only: bool = False):
    query = db.query(models.Department)
    if active_only:
        query = query.filter(models.Department.is_active.is_(True))
    return query.order_by(models.Department.name).all()


def update_department(db: Session, department_id: int, payload: schemas.DepartmentUpdate):
    dept = _get_or_404(db, models.Department, department_id, "Department")
    data = payload.model_dump(exclude_unset=True)
    if data.get("head_doctor_id") is not None:
        _get_or_404(db, models.User, data["head_doctor_id"], "Head doctor")
    for key, value in data.items():
        setattr(dept, key, value)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Department name or code already exists.")
    db.refresh(dept)
    return dept


def create_ward(db: Session, payload: schemas.WardCreate):
    if payload.department_id is not None:
        _get_or_404(db, models.Department, payload.department_id, "Department")
    db_ward = models.Ward(**payload.model_dump())
    db.add(db_ward)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Ward code '{payload.code}' already exists.")
    db.refresh(db_ward)
    return db_ward


def get_wards(db: Session, active_only: bool = False, department_id: Optional[int] = None):
    query = db.query(models.Ward).options(
        joinedload(models.Ward.rooms).joinedload(models.Room.beds), joinedload(models.Ward.department)
    )
    if active_only:
        query = query.filter(models.Ward.is_active.is_(True))
    if department_id:
        query = query.filter(models.Ward.department_id == department_id)
    return query.order_by(models.Ward.name).all()


def update_ward(db: Session, ward_id: int, payload: schemas.WardUpdate):
    ward = _get_or_404(db, models.Ward, ward_id, "Ward")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(ward, key, value)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Ward code already exists.")
    db.refresh(ward)
    return ward


def create_room(db: Session, payload: schemas.RoomCreate):
    ward = _get_or_404(db, models.Ward, payload.ward_id, "Ward")
    db_room = models.Room(**payload.model_dump())
    db.add(db_room)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=400, detail=f"Room {payload.room_number} already exists in ward '{ward.name}'."
        )
    db.refresh(db_room)
    return db_room


def update_room(db: Session, room_id: int, payload: schemas.RoomUpdate):
    room = _get_or_404(db, models.Room, room_id, "Room")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(room, key, value)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Room number already exists in this ward.")
    db.refresh(room)
    return room


def create_bed(db: Session, payload: schemas.BedCreate):
    _get_or_404(db, models.Room, payload.room_id, "Room")
    db_bed = models.Bed(**payload.model_dump())
    db.add(db_bed)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=400, detail=f"Bed '{payload.bed_code}' already exists in that room."
        )
    db.refresh(db_bed)
    return db_bed


def update_bed(db: Session, bed_id: int, payload: schemas.BedUpdate):
    bed = _get_or_404(db, models.Bed, bed_id, "Bed")
    data = payload.model_dump(exclude_unset=True)

    # A bed holding a patient cannot be quietly re-marked as free; occupancy is
    # owned by the allocation records, not by this field.
    if "status" in data and data["status"] != bed.status:
        open_allocation = _open_allocation_for_bed(db, bed.id)
        if open_allocation and data["status"] != "Occupied":
            raise HTTPException(
                status_code=409,
                detail="This bed is occupied. Discharge or transfer the patient first.",
            )
        if not open_allocation and data["status"] == "Occupied":
            raise HTTPException(
                status_code=409,
                detail="A bed can only become Occupied by admitting a patient to it.",
            )
    for key, value in data.items():
        setattr(bed, key, value)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Bed code already exists in that room.")
    db.refresh(bed)
    return bed


def delete_bed(db: Session, bed_id: int):
    bed = _get_or_404(db, models.Bed, bed_id, "Bed")
    if _open_allocation_for_bed(db, bed.id):
        raise HTTPException(status_code=409, detail="This bed is occupied and cannot be removed.")
    if db.query(models.BedAllocation).filter(models.BedAllocation.bed_id == bed_id).first():
        # Keep history intact; retire the bed instead of deleting it.
        bed.is_active = False
        bed.status = "Blocked"
        db.commit()
        return bed
    db.delete(bed)
    db.commit()
    return bed


def effective_bed_charge(bed: Optional[models.Bed]) -> float:
    """Bed rate, falling back to the room and then the ward."""
    if bed is None:
        return 0.0
    if bed.daily_charge is not None:
        return float(bed.daily_charge)
    room = bed.room
    if room is not None:
        if room.daily_charge is not None:
            return float(room.daily_charge)
        if room.ward is not None:
            return float(room.ward.daily_charge or 0.0)
    return 0.0


def _open_allocation_for_bed(db: Session, bed_id: int):
    return (
        db.query(models.BedAllocation)
        .filter(models.BedAllocation.bed_id == bed_id, models.BedAllocation.released_at.is_(None))
        .first()
    )


def _open_allocation_for_admission(db: Session, admission_id: int):
    return (
        db.query(models.BedAllocation)
        .filter(
            models.BedAllocation.admission_id == admission_id,
            models.BedAllocation.released_at.is_(None),
        )
        .first()
    )


def _bed_location(bed: models.Bed) -> dict:
    room = bed.room
    ward = room.ward if room else None
    return {
        "bed_code": bed.bed_code,
        "room_number": room.room_number if room else None,
        "ward_number": ward.name if ward else None,
    }


def _allocate_bed(
    db: Session, admission: models.IPAdmission, bed: models.Bed, actor: Optional[str], reason: Optional[str] = None
):
    """Place an admission in a bed. Caller owns the transaction."""
    if not bed.is_active:
        raise HTTPException(status_code=409, detail=f"Bed {bed.bed_code} is not in service.")
    if bed.status not in constants.BED_ALLOCATABLE_STATUSES:
        raise HTTPException(
            status_code=409, detail=f"Bed {bed.bed_code} is {bed.status.lower()} and cannot be allocated."
        )
    if _open_allocation_for_bed(db, bed.id):
        raise HTTPException(status_code=409, detail=f"Bed {bed.bed_code} is already occupied.")

    location = _bed_location(bed)
    allocation = models.BedAllocation(
        admission_id=admission.id,
        bed_id=bed.id,
        allocated_at=_utcnow(),
        allocated_by=actor,
    )
    db.add(allocation)

    bed.status = "Occupied"
    admission.bed_id = bed.id
    admission.bed_code = location["bed_code"]
    admission.room_number = location["room_number"]
    admission.ward_number = location["ward_number"]
    db.flush()
    return allocation


def _release_bed(db: Session, admission: models.IPAdmission, actor: Optional[str], reason: str, next_status: str = "Cleaning"):
    """Free the bed held by an admission. Caller owns the transaction."""
    allocation = _open_allocation_for_admission(db, admission.id)
    if allocation is None:
        return None
    allocation.released_at = _utcnow()
    allocation.released_by = actor
    allocation.release_reason = reason

    bed = db.query(models.Bed).filter(models.Bed.id == allocation.bed_id).first()
    if bed is not None and bed.status == "Occupied":
        bed.status = next_status
    db.flush()
    return allocation


def get_bed_board(
    db: Session,
    ward_id: Optional[int] = None,
    bed_status: Optional[str] = None,
    include_inactive: bool = False,
) -> List[dict]:
    """Every bed with its location and current occupant — the IPD bed board."""
    query = (
        db.query(models.Bed)
        .options(
            joinedload(models.Bed.room).joinedload(models.Room.ward).joinedload(models.Ward.department)
        )
    )
    if not include_inactive:
        query = query.filter(models.Bed.is_active.is_(True))

    beds = query.all()

    # Occupants for all beds in one query instead of one per bed.
    open_allocations = (
        db.query(models.BedAllocation)
        .options(
            joinedload(models.BedAllocation.admission).joinedload(models.IPAdmission.patient),
            joinedload(models.BedAllocation.admission).joinedload(models.IPAdmission.attending_doctor),
        )
        .filter(models.BedAllocation.released_at.is_(None))
        .all()
    )
    occupant_by_bed = {a.bed_id: a for a in open_allocations}

    board: List[dict] = []
    for bed in beds:
        room = bed.room
        ward = room.ward if room else None
        if ward_id and (ward is None or ward.id != ward_id):
            continue
        if bed_status and bed.status != bed_status:
            continue

        allocation = occupant_by_bed.get(bed.id)
        admission = allocation.admission if allocation else None
        patient = admission.patient if admission else None
        doctor = admission.attending_doctor if admission else None

        board.append(
            {
                "bed_id": bed.id,
                "bed_code": bed.bed_code,
                "bed_type": bed.bed_type,
                "status": bed.status,
                "is_active": bed.is_active,
                "ward_id": ward.id if ward else None,
                "ward_name": ward.name if ward else None,
                "ward_type": ward.ward_type if ward else None,
                "room_id": room.id if room else None,
                "room_number": room.room_number if room else None,
                "daily_charge": effective_bed_charge(bed),
                "admission_id": admission.id if admission else None,
                "patient_id": patient.id if patient else None,
                "patient_name": patient.name if patient else None,
                "patient_uhid": f"P{patient.id:06d}" if patient else None,
                "admitted_at": admission.admission_date if admission else None,
                "attending_doctor": (
                    (doctor.full_name or doctor.username) if doctor else (admission.doctor_in_charge if admission else None)
                ),
            }
        )
    return board


def get_bed_board_summary(db: Session) -> dict:
    board = get_bed_board(db)
    counts = {status: 0 for status in constants.BED_STATUSES}
    by_ward: dict = {}

    for item in board:
        counts[item["status"]] = counts.get(item["status"], 0) + 1
        ward = item["ward_name"] or "Unassigned"
        bucket = by_ward.setdefault(
            ward, {"ward": ward, "ward_type": item["ward_type"], "total": 0, "available": 0, "occupied": 0}
        )
        bucket["total"] += 1
        if item["status"] == "Available":
            bucket["available"] += 1
        if item["status"] == "Occupied":
            bucket["occupied"] += 1

    total = len(board)
    occupied = counts.get("Occupied", 0)
    return {
        "total_beds": total,
        "available": counts.get("Available", 0),
        "occupied": occupied,
        "reserved": counts.get("Reserved", 0),
        "cleaning": counts.get("Cleaning", 0),
        "maintenance": counts.get("Maintenance", 0),
        "blocked": counts.get("Blocked", 0),
        "occupancy_percent": round((occupied / total) * 100, 1) if total else 0.0,
        "by_ward": sorted(by_ward.values(), key=lambda w: w["ward"]),
    }


# ============================
# IP admissions
# ============================
def create_ip_admission(
    db: Session,
    admission: schemas.IPAdmissionCreate,
    actor: Optional[str] = None,
    actor_role: Optional[str] = None,
):
    """Admit a patient, optionally allocating a bed in the same transaction.

    Bed allocation and the admission row must succeed or fail together: a bed
    marked Occupied with no admission would be permanently lost from the board.
    """
    _require_patient(db, admission.patient_id)
    active = (
        db.query(models.IPAdmission)
        .filter(models.IPAdmission.patient_id == admission.patient_id, models.IPAdmission.status == "Admitted")
        .first()
    )
    if active:
        raise HTTPException(
            status_code=409,
            detail=f"This patient is already admitted (admission #{active.id}). Discharge or transfer them first.",
        )
    if admission.attending_doctor_id is not None:
        _get_or_404(db, models.User, admission.attending_doctor_id, "Attending doctor")
    if admission.department_id is not None:
        _get_or_404(db, models.Department, admission.department_id, "Department")

    bed = None
    if admission.bed_id is not None:
        bed = _get_or_404(db, models.Bed, admission.bed_id, "Bed")

    data = admission.model_dump(exclude={"bed_id"})
    db_admission = models.IPAdmission(**data, status="Admitted")
    _stamp_create(db_admission, actor)
    db.add(db_admission)
    db.flush()  # assign the id so the allocation can reference it

    if bed is not None:
        _allocate_bed(db, db_admission, bed, actor=actor, reason="Admission")

    _audit_change(
        db,
        db_admission,
        action="ADMISSION_CREATED",
        entity_type="ip_admission",
        actor=actor,
        actor_role=actor_role,
        patient_id=db_admission.patient_id,
        details=f"Admitted{' to bed ' + bed.bed_code if bed is not None else ' without a bed'}",
    )

    db.commit()
    db.refresh(db_admission)
    return db_admission


def get_ip_admissions(
    db: Session,
    patient_id: Optional[int] = None,
    admission_status: Optional[str] = None,
    department_id: Optional[int] = None,
    ward_id: Optional[int] = None,
    current_only: bool = False,
    skip: int = 0,
    limit: int = 200,
):
    query = db.query(models.IPAdmission).options(
        joinedload(models.IPAdmission.patient),
        joinedload(models.IPAdmission.bed).joinedload(models.Bed.room).joinedload(models.Room.ward),
        joinedload(models.IPAdmission.attending_doctor),
    )
    if patient_id:
        query = query.filter(models.IPAdmission.patient_id == patient_id)
    if admission_status:
        query = query.filter(models.IPAdmission.status == admission_status)
    if department_id:
        query = query.filter(models.IPAdmission.department_id == department_id)
    if current_only:
        query = query.filter(models.IPAdmission.status == "Admitted")
    if ward_id:
        query = query.filter(models.IPAdmission.bed_id.in_(
            db.query(models.Bed.id).join(models.Room).filter(models.Room.ward_id == ward_id)
        ))
    return (
        query.order_by(models.IPAdmission.admission_date.desc()).offset(skip).limit(limit).all()
    )


def get_ip_admission(db: Session, admission_id: int) -> models.IPAdmission:
    return _get_or_404(db, models.IPAdmission, admission_id, "IP admission")


def billable_room_charge(admission: models.IPAdmission, days: int, end: datetime) -> float:
    """Room charge for the whole stay, from every bed the patient occupied.

    The previous figure was ``current bed rate x days``. After discharge there is
    no current bed, so the charge became 0 exactly when the bill is raised, and a
    transfer between beds of different rates was billed at the last rate only.
    The billable day count is unchanged (at least one day); it is split across
    beds in proportion to the time spent in each.
    """
    billable_days = max(days, 1)
    spans = []
    for allocation in admission.allocations or []:
        if allocation.allocated_at is None:
            continue
        released = allocation.released_at or end
        seconds = max((released - allocation.allocated_at).total_seconds(), 0.0)
        spans.append((effective_bed_charge(allocation.bed), seconds))

    if not spans:
        return round(effective_bed_charge(admission.bed) * billable_days, 2)
    total_seconds = sum(seconds for _, seconds in spans)
    if total_seconds == 0:
        # Every allocation opened and closed in the same instant: bill the last bed.
        return round(spans[-1][0] * billable_days, 2)
    weighted_rate = sum(rate * seconds for rate, seconds in spans) / total_seconds
    return round(weighted_rate * billable_days, 2)


def get_ip_admission_detail(db: Session, admission_id: int) -> dict:
    """Admission with its full clinical record, for the IPD workspace."""
    admission = (
        db.query(models.IPAdmission)
        .options(
            joinedload(models.IPAdmission.patient),
            joinedload(models.IPAdmission.bed).joinedload(models.Bed.room).joinedload(models.Room.ward),
            joinedload(models.IPAdmission.attending_doctor),
            joinedload(models.IPAdmission.department),
            joinedload(models.IPAdmission.allocations).joinedload(models.BedAllocation.bed),
            joinedload(models.IPAdmission.transfers),
            joinedload(models.IPAdmission.nursing_notes),
            joinedload(models.IPAdmission.medication_orders).joinedload(models.MedicationOrder.administrations),
            joinedload(models.IPAdmission.discharge_summary),
        )
        .filter(models.IPAdmission.id == admission_id)
        .first()
    )
    if admission is None:
        raise HTTPException(status_code=404, detail="IP admission not found")

    end = admission.discharge_date or _utcnow()
    days = max((end - admission.admission_date).days, 0) if admission.admission_date else 0
    room_charge = billable_room_charge(admission, days, end)

    # ORM objects, not dicts: the response schema types them as real models so the
    # OpenAPI contract stays accurate.
    return {
        "admission": admission,
        "allocations": admission.allocations,
        "transfers": admission.transfers,
        "nursing_notes": admission.nursing_notes,
        "medication_orders": admission.medication_orders,
        "discharge_summary": admission.discharge_summary,
        "length_of_stay_days": days,
        "billable_room_charge": room_charge,
    }


def assign_bed(
    db: Session,
    admission_id: int,
    bed_id: int,
    actor: Optional[str] = None,
    reason: Optional[str] = None,
    actor_role: Optional[str] = None,
):
    """Put an admitted patient into a bed (e.g. one freed up after admission)."""
    admission = _get_or_404(db, models.IPAdmission, admission_id, "IP admission")
    if admission.status != "Admitted":
        raise HTTPException(
            status_code=409, detail=f"A {admission.status.lower()} admission cannot be given a bed."
        )
    if _open_allocation_for_admission(db, admission.id):
        raise HTTPException(
            status_code=409, detail="This patient already has a bed. Use transfer to move them."
        )
    bed = _get_or_404(db, models.Bed, bed_id, "Bed")
    _allocate_bed(db, admission, bed, actor=actor, reason=reason or "Bed assigned")
    _stamp_update(admission, actor)
    _audit_change(
        db, admission,
        action="BED_ASSIGNED", entity_type="ip_admission",
        actor=actor, actor_role=actor_role, patient_id=admission.patient_id,
        details=f"Assigned to bed {bed.bed_code}",
    )
    db.commit()
    db.refresh(admission)
    return admission


def transfer_patient(
    db: Session,
    admission_id: int,
    payload: schemas.PatientTransferRequest,
    actor: Optional[str] = None,
    actor_role: Optional[str] = None,
):
    """Move an admitted patient to another bed, keeping the full trail."""
    admission = _get_or_404(db, models.IPAdmission, admission_id, "IP admission")
    if admission.status != "Admitted":
        raise HTTPException(
            status_code=409, detail=f"A {admission.status.lower()} admission cannot be transferred."
        )

    to_bed = _get_or_404(db, models.Bed, payload.to_bed_id, "Target bed")
    current = _open_allocation_for_admission(db, admission.id)
    if current and current.bed_id == to_bed.id:
        raise HTTPException(status_code=409, detail="The patient is already in that bed.")

    from_bed = db.query(models.Bed).filter(models.Bed.id == current.bed_id).first() if current else None
    from_ward = from_bed.room.ward.name if from_bed and from_bed.room and from_bed.room.ward else admission.ward_number
    to_ward = to_bed.room.ward.name if to_bed.room and to_bed.room.ward else None

    if current:
        current.released_at = _utcnow()
        current.released_by = actor
        current.release_reason = f"Transfer to {to_bed.bed_code}"
        if from_bed is not None and from_bed.status == "Occupied":
            from_bed.status = "Cleaning"
        db.flush()

    _allocate_bed(db, admission, to_bed, actor=actor, reason="Transfer")

    db.add(
        models.PatientTransfer(
            admission_id=admission.id,
            from_bed_id=from_bed.id if from_bed else None,
            to_bed_id=to_bed.id,
            from_ward=from_ward,
            to_ward=to_ward,
            reason=payload.reason,
            transferred_by=actor,
            transferred_at=_utcnow(),
        )
    )
    _stamp_update(admission, actor)
    _audit_change(
        db, admission,
        action="PATIENT_TRANSFERRED", entity_type="ip_admission",
        actor=actor, actor_role=actor_role, patient_id=admission.patient_id,
        before={"bed_id": from_bed.id if from_bed else None,
                "ward_number": from_ward},
        details=f"{from_bed.bed_code if from_bed else 'no bed'} -> {to_bed.bed_code}"
                f"{' (' + payload.reason + ')' if payload.reason else ''}",
    )
    db.commit()
    db.refresh(admission)
    return admission


def discharge_patient(
    db: Session,
    admission_id: int,
    payload: schemas.DischargeRequest,
    actor: Optional[str] = None,
    actor_role: Optional[str] = None,
):
    """Discharge an admission: release the bed and seal the record.

    The bed is released to "Cleaning", not "Available" — housekeeping must clear
    it before the next patient, so it cannot be double-booked immediately.
    """
    admission = _get_or_404(db, models.IPAdmission, admission_id, "IP admission")
    if admission.status != "Admitted":
        raise HTTPException(status_code=409, detail=f"This admission is already {admission.status.lower()}.")

    # A clinical discharge without a summary is unsafe; allow it only explicitly.
    existing_summary = (
        db.query(models.DischargeSummary)
        .filter(models.DischargeSummary.admission_id == admission.id)
        .first()
    )
    if payload.require_summary and existing_summary is None and payload.summary is None:
        raise HTTPException(
            status_code=409,
            detail="A discharge summary is required before discharge. Save the summary first, "
                   "or send require_summary=false to override.",
        )

    if payload.summary is not None:
        summary = existing_summary or models.DischargeSummary(
            admission_id=admission.id, patient_id=admission.patient_id
        )
        for key, value in payload.summary.model_dump().items():
            setattr(summary, key, value)
        if existing_summary is None:
            db.add(summary)

    _release_bed(db, admission, actor=actor, reason=f"Discharged ({payload.discharge_type})")

    # Inpatient orders end with the stay; leaving them Active let the MAR record
    # doses for a patient who had already gone home.
    closed_at = _utcnow()
    for order in admission.medication_orders or []:
        if order.status in ("Active", "On Hold"):
            order.status = "Stopped"
            order.end_date = order.end_date or closed_at
            if not order.stop_reason:
                order.stop_reason = f"Patient discharged ({payload.discharge_type})"

    admission.status = {
        "Routine": "Discharged",
        "Transfer": "Transferred",
        "Against Medical Advice": "DAMA",
        "Expired": "Deceased",
        "Absconded": "DAMA",
    }.get(payload.discharge_type, "Discharged")

    admission.discharge_date = payload.discharge_date or _utcnow()
    admission.discharge_type = payload.discharge_type
    admission.discharged_by = actor
    admission.bed_id = None
    _stamp_update(admission, actor)
    _audit_change(
        db, admission,
        action="PATIENT_DISCHARGED", entity_type="ip_admission",
        actor=actor, actor_role=actor_role, patient_id=admission.patient_id,
        details=f"{payload.discharge_type} discharge"
                f"{' with summary' if existing_summary else ' without a summary'}",
    )
    db.commit()
    db.refresh(admission)
    return admission


def update_ip_admission_status(
    db: Session, admission_id: int, status: str, discharge_date: Optional[datetime] = None
):
    if status not in constants.ADMISSION_STATUSES:
        raise HTTPException(
            status_code=422, detail=f"Invalid admission status. Valid: {', '.join(constants.ADMISSION_STATUSES)}"
        )
    db_admission = _get_or_404(db, models.IPAdmission, admission_id, "IP admission")

    if not constants.is_valid_admission_transition(db_admission.status, status):
        raise HTTPException(
            status_code=409, detail=f"Illegal admission transition {db_admission.status} -> {status}."
        )
    if status in constants.ADMISSION_TERMINAL_STATUSES and status != db_admission.status:
        raise HTTPException(
            status_code=409,
            detail="Use POST /ip-admissions/{id}/discharge to discharge, transfer out or record a death; "
                  "it releases the bed, closes medication orders and enforces the discharge summary.",
        )
    db_admission.status = status
    if discharge_date and db_admission.status in constants.ADMISSION_TERMINAL_STATUSES:
        # Correcting the recorded date of an existing discharge is allowed.
        db_admission.discharge_date = discharge_date
    db.commit()
    db.refresh(db_admission)
    return db_admission


def update_ip_admission(db: Session, admission_id: int, admission_update: schemas.IPAdmissionUpdate):
    db_admission = _get_or_404(db, models.IPAdmission, admission_id, "IP admission")
    data = admission_update.model_dump(exclude_unset=True)

    if data.get("attending_doctor_id") is not None:
        _get_or_404(db, models.User, data["attending_doctor_id"], "Attending doctor")
    if data.get("department_id") is not None:
        _get_or_404(db, models.Department, data["department_id"], "Department")

    new_status = data.pop("status", None)
    if new_status and new_status != db_admission.status:
        if not constants.is_valid_admission_transition(db_admission.status, new_status):
            raise HTTPException(
                status_code=409,
                detail=f"Illegal admission transition {db_admission.status} -> {new_status}.",
            )
        if new_status in constants.ADMISSION_TERMINAL_STATUSES:
            raise HTTPException(
                status_code=409,
                detail="Use POST /ip-admissions/{id}/discharge to discharge, transfer out or record a death; "
                      "it releases the bed, closes medication orders and enforces the discharge summary.",
            )
        db_admission.status = new_status

    if data.get("discharge_date") and db_admission.status not in constants.ADMISSION_TERMINAL_STATUSES:
        # Setting a discharge date is a discharge, which must go through /discharge.
        raise HTTPException(
            status_code=409,
            detail="Use POST /ip-admissions/{id}/discharge to discharge, transfer out or record a death; "
                  "it releases the bed, closes medication orders and enforces the discharge summary.",
        )

    for key, value in data.items():
        setattr(db_admission, key, value)

    db.commit()
    db.refresh(db_admission)
    return db_admission


def delete_ip_admission(db: Session, admission_id: int):
    db_admission = _get_or_404(db, models.IPAdmission, admission_id, "IP admission")
    if db_admission.status == "Admitted":
        raise HTTPException(
            status_code=409,
            detail="An active admission cannot be deleted. Discharge the patient first.",
        )
    db.query(models.IPBill).filter(models.IPBill.admission_id == admission_id).update(
        {models.IPBill.admission_id: None}, synchronize_session=False
    )
    db.delete(db_admission)
    db.commit()
    return db_admission


# ============================
# IPD — nursing
# ============================
def create_nursing_note(
    db: Session,
    admission_id: int,
    payload: schemas.NursingNoteCreate,
    actor: Optional[str] = None,
    actor_role: Optional[str] = None,
):
    admission = _get_or_404(db, models.IPAdmission, admission_id, "IP admission")
    if admission.status != "Admitted":
        raise HTTPException(
            status_code=409, detail="Vitals can only be charted while the patient is admitted."
        )
    data = payload.model_dump()
    # `is_critical` is derived below, never taken from the payload.
    data.pop("is_critical", None)
    if data.get("recorded_at") is None:
        data.pop("recorded_at", None)

    # Flag physiologically dangerous observations so the ward can see them.
    is_critical = payload.is_critical or _is_critical_vitals(payload)

    note = models.NursingNote(**data, admission_id=admission_id, recorded_by=actor, is_critical=is_critical)
    _stamp_create(note, actor)
    db.add(note)
    db.flush()
    _audit_change(
        db, note,
        action="VITALS_CHARTED", entity_type="nursing_note",
        actor=actor, actor_role=actor_role, patient_id=admission.patient_id,
        details=f"{payload.shift} shift"
                + (" — CRITICAL" if is_critical else ""),
    )
    db.commit()
    db.refresh(note)
    return note


def _is_critical_vitals(payload: schemas.NursingNoteBase) -> bool:
    """Server-side early-warning check — never trust the client's flag alone."""
    if payload.spo2 is not None and payload.spo2 < 92:
        return True
    if payload.temperature is not None and (payload.temperature >= 39.0 or payload.temperature <= 35.0):
        return True
    if payload.pulse is not None and (payload.pulse > 130 or payload.pulse < 45):
        return True
    if payload.respiratory_rate is not None and (payload.respiratory_rate > 30 or payload.respiratory_rate < 8):
        return True
    if payload.bp_systolic is not None and (payload.bp_systolic >= 180 or payload.bp_systolic <= 85):
        return True
    if payload.pain_score is not None and payload.pain_score >= 8:
        return True
    return False


def get_nursing_notes(db: Session, admission_id: int, limit: int = 200):
    _get_or_404(db, models.IPAdmission, admission_id, "IP admission")
    return (
        db.query(models.NursingNote)
        .filter(models.NursingNote.admission_id == admission_id)
        .order_by(models.NursingNote.recorded_at.desc())
        .limit(limit)
        .all()
    )


# ============================
# IPD — medication
# ============================
def create_medication_order(
    db: Session,
    admission_id: int,
    payload: schemas.MedicationOrderCreate,
    actor: Optional[str] = None,
    actor_role: Optional[str] = None,
):
    admission = _get_or_404(db, models.IPAdmission, admission_id, "IP admission")
    if admission.status != "Admitted":
        raise HTTPException(
            status_code=409, detail="Medication can only be prescribed while the patient is admitted."
        )
    if payload.medicine_id is not None:
        _get_or_404(db, models.MedicineStock, payload.medicine_id, "Medicine")

    data = payload.model_dump()
    if data.get("start_date") is None:
        data.pop("start_date", None)

    order = models.MedicationOrder(**data, admission_id=admission_id, prescribed_by=actor, status="Active")
    _stamp_create(order, actor)
    db.add(order)
    db.flush()
    _audit_change(
        db, order,
        action="MEDICATION_ORDERED", entity_type="medication_order",
        actor=actor, actor_role=actor_role, patient_id=admission.patient_id,
        details=f"{order.medicine_name} {order.dose or ''} {order.route or ''} {order.frequency or ''}".strip(),
    )
    db.commit()
    db.refresh(order)
    return order


def get_medication_orders(db: Session, admission_id: int, active_only: bool = False):
    _get_or_404(db, models.IPAdmission, admission_id, "IP admission")
    query = (
        db.query(models.MedicationOrder)
        .options(joinedload(models.MedicationOrder.administrations))
        .filter(models.MedicationOrder.admission_id == admission_id)
    )
    if active_only:
        query = query.filter(models.MedicationOrder.status == "Active")
    return query.order_by(models.MedicationOrder.start_date.desc()).all()


def update_medication_order(
    db: Session,
    order_id: int,
    payload: schemas.MedicationOrderUpdate,
    actor: Optional[str] = None,
    actor_role: Optional[str] = None,
):
    order = _get_or_404(db, models.MedicationOrder, order_id, "Medication order")
    data = payload.model_dump(exclude_unset=True)
    new_status = data.get("status")
    if new_status in ("Completed", "Stopped") and not order.end_date and not data.get("end_date"):
        data["end_date"] = _utcnow()
    if new_status == "Stopped" and not data.get("stop_reason") and not order.stop_reason:
        raise HTTPException(status_code=422, detail="A reason is required to stop a medication.")

    before = audit.snapshot(order)
    for key, value in data.items():
        setattr(order, key, value)
    _stamp_update(order, actor)

    admission = _get_or_404(db, models.IPAdmission, order.admission_id, "IP admission")
    _audit_change(
        db, order,
        action="MEDICATION_UPDATED", entity_type="medication_order",
        actor=actor, actor_role=actor_role, patient_id=admission.patient_id,
        before=before,
        details=f"{order.medicine_name} -> {order.status}",
    )
    db.commit()
    db.refresh(order)
    return order


def administer_medication(
    db: Session,
    order_id: int,
    payload: schemas.MedicationAdministrationCreate,
    actor: Optional[str] = None,
    actor_role: Optional[str] = None,
):
    """Record what was actually given (the MAR)."""
    order = _get_or_404(db, models.MedicationOrder, order_id, "Medication order")
    if order.status != "Active":
        raise HTTPException(
            status_code=409, detail=f"This order is {order.status.lower()} and cannot be administered."
        )
    owning_admission = _get_or_404(db, models.IPAdmission, order.admission_id, "IP admission")
    if owning_admission.status != "Admitted":
        raise HTTPException(
            status_code=409,
            detail=f"The patient is {owning_admission.status.lower()}; medication cannot be recorded.",
        )

    data = payload.model_dump()
    if data.get("administered_at") is None:
        data.pop("administered_at", None)
    # The given dose defaults to the prescribed dose, but the nurse may record a
    # different amount actually administered.
    given_dose = data.pop("dose_given", None) or order.dose

    record = models.MedicationAdministration(
        **data,
        order_id=order_id,
        administered_by=actor,
        dose_given=given_dose,
    )
    _stamp_create(record, actor)
    db.add(record)

    # A STAT dose is given once; complete the order automatically.
    if order.frequency == "STAT" and payload.status == "Given":
        order.status = "Completed"
        order.end_date = _utcnow()

    db.flush()
    admission = _get_or_404(db, models.IPAdmission, order.admission_id, "IP admission")
    _audit_change(
        db, record,
        action="MEDICATION_ADMINISTERED", entity_type="medication_administration",
        actor=actor, actor_role=actor_role, patient_id=admission.patient_id,
        details=f"{order.medicine_name} {given_dose or ''} — {payload.status}".strip(),
    )
    db.commit()
    db.refresh(record)
    return record


def get_medication_administrations(db: Session, order_id: int, limit: int = 100):
    _get_or_404(db, models.MedicationOrder, order_id, "Medication order")
    return (
        db.query(models.MedicationAdministration)
        .filter(models.MedicationAdministration.order_id == order_id)
        .order_by(models.MedicationAdministration.administered_at.desc())
        .limit(limit)
        .all()
    )


# ============================
# IPD — discharge summary
# ============================
def upsert_discharge_summary(
    db: Session,
    admission_id: int,
    payload: schemas.DischargeSummaryCreate,
    actor: Optional[str] = None,
    actor_role: Optional[str] = None,
):
    admission = _get_or_404(db, models.IPAdmission, admission_id, "IP admission")
    summary = (
        db.query(models.DischargeSummary)
        .filter(models.DischargeSummary.admission_id == admission_id)
        .first()
    )
    if summary is None:
        summary = models.DischargeSummary(
            admission_id=admission_id, patient_id=admission.patient_id, status="Draft"
        )
        db.add(summary)

    if summary.status == "Approved":
        raise HTTPException(status_code=409, detail="An approved discharge summary cannot be edited.")

    is_new = summary.id is None
    before = None if is_new else audit.snapshot(summary)
    for key, value in payload.model_dump().items():
        setattr(summary, key, value)
    summary.prepared_by = actor
    summary.prepared_at = _utcnow()
    _stamp_create(summary, actor)
    _stamp_update(summary, actor)
    db.flush()
    _audit_change(
        db, summary,
        action="DISCHARGE_SUMMARY_CREATED" if is_new else "DISCHARGE_SUMMARY_UPDATED",
        entity_type="discharge_summary",
        actor=actor, actor_role=actor_role, patient_id=admission.patient_id,
        before=before,
        details=f"Status {summary.status}",
    )
    db.commit()
    db.refresh(summary)
    return summary


def update_discharge_summary(
    db: Session,
    summary_id: int,
    payload: schemas.DischargeSummaryUpdate,
    actor: Optional[str] = None,
    actor_role: Optional[str] = None,
):
    summary = _get_or_404(db, models.DischargeSummary, summary_id, "Discharge summary")
    data = payload.model_dump(exclude_unset=True)

    if summary.status == "Approved" and data.get("status") != "Approved":
        raise HTTPException(status_code=409, detail="An approved discharge summary cannot be edited.")

    if data.get("status") == "Approved":
        if summary.status != "Final":
            raise HTTPException(
                status_code=409, detail="Only a finalised summary can be approved."
            )
        summary.approved_by = actor
        summary.approved_at = _utcnow()

    before = audit.snapshot(summary)
    previous_status = summary.status
    for key, value in data.items():
        setattr(summary, key, value)
    _stamp_update(summary, actor)
    _audit_change(
        db, summary,
        action="DISCHARGE_SUMMARY_APPROVED" if data.get("status") == "Approved"
               else "DISCHARGE_SUMMARY_UPDATED",
        entity_type="discharge_summary",
        actor=actor, actor_role=actor_role, patient_id=summary.patient_id,
        before=before,
        details=f"{previous_status} -> {summary.status}",
    )
    db.commit()
    db.refresh(summary)
    return summary


def get_discharge_summary(db: Session, admission_id: int):
    return (
        db.query(models.DischargeSummary)
        .filter(models.DischargeSummary.admission_id == admission_id)
        .first()
    )


def get_discharge_summary_by_id(db: Session, summary_id: int) -> models.DischargeSummary:
    return _get_or_404(db, models.DischargeSummary, summary_id, "Discharge summary")


# ============================
# IPD — operational dashboard
# ============================
def get_ipd_stats(db: Session) -> dict:
    today = date.today()
    start, end = _day_bounds(today)

    board = get_bed_board_summary(db)
    current = db.query(func.count(models.IPAdmission.id)).filter(
        models.IPAdmission.status == "Admitted"
    ).scalar() or 0
    admissions_today = (
        db.query(func.count(models.IPAdmission.id))
        .filter(models.IPAdmission.admission_date >= start, models.IPAdmission.admission_date <= end)
        .scalar()
        or 0
    )
    discharges_today = (
        db.query(func.count(models.IPAdmission.id))
        .filter(
            models.IPAdmission.discharge_date >= start,
            models.IPAdmission.discharge_date <= end,
            models.IPAdmission.status.in_(constants.ADMISSION_TERMINAL_STATUSES),
        )
        .scalar()
        or 0
    )

    # Average length of stay over completed admissions.
    completed = (
        db.query(models.IPAdmission.admission_date, models.IPAdmission.discharge_date)
        .filter(
            models.IPAdmission.status.in_(constants.ADMISSION_TERMINAL_STATUSES),
            models.IPAdmission.discharge_date.isnot(None),
        )
        .all()
    )
    stays = [
        (row[1] - row[0]).total_seconds() / 86400.0
        for row in completed
        if row[0] and row[1] and row[1] >= row[0]
    ]

    last_24h = _utcnow() - timedelta(hours=24)
    critical = (
        db.query(func.count(func.distinct(models.NursingNote.admission_id)))
        .join(models.IPAdmission, models.IPAdmission.id == models.NursingNote.admission_id)
        .filter(
            models.NursingNote.is_critical.is_(True),
            models.NursingNote.recorded_at >= last_24h,
            models.IPAdmission.status == "Admitted",
        )
        .scalar()
        or 0
    )

    pending_summaries = (
        db.query(func.count(models.IPAdmission.id))
        .filter(models.IPAdmission.status == "Admitted")
        .filter(
            ~models.IPAdmission.id.in_(
                db.query(models.DischargeSummary.admission_id).filter(
                    models.DischargeSummary.status == "Final"
                )
            )
        )
        .scalar()
        or 0
    )

    active_meds = (
        db.query(func.count(models.MedicationOrder.id))
        .join(models.IPAdmission, models.IPAdmission.id == models.MedicationOrder.admission_id)
        .filter(
            models.MedicationOrder.status == "Active",
            models.IPAdmission.status == "Admitted",
        )
        .scalar()
        or 0
    )

    return {
        "total_beds": board["total_beds"],
        "available_beds": board["available"],
        "occupied_beds": board["occupied"],
        "occupancy_percent": board["occupancy_percent"],
        "current_admissions": int(current),
        "admissions_today": int(admissions_today),
        "discharges_today": int(discharges_today),
        "average_length_of_stay": round(sum(stays) / len(stays), 1) if stays else 0.0,
        "critical_patients": int(critical),
        "pending_discharge_summaries": int(pending_summaries),
        "active_medication_orders": int(active_meds),
    }


def get_bed_occupancy_report(db: Session, days: int = 30) -> List[dict]:
    """Occupancy per ward over a window, derived from the allocation history."""
    wards = db.query(models.Ward).all()
    report = []
    end = _utcnow()
    start = end - timedelta(days=days)

    for ward in wards:
        bed_ids = [
            b.id
            for b in db.query(models.Bed)
            .join(models.Room)
            .filter(models.Room.ward_id == ward.id, models.Bed.is_active.is_(True))
            .all()
        ]
        total_beds = len(bed_ids)
        if total_beds == 0:
            report.append(
                {
                    "ward": ward.name,
                    "ward_type": ward.ward_type,
                    "total_beds": 0,
                    "occupied_now": 0,
                    "occupancy_percent": 0.0,
                    "admissions": 0,
                    "patient_days": 0,
                    "average_stay_days": 0.0,
                }
            )
            continue

        allocations = (
            db.query(models.BedAllocation)
            .filter(
                models.BedAllocation.bed_id.in_(bed_ids),
                models.BedAllocation.allocated_at >= start,
            )
            .all()
        )
        patient_days = 0.0
        for alloc in allocations:
            released = alloc.released_at or end
            patient_days += max((released - alloc.allocated_at).total_seconds() / 86400.0, 0)

        occupied_now = sum(
            1 for b in bed_ids if _open_allocation_for_bed(db, b)
        )
        report.append(
            {
                "ward": ward.name,
                "ward_type": ward.ward_type,
                "total_beds": total_beds,
                "occupied_now": occupied_now,
                "occupancy_percent": round((occupied_now / total_beds) * 100, 1),
                "admissions": len(allocations),
                "patient_days": round(patient_days, 1),
                "average_stay_days": round(patient_days / len(allocations), 1) if allocations else 0.0,
            }
        )
    return report


# ============================
# Staff master
# ============================
def create_staff_member(db: Session, payload: schemas.StaffMemberCreate, hashed_password: str):
    if db.query(models.User).filter(models.User.username == payload.username).first():
        raise HTTPException(status_code=400, detail="Username already registered")
    if payload.employee_code and db.query(models.User).filter(
        models.User.employee_code == payload.employee_code
    ).first():
        raise HTTPException(status_code=400, detail="Employee code already in use")
    if payload.department_id is not None:
        _get_or_404(db, models.Department, payload.department_id, "Department")

    data = payload.model_dump(exclude={"password"})
    user = models.User(**data, hashed_password=hashed_password, is_active=True)
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Username or employee code already exists.")
    db.refresh(user)
    return user


def get_staff_members(
    db: Session,
    role: Optional[str] = None,
    department_id: Optional[int] = None,
    active_only: bool = False,
):
    query = db.query(models.User).filter(models.User.role != constants.PATIENT_ROLE)
    if role:
        query = query.filter(models.User.role == role)
    if department_id:
        query = query.filter(models.User.department_id == department_id)
    if active_only:
        query = query.filter(models.User.is_active.is_(True))
    return query.order_by(models.User.role, models.User.username).all()


def update_staff_member(db: Session, user_id: int, payload: schemas.StaffMemberUpdate):
    user = _get_or_404(db, models.User, user_id, "Staff member")
    if user.role == constants.PATIENT_ROLE:
        raise HTTPException(status_code=422, detail="This account is a patient, not staff.")
    data = payload.model_dump(exclude_unset=True)
    if data.get("employee_code") and db.query(models.User).filter(
        models.User.employee_code == data["employee_code"], models.User.id != user_id
    ).first():
        raise HTTPException(status_code=400, detail="Employee code already in use")
    if data.get("department_id") is not None:
        _get_or_404(db, models.Department, data["department_id"], "Department")
    for key, value in data.items():
        setattr(user, key, value)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Employee code already in use.")
    db.refresh(user)
    return user


def list_nurses(db: Session):
    return (
        db.query(models.User)
        .filter(models.User.role == "Nurse", models.User.is_active.is_(True))
        .order_by(models.User.username)
        .all()
    )


# ============================
# Global search
# ============================
def global_search(db: Session, query: str, limit_per_type: int = 8):
    results = []
    raw = query.strip()
    if not raw:
        return results
    term = f"%{raw.lower()}%"
    is_numeric = raw.isdigit()
    numeric = int(raw) if is_numeric else None

    patients = (
        db.query(models.Patient)
        .filter(
            or_(
                func.lower(models.Patient.name).like(term),
                models.Patient.phone.like(term),
                models.Patient.aadhaar.like(term),
                cast(models.Patient.id, String) == raw,
            )
        )
        .order_by(models.Patient.id.desc())
        .limit(limit_per_type)
        .all()
    )
    for p in patients:
        results.append(
            {
                "type": "patient",
                "id": p.id,
                "patient_id": p.id,
                "patient_name": p.name,
                "detail": f"Age: {p.age}, Gender: {p.gender}, Phone: {p.phone or '-'}",
                "date": p.created_at.strftime("%Y-%m-%d") if p.created_at else None,
                "amount": None,
            }
        )

    if not is_numeric:
        return results

    # Build a patient-name cache so the search does not issue an N+1 query per hit.
    def patient_name(pid):
        p = db.query(models.Patient).filter(models.Patient.id == pid).first()
        return p.name if p else "Unknown"

    for token in (
        db.query(models.OPToken).filter(models.OPToken.token_number == numeric).limit(limit_per_type).all()
    ):
        results.append(
            {
                "type": "op_token",
                "id": token.id,
                "patient_id": token.patient_id,
                "patient_name": patient_name(token.patient_id),
                "detail": f"Token #{token.token_number} | {token.session} | {token.date} | {token.status}",
                "date": str(token.date),
                "amount": token.fee,
            }
        )

    for order in db.query(models.LabOrder).filter(models.LabOrder.id == numeric).limit(limit_per_type).all():
        results.append(
            {
                "type": "lab_order",
                "id": order.id,
                "patient_id": order.patient_id,
                "patient_name": patient_name(order.patient_id),
                "detail": f"Lab Order #{order.id} | {order.status} | {order.priority}",
                "date": order.order_date.strftime("%Y-%m-%d") if order.order_date else None,
                "amount": None,
            }
        )

    for model, kind, label in (
        (models.OPBill, "op_bill", "OP Bill"),
        (models.IPBill, "ip_bill", "IP Bill"),
        (models.PharmacyBill, "pharmacy_bill", "Pharmacy Bill"),
        (models.LabBill, "lab_bill", "Lab Bill"),
    ):
        for bill in db.query(model).filter(model.id == numeric).limit(limit_per_type).all():
            name = patient_name(bill.patient_id) if bill.patient_id else getattr(bill, "patient_name", None) or "Walk-in"
            results.append(
                {
                    "type": kind,
                    "id": bill.id,
                    "patient_id": bill.patient_id,
                    "patient_name": name,
                    "detail": f"{label} #{bill.id} | {bill.payment_mode} | {getattr(bill, 'status', 'OK')}",
                    "date": bill.bill_date.strftime("%Y-%m-%d") if bill.bill_date else None,
                    "amount": bill.total,
                }
            )

    for admission in (
        db.query(models.IPAdmission).filter(models.IPAdmission.id == numeric).limit(limit_per_type).all()
    ):
        results.append(
            {
                "type": "admission",
                "id": admission.id,
                "patient_id": admission.patient_id,
                "patient_name": patient_name(admission.patient_id),
                "detail": f"Admission #{admission.id} | Ward: {admission.ward_number} | {admission.status}",
                "date": admission.admission_date.strftime("%Y-%m-%d") if admission.admission_date else None,
                "amount": None,
            }
        )

    return results


# ============================
# Reports
# ============================
# A cancelled bill is not revenue (and is not counted as a bill raised).
_LAB_BILL_COUNTS = (models.LabBill.status != "Cancelled",)


def _sum_between(db: Session, amount_column, date_column, start: datetime, end: datetime, *filters) -> float:
    """Sum ``amount_column`` over rows where ``date_column`` falls in the window.

    The previous helper filtered on the *amount* column, so every revenue figure
    silently came back as 0.
    """
    return float(
        db.query(func.coalesce(func.sum(amount_column), 0.0))
        .filter(date_column >= start, date_column <= end, *filters)
        .scalar()
        or 0.0
    )


def _count_between(db: Session, model, column, start: datetime, end: datetime, *filters) -> int:
    return int(db.query(func.count(model.id)).filter(column >= start, column <= end, *filters).scalar() or 0)


def get_daily_report(db: Session, report_date: date):
    start, end = _day_bounds(report_date)

    op_revenue = _sum_between(db, models.OPBill.total, models.OPBill.bill_date, start, end)
    ip_revenue = _sum_between(db, models.IPBill.total, models.IPBill.bill_date, start, end)
    pharmacy_revenue = _sum_between(db, models.PharmacyBill.total, models.PharmacyBill.bill_date, start, end)
    lab_revenue = _sum_between(db, models.LabBill.total, models.LabBill.bill_date, start, end, *_LAB_BILL_COUNTS)

    total_bills = (
        _count_between(db, models.OPBill, models.OPBill.bill_date, start, end)
        + _count_between(db, models.IPBill, models.IPBill.bill_date, start, end)
        + _count_between(db, models.PharmacyBill, models.PharmacyBill.bill_date, start, end)
        + _count_between(db, models.LabBill, models.LabBill.bill_date, start, end, *_LAB_BILL_COUNTS)
    )
    total_patients = (
        db.query(func.count(func.distinct(models.OPToken.patient_id)))
        .filter(models.OPToken.date == report_date)
        .scalar()
        or 0
    )
    registered_today = _count_between(db, models.Patient, models.Patient.created_at, start, end)

    return {
        "date": str(report_date),
        "op_revenue": round(op_revenue, 2),
        "ip_revenue": round(ip_revenue, 2),
        "pharmacy_revenue": round(pharmacy_revenue, 2),
        "lab_revenue": round(lab_revenue, 2),
        "total_revenue": round(op_revenue + ip_revenue + pharmacy_revenue + lab_revenue, 2),
        "total_patients": int(max(total_patients, registered_today)),
        "total_bills": int(total_bills),
    }


def get_monthly_report(db: Session, year: int, month: int):
    from calendar import monthrange

    _, days_in_month = monthrange(year, month)
    rows = []
    for day in range(1, days_in_month + 1):
        report = get_daily_report(db, date(year, month, day))
        if report["total_bills"] > 0 or report["total_revenue"] > 0:
            rows.append(report)
    return rows


def _shift_month(year: int, month: int, delta: int):
    index = (year * 12 + (month - 1)) + delta
    return index // 12, index % 12 + 1


def get_yearly_report(db: Session, year: int):
    import calendar

    monthly_data = []
    for month in range(1, 13):
        start, end = _month_bounds(year, month)
        op_rev = _sum_between(db, models.OPBill.total, models.OPBill.bill_date, start, end)
        ip_rev = _sum_between(db, models.IPBill.total, models.IPBill.bill_date, start, end)
        ph_rev = _sum_between(db, models.PharmacyBill.total, models.PharmacyBill.bill_date, start, end)
        lab_rev = _sum_between(db, models.LabBill.total, models.LabBill.bill_date, start, end, *_LAB_BILL_COUNTS)
        bill_count = (
            _count_between(db, models.OPBill, models.OPBill.bill_date, start, end)
            + _count_between(db, models.IPBill, models.IPBill.bill_date, start, end)
            + _count_between(db, models.PharmacyBill, models.PharmacyBill.bill_date, start, end)
            + _count_between(db, models.LabBill, models.LabBill.bill_date, start, end, *_LAB_BILL_COUNTS)
        )
        monthly_data.append(
            {
                "month": f"{calendar.month_name[month]} {year}",
                "op_revenue": round(op_rev, 2),
                "ip_revenue": round(ip_rev, 2),
                "pharmacy_revenue": round(ph_rev, 2),
                "lab_revenue": round(lab_rev, 2),
                "total_revenue": round(op_rev + ip_rev + ph_rev + lab_rev, 2),
                "total_bills": int(bill_count),
            }
        )
    return monthly_data


def get_revenue_breakdown(db: Session, start_date: Optional[date] = None, end_date: Optional[date] = None):
    def total(model, column):
        query = db.query(func.coalesce(func.sum(model.total), 0.0))
        if start_date:
            query = query.filter(column >= datetime.combine(start_date, datetime.min.time()))
        if end_date:
            query = query.filter(column <= datetime.combine(end_date, datetime.max.time()))
        return float(query.scalar() or 0.0)

    op = total(models.OPBill, models.OPBill.bill_date)
    ip = total(models.IPBill, models.IPBill.bill_date)
    ph = total(models.PharmacyBill, models.PharmacyBill.bill_date)
    lab = total(models.LabBill, models.LabBill.bill_date)

    return {
        "op_total": round(op, 2),
        "ip_total": round(ip, 2),
        "pharmacy_total": round(ph, 2),
        "lab_total": round(lab, 2),
        "grand_total": round(op + ip + ph + lab, 2),
    }


def get_doctor_wise_report(db: Session):
    doctors: dict = {}

    def bucket(name):
        key = name or "Unknown"
        return doctors.setdefault(
            key, {"doctor_name": key, "op_bills": 0, "ip_bills": 0, "total_revenue": 0.0}
        )

    for row in (
        db.query(
            models.OPBill.doctor_name,
            func.count(models.OPBill.id),
            func.coalesce(func.sum(models.OPBill.total), 0.0),
        )
        .filter(models.OPBill.doctor_name.isnot(None), models.OPBill.doctor_name != "")
        .group_by(models.OPBill.doctor_name)
        .all()
    ):
        entry = bucket(row[0])
        entry["op_bills"] += row[1]
        entry["total_revenue"] += float(row[2])

    for row in (
        db.query(
            models.IPBill.doctor_name,
            func.count(models.IPBill.id),
            func.coalesce(func.sum(models.IPBill.total), 0.0),
        )
        .filter(models.IPBill.doctor_name.isnot(None), models.IPBill.doctor_name != "")
        .group_by(models.IPBill.doctor_name)
        .all()
    ):
        entry = bucket(row[0])
        entry["ip_bills"] += row[1]
        entry["total_revenue"] += float(row[2])

    for entry in doctors.values():
        entry["total_revenue"] = round(entry["total_revenue"], 2)
    return list(doctors.values())


def get_medicine_sales_report(db: Session):
    data = (
        db.query(
            models.PharmacyBillItem.medicine_name,
            func.sum(models.PharmacyBillItem.quantity),
            func.sum(models.PharmacyBillItem.total_price),
        )
        .group_by(models.PharmacyBillItem.medicine_name)
        .order_by(func.sum(models.PharmacyBillItem.total_price).desc())
        .all()
    )
    return [
        {
            "medicine_name": row[0],
            "total_quantity_sold": int(row[1] or 0),
            "total_revenue": round(float(row[2] or 0.0), 2),
        }
        for row in data
    ]


def get_admission_report(db: Session, status: Optional[str] = None):
    query = db.query(models.IPAdmission)
    if status:
        query = query.filter(models.IPAdmission.status == status)
    return query.order_by(models.IPAdmission.admission_date.desc()).all()


def get_department_wise_report(db: Session):
    data = (
        db.query(
            models.OPBill.department,
            func.count(models.OPBill.id),
            func.coalesce(func.sum(models.OPBill.total), 0.0),
        )
        .filter(models.OPBill.department.isnot(None), models.OPBill.department != "")
        .group_by(models.OPBill.department)
        .all()
    )
    return [
        {"department": row[0], "total_bills": int(row[1]), "total_revenue": round(float(row[2]), 2)}
        for row in data
    ]


def get_patient_report(db: Session, patient_id: int):
    patient = db.query(models.Patient).filter(models.Patient.id == patient_id).first()
    if not patient:
        return None

    op_visits = db.query(func.count(models.OPToken.id)).filter(models.OPToken.patient_id == patient_id).scalar() or 0
    admissions = (
        db.query(func.count(models.IPAdmission.id)).filter(models.IPAdmission.patient_id == patient_id).scalar() or 0
    )
    lab_orders = db.query(func.count(models.LabOrder.id)).filter(models.LabOrder.patient_id == patient_id).scalar() or 0

    def revenue(model, column):
        return float(
            db.query(func.coalesce(func.sum(model.total), 0.0)).filter(column == patient_id).scalar() or 0.0
        )

    breakdown = {
        "op": revenue(models.OPBill, models.OPBill.patient_id),
        "ip": revenue(models.IPBill, models.IPBill.patient_id),
        "pharmacy": revenue(models.PharmacyBill, models.PharmacyBill.patient_id),
        "lab": revenue(models.LabBill, models.LabBill.patient_id),
    }

    return {
        "patient": patient,
        "op_visits": int(op_visits),
        "admissions": int(admissions),
        "lab_orders": int(lab_orders),
        "total_revenue": round(sum(breakdown.values()), 2),
        "breakdown": {k: round(v, 2) for k, v in breakdown.items()},
    }


def get_lab_summary_report(db: Session, start_date: Optional[date] = None, end_date: Optional[date] = None):
    """Aggregate lab activity per test (previously this returned raw legacy reports)."""
    verified_count = func.sum(case((models.LabOrder.status == "Verified", 1), else_=0))
    pending_count = func.sum(case((models.LabOrder.status.in_(("Verified", "Cancelled")), 0), else_=1))

    order_query = (
        db.query(models.LabTestMaster.test_name, func.count(models.LabOrder.id), verified_count, pending_count)
        .join(models.LabTestMaster, models.LabTestMaster.id == models.LabOrder.test_id)
    )

    if start_date:
        order_query = order_query.filter(models.LabOrder.order_date >= datetime.combine(start_date, datetime.min.time()))
    if end_date:
        order_query = order_query.filter(models.LabOrder.order_date <= datetime.combine(end_date, datetime.max.time()))

    rows = order_query.group_by(models.LabTestMaster.test_name).order_by(func.count(models.LabOrder.id).desc()).all()

    bill_query = db.query(
        models.LabBillItem.test_name, func.coalesce(func.sum(models.LabBillItem.price), 0.0)
    ).group_by(models.LabBillItem.test_name)
    revenue_map = {r[0]: float(r[1] or 0.0) for r in bill_query.all()}

    return [
        {
            "test_name": row[0],
            "total_orders": int(row[1] or 0),
            "verified": int(row[2] or 0),
            "pending": int(row[3] or 0),
            "revenue": round(revenue_map.get(row[0], 0.0), 2),
        }
        for row in rows
    ]


# ============================
# Hospital settings
# ============================
def get_hospital_settings(db: Session):
    return {s.key: s.value for s in db.query(models.HospitalSettings).all()}


def update_hospital_settings(db: Session, payload: schemas.HospitalSettingsUpdate, actor: models.User):
    for item in payload.settings:
        existing = (
            db.query(models.HospitalSettings).filter(models.HospitalSettings.key == item.key).first()
        )
        if existing:
            existing.value = item.value
            existing.updated_at = _utcnow()
        else:
            db.add(models.HospitalSettings(key=item.key, value=item.value))
    db.add(
        models.AuditLog(
            user_id=actor.id,
            username=actor.username,
            action="UPDATE_HOSPITAL_SETTINGS",
            details=f"Updated {len(payload.settings)} setting(s)",
        )
    )
    db.commit()
    return {"message": "Settings saved successfully"}


# ============================
# Backup
# ============================
def export_database(db: Session) -> dict:
    """Produce a real, restorable JSON snapshot of the business tables."""

    def rows(model):
        return [
            {c.name: _jsonify(getattr(obj, c.name)) for c in model.__table__.columns}
            for obj in db.query(model).all()
        ]

    models_to_export = [
        models.User,
        models.Patient,
        models.OPToken,
        models.Appointment,
        models.Casesheet,
        models.MedicineStock,
        models.StockTransaction,
        models.PharmacyBill,
        models.PharmacyBillItem,
        models.LabTestMaster,
        models.LabTestParameter,
        models.LabPanelItem,
        models.LabOrder,
        models.LabSample,
        models.LabReport,
        models.LabBill,
        models.LabBillItem,
        models.OPBill,
        models.IPBill,
        models.IPAdmission,
        models.HospitalSettings,
    ]

    payload = {model.__tablename__: rows(model) for model in models_to_export}
    payload["_meta"] = {
        "generated_at": _utcnow().isoformat(),
        "table_counts": {name: len(value) for name, value in payload.items()},
    }
    return payload


def _jsonify(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


# ============================
# Dashboard
# ============================
def get_dashboard_stats(db: Session):
    today = date.today()
    start, end = _day_bounds(today)

    pharma_today = _sum_between(db, models.PharmacyBill.total, models.PharmacyBill.bill_date, start, end)
    lab_today = _sum_between(db, models.LabBill.total, models.LabBill.bill_date, start, end, *_LAB_BILL_COUNTS)
    op_revenue = _sum_between(db, models.OPBill.total, models.OPBill.bill_date, start, end)
    ip_revenue = _sum_between(db, models.IPBill.total, models.IPBill.bill_date, start, end)

    return {
        "today_patients": _count_between(db, models.Patient, models.Patient.created_at, start, end),
        "today_revenue": round(op_revenue + ip_revenue + pharma_today + lab_today, 2),
        "op_count": db.query(func.count(models.OPToken.id)).filter(models.OPToken.date == today).scalar() or 0,
        "ip_count": db.query(func.count(models.IPAdmission.id))
        .filter(models.IPAdmission.status == "Admitted")
        .scalar()
        or 0,
        "lab_count": db.query(func.count(models.LabOrder.id))
        .filter(models.LabOrder.order_date >= start, models.LabOrder.order_date <= end)
        .scalar()
        or 0,
        "medicine_sales": round(pharma_today, 2),
        "lab_revenue": round(lab_today, 2),
        "total_patients": db.query(func.count(models.Patient.id)).scalar() or 0,
        "active_ip": db.query(func.count(models.IPAdmission.id))
        .filter(models.IPAdmission.status == "Admitted")
        .scalar()
        or 0,
        "low_stock_count": db.query(func.count(models.MedicineStock.id))
        .filter(models.MedicineStock.quantity <= models.MedicineStock.min_stock_level)
        .scalar()
        or 0,
    }


def get_dashboard_charts(db: Session):
    today = date.today()

    daily_revenue, monthly_revenue, patient_growth, lab_volume = [], [], [], []

    for offset in range(6, -1, -1):
        day = today - timedelta(days=offset)
        start, end = _day_bounds(day)
        value = (
            _sum_between(db, models.OPBill.total, models.OPBill.bill_date, start, end)
            + _sum_between(db, models.IPBill.total, models.IPBill.bill_date, start, end)
            + _sum_between(db, models.PharmacyBill.total, models.PharmacyBill.bill_date, start, end)
            + _sum_between(db, models.LabBill.total, models.LabBill.bill_date, start, end, *_LAB_BILL_COUNTS)
        )
        daily_revenue.append({"label": day.strftime("%d %b"), "value": round(value, 2)})

    for offset in range(5, -1, -1):
        year, month = _shift_month(today.year, today.month, -offset)
        start, end = _month_bounds(year, month)
        label = start.strftime("%b %Y")
        value = (
            _sum_between(db, models.OPBill.total, models.OPBill.bill_date, start, end)
            + _sum_between(db, models.IPBill.total, models.IPBill.bill_date, start, end)
            + _sum_between(db, models.PharmacyBill.total, models.PharmacyBill.bill_date, start, end)
            + _sum_between(db, models.LabBill.total, models.LabBill.bill_date, start, end, *_LAB_BILL_COUNTS)
        )
        monthly_revenue.append({"label": label, "value": round(value, 2)})
        patient_growth.append(
            {"label": label, "value": float(_count_between(db, models.Patient, models.Patient.created_at, start, end))}
        )
        lab_volume.append(
            {
                "label": label,
                "value": float(
                    _count_between(db, models.LabOrder, models.LabOrder.order_date, start, end)
                ),
            }
        )

    top_meds = (
        db.query(
            models.PharmacyBillItem.medicine_name,
            func.sum(models.PharmacyBillItem.total_price),
        )
        .group_by(models.PharmacyBillItem.medicine_name)
        .order_by(func.sum(models.PharmacyBillItem.total_price).desc())
        .limit(5)
        .all()
    )

    return {
        "daily_revenue": daily_revenue,
        "monthly_revenue": monthly_revenue,
        "patient_growth": patient_growth,
        "medicine_sales": [{"label": r[0], "value": round(float(r[1] or 0.0), 2)} for r in top_meds],
        "lab_volume": lab_volume,
    }


# ============================
# Seed data
# ============================
def seed_data(db: Session):
    """Idempotent demo seed. Safe to call repeatedly."""
    if db.query(models.MedicineStock).first() or db.query(models.LabTestMaster).first():
        return {"message": "Database already seeded or populated."}

    db.add_all(
        [
            models.MedicineStock(name="Paracetamol 650mg", category="Pharmacy", batch_no="B101", quantity=100, unit_price=2.5, min_stock_level=15),
            models.MedicineStock(name="Amoxicillin 500mg", category="Pharmacy", batch_no="B102", quantity=80, unit_price=8.0, min_stock_level=10),
            models.MedicineStock(name="Cetirizine 10mg", category="Pharmacy", batch_no="B103", quantity=200, unit_price=1.2, min_stock_level=20),
            models.MedicineStock(name="Ibuprofen 400mg", category="Pharmacy", batch_no="B104", quantity=120, unit_price=3.0, min_stock_level=15),
            models.MedicineStock(name="Lab Reagent - CBC Kit", category="Lab", batch_no="R201", quantity=15, unit_price=150.0, min_stock_level=3),
            models.MedicineStock(name="Disposable Syringe 5ml", category="Consumable", batch_no="C301", quantity=500, unit_price=5.0, min_stock_level=50),
        ]
    )

    patient = models.Patient(
        name="Arun Kumar", age=45, gender="Male", phone="9876543210", address="Chennai, Tamil Nadu", blood_group="O+"
    )
    db.add(patient)
    db.flush()

    db.add(
        models.OPToken(
            patient_id=patient.id,
            token_number=1,
            session="Morning",
            date=date.today(),
            status="Pending",
            fee=150.0,
            doctor_name="Dr. Demo",
        )
    )

    _seed_lab_catalogue(db)
    db.commit()
    return {"message": "Seed data populated successfully!"}


def _seed_lab_catalogue(db: Session):
    catalogue = [
        {
            "test_code": "CBC",
            "test_name": "Complete Blood Count",
            "category": "Haematology",
            "sample_type": "Blood",
            "container_type": "EDTA Tube",
            "price": 350.0,
            "tat_hours": 6,
            "parameters": [
                ("Haemoglobin", "g/dL", "13 - 17", "13 - 17", "12 - 15", "11 - 14"),
                ("Total WBC Count", "cells/µL", "4000 - 11000", "4000 - 11000", "4000 - 11000", "5000 - 13000"),
                ("Platelet Count", "cells/µL", "150000 - 410000", "150000 - 410000", "150000 - 410000", "150000 - 450000"),
                ("RBC Count", "million/µL", "4.5 - 5.9", "4.5 - 5.9", "4.1 - 5.1", "4.0 - 5.2"),
                ("Haematocrit", "%", "40 - 52", "40 - 52", "36 - 46", "34 - 43"),
            ],
        },
        {
            "test_code": "FBS",
            "test_name": "Fasting Blood Sugar",
            "category": "Biochemistry",
            "sample_type": "Blood",
            "container_type": "Fluoride Tube",
            "price": 120.0,
            "tat_hours": 4,
            "parameters": [("Glucose (Fasting)", "mg/dL", "70 - 100", "70 - 100", "70 - 100", "60 - 100")],
        },
        {
            "test_code": "LIPID",
            "test_name": "Lipid Profile",
            "category": "Biochemistry",
            "sample_type": "Blood",
            "container_type": "Plain Vial",
            "price": 700.0,
            "tat_hours": 24,
            "parameters": [
                ("Total Cholesterol", "mg/dL", "<200", "<200", "<200", "<170"),
                ("Triglycerides", "mg/dL", "<150", "<150", "<150", "<100"),
                ("HDL Cholesterol", "mg/dL", ">40", ">40", ">50", ">45"),
                ("LDL Cholesterol", "mg/dL", "<100", "<100", "<100", "<110"),
            ],
        },
        {
            "test_code": "URINE-R",
            "test_name": "Urine Routine",
            "category": "Pathology",
            "sample_type": "Urine",
            "container_type": "Sterile Container",
            "price": 150.0,
            "tat_hours": 6,
            "parameters": [
                ("Colour", "", "Pale yellow", None, None, None, "Text"),
                ("pH", "", "5.0 - 8.0", None, None, None, "Numeric"),
                ("Albumin", "", "Absent", None, None, None, "Options"),
            ],
        },
    ]

    created = {}
    for item in catalogue:
        params = item.pop("parameters")
        test = models.LabTestMaster(**item)
        db.add(test)
        db.flush()
        for index, param in enumerate(params):
            name, unit, general, male, female, child = param[:6]
            data_type = param[6] if len(param) > 6 else "Numeric"
            test.parameters.append(
                models.LabTestParameter(
                    name=name,
                    unit=unit,
                    data_type=data_type,
                    reference_range=general,
                    normal_range_male=male,
                    normal_range_female=female,
                    normal_range_child=child,
                    display_order=index,
                )
            )
        created[item["test_code"]] = test
    db.flush()

    panel = models.LabTestMaster(
        test_code="PANEL-BASIC",
        test_name="Basic Health Panel",
        category="Pathology",
        sample_type="Blood",
        container_type="Multiple",
        price=1000.0,
        tat_hours=24,
        is_panel=True,
    )
    db.add(panel)
    db.flush()
    for index, code in enumerate(("CBC", "FBS", "LIPID")):
        db.add(models.LabPanelItem(panel_id=panel.id, test_id=created[code].id, display_order=index))


# ===========================================================================
# Patient self-service accounts
# ===========================================================================
def register_patient_account(db: Session, payload: schemas.PatientRegister, hashed_password: str):
    """Create the patient record and its login atomically.

    Both rows are written in one transaction: a half-created account (a login with
    no patient, or vice versa) would be unrecoverable from the UI.
    """
    if db.query(models.User).filter(models.User.username == payload.username).first():
        raise HTTPException(status_code=400, detail="That username is already taken.")

    if payload.email and db.query(models.User).filter(models.User.email == payload.email).first():
        raise HTTPException(status_code=400, detail="An account with that email already exists.")

    # Self-signup never attaches to an existing hospital record, even when the
    # phone number matches: knowing someone's mobile number must not grant access
    # to their reports, prescriptions and bills. A matching record is only noted
    # so staff can verify identity and link it (PUT /users/{id}/link-patient).
    possible_match = (
        db.query(models.Patient).filter(models.Patient.phone == payload.phone).first()
        if payload.phone
        else None
    )
    details = {"self_registered": True}
    if possible_match:
        details["possible_existing_patient_id"] = possible_match.id

    try:
        patient = models.Patient(
            name=payload.name,
            age=payload.age,
            gender=payload.gender,
            phone=payload.phone,
            address=payload.address,
            blood_group=payload.blood_group,
            details=details,
        )
        db.add(patient)
        db.flush()

        user = models.User(
            username=payload.username,
            hashed_password=hashed_password,
            role=constants.PATIENT_ROLE,
            patient_id=patient.id,
            full_name=payload.name,
            email=payload.email,
            phone=payload.phone,
            is_active=True,
        )
        db.add(user)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Username or email is already registered.")

    db.refresh(user)
    db.refresh(patient)
    return user, patient


def link_portal_account_to_patient(db: Session, user_id: int, patient_id: int) -> models.User:
    """Attach a patient login to an existing hospital record after staff verification."""
    user = _get_or_404(db, models.User, user_id, "User")
    if user.role != constants.PATIENT_ROLE:
        raise HTTPException(status_code=400, detail="Only patient accounts can be linked to a patient record.")
    target = _get_or_404(db, models.Patient, patient_id, "Patient")
    other = (
        db.query(models.User)
        .filter(models.User.patient_id == target.id, models.User.id != user.id)
        .first()
    )
    if other:
        raise HTTPException(status_code=409, detail="That patient record already has an online account.")
    user.patient_id = target.id
    db.commit()
    db.refresh(user)
    return user


def touch_last_login(db: Session, user: models.User) -> None:
    user.last_login_at = _utcnow()
    db.commit()


def list_doctors(db: Session):
    """Active staff doctors, for the patient appointment picker."""
    return (
        db.query(models.User)
        .filter(models.User.role == "Doctor", models.User.is_active.is_(True))
        .order_by(models.User.username)
        .all()
    )


def _mask_aadhaar(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    digits = "".join(ch for ch in value if ch.isdigit())
    if len(digits) != 12:
        return "XXXX-XXXX-XXXX"
    return f"XXXX-XXXX-{digits[-4:]}"


def build_portal_profile(patient: models.Patient, user: Optional[models.User] = None) -> dict:
    return {
        "id": patient.id,
        "name": patient.name,
        "age": patient.age,
        "gender": patient.gender,
        "phone": patient.phone,
        "email": (user.email if user else None),
        "address": patient.address,
        "aadhaar_masked": _mask_aadhaar(patient.aadhaar),
        "blood_group": patient.blood_group,
        "username": (user.username if user else None),
        "details": patient.details or {},
        "created_at": patient.created_at,
    }


def update_portal_profile(db: Session, patient: models.Patient, user: models.User, payload: schemas.PortalProfileUpdate):
    data = payload.model_dump(exclude_unset=True)
    if "email" in data:
        new_email = data["email"]
        if new_email:
            clash = (
                db.query(models.User)
                .filter(models.User.email == new_email, models.User.id != user.id)
                .first()
            )
            if clash:
                raise HTTPException(status_code=400, detail="That email is already in use.")
        user.email = new_email
    for field in ("phone", "address", "blood_group"):
        if field in data:
            setattr(patient, field, data[field])
    db.commit()
    db.refresh(patient)
    db.refresh(user)
    return patient, user


# ---------------------------------------------------------------------------
# Portal queries — ALL of these take patient_id from the authenticated account,
# never from the request, so cross-patient reads are impossible by construction.
# ---------------------------------------------------------------------------
def portal_appointments(db: Session, patient_id: int, include_past: bool = True):
    query = (
        db.query(models.Appointment)
        .options(joinedload(models.Appointment.doctor))
        .filter(models.Appointment.patient_id == patient_id)
    )
    if not include_past:
        query = query.filter(models.Appointment.appointment_date >= date.today())
    return query.order_by(models.Appointment.appointment_date.desc(), models.Appointment.time_slot).all()


def serialize_appointment(appointment: models.Appointment) -> dict:
    doctor = appointment.doctor
    return {
        "id": appointment.id,
        "doctor_id": appointment.doctor_id,
        "doctor_name": appointment.doctor_name or (doctor.username if doctor else None),
        "appointment_date": appointment.appointment_date,
        "time_slot": appointment.time_slot,
        "reason": appointment.reason,
        "status": appointment.status,
        "created_at": appointment.created_at,
    }


def available_slots(db: Session, doctor_id: int, appointment_date) -> List[str]:
    """Slots still free for a doctor on a date.

    Mirrors the clash check inside `book_portal_appointment`, so what the client
    is offered is exactly what booking will accept.
    """
    doctor = (
        db.query(models.User)
        .filter(models.User.id == doctor_id, models.User.role == "Doctor")
        .first()
    )
    if doctor is None:
        raise HTTPException(status_code=404, detail="Selected doctor is not available.")

    taken = {
        row[0]
        for row in db.query(models.Appointment.time_slot)
        .filter(
            models.Appointment.doctor_id == doctor_id,
            models.Appointment.appointment_date == appointment_date,
            models.Appointment.status.notin_(("Cancelled", "Completed")),
        )
        .all()
        if row[0] is not None
    }
    return [slot for slot in constants.APPOINTMENT_SLOTS if slot not in taken]


def book_portal_appointment(db: Session, patient_id: int, payload: schemas.PortalAppointmentCreate):
    if payload.time_slot not in constants.APPOINTMENT_SLOTS:
        raise HTTPException(status_code=422, detail="Please choose one of the offered time slots.")

    doctor = None
    if payload.doctor_id is not None:
        doctor = (
            db.query(models.User)
            .filter(models.User.id == payload.doctor_id, models.User.role == "Doctor")
            .first()
        )
        if doctor is None:
            raise HTTPException(status_code=404, detail="Selected doctor is not available.")

    # A patient cannot be in two places at once: the same person may not hold two
    # active appointments at the same date and time, whichever doctor they are with.
    clash = (
        db.query(models.Appointment)
        .filter(
            models.Appointment.patient_id == patient_id,
            models.Appointment.appointment_date == payload.appointment_date,
            models.Appointment.time_slot == payload.time_slot,
            models.Appointment.status.notin_(("Cancelled", "Completed")),
        )
        .first()
    )
    if clash:
        raise HTTPException(
            status_code=409, detail="You already have an appointment booked for that date and time."
        )

    # And prevent two patients taking the same doctor's slot.
    if doctor is not None:
        taken = (
            db.query(models.Appointment)
            .filter(
                models.Appointment.doctor_id == doctor.id,
                models.Appointment.appointment_date == payload.appointment_date,
                models.Appointment.time_slot == payload.time_slot,
                models.Appointment.status.notin_(("Cancelled", "Completed")),
            )
            .first()
        )
        if taken:
            raise HTTPException(
                status_code=409, detail="That slot has just been taken. Please choose another."
            )

    appointment = models.Appointment(
        patient_id=patient_id,
        doctor_id=doctor.id if doctor else None,
        doctor_name=doctor.username if doctor else None,
        appointment_date=payload.appointment_date,
        time_slot=payload.time_slot,
        reason=payload.reason,
        status="Scheduled",
        booked_by="Patient (self-service)",
        details={"source": "portal"},
    )
    db.add(appointment)
    db.commit()
    db.refresh(appointment)
    return appointment


def cancel_portal_appointment(db: Session, patient_id: int, appointment_id: int, reason: Optional[str] = None):
    appointment = (
        db.query(models.Appointment)
        .filter(models.Appointment.id == appointment_id, models.Appointment.patient_id == patient_id)
        .first()
    )
    # 404 rather than 403 so a patient cannot probe for other patients' ids.
    if appointment is None:
        raise HTTPException(status_code=404, detail="Appointment not found.")
    if appointment.status in ("Completed",):
        raise HTTPException(status_code=409, detail="A completed appointment cannot be cancelled.")
    if appointment.status == "Cancelled":
        return appointment
    appointment.status = "Cancelled"
    appointment.cancelled_reason = reason or "Cancelled by patient"
    db.commit()
    db.refresh(appointment)
    return appointment


def portal_prescriptions(db: Session, patient_id: int) -> List[dict]:
    casesheets = (
        db.query(models.Casesheet)
        .filter(models.Casesheet.patient_id == patient_id)
        .order_by(models.Casesheet.date.desc(), models.Casesheet.id.desc())
        .all()
    )
    results = []
    for sheet in casesheets:
        results.append(
            {
                "id": sheet.id,
                "date": sheet.date,
                "doctor_name": sheet.doctor_name,
                "diagnosis": sheet.diagnosis,
                "symptoms": sheet.symptoms,
                "advice": sheet.advice,
                "follow_up_date": sheet.follow_up_date,
                "vitals_bp": sheet.vitals_bp,
                "vitals_pulse": sheet.vitals_pulse,
                "vitals_temp": sheet.vitals_temp,
                "vitals_resp": sheet.vitals_resp,
                "medicines": sheet.prescribed_medicines or [],
                "advised_labs": sheet.prescribed_labs or [],
            }
        )
    return results


def portal_lab_orders(db: Session, patient_id: int) -> List[dict]:
    orders = (
        db.query(models.LabOrder)
        .options(joinedload(models.LabOrder.test), joinedload(models.LabOrder.reports))
        .filter(models.LabOrder.patient_id == patient_id)
        .order_by(models.LabOrder.order_date.desc())
        .all()
    )
    results = []
    for order in orders:
        report = order.reports[0] if order.reports else None
        results.append(
            {
                "id": order.id,
                "test_name": order.test.test_name if order.test else "Unknown test",
                "order_date": order.order_date,
                "status": order.status,
                "priority": order.priority or "Routine",
                "due_at": order.due_at,
                "report_ready": report is not None,
                "report_id": report.id if report else None,
            }
        )
    return results


def portal_lab_reports(db: Session, patient_id: int) -> List[dict]:
    reports = (
        db.query(models.LabReport)
        .filter(models.LabReport.patient_id == patient_id)
        .order_by(models.LabReport.date_conducted.desc())
        .all()
    )
    results = []
    for report in reports:
        rows = report.results_data if isinstance(report.results_data, list) else []
        results.append(
            {
                "id": report.id,
                "order_id": report.order_id,
                "test_name": report.test_name,
                "date_conducted": report.date_conducted,
                "status": report.status or "Final",
                "is_abnormal": bool(report.is_abnormal),
                "reported_by": report.reported_by,
                "verified_by": report.verified_by,
                "verified_at": report.verified_at,
                "interpretation": report.interpretation,
                "results": rows,
            }
        )
    return results


def portal_bills(db: Session, patient_id: int) -> List[dict]:
    bills: List[dict] = []

    for bill in (
        db.query(models.OPBill).filter(models.OPBill.patient_id == patient_id).all()
    ):
        bills.append(
            {
                "id": bill.id,
                "bill_type": "OP",
                "bill_date": bill.bill_date,
                "description": f"OP consultation{f' - {bill.doctor_name}' if bill.doctor_name else ''}",
                "subtotal": bill.subtotal,
                "discount": bill.discount,
                "gst": bill.gst,
                "total": bill.total,
                "payment_mode": bill.payment_mode,
                "status": "Paid",
                "items": [
                    {"name": "Consultation", "amount": bill.consultation_fee},
                    {"name": "Laboratory", "amount": bill.lab_charges},
                    {"name": "Pharmacy", "amount": bill.pharmacy_charges},
                ]
                + list(bill.other_charges or []),
            }
        )

    for bill in db.query(models.IPBill).filter(models.IPBill.patient_id == patient_id).all():
        bills.append(
            {
                "id": bill.id,
                "bill_type": "IP",
                "bill_date": bill.bill_date,
                "description": f"Inpatient stay ({bill.days_stayed} day(s))",
                "subtotal": bill.subtotal,
                "discount": bill.discount,
                "gst": bill.gst,
                "total": bill.total,
                "payment_mode": bill.payment_mode,
                "status": "Paid",
                "items": [
                    {"name": f"Room ({bill.days_stayed} x {bill.room_charge_per_day})", "amount": bill.room_charges},
                    {"name": "Doctor", "amount": bill.doctor_charges},
                    {"name": "Nursing", "amount": bill.nursing_charges},
                    {"name": "Pharmacy", "amount": bill.pharmacy_charges},
                    {"name": "Laboratory", "amount": bill.lab_charges},
                ]
                + list(bill.other_charges or []),
            }
        )

    for bill in (
        db.query(models.PharmacyBill)
        .options(joinedload(models.PharmacyBill.items))
        .filter(models.PharmacyBill.patient_id == patient_id)
        .all()
    ):
        bills.append(
            {
                "id": bill.id,
                "bill_type": "Pharmacy",
                "bill_date": bill.bill_date,
                "description": f"Pharmacy ({len(bill.items)} item(s))",
                "subtotal": bill.subtotal,
                "discount": bill.discount,
                "gst": bill.gst,
                "total": bill.total,
                "payment_mode": bill.payment_mode,
                "status": "Paid",
                "items": [
                    {
                        "name": i.medicine_name,
                        "quantity": i.quantity,
                        "amount": i.total_price,
                    }
                    for i in bill.items
                ],
            }
        )

    for bill in (
        db.query(models.LabBill)
        .options(joinedload(models.LabBill.items))
        .filter(models.LabBill.patient_id == patient_id)
        .all()
    ):
        bills.append(
            {
                "id": bill.id,
                "bill_type": "Laboratory",
                "bill_date": bill.bill_date,
                "description": f"Laboratory ({len(bill.items)} test(s))",
                "subtotal": bill.subtotal or bill.total,
                "discount": bill.discount,
                "gst": bill.gst,
                "total": bill.total,
                "payment_mode": bill.payment_mode,
                "status": bill.status,
                "items": [{"name": i.test_name, "amount": i.price} for i in bill.items],
            }
        )

    bills.sort(key=lambda b: b["bill_date"], reverse=True)
    return bills


def portal_claims(db: Session, patient_id: int):
    return (
        db.query(models.InsuranceClaim)
        .filter(models.InsuranceClaim.patient_id == patient_id)
        .order_by(models.InsuranceClaim.created_at.desc())
        .all()
    )


def portal_policies(db: Session, patient_id: int):
    return (
        db.query(models.InsurancePolicy)
        .filter(models.InsurancePolicy.patient_id == patient_id)
        .order_by(models.InsurancePolicy.id.desc())
        .all()
    )


def portal_documents(db: Session, patient_id: int) -> List[dict]:
    """Everything the patient can keep as a document, newest first."""
    documents: List[dict] = []

    for sheet in db.query(models.Casesheet).filter(models.Casesheet.patient_id == patient_id).all():
        count = len(sheet.prescribed_medicines or [])
        documents.append(
            {
                "type": "prescription",
                "id": sheet.id,
                "title": "Prescription",
                "date": datetime.combine(sheet.date, datetime.min.time()) if sheet.date else sheet.created_at,
                "subtitle": f"{count} medicine(s)" + (f" - {sheet.doctor_name}" if sheet.doctor_name else ""),
                "downloadable": True,
            }
        )

    for report in db.query(models.LabReport).filter(models.LabReport.patient_id == patient_id).all():
        documents.append(
            {
                "type": "lab_report",
                "id": report.id,
                "title": f"Lab report - {report.test_name}",
                "date": report.date_conducted,
                "subtitle": ("Abnormal" if report.is_abnormal else "Normal") + f" - {report.status or 'Final'}",
                "downloadable": True,
            }
        )

    for bill in portal_bills(db, patient_id):
        documents.append(
            {
                "type": "bill",
                "id": bill["id"],
                "title": f"{bill['bill_type']} bill #{bill['id']}",
                "date": bill["bill_date"],
                "subtitle": f"Rs {bill['total']:.2f} - {bill['status']}",
                "downloadable": True,
            }
        )

    for admission in (
        db.query(models.IPAdmission)
        .filter(models.IPAdmission.patient_id == patient_id, models.IPAdmission.status == "Discharged")
        .all()
    ):
        documents.append(
            {
                "type": "discharge",
                "id": admission.id,
                "title": "Discharge summary",
                "date": admission.discharge_date or admission.admission_date,
                "subtitle": f"Ward {admission.ward_number or '-'} - {admission.doctor_in_charge or '-'}",
                "downloadable": True,
            }
        )

    for claim in portal_claims(db, patient_id):
        documents.append(
            {
                "type": "insurance",
                "id": claim.id,
                "title": f"Insurance claim {claim.claim_number}",
                "date": claim.created_at,
                "subtitle": f"{claim.status} - claimed Rs {claim.claimed_amount:.2f}",
                "downloadable": False,
            }
        )

    documents.sort(key=lambda d: d["date"] or datetime.min, reverse=True)
    return documents


def portal_dashboard(db: Session, patient: models.Patient, user: models.User) -> dict:
    today = date.today()
    appointments = portal_appointments(db, patient.id)
    upcoming = [a for a in appointments if a.appointment_date >= today and a.status not in ("Cancelled", "Completed")]
    lab_orders = portal_lab_orders(db, patient.id)
    reports = portal_lab_reports(db, patient.id)
    bills = portal_bills(db, patient.id)
    prescriptions = portal_prescriptions(db, patient.id)
    policies = [p for p in portal_policies(db, patient.id) if p.is_active]

    documents = portal_documents(db, patient.id)

    return {
        "profile": build_portal_profile(patient, user),
        "next_appointment": serialize_appointment(upcoming[-1]) if upcoming else None,
        "upcoming_appointments": len(upcoming),
        "pending_lab_tests": len([o for o in lab_orders if o["status"] not in ("Verified", "Cancelled")]),
        "ready_reports": len([o for o in lab_orders if o["report_ready"]]),
        "abnormal_reports": len([r for r in reports if r["is_abnormal"]]),
        "prescriptions": len(prescriptions),
        "outstanding_bills": len([b for b in bills if (b["status"] or "").lower() in ("pending", "unpaid")]),
        "total_billed": round(sum(b["total"] for b in bills), 2),
        "active_insurance": len(policies),
        "recent_lab_orders": lab_orders[:5],
        "recent_documents": documents[:8],
    }


# ===========================================================================
# Insurance
# ===========================================================================
def create_insurance_policy(db: Session, payload: schemas.InsurancePolicyCreate):
    _require_patient(db, payload.patient_id)
    policy = models.InsurancePolicy(**payload.model_dump())
    db.add(policy)
    db.commit()
    db.refresh(policy)
    return policy


def get_insurance_policies(db: Session, patient_id: Optional[int] = None, active_only: bool = False):
    query = db.query(models.InsurancePolicy)
    if patient_id:
        query = query.filter(models.InsurancePolicy.patient_id == patient_id)
    if active_only:
        query = query.filter(models.InsurancePolicy.is_active.is_(True))
    return query.order_by(models.InsurancePolicy.id.desc()).all()


def update_insurance_policy(db: Session, policy_id: int, payload: schemas.InsurancePolicyUpdate):
    policy = _get_or_404(db, models.InsurancePolicy, policy_id, "Insurance policy")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(policy, key, value)
    db.commit()
    db.refresh(policy)
    return policy


def _next_claim_number(db: Session) -> str:
    year = datetime.utcnow().year
    count = db.query(func.count(models.InsuranceClaim.id)).scalar() or 0
    return f"CLM-{year}-{count + 1:05d}"


_BILL_MODELS = {
    "OP": models.OPBill,
    "IP": models.IPBill,
    "Pharmacy": models.PharmacyBill,
    "Laboratory": models.LabBill,
}


def create_insurance_claim(db: Session, payload: schemas.InsuranceClaimCreate, actor: str):
    _require_patient(db, payload.patient_id)
    if payload.policy_id is not None:
        policy = _get_or_404(db, models.InsurancePolicy, payload.policy_id, "Insurance policy")
        if policy.patient_id != payload.patient_id:
            raise HTTPException(status_code=422, detail="That policy belongs to a different patient.")

    bill_total = None
    if payload.bill_type and payload.bill_id:
        model = _BILL_MODELS.get(payload.bill_type)
        if model is None:
            raise HTTPException(status_code=422, detail="Unknown bill type.")
        bill = db.query(model).filter(model.id == payload.bill_id).first()
        if bill is None:
            raise HTTPException(status_code=404, detail=f"{payload.bill_type} bill not found.")
        if bill.patient_id != payload.patient_id:
            raise HTTPException(status_code=422, detail="That bill belongs to a different patient.")
        bill_total = float(bill.total)

    claimed = payload.claimed_amount or bill_total or 0.0

    claim = models.InsuranceClaim(
        claim_number=_next_claim_number(db),
        patient_id=payload.patient_id,
        policy_id=payload.policy_id,
        bill_type=payload.bill_type,
        bill_id=payload.bill_id,
        claim_type=payload.claim_type,
        treatment_type=payload.treatment_type,
        diagnosis=payload.diagnosis,
        hospital_name=payload.hospital_name,
        admission_date=payload.admission_date,
        discharge_date=payload.discharge_date,
        claimed_amount=claimed,
        status="Draft",
        remarks=payload.remarks,
        created_by=actor,
        updated_by=actor,
    )
    db.add(claim)
    db.commit()
    db.refresh(claim)
    return claim


def get_insurance_claims(
    db: Session,
    patient_id: Optional[int] = None,
    claim_status: Optional[str] = None,
    policy_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 500,
):
    query = db.query(models.InsuranceClaim).options(
        joinedload(models.InsuranceClaim.patient), joinedload(models.InsuranceClaim.policy)
    )
    if patient_id:
        query = query.filter(models.InsuranceClaim.patient_id == patient_id)
    if claim_status:
        query = query.filter(models.InsuranceClaim.status == claim_status)
    if policy_id:
        query = query.filter(models.InsuranceClaim.policy_id == policy_id)
    return (
        query.order_by(models.InsuranceClaim.created_at.desc()).offset(skip).limit(limit).all()
    )


def get_insurance_claim(db: Session, claim_id: int):
    return _get_or_404(db, models.InsuranceClaim, claim_id, "Insurance claim")


def update_insurance_claim(db: Session, claim_id: int, payload: schemas.InsuranceClaimUpdate, actor: str):
    claim = _get_or_404(db, models.InsuranceClaim, claim_id, "Insurance claim")
    if claim.status in ("Settled", "Rejected"):
        raise HTTPException(status_code=409, detail=f"A {claim.status.lower()} claim cannot be edited.")
    data = payload.model_dump(exclude_unset=True)
    if data.get("policy_id") is not None:
        policy = _get_or_404(db, models.InsurancePolicy, data["policy_id"], "Insurance policy")
        if policy.patient_id != claim.patient_id:
            raise HTTPException(status_code=422, detail="That policy belongs to a different patient.")
    for key, value in data.items():
        setattr(claim, key, value)
    claim.updated_by = actor
    db.commit()
    db.refresh(claim)
    return claim


def update_insurance_claim_status(
    db: Session, claim_id: int, payload: schemas.InsuranceClaimStatusUpdate, actor: str
):
    claim = _get_or_404(db, models.InsuranceClaim, claim_id, "Insurance claim")
    if not constants.is_valid_claim_transition(claim.status, payload.status):
        raise HTTPException(
            status_code=409, detail=f"Illegal claim transition {claim.status} -> {payload.status}."
        )

    claim.status = payload.status
    if payload.approved_amount is not None:
        claim.approved_amount = payload.approved_amount
    if payload.patient_payable is not None:
        claim.patient_payable = payload.patient_payable
    elif payload.approved_amount is not None:
        claim.patient_payable = max(claim.claimed_amount - payload.approved_amount, 0.0)
    if payload.rejection_reason:
        claim.rejection_reason = payload.rejection_reason
    if payload.remarks:
        claim.remarks = payload.remarks

    if payload.status == "Submitted" and not claim.submitted_at:
        claim.submitted_at = _utcnow()
    if payload.status == "Settled":
        claim.settled_at = _utcnow()
    if payload.status == "Rejected" and not claim.rejection_reason:
        raise HTTPException(status_code=422, detail="A rejection reason is required.")
    if payload.status in ("Approved", "Partially Approved") and not claim.approved_amount:
        raise HTTPException(status_code=422, detail="An approved amount is required.")

    claim.updated_by = actor
    db.commit()
    db.refresh(claim)
    return claim


def get_insurance_stats(db: Session) -> dict:
    def count(*filters):
        return int(db.query(func.count(models.InsuranceClaim.id)).filter(*filters).scalar() or 0)

    def total(column, *filters):
        return float(
            db.query(func.coalesce(func.sum(column), 0.0)).filter(*filters).scalar() or 0.0
        )

    settled_filter = (models.InsuranceClaim.status == "Settled",)
    open_filter = (
        models.InsuranceClaim.status.in_(("Submitted", "Under Review", "Approved", "Partially Approved")),
    )

    return {
        "total_claims": count(),
        "draft": count(models.InsuranceClaim.status == "Draft"),
        "submitted": count(models.InsuranceClaim.status == "Submitted"),
        "under_review": count(models.InsuranceClaim.status == "Under Review"),
        "approved": count(
            models.InsuranceClaim.status.in_(("Approved", "Partially Approved"))
        ),
        "rejected": count(models.InsuranceClaim.status == "Rejected"),
        "settled": count(models.InsuranceClaim.status == "Settled"),
        "claimed_amount": round(total(models.InsuranceClaim.claimed_amount), 2),
        "approved_amount": round(total(models.InsuranceClaim.approved_amount), 2),
        "settled_amount": round(total(models.InsuranceClaim.approved_amount, *settled_filter), 2),
        "pending_amount": round(total(models.InsuranceClaim.claimed_amount, *open_filter), 2),
        "active_policies": int(
            db.query(func.count(models.InsurancePolicy.id))
            .filter(models.InsurancePolicy.is_active.is_(True))
            .scalar()
            or 0
        ),
    }
