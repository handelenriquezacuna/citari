"""Agente 3 (Flujos de negocio E2E) - condicion de carrera CRITICA sobre
POST /public/{slug}/bookings: dos clientes distintos intentan reservar EL
MISMO bloque de disponibilidad al mismo instante.

sp_crear_reservacion usa bloqueo pesimista (UPDLOCK, HOLDLOCK) sobre el
bloque (database/scripts/04-procedures.sql, #9) para que, bajo concurrencia
real, solo una de las dos transacciones gane la carrera y la otra choque con
50040 (409, "El bloque de disponibilidad ya esta ocupado" o "Ya existe una
reservacion activa para este bloque"). Este archivo lo prueba con hilos de
verdad (threading.Barrier sincroniza el disparo real de las 2 requests HTTP,
no solo la creacion de las tasks) contra la API real, 5 iteraciones
independientes; el resultado esperado en CADA una es EXACTAMENTE un 201 y un
409. Si alguna iteracion produce 2x201 (doble reserva del mismo bloque,
corrupcion de datos) o 2x409 (ambas transacciones abortadas, un bloque libre
que nadie reservo), el test falla y es un hallazgo BLOQUEANTE - ver
tests/reports/e2e_flows_report.md.

No modifica apps/** ni tests/e2e/conftest.py ni los test_api_*.py del
Agente 2. Reusa bearer()/sql_scalar() de conftest.py y
assert_rfc7807()/unique_tag() de test_api_helpers.py (Agente 2)."""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

import httpx
import pytest

from conftest import bearer, sql_scalar
from test_api_helpers import assert_rfc7807, unique_tag

pytestmark = pytest.mark.e2e

# Fechas 2033 exclusivas de este archivo (una por iteracion, para que el
# bloque de cada iteracion sea independiente de las demas y de los otros
# archivos test_flows_*.py de este agente). Dominio 1 del seed
# (barberia-el-colocho), localidad 1, servicio 1 (ya usados extensamente por
# el Agente 2 con fechas 2027; aqui se usa 2033 para no pisarlos).
RACE_BASE_DATE = date(2033, 8, 1)
RACE_ITERATIONS = 5


def _fire_public_booking(
    client: httpx.Client,
    barrier: threading.Barrier,
    *,
    slug: str,
    block_id: int,
    service_id: int,
    location_id: int,
    email: str,
) -> httpx.Response:
    """Se ejecuta en un worker thread. barrier.wait() bloquea a ambos
    threads hasta que los dos llegaron a este punto, para que el
    client.post() de ambos salga lo mas simultaneo posible (sincroniza el
    disparo real de la request, no solo el arranque de la tarea)."""
    barrier.wait()
    return client.post(
        f"/public/{slug}/bookings",
        json={
            "serviceId": service_id,
            "locationId": location_id,
            "availabilityBlockId": block_id,
            "customer": {
                "firstName": "Zz",
                "lastName": "Carrera",
                "email": email,
                "phone": "8888-4040",
            },
            "customerNotes": "carrera e2e - disparo simultaneo",
        },
    )


@pytest.mark.parametrize("iteration", range(1, RACE_ITERATIONS + 1))
def test_carrera_doble_reserva_simultanea_sobre_el_mismo_bloque(
    iteration: int,
    client: httpx.Client,
    owner1_token: str,
    seed_identities: dict,
    cleanup_sql,
) -> None:
    slug = seed_identities["slug1"]
    h = bearer(owner1_token)
    tag = unique_tag()
    block_date = (RACE_BASE_DATE + timedelta(days=iteration - 1)).isoformat()

    # Setup (secuencial, fuera de la carrera): un bloque nuevo por iteracion.
    block_resp = client.post(
        "/availability-blocks",
        json={
            "locationId": 1,
            "blockDate": block_date,
            "startTime": "09:00:00",
            "endTime": "09:30:00",
        },
        headers=h,
    )
    assert block_resp.status_code == 201, block_resp.text
    block_id = block_resp.json()["availabilityBlockId"]
    cleanup_sql(f"DELETE FROM bloques_de_disponibilidad WHERE bloque_disponibilidad_id = {block_id}")

    email_a = f"zz.e2e.carrera.{tag}.a@example.com"
    email_b = f"zz.e2e.carrera.{tag}.b@example.com"

    # Disparo real simultaneo: 2 threads, sincronizados por un Barrier(2) -
    # ninguno hace el POST hasta que ambos estan parados justo antes de
    # hacerlo. httpx.Client es seguro para uso concurrente desde varios
    # threads (pool de conexiones propio), asi que se reusa el fixture
    # `client` de la sesion en vez de abrir clientes nuevos por thread.
    barrier = threading.Barrier(2)
    with ThreadPoolExecutor(max_workers=2) as pool:
        future_a = pool.submit(
            _fire_public_booking,
            client,
            barrier,
            slug=slug,
            block_id=block_id,
            service_id=1,
            location_id=1,
            email=email_a,
        )
        future_b = pool.submit(
            _fire_public_booking,
            client,
            barrier,
            slug=slug,
            block_id=block_id,
            service_id=1,
            location_id=1,
            email=email_b,
        )
        resp_a = future_a.result(timeout=30)
        resp_b = future_b.result(timeout=30)

    print(
        f"\n[carrera] iteracion {iteration}/{RACE_ITERATIONS} "
        f"(bloque {block_id}, fecha {block_date}): "
        f"thread A={resp_a.status_code}, thread B={resp_b.status_code}"
    )

    # Registra la limpieza de TODO lo que cualquiera de los dos threads haya
    # llegado a crear ANTES de la asercion critica: si el hallazgo
    # bloqueante llegara a materializarse (2x201: dos reservas sobre el
    # mismo bloque), ambas deben limpiarse igual - la limpieza no puede
    # depender de que la asercion de abajo pase.
    for resp, email in ((resp_a, email_a), (resp_b, email_b)):
        cliente_id = sql_scalar(f"SELECT cliente_id FROM clientes_correos WHERE correo = '{email}'")
        if cliente_id:
            cleanup_sql(f"DELETE FROM clientes WHERE cliente_id = {cliente_id}")
            cleanup_sql(f"DELETE FROM clientes_correos WHERE cliente_id = {cliente_id}")
            cleanup_sql(f"DELETE FROM clientes_telefonos WHERE cliente_id = {cliente_id}")
        if resp.status_code == 201:
            booking_id = resp.json()["bookingId"]
            cleanup_sql(f"DELETE FROM reservaciones WHERE reserva_id = {booking_id}")
            cleanup_sql(f"DELETE FROM codigos_de_rastreos WHERE reserva_id = {booking_id}")
            cleanup_sql(
                f"DELETE FROM registros WHERE nombre_entidad = 'reservaciones' AND entidad_id = {booking_id}"
            )

    statuses = sorted([resp_a.status_code, resp_b.status_code])
    assert statuses == [201, 409], (
        f"iteracion {iteration}: resultado inesperado bajo concurrencia real - "
        f"thread A={resp_a.status_code}, thread B={resp_b.status_code} "
        f"(se esperaba EXACTAMENTE un 201 y un 409; bloqueante si esto falla: "
        f"ver docs/sql-signatures.md #9 sobre el bloqueo UPDLOCK+HOLDLOCK de "
        f"sp_crear_reservacion)"
    )

    winner_resp, loser_resp = (resp_a, resp_b) if resp_a.status_code == 201 else (resp_b, resp_a)
    assert_rfc7807(loser_resp.json(), 409)
    winner_body = winner_resp.json()
    assert winner_body["status"] == "pending"

    # Invariante de negocio (mismo que protege el trigger
    # tr_prevenir_doble_reservacion, 07-triggers.sql #6, THROW 50043):
    # exactamente una reservacion no cancelada apunta a este bloque.
    active_count = sql_scalar(
        f"SELECT COUNT(*) FROM reservaciones WHERE bloque_disponibilidad_id = {block_id} "
        "AND estado_reservacion_id <> (SELECT estado_reservacion_id FROM estados_reservaciones WHERE nombre = N'cancelada')"
    )
    assert active_count == "1", (
        f"iteracion {iteration}: se esperaba exactamente 1 reservacion activa "
        f"sobre el bloque {block_id}, se encontraron {active_count}"
    )
