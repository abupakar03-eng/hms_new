"""Regressions for the business-logic review: IPD discharge integrity, room
charges, pharmacy expiry, lab revenue, OP billing and appointment clashes."""

import uuid
from datetime import date, datetime, timedelta

from backend import crud, models
from backend.database import SessionLocal


def _uid():
    return uuid.uuid4().hex[:8]


def _phone():
    digits = str(uuid.uuid4().int)[:9]
    return "9" + digits


def _patient(client, h):
    response = client.post(
        "/patients/", json={"name": f"Logic {_uid()}", "age": 40, "gender": "Male", "phone": _phone()}, headers=h
    )
    assert response.status_code == 200, response.text
    return response.json()


def _bed(client, h, charge):
    tag = _uid()
    dept = client.post("/departments/", json={"name": f"D{tag}", "code": f"D{tag}"}, headers=h).json()
    ward = client.post(
        "/wards/",
        json={"name": f"W{tag}", "code": f"W{tag}", "ward_type": "General", "department_id": dept["id"],
              "daily_charge": charge},
        headers=h,
    ).json()
    room = client.post("/rooms/", json={"ward_id": ward["id"], "room_number": f"R{tag}"}, headers=h).json()
    bed = client.post("/beds/", json={"room_id": room["id"], "bed_code": f"B{tag}", "daily_charge": charge}, headers=h)
    assert bed.status_code == 200, bed.text
    return bed.json()


def _admit(client, h, patient_id, bed_id=None):
    body = {"patient_id": patient_id, "reason_for_admission": "Observation"}
    if bed_id is not None:
        body["bed_id"] = bed_id
    response = client.post("/ip-admissions/", json=body, headers=h)
    assert response.status_code == 200, response.text
    return response.json()


def _discharge(client, h, admission_id):
    response = client.post(
        f"/ip-admissions/{admission_id}/discharge",
        json={"discharge_type": "Routine", "require_summary": False},
        headers=h,
    )
    assert response.status_code == 200, response.text
    return response.json()


class TestAdmissionIntegrity:
    def test_patient_cannot_hold_two_active_admissions(self, client, admin_headers):
        patient = _patient(client, admin_headers)
        first = _admit(client, admin_headers, patient["id"])
        second = client.post(
            "/ip-admissions/", json={"patient_id": patient["id"], "reason_for_admission": "again"}, headers=admin_headers
        )
        assert second.status_code == 409
        assert f"#{first['id']}" in second.json()["detail"]

        # Readmission after discharge is fine.
        _discharge(client, admin_headers, first["id"])
        _admit(client, admin_headers, patient["id"])

    def test_status_endpoint_cannot_discharge_around_the_summary_rule(self, client, admin_headers):
        admission = _admit(client, admin_headers, _patient(client, admin_headers)["id"])
        for status in ("Discharged", "DAMA", "Deceased", "Transferred"):
            response = client.put(f"/ip-admissions/{admission['id']}/status?status={status}", headers=admin_headers)
            assert response.status_code == 409, status
        still = client.get(f"/ip-admissions/{admission['id']}/detail", headers=admin_headers).json()
        assert still["status"] == "Admitted"

    def test_generic_update_cannot_discharge_either(self, client, admin_headers):
        admission = _admit(client, admin_headers, _patient(client, admin_headers)["id"])
        by_status = client.put(f"/ip-admissions/{admission['id']}", json={"status": "Discharged"}, headers=admin_headers)
        by_date = client.put(
            f"/ip-admissions/{admission['id']}", json={"discharge_date": datetime.utcnow().isoformat()},
            headers=admin_headers,
        )
        assert by_status.status_code == 409
        assert by_date.status_code == 409
        # Non-discharge edits still work.
        ok = client.put(
            f"/ip-admissions/{admission['id']}", json={"reason_for_admission": "Revised"}, headers=admin_headers
        )
        assert ok.status_code == 200, ok.text


class TestMedicationAfterDischarge:
    def test_discharge_stops_orders_and_blocks_the_mar(self, client, admin_headers):
        admission = _admit(client, admin_headers, _patient(client, admin_headers)["id"])
        order = client.post(
            f"/ip-admissions/{admission['id']}/medications",
            json={"medicine_name": "Tab. Paracetamol", "dose": "500 mg", "route": "Oral", "frequency": "TDS"},
            headers=admin_headers,
        ).json()
        _discharge(client, admin_headers, admission["id"])

        orders = client.get(f"/ip-admissions/{admission['id']}/medications", headers=admin_headers).json()
        assert orders[0]["status"] == "Stopped"
        assert orders[0]["end_date"] is not None

        give = client.post(f"/ipd/medications/{order['id']}/administer", json={"status": "Given"}, headers=admin_headers)
        assert give.status_code == 409


class TestRoomCharge:
    def test_charge_survives_discharge(self, client, admin_headers):
        bed = _bed(client, admin_headers, 1000)
        admission = _admit(client, admin_headers, _patient(client, admin_headers)["id"], bed["id"])
        before = client.get(f"/ip-admissions/{admission['id']}/detail", headers=admin_headers).json()
        assert before["billable_room_charge"] == 1000.0

        _discharge(client, admin_headers, admission["id"])
        after = client.get(f"/ip-admissions/{admission['id']}/detail", headers=admin_headers).json()
        assert after["billable_room_charge"] == 1000.0

    def test_charge_is_weighted_across_transferred_beds(self, client, admin_headers):
        cheap, dear = _bed(client, admin_headers, 1000), _bed(client, admin_headers, 3000)
        admission = _admit(client, admin_headers, _patient(client, admin_headers)["id"], cheap["id"])
        moved = client.post(
            f"/ip-admissions/{admission['id']}/transfer", json={"to_bed_id": dear["id"], "reason": "ICU"},
            headers=admin_headers,
        )
        assert moved.status_code == 200, moved.text

        # Pin the timeline: 3 days in the cheap bed, then 1 day in the expensive one.
        db = SessionLocal()
        try:
            adm = db.get(models.IPAdmission, admission["id"])
            start = datetime.utcnow() - timedelta(days=4)
            adm.admission_date = start
            first, second = sorted(adm.allocations, key=lambda a: a.id)
            first.allocated_at, first.released_at = start, start + timedelta(days=3)
            second.allocated_at = start + timedelta(days=3)
            db.commit()
            detail = crud.get_ip_admission_detail(db, admission["id"])
        finally:
            db.close()

        assert detail["length_of_stay_days"] == 4
        assert detail["billable_room_charge"] == 3 * 1000.0 + 1 * 3000.0


class TestPharmacyExpiry:
    def test_expired_stock_cannot_be_dispensed(self, client, admin_headers):
        def stock(expiry):
            return client.post(
                "/inventory/",
                json={"name": f"Med {_uid()}", "category": "Pharmacy", "quantity": 10, "unit_price": 5,
                      "expiry_date": str(expiry)},
                headers=admin_headers,
            ).json()

        expired, fresh = stock(date.today() - timedelta(days=1)), stock(date.today() + timedelta(days=60))
        sale = client.post(
            "/billing/pharmacy/",
            json={"patient_name": "Walk-in", "items": [{"medicine_id": expired["id"], "quantity": 1}]},
            headers=admin_headers,
        )
        assert sale.status_code == 409
        assert "expired" in sale.json()["detail"]
        # Nothing was deducted from the expired batch.
        items = {i["id"]: i for i in client.get("/inventory/", headers=admin_headers).json()}
        assert items[expired["id"]]["quantity"] == 10

        ok = client.post(
            "/billing/pharmacy/",
            json={"patient_name": "Walk-in", "items": [{"medicine_id": fresh["id"], "quantity": 1}]},
            headers=admin_headers,
        )
        assert ok.status_code == 200, ok.text


class TestLabBillCancellation:
    def test_cancelled_bill_is_not_revenue(self, client, admin_headers):
        patient = _patient(client, admin_headers)
        before = client.get("/dashboard/stats", headers=admin_headers).json()["lab_revenue"]
        daily_before = client.get(f"/reports/daily/?report_date={date.today()}", headers=admin_headers).json()

        bill = client.post(
            "/billing/lab/", json={"patient_id": patient["id"], "items": [{"test_name": "X", "price": 500}]},
            headers=admin_headers,
        ).json()
        assert client.get("/dashboard/stats", headers=admin_headers).json()["lab_revenue"] == before + 500

        client.put(f"/billing/lab/{bill['id']}?status=Cancelled", headers=admin_headers)
        assert client.get("/dashboard/stats", headers=admin_headers).json()["lab_revenue"] == before
        daily_after = client.get(f"/reports/daily/?report_date={date.today()}", headers=admin_headers).json()
        assert daily_after["lab_revenue"] == daily_before["lab_revenue"]
        assert daily_after["total_bills"] == daily_before["total_bills"]

    def test_cancelling_releases_orders_and_cannot_be_reopened(self, client, admin_headers, patient, lab_test):
        order = client.post(
            "/lab-orders/", json={"patient_id": patient["id"], "test_id": lab_test["id"]}, headers=admin_headers
        ).json()
        bill = client.post("/billing/lab/from-orders", json={"order_ids": [order["id"]]}, headers=admin_headers)
        assert bill.status_code == 200, bill.text

        cancel = client.put(f"/billing/lab/{bill.json()['id']}?status=Cancelled", headers=admin_headers)
        assert cancel.status_code == 200, cancel.text
        reopen = client.put(f"/billing/lab/{bill.json()['id']}?status=Paid", headers=admin_headers)
        assert reopen.status_code == 409

        rebill = client.post("/billing/lab/from-orders", json={"order_ids": [order["id"]]}, headers=admin_headers)
        assert rebill.status_code == 200, rebill.text


class TestOpTokenBilling:
    def _token(self, client, h, patient_id):
        return client.post(
            "/tokens/", json={"patient_id": patient_id, "session": "Morning", "date": str(date.today()), "fee": 100},
            headers=h,
        ).json()

    def test_token_is_billed_once_and_only_for_its_patient(self, client, admin_headers):
        alice, bob = _patient(client, admin_headers), _patient(client, admin_headers)
        token = self._token(client, admin_headers, alice["id"])

        wrong = client.post(
            "/billing/op/", json={"patient_id": bob["id"], "token_id": token["id"], "consultation_fee": 100},
            headers=admin_headers,
        )
        assert wrong.status_code == 422

        first = client.post(
            "/billing/op/", json={"patient_id": alice["id"], "token_id": token["id"], "consultation_fee": 100},
            headers=admin_headers,
        )
        assert first.status_code == 200, first.text
        again = client.post(
            "/billing/op/", json={"patient_id": alice["id"], "token_id": token["id"], "consultation_fee": 100},
            headers=admin_headers,
        )
        assert again.status_code == 409

    def test_casesheet_rejects_another_patients_token(self, client, admin_headers):
        alice, bob = _patient(client, admin_headers), _patient(client, admin_headers)
        token = self._token(client, admin_headers, bob["id"])
        response = client.post(
            "/casesheets/", json={"patient_id": alice["id"], "token_id": token["id"], "doctor_name": "Dr X"},
            headers=admin_headers,
        )
        assert response.status_code == 422
        tokens = client.get(f"/tokens/?target_date={date.today()}", headers=admin_headers).json()
        assert next(t for t in tokens if t["id"] == token["id"])["status"] == "Pending"


class TestStaffAppointmentClashes:
    def test_doctor_and_patient_slots_cannot_be_double_booked(self, client, admin_headers):
        doctor = client.post(
            "/users/", json={"username": f"doc_{_uid()}", "password": "Staff@Pass1", "role": "Doctor"},
            headers=admin_headers,
        ).json()
        alice, bob = _patient(client, admin_headers), _patient(client, admin_headers)
        day = str(date.today() + timedelta(days=5))

        def book(patient_id, slot, doctor_id=doctor["id"]):
            return client.post(
                "/appointments/",
                json={"patient_id": patient_id, "doctor_id": doctor_id, "appointment_date": day, "time_slot": slot},
                headers=admin_headers,
            )

        first = book(alice["id"], "10:00")
        assert first.status_code == 200, first.text
        assert book(bob["id"], "10:00").status_code == 409            # doctor busy
        assert book(alice["id"], "10:00", doctor_id=None).status_code == 409  # patient busy

        second = book(bob["id"], "11:00")
        assert second.status_code == 200, second.text
        moved = client.put(f"/appointments/{second.json()['id']}", json={"time_slot": "10:00"}, headers=admin_headers)
        assert moved.status_code == 409

        # Editing an appointment without moving it does not clash with itself.
        same = client.put(
            f"/appointments/{first.json()['id']}", json={"time_slot": "10:00", "reason": "Follow-up"},
            headers=admin_headers,
        )
        assert same.status_code == 200, same.text

        # A cancelled appointment frees the slot.
        client.put(f"/appointments/{first.json()['id']}", json={"status": "Cancelled"}, headers=admin_headers)
        assert book(bob["id"], "10:00").status_code == 200
