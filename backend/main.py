"""FastAPI application entrypoint.

Security model
--------------
``AuthGuardMiddleware`` denies **every** request that is not explicitly listed in
``PUBLIC_PATHS``. The previous revision protected only four admin endpoints, so
anyone who could reach the port could read and delete patient records, lab
results and bills without a token. Individual routes additionally declare
``Depends(require_roles(...))`` for role-level restrictions.
"""

import logging
import re
import time
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from typing import List, Optional

from fastapi import Body, Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware

from . import auth, constants, crud, models, schemas, audit
from .config import settings
from .database import SessionLocal, engine, get_db, run_migrations
from .migrations import run_alembic_upgrade

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("hospital_os")

CORS_ORIGINS = settings.cors_origin_list


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Refuse to start a misconfigured production instance rather than failing open.
    problems = settings.validate_for_production()
    if problems:
        for problem in problems:
            logger.error("Configuration problem: %s", problem)
        raise RuntimeError(
            "Refusing to start: production configuration is invalid. See the errors above."
        )

    alembic_applied = run_alembic_upgrade(engine)
    if alembic_applied:
        logger.info("Alembic migrations applied: %s", ", ".join(alembic_applied))

    # Legacy schema sync for databases created before Alembic was introduced.
    applied = run_migrations(engine)
    if applied:
        logger.info("Applied %d legacy schema change(s) at startup", len(applied))

    _bootstrap_admin()
    yield


def _bootstrap_admin():
    """Create the default administrator if no users exist.

    Reads ``ADMIN_PASSWORD`` from the environment; the well-known default is only
    used for a brand new database and a warning is emitted so it cannot go
    unnoticed in production.
    """
    db = SessionLocal()
    try:
        if db.query(models.User).count() == 0:
            password = settings.admin_password or "Admin@123"
            if not settings.admin_password:
                logger.warning(
                    "No users found. Created default administrator 'admin' with password '%s'. "
                    "Change it immediately (POST /users/me/password).",
                    password,
                )
            db.add(
                models.User(
                    username="admin",
                    hashed_password=auth.get_password_hash(password),
                    role="Admin",
                    is_active=True,
                )
            )
            db.commit()
    finally:
        db.close()


app = FastAPI(
    title=settings.app_name,
    description="Secure Hospital Management System with Role-Based Access Control",
    version=settings.app_version,
    docs_url="/docs",
    redoc_url=None,
    lifespan=lifespan,
)


# ============================
# Authentication guard
# ============================
class AuthGuardMiddleware(BaseHTTPMiddleware):
    """Deny-by-default authentication for the whole API surface."""

    PUBLIC_PATHS = {
        "/login",
        # /refresh-token authenticates with the refresh token itself, so it cannot
        # require an access token.
        "/refresh-token",
        "/health",
        "/docs",
        "/openapi.json",
        "/redoc",
        "/favicon.ico",
        # Patient self-signup must be reachable before any token exists.
        "/portal/register",
        # Static shell of the bundled frontend (see the StaticFiles mount at the
        # bottom of this module). These serve the login screen itself; every API
        # route stays behind the token check.
        "/",
        "/index.html",
        "/manifest.webmanifest",
        "/vite.svg",
    }
    PUBLIC_PREFIXES = ("/docs/", "/static/", "/assets/")

    # A self-service patient account may only reach the portal plus its own
    # session-management endpoints. Everything else is hospital staff territory.
    PATIENT_ALLOWED_EXACT = {
        "/users/me",
        "/users/me/password",
        "/logout",
        "/health",
    }
    PATIENT_ALLOWED_PREFIXES = ("/portal/",)

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if request.method == "OPTIONS" or path in self.PUBLIC_PATHS or path.startswith(self.PUBLIC_PREFIXES):
            return await call_next(request)

        header = request.headers.get("Authorization", "")
        token = header[7:].strip() if header.lower().startswith("bearer ") else ""

        db = SessionLocal()
        try:
            user = auth.authenticate_token(db, token)
        except HTTPException as exc:
            return JSONResponse(
                status_code=exc.status_code,
                content={"detail": exc.detail},
                headers=exc.headers or {},
            )
        except Exception:  # pragma: no cover - defensive
            logger.exception("Authentication failed for %s %s", request.method, path)
            return JSONResponse(status_code=401, content={"detail": "Could not validate credentials"})
        finally:
            db.close()

        # ---- role surface enforcement -------------------------------------
        is_patient = user.role == constants.PATIENT_ROLE
        is_portal_path = path.startswith(self.PATIENT_ALLOWED_PREFIXES)

        if is_patient and not (is_portal_path or path in self.PATIENT_ALLOWED_EXACT):
            return JSONResponse(
                status_code=403,
                content={
                    "detail": "Patient accounts can only access their own portal. "
                    "Hospital staff should use a staff account."
                },
            )
        if not is_patient and is_portal_path:
            return JSONResponse(
                status_code=403,
                content={"detail": "The patient portal is only available to patient accounts."},
            )

        if not is_patient:
            allowed = required_staff_roles(request.method, path)
            if allowed is not None and user.role not in allowed:
                return JSONResponse(
                    status_code=403,
                    content={
                        "detail": (
                            f"Your role ({user.role}) cannot perform this action. "
                            f"Permitted: {', '.join(allowed)}."
                        )
                    },
                )

        request.state.user = user
        request.state.username = user.username
        return await call_next(request)


# ============================
# Audit trail
# ============================
class AuditTrailMiddleware(BaseHTTPMiddleware):
    """Record every successful mutating request."""

    WRITE_METHODS = {"POST", "PUT", "DELETE", "PATCH"}
    SKIP_PATHS = {"/login", "/docs", "/openapi.json", "/redoc", "/favicon.ico", "/logout"}

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        if (
            request.method in self.WRITE_METHODS
            and request.url.path not in self.SKIP_PATHS
            and response.status_code < 400
        ):
            db = SessionLocal()
            try:
                username = getattr(request.state, "username", None) or "anonymous"
                client_ip = request.client.host if request.client else "unknown"
                action = f"{request.method}_{request.url.path.strip('/').replace('-', '_').upper()}"
                db.add(
                    models.AuditLog(
                        username=username,
                        action=action[:100],
                        details=f"{request.method} {request.url.path}"[:500],
                        ip_address=client_ip,
                        timestamp=datetime.utcnow(),
                    )
                )
                db.commit()
            except Exception:  # never let auditing break the request
                db.rollback()
                logger.exception("Audit logging failed")
            finally:
                db.close()

        return response


# ============================
# Rate limiting
# ============================
RATE_LIMIT_WINDOW = settings.rate_limit_window_seconds
RATE_LIMIT_MAX = settings.rate_limit_max_requests
RATE_LIMIT_BUCKETS: dict = {}
RATE_LIMIT_MAX_BUCKETS = 10_000


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        window_start = now - RATE_LIMIT_WINDOW

        hits = [t for t in RATE_LIMIT_BUCKETS.get(client_ip, ()) if t > window_start]
        hits.append(now)
        RATE_LIMIT_BUCKETS[client_ip] = hits

        # Bound the table so a spray of spoofed/rotating IPs cannot exhaust memory.
        if len(RATE_LIMIT_BUCKETS) > RATE_LIMIT_MAX_BUCKETS:
            for key in [k for k, v in RATE_LIMIT_BUCKETS.items() if not v or v[-1] <= window_start]:
                RATE_LIMIT_BUCKETS.pop(key, None)

        if len(hits) > RATE_LIMIT_MAX:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please slow down."},
                headers={"Retry-After": str(RATE_LIMIT_WINDOW)},
            )
        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.time()
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        response.headers["X-Process-Time"] = f"{time.time() - start:.4f}"
        # Swagger UI and the built React bundle both need inline styles; scripts
        # are still restricted to same-origin.
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: blob:; font-src 'self' data:; connect-src 'self'"
        )
        response.headers["Server"] = "MedBillPro"
        return response


# ============================
# Staff role policy
# ============================
# Declarative "who may write what" table, evaluated top to bottom, first match wins.
# Reads are deliberately open to every staff role: a doctor needs the patient list,
# the lab needs the case sheet, the billing desk needs the lab orders. What is
# restricted is *authoring* in another team's module.
ADMIN = ("Admin",)
PHARMACY = ("Admin", "Pharmacy")
BILLING = ("Admin", "Billing", "Receptionist")
LAB = ("Admin", "Laboratory", "Doctor")
# Ward work: doctors prescribe and nurse/administer, so both need write access.
IPD_CLINICAL = ("Admin", "Doctor", "Nurse")
IPD_ADMIN = ("Admin",)

ROLE_POLICY = (
    # path prefix, allowed roles, methods it applies to
    ("/users/me/password", None, {"POST"}),          # anyone may change their own password
    ("/users", ADMIN, {"POST", "PUT", "PATCH", "DELETE"}),
    ("/audit-logs", ADMIN, {"POST", "PUT", "PATCH", "DELETE"}),
    ("/backup", ADMIN, {"GET", "POST"}),
    ("/seed", ADMIN, {"POST"}),
    ("/hospital-settings", ADMIN, {"POST", "PUT", "PATCH", "DELETE"}),
    ("/security", ADMIN, {"GET", "POST", "PUT", "PATCH", "DELETE"}),
    ("/insurance", ("Admin", "Insurance"), {"POST", "PUT", "PATCH", "DELETE"}),
    ("/inventory", PHARMACY, {"POST", "PUT", "PATCH", "DELETE"}),
    # The pharmacy counter dispenses and raises its own point-of-sale bill; the
    # billing team handles OP/IP invoices, not the dispensary.
    ("/billing/pharmacy", PHARMACY, {"POST", "PUT", "PATCH", "DELETE"}),
    ("/billing/op", BILLING, {"POST", "PUT", "PATCH", "DELETE"}),
    ("/billing/ip", BILLING, {"POST", "PUT", "PATCH", "DELETE"}),
    ("/billing/lab", ("Admin", "Billing", "Receptionist", "Laboratory"), {"POST", "PUT", "PATCH", "DELETE"}),
    ("/lab-test-masters", ("Admin", "Laboratory"), {"POST", "PUT", "PATCH", "DELETE"}),
    ("/lab-orders", LAB, {"POST", "PUT", "PATCH", "DELETE"}),
    ("/lab-samples", LAB, {"POST", "PUT", "PATCH", "DELETE"}),
    ("/lab-reports", LAB, {"POST", "PUT", "PATCH", "DELETE"}),
    # --- inpatient -------------------------------------------------------
    ("/staff", ADMIN, {"POST", "PUT", "PATCH", "DELETE"}),
    ("/departments", IPD_ADMIN, {"POST", "PUT", "PATCH", "DELETE"}),
    ("/wards", IPD_ADMIN, {"POST", "PUT", "PATCH", "DELETE"}),
    ("/rooms", IPD_ADMIN, {"POST", "PUT", "PATCH", "DELETE"}),
    ("/beds", IPD_ADMIN, {"POST", "PUT", "PATCH", "DELETE"}),
    ("/ipd/discharge", ("Admin", "Doctor"), {"POST", "PUT", "PATCH", "DELETE"}),
    ("/ipd", IPD_CLINICAL, {"POST", "PUT", "PATCH", "DELETE"}),
    # Clinical charting on an admission is not front-desk work: the generic
    # /ip-admissions rule below would otherwise let Receptionist write orders.
    (re.compile(r"^/ip-admissions/[^/]+/(nursing-notes|medications)(/|$)"), IPD_CLINICAL, {"POST", "PUT", "PATCH", "DELETE"}),
    (re.compile(r"^/ip-admissions/[^/]+/discharge-summary(/|$)"), ("Admin", "Doctor"), {"POST", "PUT", "PATCH", "DELETE"}),
    ("/ip-admissions", ("Admin", "Doctor", "Nurse", "Receptionist"), {"POST", "PUT", "PATCH", "DELETE"}),
)


def required_staff_roles(method: str, path: str):
    """Return the roles allowed to perform ``method path``, or None for any staff."""
    for rule, roles, methods in ROLE_POLICY:
        if method not in methods:
            continue
        matched = rule.match(path) if isinstance(rule, re.Pattern) else path.startswith(rule)
        if matched:
            return roles
    return None


# Middleware order: last added runs first.
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(AuditTrailMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(AuthGuardMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
    expose_headers=["X-Process-Time"],
)


# ============================
# Health & auth
# ============================
@app.get("/health", tags=["system"])
def health():
    return {"status": "ok", "version": app.version}


@app.post("/login", response_model=schemas.Token, tags=["auth"])
def login_for_access_token(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    client_ip = request.client.host if request.client else "unknown"
    auth.check_account_lockout(form_data.username, client_ip)

    user = crud.get_user_by_username(db, username=form_data.username)
    if not user or not auth.verify_password(form_data.password, user.hashed_password):
        auth.record_failed_login(form_data.username, client_ip)
        db.add(
            models.AuditLog(
                username=form_data.username,
                action="LOGIN_FAILED",
                details=f"Failed login attempt for user '{form_data.username}'",
                ip_address=client_ip,
            )
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled. Contact administrator.")

    auth.reset_failed_logins(form_data.username, client_ip)
    user.last_login_at = datetime.utcnow()

    access_token = auth.create_access_token(
        data={"sub": user.username, "role": user.role},
        expires_delta=timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    refresh_token = auth.create_refresh_token(data={"sub": user.username, "role": user.role})

    db.add(
        models.AuditLog(
            user_id=user.id,
            username=user.username,
            action="LOGIN_SUCCESS",
            details=f"User '{user.username}' logged in (role: {user.role})",
            ip_address=client_ip,
        )
    )
    db.commit()

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "refresh_token": refresh_token,
        "expires_in": auth.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "role": user.role,
    }


@app.post("/logout", response_model=schemas.MessageResponse, tags=["auth"])
def logout(
    request: Request,
    body: Optional[schemas.LogoutRequest] = Body(None),
    raw_token: str = Depends(auth.get_token_raw),
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    auth.blacklist_token(db, raw_token, username=current_user.username)
    # Revoke the session's refresh token too; otherwise it keeps minting new
    # access tokens after "logout". Only the caller's own token is accepted.
    if body and body.refresh_token:
        try:
            refresh_payload = auth.decode_token(body.refresh_token, "refresh")
        except HTTPException:
            refresh_payload = None  # already expired/invalid: nothing to revoke
        if refresh_payload and refresh_payload.get("sub") == current_user.username:
            auth.blacklist_token(db, body.refresh_token, username=current_user.username)
    client_ip = request.client.host if request.client else "unknown"
    db.add(
        models.AuditLog(
            user_id=current_user.id,
            username=current_user.username,
            action="LOGOUT",
            details=f"User '{current_user.username}' logged out",
            ip_address=client_ip,
        )
    )
    db.commit()
    return {"message": "Logged out successfully. Token has been revoked."}


@app.post("/refresh-token", response_model=schemas.Token, tags=["auth"])
def refresh_access_token(
    refresh_token: Optional[str] = Query(None, description="Deprecated: prefer the JSON body."),
    body: Optional[schemas.RefreshRequest] = Body(None),
    db: Session = Depends(get_db),
):
    """Exchange a refresh token for a new access token.

    The token is still accepted as a query string for backwards compatibility with
    the existing frontend, but the body form is preferred because query strings
    end up in access logs and proxy history.
    """
    token = (body.refresh_token if body else None) or refresh_token
    user = auth.authenticate_refresh_token(db, token)

    return {
        "access_token": auth.create_access_token(data={"sub": user.username, "role": user.role}),
        "token_type": "bearer",
        "refresh_token": token,
        "expires_in": auth.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "role": user.role,
    }


@app.get("/users/me", response_model=schemas.UserResponse, tags=["auth"])
def read_users_me(current_user: models.User = Depends(auth.get_current_user)):
    return current_user


# ============================
# Patient portal
# ============================
@app.post("/portal/register", response_model=schemas.Token, tags=["portal"])
def register_patient_account(payload: schemas.PatientRegister, request: Request, db: Session = Depends(get_db)):
    """Public self-signup: creates the patient record and its login, then signs in.

    The account is created with the Patient role and can only ever reach
    ``/portal/*``, where every query is scoped to its own ``patient_id``.
    """
    auth.assert_password_strength(payload.password)

    user, patient = crud.register_patient_account(db, payload, auth.get_password_hash(payload.password))

    client_ip = request.client.host if request.client else "unknown"
    db.add(
        models.AuditLog(
            user_id=user.id,
            username=user.username,
            action="PATIENT_SELF_REGISTER",
            details=f"Patient #{patient.id} ({patient.name}) self-registered",
            ip_address=client_ip,
        )
    )
    db.commit()

    return {
        "access_token": auth.create_access_token(data={"sub": user.username, "role": user.role}),
        "token_type": "bearer",
        "refresh_token": auth.create_refresh_token(data={"sub": user.username, "role": user.role}),
        "expires_in": auth.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "role": user.role,
    }


@app.get("/portal/me", response_model=schemas.PortalProfile, tags=["portal"])
def portal_me(
    patient: models.Patient = Depends(auth.get_current_patient),
    current_user: models.User = Depends(auth.get_current_user),
):
    return crud.build_portal_profile(patient, current_user)


@app.put("/portal/me", response_model=schemas.PortalProfile, tags=["portal"])
def portal_update_me(
    payload: schemas.PortalProfileUpdate,
    patient: models.Patient = Depends(auth.get_current_patient),
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    patient, user = crud.update_portal_profile(db, patient, current_user, payload)
    return crud.build_portal_profile(patient, user)


@app.get("/portal/dashboard", response_model=schemas.PortalDashboard, tags=["portal"])
def portal_dashboard(
    patient: models.Patient = Depends(auth.get_current_patient),
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    return crud.portal_dashboard(db, patient, current_user)


@app.get("/portal/doctors", response_model=List[schemas.PortalDoctor], tags=["portal"])
def portal_doctors(db: Session = Depends(get_db), patient: models.Patient = Depends(auth.get_current_patient)):
    doctors = crud.list_doctors(db)
    departments = {
        d.id: d.name for d in db.query(models.Department).all()
    }
    return [
        {
            "id": d.id,
            "name": d.full_name or d.username,
            "department": departments.get(d.department_id),
            "specialization": d.specialization,
            "consultation_fee": float(d.consultation_fee) if d.consultation_fee is not None else None,
        }
        for d in doctors
    ]


@app.get("/portal/slots", response_model=List[str], tags=["portal"])
def portal_slots(
    doctor_id: Optional[int] = None,
    appointment_date: Optional[date] = None,
    patient: models.Patient = Depends(auth.get_current_patient),
    db: Session = Depends(get_db),
):
    """Bookable time slots.

    Without `doctor_id` and `appointment_date` this returns the full roster of
    slots. Supplying both narrows the answer to the slots that are actually
    free, so a patient is not offered a time that booking would then reject.
    """
    if doctor_id is None or appointment_date is None:
        return list(constants.APPOINTMENT_SLOTS)
    return crud.available_slots(db, doctor_id, appointment_date)


@app.get("/portal/appointments", response_model=List[schemas.PortalAppointment], tags=["portal"])
def portal_appointments(
    include_past: bool = True,
    patient: models.Patient = Depends(auth.get_current_patient),
    db: Session = Depends(get_db),
):
    return [
        crud.serialize_appointment(a)
        for a in crud.portal_appointments(db, patient.id, include_past=include_past)
    ]


@app.post("/portal/appointments", response_model=schemas.PortalAppointment, tags=["portal"])
def portal_book_appointment(
    payload: schemas.PortalAppointmentCreate,
    patient: models.Patient = Depends(auth.get_current_patient),
    db: Session = Depends(get_db),
):
    """Book an appointment for the signed-in patient.

    ``patient_id`` is taken from the token, never from the request, so a patient
    cannot book on somebody else's behalf.
    """
    appointment = crud.book_portal_appointment(db, patient.id, payload)
    return crud.serialize_appointment(appointment)


@app.put("/portal/appointments/{appointment_id}/cancel", response_model=schemas.PortalAppointment, tags=["portal"])
def portal_cancel_appointment(
    appointment_id: int,
    reason: Optional[str] = None,
    patient: models.Patient = Depends(auth.get_current_patient),
    db: Session = Depends(get_db),
):
    appointment = crud.cancel_portal_appointment(db, patient.id, appointment_id, reason)
    return crud.serialize_appointment(appointment)


@app.get("/portal/prescriptions", response_model=List[schemas.PortalPrescription], tags=["portal"])
def portal_prescriptions(
    patient: models.Patient = Depends(auth.get_current_patient), db: Session = Depends(get_db)
):
    return crud.portal_prescriptions(db, patient.id)


@app.get("/portal/lab-orders", response_model=List[schemas.PortalLabOrder], tags=["portal"])
def portal_lab_orders_endpoint(
    patient: models.Patient = Depends(auth.get_current_patient), db: Session = Depends(get_db)
):
    return crud.portal_lab_orders(db, patient.id)


@app.get("/portal/lab-reports", response_model=List[schemas.PortalLabReport], tags=["portal"])
def portal_lab_reports_endpoint(
    patient: models.Patient = Depends(auth.get_current_patient), db: Session = Depends(get_db)
):
    return crud.portal_lab_reports(db, patient.id)


@app.get("/portal/bills", response_model=List[schemas.PortalBill], tags=["portal"])
def portal_bills_endpoint(
    patient: models.Patient = Depends(auth.get_current_patient), db: Session = Depends(get_db)
):
    return crud.portal_bills(db, patient.id)


@app.get("/portal/documents", response_model=List[schemas.PortalDocument], tags=["portal"])
def portal_documents_endpoint(
    patient: models.Patient = Depends(auth.get_current_patient), db: Session = Depends(get_db)
):
    return crud.portal_documents(db, patient.id)


@app.get("/portal/insurance", tags=["portal"])
def portal_insurance(
    patient: models.Patient = Depends(auth.get_current_patient), db: Session = Depends(get_db)
):
    return {
        "policies": [schemas.InsurancePolicy.model_validate(p).model_dump() for p in crud.portal_policies(db, patient.id)],
        "claims": [schemas.InsuranceClaim.model_validate(c).model_dump() for c in crud.portal_claims(db, patient.id)],
    }


@app.post("/users/me/password", response_model=schemas.MessageResponse, tags=["auth"])
def change_my_password(
    payload: schemas.PasswordChange,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    """Self-service password change; requires the current password."""
    if not auth.verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect.")
    auth.assert_password_strength(payload.new_password)

    current_user.hashed_password = auth.get_password_hash(payload.new_password)
    auth.mark_password_changed(current_user)
    db.add(
        models.AuditLog(
            user_id=current_user.id, username=current_user.username, action="CHANGE_PASSWORD", details="Self-service"
        )
    )
    db.commit()
    return {"message": "Password updated successfully."}


@app.get("/security/status", tags=["auth"])
def get_security_status(
    current_user: models.User = Depends(auth.get_current_admin),
):
    return {
        "session_timeout_minutes": auth.ACCESS_TOKEN_EXPIRE_MINUTES,
        "max_failed_attempts": auth.MAX_FAILED_ATTEMPTS,
        "lockout_minutes": auth.LOCKOUT_MINUTES,
        "locked_accounts": [
            {
                "username": key[0],
                "client_ip": key[1],
                "locked_until": value.get("locked_until").isoformat() if value.get("locked_until") else None,
                "attempts": value.get("count", 0),
            }
            for key, value in auth.FAILED_LOGINS.items()
        ],
        "rate_limit_per_minute": RATE_LIMIT_MAX,
        "token_signing_key_source": "environment" if __import__("os").getenv("SECRET_KEY") else "generated file",
        "security_features": [
            "JWT Authentication (deny-by-default)",
            "Bcrypt Password Hashing",
            "Role-Based Access Control",
            "Brute Force Protection (lockout)",
            "Persisted Token Revocation (logout)",
            "Password Strength Policy",
            "Security Headers (CSP, XFO, nosniff)",
            "Per-IP Rate Limiting",
            "SQL Injection Protection (SQLAlchemy ORM)",
            "Audit Trail (all write operations)",
            "Request Validation (Pydantic v2)",
            "CORS restricted to known origins",
        ],
    }


# ============================
# User management (Admin)
# ============================
@app.post("/users/", response_model=schemas.UserResponse, tags=["users"])
def create_new_user(
    user: schemas.UserCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_admin),
):
    if crud.get_user_by_username(db, username=user.username):
        raise HTTPException(status_code=400, detail="Username already registered")
    auth.assert_password_strength(user.password)
    return crud.create_user(db=db, user=user, hashed_password=auth.get_password_hash(user.password))


@app.get("/users/", response_model=List[schemas.UserResponse], tags=["users"])
def read_all_users(db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_admin)):
    return crud.get_all_users(db)


@app.put("/users/{user_id}", response_model=schemas.UserResponse, tags=["users"])
def update_user(
    user_id: int,
    payload: schemas.UserUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_admin),
):
    target = db.query(models.User).filter(models.User.id == user_id).first()
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")
    if payload.role is not None:
        target = crud.update_user_role(db, user_id, payload.role)
    if payload.is_active is not None:
        target = crud.set_user_active(db, user_id, payload.is_active)
    db.refresh(target)
    return target


@app.put("/users/{user_id}/role", response_model=schemas.UserResponse, tags=["users"])
def update_role(
    user_id: int,
    role: str = Query(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_admin),
):
    return crud.update_user_role(db, user_id, role)


@app.put("/users/{user_id}/reset-password", response_model=schemas.MessageResponse, tags=["users"])
def reset_password(
    user_id: int,
    payload: schemas.PasswordReset,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_admin),
):
    auth.assert_password_strength(payload.new_password)
    crud.update_user_password(db, user_id, auth.get_password_hash(payload.new_password))
    return {"message": "Password reset successfully."}


@app.put("/users/{user_id}/link-patient", response_model=schemas.UserResponse, tags=["users"])
def link_patient_account(
    user_id: int,
    patient_id: int = Query(..., ge=1),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_admin),
):
    """Link a self-registered portal login to a verified existing patient record."""
    return crud.link_portal_account_to_patient(db, user_id, patient_id)


@app.delete("/users/{user_id}", response_model=schemas.MessageResponse, tags=["users"])
def remove_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_admin),
):
    crud.delete_user(db, user_id, acting_user_id=current_user.id)
    return {"message": "User deleted successfully"}


# ============================
# Patients
# ============================
@app.post("/patients/", response_model=schemas.Patient, tags=["patients"])
def create_patient(patient: schemas.PatientCreate, db: Session = Depends(get_db)):
    return crud.create_patient(db=db, patient=patient)


@app.get("/patients/", response_model=List[schemas.Patient], tags=["patients"])
def read_patients(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    search: Optional[str] = None,
    db: Session = Depends(get_db),
):
    return crud.get_patients(db, skip=skip, limit=limit, search=search)


@app.get("/patients/{patient_id}", response_model=schemas.Patient, tags=["patients"])
def read_patient(patient_id: int, db: Session = Depends(get_db)):
    db_patient = crud.get_patient(db, patient_id=patient_id)
    if db_patient is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    return db_patient


@app.put("/patients/{patient_id}", response_model=schemas.Patient, tags=["patients"])
def update_patient_endpoint(
    patient_id: int, patient_update: schemas.PatientUpdate, db: Session = Depends(get_db)
):
    return crud.update_patient(db, patient_id, patient_update)


@app.delete("/patients/{patient_id}", response_model=schemas.MessageResponse, tags=["patients"])
def delete_patient_endpoint(
    patient_id: int,
    force: bool = Query(False, description="Delete even when clinical records exist."),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_roles("Admin", "Receptionist")),
):
    if crud.patient_has_records(db, patient_id) and not force:
        raise HTTPException(
            status_code=409,
            detail=(
                "Patient has clinical or billing records. Pass force=true to delete anyway "
                "(this also removes dependent records)."
            ),
        )
    if force:
        for model, column in (
            (models.LabReport, models.LabReport.patient_id),
            (models.LabSample, None),
            (models.LabOrder, models.LabOrder.patient_id),
            (models.Casesheet, models.Casesheet.patient_id),
            (models.OPToken, models.OPToken.patient_id),
        ):
            if model is models.LabSample:
                order_ids = [o.id for o in db.query(models.LabOrder.id).filter(models.LabOrder.patient_id == patient_id)]
                if order_ids:
                    db.query(models.LabSample).filter(models.LabSample.order_id.in_(order_ids)).delete(
                        synchronize_session=False
                    )
                continue
            db.query(model).filter(column == patient_id).delete(synchronize_session=False)
        db.commit()
    crud.delete_patient(db, patient_id)
    return {"message": "Patient deleted successfully"}


@app.get("/patients/{patient_id}/casesheets/", response_model=List[schemas.Casesheet], tags=["patients"])
def read_patient_casesheets(patient_id: int, db: Session = Depends(get_db)):
    return crud.get_casesheets(db=db, patient_id=patient_id)


# ============================
# OP tokens
# ============================
@app.post("/tokens/", response_model=schemas.OPToken, tags=["op"])
def create_token(token: schemas.OPTokenCreate, db: Session = Depends(get_db)):
    return crud.create_op_token(db=db, token=token)


@app.get("/tokens/", response_model=List[schemas.OPToken], tags=["op"])
def read_tokens(
    target_date: Optional[date] = None,
    session: Optional[str] = None,
    db: Session = Depends(get_db),
):
    return crud.get_op_tokens(db=db, target_date=target_date or date.today(), session=session)


@app.get("/tokens/{token_id}", response_model=schemas.OPToken, tags=["op"])
def read_token(token_id: int, db: Session = Depends(get_db)):
    db_token = crud.get_op_token(db, token_id)
    if not db_token:
        raise HTTPException(status_code=404, detail="Token not found")
    return db_token


@app.put("/tokens/{token_id}", response_model=schemas.OPToken, tags=["op"])
def update_token_endpoint(token_id: int, payload: schemas.OPTokenUpdate, db: Session = Depends(get_db)):
    return crud.update_op_token(db=db, token_id=token_id, payload=payload)


@app.put("/tokens/{token_id}/status", response_model=schemas.OPToken, tags=["op"])
def update_token_status(
    token_id: int, new_status: str = Query(..., alias="status"), db: Session = Depends(get_db)
):
    return crud.update_op_token_status(db=db, token_id=token_id, status=new_status)


@app.delete("/tokens/{token_id}", response_model=schemas.MessageResponse, tags=["op"])
def delete_op_token_endpoint(token_id: int, db: Session = Depends(get_db)):
    crud.delete_op_token(db, token_id)
    return {"message": "Token deleted successfully"}


# ============================
# Appointments
# ============================
@app.post("/appointments/", response_model=schemas.AppointmentResponse, tags=["appointments"])
def create_appointment(appointment: schemas.AppointmentCreate, db: Session = Depends(get_db)):
    return crud.create_appointment(db=db, appointment=appointment)


@app.get("/appointments/", response_model=List[schemas.AppointmentResponse], tags=["appointments"])
def read_appointments(
    target_date: Optional[date] = None,
    include_upcoming: bool = Query(False, description="Include all future appointments."),
    db: Session = Depends(get_db),
):
    return crud.get_appointments(db=db, target_date=target_date or date.today(), include_upcoming=include_upcoming)


@app.put("/appointments/{appointment_id}", response_model=schemas.AppointmentResponse, tags=["appointments"])
def update_appointment_endpoint(
    appointment_id: int, payload: schemas.AppointmentUpdate, db: Session = Depends(get_db)
):
    return crud.update_appointment(db=db, appointment_id=appointment_id, payload=payload)


@app.delete("/appointments/{appointment_id}", response_model=schemas.MessageResponse, tags=["appointments"])
def delete_appointment_endpoint(appointment_id: int, db: Session = Depends(get_db)):
    crud.delete_appointment(db, appointment_id)
    return {"message": "Appointment deleted successfully"}


# ============================
# Casesheets
# ============================
@app.post("/casesheets/", response_model=schemas.Casesheet, tags=["casesheets"])
def create_casesheet(casesheet: schemas.CasesheetCreate, db: Session = Depends(get_db)):
    db_casesheet, _orders = crud.create_casesheet(db=db, casesheet=casesheet)
    return db_casesheet


@app.get("/casesheets/{casesheet_id}", response_model=schemas.Casesheet, tags=["casesheets"])
def get_casesheet_endpoint(casesheet_id: int, db: Session = Depends(get_db)):
    db_casesheet = crud.get_casesheet(db, casesheet_id)
    if not db_casesheet:
        raise HTTPException(status_code=404, detail="Casesheet not found")
    return db_casesheet


@app.put("/casesheets/{casesheet_id}", response_model=schemas.Casesheet, tags=["casesheets"])
def update_casesheet_endpoint(
    casesheet_id: int, casesheet_update: schemas.CasesheetUpdate, db: Session = Depends(get_db)
):
    return crud.update_casesheet(db, casesheet_id, casesheet_update)


@app.delete("/casesheets/{casesheet_id}", response_model=schemas.MessageResponse, tags=["casesheets"])
def delete_casesheet_endpoint(casesheet_id: int, db: Session = Depends(get_db)):
    crud.delete_casesheet(db, casesheet_id)
    return {"message": "Casesheet deleted successfully"}


# ============================
# Inventory
# ============================
@app.post("/inventory/", response_model=schemas.MedicineStock, tags=["inventory"])
def create_inventory_item(item: schemas.MedicineStockCreate, db: Session = Depends(get_db)):
    return crud.create_medicine_stock(db=db, item=item)


@app.get("/inventory/", response_model=List[schemas.MedicineStock], tags=["inventory"])
def read_inventory_items(category: Optional[str] = None, db: Session = Depends(get_db)):
    return crud.get_medicine_stocks(db=db, category=category)


@app.get("/inventory/alerts/low-stock", response_model=List[schemas.MedicineStock], tags=["inventory"])
def low_stock_items(db: Session = Depends(get_db)):
    return crud.low_stock_items(db)


@app.get("/inventory/alerts/expiring", response_model=List[schemas.MedicineStock], tags=["inventory"])
def expiring_items(within_days: int = Query(90, ge=1, le=3650), db: Session = Depends(get_db)):
    return crud.expiring_items(db, within_days=within_days)


@app.post("/inventory/adjust/", response_model=schemas.MedicineStock, tags=["inventory"])
def adjust_inventory_quantity(transaction: schemas.StockTransactionCreate, db: Session = Depends(get_db)):
    return crud.update_medicine_quantity(db=db, transaction=transaction)


@app.put("/inventory/{stock_id}", response_model=schemas.MedicineStock, tags=["inventory"])
def update_medicine_stock_endpoint(
    stock_id: int, stock_update: schemas.MedicineStockUpdate, db: Session = Depends(get_db)
):
    return crud.update_medicine_stock(db, stock_id, stock_update)


@app.delete("/inventory/{stock_id}", response_model=schemas.MessageResponse, tags=["inventory"])
def delete_medicine_stock_endpoint(
    stock_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(auth.require_roles("Admin", "Pharmacy"))
):
    crud.delete_medicine_stock(db, stock_id)
    return {"message": "Medicine stock deleted successfully"}


# ============================
# Pharmacy billing
# ============================
@app.post("/billing/pharmacy/", response_model=schemas.PharmacyBillResponse, tags=["billing"])
def create_pharmacy_bill(bill: schemas.PharmacyBillCreate, db: Session = Depends(get_db)):
    return crud.create_pharmacy_bill(db=db, bill=bill)


@app.get("/billing/pharmacy/", response_model=List[schemas.PharmacyBillResponse], tags=["billing"])
def read_pharmacy_bills(
    skip: int = Query(0, ge=0), limit: int = Query(200, ge=1, le=1000), db: Session = Depends(get_db)
):
    return crud.get_pharmacy_bills(db=db, skip=skip, limit=limit)


# ============================
# Laboratory - billing
# ============================
@app.post("/billing/lab/", response_model=schemas.LabBillResponse, tags=["lab"])
def create_lab_bill(bill: schemas.LabBillCreate, db: Session = Depends(get_db)):
    return crud.create_lab_bill(db=db, bill=bill)


@app.post("/billing/lab/from-orders", response_model=schemas.LabBillResponse, tags=["lab"])
def create_lab_bill_from_orders(payload: schemas.LabBillFromOrders, db: Session = Depends(get_db)):
    return crud.create_lab_bill_from_orders(db=db, payload=payload)


@app.get("/billing/lab/", response_model=List[schemas.LabBillResponse], tags=["lab"])
def read_lab_bills(
    patient_id: Optional[int] = None,
    bill_status: Optional[str] = Query(None, alias="status"),
    db: Session = Depends(get_db),
):
    return crud.get_lab_bills(db=db, patient_id=patient_id, bill_status=bill_status)


@app.put("/billing/lab/{bill_id}", response_model=schemas.LabBillResponse, tags=["lab"])
def update_lab_bill_status(
    bill_id: int, new_status: str = Query(..., alias="status"), db: Session = Depends(get_db)
):
    return crud.update_lab_bill_status(db=db, bill_id=bill_id, status=new_status)


# ============================
# OP / IP billing
# ============================
@app.post("/billing/op/", response_model=schemas.OPBillResponse, tags=["billing"])
def create_op_bill(bill: schemas.OPBillCreate, db: Session = Depends(get_db)):
    return crud.create_op_bill(db=db, bill=bill)


@app.get("/billing/op/", response_model=List[schemas.OPBillResponse], tags=["billing"])
def read_op_bills(patient_id: Optional[int] = None, db: Session = Depends(get_db)):
    return crud.get_op_bills(db=db, patient_id=patient_id)


@app.post("/billing/ip/", response_model=schemas.IPBillResponse, tags=["billing"])
def create_ip_bill(bill: schemas.IPBillCreate, db: Session = Depends(get_db)):
    return crud.create_ip_bill(db=db, bill=bill)


@app.get("/billing/ip/", response_model=List[schemas.IPBillResponse], tags=["billing"])
def read_ip_bills(patient_id: Optional[int] = None, db: Session = Depends(get_db)):
    return crud.get_ip_bills(db=db, patient_id=patient_id)


# ============================
# Hospital structure: departments → wards → rooms → beds
# ============================
@app.post("/departments/", response_model=schemas.Department, tags=["structure"])
def create_department(
    payload: schemas.DepartmentCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_admin),
):
    return crud.create_department(db, payload)


@app.get("/departments/", response_model=List[schemas.Department], tags=["structure"])
def read_departments(active_only: bool = False, db: Session = Depends(get_db)):
    return crud.get_departments(db, active_only=active_only)


@app.put("/departments/{department_id}", response_model=schemas.Department, tags=["structure"])
def update_department(
    department_id: int,
    payload: schemas.DepartmentUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_admin),
):
    return crud.update_department(db, department_id, payload)


@app.post("/wards/", response_model=schemas.Ward, tags=["structure"])
def create_ward(
    payload: schemas.WardCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_admin),
):
    return crud.create_ward(db, payload)


@app.get("/wards/", response_model=List[schemas.Ward], tags=["structure"])
def read_wards(
    active_only: bool = False, department_id: Optional[int] = None, db: Session = Depends(get_db)
):
    return crud.get_wards(db, active_only=active_only, department_id=department_id)


@app.put("/wards/{ward_id}", response_model=schemas.Ward, tags=["structure"])
def update_ward(
    ward_id: int,
    payload: schemas.WardUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_admin),
):
    return crud.update_ward(db, ward_id, payload)


@app.post("/rooms/", response_model=schemas.Room, tags=["structure"])
def create_room(
    payload: schemas.RoomCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_admin),
):
    return crud.create_room(db, payload)


@app.get("/rooms/", response_model=List[schemas.Room], tags=["structure"])
def read_rooms(ward_id: Optional[int] = None, db: Session = Depends(get_db)):
    query = db.query(models.Room)
    if ward_id:
        query = query.filter(models.Room.ward_id == ward_id)
    return query.order_by(models.Room.room_number).all()


@app.put("/rooms/{room_id}", response_model=schemas.Room, tags=["structure"])
def update_room(
    room_id: int,
    payload: schemas.RoomUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_admin),
):
    return crud.update_room(db, room_id, payload)


@app.post("/beds/", response_model=schemas.Bed, tags=["structure"])
def create_bed(
    payload: schemas.BedCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_admin),
):
    return crud.create_bed(db, payload)


@app.get("/beds/", response_model=List[schemas.Bed], tags=["structure"])
def read_beds(room_id: Optional[int] = None, db: Session = Depends(get_db)):
    query = db.query(models.Bed)
    if room_id:
        query = query.filter(models.Bed.room_id == room_id)
    return query.order_by(models.Bed.bed_code).all()


@app.put("/beds/{bed_id}", response_model=schemas.Bed, tags=["structure"])
def update_bed(
    bed_id: int,
    payload: schemas.BedUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_admin),
):
    return crud.update_bed(db, bed_id, payload)


@app.delete("/beds/{bed_id}", tags=["structure"])
def delete_bed(
    bed_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_admin),
):
    crud.delete_bed(db, bed_id)
    return {"message": "Bed removed"}


# ============================
# IPD — bed board, occupancy, dashboard
# ============================
@app.get("/ipd/bed-board", response_model=List[schemas.BedBoardItem], tags=["ipd"])
def ipd_bed_board(
    ward_id: Optional[int] = None,
    bed_status: Optional[str] = Query(None, alias="status"),
    include_inactive: bool = False,
    db: Session = Depends(get_db),
):
    return crud.get_bed_board(db, ward_id=ward_id, bed_status=bed_status, include_inactive=include_inactive)


@app.get("/ipd/bed-board/summary", response_model=schemas.BedBoardSummary, tags=["ipd"])
def ipd_bed_board_summary(db: Session = Depends(get_db)):
    return crud.get_bed_board_summary(db)


@app.get("/ipd/stats", response_model=schemas.IPDStats, tags=["ipd"])
def ipd_stats(db: Session = Depends(get_db)):
    return crud.get_ipd_stats(db)


@app.get("/ipd/occupancy", tags=["ipd"])
def ipd_occupancy(days: int = Query(30, ge=1, le=365), db: Session = Depends(get_db)):
    return crud.get_bed_occupancy_report(db, days=days)


@app.get("/ipd/doctors", response_model=List[schemas.StaffMember], tags=["ipd"])
def ipd_doctors(db: Session = Depends(get_db)):
    return crud.list_doctors(db)


@app.get("/ipd/nurses", response_model=List[schemas.StaffMember], tags=["ipd"])
def ipd_nurses(db: Session = Depends(get_db)):
    return crud.list_nurses(db)


# ============================
# IP admissions
# ============================
@app.post("/ip-admissions/", response_model=schemas.IPAdmission, tags=["ipd"])
def create_ip_admission(
    admission: schemas.IPAdmissionCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """Admit a patient, optionally allocating a bed atomically."""
    return crud.create_ip_admission(
        db=db, admission=admission,
        actor=current_user.username, actor_role=current_user.role,
    )


@app.get("/ip-admissions/", response_model=List[schemas.IPAdmission], tags=["ipd"])
def read_ip_admissions(
    patient_id: Optional[int] = None,
    admission_status: Optional[str] = Query(None, alias="status"),
    department_id: Optional[int] = None,
    ward_id: Optional[int] = None,
    current_only: bool = False,
    skip: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    return crud.get_ip_admissions(
        db=db,
        patient_id=patient_id,
        admission_status=admission_status,
        department_id=department_id,
        ward_id=ward_id,
        current_only=current_only,
        skip=skip,
        limit=limit,
    )


@app.get("/ip-admissions/{admission_id}/detail", response_model=schemas.IPAdmissionDetail, tags=["ipd"])
def read_ip_admission_detail(admission_id: int, db: Session = Depends(get_db)):
    detail = crud.get_ip_admission_detail(db, admission_id)
    admission = detail["admission"]
    # Every column is included automatically, so the detail payload cannot drift
    # out of sync as the admission model gains fields.
    payload = {column.name: getattr(admission, column.name) for column in admission.__table__.columns}
    payload.update(
        {
            "patient": admission.patient,
            "bed": admission.bed,
            "department": admission.department,
            "allocations": detail["allocations"],
            "transfers": detail["transfers"],
            "nursing_notes": detail["nursing_notes"],
            "medication_orders": detail["medication_orders"],
            "discharge_summary": detail["discharge_summary"],
            "length_of_stay_days": detail["length_of_stay_days"],
            "billable_room_charge": detail["billable_room_charge"],
        }
    )
    return payload


@app.put("/ip-admissions/{admission_id}", response_model=schemas.IPAdmission, tags=["ipd"])
def update_ip_admission_endpoint(
    admission_id: int, admission_update: schemas.IPAdmissionUpdate, db: Session = Depends(get_db)
):
    return crud.update_ip_admission(db, admission_id, admission_update)


@app.put("/ip-admissions/{admission_id}/status", response_model=schemas.IPAdmission, tags=["ipd"])
def update_ip_admission_status_endpoint(
    admission_id: int,
    new_status: str = Query(..., alias="status"),
    discharge_date: Optional[datetime] = None,
    db: Session = Depends(get_db),
):
    return crud.update_ip_admission_status(
        db=db, admission_id=admission_id, status=new_status, discharge_date=discharge_date
    )


@app.post("/ip-admissions/{admission_id}/bed", response_model=schemas.IPAdmission, tags=["ipd"])
def assign_bed_endpoint(
    admission_id: int,
    payload: schemas.BedAssignRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    return crud.assign_bed(db, admission_id, payload.bed_id, actor=current_user.username, actor_role=current_user.role, reason=payload.reason)


@app.post("/ip-admissions/{admission_id}/transfer", response_model=schemas.IPAdmission, tags=["ipd"])
def transfer_patient_endpoint(
    admission_id: int,
    payload: schemas.PatientTransferRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    return crud.transfer_patient(db, admission_id, payload, actor=current_user.username, actor_role=current_user.role)


@app.post("/ip-admissions/{admission_id}/discharge", response_model=schemas.IPAdmission, tags=["ipd"])
def discharge_patient_endpoint(
    admission_id: int,
    payload: schemas.DischargeRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    return crud.discharge_patient(db, admission_id, payload, actor=current_user.username, actor_role=current_user.role)


@app.delete("/ip-admissions/{admission_id}", response_model=schemas.MessageResponse, tags=["ipd"])
def delete_ip_admission_endpoint(admission_id: int, db: Session = Depends(get_db)):
    crud.delete_ip_admission(db, admission_id)
    return {"message": "IP admission deleted successfully"}


# ============================
# IPD — nursing chart
# ============================
@app.post("/ip-admissions/{admission_id}/nursing-notes", response_model=schemas.NursingNote, tags=["ipd"])
def create_nursing_note(
    admission_id: int,
    payload: schemas.NursingNoteCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    return crud.create_nursing_note(db, admission_id, payload, actor=current_user.username, actor_role=current_user.role)


@app.get("/ip-admissions/{admission_id}/nursing-notes", response_model=List[schemas.NursingNote], tags=["ipd"])
def read_nursing_notes(admission_id: int, limit: int = Query(200, ge=1, le=1000), db: Session = Depends(get_db)):
    return crud.get_nursing_notes(db, admission_id, limit=limit)


# ============================
# IPD — medication orders & administration
# ============================
@app.post("/ip-admissions/{admission_id}/medications", response_model=schemas.MedicationOrder, tags=["ipd"])
def create_medication_order(
    admission_id: int,
    payload: schemas.MedicationOrderCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    return crud.create_medication_order(db, admission_id, payload, actor=current_user.username, actor_role=current_user.role)


@app.get("/ip-admissions/{admission_id}/medications", response_model=List[schemas.MedicationOrder], tags=["ipd"])
def read_medication_orders(admission_id: int, active_only: bool = False, db: Session = Depends(get_db)):
    return crud.get_medication_orders(db, admission_id, active_only=active_only)


@app.put("/ipd/medications/{order_id}", response_model=schemas.MedicationOrder, tags=["ipd"])
def update_medication_order(
    order_id: int,
    payload: schemas.MedicationOrderUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    return crud.update_medication_order(
        db, order_id, payload,
        actor=current_user.username, actor_role=current_user.role,
    )


@app.post("/ipd/medications/{order_id}/administer", response_model=schemas.MedicationAdministration, tags=["ipd"])
def administer_medication(
    order_id: int,
    payload: schemas.MedicationAdministrationCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    return crud.administer_medication(db, order_id, payload, actor=current_user.username, actor_role=current_user.role)


@app.get(
    "/ipd/medications/{order_id}/administrations",
    response_model=List[schemas.MedicationAdministration],
    tags=["ipd"],
)
def read_medication_administrations(
    order_id: int, limit: int = Query(100, ge=1, le=1000), db: Session = Depends(get_db)
):
    return crud.get_medication_administrations(db, order_id, limit=limit)


# ============================
# IPD — discharge summary
# ============================
@app.get("/ip-admissions/{admission_id}/discharge-summary", response_model=Optional[schemas.DischargeSummary], tags=["ipd"])
def read_discharge_summary(admission_id: int, db: Session = Depends(get_db)):
    return crud.get_discharge_summary(db, admission_id)


@app.post("/ip-admissions/{admission_id}/discharge-summary", response_model=schemas.DischargeSummary, tags=["ipd"])
def upsert_discharge_summary(
    admission_id: int,
    payload: schemas.DischargeSummaryCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    return crud.upsert_discharge_summary(db, admission_id, payload, actor=current_user.username, actor_role=current_user.role)


@app.get("/ipd/discharge-summaries/{summary_id}", response_model=schemas.DischargeSummary, tags=["ipd"])
def read_discharge_summary_by_id(summary_id: int, db: Session = Depends(get_db)):
    return crud.get_discharge_summary_by_id(db, summary_id)


@app.put("/ipd/discharge-summaries/{summary_id}", response_model=schemas.DischargeSummary, tags=["ipd"])
def update_discharge_summary(
    summary_id: int,
    payload: schemas.DischargeSummaryUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    return crud.update_discharge_summary(db, summary_id, payload, actor=current_user.username, actor_role=current_user.role)


# ============================
# Staff master
# ============================
@app.post("/staff/", response_model=schemas.StaffMember, tags=["staff"])
def create_staff_member(
    payload: schemas.StaffMemberCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_admin),
):
    auth.assert_password_strength(payload.password)
    return crud.create_staff_member(db, payload, auth.get_password_hash(payload.password))


@app.get("/staff/", response_model=List[schemas.StaffMember], tags=["staff"])
def read_staff_members(
    role: Optional[str] = None,
    department_id: Optional[int] = None,
    active_only: bool = False,
    db: Session = Depends(get_db),
):
    return crud.get_staff_members(db, role=role, department_id=department_id, active_only=active_only)


@app.put("/staff/{user_id}", response_model=schemas.StaffMember, tags=["staff"])
def update_staff_member(
    user_id: int,
    payload: schemas.StaffMemberUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_admin),
):
    return crud.update_staff_member(db, user_id, payload)


# ============================
# Laboratory - test master, parameters, panels
# ============================
@app.post("/lab-test-masters/", response_model=schemas.LabTestMaster, tags=["lab"])
def create_lab_test_master(
    test: schemas.LabTestMasterCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_roles("Admin", "Laboratory", "Doctor")),
):
    return crud.create_lab_test_master(db=db, test=test)


@app.get("/lab-test-masters/", response_model=List[schemas.LabTestMaster], tags=["lab"])
def read_lab_test_masters(
    include_inactive: bool = False,
    panels_only: bool = False,
    tests_only: bool = False,
    db: Session = Depends(get_db),
):
    items = crud.get_lab_test_masters(db=db, include_inactive=include_inactive)
    if panels_only:
        items = [i for i in items if i.is_panel]
    if tests_only:
        items = [i for i in items if not i.is_panel]
    return items


@app.get("/lab-test-masters/{test_id}", response_model=schemas.LabTestMaster, tags=["lab"])
def read_lab_test_master(test_id: int, db: Session = Depends(get_db)):
    return crud.get_lab_test(db, test_id)


@app.put("/lab-test-masters/{test_id}", response_model=schemas.LabTestMaster, tags=["lab"])
def update_lab_test_master(
    test_id: int,
    test: schemas.LabTestMasterUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_roles("Admin", "Laboratory")),
):
    return crud.update_lab_test_master(db, test_id, test)


@app.put("/lab-test-masters/{test_id}/active", response_model=schemas.LabTestMaster, tags=["lab"])
def set_lab_test_active(
    test_id: int,
    is_active: bool = Query(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_roles("Admin", "Laboratory")),
):
    return crud.set_lab_test_active(db, test_id, is_active)


@app.delete("/lab-test-masters/{test_id}", response_model=schemas.MessageResponse, tags=["lab"])
def delete_lab_test_master(
    test_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_roles("Admin", "Laboratory")),
):
    crud.delete_lab_test_master(db, test_id)
    return {"message": "Test master deactivated successfully"}


# ============================
# Laboratory - orders
# ============================
@app.post("/lab-orders/", response_model=schemas.LabOrder, tags=["lab"])
def create_lab_order(order: schemas.LabOrderCreate, db: Session = Depends(get_db)):
    return crud.create_lab_order(db=db, order=order)


@app.post("/lab-orders/bulk", response_model=List[schemas.LabOrder], tags=["lab"])
def create_lab_orders_bulk(payload: schemas.LabOrderBulkCreate, db: Session = Depends(get_db)):
    """Order several tests (or a panel) for one patient in a single transaction."""
    return crud.create_lab_orders_bulk(db=db, payload=payload)


@app.get("/lab-orders/", response_model=List[schemas.LabOrder], tags=["lab"])
def read_lab_orders(
    target_date: Optional[date] = None,
    patient_id: Optional[int] = None,
    order_status: Optional[str] = Query(None, alias="status"),
    priority: Optional[str] = None,
    overdue_only: bool = False,
    db: Session = Depends(get_db),
):
    return crud.get_lab_orders(
        db=db,
        target_date=target_date,
        patient_id=patient_id,
        order_status=order_status,
        priority=priority,
        overdue_only=overdue_only,
    )


@app.get("/lab-orders/{order_id}", response_model=schemas.LabOrder, tags=["lab"])
def read_lab_order(order_id: int, db: Session = Depends(get_db)):
    return crud.get_lab_order(db, order_id)


@app.put("/lab-orders/{order_id}", response_model=schemas.LabOrder, tags=["lab"])
def update_lab_order(order_id: int, order_data: schemas.LabOrderUpdate, db: Session = Depends(get_db)):
    return crud.update_lab_order(db=db, order_id=order_id, order_data=order_data)


@app.put("/lab-orders/{order_id}/status", response_model=schemas.LabOrder, tags=["lab"])
def update_lab_order_status(
    order_id: int, new_status: str = Query(..., alias="status"), db: Session = Depends(get_db)
):
    return crud.update_lab_order_status(db=db, order_id=order_id, status=new_status)


@app.post("/lab-orders/{order_id}/results", response_model=schemas.LabReport, tags=["lab"])
def submit_lab_order_results(
    order_id: int,
    payload: schemas.LabResultSubmit,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_roles("Admin", "Laboratory", "Doctor")),
):
    """Save (and optionally verify) the result rows for an order."""
    return crud.submit_lab_results(db=db, order_id=order_id, payload=payload, actor=current_user.username)


@app.delete("/lab-orders/{order_id}", response_model=schemas.MessageResponse, tags=["lab"])
def delete_lab_order_endpoint(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_roles("Admin", "Laboratory")),
):
    crud.delete_lab_order(db, order_id)
    return {"message": "Lab order deleted successfully"}


# ============================
# Laboratory - samples
# ============================
@app.post("/lab-samples/", response_model=schemas.LabSample, tags=["lab"])
def create_lab_sample(sample: schemas.LabSampleCreate, db: Session = Depends(get_db)):
    return crud.create_lab_sample(db=db, sample=sample)


@app.get("/lab-samples/", response_model=List[schemas.LabSample], tags=["lab"])
def read_lab_samples(
    order_id: Optional[int] = None,
    sample_status: Optional[str] = Query(None, alias="status"),
    db: Session = Depends(get_db),
):
    return crud.get_lab_samples(db=db, order_id=order_id, sample_status=sample_status)


@app.put("/lab-samples/{sample_id}", response_model=schemas.LabSample, tags=["lab"])
def update_lab_sample(sample_id: int, sample_data: schemas.LabSampleUpdate, db: Session = Depends(get_db)):
    return crud.update_lab_sample(db=db, sample_id=sample_id, sample_data=sample_data)


@app.put("/lab-samples/{sample_id}/status", response_model=schemas.LabSample, tags=["lab"])
def update_lab_sample_status(
    sample_id: int, new_status: str = Query(..., alias="status"), db: Session = Depends(get_db)
):
    return crud.update_lab_sample_status(db=db, sample_id=sample_id, status=new_status)


@app.delete("/lab-samples/{sample_id}", response_model=schemas.MessageResponse, tags=["lab"])
def delete_lab_sample_endpoint(
    sample_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_roles("Admin", "Laboratory")),
):
    crud.delete_lab_sample(db, sample_id)
    return {"message": "Lab sample deleted successfully"}


# ============================
# Laboratory - reports & stats
# ============================
@app.post("/lab-reports/", response_model=schemas.LabReport, tags=["lab"])
def create_lab_report(report: schemas.LabReportCreate, db: Session = Depends(get_db)):
    return crud.create_lab_report(db=db, report=report)


@app.get("/lab-reports/", response_model=List[schemas.LabReport], tags=["lab"])
def read_lab_reports(
    patient_id: Optional[int] = None,
    order_id: Optional[int] = None,
    abnormal_only: bool = False,
    skip: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    return crud.get_lab_reports(
        db=db, patient_id=patient_id, order_id=order_id, abnormal_only=abnormal_only, skip=skip, limit=limit
    )


@app.put("/lab-reports/{report_id}", response_model=schemas.LabReport, tags=["lab"])
def update_lab_report_endpoint(
    report_id: int, report_update: schemas.LabReportUpdate, db: Session = Depends(get_db)
):
    return crud.update_lab_report(db, report_id, report_update)


@app.delete("/lab-reports/{report_id}", response_model=schemas.MessageResponse, tags=["lab"])
def delete_lab_report_endpoint(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_roles("Admin", "Laboratory")),
):
    crud.delete_lab_report(db, report_id)
    return {"message": "Lab report deleted successfully"}


@app.get("/lab/stats", response_model=schemas.LabStats, tags=["lab"])
def lab_stats(db: Session = Depends(get_db)):
    return crud.get_lab_stats(db=db)


# ============================
# Search
# ============================
@app.get("/search/", response_model=List[schemas.SearchResult], tags=["search"])
def search(q: str = Query(..., min_length=1, max_length=60), db: Session = Depends(get_db)):
    return crud.global_search(db=db, query=q)


# ============================
# Reports
# ============================
@app.get("/reports/daily/", response_model=schemas.DailyReportResponse, tags=["reports"])
def daily_report(report_date: Optional[date] = None, db: Session = Depends(get_db)):
    return crud.get_daily_report(db=db, report_date=report_date or date.today())


@app.get("/reports/monthly/", response_model=List[schemas.DailyReportResponse], tags=["reports"])
def monthly_report(
    year: Optional[int] = Query(None, ge=2000, le=2100),
    month: Optional[int] = Query(None, ge=1, le=12),
    db: Session = Depends(get_db),
):
    today = date.today()
    return crud.get_monthly_report(db=db, year=year or today.year, month=month or today.month)


@app.get("/reports/yearly/", response_model=List[schemas.MonthlyReportItem], tags=["reports"])
def yearly_report(year: Optional[int] = Query(None, ge=2000, le=2100), db: Session = Depends(get_db)):
    return crud.get_yearly_report(db=db, year=year or date.today().year)


@app.get("/reports/revenue/", response_model=schemas.RevenueBreakdown, tags=["reports"])
def revenue_report(
    start_date: Optional[date] = None, end_date: Optional[date] = None, db: Session = Depends(get_db)
):
    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=422, detail="start_date must be on or before end_date.")
    return crud.get_revenue_breakdown(db=db, start_date=start_date, end_date=end_date)


@app.get("/reports/doctor-wise/", response_model=List[schemas.DoctorWiseReport], tags=["reports"])
def doctor_wise_report(db: Session = Depends(get_db)):
    return crud.get_doctor_wise_report(db=db)


@app.get("/reports/medicine-sales/", response_model=List[schemas.MedicineSalesReport], tags=["reports"])
def medicine_sales_report(db: Session = Depends(get_db)):
    return crud.get_medicine_sales_report(db=db)


@app.get("/reports/admissions/", response_model=List[schemas.IPAdmission], tags=["reports"])
def admissions_report(admission_status: Optional[str] = Query(None, alias="status"), db: Session = Depends(get_db)):
    return crud.get_admission_report(db=db, status=admission_status)


@app.get("/reports/department-wise/", response_model=List[schemas.DepartmentWiseReport], tags=["reports"])
def department_wise_report(db: Session = Depends(get_db)):
    return crud.get_department_wise_report(db=db)


@app.get("/reports/patient/{patient_id}", tags=["reports"])
def patient_report(patient_id: int, db: Session = Depends(get_db)):
    report = crud.get_patient_report(db=db, patient_id=patient_id)
    if not report:
        raise HTTPException(status_code=404, detail="Patient not found")
    report["patient"] = schemas.Patient.model_validate(report["patient"]).model_dump()
    return report


@app.get("/reports/medicine-stock/", response_model=List[schemas.MedicineStock], tags=["reports"])
def medicine_stock_report(db: Session = Depends(get_db)):
    return crud.get_medicine_stocks(db=db)


@app.get("/reports/lab-summary/", response_model=List[schemas.LabSummaryItem], tags=["reports"])
def lab_summary_report(
    start_date: Optional[date] = None, end_date: Optional[date] = None, db: Session = Depends(get_db)
):
    """Aggregated lab activity per test (previously returned raw report rows)."""
    return crud.get_lab_summary_report(db=db, start_date=start_date, end_date=end_date)


@app.get("/reports/discharge/", response_model=List[schemas.IPAdmission], tags=["reports"])
def discharge_report(db: Session = Depends(get_db)):
    return crud.get_admission_report(db=db, status="Discharged")


# ============================
# Dashboard
# ============================
@app.get("/dashboard/stats", response_model=schemas.DashboardStats, tags=["dashboard"])
def get_dashboard_stats(db: Session = Depends(get_db)):
    return crud.get_dashboard_stats(db)


@app.get("/dashboard/charts", response_model=schemas.DashboardCharts, tags=["dashboard"])
def get_dashboard_charts(db: Session = Depends(get_db)):
    return crud.get_dashboard_charts(db)


# ============================
# Hospital settings
# ============================
@app.get("/hospital-settings/", tags=["settings"])
def get_hospital_settings(db: Session = Depends(get_db)):
    return crud.get_hospital_settings(db)


@app.post("/hospital-settings/", response_model=schemas.MessageResponse, tags=["settings"])
def update_hospital_settings(
    body: schemas.HospitalSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_roles("Admin")),
):
    return crud.update_hospital_settings(db=db, payload=body, actor=current_user)


# ============================
# Audit & backup
# ============================
@app.get("/audit-logs/", response_model=List[schemas.AuditLogResponse], tags=["admin"])
def get_audit_logs(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    action: Optional[str] = None,
    entity_type: Optional[str] = None,
    patient_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_admin),
):
    query = db.query(models.AuditLog)
    if action:
        query = query.filter(models.AuditLog.action.like(f"%{action.upper()}%"))
    if entity_type:
        query = query.filter(models.AuditLog.entity_type == entity_type)
    if patient_id:
        query = query.filter(models.AuditLog.patient_id == patient_id)
    return query.order_by(models.AuditLog.timestamp.desc()).offset(skip).limit(limit).all()


@app.get(
    "/audit-logs/entity/{entity_type}/{entity_id}",
    response_model=List[schemas.AuditLogResponse],
    tags=["ipd"],
)
def get_entity_audit_trail(
    entity_type: str,
    entity_id: int,
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """The change history of one clinical record.

    Readable by any authenticated clinician (so a ward nurse can see what
    happened to their patient); there is deliberately no write endpoint —
    the trail is append-only.
    """
    return audit.entity_trail(db, entity_type, entity_id, limit=limit)


@app.get(
    "/audit-logs/patient/{patient_id}",
    response_model=List[schemas.AuditLogResponse],
    tags=["ipd"],
)
def get_patient_audit_trail(
    patient_id: int,
    limit: int = Query(300, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """Everything that happened to a patient, across every record type."""
    if not db.query(models.Patient).filter(models.Patient.id == patient_id).first():
        raise HTTPException(status_code=404, detail="Patient not found")
    return audit.patient_trail(db, patient_id, limit=limit)


@app.get("/backup/", tags=["admin"])
def backup_database(
    current_user: models.User = Depends(auth.get_current_admin),
    db: Session = Depends(get_db),
):
    """Download a real JSON snapshot of the business tables.

    The previous implementation returned only record counts, so the "backup"
    button downloaded a file that could not restore anything.
    """
    payload = crud.export_database(db)
    db.add(
        models.AuditLog(
            user_id=current_user.id,
            username=current_user.username,
            action="DATABASE_BACKUP",
            details=f"Exported {len(payload) - 1} tables",
        )
    )
    db.commit()
    return JSONResponse(content=payload)


@app.post("/seed/", response_model=schemas.MessageResponse, tags=["admin"])
def seed_data_endpoint(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_admin),
):
    """Populate demo data. Admin-only: this was previously open to anonymous callers."""
    return crud.seed_data(db)


# ============================
# Insurance desk
# ============================
insurance_team = auth.require_roles("Admin", "Insurance")
insurance_read = auth.require_roles("Admin", "Insurance", "Billing", "Receptionist", "Doctor")


@app.post("/insurance/policies", response_model=schemas.InsurancePolicy, tags=["insurance"])
def create_insurance_policy(
    payload: schemas.InsurancePolicyCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(insurance_team),
):
    return crud.create_insurance_policy(db, payload)


@app.get("/insurance/policies", response_model=List[schemas.InsurancePolicy], tags=["insurance"])
def list_insurance_policies(
    patient_id: Optional[int] = None,
    active_only: bool = False,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(insurance_read),
):
    return crud.get_insurance_policies(db, patient_id=patient_id, active_only=active_only)


@app.put("/insurance/policies/{policy_id}", response_model=schemas.InsurancePolicy, tags=["insurance"])
def update_insurance_policy(
    policy_id: int,
    payload: schemas.InsurancePolicyUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(insurance_team),
):
    return crud.update_insurance_policy(db, policy_id, payload)


@app.post("/insurance/claims", response_model=schemas.InsuranceClaim, tags=["insurance"])
def create_insurance_claim(
    payload: schemas.InsuranceClaimCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(insurance_team),
):
    return crud.create_insurance_claim(db, payload, actor=current_user.username)


@app.get("/insurance/claims", response_model=List[schemas.InsuranceClaim], tags=["insurance"])
def list_insurance_claims(
    patient_id: Optional[int] = None,
    claim_status: Optional[str] = Query(None, alias="status"),
    policy_id: Optional[int] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(500, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(insurance_read),
):
    return crud.get_insurance_claims(
        db, patient_id=patient_id, claim_status=claim_status, policy_id=policy_id, skip=skip, limit=limit
    )


@app.get("/insurance/claims/{claim_id}", response_model=schemas.InsuranceClaim, tags=["insurance"])
def read_insurance_claim(
    claim_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(insurance_read),
):
    return crud.get_insurance_claim(db, claim_id)


@app.put("/insurance/claims/{claim_id}", response_model=schemas.InsuranceClaim, tags=["insurance"])
def update_insurance_claim(
    claim_id: int,
    payload: schemas.InsuranceClaimUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(insurance_team),
):
    return crud.update_insurance_claim(db, claim_id, payload, actor=current_user.username)


@app.put("/insurance/claims/{claim_id}/status", response_model=schemas.InsuranceClaim, tags=["insurance"])
def update_insurance_claim_status(
    claim_id: int,
    payload: schemas.InsuranceClaimStatusUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(insurance_team),
):
    return crud.update_insurance_claim_status(db, claim_id, payload, actor=current_user.username)


@app.get("/insurance/stats", response_model=schemas.InsuranceStats, tags=["insurance"])
def insurance_stats(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(insurance_read),
):
    return crud.get_insurance_stats(db)


# ============================
# Bundled frontend (single-service local deployment)
# ============================
# When SERVE_FRONTEND is enabled and a production build exists, the API also serves
# the React bundle. That makes a local deployment a single process on a single
# origin — no second dev server to keep alive and no CORS to configure.
# Must be mounted LAST: earlier routes take precedence over this catch-all mount.
def _mount_frontend(application: FastAPI) -> bool:
    from pathlib import Path

    from fastapi.staticfiles import StaticFiles

    dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
    if not dist.is_dir() or not (dist / "index.html").is_file():
        logger.warning("SERVE_FRONTEND is on but no build was found at %s (run `npm run build`).", dist)
        return False

    application.mount("/", StaticFiles(directory=str(dist), html=True), name="frontend")
    logger.info("Serving the bundled frontend from %s", dist)
    return True


if settings.serve_frontend:
    _mount_frontend(app)
