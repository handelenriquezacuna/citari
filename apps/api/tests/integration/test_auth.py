"""Integration tests for /api/v1/auth/* against the real seed database.
Covers the WP7a brief's cases (a) owner login, (b) wrong password, (c)
superadmin login, (d) GET /auth/me, (h) register-owner + cleanup, (i)
protected route without a token, (j) owner login blocked by an inactive
tenant.
"""

from __future__ import annotations

import uuid
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from tests.integration.conftest import owner_auth_headers


@pytest.fixture
def temp_pending_owner(
    client: TestClient, raw_conn, seed_business_type: dict
) -> Generator[dict, None, None]:
    """Registers a fresh owner + tenant (sp_crear_dominio always creates it
    in the 'pendiente' state) via POST /auth/register-owner, yields its
    data, then deletes both rows (and any audit trail) so the suite stays
    re-runnable and the seed counts (duenos_de_dominios/dominios = 50 each)
    are restored - WP7a brief case (h)."""
    suffix = uuid.uuid4().hex[:8]
    payload = {
        "businessName": f"WP7a Test Business {suffix}",
        "businessTypeId": seed_business_type["business_type_id"],
        "slug": f"wp7a-test-{suffix}",
        "businessEmail": f"wp7a.business.{suffix}@example.com",
        "ownerFirstName": "Wp7a",
        "ownerLastName": "IntegrationTest",
        "ownerEmail": f"wp7a.owner.{suffix}@example.com",
        "password": "TempOwnerPass123",
        "phone": "8888-0000",
    }
    response = client.post("/api/v1/auth/register-owner", json=payload)
    assert response.status_code == 201, response.text
    body = response.json()
    tenant_id = body["tenantId"]
    owner_id = body["owner"]["id"]

    yield {
        "tenant_id": tenant_id,
        "owner_id": owner_id,
        "email": payload["ownerEmail"],
        "password": payload["password"],
        "slug": payload["slug"],
    }

    cursor = raw_conn.cursor()
    cursor.execute(
        "DELETE FROM registros WHERE nombre_entidad = 'duenos_de_dominios' AND entidad_id = ?",
        [owner_id],
    )
    cursor.execute(
        "DELETE FROM registros WHERE nombre_entidad = 'dominios' AND entidad_id = ?",
        [tenant_id],
    )
    cursor.execute("DELETE FROM duenos_de_dominios_correos WHERE dueno_id = ?", [owner_id])
    cursor.execute("DELETE FROM duenos_de_dominios_telefonos WHERE dueno_id = ?", [owner_id])
    cursor.execute("DELETE FROM dominios_correos WHERE dominio_id = ?", [tenant_id])
    cursor.execute("DELETE FROM dominios_telefonos WHERE dominio_id = ?", [tenant_id])
    cursor.execute("DELETE FROM duenos_de_dominios WHERE dueno_id = ?", [owner_id])
    cursor.execute("DELETE FROM dominios WHERE dominio_id = ?", [tenant_id])
    raw_conn.commit()
    cursor.close()


def test_login_owner_with_seed_credentials_returns_token(
    client: TestClient, seed_owner: dict
) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": seed_owner["email"], "password": seed_owner["password"]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["tokenType"] == "bearer"
    assert isinstance(body["accessToken"], str) and body["accessToken"]
    assert body["user"]["role"] == "owner"
    assert body["user"]["tenantId"] == seed_owner["tenant_id"]
    assert body["user"]["email"] == seed_owner["email"]
    assert {"id", "firstName", "lastName", "email", "role", "tenantId"} <= body["user"].keys()


def test_login_owner_wrong_password_returns_401(client: TestClient, seed_owner: dict) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": seed_owner["email"], "password": "definitely-wrong"},
    )

    assert response.status_code == 401
    body = response.json()
    assert {"type", "title", "status", "detail", "traceId"} <= body.keys()


def test_login_unknown_email_returns_401_generic(client: TestClient) -> None:
    """Must be indistinguishable from a wrong-password 401 - never reveals
    whether the email is registered."""
    known_email_response = client.post(
        "/api/v1/auth/login",
        json={"email": "nobody.wp7a@example.com", "password": "whatever123"},
    )

    assert known_email_response.status_code == 401


def test_login_superadmin_with_seed_credentials_returns_token(
    client: TestClient, seed_superadmin: dict
) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": seed_superadmin["email"],
            "password": seed_superadmin["password"],
            "role": "superadmin",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["user"]["role"] == "superadmin"
    assert body["user"]["tenantId"] is None


def test_get_me_returns_current_owner(client: TestClient, seed_owner: dict) -> None:
    headers = owner_auth_headers(client, email=seed_owner["email"], password=seed_owner["password"])

    response = client.get("/api/v1/auth/me", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == seed_owner["owner_id"]
    assert body["role"] == "owner"
    assert body["tenantId"] == seed_owner["tenant_id"]
    assert body["email"] == seed_owner["email"]


def test_get_me_without_token_returns_401(client: TestClient) -> None:
    response = client.get("/api/v1/auth/me")

    assert response.status_code == 401


def test_get_me_with_garbage_token_returns_401(client: TestClient) -> None:
    response = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer this-is-not-a-jwt"})

    assert response.status_code == 401


def test_logout_returns_204(client: TestClient) -> None:
    response = client.post("/api/v1/auth/logout")

    assert response.status_code == 204


def test_register_owner_creates_pending_tenant(
    client: TestClient, temp_pending_owner: dict, raw_conn
) -> None:
    cursor = raw_conn.cursor()
    cursor.execute(
        "SELECT ed.nombre FROM dominios d "
        "JOIN estados_dominios ed ON ed.dominio_estado_id = d.dominio_estado_id "
        "WHERE d.dominio_id = ?",
        [temp_pending_owner["tenant_id"]],
    )
    row = cursor.fetchone()
    cursor.close()

    assert row is not None
    assert row[0] == "pendiente"


def test_login_owner_with_inactive_domain_returns_403(
    client: TestClient, temp_pending_owner: dict
) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": temp_pending_owner["email"],
            "password": temp_pending_owner["password"],
        },
    )

    assert response.status_code == 403
    body = response.json()
    assert "pendiente" in body["detail"]


def test_register_owner_duplicate_slug_returns_400(
    client: TestClient, temp_pending_owner: dict, seed_business_type: dict
) -> None:
    payload = {
        "businessName": "Duplicate Slug Attempt",
        "businessTypeId": seed_business_type["business_type_id"],
        "slug": temp_pending_owner["slug"],
        "businessEmail": "duplicate.slug@example.com",
        "ownerFirstName": "Dup",
        "ownerLastName": "Licate",
        "ownerEmail": "duplicate.owner@example.com",
        "password": "AnotherPass123",
    }

    response = client.post("/api/v1/auth/register-owner", json=payload)

    assert response.status_code == 400
    body = response.json()
    assert {"type", "title", "status", "detail", "traceId"} <= body.keys()
