"""Fixtures base para la validacion E2E caja negra de Citari.

Estos tests corren desde el HOST contra la API real del docker compose
(servicio api en localhost:8000). No usan pyodbc: las verificaciones y la
limpieza de base de datos se hacen via docker exec sqlcmd contra el
contenedor db (base citari).

Requisitos: stack arriba (docker compose up -d db db-init api) y .env en la
raiz del repo con SQLSERVER_PASSWORD.

Ejecucion: make test-e2e  (o: apps/api/.venv/bin/pytest tests/e2e -q)
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import httpx
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
API_BASE = os.environ.get("E2E_API_BASE", "http://localhost:8000")
API_V1 = f"{API_BASE}/api/v1"

# Credenciales de seed documentadas en database/docos/PASSWORDS.md
OWNER_PASSWORD = "bowner123"
SUPERADMIN_PASSWORD = "Admin123"


def _sqlserver_password() -> str:
    env_file = REPO_ROOT / ".env"
    for line in env_file.read_text().splitlines():
        if line.startswith("SQLSERVER_PASSWORD="):
            return line.split("=", 1)[1].strip()
    raise RuntimeError("SQLSERVER_PASSWORD no encontrado en .env")


def run_sql(query: str) -> str:
    """Ejecuta una query en la base citari via docker exec sqlcmd.

    Devuelve stdout crudo (formato -W separado por espacios). Para queries de
    un solo valor usar sql_scalar().
    """
    cmd = [
        "docker", "exec", "db",
        "/opt/mssql-tools18/bin/sqlcmd",
        "-S", "localhost", "-U", "sa", "-P", _sqlserver_password(),
        "-C", "-I", "-b", "-d", "citari", "-W", "-h", "-1",
        "-Q", f"SET NOCOUNT ON; {query}",
    ]
    # -b: sin esta bandera, sqlcmd sale con codigo 0 aunque el motor haya
    # rechazado la sentencia (por ejemplo, una violacion de FK) - el error
    # queda solo impreso en stdout/stderr, silencioso para quien solo mira
    # el codigo de salida. Con -b, un error de T-SQL SI produce codigo != 0.
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        raise RuntimeError(f"sqlcmd fallo: {result.stderr or result.stdout}")
    return result.stdout.strip()


def sql_scalar(query: str) -> str:
    out = run_sql(query)
    lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
    return lines[0] if lines else ""


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "e2e: validacion end-to-end contra la API real")


@pytest.fixture(scope="session")
def client() -> httpx.Client:
    with httpx.Client(base_url=API_V1, timeout=30.0) as c:
        yield c


@pytest.fixture(scope="session", autouse=True)
def stack_disponible(client: httpx.Client) -> None:
    """Aborta la sesion completa si el stack no esta arriba."""
    try:
        r = httpx.get(f"{API_BASE}/ready", timeout=10.0)
    except httpx.HTTPError as exc:
        pytest.exit(f"API no disponible en {API_BASE}: {exc}", returncode=3)
    if r.status_code != 200:
        pytest.exit(f"/ready devolvio {r.status_code}; levantar el stack con make up", returncode=3)


def login(client: httpx.Client, email: str, password: str, role: str) -> dict:
    r = client.post("/auth/login", json={"email": email, "password": password, "role": role})
    assert r.status_code == 200, f"login {role} {email} fallo: {r.status_code} {r.text}"
    return r.json()


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="session")
def seed_identities() -> dict:
    """Resuelve dinamicamente identidades del seed (emails post-rebrand)."""
    owner1 = sql_scalar(
        "SELECT TOP 1 correo FROM duenos_de_dominios_correos "
        "WHERE dueno_id = (SELECT dueno_id FROM duenos_de_dominios WHERE dominio_id = 1) "
        "ORDER BY dueno_correo_id"
    )
    owner2 = sql_scalar(
        "SELECT TOP 1 correo FROM duenos_de_dominios_correos "
        "WHERE dueno_id = (SELECT dueno_id FROM duenos_de_dominios WHERE dominio_id = 2) "
        "ORDER BY dueno_correo_id"
    )
    slug1 = sql_scalar("SELECT slug FROM dominios WHERE dominio_id = 1")
    slug2 = sql_scalar("SELECT slug FROM dominios WHERE dominio_id = 2")
    superadmin = sql_scalar(
        "SELECT TOP 1 correo FROM superadmins_correos "
        "WHERE superadmin_id = 1 ORDER BY superadmin_correo_id"
    )
    return {
        "owner1_email": owner1, "owner2_email": owner2,
        "slug1": slug1, "slug2": slug2,
        "superadmin_email": superadmin,
    }


@pytest.fixture(scope="session")
def owner1_token(client: httpx.Client, seed_identities: dict) -> str:
    return login(client, seed_identities["owner1_email"], OWNER_PASSWORD, "owner")["accessToken"]


@pytest.fixture(scope="session")
def owner2_token(client: httpx.Client, seed_identities: dict) -> str:
    return login(client, seed_identities["owner2_email"], OWNER_PASSWORD, "owner")["accessToken"]


@pytest.fixture(scope="session")
def superadmin_token(client: httpx.Client, seed_identities: dict) -> str:
    return login(client, seed_identities["superadmin_email"], SUPERADMIN_PASSWORD, "superadmin")["accessToken"]


@pytest.fixture()
def cleanup_sql():
    """Registra statements de limpieza que se ejecutan en teardown (orden LIFO).

    Uso: cleanup_sql(f"DELETE FROM reservaciones WHERE reserva_id = {rid}")
    La BD debe quedar en el estado del seed al terminar cada test.
    """
    statements: list[str] = []

    def register(stmt: str) -> None:
        statements.append(stmt)

    yield register
    for stmt in reversed(statements):
        run_sql(stmt)
