"""Receipt numbering, day-end cash closing and role notifications."""

import re
import uuid
from datetime import date, timedelta

from backend import crud


def _uid():
    return uuid.uuid4().hex[:8]


def _patient(client, h):
    return client.post(
        "/patients/",
        json={"name": f"Ops {_uid()}", "age": 41, "gender": "Female", "phone": "9" + str(uuid.uuid4().int)[:9]},
        headers=h,
    ).json()


def _staff(client, h, role):
    name = f"{role.lower()}_{_uid()}"
    client.post("/users/", json={"username": name, "password": "Staff@Pass1", "role": role}, headers=h)
    token = client.post("/login", data={"username": name, "password": "Staff@Pass1"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


RECEIPT = re.compile(r"^(OP|IP|PH|LB)/\d{4}-\d{2}/\d{6}$")


class TestReceiptNumbers:
    def test_financial_year_runs_april_to_march(self):
        assert crud.financial_year(date(2026, 4, 1)) == "2026-27"
        assert crud.financial_year(date(2027, 3, 31)) == "2026-27"
        assert crud.financial_year(date(2027, 4, 1)) == "2027-28"
        assert crud.financial_year(date(2000, 1, 15)) == "1999-00"

    def test_every_bill_type_gets_a_sequential_number_in_its_own_series(self, client, admin_headers):
        patient = _patient(client, admin_headers)
        a = client.post("/billing/op/", json={"patient_id": patient["id"], "consultation_fee": 100},
                        headers=admin_headers).json()
        b = client.post("/billing/op/", json={"patient_id": patient["id"], "consultation_fee": 100},
                        headers=admin_headers).json()
        lab = client.post("/billing/lab/", json={"patient_id": patient["id"], "items": [{"test_name": "X", "price": 10}]},
                          headers=admin_headers).json()
        ip = client.post("/billing/ip/", json={"patient_id": patient["id"], "doctor_charges": 10},
                         headers=admin_headers).json()

        for bill in (a, b, lab, ip):
            assert RECEIPT.match(bill["receipt_no"]), bill["receipt_no"]
        assert a["receipt_no"].startswith("OP/") and lab["receipt_no"].startswith("LB/") and ip["receipt_no"].startswith("IP/")
        assert int(b["receipt_no"][-6:]) == int(a["receipt_no"][-6:]) + 1

    def test_receipt_numbers_are_unique(self, client, admin_headers):
        patient = _patient(client, admin_headers)
        numbers = [
            client.post("/billing/op/", json={"patient_id": patient["id"], "consultation_fee": 1},
                        headers=admin_headers).json()["receipt_no"]
            for _ in range(5)
        ]
        assert len(set(numbers)) == 5


class TestDayClose:
    def test_summary_counts_collections_by_mode_and_source(self, client, admin_headers):
        today = date.today().isoformat()
        before = client.get(f"/reports/day-close?date={today}", headers=admin_headers).json()

        patient = _patient(client, admin_headers)
        bill = client.post("/billing/op/", json={"patient_id": patient["id"], "consultation_fee": 500,
                                                 "amount_paid": 200, "payment_mode": "Cash"},
                           headers=admin_headers).json()
        client.post(f"/billing/op/{bill['id']}/payments", json={"amount": 300, "payment_mode": "UPI"},
                    headers=admin_headers)

        after = client.get(f"/reports/day-close?date={today}", headers=admin_headers).json()
        assert round(after["by_mode"].get("Cash", 0) - before["by_mode"].get("Cash", 0), 2) == 200
        assert round(after["by_mode"].get("UPI", 0) - before["by_mode"].get("UPI", 0), 2) == 300
        assert round(after["by_source"]["op"] - before["by_source"]["op"], 2) == 500

    def test_cancellation_refunds_reduce_expected_cash(self, client, admin_headers):
        today = date.today().isoformat()
        patient = _patient(client, admin_headers)
        bill = client.post("/billing/op/", json={"patient_id": patient["id"], "consultation_fee": 250},
                           headers=admin_headers).json()
        before = client.get(f"/reports/day-close?date={today}", headers=admin_headers).json()
        client.post(f"/billing/op/{bill['id']}/cancel", json={"reason": "Duplicate bill"}, headers=admin_headers)
        after = client.get(f"/reports/day-close?date={today}", headers=admin_headers).json()
        assert round(after["refunds_due"] - before["refunds_due"], 2) == 250
        assert round(before["expected_cash"] - after["expected_cash"], 2) == 250

    def test_closing_rules(self, client, admin_headers):
        day = (date.today() - timedelta(days=3)).isoformat()
        summary = client.get(f"/reports/day-close?date={day}", headers=admin_headers).json()
        expected = summary["expected_cash"]

        future = client.post("/reports/day-close", json={"date": (date.today() + timedelta(days=1)).isoformat(),
                                                         "counted_cash": 0}, headers=admin_headers)
        assert future.status_code == 422

        unexplained = client.post("/reports/day-close", json={"date": day, "counted_cash": expected + 50},
                                  headers=admin_headers)
        assert unexplained.status_code == 422

        closed = client.post("/reports/day-close", json={"date": day, "counted_cash": expected + 50,
                                                         "notes": "Rs 50 float left in drawer"},
                             headers=admin_headers)
        assert closed.status_code == 200, closed.text
        assert closed.json()["closing"]["variance"] == 50

        again = client.post("/reports/day-close", json={"date": day, "counted_cash": expected}, headers=admin_headers)
        assert again.status_code == 409

    def test_only_billing_and_admin_can_close(self, client, admin_headers):
        day = (date.today() - timedelta(days=5)).isoformat()
        pharmacy = _staff(client, admin_headers, "Pharmacy")
        assert client.post("/reports/day-close", json={"date": day, "counted_cash": 0},
                           headers=pharmacy).status_code == 403
        billing = _staff(client, admin_headers, "Billing")
        expected = client.get(f"/reports/day-close?date={day}", headers=billing).json()["expected_cash"]
        assert client.post("/reports/day-close", json={"date": day, "counted_cash": expected},
                           headers=billing).status_code == 200


class TestNotifications:
    def test_pharmacy_sees_stock_alerts_but_not_billing_ones(self, client, admin_headers):
        item = client.post("/inventory/", json={"name": f"Note {_uid()}", "category": "Pharmacy", "quantity": 1,
                                                "unit_price": 1, "min_stock_level": 10}, headers=admin_headers).json()
        assert item["id"]
        patient = _patient(client, admin_headers)
        client.post("/billing/op/", json={"patient_id": patient["id"], "consultation_fee": 90, "amount_paid": 0},
                    headers=admin_headers)

        pharmacy = {n["key"] for n in client.get("/notifications", headers=_staff(client, admin_headers, "Pharmacy")).json()}
        billing = {n["key"] for n in client.get("/notifications", headers=_staff(client, admin_headers, "Billing")).json()}
        admin = {n["key"] for n in client.get("/notifications", headers=admin_headers).json()}

        assert "low_stock" in pharmacy and "dues" not in pharmacy
        assert "dues" in billing and "low_stock" not in billing
        assert {"low_stock", "dues"} <= admin

    def test_items_carry_a_target_screen_and_are_ordered_by_severity(self, client, admin_headers):
        notes = client.get("/notifications", headers=admin_headers).json()
        assert all(n["tab"] and n["count"] > 0 for n in notes)
        order = {"error": 0, "warning": 1, "info": 2}
        assert [order[n["severity"]] for n in notes] == sorted(order[n["severity"]] for n in notes)
