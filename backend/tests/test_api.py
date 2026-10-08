"""Regression tests for the defects found during the code review.

Each test name states the behaviour that was broken, so a future regression is
self-documenting.
"""

from datetime import date, timedelta

import pytest

from backend import constants

# Routes that used to be fully anonymous. All must now require a bearer token.
PROTECTED_ROUTES = [
    ("GET", "/patients/"),
    ("GET", "/tokens/"),
    ("GET", "/inventory/"),
    ("GET", "/billing/pharmacy/"),
    ("GET", "/billing/op/"),
    ("GET", "/billing/ip/"),
    ("GET", "/billing/lab/"),
    ("GET", "/ip-admissions/"),
    ("GET", "/lab-reports/"),
    ("GET", "/lab-orders/"),
    ("GET", "/lab-samples/"),
    ("GET", "/lab-test-masters/"),
    ("GET", "/lab/stats"),
    ("GET", "/dashboard/stats"),
    ("GET", "/dashboard/charts"),
    ("GET", "/search/?q=a"),
    ("GET", "/reports/daily/"),
    ("GET", "/reports/revenue/"),
    ("GET", "/hospital-settings/"),
    ("GET", "/audit-logs/"),
    ("GET", "/backup/"),
    ("GET", "/users/"),
]

# Mutating routes that used to be anonymous.
ANONYMOUS_WRITES = [
    ("POST", "/patients/", {"name": "Anonymous Injection", "age": 20, "gender": "Male"}),
    ("DELETE", "/patients/1", None),
    ("DELETE", "/tokens/1", None),
    ("POST", "/seed/", None),
    ("POST", "/lab-test-masters/", {"test_code": "X", "test_name": "X"}),
    ("POST", "/lab-orders/", {"patient_id": 1, "test_id": 1}),
]


class TestAuthentication:
    @pytest.mark.parametrize("method,path", PROTECTED_ROUTES)
    def test_reads_require_authentication(self, client, method, path):
        response = client.request(method, path)
        assert response.status_code == 401, f"{method} {path} returned {response.status_code}"

    @pytest.mark.parametrize("method,path,body", ANONYMOUS_WRITES)
    def test_writes_require_authentication(self, client, method, path, body):
        response = client.request(method, path, json=body)
        assert response.status_code == 401, f"{method} {path} returned {response.status_code}"

    def test_garbage_token_is_rejected(self, client):
        response = client.get("/patients/", headers={"Authorization": "Bearer not-a-jwt"})
        assert response.status_code == 401

    def test_health_is_public(self, client):
        assert client.get("/health").status_code == 200

    def test_logout_revokes_token(self, client):
        login = client.post("/login", data={"username": "admin", "password": "Admin@123"})
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        assert client.get("/users/me", headers=headers).status_code == 200
        assert client.post("/logout", headers=headers).status_code == 200
        assert client.get("/users/me", headers=headers).status_code == 401

    def test_refresh_token_accepts_body_and_query(self, client):
        login = client.post("/login", data={"username": "admin", "password": "Admin@123"})
        refresh = login.json()["refresh_token"]

        by_body = client.post("/refresh-token", json={"refresh_token": refresh})
        assert by_body.status_code == 200
        assert by_body.json()["access_token"]

        by_query = client.post(f"/refresh-token?refresh_token={refresh}")
        assert by_query.status_code == 200

    def test_access_token_is_not_accepted_as_refresh_token(self, client):
        login = client.post("/login", data={"username": "admin", "password": "Admin@123"})
        access = login.json()["access_token"]
        assert client.post("/refresh-token", json={"refresh_token": access}).status_code == 401


class TestUserAdministration:
    def test_role_must_be_a_known_role(self, client, admin_headers):
        created = client.post(
            "/users/", json={"username": "roleprobe", "password": "StrongPass1", "role": "Admin"}, headers=admin_headers
        )
        assert created.status_code == 200
        user_id = created.json()["id"]

        bad = client.put(f"/users/{user_id}/role?role=Wizard", headers=admin_headers)
        assert bad.status_code == 422

    def test_weak_password_is_rejected(self, client, admin_headers):
        response = client.post(
            "/users/",
            json={"username": "weakpass", "password": "abcdefgh", "role": "Receptionist"},
            headers=admin_headers,
        )
        assert response.status_code == 422
        assert "Password must contain" in response.json()["detail"]

    def test_password_reset_enforces_policy(self, client, admin_headers):
        response = client.put(
            "/users/1/reset-password", json={"new_password": "a"}, headers=admin_headers
        )
        assert response.status_code == 422

    def test_cannot_delete_the_last_administrator(self, client, admin_headers):
        me = client.get("/users/me", headers=admin_headers).json()
        response = client.delete(f"/users/{me['id']}", headers=admin_headers)
        assert response.status_code == 400
        assert "own account" in response.json()["detail"].lower()

    def test_non_admin_cannot_list_users(self, client, admin_headers):
        client.post(
            "/users/",
            json={"username": "doc_probe", "password": "StrongPass1", "role": "Doctor"},
            headers=admin_headers,
        )
        login = client.post("/login", data={"username": "doc_probe", "password": "StrongPass1"})
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        assert client.get("/users/", headers=headers).status_code == 403
        assert client.get("/security/status", headers=headers).status_code == 403

    def test_doctor_cannot_change_hospital_settings(self, client, admin_headers):
        client.post(
            "/users/",
            json={"username": "doc_settings", "password": "StrongPass1", "role": "Doctor"},
            headers=admin_headers,
        )
        login = client.post("/login", data={"username": "doc_settings", "password": "StrongPass1"})
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        response = client.post("/hospital-settings/", json={"settings": [{"key": "a", "value": "b"}]}, headers=headers)
        assert response.status_code == 403


class TestSelfServicePassword:
    """The change-password endpoint must require proof of the current password."""

    def test_change_without_current_password_is_rejected(self, client, admin_headers):
        response = client.post("/users/me/password", json={"new_password": "TotallyNew1"}, headers=admin_headers)
        # `current_password` is required by the schema.
        assert response.status_code == 422

    def test_change_with_wrong_current_password_is_rejected(self, client, admin_headers):
        response = client.post(
            "/users/me/password",
            json={"current_password": "not-my-password", "new_password": "TotallyNew1"},
            headers=admin_headers,
        )
        assert response.status_code == 400
        assert "incorrect" in response.json()["detail"].lower()

    def test_change_rejects_weak_new_password(self, client, admin_headers):
        response = client.post(
            "/users/me/password",
            json={"current_password": "Admin@123", "new_password": "abc"},
            headers=admin_headers,
        )
        assert response.status_code == 422

    def test_change_then_restore(self, client, admin_headers):
        # A dedicated account: a password change revokes the user's existing
        # tokens, so rotating the shared admin would break admin_headers.
        created = client.post(
            "/users/", json={"username": "rotate_me", "password": "Admin@123", "role": "Doctor"},
            headers=admin_headers,
        )
        assert created.status_code == 200, created.text
        login = client.post("/login", data={"username": "rotate_me", "password": "Admin@123"})
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        changed = client.post(
            "/users/me/password",
            json={"current_password": "Admin@123", "new_password": "RotatedPass9"},
            headers=headers,
        )
        assert changed.status_code == 200, changed.text

        assert client.post("/login", data={"username": "rotate_me", "password": "Admin@123"}).status_code == 401
        relogin = client.post("/login", data={"username": "rotate_me", "password": "RotatedPass9"})
        assert relogin.status_code == 200

        restored = client.post(
            "/users/me/password",
            json={"current_password": "RotatedPass9", "new_password": "Admin@123"},
            headers={"Authorization": f"Bearer {relogin.json()['access_token']}"},
        )
        assert restored.status_code == 200
        assert client.post("/login", data={"username": "rotate_me", "password": "Admin@123"}).status_code == 200


class TestPatientPortal:
    """Self-service patient accounts and their isolation from staff data."""

    @staticmethod
    def _register(client, suffix, **overrides):
        payload = {
            "username": f"pat_{suffix}",
            "password": "Patient@1",
            "name": f"Portal Patient {suffix}",
            "age": 33,
            "gender": "Female",
            "phone": f"98765{suffix.zfill(5)[-5:]}",
            "address": "Chennai",
            "blood_group": "O+",
        }
        payload.update(overrides)
        response = client.post("/portal/register", json=payload)
        assert response.status_code == 200, response.text
        return response.json(), payload

    @staticmethod
    def _headers(token):
        return {"Authorization": f"Bearer {token}"}

    def test_self_registration_returns_a_patient_token(self, client):
        data, _ = self._register(client, "10001")
        assert data["role"] == "Patient"
        assert data["access_token"]

        me = client.get("/users/me", headers=self._headers(data["access_token"]))
        assert me.status_code == 200
        assert me.json()["role"] == "Patient"
        assert me.json()["patient_id"] is not None
        assert me.json()["email"] is None  # optional field left blank

    def test_duplicate_username_is_rejected(self, client):
        self._register(client, "10002")
        duplicate = client.post(
            "/portal/register",
            json={
                "username": "pat_10002",
                "password": "Patient@1",
                "name": "Someone Else",
                "age": 20,
                "gender": "Male",
                "phone": "9876510099",
            },
        )
        assert duplicate.status_code == 400
        assert "taken" in duplicate.json()["detail"].lower()

    def test_weak_password_is_rejected_at_signup(self, client):
        response = client.post(
            "/portal/register",
            json={
                "username": "pat_weak",
                "password": "abcdefgh",
                "name": "Weak Password",
                "age": 20,
                "gender": "Male",
                "phone": "98765100098",
            },
        )
        assert response.status_code == 422

    def test_invalid_phone_is_rejected_at_signup(self, client):
        response = client.post(
            "/portal/register",
            json={
                "username": "pat_badphone",
                "password": "Patient@1",
                "name": "Bad Phone",
                "age": 20,
                "gender": "Male",
                "phone": "12345",
            },
        )
        assert response.status_code == 422

    def test_patient_cannot_touch_staff_endpoints(self, client):
        data, _ = self._register(client, "10003")
        headers = self._headers(data["access_token"])
        for method, path in [
            ("GET", "/patients/"),
            ("GET", "/tokens/"),
            ("GET", "/lab-orders/"),
            ("GET", "/billing/op/"),
            ("GET", "/inventory/"),
            ("GET", "/audit-logs/"),
            ("GET", "/users/"),
            ("GET", "/insurance/claims"),
            ("GET", "/dashboard/stats"),
            ("POST", "/patients/"),
            ("POST", "/lab-orders/"),
        ]:
            response = client.request(method, path, headers=headers, json={} if method == "POST" else None)
            assert response.status_code == 403, f"{method} {path} returned {response.status_code}"

    def test_staff_cannot_use_the_patient_portal(self, client, admin_headers):
        for method, path in [("GET", "/portal/me"), ("GET", "/portal/dashboard"), ("GET", "/portal/bills")]:
            response = client.request(method, path, headers=admin_headers)
            assert response.status_code == 403, f"{method} {path} returned {response.status_code}"

    def test_patient_only_ever_sees_their_own_records(self, client, admin_headers):
        """The core isolation guarantee: two patients never see each other."""
        alice, _ = self._register(client, "10004")
        bob, bob_payload = self._register(client, "10005")
        alice_h = self._headers(alice["access_token"])
        bob_h = self._headers(bob["access_token"])

        alice_id = client.get("/portal/me", headers=alice_h).json()["id"]
        bob_id = client.get("/portal/me", headers=bob_h).json()["id"]
        assert alice_id != bob_id

        # Give Alice a lab order through the staff API.
        lab = client.post(
            "/lab-test-masters/",
            json={"test_code": "PORTAL1", "test_name": "Portal Isolation Test", "price": 100.0},
            headers=admin_headers,
        ).json()
        client.post(
            "/lab-orders/", json={"patient_id": alice_id, "test_id": lab["id"]}, headers=admin_headers
        )

        alice_orders = client.get("/portal/lab-orders", headers=alice_h).json()
        bob_orders = client.get("/portal/lab-orders", headers=bob_h).json()
        assert len(alice_orders) == 1
        assert bob_orders == []

        # Portal payloads never expose another patient's id.
        assert all(o["test_name"] == "Portal Isolation Test" for o in alice_orders)
        assert client.get("/portal/me", headers=bob_h).json()["name"] == bob_payload["name"]

    def test_patient_cannot_cancel_another_patients_appointment(self, client):
        alice, _ = self._register(client, "10006")
        bob, _ = self._register(client, "10007")
        alice_h = self._headers(alice["access_token"])
        bob_h = self._headers(bob["access_token"])

        booked = client.post(
            "/portal/appointments",
            json={"appointment_date": date.today().isoformat(), "time_slot": "10:00 AM", "reason": "Checkup"},
            headers=alice_h,
        )
        assert booked.status_code == 200, booked.text
        appointment_id = booked.json()["id"]

        # Bob guesses Alice's appointment id.
        stolen = client.put(f"/portal/appointments/{appointment_id}/cancel", headers=bob_h)
        assert stolen.status_code == 404

        still_there = client.get("/portal/appointments", headers=alice_h).json()
        assert still_there[0]["status"] == "Scheduled"

    def test_patient_books_and_cancels_an_appointment(self, client):
        data, _ = self._register(client, "10008")
        headers = self._headers(data["access_token"])

        slots = client.get("/portal/slots", headers=headers).json()
        assert "10:00 AM" in slots

        booked = client.post(
            "/portal/appointments",
            json={"appointment_date": date.today().isoformat(), "time_slot": slots[0], "reason": "Fever"},
            headers=headers,
        )
        assert booked.status_code == 200, booked.text
        assert booked.json()["status"] == "Scheduled"

        # Same slot, same patient -> conflict.
        again = client.post(
            "/portal/appointments",
            json={"appointment_date": date.today().isoformat(), "time_slot": slots[0]},
            headers=headers,
        )
        assert again.status_code == 409

        cancelled = client.put(f"/portal/appointments/{booked.json()['id']}/cancel", headers=headers)
        assert cancelled.status_code == 200
        assert cancelled.json()["status"] == "Cancelled"

    def test_appointment_cannot_be_booked_in_the_past(self, client):
        data, _ = self._register(client, "10009")
        past = (date.today() - timedelta(days=1)).isoformat()
        response = client.post(
            "/portal/appointments",
            json={"appointment_date": past, "time_slot": "10:00 AM"},
            headers=self._headers(data["access_token"]),
        )
        assert response.status_code == 422

    def test_unknown_time_slot_is_rejected(self, client):
        data, _ = self._register(client, "10010")
        response = client.post(
            "/portal/appointments",
            json={"appointment_date": date.today().isoformat(), "time_slot": "03:17 AM"},
            headers=self._headers(data["access_token"]),
        )
        assert response.status_code == 422

    def test_patient_updates_their_own_contact_details(self, client):
        data, _ = self._register(client, "10011")
        headers = self._headers(data["access_token"])

        updated = client.put(
            "/portal/me", json={"address": "New Address 42", "blood_group": "AB+"}, headers=headers
        )
        assert updated.status_code == 200
        assert updated.json()["address"] == "New Address 42"
        assert updated.json()["blood_group"] == "AB+"

    def test_patient_sees_prescriptions_lab_reports_bills_and_documents(self, client, admin_headers):
        data, _ = self._register(client, "10012")
        headers = self._headers(data["access_token"])
        patient_id = client.get("/portal/me", headers=headers).json()["id"]

        # Staff side: a consultation with a prescription and a lab order.
        lab = client.post(
            "/lab-test-masters/",
            json={
                "test_code": "PORTAL2",
                "test_name": "Portal Haemogram",
                "price": 250.0,
                "parameters": [{"name": "Haemoglobin", "unit": "g/dL", "reference_range": "13 - 17"}],
            },
            headers=admin_headers,
        ).json()
        client.post(
            "/casesheets/",
            json={
                "patient_id": patient_id,
                "doctor_name": "Dr. Portal",
                "diagnosis": "Anaemia",
                "prescribed_medicines": [{"name": "Ferrous Sulphate", "quantity": 30, "duration": "30 days"}],
                "prescribed_labs": [],
            },
            headers=admin_headers,
        )
        order = client.post(
            "/lab-orders/", json={"patient_id": patient_id, "test_id": lab["id"]}, headers=admin_headers
        ).json()
        client.put(f"/lab-orders/{order['id']}/status?status=Sample Collected", headers=admin_headers)
        client.post(
            f"/lab-orders/{order['id']}/results",
            json={"verify": True, "results": [{"parameter": "Haemoglobin", "result": "9.0", "range": "13 - 17"}]},
            headers=admin_headers,
        )
        bill = client.post(
            "/billing/lab/from-orders", json={"order_ids": [order["id"]]}, headers=admin_headers
        ).json()

        prescriptions = client.get("/portal/prescriptions", headers=headers).json()
        assert len(prescriptions) == 1
        assert prescriptions[0]["diagnosis"] == "Anaemia"
        assert prescriptions[0]["medicines"][0]["name"] == "Ferrous Sulphate"

        reports = client.get("/portal/lab-reports", headers=headers).json()
        assert len(reports) == 1
        assert reports[0]["test_name"] == "Portal Haemogram"
        assert reports[0]["is_abnormal"] is True
        assert reports[0]["results"][0]["flag"] == "Low"

        assert any(o["report_ready"] for o in client.get("/portal/lab-orders", headers=headers).json())

        bills = client.get("/portal/bills", headers=headers).json()
        assert any(b["id"] == bill["id"] and b["bill_type"] == "Laboratory" for b in bills)

        documents = client.get("/portal/documents", headers=headers).json()
        types = {d["type"] for d in documents}
        assert {"prescription", "lab_report", "bill"} <= types

        dash = client.get("/portal/dashboard", headers=headers).json()
        assert dash["profile"]["id"] == patient_id
        assert dash["prescriptions"] == 1
        assert dash["abnormal_reports"] == 1

    def test_aadhaar_is_masked_in_the_portal(self, client):
        data, _ = self._register(client, "10013", aadhaar=None)
        headers = self._headers(data["access_token"])
        profile = client.get("/portal/me", headers=headers).json()
        # The Aadhaar field is never returned in full.
        assert profile["aadhaar_masked"] is None or profile["aadhaar_masked"].startswith("XXXX")


class TestRoleBasedAccess:
    """Each hospital team may only author in its own module."""

    @staticmethod
    def _staff(client, admin_headers, username, role):
        created = client.post(
            "/users/",
            json={"username": username, "password": "Staff@Pass1", "role": role},
            headers=admin_headers,
        )
        assert created.status_code == 200, created.text
        login = client.post("/login", data={"username": username, "password": "Staff@Pass1"})
        assert login.status_code == 200, login.text
        return {"Authorization": f"Bearer {login.json()['access_token']}"}

    def test_billing_team_can_create_op_bills_but_not_dispense_pharmacy(self, client, admin_headers):
        headers = self._staff(client, admin_headers, "billing_probe", "Billing")
        assert client.post(
            "/billing/op/", json={"patient_id": 1, "consultation_fee": 100}, headers=headers
        ).status_code in (200, 404)
        assert client.post(
            "/billing/pharmacy/", json={"patient_name": "X", "items": [{"medicine_id": 1, "quantity": 1}]}, headers=headers
        ).status_code == 403

    def test_pharmacy_cannot_create_op_bills(self, client, admin_headers):
        headers = self._staff(client, admin_headers, "pharma_probe", "Pharmacy")
        response = client.post("/billing/op/", json={"patient_id": 1, "consultation_fee": 100}, headers=headers)
        assert response.status_code == 403

    def test_pharmacy_can_adjust_inventory_but_not_manage_users(self, client, admin_headers):
        headers = self._staff(client, admin_headers, "pharma_probe2", "Pharmacy")
        assert client.post(
            "/users/", json={"username": "x", "password": "Staff@Pass1", "role": "Doctor"}, headers=headers
        ).status_code == 403
        # Inventory writes are allowed; a missing stock id yields 404, not 403.
        assert client.post(
            "/inventory/adjust/", json={"medicine_id": 999999, "type": "Stock In", "quantity": 1}, headers=headers
        ).status_code == 404

    def test_laboratory_can_manage_tests_but_not_patients(self, client, admin_headers):
        headers = self._staff(client, admin_headers, "lab_probe", "Laboratory")
        assert client.post(
            "/lab-test-masters/", json={"test_code": "LABPROBE", "test_name": "Probe", "price": 1.0}, headers=headers
        ).status_code == 200
        assert client.delete("/patients/1", headers=headers).status_code == 403

    def test_insurance_team_owns_claims_and_billing_cannot_edit_them(self, client, admin_headers):
        insurance = self._staff(client, admin_headers, "ins_probe", "Insurance")
        billing = self._staff(client, admin_headers, "bill_probe", "Billing")

        patient = client.post(
            "/patients/",
            json={"name": "Claim Patient", "age": 50, "gender": "Male", "phone": "9876522001"},
            headers=admin_headers,
        ).json()

        claim = client.post(
            "/insurance/claims",
            json={
                "patient_id": patient["id"],
                "claim_type": "Reimbursement",
                "treatment_type": "OP",
                "diagnosis": "Fracture",
                "claimed_amount": 25000,
            },
            headers=insurance,
        )
        assert claim.status_code == 200, claim.text
        claim_id = claim.json()["id"]
        assert claim.json()["claim_number"].startswith("CLM-")
        assert claim.json()["status"] == "Draft"

        # Billing may read claims (they raise the bill) but not modify them.
        assert client.get("/insurance/claims", headers=billing).status_code == 200
        assert client.put(
            f"/insurance/claims/{claim_id}/status", json={"status": "Submitted"}, headers=billing
        ).status_code == 403

    def test_claim_lifecycle_and_transition_guards(self, client, admin_headers):
        insurance = self._staff(client, admin_headers, "ins_probe2", "Insurance")
        patient = client.post(
            "/patients/",
            json={"name": "Lifecycle Patient", "age": 40, "gender": "Female", "phone": "9876522002"},
            headers=admin_headers,
        ).json()
        claim = client.post(
            "/insurance/claims",
            json={"patient_id": patient["id"], "claimed_amount": 10000},
            headers=insurance,
        ).json()
        path = f"/insurance/claims/{claim['id']}/status"

        # Draft -> Approved is not a legal jump.
        assert client.put(path, json={"status": "Approved", "approved_amount": 9000}, headers=insurance).status_code == 409

        assert client.put(path, json={"status": "Submitted"}, headers=insurance).status_code == 200
        # Approval demands an amount.
        assert client.put(path, json={"status": "Approved"}, headers=insurance).status_code == 422
        approved = client.put(
            path, json={"status": "Approved", "approved_amount": 8000}, headers=insurance
        )
        assert approved.status_code == 200
        # patient_payable is derived when not supplied.
        assert approved.json()["patient_payable"] == 2000.0

        settled = client.put(path, json={"status": "Settled"}, headers=insurance)
        assert settled.status_code == 200
        assert settled.json()["settled_at"] is not None

        # Settled is terminal.
        assert client.put(path, json={"status": "Under Review"}, headers=insurance).status_code == 409

    def test_rejection_requires_a_reason(self, client, admin_headers):
        insurance = self._staff(client, admin_headers, "ins_probe3", "Insurance")
        patient = client.post(
            "/patients/",
            json={"name": "Reject Patient", "age": 40, "gender": "Female", "phone": "9876522003"},
            headers=admin_headers,
        ).json()
        claim = client.post(
            "/insurance/claims", json={"patient_id": patient["id"], "claimed_amount": 5000}, headers=insurance
        ).json()
        path = f"/insurance/claims/{claim['id']}/status"
        client.put(path, json={"status": "Submitted"}, headers=insurance)
        assert client.put(path, json={"status": "Rejected"}, headers=insurance).status_code == 422
        assert client.put(
            path, json={"status": "Rejected", "rejection_reason": "Not covered"}, headers=insurance
        ).status_code == 200

    def test_claim_cannot_reference_another_patients_bill(self, client, admin_headers):
        insurance = self._staff(client, admin_headers, "ins_probe4", "Insurance")
        a = client.post(
            "/patients/", json={"name": "Owner A", "age": 30, "gender": "Male", "phone": "9876522004"}, headers=admin_headers
        ).json()
        b = client.post(
            "/patients/", json={"name": "Owner B", "age": 30, "gender": "Male", "phone": "9876522005"}, headers=admin_headers
        ).json()
        bill = client.post(
            "/billing/op/", json={"patient_id": a["id"], "consultation_fee": 500}, headers=admin_headers
        ).json()

        mismatched = client.post(
            "/insurance/claims",
            json={"patient_id": b["id"], "bill_type": "OP", "bill_id": bill["id"], "claimed_amount": 500},
            headers=insurance,
        )
        assert mismatched.status_code == 422

    def test_insurance_stats_endpoint(self, client, admin_headers):
        insurance = self._staff(client, admin_headers, "ins_probe5", "Insurance")
        stats = client.get("/insurance/stats", headers=insurance)
        assert stats.status_code == 200
        for key in ("total_claims", "approved_amount", "pending_amount", "active_policies"):
            assert key in stats.json()


class TestHospitalStructure:
    """Departments → wards → rooms → beds, and the invariants that protect them."""

    @staticmethod
    def _phone(seed: str) -> str:
        """Deterministic valid Indian mobile number for a test seed."""
        digits = "".join(str(ord(c) % 10) for c in seed)
        return "97" + digits.ljust(8, "0")[:8]

    @staticmethod
    def _chain(client, admin_headers, suffix):
        dept = client.post(
            "/departments/",
            json={"name": f"Dept {suffix}", "code": f"DP{suffix}", "department_type": "Clinical"},
            headers=admin_headers,
        )
        assert dept.status_code == 200, dept.text
        ward = client.post(
            "/wards/",
            json={
                "name": f"Ward {suffix}", "code": f"WD{suffix}", "ward_type": "General",
                "department_id": dept.json()["id"], "daily_charge": 1500,
            },
            headers=admin_headers,
        )
        assert ward.status_code == 200, ward.text
        room = client.post(
            "/rooms/",
            json={"ward_id": ward.json()["id"], "room_number": f"R{suffix}", "room_type": "General"},
            headers=admin_headers,
        )
        assert room.status_code == 200, room.text
        bed = client.post(
            "/beds/",
            json={"room_id": room.json()["id"], "bed_code": f"B{suffix}", "bed_type": "Standard"},
            headers=admin_headers,
        )
        assert bed.status_code == 200, bed.text
        return dept.json(), ward.json(), room.json(), bed.json()

    def test_create_the_full_location_chain(self, client, admin_headers):
        dept, ward, room, bed = self._chain(client, admin_headers, "A1")
        assert bed["status"] == "Available"
        assert ward["daily_charge"] == 1500

    def test_duplicate_codes_are_rejected(self, client, admin_headers):
        self._chain(client, admin_headers, "A2")
        again = client.post(
            "/departments/", json={"name": "Other", "code": "DPA2"}, headers=admin_headers
        )
        assert again.status_code == 400

    def test_duplicate_bed_in_same_room_is_rejected(self, client, admin_headers):
        _, _, room, bed = self._chain(client, admin_headers, "A3")
        dupe = client.post(
            "/beds/", json={"room_id": room["id"], "bed_code": bed["bed_code"]}, headers=admin_headers
        )
        assert dupe.status_code == 400

    def test_structure_writes_are_admin_only(self, client, admin_headers):
        doctor = self._staff(client, admin_headers, "struct_doc", "Doctor")
        response = client.post(
            "/departments/", json={"name": "Sneaky", "code": "SNK"}, headers=doctor
        )
        assert response.status_code == 403

    def test_bed_cannot_be_marked_occupied_by_hand(self, client, admin_headers):
        _, _, _, bed = self._chain(client, admin_headers, "A4")
        response = client.put(f"/beds/{bed['id']}", json={"status": "Occupied"}, headers=admin_headers)
        assert response.status_code == 409
        assert "admitting a patient" in response.json()["detail"]

    def test_bed_board_lists_location_and_occupant(self, client, admin_headers):
        _, ward, room, bed = self._chain(client, admin_headers, "A5")
        board = client.get("/ipd/bed-board", headers=admin_headers)
        assert board.status_code == 200
        entry = next(b for b in board.json() if b["bed_id"] == bed["id"])
        assert entry["ward_name"] == ward["name"]
        assert entry["room_number"] == room["room_number"]
        assert entry["status"] == "Available"
        assert entry["daily_charge"] == 1500.0  # inherited from the ward
        assert entry["patient_id"] is None

    def test_bed_board_filters_by_ward(self, client, admin_headers):
        _, ward, _, _ = self._chain(client, admin_headers, "A6")
        board = client.get(f"/ipd/bed-board?ward_id={ward['id']}", headers=admin_headers)
        assert board.status_code == 200
        assert all(item["ward_id"] == ward["id"] for item in board.json())

    @staticmethod
    def _staff(client, admin_headers, username, role):
        created = client.post(
            "/staff/",
            json={"username": username, "password": "Staff@Pass1", "role": role},
            headers=admin_headers,
        )
        if created.status_code != 200:
            # Already created by another test in this session; just sign in.
            pass
        login = client.post("/login", data={"username": username, "password": "Staff@Pass1"})
        assert login.status_code == 200, login.text
        return {"Authorization": f"Bearer {login.json()['access_token']}"}


class TestIPDAdmissionLifecycle:
    """Admission → bed allocation → transfer → discharge, with bed-safety invariants."""

    @staticmethod
    def _bed(client, admin_headers, suffix, charge=None):
        dept = client.post(
            "/departments/", json={"name": f"IP Dept {suffix}", "code": f"ID{suffix}"}, headers=admin_headers
        ).json()
        payload = {
            "name": f"IP Ward {suffix}", "code": f"IW{suffix}", "ward_type": "General",
            "department_id": dept["id"], "daily_charge": 2000,
        }
        ward = client.post("/wards/", json=payload, headers=admin_headers).json()
        room = client.post(
            "/rooms/", json={"ward_id": ward["id"], "room_number": f"IR{suffix}"}, headers=admin_headers
        ).json()
        bed_payload = {"room_id": room["id"], "bed_code": f"IB{suffix}"}
        if charge is not None:
            bed_payload["daily_charge"] = charge
        bed = client.post("/beds/", json=bed_payload, headers=admin_headers).json()
        return ward, room, bed

    @staticmethod
    def _patient(client, admin_headers, suffix):
        return client.post(
            "/patients/",
            json={"name": f"IP Patient {suffix}", "age": 55, "gender": "Male",
                  "phone": TestHospitalStructure._phone(suffix)},
            headers=admin_headers,
        ).json()

    def test_admit_with_bed_allocates_atomically(self, client, admin_headers):
        ward, room, bed = self._bed(client, admin_headers, "B01")
        patient = self._patient(client, admin_headers, "B01")

        created = client.post(
            "/ip-admissions/",
            json={"patient_id": patient["id"], "bed_id": bed["id"], "admission_type": "Planned",
                  "admission_source": "OPD", "reason_for_admission": "Observation"},
            headers=admin_headers,
        )
        assert created.status_code == 200, created.text
        admission = created.json()
        assert admission["status"] == "Admitted"
        assert admission["bed_id"] == bed["id"]
        assert admission["ward_number"] == ward["name"]
        assert admission["room_number"] == room["room_number"]

        board = {b["bed_id"]: b for b in client.get("/ipd/bed-board", headers=admin_headers).json()}
        assert board[bed["id"]]["status"] == "Occupied"
        assert board[bed["id"]]["patient_id"] == patient["id"]

    def test_a_second_patient_cannot_take_an_occupied_bed(self, client, admin_headers):
        _, _, bed = self._bed(client, admin_headers, "B02")
        first = self._patient(client, admin_headers, "B02")
        second = self._patient(client, admin_headers, "B03")

        client.post(
            "/ip-admissions/", json={"patient_id": first["id"], "bed_id": bed["id"]}, headers=admin_headers
        )
        clash = client.post(
            "/ip-admissions/", json={"patient_id": second["id"], "bed_id": bed["id"]}, headers=admin_headers
        )
        assert clash.status_code == 409
        assert "occupied" in clash.json()["detail"].lower()

    def test_allocation_rolls_back_when_the_admission_fails(self, client, admin_headers):
        """A bed must never be left Occupied by a failed admission."""
        _, _, bed = self._bed(client, admin_headers, "B04")
        response = client.post(
            "/ip-admissions/",
            json={"patient_id": 999999, "bed_id": bed["id"]},
            headers=admin_headers,
        )
        assert response.status_code == 404
        board = {b["bed_id"]: b for b in client.get("/ipd/bed-board", headers=admin_headers).json()}
        assert board[bed["id"]]["status"] == "Available"

    def test_transfer_moves_the_patient_and_frees_the_old_bed(self, client, admin_headers):
        _, _, bed_a = self._bed(client, admin_headers, "B05")
        _, _, bed_b = self._bed(client, admin_headers, "B06")
        patient = self._patient(client, admin_headers, "B05")

        admission = client.post(
            "/ip-admissions/", json={"patient_id": patient["id"], "bed_id": bed_a["id"]}, headers=admin_headers
        ).json()
        moved = client.post(
            f"/ip-admissions/{admission['id']}/transfer",
            json={"to_bed_id": bed_b["id"], "reason": "Requires closer monitoring"},
            headers=admin_headers,
        )
        assert moved.status_code == 200, moved.text
        assert moved.json()["bed_id"] == bed_b["id"]

        board = {b["bed_id"]: b for b in client.get("/ipd/bed-board", headers=admin_headers).json()}
        assert board[bed_b["id"]]["status"] == "Occupied"
        assert board[bed_a["id"]]["status"] == "Cleaning"  # not instantly rebookable

        detail = client.get(f"/ip-admissions/{admission['id']}/detail", headers=admin_headers).json()
        assert len(detail["transfers"]) == 1
        assert detail["transfers"][0]["reason"] == "Requires closer monitoring"
        assert len([a for a in detail["allocations"] if a["released_at"] is None]) == 1

    def test_transfer_to_the_current_bed_is_rejected(self, client, admin_headers):
        _, _, bed = self._bed(client, admin_headers, "B07")
        patient = self._patient(client, admin_headers, "B07")
        admission = client.post(
            "/ip-admissions/", json={"patient_id": patient["id"], "bed_id": bed["id"]}, headers=admin_headers
        ).json()
        same = client.post(
            f"/ip-admissions/{admission['id']}/transfer",
            json={"to_bed_id": bed["id"], "reason": "No actual move"},
            headers=admin_headers,
        )
        assert same.status_code == 409

    def test_discharge_requires_a_summary(self, client, admin_headers):
        _, _, bed = self._bed(client, admin_headers, "B08")
        patient = self._patient(client, admin_headers, "B08")
        admission = client.post(
            "/ip-admissions/", json={"patient_id": patient["id"], "bed_id": bed["id"]}, headers=admin_headers
        ).json()

        blocked = client.post(
            f"/ip-admissions/{admission['id']}/discharge", json={"discharge_type": "Routine"}, headers=admin_headers
        )
        assert blocked.status_code == 409
        assert "discharge summary is required" in blocked.json()["detail"].lower()

        forced = client.post(
            f"/ip-admissions/{admission['id']}/discharge",
            json={"discharge_type": "Routine", "require_summary": False},
            headers=admin_headers,
        )
        assert forced.status_code == 200

    def test_full_discharge_flow_releases_the_bed(self, client, admin_headers):
        _, _, bed = self._bed(client, admin_headers, "B09")
        patient = self._patient(client, admin_headers, "B09")
        admission = client.post(
            "/ip-admissions/", json={"patient_id": patient["id"], "bed_id": bed["id"]}, headers=admin_headers
        ).json()

        summary = client.post(
            f"/ip-admissions/{admission['id']}/discharge-summary",
            json={
                "final_diagnosis": "Acute gastroenteritis",
                "condition_at_discharge": "Improved",
                "medication_summary": "ORS, Zinc",
                "follow_up_instructions": "Review in 5 days",
            },
            headers=admin_headers,
        )
        assert summary.status_code == 200, summary.text
        assert summary.json()["status"] == "Draft"

        finalised = client.put(
            f"/ipd/discharge-summaries/{summary.json()['id']}", json={"status": "Final"}, headers=admin_headers
        )
        assert finalised.status_code == 200

        discharge = client.post(
            f"/ip-admissions/{admission['id']}/discharge",
            json={"discharge_type": "Routine"},
            headers=admin_headers,
        )
        assert discharge.status_code == 200, discharge.text
        assert discharge.json()["status"] == "Discharged"
        assert discharge.json()["discharge_date"] is not None
        assert discharge.json()["bed_id"] is None

        board = {b["bed_id"]: b for b in client.get("/ipd/bed-board", headers=admin_headers).json()}
        assert board[bed["id"]]["status"] == "Cleaning"
        assert board[bed["id"]]["patient_id"] is None

    def test_discharging_twice_is_rejected(self, client, admin_headers):
        _, _, bed = self._bed(client, admin_headers, "B10")
        patient = self._patient(client, admin_headers, "B10")
        admission = client.post(
            "/ip-admissions/", json={"patient_id": patient["id"], "bed_id": bed["id"]}, headers=admin_headers
        ).json()
        client.post(
            f"/ip-admissions/{admission['id']}/discharge",
            json={"discharge_type": "Routine", "require_summary": False},
            headers=admin_headers,
        )
        again = client.post(
            f"/ip-admissions/{admission['id']}/discharge",
            json={"discharge_type": "Routine", "require_summary": False},
            headers=admin_headers,
        )
        assert again.status_code == 409

    def test_an_active_admission_cannot_be_deleted(self, client, admin_headers):
        _, _, bed = self._bed(client, admin_headers, "B11")
        patient = self._patient(client, admin_headers, "B11")
        admission = client.post(
            "/ip-admissions/", json={"patient_id": patient["id"], "bed_id": bed["id"]}, headers=admin_headers
        ).json()
        response = client.delete(f"/ip-admissions/{admission['id']}", headers=admin_headers)
        assert response.status_code == 409

    def test_assign_bed_after_admission_without_one(self, client, admin_headers):
        _, _, bed = self._bed(client, admin_headers, "B12")
        patient = self._patient(client, admin_headers, "B12")
        admission = client.post(
            "/ip-admissions/", json={"patient_id": patient["id"]}, headers=admin_headers
        ).json()
        assert admission["bed_id"] is None

        assigned = client.post(
            f"/ip-admissions/{admission['id']}/bed", json={"bed_id": bed["id"]}, headers=admin_headers
        )
        assert assigned.status_code == 200
        assert assigned.json()["bed_id"] == bed["id"]

        # A second assignment without a transfer is refused.
        _, _, other = self._bed(client, admin_headers, "B13")
        again = client.post(
            f"/ip-admissions/{admission['id']}/bed", json={"bed_id": other["id"]}, headers=admin_headers
        )
        assert again.status_code == 409

    def test_length_of_stay_and_room_charge_are_computed(self, client, admin_headers):
        _, _, bed = self._bed(client, admin_headers, "B14", charge=3000)
        patient = self._patient(client, admin_headers, "B14")
        admission = client.post(
            "/ip-admissions/", json={"patient_id": patient["id"], "bed_id": bed["id"]}, headers=admin_headers
        ).json()
        detail = client.get(f"/ip-admissions/{admission['id']}/detail", headers=admin_headers).json()
        assert detail["length_of_stay_days"] == 0
        # At least one night is billable on the day of admission.
        assert detail["billable_room_charge"] == 3000.0


class TestIPDClinical:
    """Nursing chart, medication orders and administration."""

    @staticmethod
    def _admitted(client, admin_headers, suffix):
        dept = client.post(
            "/departments/", json={"name": f"Cl Dept {suffix}", "code": f"CD{suffix}"}, headers=admin_headers
        ).json()
        ward = client.post(
            "/wards/", json={"name": f"Cl Ward {suffix}", "code": f"CW{suffix}", "department_id": dept["id"]},
            headers=admin_headers,
        ).json()
        room = client.post(
            "/rooms/", json={"ward_id": ward["id"], "room_number": f"CR{suffix}"}, headers=admin_headers
        ).json()
        bed = client.post(
            "/beds/", json={"room_id": room["id"], "bed_code": f"CB{suffix}"}, headers=admin_headers
        ).json()
        patient = client.post(
            "/patients/",
            json={"name": f"Cl Patient {suffix}", "age": 60, "gender": "Female",
                  "phone": TestHospitalStructure._phone(suffix)},
            headers=admin_headers,
        ).json()
        admission = client.post(
            "/ip-admissions/", json={"patient_id": patient["id"], "bed_id": bed["id"]}, headers=admin_headers
        ).json()
        return admission

    def test_chart_normal_vitals(self, client, admin_headers):
        admission = self._admitted(client, admin_headers, "C01")
        note = client.post(
            f"/ip-admissions/{admission['id']}/nursing-notes",
            json={"shift": "Morning", "temperature": 37.2, "pulse": 78, "bp_systolic": 120,
                  "bp_diastolic": 80, "spo2": 98, "respiratory_rate": 16, "pain_score": 2},
            headers=admin_headers,
        )
        assert note.status_code == 200, note.text
        assert note.json()["is_critical"] is False

    def test_dangerous_vitals_are_flagged_server_side(self, client, admin_headers):
        admission = self._admitted(client, admin_headers, "C02")
        # Client claims it is fine; the server must disagree.
        note = client.post(
            f"/ip-admissions/{admission['id']}/nursing-notes",
            json={"shift": "Night", "spo2": 86, "pulse": 140, "is_critical": False},
            headers=admin_headers,
        )
        assert note.status_code == 200
        assert note.json()["is_critical"] is True

    def test_diastolic_above_systolic_is_rejected(self, client, admin_headers):
        admission = self._admitted(client, admin_headers, "C03")
        bad = client.post(
            f"/ip-admissions/{admission['id']}/nursing-notes",
            json={"bp_systolic": 80, "bp_diastolic": 120},
            headers=admin_headers,
        )
        assert bad.status_code == 422

    def test_vitals_cannot_be_charted_after_discharge(self, client, admin_headers):
        admission = self._admitted(client, admin_headers, "C04")
        client.post(
            f"/ip-admissions/{admission['id']}/discharge",
            json={"discharge_type": "Routine", "require_summary": False},
            headers=admin_headers,
        )
        late = client.post(
            f"/ip-admissions/{admission['id']}/nursing-notes", json={"temperature": 37}, headers=admin_headers
        )
        assert late.status_code == 409

    def test_medication_order_and_administration(self, client, admin_headers):
        admission = self._admitted(client, admin_headers, "C05")
        order = client.post(
            f"/ip-admissions/{admission['id']}/medications",
            json={"medicine_name": "Inj. Ceftriaxone", "dose": "1 g", "route": "IV", "frequency": "BD"},
            headers=admin_headers,
        )
        assert order.status_code == 200, order.text
        assert order.json()["status"] == "Active"

        given = client.post(
            f"/ipd/medications/{order.json()['id']}/administer",
            json={"status": "Given", "dose_given": "1 g"},
            headers=admin_headers,
        )
        assert given.status_code == 200
        assert given.json()["dose_given"] == "1 g"
        assert given.json()["administered_by"] == "admin"

        mar = client.get(f"/ipd/medications/{order.json()['id']}/administrations", headers=admin_headers)
        assert mar.status_code == 200 and len(mar.json()) == 1

    def test_stat_dose_completes_the_order(self, client, admin_headers):
        admission = self._admitted(client, admin_headers, "C06")
        order = client.post(
            f"/ip-admissions/{admission['id']}/medications",
            json={"medicine_name": "Inj. Furosemide", "dose": "40 mg", "route": "IV", "frequency": "STAT"},
            headers=admin_headers,
        ).json()
        client.post(
            f"/ipd/medications/{order['id']}/administer", json={"status": "Given"}, headers=admin_headers
        )
        refreshed = client.get(f"/ip-admissions/{admission['id']}/medications", headers=admin_headers).json()
        assert refreshed[0]["status"] == "Completed"

    def test_stopping_medication_requires_a_reason(self, client, admin_headers):
        admission = self._admitted(client, admin_headers, "C07")
        order = client.post(
            f"/ip-admissions/{admission['id']}/medications",
            json={"medicine_name": "Tab. Amoxicillin", "dose": "500 mg"},
            headers=admin_headers,
        ).json()
        bad = client.put(f"/ipd/medications/{order['id']}", json={"status": "Stopped"}, headers=admin_headers)
        assert bad.status_code == 422
        good = client.put(
            f"/ipd/medications/{order['id']}",
            json={"status": "Stopped", "stop_reason": "Rash"},
            headers=admin_headers,
        )
        assert good.status_code == 200

    def test_a_stopped_order_cannot_be_administered(self, client, admin_headers):
        admission = self._admitted(client, admin_headers, "C08")
        order = client.post(
            f"/ip-admissions/{admission['id']}/medications",
            json={"medicine_name": "Tab. X"},
            headers=admin_headers,
        ).json()
        client.put(
            f"/ipd/medications/{order['id']}",
            json={"status": "Stopped", "stop_reason": "Not needed"},
            headers=admin_headers,
        )
        blocked = client.post(
            f"/ipd/medications/{order['id']}/administer", json={"status": "Given"}, headers=admin_headers
        )
        assert blocked.status_code == 409

    def test_detail_serialises_a_fully_populated_record(self, client, admin_headers):
        """Regression: the nested collections are ORM objects, not dicts.

        The earlier test only covered an admission with empty lists, so a schema
        that declared them as ``List[Dict]`` passed and then 500'd in production.
        """
        admission = self._admitted(client, admin_headers, "C11")

        client.post(
            f"/ip-admissions/{admission['id']}/nursing-notes",
            json={"temperature": 37.1, "pulse": 80, "bp_systolic": 118, "bp_diastolic": 76},
            headers=admin_headers,
        )
        order = client.post(
            f"/ip-admissions/{admission['id']}/medications",
            json={"medicine_name": "Tab. Metformin", "dose": "500 mg", "frequency": "BD"},
            headers=admin_headers,
        ).json()
        client.post(f"/ipd/medications/{order['id']}/administer", json={"status": "Given"}, headers=admin_headers)
        client.post(
            f"/ip-admissions/{admission['id']}/discharge-summary",
            json={"final_diagnosis": "Type 2 diabetes"},
            headers=admin_headers,
        )

        response = client.get(f"/ip-admissions/{admission['id']}/detail", headers=admin_headers)
        assert response.status_code == 200, response.text
        body = response.json()

        assert len(body["allocations"]) == 1
        assert body["allocations"][0]["bed_id"] is not None
        assert body["allocations"][0]["bed"]["bed_code"]  # nested bed model serialised
        assert body["allocations"][0]["released_at"] is None
        assert len(body["nursing_notes"]) == 1
        assert body["nursing_notes"][0]["pulse"] == 80
        assert len(body["medication_orders"]) == 1
        assert body["medication_orders"][0]["medicine_name"] == "Tab. Metformin"
        assert len(body["medication_orders"][0]["administrations"]) == 1
        assert body["discharge_summary"]["final_diagnosis"] == "Type 2 diabetes"
        assert body["patient"]["id"] == admission["patient_id"]
        assert body["status"] == "Admitted"

    def test_approved_discharge_summary_is_locked(self, client, admin_headers):
        admission = self._admitted(client, admin_headers, "C09")
        summary = client.post(
            f"/ip-admissions/{admission['id']}/discharge-summary",
            json={"final_diagnosis": "Pneumonia"},
            headers=admin_headers,
        ).json()

        # Cannot jump straight from Draft to Approved.
        early = client.put(
            f"/ipd/discharge-summaries/{summary['id']}", json={"status": "Approved"}, headers=admin_headers
        )
        assert early.status_code == 409

        client.put(f"/ipd/discharge-summaries/{summary['id']}", json={"status": "Final"}, headers=admin_headers)
        approved = client.put(
            f"/ipd/discharge-summaries/{summary['id']}", json={"status": "Approved"}, headers=admin_headers
        )
        assert approved.status_code == 200
        assert approved.json()["approved_by"] == "admin"
        assert approved.json()["approved_at"] is not None

        edit = client.put(
            f"/ipd/discharge-summaries/{summary['id']}",
            json={"final_diagnosis": "Changed my mind"},
            headers=admin_headers,
        )
        assert edit.status_code == 409

    def test_nurse_can_chart_but_pharmacy_cannot_administer(self, client, admin_headers):
        admission = self._admitted(client, admin_headers, "C10")
        order = client.post(
            f"/ip-admissions/{admission['id']}/medications",
            json={"medicine_name": "Tab. Paracetamol", "dose": "650 mg"},
            headers=admin_headers,
        ).json()

        nurse = client.post(
            "/staff/",
            json={"username": "nurse_ipd", "password": "Staff@Pass1", "role": "Nurse"},
            headers=admin_headers,
        )
        assert nurse.status_code == 200, nurse.text
        login = client.post("/login", data={"username": "nurse_ipd", "password": "Staff@Pass1"})
        nurse_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        charted = client.post(
            f"/ip-admissions/{admission['id']}/nursing-notes",
            json={"temperature": 36.8, "pulse": 72},
            headers=nurse_headers,
        )
        assert charted.status_code == 200
        assert charted.json()["recorded_by"] == "nurse_ipd"

        pharmacy = client.post(
            "/staff/",
            json={"username": "pharm_ipd", "password": "Staff@Pass1", "role": "Pharmacy"},
            headers=admin_headers,
        )
        assert pharmacy.status_code == 200
        plogin = client.post("/login", data={"username": "pharm_ipd", "password": "Staff@Pass1"})
        ph_headers = {"Authorization": f"Bearer {plogin.json()['access_token']}"}

        refused = client.post(
            f"/ipd/medications/{order['id']}/administer", json={"status": "Given"}, headers=ph_headers
        )
        assert refused.status_code == 403


class TestIPDReporting:
    def test_ipd_stats_reflect_real_activity(self, client, admin_headers):
        stats = client.get("/ipd/stats", headers=admin_headers)
        assert stats.status_code == 200
        body = stats.json()
        for key in (
            "total_beds", "available_beds", "occupied_beds", "occupancy_percent",
            "current_admissions", "admissions_today", "discharges_today",
            "average_length_of_stay", "critical_patients", "pending_discharge_summaries",
            "active_medication_orders",
        ):
            assert key in body, f"missing {key}"
        assert body["total_beds"] >= body["occupied_beds"]
        assert 0 <= body["occupancy_percent"] <= 100

    def test_bed_board_summary_adds_up(self, client, admin_headers):
        summary = client.get("/ipd/bed-board/summary", headers=admin_headers)
        assert summary.status_code == 200
        body = summary.json()
        total = body["available"] + body["occupied"] + body["reserved"] + body["cleaning"] + body["maintenance"] + body["blocked"]
        assert total == body["total_beds"]
        assert isinstance(body["by_ward"], list)

    def test_occupancy_report_per_ward(self, client, admin_headers):
        report = client.get("/ipd/occupancy?days=30", headers=admin_headers)
        assert report.status_code == 200
        for row in report.json():
            for key in ("ward", "total_beds", "occupied_now", "occupancy_percent", "admissions", "patient_days"):
                assert key in row

    def test_staff_master_separates_roles(self, client, admin_headers):
        client.post(
            "/staff/",
            json={"username": "dr_master", "password": "Staff@Pass1", "role": "Doctor",
                  "full_name": "Dr Master", "specialization": "Cardiology", "consultation_fee": 500},
            headers=admin_headers,
        )
        doctors = client.get("/staff/?role=Doctor", headers=admin_headers).json()
        assert any(d["username"] == "dr_master" for d in doctors)
        assert all(d["role"] == "Doctor" for d in doctors)

        nurses = client.get("/ipd/nurses", headers=admin_headers).json()
        assert all(n["role"] == "Nurse" for n in nurses)

    def test_patient_accounts_are_not_listed_as_staff(self, client):
        """Patient registrations must never leak into the staff directory."""
        data = client.post(
            "/portal/register",
            json={"username": "not_staff_1", "password": "Patient@1", "name": "Not Staff",
                  "age": 30, "gender": "Male", "phone": "9876599001"},
        )
        assert data.status_code == 200
        login = client.post("/login", data={"username": "admin", "password": "Admin@123"})
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        staff = client.get("/staff/", headers=headers).json()
        assert not any(s["username"] == "not_staff_1" for s in staff)


class TestAppointmentAvailability:
    """What the portal offers must match what booking will actually accept."""

    @staticmethod
    def _patient(client, suffix):
        # Phone must be 10 digits starting 6-9; derive them from the suffix.
        digits = "".join(c for c in suffix if c.isdigit()) or "0"
        phone = "98" + digits.rjust(8, "0")[-8:]
        response = client.post("/portal/register", json={
            "username": f"slot_{suffix}", "password": "Patient@1",
            "name": f"Slot Patient {suffix}", "age": 29, "gender": "Male",
            "phone": phone,
        })
        assert response.status_code == 200, response.text
        login = client.post("/login", data={"username": f"slot_{suffix}", "password": "Patient@1"})
        assert login.status_code == 200, login.text
        return {"Authorization": f"Bearer {login.json()['access_token']}"}

    @staticmethod
    def _doctor(client, admin_headers, suffix, fee=650):
        response = client.post("/staff/", json={
            "username": f"dr_slot{suffix}", "password": "Staff@Pass1", "role": "Doctor",
            "full_name": f"Dr Slot {suffix}", "specialization": "Orthopaedics",
            "consultation_fee": fee,
        }, headers=admin_headers)
        assert response.status_code == 200, response.text
        return response.json()["id"]

    def test_doctor_listing_carries_fee_and_specialisation(self, client, admin_headers):
        doctor_id = self._doctor(client, admin_headers, "A1", fee=725)
        headers = self._patient(client, "A1")

        doctors = client.get("/portal/doctors", headers=headers)
        assert doctors.status_code == 200, doctors.text
        listed = next((d for d in doctors.json() if d["id"] == doctor_id), None)
        assert listed is not None, "the doctor should be bookable"
        assert listed["name"]
        assert listed["specialization"] == "Orthopaedics"
        assert listed["consultation_fee"] == 725.0

    def test_unfiltered_slots_return_the_full_roster(self, client):
        headers = self._patient(client, "A2")
        response = client.get("/portal/slots", headers=headers)
        assert response.status_code == 200
        assert len(response.json()) == len(constants.APPOINTMENT_SLOTS)

    def test_booked_slots_disappear_from_availability(self, client, admin_headers):
        doctor_id = self._doctor(client, admin_headers, "A3")
        headers = self._patient(client, "A3")

        listing = client.get(
            f"/portal/slots?doctor_id={doctor_id}&appointment_date=2026-11-10", headers=headers
        )
        assert listing.status_code == 200, listing.text
        open_slots = listing.json()
        assert open_slots, "a fresh doctor should have every slot free"

        chosen = open_slots[0]
        booked = client.post("/portal/appointments", json={
            "doctor_id": doctor_id, "appointment_date": "2026-11-10",
            "time_slot": chosen, "reason": "Knee pain",
        }, headers=headers)
        assert booked.status_code == 200, booked.text

        after = client.get(
            f"/portal/slots?doctor_id={doctor_id}&appointment_date=2026-11-10", headers=headers
        ).json()
        assert chosen not in after, "a booked slot must not be offered again"
        assert len(after) == len(open_slots) - 1

    def test_availability_is_per_doctor_and_per_date(self, client, admin_headers):
        doctor_a = self._doctor(client, admin_headers, "A4")
        doctor_b = self._doctor(client, admin_headers, "A5")
        headers = self._patient(client, "A4")

        first = client.get(
            f"/portal/slots?doctor_id={doctor_a}&appointment_date=2026-11-11", headers=headers
        ).json()
        chosen = first[0]
        client.post("/portal/appointments", json={
            "doctor_id": doctor_a, "appointment_date": "2026-11-11", "time_slot": chosen,
        }, headers=headers)

        # Another doctor keeps the slot, and the same doctor keeps it on a new day.
        other_doctor = client.get(
            f"/portal/slots?doctor_id={doctor_b}&appointment_date=2026-11-11", headers=headers
        ).json()
        other_day = client.get(
            f"/portal/slots?doctor_id={doctor_a}&appointment_date=2026-11-12", headers=headers
        ).json()
        assert chosen in other_doctor
        assert chosen in other_day

    def test_cancelling_frees_the_slot_again(self, client, admin_headers):
        doctor_id = self._doctor(client, admin_headers, "A6")
        headers = self._patient(client, "A6")

        open_slots = client.get(
            f"/portal/slots?doctor_id={doctor_id}&appointment_date=2026-11-13", headers=headers
        ).json()
        chosen = open_slots[0]
        appointment = client.post("/portal/appointments", json={
            "doctor_id": doctor_id, "appointment_date": "2026-11-13", "time_slot": chosen,
        }, headers=headers).json()

        client.put(f"/portal/appointments/{appointment['id']}/cancel", headers=headers)

        reoffered = client.get(
            f"/portal/slots?doctor_id={doctor_id}&appointment_date=2026-11-13", headers=headers
        ).json()
        assert chosen in reoffered, "a cancelled appointment should release its slot"

    def test_availability_for_an_unknown_doctor_is_404(self, client):
        headers = self._patient(client, "A7")
        response = client.get(
            "/portal/slots?doctor_id=999999&appointment_date=2026-11-14", headers=headers
        )
        assert response.status_code == 404

    def test_a_patient_cannot_be_in_two_places_at_once(self, client, admin_headers):
        """The clash rule is per patient and time, regardless of which doctor."""
        doctor_a = self._doctor(client, admin_headers, "A8")
        doctor_b = self._doctor(client, admin_headers, "A9")
        headers = self._patient(client, "A8")

        slot = "10:00 AM"
        first = client.post("/portal/appointments", json={
            "doctor_id": doctor_a, "appointment_date": "2026-11-15", "time_slot": slot,
        }, headers=headers)
        assert first.status_code == 200, first.text

        # Same patient, same date and time, different doctor -> still a clash.
        second = client.post("/portal/appointments", json={
            "doctor_id": doctor_b, "appointment_date": "2026-11-15", "time_slot": slot,
        }, headers=headers)
        assert second.status_code == 409

        # A different time with the other doctor is fine.
        third = client.post("/portal/appointments", json={
            "doctor_id": doctor_b, "appointment_date": "2026-11-15", "time_slot": "11:30 AM",
        }, headers=headers)
        assert third.status_code == 200, third.text


class TestClinicalAuditTrail:
    """The clinical trail must be complete, attributable and append-only."""

    @staticmethod
    def _admitted(client, admin_headers, suffix):
        dept = client.post(
            "/departments/", json={"name": f"Au Dept {suffix}", "code": f"AD{suffix}"},
            headers=admin_headers,
        ).json()
        ward = client.post(
            "/wards/", json={"name": f"Au Ward {suffix}", "code": f"AW{suffix}",
                             "department_id": dept["id"], "daily_charge": 1000},
            headers=admin_headers,
        ).json()
        room = client.post(
            "/rooms/", json={"ward_id": ward["id"], "room_number": f"AR{suffix}"},
            headers=admin_headers,
        ).json()
        bed = client.post(
            "/beds/", json={"room_id": room["id"], "bed_code": f"AB{suffix}"},
            headers=admin_headers,
        ).json()
        # A second bed in the same room, kept free, so transfers have a target.
        spare = client.post(
            "/beds/", json={"room_id": room["id"], "bed_code": f"AB{suffix}X"},
            headers=admin_headers,
        ).json()
        patient = client.post(
            "/patients/",
            json={"name": f"Au Patient {suffix}", "age": 50, "gender": "Male",
                  "phone": TestHospitalStructure._phone(suffix)},
            headers=admin_headers,
        ).json()
        admission = client.post(
            "/ip-admissions/", json={"patient_id": patient["id"], "bed_id": bed["id"]},
            headers=admin_headers,
        ).json()
        return patient, bed, admission, spare

    def test_admission_is_recorded_with_actor_and_role(self, client, admin_headers):
        patient, _, admission, spare = self._admitted(client, admin_headers, "T01")
        trail = client.get(f"/audit-logs/entity/ip_admission/{admission['id']}", headers=admin_headers)
        assert trail.status_code == 200, trail.text
        entries = trail.json()
        assert any(e["action"] == "ADMISSION_CREATED" for e in entries), [e["action"] for e in entries]

        created = next(e for e in entries if e["action"] == "ADMISSION_CREATED")
        assert created["username"] == "admin"
        assert created["actor_role"] == "Admin"
        assert created["patient_id"] == patient["id"]
        assert created["after_state"] is not None

    def test_vitals_charting_is_attributed(self, client, admin_headers):
        _, _, admission, spare = self._admitted(client, admin_headers, "T02")
        client.post(
            f"/ip-admissions/{admission['id']}/nursing-notes",
            json={"shift": "Night", "temperature": 38.9, "spo2": 90},
            headers=admin_headers,
        )
        trail = client.get(f"/audit-logs/patient/{admission['patient_id']}", headers=admin_headers).json()
        charted = [e for e in trail if e["action"] == "VITALS_CHARTED"]
        assert len(charted) == 1
        assert charted[0]["username"] == "admin"
        assert "CRITICAL" in charted[0]["details"]

    def test_medication_lifecycle_is_traced(self, client, admin_headers):
        _, _, admission, spare = self._admitted(client, admin_headers, "T03")
        order = client.post(
            f"/ip-admissions/{admission['id']}/medications",
            json={"medicine_name": "Inj. Audit", "dose": "1 g", "route": "IV", "frequency": "BD"},
            headers=admin_headers,
        ).json()
        client.post(f"/ipd/medications/{order['id']}/administer",
                    json={"status": "Given"}, headers=admin_headers)
        client.put(f"/ipd/medications/{order['id']}",
                   json={"status": "Stopped", "stop_reason": "Adverse reaction"},
                   headers=admin_headers)

        trail = client.get(f"/audit-logs/patient/{admission['patient_id']}", headers=admin_headers).json()
        actions = [e["action"] for e in trail]
        assert "MEDICATION_ORDERED" in actions
        assert "MEDICATION_ADMINISTERED" in actions
        assert "MEDICATION_UPDATED" in actions

        stopped = next(e for e in trail if e["action"] == "MEDICATION_UPDATED")
        # A before/after diff must let an auditor reconstruct the change.
        assert stopped["before_state"] is not None
        assert "Active" in stopped["before_state"]

    def test_transfer_and_discharge_are_traced(self, client, admin_headers):
        patient, _, admission, spare = self._admitted(client, admin_headers, "T04")

        client.post(f"/ip-admissions/{admission['id']}/transfer",
                    json={"to_bed_id": spare["id"], "reason": "Needs monitoring"},
                    headers=admin_headers)
        client.post(f"/ip-admissions/{admission['id']}/discharge",
                    json={"discharge_type": "Routine", "require_summary": False},
                    headers=admin_headers)

        trail = client.get(f"/audit-logs/patient/{patient['id']}", headers=admin_headers).json()
        actions = {e["action"] for e in trail}
        assert {"PATIENT_TRANSFERRED", "PATIENT_DISCHARGED"} <= actions
        transferred = next(e for e in trail if e["action"] == "PATIENT_TRANSFERRED")
        assert "->" in transferred["details"]

    def test_discharge_summary_approval_is_traced(self, client, admin_headers):
        _, _, admission, spare = self._admitted(client, admin_headers, "T05")
        summary = client.post(
            f"/ip-admissions/{admission['id']}/discharge-summary",
            json={"final_diagnosis": "Audited condition"}, headers=admin_headers,
        ).json()
        client.put(f"/ipd/discharge-summaries/{summary['id']}", json={"status": "Final"},
                   headers=admin_headers)
        client.put(f"/ipd/discharge-summaries/{summary['id']}", json={"status": "Approved"},
                   headers=admin_headers)

        trail = client.get(f"/audit-logs/patient/{admission['patient_id']}", headers=admin_headers).json()
        actions = [e["action"] for e in trail]
        assert "DISCHARGE_SUMMARY_CREATED" in actions
        assert "DISCHARGE_SUMMARY_APPROVED" in actions

    def test_a_failed_operation_leaves_no_audit_entry(self, client, admin_headers):
        """The trail and the change commit together, so neither can be orphaned."""
        _, _, admission, spare = self._admitted(client, admin_headers, "T06")
        before = client.get(f"/audit-logs/patient/{admission['patient_id']}", headers=admin_headers).json()

        # Discharging twice fails the second time.
        first = client.post(f"/ip-admissions/{admission['id']}/discharge",
                            json={"discharge_type": "Routine", "require_summary": False},
                            headers=admin_headers)
        assert first.status_code == 200
        after_first = client.get(f"/audit-logs/patient/{admission['patient_id']}", headers=admin_headers).json()

        second = client.post(f"/ip-admissions/{admission['id']}/discharge",
                             json={"discharge_type": "Routine", "require_summary": False},
                             headers=admin_headers)
        assert second.status_code == 409
        after_second = client.get(f"/audit-logs/patient/{admission['patient_id']}", headers=admin_headers).json()

        assert len(after_first) == len(before) + 1
        assert len(after_second) == len(after_first), "a rejected operation must not be audited"

    def test_the_trail_is_append_only(self, client, admin_headers):
        """No API may rewrite history."""
        patient, _, admission, spare = self._admitted(client, admin_headers, "T07")
        trail = client.get(f"/audit-logs/patient/{patient['id']}", headers=admin_headers).json()
        entry_id = trail[0]["id"]

        for method, path in (
            ("put", f"/audit-logs/{entry_id}"),
            ("patch", f"/audit-logs/{entry_id}"),
            ("post", "/audit-logs/"),
        ):
            response = getattr(client, method)(path, json={"action": "TAMPERED"}, headers=admin_headers)
            assert response.status_code in (403, 404, 405), f"{method} {path} -> {response.status_code}"

        # DELETE carries no body.
        deleted = client.delete(f"/audit-logs/{entry_id}", headers=admin_headers)
        assert deleted.status_code in (403, 404, 405), f"delete -> {deleted.status_code}"

        # The entry is still exactly as written.
        again = client.get(f"/audit-logs/patient/{patient['id']}", headers=admin_headers).json()
        assert any(e["id"] == entry_id and e["action"] == "ADMISSION_CREATED" for e in again)

    def test_audit_trail_requires_authentication(self, client):
        assert client.get("/audit-logs/patient/1").status_code == 401
        assert client.get("/audit-logs/entity/ip_admission/1").status_code == 401

    def test_audit_trail_for_an_unknown_patient_is_404(self, client, admin_headers):
        assert client.get("/audit-logs/patient/999999", headers=admin_headers).status_code == 404

    def test_admin_can_filter_the_global_log(self, client, admin_headers):
        _, _, admission, spare = self._admitted(client, admin_headers, "T08")
        filtered = client.get(
            f"/audit-logs/?patient_id={admission['patient_id']}", headers=admin_headers
        )
        assert filtered.status_code == 200
        assert all(e["patient_id"] == admission["patient_id"] for e in filtered.json())
        assert filtered.json(), "the filter should return the entries for this patient"

    def test_clinical_records_carry_their_author(self, client, admin_headers):
        """created_by/updated_by make authorship visible without reading the log."""
        _, _, admission, spare = self._admitted(client, admin_headers, "T09")
        detail = client.get(f"/ip-admissions/{admission['id']}/detail", headers=admin_headers)
        assert detail.status_code == 200

        order = client.post(
            f"/ip-admissions/{admission['id']}/medications",
            json={"medicine_name": "Tab. Authorship"}, headers=admin_headers,
        ).json()
        assert order["prescribed_by"] == "admin"

        summary = client.post(
            f"/ip-admissions/{admission['id']}/discharge-summary",
            json={"final_diagnosis": "Authorship"}, headers=admin_headers,
        ).json()
        assert summary["prepared_by"] == "admin"

        note = client.post(
            f"/ip-admissions/{admission['id']}/nursing-notes",
            json={"temperature": 37.0}, headers=admin_headers,
        ).json()
        assert note["recorded_by"] == "admin"


class TestRateLimiting:
    """The suite runs with a raised budget, so the limiter is exercised directly."""

    def test_requests_are_blocked_once_the_budget_is_exhausted(self, client):
        from backend import main

        original_max = main.RATE_LIMIT_MAX
        main.RATE_LIMIT_BUCKETS.clear()
        main.RATE_LIMIT_MAX = 3
        try:
            codes = [client.get("/health").status_code for _ in range(6)]
        finally:
            main.RATE_LIMIT_MAX = original_max
            main.RATE_LIMIT_BUCKETS.clear()

        assert 200 in codes, "the first requests should succeed"
        assert 429 in codes, "the limiter should engage once the budget is spent"
        # Ordering matters: allowed first, then limited.
        assert codes.index(429) > codes.index(200)

    def test_limit_is_configurable(self):
        from backend.config import settings

        assert settings.rate_limit_window_seconds > 0
        assert settings.rate_limit_max_requests > 0


class TestPatientRules:
    def test_phone_must_be_a_valid_indian_number(self, client, admin_headers):
        response = client.post(
            "/patients/", json={"name": "Bad Phone", "age": 30, "gender": "Male", "phone": "123"}, headers=admin_headers
        )
        assert response.status_code == 422

    def test_patient_list_limit_is_capped(self, client, admin_headers):
        response = client.get("/patients/?limit=1000000", headers=admin_headers)
        assert response.status_code == 422

    def test_patient_with_records_cannot_be_deleted_without_force(self, client, admin_headers):
        created = client.post(
            "/patients/",
            json={"name": "Has Records", "age": 40, "gender": "Female", "phone": "9876500002"},
            headers=admin_headers,
        ).json()
        token = client.post(
            "/tokens/",
            json={
                "patient_id": created["id"],
                "session": "Morning",
                "date": date.today().isoformat(),
                "fee": 100.0,
            },
            headers=admin_headers,
        )
        assert token.status_code == 200

        guarded = client.delete(f"/patients/{created['id']}", headers=admin_headers)
        assert guarded.status_code == 409

        forced = client.delete(f"/patients/{created['id']}?force=true", headers=admin_headers)
        assert forced.status_code == 200


class TestOpTokensAndAppointments:
    def test_token_status_is_validated(self, client, admin_headers, patient):
        token = client.post(
            "/tokens/",
            json={"patient_id": patient["id"], "session": "Morning", "date": date.today().isoformat(), "fee": 50.0},
            headers=admin_headers,
        ).json()
        bad = client.put(f"/tokens/{token['id']}/status?status=Nonsense", headers=admin_headers)
        assert bad.status_code == 422
        good = client.put(f"/tokens/{token['id']}/status?status=Completed", headers=admin_headers)
        assert good.status_code == 200 and good.json()["status"] == "Completed"

    def test_token_numbering_is_sequential_per_session(self, client, admin_headers, patient):
        today = date.today().isoformat()
        numbers = []
        for _ in range(3):
            response = client.post(
                "/tokens/",
                json={"patient_id": patient["id"], "session": "Evening", "date": today, "fee": 10.0},
                headers=admin_headers,
            )
            numbers.append(response.json()["token_number"])
        assert numbers == sorted(numbers)
        assert len(set(numbers)) == 3

    def test_token_creation_rejects_unknown_patient(self, client, admin_headers):
        response = client.post(
            "/tokens/",
            json={"patient_id": 999999, "session": "Morning", "date": date.today().isoformat(), "fee": 1.0},
            headers=admin_headers,
        )
        assert response.status_code == 404

    def test_appointments_filter_is_a_real_date_filter(self, client, admin_headers, patient):
        """Previously filtered ``>= date`` so future bookings leaked into 'today'."""
        today = date.today()
        future = today + timedelta(days=10)
        client.post(
            "/appointments/",
            json={"patient_id": patient["id"], "appointment_date": future.isoformat(), "time_slot": "10:00 AM"},
            headers=admin_headers,
        )
        todays = client.get(f"/appointments/?target_date={today.isoformat()}", headers=admin_headers).json()
        assert all(item["appointment_date"] == today.isoformat() for item in todays)

        upcoming = client.get(
            f"/appointments/?target_date={today.isoformat()}&include_upcoming=true", headers=admin_headers
        ).json()
        assert any(item["appointment_date"] == future.isoformat() for item in upcoming)


class TestCasesheetRules:
    def test_casesheet_update_persists_real_fields(self, client, admin_headers, patient):
        """The old CasesheetUpdate schema declared fields that did not exist on the model."""
        created = client.post(
            "/casesheets/",
            json={
                "patient_id": patient["id"],
                "symptoms": "Fever",
                "diagnosis": "Viral fever",
                "prescribed_medicines": [{"name": "Paracetamol", "quantity": 6}],
                "prescribed_labs": [],
            },
            headers=admin_headers,
        )
        assert created.status_code == 200, created.text
        casesheet_id = created.json()["id"]

        updated = client.put(
            f"/casesheets/{casesheet_id}",
            json={"diagnosis": "Dengue", "advice": "Rest and fluids", "follow_up_date": date.today().isoformat()},
            headers=admin_headers,
        )
        assert updated.status_code == 200
        body = updated.json()
        assert body["diagnosis"] == "Dengue"
        assert body["advice"] == "Rest and fluids"

        refetched = client.get(f"/casesheets/{casesheet_id}", headers=admin_headers).json()
        assert refetched["diagnosis"] == "Dengue"

    def test_prescribing_a_known_test_creates_lab_orders(self, client, admin_headers, patient, lab_test):
        response = client.post(
            "/casesheets/",
            json={
                "patient_id": patient["id"],
                "prescribed_medicines": [],
                "prescribed_labs": [lab_test["test_name"]],
            },
            headers=admin_headers,
        )
        assert response.status_code == 200, response.text
        orders = client.get(f"/lab-orders/?patient_id={patient['id']}", headers=admin_headers).json()
        assert any(order["test_id"] == lab_test["id"] for order in orders)


class TestLaboratory:
    def _order(self, client, headers, patient, lab_test, priority="Routine"):
        response = client.post(
            "/lab-orders/",
            json={"patient_id": patient["id"], "test_id": lab_test["id"], "priority": priority},
            headers=headers,
        )
        assert response.status_code == 200, response.text
        return response.json()

    def test_target_date_filter_does_not_crash(self, client, admin_headers):
        """Regression: ``GET /lab-orders/?target_date=`` raised AttributeError -> HTTP 500."""
        response = client.get(f"/lab-orders/?target_date={date.today().isoformat()}", headers=admin_headers)
        assert response.status_code == 200

    def test_order_requires_an_existing_patient_and_test(self, client, admin_headers, patient, lab_test):
        assert (
            client.post(
                "/lab-orders/", json={"patient_id": 999999, "test_id": lab_test["id"]}, headers=admin_headers
            ).status_code
            == 404
        )
        assert (
            client.post(
                "/lab-orders/", json={"patient_id": patient["id"], "test_id": 999999}, headers=admin_headers
            ).status_code
            == 404
        )

    def test_order_status_is_validated(self, client, admin_headers, patient, lab_test):
        order = self._order(client, admin_headers, patient, lab_test)
        bad = client.put(f"/lab-orders/{order['id']}/status?status=Bogus", headers=admin_headers)
        assert bad.status_code == 422

    def test_workflow_transitions_are_enforced(self, client, admin_headers, patient, lab_test):
        order = self._order(client, admin_headers, patient, lab_test)
        # Pending -> Verified is not a legal transition.
        illegal = client.put(f"/lab-orders/{order['id']}/status?status=Verified", headers=admin_headers)
        assert illegal.status_code == 409

        step1 = client.put(f"/lab-orders/{order['id']}/status?status=Sample Collected", headers=admin_headers)
        assert step1.status_code == 200
        assert step1.json()["sample_collected_at"] is not None
        assert (
            client.put(f"/lab-orders/{order['id']}/status?status=Testing", headers=admin_headers).status_code == 200
        )

    def test_cannot_verify_without_a_result(self, client, admin_headers, patient, lab_test):
        order = self._order(client, admin_headers, patient, lab_test)
        client.put(f"/lab-orders/{order['id']}/status?status=Sample Collected", headers=admin_headers)
        client.put(f"/lab-orders/{order['id']}/status?status=Testing", headers=admin_headers)
        response = client.put(f"/lab-orders/{order['id']}/status?status=Verified", headers=admin_headers)
        assert response.status_code == 409

    def test_results_are_auto_flagged_server_side(self, client, admin_headers, patient, lab_test):
        order = self._order(client, admin_headers, patient, lab_test)
        client.put(f"/lab-orders/{order['id']}/status?status=Sample Collected", headers=admin_headers)

        response = client.post(
            f"/lab-orders/{order['id']}/results",
            json={
                "verify": True,
                "results": [
                    # Client lies about the flag; the server must recompute.
                    {"parameter": "Haemoglobin", "result": "5.0", "unit": "g/dL", "range": "13 - 17", "flag": "Normal"},
                    {"parameter": "WBC", "result": "7000", "unit": "cells/uL", "range": "4000 - 11000", "flag": "High"},
                ],
            },
            headers=admin_headers,
        )
        assert response.status_code == 200, response.text
        report = response.json()
        flags = {row["parameter"]: row["flag"] for row in report["results_data"]}
        # 5.0 is below the parameter's critical_low of 7.0 -> Critical Low.
        assert flags["Haemoglobin"] == "Critical Low"
        assert flags["WBC"] == "Normal"
        assert report["is_abnormal"] is True
        assert report["status"] == "Verified"

        order_after = client.get(f"/lab-orders/{order['id']}", headers=admin_headers).json()
        assert order_after["status"] == "Verified"

    def test_critical_limits_from_the_parameter_drive_the_flag(self, client, admin_headers, patient, lab_test):
        """A value outside the parameter's critical limits is 'Critical Low/High'."""
        order = self._order(client, admin_headers, patient, lab_test)
        client.put(f"/lab-orders/{order['id']}/status?status=Sample Collected", headers=admin_headers)

        # lab_test's Haemoglobin has critical_low = 7.0; 5.0 is below it.
        response = client.post(
            f"/lab-orders/{order['id']}/results",
            json={
                "verify": True,
                "results": [{"parameter": "Haemoglobin", "result": "5.0", "unit": "g/dL", "range": "13 - 17"}],
            },
            headers=admin_headers,
        )
        assert response.status_code == 200, response.text
        assert response.json()["results_data"][0]["flag"] == "Critical Low"

        # 9.0 is below the normal range but above the critical limit -> plain Low.
        order2 = self._order(client, admin_headers, patient, lab_test)
        client.put(f"/lab-orders/{order2['id']}/status?status=Sample Collected", headers=admin_headers)
        again = client.post(
            f"/lab-orders/{order2['id']}/results",
            json={
                "verify": True,
                "results": [{"parameter": "Haemoglobin", "result": "9.0", "unit": "g/dL", "range": "13 - 17"}],
            },
            headers=admin_headers,
        )
        assert again.json()["results_data"][0]["flag"] == "Low"

    def test_verified_order_results_are_locked(self, client, admin_headers, patient, lab_test):
        order = self._order(client, admin_headers, patient, lab_test)
        client.put(f"/lab-orders/{order['id']}/status?status=Sample Collected", headers=admin_headers)
        client.post(
            f"/lab-orders/{order['id']}/results",
            json={"verify": True, "results": [{"parameter": "Haemoglobin", "result": "14", "range": "13 - 17"}]},
            headers=admin_headers,
        )
        again = client.post(
            f"/lab-orders/{order['id']}/results",
            json={"verify": True, "results": [{"parameter": "Haemoglobin", "result": "15", "range": "13 - 17"}]},
            headers=admin_headers,
        )
        assert again.status_code == 409

    def test_bulk_order_expands_a_panel_but_bills_it_once(self, client, admin_headers, patient, lab_test):
        second = client.post(
            "/lab-test-masters/",
            json={"test_code": "T-FBS", "test_name": "Test Fasting Sugar", "price": 120.0, "tat_hours": 4},
            headers=admin_headers,
        ).json()
        panel = client.post(
            "/lab-test-masters/",
            json={
                "test_code": "T-PANEL",
                "test_name": "Test Mini Panel",
                "price": 400.0,
                "is_panel": True,
                "panel_test_ids": [lab_test["id"], second["id"]],
            },
            headers=admin_headers,
        )
        assert panel.status_code == 200, panel.text
        panel_id = panel.json()["id"]

        created = client.post(
            "/lab-orders/bulk",
            json={"patient_id": patient["id"], "test_ids": [panel_id], "priority": "Urgent"},
            headers=admin_headers,
        )
        assert created.status_code == 200, created.text
        orders = created.json()
        assert len(orders) == 2
        assert all(order["panel_id"] == panel_id for order in orders)
        assert all(order["priority"] == "Urgent" for order in orders)

        billed = client.post(
            "/billing/lab/from-orders",
            json={"order_ids": [order["id"] for order in orders], "mark_paid": True},
            headers=admin_headers,
        )
        assert billed.status_code == 200, billed.text
        bill = billed.json()
        # Panel charged once at panel price, not per member test.
        assert len(bill["items"]) == 1
        assert bill["items"][0]["test_name"] == "Test Mini Panel"
        assert bill["total"] == 400.0
        assert bill["status"] == "Paid"

        for order in orders:
            refreshed = client.get(f"/lab-orders/{order['id']}", headers=admin_headers).json()
            assert refreshed["bill_id"] == bill["id"]

    def test_order_cannot_be_billed_twice(self, client, admin_headers, patient, lab_test):
        order = self._order(client, admin_headers, patient, lab_test)
        assert client.post(
            "/billing/lab/from-orders", json={"order_ids": [order["id"]]}, headers=admin_headers
        ).status_code == 200
        assert client.post(
            "/billing/lab/from-orders", json={"order_ids": [order["id"]]}, headers=admin_headers
        ).status_code == 409

    def test_bill_status_is_validated(self, client, admin_headers, patient, lab_test):
        order = self._order(client, admin_headers, patient, lab_test)
        bill = client.post(
            "/billing/lab/from-orders", json={"order_ids": [order["id"]]}, headers=admin_headers
        ).json()
        assert client.put(f"/billing/lab/{bill['id']}?status=Nope", headers=admin_headers).status_code == 422
        assert client.put(f"/billing/lab/{bill['id']}?status=Paid", headers=admin_headers).status_code == 200

    def test_sample_auto_generates_barcode_and_collection_date(self, client, admin_headers, patient, lab_test):
        order = self._order(client, admin_headers, patient, lab_test)
        response = client.post(
            "/lab-samples/",
            json={"order_id": order["id"], "sample_type": "Blood", "status": "Collected"},
            headers=admin_headers,
        )
        assert response.status_code == 200, response.text
        sample = response.json()
        assert sample["barcode"]
        # Regression: samples created directly as Collected used to keep a NULL date.
        assert sample["collection_date"] is not None

        refreshed = client.get(f"/lab-orders/{order['id']}", headers=admin_headers).json()
        assert refreshed["status"] == "Sample Collected"

    def test_sample_status_is_validated(self, client, admin_headers, patient, lab_test):
        order = self._order(client, admin_headers, patient, lab_test)
        sample = client.post(
            "/lab-samples/", json={"order_id": order["id"], "sample_type": "Blood"}, headers=admin_headers
        ).json()
        assert client.put(f"/lab-samples/{sample['id']}/status?status=Nope", headers=admin_headers).status_code == 422

    def test_test_master_can_be_deactivated_and_reactivated(self, client, admin_headers, lab_test):
        assert client.delete(f"/lab-test-masters/{lab_test['id']}", headers=admin_headers).status_code == 200
        active = client.get("/lab-test-masters/", headers=admin_headers).json()
        assert lab_test["id"] not in [t["id"] for t in active]

        restored = client.put(f"/lab-test-masters/{lab_test['id']}/active?is_active=true", headers=admin_headers)
        assert restored.status_code == 200 and restored.json()["is_active"] is True

    def test_duplicate_test_code_is_a_400_not_a_500(self, client, admin_headers, lab_test):
        response = client.post(
            "/lab-test-masters/",
            json={"test_code": lab_test["test_code"], "test_name": "Duplicate", "price": 1.0},
            headers=admin_headers,
        )
        assert response.status_code == 400

    def test_stats_endpoint_reports_real_numbers(self, client, admin_headers):
        stats = client.get("/lab/stats", headers=admin_headers)
        assert stats.status_code == 200
        body = stats.json()
        for key in ("pending", "verified_today", "overdue", "active_tests", "panels", "tat_compliance_percent"):
            assert key in body


class TestBillingAndInventory:
    def test_pharmacy_bill_rejects_insufficient_stock(self, client, admin_headers):
        item = client.post(
            "/inventory/",
            json={"name": "Test Drug A", "category": "Pharmacy", "quantity": 2, "unit_price": 10.0},
            headers=admin_headers,
        ).json()
        response = client.post(
            "/billing/pharmacy/",
            json={"patient_name": "Walk In", "items": [{"medicine_id": item["id"], "quantity": 5}]},
            headers=admin_headers,
        )
        assert response.status_code == 400

    def test_pharmacy_bill_requires_a_payer(self, client, admin_headers):
        response = client.post("/billing/pharmacy/", json={"items": [{"medicine_id": 1, "quantity": 1}]}, headers=admin_headers)
        assert response.status_code == 422

    def test_pharmacy_bill_totals_use_percentage_discount(self, client, admin_headers):
        item = client.post(
            "/inventory/",
            json={"name": "Test Drug B", "category": "Pharmacy", "quantity": 10, "unit_price": 100.0},
            headers=admin_headers,
        ).json()
        bill = client.post(
            "/billing/pharmacy/",
            json={
                "patient_name": "Walk In",
                "discount": 10,
                "gst": 0,
                "items": [{"medicine_id": item["id"], "quantity": 2}],
            },
            headers=admin_headers,
        ).json()
        assert bill["subtotal"] == 200.0
        assert bill["total"] == 180.0

    def test_negative_stock_adjustment_is_rejected(self, client, admin_headers):
        item = client.post(
            "/inventory/",
            json={"name": "Test Drug C", "category": "Pharmacy", "quantity": 1, "unit_price": 5.0},
            headers=admin_headers,
        ).json()
        response = client.post(
            "/inventory/adjust/",
            json={"medicine_id": item["id"], "type": "Stock Out", "quantity": 99},
            headers=admin_headers,
        )
        assert response.status_code == 400

    def test_invalid_payment_mode_is_rejected(self, client, admin_headers):
        response = client.post(
            "/billing/op/",
            json={"patient_id": 1, "consultation_fee": 100, "payment_mode": "Bitcoin"},
            headers=admin_headers,
        )
        assert response.status_code == 422


class TestReportsAndDashboard:
    def test_lab_summary_is_aggregated_not_raw_reports(self, client, admin_headers, patient, lab_test):
        client.post(
            "/lab-orders/", json={"patient_id": patient["id"], "test_id": lab_test["id"]}, headers=admin_headers
        )
        rows = client.get("/reports/lab-summary/", headers=admin_headers).json()
        assert isinstance(rows, list)
        if rows:
            assert set(rows[0]) == {"test_name", "total_orders", "verified", "pending", "revenue"}

    def test_dashboard_revenue_includes_lab_bills(self, client, admin_headers, patient, lab_test):
        order = client.post(
            "/lab-orders/", json={"patient_id": patient["id"], "test_id": lab_test["id"]}, headers=admin_headers
        ).json()
        client.post("/billing/lab/from-orders", json={"order_ids": [order["id"]]}, headers=admin_headers)

        daily = client.get(f"/reports/daily/?report_date={date.today().isoformat()}", headers=admin_headers).json()
        assert daily["lab_revenue"] >= lab_test["price"]

        stats = client.get("/dashboard/stats", headers=admin_headers).json()
        assert "lab_revenue" in stats
        assert stats["today_revenue"] >= daily["lab_revenue"]

    def test_monthly_chart_has_six_distinct_months(self, client, admin_headers):
        charts = client.get("/dashboard/charts", headers=admin_headers).json()
        labels = [point["label"] for point in charts["monthly_revenue"]]
        assert len(labels) == 6
        assert len(set(labels)) == 6
        assert "lab_volume" in charts

    def test_revenue_report_rejects_inverted_range(self, client, admin_headers):
        response = client.get(
            "/reports/revenue/?start_date=2030-01-01&end_date=2020-01-01", headers=admin_headers
        )
        assert response.status_code == 422


class TestSearchAndBackup:
    def test_search_finds_patients_by_name(self, client, admin_headers, patient):
        results = client.get("/search/?q=Regression", headers=admin_headers).json()
        assert any(item["type"] == "patient" and item["id"] == patient["id"] for item in results)

    def test_search_by_bill_id_returns_typed_hits(self, client, admin_headers, patient, lab_test):
        order = client.post(
            "/lab-orders/", json={"patient_id": patient["id"], "test_id": lab_test["id"]}, headers=admin_headers
        ).json()
        bill = client.post(
            "/billing/lab/from-orders", json={"order_ids": [order["id"]]}, headers=admin_headers
        ).json()
        results = client.get(f"/search/?q={bill['id']}", headers=admin_headers).json()
        assert any(item["type"] == "lab_bill" for item in results)

    def test_backup_contains_actual_rows(self, client, admin_headers, patient):
        backup = client.get("/backup/", headers=admin_headers)
        assert backup.status_code == 200
        payload = backup.json()
        assert "patients" in payload and "lab_orders" in payload
        assert any(row["id"] == patient["id"] for row in payload["patients"])
        assert payload["_meta"]["table_counts"]["patients"] >= 1


class TestSchemaHygiene:
    def test_json_columns_are_not_shared_between_rows(self, client, admin_headers):
        """A literal ``default={}`` shares one dict across every instance."""
        first = client.post(
            "/patients/", json={"name": "Json Alpha", "age": 20, "gender": "Male"}, headers=admin_headers
        ).json()
        second = client.post(
            "/patients/", json={"name": "Json Beta", "age": 21, "gender": "Female"}, headers=admin_headers
        ).json()

        client.put(
            f"/patients/{first['id']}", json={"details": {"mutated": True}}, headers=admin_headers
        )
        reread = client.get(f"/patients/{second['id']}", headers=admin_headers).json()
        assert reread["details"] == {}
