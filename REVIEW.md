# Code Review, Fixes & Laboratory Module

Review of `hospital_os` (FastAPI + SQLAlchemy backend, React/TypeScript frontend),
the defects found and repaired, and the new laboratory features added.

Everything below is reproducible: `python -m pytest` (77 tests),
`npx tsc --noEmit`, `npm run build`, plus two Playwright suites that drive the real UI.

---

## 1. Verification status

| Check | Command | Result |
| --- | --- | --- |
| Backend regression suite | `python -m pytest` | **140 passed** |
| TypeScript | `npx tsc --noEmit` in `frontend/` | **clean** (was 44 errors) |
| Production build | `npm run build` | **succeeds** (was broken) |
| Schema migrations | Alembic `0001_baseline` → `0002_ipd_module` | **applied to the live DB, data preserved** |
| Lab UI smoke test | Playwright, 18 checks | **18/18** |
| Lab workflow end-to-end | Playwright, 28 checks | **28/28** |
| Deployed app (single service) | Playwright, 14 checks | **14/14** |
| Dev setup at `localhost:3000` | Playwright, 12 checks | **12/12** |
| Patient portal + all staff roles | Playwright, 32 checks | **32/32** |
| Admin role management | Playwright, 15 checks | **15/15** |
| Per-role complete workflows | Playwright, 59 checks | **59/59** |
| IPD API workflow (live server) | Playwright, 34 checks | **34/34** |
| IPD UI (setup → admit → chart → discharge) | Playwright, 20 checks | **20/20** |

---

## 2. Critical defects fixed

### 2.1 The API had no authentication
`POST /patients/`, `DELETE /patients/1`, `POST /seed/` and ~60 other routes were
completely anonymous. Only four admin routes were protected.

* Added `AuthGuardMiddleware` — **deny by default**: any path not in
  `PUBLIC_PATHS` (`/login`, `/refresh-token`, `/health`, `/docs`) requires a valid
  bearer token. New routes are protected automatically.
* Added `require_roles(...)`; `/users/*`, `/audit-logs/`, `/backup/`, `/seed/`
  and hospital settings are now Admin-only.

### 2.2 Hard-coded JWT signing key
`SECRET_KEY = "h0spit@l_s3cr3t_k3y_v3ry_s3cur3_2024"` was committed to the repo.
It now comes from the `SECRET_KEY` environment variable; if absent a random key is
generated once, stored in `.secret_key` (git-ignored, mode 0600) and a warning is
logged.

### 2.3 Stored-but-unused password policy
`validate_password_strength()` existed but was never called, so
`PUT /users/1/reset-password?new_password=a` succeeded. The policy is now enforced
on user creation, admin reset and self-service change.

There was also **no password-change UI at all** — the endpoints existed but nothing
called them, so a deployment could never rotate the default credential. A *Change
password* button (top bar, any role) and an admin *Reset password* action were added.

The self-service endpoint was then found to be insecure by the browser test:
`POST /users/me/password` accepted only `new_password` and never verified the
current one, so anyone holding a borrowed token could take over the account. It now
requires `current_password` and rejects a mismatch with 400; four regression tests
cover it (`TestSelfServicePassword`).

### 2.4 Free-form roles broke authorisation
`PUT /users/1/role?role=Wizard` returned 200 and permanently removed the caller's
own admin rights. Roles are now validated against `constants.ROLES`, and the last
active administrator cannot be demoted, deactivated or deleted. Self-deletion is
blocked.

### 2.5 Logout revoked other sessions
`create_access_token` produced byte-identical tokens when the same user logged in
twice within one second (second-resolution `iat`/`exp`), so blacklisting one token
also killed the other session. Tokens now carry a unique `jti`.

Additionally, the blacklist was an in-memory `set` — every logout was undone by a
restart. It is now the persisted `token_blacklist` table with expiry-based pruning.

### 2.6 `/refresh-token` was blocked by the new guard
Caught by the test suite: the endpoint authenticates with the refresh token itself,
so it must be public. Also now accepts the token in the JSON body (query strings
leak into access logs) while staying backwards compatible.

### 2.7 Revenue reports always returned zero
`_sum_between(db, models.LabBill.total, start, end)` filtered `total >= start`,
comparing a float against a datetime, so **every** revenue figure in the daily,
monthly, yearly, chart and dashboard reports silently came back as `0`. The helper
now takes the amount column and the date column separately.

### 2.8 The dashboard omitted lab revenue
`/dashboard/stats` summed OP + IP + pharmacy only, so the dashboard total never
matched `/reports/daily/`. Lab revenue is now included and exposed as its own field.

### 2.9 Lab order date filter crashed
`GET /lab-orders/?target_date=2024-01-01` raised
`AttributeError: 'datetime.date' object has no attribute 'date'` → HTTP 500.

### 2.10 Casesheet edits were silently discarded
`CasesheetUpdate` declared `vitals`, `hpi`, `chief_complaint` … — none of which
existed on the ORM model — while omitting every real column. `setattr` set
throwaway attributes, so **no** field could ever be updated. The schema now mirrors
the model (and the model gained the narrative fields it was missing).

### 2.11 Mutable JSON defaults shared across rows
`details = Column(JSON, default={})` hands the *same* dict to every instance.
All JSON columns now use `default=dict` / `default=list`.

### 2.12 Other correctness fixes
* `get_appointments` filtered `>= date`, so "today's appointments" included every
  future booking. Now `== date`, with an opt-in `include_upcoming`.
* Lab order / sample / bill / token / appointment statuses were free strings
  (`status=Bogus` → 200). All are validated against `constants` and return 422.
* Lab orders accepted non-existent patients and tests (orphan rows). Now 404.
* Lab workflow had no transition rules (Pending → Verified was accepted). Now
  enforced by `LAB_ORDER_TRANSITIONS` with 409 responses, and an order cannot be
  verified without a result.
* Samples created directly as `Collected` always had a NULL `collection_date`
  because only the separate status endpoint set it.
* `POST /lab-samples/` forced the parent order to "Sample Collected" even for a
  Pending sample.
* Duplicate `test_code` returned HTTP 500 (the `IntegrityError` fires on
  `flush()`, which was outside the try block).
* `/backup/` returned only record counts — the downloaded "backup" could not
  restore anything. It now exports every business table.
* `/reports/lab-summary/` returned raw legacy report rows; it is now a real
  per-test aggregation (`func.case(...)` was also invalid — `case()` is a
  top-level SQLAlchemy construct).
* Monthly chart labels drifted (`timedelta(days=i*30)`); now calendar-correct, and
  six distinct months are asserted by a test.
* `seed_data` was unauthenticated and re-seeded on every call; now Admin-only and
  idempotent.
* `Patient` deletion had no guard against cascading clinical data loss; it now
  returns 409 unless `force=true`.
* Unbounded `limit` on list endpoints (`limit=1000000`); now capped.
* Rate-limiter and blacklist memory growth is bounded.
* `CORS_ORIGINS` is configurable via environment instead of a hard-coded list.

---

## 3. Laboratory module — new features

### Multi-parameter tests with reference ranges
New `lab_test_parameters` table. Each parameter carries a unit, a general
reference range, male/female/child ranges, and critical low/high limits — all
editable in the Test Master screen.

### Test panels / profiles
New `lab_panel_items` table plus `LabTestMaster.is_panel`. Ordering a panel
expands it into one order per member test (so the worklist shows real work) while
**the panel is billed once at the panel price**.

### Automatic abnormal flagging
`backend/lab_utils.py` parses ranges (`4.0 - 11.0`, `<200`, `>40`) and critical
limits to classify results as `Normal / Low / High / Critical Low / Critical High`.
Flags are recomputed **server-side** — a client claiming `Normal` for a critical
value is overridden.

### Result entry sheet pre-filled from the test definition
Opening *Enter Results* builds one row per parameter, with the age/gender-correct
reference range, a live flag preview, per-row remarks, and an interpretation field.
Draft saving and "Verify & Generate Report" share one endpoint.

### Order → bill linkage
`LabOrder.bill_id` + `POST /billing/lab/from-orders`. Select several orders in the
worklist and raise one bill; already-billed orders are rejected with 409, and
orders are linked back to the bill for traceability. This replaces the old
heuristic that guessed "billed" from *any* OP bill existing for the patient.

### TAT tracking
`tat_hours` is snapshotted per order, `due_at = order_date + TAT`, and the UI
shows an **Overdue (past TAT)** count plus per-row overdue highlighting and a
filter. `/lab/stats` reports TAT compliance percentage.

### Sample tracking
Auto-generated specimen barcodes, volume/container capture, and a
Pending → Collected → Received → Rejected → Recollected lifecycle.

### Verifiable, printable reports
`LabReport` gained `order_id`, `status`, `verified_by`, `verified_at` and
`is_abnormal`. Printing opens an **isolated window** with hospital letterhead,
patient/order metadata, reference ranges, abnormal rows highlighted, and the
verification block — instead of the old `window.print()` which printed the entire
application including the sidebar.

### Laboratory dashboard
`GET /lab/stats` powers eight live tiles (pending collection, collected/testing,
verified today, overdue, TAT compliance, lab revenue today, tests/panels, unbilled
orders) plus a due-sorted worklist.

### Roles and navigation
`Laboratory` now lands on the lab dashboard. Admin and Doctor get a full
**LABORATORY** nav section (dashboard, test master, orders, sample collection,
result entry, reports) — previously Admin could only reach a "Lab Reports" item
that rendered **nothing**, because no `activeTab === 'lab_reports'` block existed.

---

## 4. Frontend fixes

* **`npm run build` was broken** — 44 TypeScript errors (`noUnusedLocals`,
  missing interface fields, a mistyped result-entry row type, `selectedOPToken`
  possibly null, implicit `any`). All fixed.
* **Duplicated reports screen**: `activeTab === 'reports'` rendered twice — once a
  pharmacy invoice list, once the real reports page. The invoice list is now the
  `pharmacy_invoices` tab with its own nav entry.
* **Blank lab tab** for the Laboratory role and the Admin "Lab Reports" item.
* **Lab modals were nested inside the Lab Orders tab**, so "Enter Results" opened
  from the Result Entry tab rendered nothing. Found by the Playwright workflow
  test; the modals now live outside the per-tab blocks.
* **Data requests fired before login**, producing a burst of 401s on the login
  screen; the initial load effect is now gated on the authenticated user.
* **`.dashboard-grid` had no CSS** (only `.stat-grid` existed), so every stat card
  stacked vertically. Both classes are now defined.
* Lab billing assumptions removed; inventory search box and delete actions wired
  up; appointment delete wired up; CSV export of lab orders added.
* One-off editing scripts (`frontend/fix_*.py`, `edit*.py`, `backend/temp_migrate*.py`,
  `append_*.py`, `check_imports.py`) were removed — they contained hard-coded
  `f:\Hospital Soft\` paths and database passwords.

---

## 5. Structural changes

| Change | Why |
| --- | --- |
| `backend/constants.py` | Single source of truth for roles, statuses, payment modes; drives Pydantic `Literal` validation and workflow guards |
| `backend/lab_utils.py` | Range parsing, flag computation, barcode generation |
| `run_migrations()` in `database.py` | Replaces `ALTER TABLE … except Exception: pass` with an inspector-driven, idempotent migrator that also creates missing indexes |
| `backend/tests/` (77 tests) | Each test names the broken behaviour, so regressions are self-documenting |
| `requirements.txt` | The project had no dependency manifest; `psycopg2`/`passlib` were imported by deleted scripts but not installed |
| `pytest.ini` | Test discovery |

`DATABASE_URL` now also resolves the default SQLite path relative to the project
root, so starting uvicorn from another directory no longer silently creates a
second empty database.

---

## 6. Running it

Two supported ways to run the app locally. Both use the same backend; only the
frontend delivery differs.

### A. Development (Vite + API) — frontend on port 3000

```powershell
# terminal 1 - API
$env:SECRET_KEY = "<random-64-char-string>"     # optional; otherwise a local key is generated
python -m uvicorn backend.main:app --reload --port 8000

# terminal 2 - UI with hot reload
cd frontend
npm run dev -- --port 3000
```

Open **http://localhost:3000**. The dev bundle targets `http://127.0.0.1:8000`
for the API (`import.meta.env.DEV`), and `http://localhost:3000` is in the default
`CORS_ORIGINS` allow-list. Override the API target with `frontend/.env`
(see `frontend/.env.example`).

### B. Local deployment (single service) — everything on one port

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
.\run_app.ps1
```

| URL | What |
| --- | --- |
| http://127.0.0.1:8000/ | the application |
| http://127.0.0.1:8000/docs | OpenAPI / Swagger |
| http://127.0.0.1:8000/health | health probe |

* `-Rebuild` forces a fresh frontend build, `-NoBuild` skips npm entirely.
* `-Port 3000` deploys the whole app on another port.
* Stop with Ctrl+C.

Because the backend serves the bundle, production is same-origin — no second
server to keep alive and no CORS to configure. `frontend/src/App.tsx` derives its
API base from `window.location.origin` in a production build, so the UI follows
whatever host and port it was deployed to instead of being pinned to
`localhost:8000`.

### First login

The initial administrator is `admin`. If the database already had users it keeps
the existing password (`admin123` for this checkout); a brand-new database uses
`ADMIN_PASSWORD`, or `Admin@123` with a warning. **Rotate it immediately** via
*Change password* in the top bar — the policy requires 8+ characters with an
uppercase letter and a digit.

### Tests

```powershell
python -m pytest            # 104 backend tests
cd frontend; npx tsc --noEmit; npm run build
```

### Creating the hospital teams

Sign in as `admin` → **User Management** → pick a role (`Admin`, `Doctor`,
`Receptionist`, `Pharmacy`, `Laboratory`, `Insurance`, `Billing`) and create the
account. Roles can be changed later from the same table; your own row is locked so
you cannot demote yourself out of the admin area.

Patients create their own accounts from the sign-in screen — they are never created
from the staff screen.

---

## 7. Patient self-service and role-based modules

### 7.1 Roles

`constants.ROLES` now covers the whole hospital, and the split is enforced on the
server, not just hidden in the UI:

| Role | Owns |
| --- | --- |
| `Admin` | everything, plus users, audit log, settings, backup, seed |
| `Doctor` | case sheets / prescriptions, ordering labs, reading results |
| `Receptionist` | registration, OP tokens, appointments, OP/IP billing |
| `Pharmacy` | inventory and the dispensary (its own point-of-sale bill) |
| `Laboratory` | test master, orders, samples, results, lab reports, lab billing |
| `Insurance` | policies and claims; may read bills, may not edit them |
| `Billing` | OP/IP invoices, lab billing, pharmacy invoice reports |
| `Patient` | **only** its own records, through `/portal/*` |

Enforcement lives in one place: `AuthGuardMiddleware` declares a `ROLE_POLICY`
table of *"who may write what"* (`required_staff_roles()`). Reads stay open to all
staff — a doctor needs the patient list, the lab needs the case sheet — but
authoring in another team's module returns 403. This is deliberately a single
auditable table rather than a `Depends(...)` sprinkled across 50 routes.

The Admin's *User Management* screen was also missing `Insurance` and `Billing`
from its role dropdown, so those teams could not be created at all; the dropdown
now lists every staff role and the table has an inline role changer
(`PUT /users/{id}/role`), with your own row locked against self-demotion.

### 7.2 Patient self-registration

`POST /portal/register` is public and creates the **patient record and its login in
one transaction** — a half-created account (a login with no patient) would be
unrecoverable from the UI. If the mobile number already exists because of a prior
hospital visit, the new login is attached to that existing record instead of
duplicating the patient. Username/email collisions and weak passwords are rejected.

The sign-in screen has a *Register as a patient* flow; successful signup signs the
patient straight in.

### 7.3 The portal

| Area | What the patient can do |
| --- | --- |
| Overview | upcoming appointment, tests in progress, ready/abnormal reports, prescriptions, total billed |
| Appointments | book (date, slot, doctor, reason) and cancel; past appointments in a collapsible list |
| Prescriptions | every prescription with its medicines, timing, duration, advice and advised tests; print |
| Lab | live test progress (Pending → Sample Collected → Testing → Verified) and results with High/Low flags; view + print |
| Bills | OP, IP, pharmacy and lab bills with line items; print |
| Documents | one wallet combining prescriptions, lab reports, bills, discharge summaries and insurance claims |
| Profile | view the record, edit contact details, see policies and claims |

Aadhaar is returned **masked** (`XXXX-XXXX-1234`), and name/age/gender are
deliberately not self-editable — those must be corrected at the hospital desk.

### 7.4 Cross-patient isolation

This is the part that matters most, so it is structural rather than a check that can
be forgotten:

* Portal endpoints resolve the patient from the **token** (`get_current_patient`) and
  never accept a patient id from the request. Bookings are created with
  `patient_id` taken from the account, so a patient cannot book or read on somebody
  else's behalf.
* Cancelling another patient's appointment returns **404, not 403**, so patient ids
  cannot be probed.
* The middleware blocks `Patient` accounts from every non-`/portal/*` route, and
  blocks staff from `/portal/*`.

Tests: `TestPatientPortal` (registration, isolation, booking rules, documents,
Aadhaar masking) and `TestRoleBasedAccess` (per-role authoring limits).

### 7.5 Insurance module

New `InsurancePolicy` and `InsuranceClaim` tables with a claim lifecycle
(`Draft → Submitted → Under Review → Approved / Partially Approved / Rejected →
Settled`) enforced by `INSURANCE_CLAIM_TRANSITIONS`:

* `patient_payable` is derived from `claimed − approved` when not supplied.
* Approving requires an amount; rejecting requires a reason; `Settled`/`Rejected`
  are terminal.
* A claim cannot reference another patient's policy or bill.
* The Insurance Desk has its own dashboard (claim pipeline, claimed/approved/pending
  amounts) and policy register; patients see their own policies and claims read-only
  in the portal.

---

## 8. Complete workflow per role

Each role now lands on **one screen that contains its whole job** — live counters,
a numbered step guide with real counts, and stage lanes with inline actions — instead
of a dashboard plus a handful of scattered (and in several cases duplicated) tabs.
The shared `RoleFlow` component renders it, so every role reads the same way.

| Role | Page | Flow |
| --- | --- | --- |
| Front Desk (Admin & Receptionist) | Front Desk Flow | register → token → queue → appointment → bill → payment |
| Doctor | My Workflow | pick patient → case sheet → prescribe → order labs → review results → send to billing |
| Laboratory | Lab Dashboard | receive → collect → run → enter results → verify & report → bill |
| Pharmacy | Pharmacy Flow | check stock → dispense → load prescription → purchase/GRN → reorder → expiry |
| Insurance | Claims Dashboard | policy → claim → submit → approve/reject → settle |
| Billing | OP/IP Billing + Lab Billing | raise invoices, lab billing, pharmacy invoice reports |
| Patient | Patient Portal | overview → appointments → prescriptions → labs → bills → documents → profile |

### Dead and duplicated navigation replaced

* The **Pharmacy** sidebar had **five** entries all pointing at the same `inventory`
  tab (`Purchase`, `Expiry Management`, `Inventory`, `Medicine Search`, `Medicine
  Stock`). These are now four real screens: *Purchase / GRN* (with a reorder list and
  a one-click "Receive"), *Expiry Management* (expired vs expiring-in-90-days, stock
  value at risk, write-off against a stock movement), *Medicine Search* (name, batch,
  category or barcode, with add-to-cart) and *Full Inventory*.
* **Admin/Doctor** had `OP Casesheet` and `Write Prescription` — two nav items,
  same tab. Doctor now has its own dedicated sidebar.
* The **Patient Database** "View History" button had **no handler at all** — it did
  nothing. It is now **Patient 360**: one screen with demographics, prescriptions
  (printable), lab orders and reports (printable), OP/IP/lab bills, admissions and
  insurance, loaded via `Promise.allSettled` so a desk that may not read one module
  still gets the rest. The Front Desk, Doctor, Laboratory and Billing boards all
  link into it.
* The live-queue "Mark Waiting" button called `PUT /tokens/{id}?status=Waiting` —
  the wrong endpoint *and* a status that is not in `OP_TOKEN_STATUSES`, so it could
  never work. Replaced by proper `Call in` / `Consulted` / `Bill` actions wired to
  `PUT /tokens/{id}/status`.
* The **Receptionist** had no route to billing at all, despite the role policy
  allowing it. Added *Billing & Payment* and *IP Admissions*.

The lab board's stage actions were verified to drive real state: collecting from the
*Pending collection* lane moved the order to `Sample Collected`, and verifying from
the *Sample collected* lane produced a `Verified` report.

---

## 9. Production foundations & the IPD module

### 9.1 Phase A — foundations

| Added | Why |
| --- | --- |
| `backend/config.py` | One validated `Settings` object. A production start is **refused** on SQLite, a missing/short `SECRET_KEY`, `TRUSTED_HOSTS=*` or `DEBUG=on` |
| Alembic (`alembic/`, `0001_baseline`, `0002_ipd_module`) | Replaces the ad-hoc schema sync. The baseline was proved **identical to the models** (25 tables, 0 column mismatches) |
| `backend/migrations.py` | Adopts a pre-Alembic database by *stamping* the baseline instead of re-creating its tables |
| Engine options | Pooling/recycle for PostgreSQL; audit found **no SQLite-specific SQL** in business logic |
| Naming convention on `Base.metadata` | Deterministic constraint names, so SQLite batch rewrites and future migrations work without hand-naming |

`run_migrations()` is retained **only** to adopt databases that predate Alembic. New schema changes must be an Alembic revision.

### 9.2 Phase B — inpatient (IPD)

**10 new tables:** `departments`, `wards`, `rooms`, `beds`, `bed_allocations`, `patient_transfers`, `nursing_notes`, `medication_orders`, `medication_administrations`, `discharge_summaries` — plus a staff master on `users` (employee code, designation, specialization, licence, department, joining date, consultation fee) and bed/attending-doctor/department/admission-type on `ip_admissions`.

**34 new endpoints** (`structure`, `ipd`, `staff` tags), with a new **Nurse** role in the policy table (nurses chart vitals and administer medication; pharmacy cannot).

**Invariants enforced server-side, not in the UI:**

* Occupancy is owned by `bed_allocations`, never by the `beds.status` field. A bed cannot be hand-marked `Occupied`, and an occupied bed cannot be freed without discharging or transferring.
* Admission + allocation happen in one transaction — a failed admission cannot leave a bed stuck Occupied.
* Discharge releases the bed to **`Cleaning`**, not `Available`, so housekeeping must clear it before the next patient.
* A discharge requires a saved summary unless explicitly overridden.
* Vital signs are re-checked on the server: a client claiming "not critical" for SpO₂ 88 is overridden.
* Approving a discharge summary requires `Final` first, and an approved summary is locked.

**Frontend:** the hard-coded `HOSPITAL_LAYOUT` bed picker (`GW-1…GW-10`, matching occupancy by comparing a room number to a bed id) is **gone** — the bed board, ward tabs and admission form are driven by `/ipd/bed-board`. New screens: *Inpatient Ward* (live bed board + ward metrics + admitted patients) and *Ward & Bed Setup*, plus a ward record workspace for vitals, medication administration and the printable discharge summary.

### 9.3 Bugs found during this work

| Bug | Impact |
| --- | --- |
| `IPAdmissionDetail` typed nested collections as `List[Dict]` while the CRUD passed ORM objects | 500 on any admission that actually had nursing notes |
| `/wards/` does not return rooms | the bed-creation form had no room options — a new bed could never be created from the UI |
| `NOT NULL` columns added without a default in the IPD migration | would have failed on any database containing admissions |
| Circular FK `users.department_id` ↔ `departments.head_doctor_id` | SQLAlchemy could not order tables; resolved with `use_alter=True` |
| The IP Admissions screen showed `#{patient_id}`, never the patient's name | clinical-safety defect |
| The rate limiter rejected the test suite (429) | root-caused by moving the hard-coded limit into config |

---

## 10. Flutter mobile client (`mobile/`)

A companion app for Android and iOS, sharing the same REST API as the web console.

| Layer | Contents |
| --- | --- |
| `core/config.dart` | Platform-aware API base. Android emulators reach the host at `10.0.2.2`; `--dart-define=API_BASE=…` overrides for a real deployment |
| `core/api_client.dart` | Typed client over the REST API. On a 401 it refreshes the access token once and replays the request; FastAPI `detail` strings (including validation-error lists) are surfaced as readable messages |
| `core/models.dart` | Models mirroring the Pydantic schemas, each with `fromJson` |
| `core/theme.dart` | Shared palette, status chips, empty/error states and Indian-format currency |
| `features/auth` | Sign-in; the stored token is re-validated against `/users/me` on launch rather than trusted |
| `features/patient` | Dashboard (next appointment, pending tests, abnormal-report alert, billed total), appointment booking with server-provided slots, and a record browser (prescriptions, lab reports, bills, documents) |
| `features/staff` | Live bed board with status/ward filters, ward metrics, and a ward record for charting vitals and recording medication (MAR) |

**Role routing:** patients get the portal shell; ward staff get the bed board. The backend enforces authorisation regardless — the app only chooses what to show.

**Android network policy:** `network_security_config.xml` permits cleartext **only** for `10.0.2.2`, `localhost` and `127.0.0.1`; every other host requires TLS, so a production build cannot silently fall back to plaintext.

### Verification

| Check | Result |
| --- | --- |
| `flutter analyze` | **No issues found** |
| `flutter test` (unit) | **20 passed** — model parsing, null-safety of partial records, Indian currency grouping, status colours, date rendering |
| `flutter build apk --debug` | **Built** `app-debug.apk` |
| `flutter test test/live_api_test.dart` | **Not yet run** — see below |

---

## 11. Clinical audit trail (`backend/audit.py`, migration `0003_clinical_audit`)

Clinical records had no change history and no authorship — for a hospital that is
a regulatory gap, not a nicety.

- `audit_logs` gained `actor_role`, `entity_type`, `entity_id`, `patient_id` and
  `before_state` / `after_state`. A `ClinicalAuditMixin` adds `created_by` /
  `updated_by` to nine clinical tables.
- Both states are stored as **full snapshots**, so a consumer derives the diff and
  an unchanged field can never be mistaken for a change.
- The audit row commits **in the same transaction** as the change: a rejected
  operation leaves no entry, and a change cannot be recorded without its trail.
- **Append-only by construction** — there is no write endpoint. The suite actively
  tries `PUT`/`PATCH`/`POST`/`DELETE` against the log and asserts `405`/`404`,
  then confirms the entry count is unchanged.
- UI: the Admin audit tab shows actor + role, the linked record, filters, and
  expandable Before → After diffs; the ward record shows the patient's clinical
  history timeline.

### Bug found by looking at the screenshot

The first version reported **"13 fields changed"** on a medication stop, listing
`admission_id`, `dose` and `id` as changed when only the status had. Cause:
`record_change` stored `before` as a full snapshot but `after` as a nested diff.
Both sides are now full snapshots; it correctly reports 3 fields.

---

## 12. Mobile API contract verification

`flutter test` cannot run in this environment (Flutter shells out to `git` inside
its SDK at `C:\flutter`, which the sandbox blocks). So the contract the Dart
models depend on was verified from Python against the running server instead —
**97/97 field expectations satisfied**.

That check found three real defects the live test would have caught:

| Defect | Impact |
| --- | --- |
| The Dart client called `/portal/doctors/{id}/slots` — **that endpoint does not exist** | every booking attempt would 404 |
| `/portal/doctors` returned only `{id, name, department}` while the model read `full_name`, `specialization`, `consultation_fee` | doctor cards would render blank |
| `/portal/slots` returned a static roster, ignoring doctor, date and existing bookings | patients were offered times that booking then rejected with 409 |

Fixed at the root, additively: `PortalDoctor` gained `specialization` and
`consultation_fee`; `/portal/slots` accepts optional `doctor_id` +
`appointment_date` and returns only genuinely free times via `crud.available_slots()`,
which mirrors the booking clash check. Without those parameters it behaves as before.

The booking clash rule is per **patient and time**, not per doctor — you cannot be
in two places at once. A test asserting otherwise was wrong and was corrected.

---

## 13. Full cross-role regression (57/57)

| Role | Screens walked | JS errors | API 5xx |
| --- | --- | --- | --- |
| Admin | all | 0 | 0 |
| Doctor | 7 | 0 | 0 |
| Nurse | 4 | 0 | 0 |
| Receptionist | 9 | 0 | 0 |
| Pharmacy | 8 | 0 | 0 |
| Laboratory | 6 | 0 | 0 |
| Insurance | 3 | 0 | 0 |
| Billing | 5 | 0 | 0 |
| Patient (portal) | 7 sections | 0 | 0 |

Every screen rendered content; the patient portal showed the patient's own record
and no staff navigation; the bed board, IPD stats and audit trail all read back
correctly.

---

## 14. Notes on the previous deployment scripts

`run_app.ps1`, `setup_env.ps1` and `start_db.ps1` referenced paths that do not
exist on this machine (`f:\Hospital Soft`, `d:\H`) and `run_app.ps1` ended with
`Stop-Process -Name "python"` / `Stop-Process -Name "node"` — a blanket kill of
**every** Python and Node process on the computer, including unrelated
applications. `run_app.ps1` has been rewritten to resolve paths from
`$PSScriptRoot`, verify only its own dependencies, deploy the SQLite default (or an
explicit `DATABASE_URL`), and stop cleanly on Ctrl+C without touching anything it
did not start.

`setup_env.ps1` / `start_db.ps1` (the PostgreSQL bootstrap) were left untouched —
they belong to the portable-installer flow and are not used by the default SQLite
deployment.
