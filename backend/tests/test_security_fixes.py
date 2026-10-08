"""Regressions for the security review fixes (portal takeover, session revocation,
IPD clinical write access, lockout denial-of-service)."""

import time

import pytest
from fastapi import HTTPException

from backend import auth


def _login(client, username, password):
    response = client.post("/login", data={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return response.json()


def _bearer(token):
    return {"Authorization": f"Bearer {token}"}


def _register(client, username, phone, name="Portal User"):
    response = client.post("/portal/register", json={
        "username": username, "password": "Patient@1", "name": name,
        "age": 30, "gender": "Male", "phone": phone,
    })
    assert response.status_code == 200, response.text
    tokens = response.json()
    me = client.get("/users/me", headers=_bearer(tokens["access_token"])).json()
    return tokens, me


class TestPortalRegistrationDoesNotHijackRecords:
    def test_matching_phone_gets_a_fresh_record_not_the_existing_one(self, client, admin_headers):
        existing = client.post(
            "/patients/",
            json={"name": "Real Patient", "age": 50, "gender": "Female", "phone": "9123400001"},
            headers=admin_headers,
        ).json()

        tokens, me = _register(client, "impostor_1", "9123400001", name="Impostor")
        assert me["patient_id"] != existing["id"]

        profile = client.get("/portal/me", headers=_bearer(tokens["access_token"]))
        assert profile.status_code == 200
        assert "Real Patient" not in profile.text

    def test_admin_can_link_after_verification(self, client, admin_headers):
        existing = client.post(
            "/patients/",
            json={"name": "Verified Patient", "age": 41, "gender": "Male", "phone": "9123400002"},
            headers=admin_headers,
        ).json()
        _, me = _register(client, "verified_1", "9123400002", name="Verified Patient")

        linked = client.put(f"/users/{me['id']}/link-patient?patient_id={existing['id']}", headers=admin_headers)
        assert linked.status_code == 200, linked.text
        assert linked.json()["patient_id"] == existing["id"]

        # A second portal login cannot be linked to the same record.
        _, other = _register(client, "verified_2", "9123400003")
        clash = client.put(f"/users/{other['id']}/link-patient?patient_id={existing['id']}", headers=admin_headers)
        assert clash.status_code == 409

    def test_staff_accounts_cannot_be_linked(self, client, admin_headers):
        admin_id = client.get("/users/me", headers=admin_headers).json()["id"]
        response = client.put(f"/users/{admin_id}/link-patient?patient_id=1", headers=admin_headers)
        assert response.status_code == 400

    def test_patient_cannot_link_themselves(self, client):
        tokens, me = _register(client, "selflink_1", "9123400004")
        response = client.put(
            f"/users/{me['id']}/link-patient?patient_id=1", headers=_bearer(tokens["access_token"])
        )
        assert response.status_code == 403


class TestSessionRevocation:
    @staticmethod
    def _staff(client, admin_headers, username):
        created = client.post(
            "/users/", json={"username": username, "password": "Staff@Pass1", "role": "Doctor"},
            headers=admin_headers,
        )
        assert created.status_code == 200, created.text
        return created.json()["id"]

    def test_logout_revokes_the_refresh_token(self, client):
        tokens = _login(client, "admin", "Admin@123")
        out = client.post(
            "/logout", json={"refresh_token": tokens["refresh_token"]}, headers=_bearer(tokens["access_token"])
        )
        assert out.status_code == 200
        assert client.post("/refresh-token", json={"refresh_token": tokens["refresh_token"]}).status_code == 401

    def test_logout_without_body_still_works(self, client):
        tokens = _login(client, "admin", "Admin@123")
        assert client.post("/logout", headers=_bearer(tokens["access_token"])).status_code == 200

    def test_logout_cannot_revoke_another_users_refresh_token(self, client, admin_headers):
        self._staff(client, admin_headers, "victim_doc")
        victim = _login(client, "victim_doc", "Staff@Pass1")
        attacker = _login(client, "admin", "Admin@123")
        client.post(
            "/logout", json={"refresh_token": victim["refresh_token"]}, headers=_bearer(attacker["access_token"])
        )
        assert client.post("/refresh-token", json={"refresh_token": victim["refresh_token"]}).status_code == 200

    def test_self_password_change_signs_out_old_sessions(self, client, admin_headers):
        self._staff(client, admin_headers, "rotating_doc")
        old = _login(client, "rotating_doc", "Staff@Pass1")
        time.sleep(1.1)  # iat has one-second resolution
        changed = client.post(
            "/users/me/password",
            json={"current_password": "Staff@Pass1", "new_password": "Staff@Pass2"},
            headers=_bearer(old["access_token"]),
        )
        assert changed.status_code == 200, changed.text

        assert client.get("/users/me", headers=_bearer(old["access_token"])).status_code == 401
        assert client.post("/refresh-token", json={"refresh_token": old["refresh_token"]}).status_code == 401
        # The caller's own session continues on the pair the change returned.
        assert client.get("/users/me", headers=_bearer(changed.json()["access_token"])).status_code == 200
        refreshed = client.post("/refresh-token", json={"refresh_token": changed.json()["refresh_token"]})
        assert refreshed.status_code == 200
        fresh = _login(client, "rotating_doc", "Staff@Pass2")
        assert client.get("/users/me", headers=_bearer(fresh["access_token"])).status_code == 200

    def test_admin_reset_signs_out_old_sessions(self, client, admin_headers):
        user_id = self._staff(client, admin_headers, "reset_doc")
        old = _login(client, "reset_doc", "Staff@Pass1")
        time.sleep(1.1)
        reset = client.put(
            f"/users/{user_id}/reset-password", json={"new_password": "Staff@Pass9"}, headers=admin_headers
        )
        assert reset.status_code == 200, reset.text
        assert client.post("/refresh-token", json={"refresh_token": old["refresh_token"]}).status_code == 401


class TestIpdClinicalWriteAccess:
    def test_receptionist_cannot_chart_on_an_admission(self, client, admin_headers):
        for name, role in (("desk_probe", "Receptionist"), ("ward_probe", "Nurse")):
            client.post("/users/", json={"username": name, "password": "Staff@Pass1", "role": role},
                        headers=admin_headers)
        desk = _bearer(_login(client, "desk_probe", "Staff@Pass1")["access_token"])
        ward = _bearer(_login(client, "ward_probe", "Staff@Pass1")["access_token"])

        for path in ("/ip-admissions/999999/medications", "/ip-admissions/999999/nursing-notes",
                     "/ip-admissions/999999/discharge-summary"):
            assert client.post(path, json={}, headers=desk).status_code == 403, path

        # Nurses pass the role gate (the missing admission / empty body fails later).
        assert client.post("/ip-admissions/999999/nursing-notes", json={}, headers=ward).status_code != 403
        # Discharge summaries stay with doctors, matching the /ipd/discharge-summaries rule.
        assert client.post("/ip-admissions/999999/discharge-summary", json={}, headers=ward).status_code == 403


class TestLockoutIsPerClient:
    def test_failed_attempts_from_one_client_do_not_lock_out_another(self):
        auth.FAILED_LOGINS.clear()
        try:
            for _ in range(auth.MAX_FAILED_ATTEMPTS):
                auth.record_failed_login("admin", "10.0.0.66")
            with pytest.raises(HTTPException) as locked:
                auth.check_account_lockout("admin", "10.0.0.66")
            assert locked.value.status_code == 429
            auth.check_account_lockout("admin", "10.0.0.5")  # the real admin is unaffected
        finally:
            auth.FAILED_LOGINS.clear()
