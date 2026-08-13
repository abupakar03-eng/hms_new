
with open('f:\\\\Hospital Soft\\\\backend\\\\crud.py', 'a') as f:
    f.write('''
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
''')

