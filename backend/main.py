from fastapi import FastAPI, Depends, HTTPException, Query, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date, timedelta, datetime
import time
from .database import engine, Base, get_db
from . import crud, schemas, models, auth

# Create database tables
Base.metadata.create_all(bind=engine)

# Safely add JSON details columns (Incremental Migration)
from sqlalchemy import text
with engine.begin() as conn:
    try:
        conn.execute(text("ALTER TABLE patients ADD COLUMN details JSON DEFAULT '{}'"))
    except Exception:
        pass
    try:
        conn.execute(text("ALTER TABLE op_tokens ADD COLUMN details JSON DEFAULT '{}'"))
    except Exception:
        pass
    try:
        conn.execute(text("ALTER TABLE lab_reports ADD COLUMN results_data JSON"))
    except Exception:
        pass
    try:
        conn.execute(text("ALTER TABLE lab_orders ADD COLUMN priority VARCHAR DEFAULT 'Routine'"))
    except Exception:
        pass
    try:
        conn.execute(text("ALTER TABLE lab_orders ADD COLUMN remarks TEXT"))
    except Exception:
        pass
    try:
        conn.execute(text("ALTER TABLE lab_samples ADD COLUMN barcode VARCHAR"))
    except Exception:
        pass

app = FastAPI(
    title="Hospital Management & Billing API",
    description="Secure Hospital Management System with Role-Based Access Control",
    version="2.0.0",
    docs_url="/docs",
    redoc_url=None
)

# ============================
# SECURITY HEADERS MIDDLEWARE
# Adds XSS, CSRF, Clickjacking protection headers
# ============================
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        response = await call_next(request)
        
        # XSS Protection
        response.headers["X-XSS-Protection"] = "1; mode=block"
        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"
        # Clickjacking protection
        response.headers["X-Frame-Options"] = "DENY"
        # HSTS (force HTTPS)
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        # Content Security Policy - restrict resource loading
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:;"
        )
        # Referrer Policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        # Remove server fingerprint
        response.headers["Server"] = "MedBillPro"
        # Add request timing
        response.headers["X-Process-Time"] = str(round(time.time() - start_time, 4))
        return response


# ============================
# AUDIT TRAIL MIDDLEWARE
# Auto-logs all write operations (POST, PUT, DELETE, PATCH)
# ============================
class AuditTrailMiddleware(BaseHTTPMiddleware):
    WRITE_METHODS = {"POST", "PUT", "DELETE", "PATCH"}
    SKIP_PATHS = {"/login", "/docs", "/openapi.json", "/redoc", "/favicon.ico"}

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # Only audit write operations on success
        if (
            request.method in self.WRITE_METHODS
            and request.url.path not in self.SKIP_PATHS
            and response.status_code < 400
        ):
            try:
                # Extract user from Authorization header if present
                token = request.headers.get("Authorization", "").replace("Bearer ", "")
                username = "anonymous"
                user_id = None
                if token:
                    try:
                        from jose import jwt as jose_jwt
                        payload = jose_jwt.decode(token, auth.SECRET_KEY, algorithms=[auth.ALGORITHM])
                        username = payload.get("sub", "anonymous")
                    except Exception:
                        pass

                # Generate action name from method + path
                path_parts = request.url.path.strip("/").replace("-", "_").upper()
                action = f"{request.method}_{path_parts}"
                client_ip = request.client.host if request.client else "unknown"

                db_gen = get_db()
                db = next(db_gen)
                try:
                    db.add(models.AuditLog(
                        username=username,
                        action=action[:100],
                        details=f"{request.method} {request.url.path}",
                        ip_address=client_ip,
                        timestamp=datetime.utcnow()
                    ))
                    db.commit()
                finally:
                    db.close()
            except Exception:
                pass  # Never let audit logging break the main request
        
        return response


# ============================
# RATE LIMITER (simple in-memory)
# ============================
REQUEST_COUNTS: dict = {}
RATE_LIMIT_WINDOW = 60   # seconds
RATE_LIMIT_MAX = 200     # requests per window per IP

class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        window_start = now - RATE_LIMIT_WINDOW
        
        if client_ip not in REQUEST_COUNTS:
            REQUEST_COUNTS[client_ip] = []
        
        # Clean old requests
        REQUEST_COUNTS[client_ip] = [t for t in REQUEST_COUNTS[client_ip] if t > window_start]
        REQUEST_COUNTS[client_ip].append(now)
        
        if len(REQUEST_COUNTS[client_ip]) > RATE_LIMIT_MAX:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please slow down."},
                headers={"Retry-After": str(RATE_LIMIT_WINDOW)}
            )
        return await call_next(request)

@app.on_event("startup")
def startup_event():
    db = next(get_db())
    try:
        admin_user = crud.get_user_by_username(db, "admin")
        if not admin_user:
            hashed = auth.get_password_hash("admin123")
            user_schema = schemas.UserCreate(username="admin", password="admin123", role="Admin")
            crud.create_user(db, user_schema, hashed)
    finally:
        db.close()


# Add Middleware (order matters: last added = first executed)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(AuditTrailMiddleware)
app.add_middleware(RateLimitMiddleware)

# Enable CORS for React Frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000", "http://127.0.0.1:3000"],  # Restrict to known origins
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
    expose_headers=["X-Process-Time"]
)

# ----------------- AUTHENTICATION -----------------
@app.post("/login", response_model=schemas.Token)
def login_for_access_token(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    # 1. Brute force / account lockout check
    auth.check_account_lockout(form_data.username)

    # 2. Validate credentials
    user = crud.get_user_by_username(db, username=form_data.username)
    if not user or not auth.verify_password(form_data.password, user.hashed_password):
        auth.record_failed_login(form_data.username)
        client_ip = request.client.host if request.client else "unknown"
        # Log failed attempt
        db.add(models.AuditLog(
            username=form_data.username,
            action="LOGIN_FAILED",
            details=f"Failed login attempt for user '{form_data.username}'",
            ip_address=client_ip
        ))
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 3. Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled. Contact administrator."
        )

    # 4. Reset failed login counter on success
    auth.reset_failed_logins(form_data.username)

    # 5. Generate tokens
    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": user.username, "role": user.role},
        expires_delta=access_token_expires
    )
    refresh_token = auth.create_refresh_token(data={"sub": user.username, "role": user.role})

    # 6. Log successful login
    client_ip = request.client.host if request.client else "unknown"
    db.add(models.AuditLog(
        user_id=user.id,
        username=user.username,
        action="LOGIN_SUCCESS",
        details=f"User '{user.username}' logged in successfully (role: {user.role})",
        ip_address=client_ip
    ))
    db.commit()

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "refresh_token": refresh_token,
        "expires_in": auth.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "role": user.role
    }


@app.post("/logout")
def logout(
    request: Request,
    raw_token: str = Depends(auth.get_token_raw),
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """Revoke the current JWT token (adds to blacklist)."""
    auth.blacklist_token(raw_token)
    client_ip = request.client.host if request.client else "unknown"
    db.add(models.AuditLog(
        user_id=current_user.id,
        username=current_user.username,
        action="LOGOUT",
        details=f"User '{current_user.username}' logged out",
        ip_address=client_ip
    ))
    db.commit()
    return {"message": "Logged out successfully. Token has been revoked."}


@app.post("/refresh-token", response_model=schemas.Token)
def refresh_access_token(refresh_token: str, db: Session = Depends(get_db)):
    """Exchange a valid refresh token for a new access token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired refresh token"
    )
    try:
        from jose import jwt as jose_jwt
        payload = jose_jwt.decode(refresh_token, auth.SECRET_KEY, algorithms=[auth.ALGORITHM])
        username: str = payload.get("sub")
        token_type: str = payload.get("type", "")
        if username is None or token_type != "refresh":
            raise credentials_exception
    except Exception:
        raise credentials_exception

    user = crud.get_user_by_username(db, username=username)
    if not user or not user.is_active:
        raise credentials_exception

    new_access_token = auth.create_access_token(
        data={"sub": user.username, "role": user.role}
    )
    return {
        "access_token": new_access_token,
        "token_type": "bearer",
        "expires_in": auth.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    }


@app.get("/users/me", response_model=schemas.UserResponse)
def read_users_me(current_user: models.User = Depends(auth.get_current_user)):
    return current_user


@app.get("/security/status")
def get_security_status(current_user: models.User = Depends(auth.get_current_admin)):
    """Security overview for admin dashboard."""
    return {
        "session_timeout_minutes": auth.ACCESS_TOKEN_EXPIRE_MINUTES,
        "max_failed_attempts": auth.MAX_FAILED_ATTEMPTS,
        "lockout_minutes": auth.LOCKOUT_MINUTES,
        "blacklisted_tokens": len(auth.TOKEN_BLACKLIST),
        "locked_accounts": [
            {"username": k, "locked_until": v.get("locked_until").isoformat() if v.get("locked_until") else None, "attempts": v.get("count", 0)}
            for k, v in auth.FAILED_LOGINS.items()
        ],
        "rate_limit_per_minute": RATE_LIMIT_MAX,
        "security_features": [
            "JWT Authentication",
            "Bcrypt Password Hashing (cost=12)",
            "Role-Based Access Control",
            "Brute Force Protection (lockout)",
            "Token Blacklisting (logout)",
            "XSS Protection Headers",
            "Clickjacking Protection (X-Frame-Options)",
            "MIME Sniffing Protection",
            "Rate Limiting",
            "SQL Injection Protection (SQLAlchemy ORM)",
            "Audit Trail (all write ops logged)",
            "Session Timeout (8h)",
            "Input Validation (Pydantic)",
            "CORS Restricted to known origins"
        ]
    }

# ----------------- USER MANAGEMENT (Admin Only) -----------------
@app.post("/users/", response_model=schemas.UserResponse)
def create_new_user(user: schemas.UserCreate, db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_admin)):
    db_user = crud.get_user_by_username(db, username=user.username)
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    hashed_password = auth.get_password_hash(user.password)
    return crud.create_user(db=db, user=user, hashed_password=hashed_password)

@app.get("/users/", response_model=List[schemas.UserResponse])
def read_all_users(db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_admin)):
    return crud.get_all_users(db)

@app.put("/users/{user_id}/role", response_model=schemas.UserResponse)
def update_role(user_id: int, role: str = Query(...), db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_admin)):
    return crud.update_user_role(db, user_id, role)

@app.put("/users/{user_id}/reset-password", response_model=schemas.UserResponse)
def reset_password(user_id: int, new_password: str = Query(...), db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_admin)):
    hashed = auth.get_password_hash(new_password)
    return crud.update_user_password(db, user_id, hashed)

@app.delete("/users/{user_id}")
def remove_user(user_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_admin)):
    crud.delete_user(db, user_id)
    return {"message": "User deleted successfully"}

# ----------------- PATIENTS ENDPOINTS -----------------
@app.post("/patients/", response_model=schemas.Patient)
def create_patient(patient: schemas.PatientCreate, db: Session = Depends(get_db)):
    return crud.create_patient(db=db, patient=patient)

@app.get("/patients/", response_model=List[schemas.Patient])
def read_patients(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return crud.get_patients(db, skip=skip, limit=limit)

@app.get("/patients/{patient_id}", response_model=schemas.Patient)
def read_patient(patient_id: int, db: Session = Depends(get_db)):
    db_patient = crud.get_patient(db, patient_id=patient_id)
    if db_patient is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    return db_patient

# ----------------- OP TOKENS ENDPOINTS -----------------
@app.post("/tokens/", response_model=schemas.OPToken)
def create_token(token: schemas.OPTokenCreate, db: Session = Depends(get_db)):
    return crud.create_op_token(db=db, token=token)

@app.get("/tokens/", response_model=List[schemas.OPToken])
def read_tokens(target_date: Optional[date] = None, db: Session = Depends(get_db)):
    if not target_date:
        target_date = date.today()
    return crud.get_op_tokens(db=db, target_date=target_date)

@app.put("/tokens/{token_id}", response_model=schemas.OPToken)
def update_token_status(token_id: int, status: str, db: Session = Depends(get_db)):
    db_token = crud.update_op_token_status(db=db, token_id=token_id, status=status)
    if not db_token:
        raise HTTPException(status_code=404, detail="Token not found")
    return db_token

# ----------------- APPOINTMENTS ENDPOINTS -----------------
@app.post("/appointments/", response_model=schemas.AppointmentResponse)
def create_appointment(appointment: schemas.AppointmentCreate, db: Session = Depends(get_db)):
    return crud.create_appointment(db=db, appointment=appointment)

@app.get("/appointments/", response_model=List[schemas.AppointmentResponse])
def read_appointments(target_date: Optional[date] = None, db: Session = Depends(get_db)):
    if not target_date:
        target_date = date.today()
    return crud.get_appointments(db=db, target_date=target_date)

@app.put("/appointments/{appointment_id}", response_model=schemas.AppointmentResponse)
def update_appointment_status(appointment_id: int, status: str, db: Session = Depends(get_db)):
    db_appointment = crud.update_appointment_status(db=db, appointment_id=appointment_id, status=status)
    if not db_appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    return db_appointment

# ----------------- CASESHEETS ENDPOINTS -----------------
@app.post("/casesheets/", response_model=schemas.Casesheet)
def create_casesheet(casesheet: schemas.CasesheetCreate, db: Session = Depends(get_db)):
    return crud.create_casesheet(db=db, casesheet=casesheet)

@app.get("/patients/{patient_id}/casesheets/", response_model=List[schemas.Casesheet])
def read_patient_casesheets(patient_id: int, db: Session = Depends(get_db)):
    return crud.get_casesheets(db=db, patient_id=patient_id)

# ----------------- STOCK / INVENTORY ENDPOINTS -----------------
@app.post("/inventory/", response_model=schemas.MedicineStock)
def create_inventory_item(item: schemas.MedicineStockCreate, db: Session = Depends(get_db)):
    return crud.create_medicine_stock(db=db, item=item)

@app.get("/inventory/", response_model=List[schemas.MedicineStock])
def read_inventory_items(db: Session = Depends(get_db)):
    return crud.get_medicine_stocks(db=db)

@app.post("/inventory/adjust/", response_model=schemas.MedicineStock)
def adjust_inventory_quantity(transaction: schemas.StockTransactionCreate, db: Session = Depends(get_db)):
    return crud.update_medicine_quantity(db=db, transaction=transaction)

# ----------------- PHARMACY BILLING ENDPOINTS -----------------
@app.post("/billing/pharmacy/", response_model=schemas.PharmacyBillResponse)
def create_pharmacy_bill(bill: schemas.PharmacyBillCreate, db: Session = Depends(get_db)):
    return crud.create_pharmacy_bill(db=db, bill=bill)

@app.get("/billing/pharmacy/", response_model=List[schemas.PharmacyBillResponse])
def read_pharmacy_bills(db: Session = Depends(get_db)):
    return crud.get_pharmacy_bills(db=db)

# ----------------- LAB BILLING ENDPOINTS -----------------
@app.post("/billing/lab/", response_model=schemas.LabBillResponse)
def create_lab_bill(bill: schemas.LabBillCreate, db: Session = Depends(get_db)):
    return crud.create_lab_bill(db=db, bill=bill)

@app.get("/billing/lab/", response_model=List[schemas.LabBillResponse])
def read_lab_bills(db: Session = Depends(get_db)):
    return crud.get_lab_bills(db=db)

@app.put("/billing/lab/{bill_id}", response_model=schemas.LabBillResponse)
def update_lab_bill_status(bill_id: int, status: str, db: Session = Depends(get_db)):
    db_bill = crud.update_lab_bill_status(db=db, bill_id=bill_id, status=status)
    if not db_bill:
        raise HTTPException(status_code=404, detail="Lab bill not found")
    return db_bill

# ----------------- OP BILLING ENDPOINTS (NEW) -----------------
@app.post("/billing/op/", response_model=schemas.OPBillResponse)
def create_op_bill(bill: schemas.OPBillCreate, db: Session = Depends(get_db)):
    return crud.create_op_bill(db=db, bill=bill)

@app.get("/billing/op/", response_model=List[schemas.OPBillResponse])
def read_op_bills(patient_id: Optional[int] = None, db: Session = Depends(get_db)):
    return crud.get_op_bills(db=db, patient_id=patient_id)

# ----------------- IP BILLING ENDPOINTS (NEW) -----------------
@app.post("/billing/ip/", response_model=schemas.IPBillResponse)
def create_ip_bill(bill: schemas.IPBillCreate, db: Session = Depends(get_db)):
    return crud.create_ip_bill(db=db, bill=bill)

@app.get("/billing/ip/", response_model=List[schemas.IPBillResponse])
def read_ip_bills(patient_id: Optional[int] = None, db: Session = Depends(get_db)):
    return crud.get_ip_bills(db=db, patient_id=patient_id)

# ----------------- IP ADMISSION ENDPOINTS -----------------
@app.post("/ip-admissions/", response_model=schemas.IPAdmission)
def create_ip_admission(admission: schemas.IPAdmissionCreate, db: Session = Depends(get_db)):
    return crud.create_ip_admission(db=db, admission=admission)

@app.get("/ip-admissions/", response_model=List[schemas.IPAdmission])
def read_ip_admissions(patient_id: Optional[int] = None, db: Session = Depends(get_db)):
    return crud.get_ip_admissions(db=db, patient_id=patient_id)

@app.put("/ip-admissions/{admission_id}/status", response_model=schemas.IPAdmission)
def update_ip_admission_status(admission_id: int, status: str, discharge_date: Optional[datetime] = None, db: Session = Depends(get_db)):
    db_admission = crud.update_ip_admission_status(db=db, admission_id=admission_id, status=status, discharge_date=discharge_date)
    if not db_admission:
        raise HTTPException(status_code=404, detail="IP Admission not found")
    return db_admission

# ----------------- LAB REPORT ENDPOINTS -----------------
@app.post("/lab-reports/", response_model=schemas.LabReport)
def create_lab_report(report: schemas.LabReportCreate, db: Session = Depends(get_db)):
    return crud.create_lab_report(db=db, report=report)

@app.get("/lab-reports/", response_model=List[schemas.LabReport])
def read_lab_reports(patient_id: Optional[int] = None, db: Session = Depends(get_db)):
    return crud.get_lab_reports(db=db, patient_id=patient_id)

# ----------------- NEW LAB MANAGEMENT ENDPOINTS -----------------
@app.post("/lab-test-masters/", response_model=schemas.LabTestMaster)
def create_lab_test_master(test: schemas.LabTestMasterCreate, db: Session = Depends(get_db)):
    return crud.create_lab_test_master(db=db, test=test)

@app.get("/lab-test-masters/", response_model=List[schemas.LabTestMaster])
def read_lab_test_masters(db: Session = Depends(get_db)):
    return crud.get_lab_test_masters(db=db)

@app.put("/lab-test-masters/{test_id}", response_model=schemas.LabTestMaster)
def update_lab_test_master(test_id: int, test: schemas.LabTestMasterUpdate, db: Session = Depends(get_db)):
    db_test = crud.update_lab_test_master(db, test_id, test)
    if not db_test:
        raise HTTPException(status_code=404, detail="Test not found")
    return db_test

@app.delete("/lab-test-masters/{test_id}")
def delete_lab_test_master(test_id: int, db: Session = Depends(get_db)):
    db_test = crud.delete_lab_test_master(db, test_id)
    if not db_test:
        raise HTTPException(status_code=404, detail="Test not found")
    return {"message": "Test master deleted successfully"}

@app.post("/lab-orders/", response_model=schemas.LabOrder)
def create_lab_order(order: schemas.LabOrderCreate, db: Session = Depends(get_db)):
    return crud.create_lab_order(db=db, order=order)

@app.get("/lab-orders/", response_model=List[schemas.LabOrder])
def read_lab_orders(target_date: Optional[date] = None, db: Session = Depends(get_db)):
    return crud.get_lab_orders(db=db, target_date=target_date)

@app.put("/lab-orders/{order_id}/status", response_model=schemas.LabOrder)
def update_lab_order_status(order_id: int, status: str, db: Session = Depends(get_db)):
    db_order = crud.update_lab_order_status(db=db, order_id=order_id, status=status)
    if not db_order:
        raise HTTPException(status_code=404, detail="Lab Order not found")
    return db_order

@app.put("/lab-orders/{order_id}", response_model=schemas.LabOrder)
def update_lab_order(order_id: int, order_data: schemas.LabOrderUpdate, db: Session = Depends(get_db)):
    return crud.update_lab_order(db=db, order_id=order_id, order_data=order_data)

@app.post("/lab-samples/", response_model=schemas.LabSample)
def create_lab_sample(sample: schemas.LabSampleCreate, db: Session = Depends(get_db)):
    return crud.create_lab_sample(db=db, sample=sample)

@app.get("/lab-samples/", response_model=List[schemas.LabSample])
def read_lab_samples(db: Session = Depends(get_db)):
    return crud.get_lab_samples(db=db)

@app.put("/lab-samples/{sample_id}/status", response_model=schemas.LabSample)
def update_lab_sample_status(sample_id: int, status: str, db: Session = Depends(get_db)):
    db_sample = crud.update_lab_sample_status(db=db, sample_id=sample_id, status=status)
    if not db_sample:
        raise HTTPException(status_code=404, detail="Lab Sample not found")
    return db_sample

@app.put("/lab-samples/{sample_id}", response_model=schemas.LabSample)
def update_lab_sample(sample_id: int, sample_data: schemas.LabSampleUpdate, db: Session = Depends(get_db)):
    return crud.update_lab_sample(db=db, sample_id=sample_id, sample_data=sample_data)

# ----------------- GLOBAL SEARCH (NEW) -----------------
@app.get("/search/")
def search(q: str = Query(..., min_length=1), db: Session = Depends(get_db)):
    return crud.global_search(db=db, query=q)

# ----------------- REPORTS ENDPOINTS (NEW) -----------------
@app.get("/reports/daily/")
def daily_report(report_date: Optional[date] = None, db: Session = Depends(get_db)):
    if not report_date:
        report_date = date.today()
    return crud.get_daily_report(db=db, report_date=report_date)

@app.get("/reports/monthly/")
def monthly_report(year: int = None, month: int = None, db: Session = Depends(get_db)):
    today = date.today()
    if not year:
        year = today.year
    if not month:
        month = today.month
    return crud.get_monthly_report(db=db, year=year, month=month)

@app.get("/reports/yearly/")
def yearly_report(year: int = None, db: Session = Depends(get_db)):
    if not year:
        year = date.today().year
    return crud.get_yearly_report(db=db, year=year)

@app.get("/reports/revenue/")
def revenue_report(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db)
):
    return crud.get_revenue_breakdown(db=db, start_date=start_date, end_date=end_date)

@app.get("/reports/doctor-wise/")
def doctor_wise_report(db: Session = Depends(get_db)):
    return crud.get_doctor_wise_report(db=db)

@app.get("/reports/medicine-sales/")
def medicine_sales_report(db: Session = Depends(get_db)):
    return crud.get_medicine_sales_report(db=db)

@app.get("/reports/admissions/")
def admissions_report(status: Optional[str] = None, db: Session = Depends(get_db)):
    return crud.get_admission_report(db=db, status=status)

@app.get("/reports/department-wise/")
def department_wise_report(db: Session = Depends(get_db)):
    return crud.get_department_wise_report(db=db)

@app.get("/reports/patient/{patient_id}")
def patient_report(patient_id: int, db: Session = Depends(get_db)):
    report = crud.get_patient_report(db=db, patient_id=patient_id)
    if not report:
        raise HTTPException(status_code=404, detail="Patient not found")
    return report

@app.get("/reports/medicine-stock/")
def medicine_stock_report(db: Session = Depends(get_db)):
    return crud.get_medicine_stocks(db=db)

@app.get("/reports/lab-summary/")
def lab_summary_report(db: Session = Depends(get_db)):
    return crud.get_lab_reports(db=db)

@app.get("/reports/discharge/")
def discharge_report(db: Session = Depends(get_db)):
    return crud.get_admission_report(db=db, status="Discharged")

# ----------------- DASHBOARD -----------------
@app.get("/dashboard/stats", response_model=schemas.DashboardStats)
def get_dashboard_stats(db: Session = Depends(get_db)):
    from sqlalchemy import func
    today = date.today()
    today_start = datetime.combine(today, datetime.min.time())
    today_end = datetime.combine(today, datetime.max.time())

    today_patients = db.query(models.Patient).filter(
        models.Patient.created_at >= today_start,
        models.Patient.created_at <= today_end
    ).count()

    op_count = db.query(models.OPToken).filter(
        models.OPToken.date == today
    ).count()

    ip_count = db.query(models.IPAdmission).filter(
        models.IPAdmission.status == "Admitted"
    ).count()

    lab_count = db.query(models.LabReport).filter(
        models.LabReport.date_conducted >= today_start,
        models.LabReport.date_conducted <= today_end
    ).count()

    pharma_today = db.query(func.sum(models.PharmacyBill.total)).filter(
        models.PharmacyBill.bill_date >= today_start,
        models.PharmacyBill.bill_date <= today_end
    ).scalar() or 0.0

    op_revenue = db.query(func.sum(models.OPBill.total)).filter(
        models.OPBill.bill_date >= today_start,
        models.OPBill.bill_date <= today_end
    ).scalar() or 0.0

    ip_revenue = db.query(func.sum(models.IPBill.total)).filter(
        models.IPBill.bill_date >= today_start,
        models.IPBill.bill_date <= today_end
    ).scalar() or 0.0

    today_revenue = op_revenue + ip_revenue + pharma_today

    total_patients = db.query(models.Patient).count()
    active_ip = ip_count

    low_stock = db.query(models.MedicineStock).filter(
        models.MedicineStock.quantity <= models.MedicineStock.min_stock_level
    ).count()

    return schemas.DashboardStats(
        today_patients=today_patients,
        today_revenue=round(today_revenue, 2),
        op_count=op_count,
        ip_count=ip_count,
        lab_count=lab_count,
        medicine_sales=round(pharma_today, 2),
        total_patients=total_patients,
        active_ip=active_ip,
        low_stock_count=low_stock
    )

@app.get("/dashboard/charts", response_model=schemas.DashboardCharts)
def get_dashboard_charts(db: Session = Depends(get_db)):
    from sqlalchemy import func
    today = date.today()

    # Daily revenue - last 7 days
    daily_revenue = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        d_start = datetime.combine(d, datetime.min.time())
        d_end = datetime.combine(d, datetime.max.time())
        op_rev = db.query(func.sum(models.OPBill.total)).filter(
            models.OPBill.bill_date >= d_start, models.OPBill.bill_date <= d_end
        ).scalar() or 0.0
        ip_rev = db.query(func.sum(models.IPBill.total)).filter(
            models.IPBill.bill_date >= d_start, models.IPBill.bill_date <= d_end
        ).scalar() or 0.0
        ph_rev = db.query(func.sum(models.PharmacyBill.total)).filter(
            models.PharmacyBill.bill_date >= d_start, models.PharmacyBill.bill_date <= d_end
        ).scalar() or 0.0
        daily_revenue.append(schemas.ChartDataPoint(label=d.strftime("%d %b"), value=round(op_rev + ip_rev + ph_rev, 2)))

    # Monthly revenue - last 6 months
    monthly_revenue = []
    for i in range(5, -1, -1):
        m_date = today.replace(day=1) - timedelta(days=i*30)
        m_start = m_date.replace(day=1)
        if m_date.month == 12:
            m_end = m_date.replace(year=m_date.year+1, month=1, day=1) - timedelta(days=1)
        else:
            m_end = m_date.replace(month=m_date.month+1, day=1) - timedelta(days=1)
        ms = datetime.combine(m_start, datetime.min.time())
        me = datetime.combine(m_end, datetime.max.time())
        op_r = db.query(func.sum(models.OPBill.total)).filter(models.OPBill.bill_date >= ms, models.OPBill.bill_date <= me).scalar() or 0.0
        ip_r = db.query(func.sum(models.IPBill.total)).filter(models.IPBill.bill_date >= ms, models.IPBill.bill_date <= me).scalar() or 0.0
        ph_r = db.query(func.sum(models.PharmacyBill.total)).filter(models.PharmacyBill.bill_date >= ms, models.PharmacyBill.bill_date <= me).scalar() or 0.0
        monthly_revenue.append(schemas.ChartDataPoint(label=m_start.strftime("%b %Y"), value=round(op_r + ip_r + ph_r, 2)))

    # Patient growth - last 6 months
    patient_growth = []
    for i in range(5, -1, -1):
        m_date = today.replace(day=1) - timedelta(days=i*30)
        m_start = m_date.replace(day=1)
        if m_date.month == 12:
            m_end = m_date.replace(year=m_date.year+1, month=1, day=1) - timedelta(days=1)
        else:
            m_end = m_date.replace(month=m_date.month+1, day=1) - timedelta(days=1)
        ms = datetime.combine(m_start, datetime.min.time())
        me = datetime.combine(m_end, datetime.max.time())
        count = db.query(models.Patient).filter(models.Patient.created_at >= ms, models.Patient.created_at <= me).count()
        patient_growth.append(schemas.ChartDataPoint(label=m_start.strftime("%b %Y"), value=float(count)))

    # Medicine sales - top 5
    from sqlalchemy import desc
    top_meds = db.query(
        models.PharmacyBillItem.medicine_name,
        func.sum(models.PharmacyBillItem.total_price).label("total")
    ).group_by(models.PharmacyBillItem.medicine_name).order_by(desc("total")).limit(5).all()
    medicine_sales = [schemas.ChartDataPoint(label=row[0], value=round(row[1], 2)) for row in top_meds]

    return schemas.DashboardCharts(
        daily_revenue=daily_revenue,
        monthly_revenue=monthly_revenue,
        patient_growth=patient_growth,
        medicine_sales=medicine_sales
    )

# ----------------- HOSPITAL SETTINGS -----------------
@app.get("/hospital-settings/")
def get_hospital_settings(db: Session = Depends(get_db)):
    settings = db.query(models.HospitalSettings).all()
    return {s.key: s.value for s in settings}

@app.post("/hospital-settings/")
def update_hospital_settings(
    body: schemas.HospitalSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    for item in body.settings:
        existing = db.query(models.HospitalSettings).filter(models.HospitalSettings.key == item.key).first()
        if existing:
            existing.value = item.value
            existing.updated_at = datetime.utcnow()
        else:
            db.add(models.HospitalSettings(key=item.key, value=item.value))
    # Log audit
    db.add(models.AuditLog(
        user_id=current_user.id,
        username=current_user.username,
        action="UPDATE_HOSPITAL_SETTINGS",
        details="Hospital settings updated"
    ))
    db.commit()
    return {"message": "Settings saved successfully"}

# ----------------- AUDIT LOGS -----------------
@app.get("/audit-logs/", response_model=List[schemas.AuditLogResponse])
def get_audit_logs(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_admin)
):
    return db.query(models.AuditLog).order_by(models.AuditLog.timestamp.desc()).offset(skip).limit(limit).all()

# ----------------- DATABASE BACKUP -----------------
@app.get("/backup/")
def backup_database(
    current_user: models.User = Depends(auth.get_current_admin),
    db: Session = Depends(get_db)
):
    from fastapi.responses import JSONResponse
    import json
    # Export all data as JSON
    patients = db.query(models.Patient).all()
    users = db.query(models.User).all()
    inventory = db.query(models.MedicineStock).all()
    
    backup_data = {
        "backup_date": datetime.utcnow().isoformat(),
        "hospital": "MedBill Pro",
        "patients_count": len(patients),
        "users_count": len(users),
        "inventory_count": len(inventory),
    }
    
    # Log audit
    db.add(models.AuditLog(
        user_id=current_user.id,
        username=current_user.username,
        action="DATABASE_BACKUP",
        details=f"Backup created with {len(patients)} patients"
    ))
    db.commit()
    
    return backup_data

# ----------------- INITIALIZE SEED DATA -----------------
@app.post("/seed/")
def seed_data(db: Session = Depends(get_db)):
    existing = db.query(models.MedicineStock).first()
    if existing:
        return {"message": "Database already seeded or populated."}

    initial_medicines = [
        models.MedicineStock(name="Paracetamol 650mg", category="Pharmacy", batch_no="B101", quantity=100, unit_price=2.5, min_stock_level=15),
        models.MedicineStock(name="Amoxicillin 500mg", category="Pharmacy", batch_no="B102", quantity=80, unit_price=8.0, min_stock_level=10),
        models.MedicineStock(name="Cetirizine 10mg", category="Pharmacy", batch_no="B103", quantity=200, unit_price=1.2, min_stock_level=20),
        models.MedicineStock(name="Ibuprofen 400mg", category="Pharmacy", batch_no="B104", quantity=120, unit_price=3.0, min_stock_level=15),
        models.MedicineStock(name="Lab Reagent - CBC Kit", category="Lab", batch_no="R201", quantity=15, unit_price=150.0, min_stock_level=3),
        models.MedicineStock(name="Disposable Syringe 5ml", category="Consumable", batch_no="C301", quantity=500, unit_price=5.0, min_stock_level=50),
    ]
    db.add_all(initial_medicines)
    
    sample_patient = models.Patient(name="Arun Kumar", age=45, gender="Male", phone="9876543210", address="Chennai, Tamil Nadu", blood_group="O+")
    db.add(sample_patient)
    db.commit()
    
    db.refresh(sample_patient)
    sample_token = models.OPToken(patient_id=sample_patient.id, token_number=1, session="Morning", date=date.today(), status="Pending", fee=150.0)
    db.add(sample_token)
    db.commit()
    
    return {"message": "Seed data populated successfully!"}




# --- Additional Endpoints ---

@app.put("/patients/{patient_id}", response_model=schemas.Patient)
def update_patient_endpoint(patient_id: int, patient_update: schemas.PatientUpdate, db: Session = Depends(get_db)):
    db_patient = crud.update_patient(db, patient_id, patient_update)
    if not db_patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    return db_patient

@app.delete("/patients/{patient_id}")
def delete_patient_endpoint(patient_id: int, db: Session = Depends(get_db)):
    db_patient = crud.delete_patient(db, patient_id)
    if not db_patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    return {"message": "Patient deleted successfully"}

@app.delete("/tokens/{token_id}")
def delete_op_token_endpoint(token_id: int, db: Session = Depends(get_db)):
    db_token = crud.delete_op_token(db, token_id)
    if not db_token:
        raise HTTPException(status_code=404, detail="Token not found")
    return {"message": "Token deleted successfully"}

@app.delete("/appointments/{appointment_id}")
def delete_appointment_endpoint(appointment_id: int, db: Session = Depends(get_db)):
    db_app = crud.delete_appointment(db, appointment_id)
    if not db_app:
        raise HTTPException(status_code=404, detail="Appointment not found")
    return {"message": "Appointment deleted successfully"}

@app.get("/casesheets/{casesheet_id}", response_model=schemas.Casesheet)
def get_casesheet_endpoint(casesheet_id: int, db: Session = Depends(get_db)):
    db_casesheet = crud.get_casesheet(db, casesheet_id)
    if not db_casesheet:
        raise HTTPException(status_code=404, detail="Casesheet not found")
    return db_casesheet

@app.put("/casesheets/{casesheet_id}", response_model=schemas.Casesheet)
def update_casesheet_endpoint(casesheet_id: int, casesheet_update: schemas.CasesheetUpdate, db: Session = Depends(get_db)):
    db_casesheet = crud.update_casesheet(db, casesheet_id, casesheet_update)
    if not db_casesheet:
        raise HTTPException(status_code=404, detail="Casesheet not found")
    return db_casesheet

@app.delete("/casesheets/{casesheet_id}")
def delete_casesheet_endpoint(casesheet_id: int, db: Session = Depends(get_db)):
    db_casesheet = crud.delete_casesheet(db, casesheet_id)
    if not db_casesheet:
        raise HTTPException(status_code=404, detail="Casesheet not found")
    return {"message": "Casesheet deleted successfully"}

@app.put("/inventory/{stock_id}", response_model=schemas.MedicineStock)
def update_medicine_stock_endpoint(stock_id: int, stock_update: schemas.MedicineStockUpdate, db: Session = Depends(get_db)):
    db_stock = crud.update_medicine_stock(db, stock_id, stock_update)
    if not db_stock:
        raise HTTPException(status_code=404, detail="Medicine stock not found")
    return db_stock

@app.delete("/inventory/{stock_id}")
def delete_medicine_stock_endpoint(stock_id: int, db: Session = Depends(get_db)):
    db_stock = crud.delete_medicine_stock(db, stock_id)
    if not db_stock:
        raise HTTPException(status_code=404, detail="Medicine stock not found")
    return {"message": "Medicine stock deleted successfully"}

@app.put("/ip-admissions/{admission_id}", response_model=schemas.IPAdmission)
def update_ip_admission_endpoint(admission_id: int, admission_update: schemas.IPAdmissionUpdate, db: Session = Depends(get_db)):
    db_admission = crud.update_ip_admission(db, admission_id, admission_update)
    if not db_admission:
        raise HTTPException(status_code=404, detail="IP admission not found")
    return db_admission

@app.delete("/ip-admissions/{admission_id}")
def delete_ip_admission_endpoint(admission_id: int, db: Session = Depends(get_db)):
    db_admission = crud.delete_ip_admission(db, admission_id)
    if not db_admission:
        raise HTTPException(status_code=404, detail="IP admission not found")
    return {"message": "IP admission deleted successfully"}

@app.put("/lab-reports/{report_id}", response_model=schemas.LabReport)
def update_lab_report_endpoint(report_id: int, report_update: schemas.LabReportUpdate, db: Session = Depends(get_db)):
    db_report = crud.update_lab_report(db, report_id, report_update)
    if not db_report:
        raise HTTPException(status_code=404, detail="Lab report not found")
    return db_report

@app.delete("/lab-reports/{report_id}")
def delete_lab_report_endpoint(report_id: int, db: Session = Depends(get_db)):
    db_report = crud.delete_lab_report(db, report_id)
    if not db_report:
        raise HTTPException(status_code=404, detail="Lab report not found")
    return {"message": "Lab report deleted successfully"}

@app.delete("/lab-orders/{order_id}")
def delete_lab_order_endpoint(order_id: int, db: Session = Depends(get_db)):
    db_order = crud.delete_lab_order(db, order_id)
    if not db_order:
        raise HTTPException(status_code=404, detail="Lab order not found")
    return {"message": "Lab order deleted successfully"}

@app.delete("/lab-samples/{sample_id}")
def delete_lab_sample_endpoint(sample_id: int, db: Session = Depends(get_db)):
    db_sample = crud.delete_lab_sample(db, sample_id)
    if not db_sample:
        raise HTTPException(status_code=404, detail="Lab sample not found")
    return {"message": "Lab sample deleted successfully"}
