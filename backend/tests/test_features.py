"""Bill settlement, IP final-bill charges, discharge clearance, protected
clinical deletes and FEFO pharmacy batches."""

import uuid
from datetime import date, timedelta


def _uid():
    return uuid.uuid4().hex[:8]


def _phone():
    return "9" + str(uuid.uuid4().int)[:9]


def _patient(client, h):
    response = client.post(
        "/patients/", json={"name": f"Feat {_uid()}", "age": 50, "gender": "Female", "phone": _phone()}, headers=h
    )
    assert response.status_code == 200, response.text
    return response.json()


def _admit(client, h, patient_id):
    response = client.post(
        "/ip-admissions/", json={"patient_id": patient_id, "reason_for_admission": "Observation"}, headers=h
    )
    assert response.status_code == 200, response.text
    return response.json()


def _staff(client, h, role):
    name = f"{role.lower()}_{_uid()}"
    client.post("/users/", json={"username": name, "password": "Staff@Pass1", "role": role}, headers=h)
    login = client.post("/login", data={"username": name, "password": "Staff@Pass1"})
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def _stock(client, h, quantity=0, expiry=None, unit_price=10.0):
    body = {"name": f"Med {_uid()}", "category": "Pharmacy", "quantity": quantity, "unit_price": unit_price}
    if expiry is not None:
        body["expiry_date"] = str(expiry)
    response = client.post("/inventory/", json=body, headers=h)
    assert response.status_code == 200, response.text
    return response.json()


def _receive(client, h, stock_id, batch, expiry, quantity):
    response = client.post(
        f"/inventory/{stock_id}/batches",
        json={"batch_number": batch, "expiry_date": str(expiry) if expiry else None, "quantity": quantity},
        headers=h,
    )
    assert response.status_code == 200, response.text
    return response.json()


def _batches(client, h, stock_id):
    return {b["batch_number"]: b["quantity"] for b in client.get(f"/inventory/{stock_id}/batches", headers=h).json()}


# ---------------------------------------------------------------------------
# Bill settlement
# ---------------------------------------------------------------------------
class TestBillSettlement:
    def test_bill_defaults_to_paid_in_full(self, client, admin_headers):
        patient = _patient(client, admin_headers)
        bill = client.post("/billing/op/", json={"patient_id": patient["id"], "consultation_fee": 300},
                           headers=admin_headers).json()
        assert bill["payment_status"] == "Paid"
        assert bill["amount_paid"] == 300
        assert bill["amount_due"] == 0

    def test_partial_then_full_payment(self, client, admin_headers):
        patient = _patient(client, admin_headers)
        bill = client.post(
            "/billing/op/", json={"patient_id": patient["id"], "consultation_fee": 500, "amount_paid": 200},
            headers=admin_headers,
        ).json()
        assert (bill["payment_status"], bill["amount_due"]) == ("Partial", 300)

        over = client.post(f"/billing/op/{bill['id']}/payments", json={"amount": 301}, headers=admin_headers)
        assert over.status_code == 422

        paid = client.post(f"/billing/op/{bill['id']}/payments", json={"amount": 300, "payment_mode": "UPI"},
                           headers=admin_headers).json()
        assert (paid["payment_status"], paid["amount_due"]) == ("Paid", 0)
        assert [p["amount"] for p in paid["payment_history"]] == [200, 300]

        again = client.post(f"/billing/op/{bill['id']}/payments", json={"amount": 1}, headers=admin_headers)
        assert again.status_code == 409

    def test_amount_paid_cannot_exceed_total(self, client, admin_headers):
        patient = _patient(client, admin_headers)
        response = client.post(
            "/billing/op/", json={"patient_id": patient["id"], "consultation_fee": 100, "amount_paid": 150},
            headers=admin_headers,
        )
        assert response.status_code == 422

    def test_unpaid_bill_shows_in_dashboard_dues(self, client, admin_headers):
        patient = _patient(client, admin_headers)
        before = client.get("/dashboard/stats", headers=admin_headers).json()["outstanding_dues"]
        client.post("/billing/op/", json={"patient_id": patient["id"], "consultation_fee": 700, "amount_paid": 0},
                    headers=admin_headers)
        after = client.get("/dashboard/stats", headers=admin_headers).json()["outstanding_dues"]
        assert round(after - before, 2) == 700

    def test_cancel_removes_revenue_and_frees_the_token(self, client, admin_headers):
        patient = _patient(client, admin_headers)
        token = client.post(
            "/tokens/", json={"patient_id": patient["id"], "session": "Morning", "date": str(date.today()), "fee": 100},
            headers=admin_headers,
        ).json()
        today = f"/reports/daily/?report_date={date.today()}"
        before = client.get(today, headers=admin_headers).json()["op_revenue"]
        bill = client.post(
            "/billing/op/", json={"patient_id": patient["id"], "token_id": token["id"], "consultation_fee": 400},
            headers=admin_headers,
        ).json()
        assert client.get(today, headers=admin_headers).json()["op_revenue"] == before + 400

        assert client.post(f"/billing/op/{bill['id']}/cancel", json={"reason": "x"}, headers=admin_headers).status_code == 422
        cancelled = client.post(f"/billing/op/{bill['id']}/cancel", json={"reason": "Wrong patient"},
                                headers=admin_headers).json()
        assert cancelled["payment_status"] == "Cancelled"
        assert cancelled["amount_due"] == 0
        assert cancelled["payment_history"][-1]["refund_due"] == 400
        assert client.get(today, headers=admin_headers).json()["op_revenue"] == before

        assert client.post(f"/billing/op/{bill['id']}/payments", json={"amount": 1},
                           headers=admin_headers).status_code == 409
        # The token can be billed again.
        rebill = client.post(
            "/billing/op/", json={"patient_id": patient["id"], "token_id": token["id"], "consultation_fee": 400},
            headers=admin_headers,
        )
        assert rebill.status_code == 200, rebill.text

    def test_pharmacy_cannot_settle_op_bills(self, client, admin_headers):
        patient = _patient(client, admin_headers)
        bill = client.post("/billing/op/", json={"patient_id": patient["id"], "consultation_fee": 100, "amount_paid": 0},
                           headers=admin_headers).json()
        pharmacy = _staff(client, admin_headers, "Pharmacy")
        assert client.post(f"/billing/op/{bill['id']}/payments", json={"amount": 100},
                           headers=pharmacy).status_code == 403


# ---------------------------------------------------------------------------
# IP final bill picks up lab and pharmacy charges
# ---------------------------------------------------------------------------
class TestIpFinalBill:
    def test_preview_includes_unbilled_lab_and_ip_credit_pharmacy(self, client, admin_headers, lab_test):
        patient = _patient(client, admin_headers)
        admission = _admit(client, admin_headers, patient["id"])

        order = client.post("/lab-orders/", json={"patient_id": patient["id"], "test_id": lab_test["id"]},
                            headers=admin_headers).json()
        med = _stock(client, admin_headers, quantity=20, unit_price=15)
        credit = client.post(
            "/billing/pharmacy/",
            json={"admission_id": admission["id"], "items": [{"medicine_id": med["id"], "quantity": 2}]},
            headers=admin_headers,
        ).json()
        assert credit["payment_mode"] == "IP Credit"
        assert credit["patient_id"] == patient["id"]

        preview = client.get(f"/ip-admissions/{admission['id']}/bill-preview", headers=admin_headers).json()
        assert preview["lab_order_ids"] == [order["id"]]
        assert preview["lab_charges"] == lab_test["price"]
        assert preview["pharmacy_bill_ids"] == [credit["id"]]
        assert preview["pharmacy_charges"] == 30

        bill = client.post("/billing/ip/", json={
            "patient_id": patient["id"], "admission_id": admission["id"],
            "lab_charges": preview["lab_charges"], "pharmacy_charges": preview["pharmacy_charges"],
            "lab_order_ids": preview["lab_order_ids"], "pharmacy_bill_ids": preview["pharmacy_bill_ids"],
        }, headers=admin_headers)
        assert bill.status_code == 200, bill.text

        # Locked: neither a lab bill nor a second IP bill can charge them again.
        after = client.get(f"/ip-admissions/{admission['id']}/bill-preview", headers=admin_headers).json()
        assert after["lab_order_ids"] == [] and after["pharmacy_bill_ids"] == []
        assert after["existing_ip_bills"] == [bill.json()["id"]]
        assert client.post("/billing/lab/from-orders", json={"order_ids": [order["id"]]},
                           headers=admin_headers).status_code == 409
        twice = client.post("/billing/ip/", json={
            "patient_id": patient["id"], "admission_id": admission["id"], "lab_order_ids": [order["id"]],
        }, headers=admin_headers)
        assert twice.status_code == 409

        # Cancelling the IP bill releases them again.
        client.post(f"/billing/ip/{bill.json()['id']}/cancel", json={"reason": "Re-issue"}, headers=admin_headers)
        released = client.get(f"/ip-admissions/{admission['id']}/bill-preview", headers=admin_headers).json()
        assert released["lab_order_ids"] == [order["id"]]
        assert released["pharmacy_bill_ids"] == [credit["id"]]

    def test_ip_credit_sale_is_not_counter_revenue(self, client, admin_headers):
        patient = _patient(client, admin_headers)
        admission = _admit(client, admin_headers, patient["id"])
        med = _stock(client, admin_headers, quantity=5, unit_price=100)
        today = f"/reports/daily/?report_date={date.today()}"
        before = client.get(today, headers=admin_headers).json()["pharmacy_revenue"]
        client.post("/billing/pharmacy/", json={"admission_id": admission["id"],
                                                "items": [{"medicine_id": med["id"], "quantity": 1}]},
                    headers=admin_headers)
        assert client.get(today, headers=admin_headers).json()["pharmacy_revenue"] == before

    def test_ip_credit_rules(self, client, admin_headers):
        patient, other = _patient(client, admin_headers), _patient(client, admin_headers)
        admission = _admit(client, admin_headers, patient["id"])
        med = _stock(client, admin_headers, quantity=5)
        line = [{"medicine_id": med["id"], "quantity": 1}]

        wrong = client.post("/billing/pharmacy/", json={"admission_id": admission["id"], "patient_id": other["id"],
                                                        "items": line}, headers=admin_headers)
        assert wrong.status_code == 422
        no_admission = client.post("/billing/pharmacy/", json={"patient_id": patient["id"], "payment_mode": "IP Credit",
                                                               "items": line}, headers=admin_headers)
        assert no_admission.status_code == 422

        client.post(f"/ip-admissions/{admission['id']}/discharge",
                    json={"discharge_type": "Routine", "require_summary": False}, headers=admin_headers)
        after_discharge = client.post("/billing/pharmacy/", json={"admission_id": admission["id"], "items": line},
                                      headers=admin_headers)
        assert after_discharge.status_code == 409

    def test_links_need_a_matching_admission(self, client, admin_headers):
        patient, other = _patient(client, admin_headers), _patient(client, admin_headers)
        admission = _admit(client, admin_headers, other["id"])
        mismatch = client.post("/billing/ip/", json={"patient_id": patient["id"], "admission_id": admission["id"]},
                               headers=admin_headers)
        assert mismatch.status_code == 422
        orphan = client.post("/billing/ip/", json={"patient_id": patient["id"], "lab_order_ids": [1]},
                             headers=admin_headers)
        assert orphan.status_code == 422


# ---------------------------------------------------------------------------
# Discharge clearance
# ---------------------------------------------------------------------------
class TestDischargeClearance:
    def _status(self, clearance):
        return {c["key"]: c["status"] for c in clearance["checks"]}

    def test_checklist_reflects_the_stay(self, client, admin_headers, lab_test):
        patient = _patient(client, admin_headers)
        admission = _admit(client, admin_headers, patient["id"])
        client.post("/lab-orders/", json={"patient_id": patient["id"], "test_id": lab_test["id"]}, headers=admin_headers)
        client.post(f"/ip-admissions/{admission['id']}/medications",
                    json={"medicine_name": "Tab. X", "dose": "1", "frequency": "BD"}, headers=admin_headers)

        clearance = client.get(f"/ip-admissions/{admission['id']}/discharge-clearance", headers=admin_headers).json()
        assert clearance["ready"] is False
        status = self._status(clearance)
        assert status == {
            "discharge_summary": "warning", "lab_results": "warning", "unbilled_charges": "warning",
            "final_bill": "warning", "dues": "ok", "medications": "info",
        }

        blocked = client.post(
            f"/ip-admissions/{admission['id']}/discharge",
            json={"discharge_type": "Routine", "require_summary": False, "require_clearance": True},
            headers=admin_headers,
        )
        assert blocked.status_code == 409
        assert "Lab results" in blocked.json()["detail"]

        # Without enforcement the discharge goes through and the open items are audited.
        done = client.post(
            f"/ip-admissions/{admission['id']}/discharge",
            json={"discharge_type": "Routine", "require_summary": False}, headers=admin_headers,
        )
        assert done.status_code == 200, done.text
        trail = client.get(f"/audit-logs/entity/ip_admission/{admission['id']}", headers=admin_headers).json()
        discharge_entry = next(e for e in trail if e["action"] == "PATIENT_DISCHARGED")
        assert "open at discharge" in discharge_entry["details"]

    def test_outstanding_dues_are_a_warning(self, client, admin_headers):
        patient = _patient(client, admin_headers)
        admission = _admit(client, admin_headers, patient["id"])
        client.post("/billing/ip/", json={"patient_id": patient["id"], "admission_id": admission["id"],
                                          "doctor_charges": 1000, "amount_paid": 400}, headers=admin_headers)
        clearance = client.get(f"/ip-admissions/{admission['id']}/discharge-clearance", headers=admin_headers).json()
        assert self._status(clearance)["final_bill"] == "ok"
        assert self._status(clearance)["dues"] == "warning"
        assert clearance["outstanding_amount"] == 600


# ---------------------------------------------------------------------------
# Clinical records cannot be deleted from the front desk
# ---------------------------------------------------------------------------
class TestProtectedDeletes:
    def test_receptionist_cannot_delete_admissions_patients_or_casesheets(self, client, admin_headers):
        desk = _staff(client, admin_headers, "Receptionist")
        patient = _patient(client, admin_headers)
        admission = _admit(client, admin_headers, patient["id"])
        client.post(f"/ip-admissions/{admission['id']}/discharge",
                    json={"discharge_type": "Routine", "require_summary": False}, headers=admin_headers)
        casesheet = client.post("/casesheets/", json={"patient_id": patient["id"], "doctor_name": "Dr"},
                                headers=admin_headers).json()

        assert client.delete(f"/ip-admissions/{admission['id']}", headers=desk).status_code == 403
        assert client.delete(f"/patients/{patient['id']}", headers=desk).status_code == 403
        assert client.delete(f"/casesheets/{casesheet['id']}", headers=desk).status_code == 403

    def test_admission_with_charting_is_retained_even_for_admin(self, client, admin_headers):
        patient = _patient(client, admin_headers)
        admission = _admit(client, admin_headers, patient["id"])
        client.post(f"/ip-admissions/{admission['id']}/nursing-notes",
                    json={"shift": "Morning", "temperature": 37.0}, headers=admin_headers)
        client.post(f"/ip-admissions/{admission['id']}/discharge",
                    json={"discharge_type": "Routine", "require_summary": False}, headers=admin_headers)
        response = client.delete(f"/ip-admissions/{admission['id']}", headers=admin_headers)
        assert response.status_code == 409
        assert "retained" in response.json()["detail"]

    def test_admin_can_delete_an_empty_discharged_admission(self, client, admin_headers):
        patient = _patient(client, admin_headers)
        admission = _admit(client, admin_headers, patient["id"])
        client.post(f"/ip-admissions/{admission['id']}/discharge",
                    json={"discharge_type": "Routine", "require_summary": False}, headers=admin_headers)
        assert client.delete(f"/ip-admissions/{admission['id']}", headers=admin_headers).status_code == 200


# ---------------------------------------------------------------------------
# Pharmacy batches (FEFO)
# ---------------------------------------------------------------------------
class TestPharmacyBatches:
    def test_sale_draws_from_the_earliest_expiring_batch(self, client, admin_headers):
        med = _stock(client, admin_headers)
        soon, later = date.today() + timedelta(days=30), date.today() + timedelta(days=300)
        _receive(client, admin_headers, med["id"], "LATE", later, 10)
        _receive(client, admin_headers, med["id"], "SOON", soon, 4)

        sale = client.post("/billing/pharmacy/", json={"patient_name": "Walk-in",
                                                       "items": [{"medicine_id": med["id"], "quantity": 6}]},
                           headers=admin_headers)
        assert sale.status_code == 200, sale.text
        used = {a["batch_number"]: a["quantity"] for a in sale.json()["items"][0]["batches"]}
        assert used == {"SOON": 4, "LATE": 2}
        assert _batches(client, admin_headers, med["id"]) == {"SOON": 0, "LATE": 8}

    def test_expired_batch_is_skipped_and_reported(self, client, admin_headers):
        med = _stock(client, admin_headers)
        _receive(client, admin_headers, med["id"], "OLD", date.today() - timedelta(days=1), 5)
        _receive(client, admin_headers, med["id"], "NEW", date.today() + timedelta(days=90), 3)

        items = {i["id"]: i for i in client.get("/inventory/", headers=admin_headers).json()}
        assert (items[med["id"]]["quantity"], items[med["id"]]["sellable_quantity"]) == (8, 3)

        too_many = client.post("/billing/pharmacy/", json={"patient_name": "Walk-in",
                                                           "items": [{"medicine_id": med["id"], "quantity": 4}]},
                               headers=admin_headers)
        assert too_many.status_code == 409
        assert "only 3 of 8" in too_many.json()["detail"]

        ok = client.post("/billing/pharmacy/", json={"patient_name": "Walk-in",
                                                     "items": [{"medicine_id": med["id"], "quantity": 3}]},
                         headers=admin_headers)
        assert ok.status_code == 200
        assert _batches(client, admin_headers, med["id"]) == {"OLD": 5, "NEW": 0}

        # Expired stock can be written off with a Stock Out.
        write_off = client.post("/inventory/adjust/", json={"medicine_id": med["id"], "type": "Stock Out",
                                                            "quantity": 5}, headers=admin_headers)
        assert write_off.status_code == 200, write_off.text
        assert write_off.json()["quantity"] == 0

    def test_legacy_unbatched_stock_still_sells(self, client, admin_headers):
        med = _stock(client, admin_headers, quantity=5, expiry=date.today() + timedelta(days=400))
        _receive(client, admin_headers, med["id"], "B1", date.today() + timedelta(days=20), 2)
        sale = client.post("/billing/pharmacy/", json={"patient_name": "Walk-in",
                                                       "items": [{"medicine_id": med["id"], "quantity": 4}]},
                           headers=admin_headers).json()
        used = [(a["batch_number"], a["quantity"]) for a in sale["items"][0]["batches"]]
        assert used == [("B1", 2), (None, 2)]  # the batch expires first, then legacy stock

    def test_grn_stock_in_with_batch_number_opens_a_batch(self, client, admin_headers):
        med = _stock(client, admin_headers)
        expiry = date.today() + timedelta(days=200)
        for _ in range(2):
            response = client.post("/inventory/adjust/", json={
                "medicine_id": med["id"], "type": "Stock In", "quantity": 5,
                "batch_number": "GRN-1", "expiry_date": str(expiry),
            }, headers=admin_headers)
            assert response.status_code == 200, response.text
        assert _batches(client, admin_headers, med["id"]) == {"GRN-1": 10}
        assert response.json()["quantity"] == 10

    def test_total_cannot_drop_below_what_batches_hold(self, client, admin_headers):
        med = _stock(client, admin_headers)
        batch = _receive(client, admin_headers, med["id"], "HOLD", date.today() + timedelta(days=60), 6)
        assert client.post("/inventory/adjust/", json={"medicine_id": med["id"], "type": "Adjustment", "quantity": 4},
                           headers=admin_headers).status_code == 409
        assert client.put(f"/inventory/{med['id']}", json={"quantity": 4}, headers=admin_headers).status_code == 409

        fixed = client.post("/inventory/adjust/", json={"medicine_id": med["id"], "type": "Adjustment",
                                                        "quantity": 4, "batch_id": batch["id"]}, headers=admin_headers)
        assert fixed.status_code == 200
        assert fixed.json()["quantity"] == 4

    def test_expiring_alert_includes_batches(self, client, admin_headers):
        med = _stock(client, admin_headers)
        _receive(client, admin_headers, med["id"], "SHORT", date.today() + timedelta(days=10), 3)
        expiring = client.get("/inventory/alerts/expiring?within_days=30", headers=admin_headers).json()
        assert med["id"] in {i["id"] for i in expiring}
