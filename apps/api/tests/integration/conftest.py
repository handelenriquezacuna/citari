"""Shared fixtures for the WP6 integration suite: real SQL Server (the live
`db` container / `citari` database, seed already loaded - see
docs/sql-signatures.md and scripts/smoke-db.sql for the conventions this
mirrors).

Every test creates its own throwaway data (year-2032 availability blocks, one
fixed test-customer email) and the `cleanup_tracker` fixture removes it again
after each test in FK order (codigos_de_rastreos -> registros ->
reservaciones -> bloques_de_disponibilidad, then the test customer by email),
so the suite is safely re-runnable and always leaves the seed counts
(reservaciones / bloques_de_disponibilidad / codigos_de_rastreos = 50 each)
untouched.

Connection target: SQLSERVER_HOST/PORT/USER/PASSWORD/DB env vars (same ones
app.config.Settings reads). `app.config.Settings` defaults to port 1433 (the
in-container port); running this suite from the HOST machine against the
dockerized instance needs SQLSERVER_PORT=11433 (docker-compose.yml's default
published port, chosen to avoid clashing with a local SQL Server on 1433). If
pyodbc cannot load "ODBC Driver 18 for SQL Server" from the host (no driver
installed on macOS), run this suite inside a container on the compose network
instead (SQLSERVER_HOST=db, SQLSERVER_PORT=1433) - see apps/api/README and
the WP6 report for the exact command used.
"""

from __future__ import annotations

from collections.abc import Generator
from datetime import date, time

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.db import ConnectionFactory
from app.main import app
from app.repositories.availability_repository import AvailabilityRepository

TEST_CUSTOMER_EMAIL = "wp6.integration.tests@example.com"


@pytest.fixture(scope="session")
def settings() -> Settings:
    return Settings()


@pytest.fixture(scope="session")
def db_factory(settings: Settings) -> ConnectionFactory:
    return ConnectionFactory(settings)


@pytest.fixture
def raw_conn(db_factory: ConnectionFactory) -> Generator:
    conn = db_factory.new_connection()
    try:
        yield conn
    finally:
        conn.close()


@pytest.fixture(scope="session")
def client() -> TestClient:
    return TestClient(app)


# WP7a: every seed owner shares the same bcrypt hash of "bowner123", and
# every seed superadmin shares the same bcrypt hash of "Admin123" - see
# database/docs/PASSWORDS.md.
SEED_OWNER_PASSWORD = "bowner123"
SEED_SUPERADMIN_PASSWORD = "Admin123"


@pytest.fixture(scope="session")
def seed_owner(db_factory: ConnectionFactory) -> dict:
    """One active owner (active account + active tenant) from the seed, used
    by the WP7a /auth and /tenant integration tests."""
    conn = db_factory.new_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT TOP 1 o.dueno_id, o.dominio_id, oco.correo, o.nombre
            FROM duenos_de_dominios o
            OUTER APPLY (
                SELECT TOP 1 oc.correo
                FROM duenos_de_dominios_correos oc
                WHERE oc.dueno_id = o.dueno_id
                ORDER BY oc.dueno_correo_id
            ) oco
            WHERE o.activo = 1 AND dbo.fn_dominio_activo(o.dominio_id) = 1
            ORDER BY o.dueno_id
            """
        )
        row = cursor.fetchone()
        if row is None:
            pytest.skip("seed data has no active owner with an active tenant")
        return {
            "owner_id": row.dueno_id,
            "tenant_id": row.dominio_id,
            "email": row.correo,
            "password": SEED_OWNER_PASSWORD,
            "first_name": row.nombre,
        }
    finally:
        conn.close()


@pytest.fixture(scope="session")
def seed_superadmin(db_factory: ConnectionFactory) -> dict:
    """One active superadmin from the seed."""
    conn = db_factory.new_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT TOP 1 s.superadmin_id, sco.correo, s.nombre
            FROM superadmins s
            OUTER APPLY (
                SELECT TOP 1 sc.correo
                FROM superadmins_correos sc
                WHERE sc.superadmin_id = s.superadmin_id
                ORDER BY sc.superadmin_correo_id
            ) sco
            WHERE s.activo = 1
            ORDER BY s.superadmin_id
            """
        )
        row = cursor.fetchone()
        if row is None:
            pytest.skip("seed data has no active superadmin")
        return {
            "superadmin_id": row.superadmin_id,
            "email": row.correo,
            "password": SEED_SUPERADMIN_PASSWORD,
            "first_name": row.nombre,
        }
    finally:
        conn.close()


@pytest.fixture(scope="session")
def seed_business_type(db_factory: ConnectionFactory) -> dict:
    """One active business type from the seed, used by
    POST /auth/register-owner."""
    conn = db_factory.new_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT TOP 1 tipo_negocio_id, nombre FROM tipos_negocios "
            "WHERE activo = 1 ORDER BY tipo_negocio_id"
        )
        row = cursor.fetchone()
        if row is None:
            pytest.skip("seed data has no active business type")
        return {"business_type_id": row.tipo_negocio_id, "name": row.nombre}
    finally:
        conn.close()


def owner_auth_headers(client: TestClient, *, email: str, password: str) -> dict[str, str]:
    """Logs in and returns an `Authorization: Bearer ...` header dict, for
    tests that need an authenticated owner session."""
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password, "role": "owner"},
    )
    assert response.status_code == 200, response.text
    token = response.json()["accessToken"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="session")
def seed_tenant(db_factory: ConnectionFactory) -> dict:
    """Finds one active tenant from the seed (50 dominios, slugs like
    'barberia-el-colocho') with at least one active service and one active
    location - the same lookup pattern scripts/smoke-db.sql uses."""
    conn = db_factory.new_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT TOP 1 d.dominio_id, d.slug
            FROM dominios d
            WHERE dbo.fn_dominio_activo(d.dominio_id) = 1
              AND EXISTS (
                  SELECT 1 FROM servicios s
                  WHERE s.dominio_id = d.dominio_id AND s.activo = 1
              )
              AND EXISTS (
                  SELECT 1 FROM localidades l
                  WHERE l.dominio_id = d.dominio_id AND l.activo = 1
              )
            ORDER BY d.dominio_id
            """
        )
        row = cursor.fetchone()
        if row is None:
            pytest.skip("seed data has no active tenant with an active service+location")
        dominio_id, slug = row.dominio_id, row.slug

        cursor.execute(
            "SELECT TOP 1 servicio_id FROM servicios "
            "WHERE dominio_id = ? AND activo = 1 ORDER BY servicio_id",
            [dominio_id],
        )
        servicio_id = cursor.fetchone().servicio_id

        cursor.execute(
            "SELECT TOP 1 localidad_id FROM localidades "
            "WHERE dominio_id = ? AND activo = 1 ORDER BY localidad_id",
            [dominio_id],
        )
        localidad_id = cursor.fetchone().localidad_id

        cursor.close()
        return {
            "dominio_id": dominio_id,
            "slug": slug,
            "servicio_id": servicio_id,
            "localidad_id": localidad_id,
        }
    finally:
        conn.close()


@pytest.fixture
def cleanup_tracker(raw_conn) -> Generator[dict, None, None]:
    """Tests append the ids they create to `tracker["reserva_ids"]` /
    `tracker["block_ids"]`; everything is deleted here afterwards, in FK
    order, regardless of whether the test passed or failed."""
    tracker: dict[str, list[int]] = {"reserva_ids": [], "block_ids": []}
    yield tracker

    cursor = raw_conn.cursor()
    reserva_ids = tracker["reserva_ids"]
    block_ids = tracker["block_ids"]

    if reserva_ids:
        placeholders = ",".join("?" for _ in reserva_ids)
        cursor.execute(
            f"DELETE FROM codigos_de_rastreos WHERE reserva_id IN ({placeholders})",
            reserva_ids,
        )
        cursor.execute(
            "DELETE FROM registros WHERE nombre_entidad = 'reservaciones' "
            f"AND entidad_id IN ({placeholders})",
            reserva_ids,
        )
        cursor.execute(
            f"DELETE FROM reservaciones WHERE reserva_id IN ({placeholders})",
            reserva_ids,
        )

    if block_ids:
        placeholders = ",".join("?" for _ in block_ids)
        cursor.execute(
            "DELETE FROM bloques_de_disponibilidad "
            f"WHERE bloque_disponibilidad_id IN ({placeholders})",
            block_ids,
        )

    cursor.execute(
        "SELECT cliente_id FROM clientes_correos WHERE correo = ?", [TEST_CUSTOMER_EMAIL]
    )
    test_customer_ids = [row.cliente_id for row in cursor.fetchall()]
    if test_customer_ids:
        placeholders = ",".join("?" for _ in test_customer_ids)
        cursor.execute(
            f"DELETE FROM clientes_correos WHERE cliente_id IN ({placeholders})",
            test_customer_ids,
        )
        cursor.execute(
            f"DELETE FROM clientes_telefonos WHERE cliente_id IN ({placeholders})",
            test_customer_ids,
        )
        cursor.execute(
            f"DELETE FROM clientes WHERE cliente_id IN ({placeholders})",
            test_customer_ids,
        )
    raw_conn.commit()
    cursor.close()


def make_block(
    db_factory: ConnectionFactory,
    seed_tenant: dict,
    *,
    block_date: date,
    start_time: time = time(9, 0),
    end_time: time = time(9, 30),
) -> int:
    """Creates one throwaway availability block via
    sp_crear_bloque_disponibilidad (through the already-fixed
    AvailabilityRepository.create_block) on its own short-lived connection.
    Callers must record the returned id in `cleanup_tracker["block_ids"]`.
    """
    conn = db_factory.new_connection()
    try:
        repo = AvailabilityRepository(conn)
        return repo.create_block(
            tenant_id=seed_tenant["dominio_id"],
            location_id=seed_tenant["localidad_id"],
            block_date=block_date,
            start_time=start_time,
            end_time=end_time,
        )
    finally:
        conn.close()


def booking_payload(*, service_id: int, location_id: int, availability_block_id: int) -> dict:
    return {
        "serviceId": service_id,
        "locationId": location_id,
        "availabilityBlockId": availability_block_id,
        "customer": {
            "firstName": "Ana",
            "lastName": "Rodriguez Solis",
            "email": TEST_CUSTOMER_EMAIL,
            "phone": "8888-0000",
        },
        "customerNotes": "wp6-integration-test",
    }
