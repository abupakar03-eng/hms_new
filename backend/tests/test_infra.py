"""Production infrastructure: integrity-safe deletes, health/readiness,
request correlation, forced password change and backups."""

import contextlib
import sqlite3
import uuid
from datetime import date, timedelta

from backend import backup
from backend.database import engine


def _uid():
    return uuid.uuid4().hex[:8]


def _patient(client, h):
    return client.post(
        "/patients/",
        json={"name": f"Infra {_uid()}", "age": 33, "gender": "Male", "phone": "9" + str(uuid.uuid4().int)[:9]},
        headers=h,
    ).json()


class TestForeignKeysAreEnforced:
    def test_sqlite_runs_with_foreign_keys_and_wal(self):
        if engine.dialect.name != "sqlite":
            return
        with engine.connect() as conn:
            assert conn.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
            assert conn.exec_driver_sql("PRAGMA journal_mode").scalar().lower() == "wal"

    def test_deleting_a_referenced_doctor_is_a_409_not_a_500(self, client, admin_headers):
        doctor = client.post("/users/", json={"username": f"doc_{_uid()}", "password": "Staff@Pass1", "role": "Doctor"},
                             headers=admin_headers).json()
        patient = _patient(client, admin_headers)
        client.post("/appointments/", json={"patient_id": patient["id"], "doctor_id": doctor["id"],
                                            "appointment_date": str(date.today() + timedelta(days=9)),
                                            "time_slot": "09:00"}, headers=admin_headers)
        response = client.delete(f"/users/{doctor['id']}", headers=admin_headers)
        assert response.status_code == 409
        assert "Deactivate" in response.json()["detail"]

    def test_deleting_a_billed_token_is_refused(self, client, admin_headers):
        patient = _patient(client, admin_headers)
        token = client.post("/tokens/", json={"patient_id": patient["id"], "session": "Morning",
                                              "date": str(date.today()), "fee": 100}, headers=admin_headers).json()
        client.post("/billing/op/", json={"patient_id": patient["id"], "token_id": token["id"],
                                          "consultation_fee": 100}, headers=admin_headers)
        assert client.delete(f"/tokens/{token['id']}", headers=admin_headers).status_code == 409

    def test_stock_item_with_history_can_be_deleted_without_orphans(self, client, admin_headers):
        item = client.post("/inventory/", json={"name": f"Del {_uid()}", "category": "Pharmacy", "quantity": 0,
                                                "unit_price": 1}, headers=admin_headers).json()
        client.post("/inventory/adjust/", json={"medicine_id": item["id"], "type": "Stock In", "quantity": 5},
                    headers=admin_headers)
        assert client.delete(f"/inventory/{item['id']}", headers=admin_headers).status_code == 200
        with engine.connect() as conn:
            if engine.dialect.name == "sqlite":
                assert conn.exec_driver_sql("PRAGMA foreign_key_check").fetchall() == []


class TestPatientDeletion:
    def test_clinical_or_billing_history_always_blocks(self, client, admin_headers):
        patient = _patient(client, admin_headers)
        client.post("/billing/op/", json={"patient_id": patient["id"], "consultation_fee": 50}, headers=admin_headers)
        forced = client.delete(f"/patients/{patient['id']}?force=true", headers=admin_headers)
        assert forced.status_code == 409
        assert "OP bills" in forced.json()["detail"]

    def test_mistaken_registration_can_be_removed_with_force(self, client, admin_headers):
        patient = _patient(client, admin_headers)
        client.post("/tokens/", json={"patient_id": patient["id"], "session": "Morning", "date": str(date.today()),
                                      "fee": 0}, headers=admin_headers)
        assert client.delete(f"/patients/{patient['id']}", headers=admin_headers).status_code == 409
        assert client.delete(f"/patients/{patient['id']}?force=true", headers=admin_headers).status_code == 200
        assert client.get(f"/patients/{patient['id']}", headers=admin_headers).status_code == 404


class TestHealthAndCorrelation:
    def test_health_reports_database_readiness(self, client):
        body = client.get("/health").json()
        assert body["status"] == "ok"
        assert body["database"] == "ok"

    def test_every_response_carries_a_request_id(self, client):
        generated = client.get("/health")
        assert len(generated.headers["X-Request-ID"]) >= 8
        echoed = client.get("/health", headers={"X-Request-ID": "trace-abc123"})
        assert echoed.headers["X-Request-ID"] == "trace-abc123"
        hostile = client.get("/health", headers={"X-Request-ID": "<script>"})
        assert hostile.headers["X-Request-ID"] != "<script>"


class TestForcedPasswordChange:
    def test_admin_reset_requires_a_new_password_at_next_login(self, client, admin_headers):
        name = f"temp_{_uid()}"
        user = client.post("/users/", json={"username": name, "password": "Staff@Pass1", "role": "Nurse"},
                           headers=admin_headers).json()
        assert client.post("/login", data={"username": name, "password": "Staff@Pass1"}).json()[
            "must_change_password"] is False

        client.put(f"/users/{user['id']}/reset-password", json={"new_password": "Temp@Pass1"}, headers=admin_headers)
        login = client.post("/login", data={"username": name, "password": "Temp@Pass1"}).json()
        assert login["must_change_password"] is True

        changed = client.post(
            "/users/me/password", json={"current_password": "Temp@Pass1", "new_password": "Mine@Pass1"},
            headers={"Authorization": f"Bearer {login['access_token']}"},
        )
        assert changed.status_code == 200
        me = client.get("/users/me", headers={"Authorization": f"Bearer {changed.json()['access_token']}"}).json()
        assert me["must_change_password"] is False


class TestBackup:
    def test_sqlite_backup_is_consistent_and_pruned(self, tmp_path):
        if engine.dialect.name != "sqlite":
            return
        first = backup.run_backup(tmp_path, keep=2)
        with contextlib.closing(sqlite3.connect(first)) as conn:
            assert conn.execute("SELECT count(*) FROM users").fetchone()[0] >= 1
        for _ in range(3):
            backup.run_backup(tmp_path, keep=2)
        assert len(list(tmp_path.glob("hms-*"))) == 2
