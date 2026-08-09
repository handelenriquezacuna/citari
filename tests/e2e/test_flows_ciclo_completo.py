"""Agente 3 (Flujos de negocio E2E) - flujo de negocio completo, de punta a
punta, con un tenant NUEVO (no del seed): registro -> activacion -> el owner
monta su catalogo (categoria/servicio/localidad/horario/bloques) -> un
cliente publico reserva -> rastrea/reagenda/cancela -> el owner y el
superadmin ven el resultado reflejado en /bookings, /reports/dashboard y
/audit-logs.

No modifica apps/** ni tests/e2e/conftest.py ni los test_api_*.py del
Agente 2 (fuera de alcance de escritura). Reusa bearer()/run_sql()/
sql_scalar() de conftest.py y unique_tag()/assert_rfc7807() de
test_api_helpers.py (helpers del Agente 2, import directo, sin duplicar
logica).

Slug/correos con SUFIJO FIJO (no unique_tag()): a diferencia de los tests
del Agente 2 (que corren muchos tests pequenos por sesion y necesitan evitar
colisiones entre ellos), este archivo tiene un solo escenario narrativo por
corrida; usar un sufijo fijo lo hace legible en los logs/reportes y sigue
siendo seguro entre corridas porque cleanup_sql borra el dominio temporal
COMPLETO (por dominio_id) al final de cada corrida - ver DoD: verde dos
veces seguidas.

Orden de limpieza (FK reales confirmadas en database/scripts/02-create-tables.sql):
reservaciones depende de dominios/clientes/servicios/localidades/bloques;
codigos_de_rastreos depende de reservaciones; registros depende de dominios
(dueno_id/superadmin_id quedan NULL en los registros que generan los
triggers de reservaciones, asi que no dependen realmente de
duenos_de_dominios aqui); servicios depende de categorias_servicios;
horarios depende de localidades; duenos_de_dominios depende de dominios.
cleanup_sql corre en orden LIFO (conftest.py), por lo que el borrado FISICO
correcto (codigos_de_rastreos -> registros -> reservaciones -> bloques ->
clientes -> servicios -> categorias -> horarios -> localidades -> duenos ->
dominios) se logra registrando las 11 sentencias en el orden EXACTAMENTE
INVERSO, todas de una vez apenas se conoce tenant_id (ver primer bloque del
test), para que sin importar en que paso posterior falle el resto del
flujo, el teardown deje la base sin residuos del dominio temporal."""

from __future__ import annotations

import re

import httpx
import pytest

from conftest import bearer, sql_scalar
from test_api_helpers import assert_rfc7807

pytestmark = pytest.mark.e2e

FLOW_SLUG = "e2e-flow-ciclocompleto"
FLOW_BUSINESS_EMAIL = "zz.e2e.flow.negocio@example.com"
FLOW_OWNER_EMAIL = "zz.e2e.flow.duenio@example.com"
FLOW_OWNER_PASSWORD = "ZzE2eFlow123"
FLOW_CUSTOMER_EMAIL = "zz.e2e.flow.cliente@example.com"

# CITARI-XXXXXX, alfabeto real de dbo.fn_generar_codigo_rastreo
# (database/scripts/05-functions.sql): sin 0/O ni 1/I.
TRACKING_CODE_RE = re.compile(r"^CITARI-[23456789ABCDEFGHJKLMNPQRSTUVWXYZ]{6}$")

# Fechas 2033 exclusivas de este archivo (no chocan con los 2027 del
# Agente 2 ni con los rangos usados por test_flows_carrera.py /
# test_flows_logging.py dentro de este mismo agente).
BLOCK_A_DATE = "2033-06-15"  # miercoles
BLOCK_B_DATE = "2033-06-16"  # jueves

SEED_COUNT_TABLES = ("dominios", "reservaciones", "bloques_de_disponibilidad", "clientes")


@pytest.fixture(scope="module", autouse=True)
def _seed_counts_intactos_alrededor_del_modulo():
    """Confirma que los 4 conteos criticos del seed (50 filas cada uno,
    R4) estan intactos ANTES de que este modulo cree el dominio temporal, y
    otra vez DESPUES de que el teardown de cleanup_sql (fixture
    function-scoped que se resuelve/cierra antes que este fixture
    module-scoped, al ser el unico test del modulo) termine de borrarlo
    todo. Es la verificacion final que pide el DoD del Agente 3."""
    for table in SEED_COUNT_TABLES:
        count = sql_scalar(f"SELECT COUNT(*) FROM {table}")
        assert count == "50", (
            f"{table} no tiene 50 filas ANTES de correr este modulo "
            f"(count={count}; residuo de una corrida previa sin limpiar)"
        )
    yield
    for table in SEED_COUNT_TABLES:
        count = sql_scalar(f"SELECT COUNT(*) FROM {table}")
        assert count == "50", (
            f"{table} no volvio a 50 filas DESPUES de la limpieza de este modulo "
            f"(count={count}; el dominio temporal dejo residuos)"
        )


def test_ciclo_completo_flujo_de_negocio_extremo_a_extremo(
    client: httpx.Client,
    superadmin_token: str,
    cleanup_sql,
) -> None:
    sh = bearer(superadmin_token)

    # -----------------------------------------------------------------
    # (a) Registro de un tenant NUEVO -> 201, dominio 'pendiente'; login
    # del owner recien registrado -> 403 (dominio pendiente de activacion,
    # comportamiento real documentado por el Agente 2 en
    # test_api_auth.py::test_register_owner_creates_pending_tenant_and_cleans_up).
    # -----------------------------------------------------------------
    register_resp = client.post(
        "/auth/register-owner",
        json={
            "businessName": "ZZ E2E Flow Ciclo Completo",
            "businessTypeId": 1,
            "slug": FLOW_SLUG,
            "businessEmail": FLOW_BUSINESS_EMAIL,
            "ownerFirstName": "Zz",
            "ownerLastName": "Flow Ciclo Completo",
            "ownerEmail": FLOW_OWNER_EMAIL,
            "password": FLOW_OWNER_PASSWORD,
        },
    )
    assert register_resp.status_code == 201, register_resp.text
    register_body = register_resp.json()
    tenant_id = register_body["tenantId"]
    assert register_body["owner"]["email"] == FLOW_OWNER_EMAIL
    assert register_body["owner"]["tenantId"] == tenant_id

    # Limpieza total del dominio temporal, registrada YA (antes de crear
    # nada mas): ver docstring del modulo para la justificacion del orden.
    cleanup_sql(f"DELETE FROM dominios WHERE dominio_id = {tenant_id}")
    cleanup_sql(f"DELETE FROM duenos_de_dominios WHERE dominio_id = {tenant_id}")
    cleanup_sql(f"DELETE FROM localidades WHERE dominio_id = {tenant_id}")
    cleanup_sql(f"DELETE FROM horarios WHERE dominio_id = {tenant_id}")
    cleanup_sql(f"DELETE FROM categorias_servicios WHERE dominio_id = {tenant_id}")
    cleanup_sql(f"DELETE FROM servicios WHERE dominio_id = {tenant_id}")
    cleanup_sql(f"DELETE FROM clientes WHERE dominio_id = {tenant_id}")
    cleanup_sql(f"DELETE FROM bloques_de_disponibilidad WHERE dominio_id = {tenant_id}")
    cleanup_sql(f"DELETE FROM reservaciones WHERE dominio_id = {tenant_id}")
    cleanup_sql(f"DELETE FROM registros WHERE dominio_id = {tenant_id}")
    cleanup_sql(
        "DELETE FROM codigos_de_rastreos WHERE reserva_id IN "
        f"(SELECT reserva_id FROM reservaciones WHERE dominio_id = {tenant_id})"
    )
    # Tablas hijas normalizadas (correo/telefono 1:N): deben registrarse
    # despues de sus tablas padre en esta lista para que, en el orden LIFO
    # del teardown, se borren ANTES que el padre.
    cleanup_sql(f"DELETE FROM dominios_correos WHERE dominio_id = {tenant_id}")
    cleanup_sql(f"DELETE FROM dominios_telefonos WHERE dominio_id = {tenant_id}")
    cleanup_sql(
        "DELETE FROM duenos_de_dominios_correos WHERE dueno_id IN "
        f"(SELECT dueno_id FROM duenos_de_dominios WHERE dominio_id = {tenant_id})"
    )
    cleanup_sql(
        "DELETE FROM duenos_de_dominios_telefonos WHERE dueno_id IN "
        f"(SELECT dueno_id FROM duenos_de_dominios WHERE dominio_id = {tenant_id})"
    )
    cleanup_sql(
        "DELETE FROM clientes_correos WHERE cliente_id IN "
        f"(SELECT cliente_id FROM clientes WHERE dominio_id = {tenant_id})"
    )
    cleanup_sql(
        "DELETE FROM clientes_telefonos WHERE cliente_id IN "
        f"(SELECT cliente_id FROM clientes WHERE dominio_id = {tenant_id})"
    )
    cleanup_sql(
        "DELETE FROM localidades_telefonos WHERE localidad_id IN "
        f"(SELECT localidad_id FROM localidades WHERE dominio_id = {tenant_id})"
    )

    assert sql_scalar(
        "SELECT ed.nombre FROM dominios d JOIN estados_dominios ed "
        f"ON ed.dominio_estado_id = d.dominio_estado_id WHERE d.dominio_id = {tenant_id}"
    ) == "pendiente"

    login_pending_resp = client.post(
        "/auth/login",
        json={"email": FLOW_OWNER_EMAIL, "password": FLOW_OWNER_PASSWORD, "role": "owner"},
    )
    assert login_pending_resp.status_code == 403, login_pending_resp.text
    assert_rfc7807(login_pending_resp.json(), 403)
    assert "pendiente" in login_pending_resp.json()["detail"]

    # -----------------------------------------------------------------
    # (b) Superadmin activa el dominio -> login del owner nuevo ahora es 200.
    # -----------------------------------------------------------------
    activate_resp = client.post(f"/admin/tenants/{tenant_id}/activate", headers=sh)
    assert activate_resp.status_code == 200, activate_resp.text
    assert activate_resp.json()["status"] == "activo"

    login_resp = client.post(
        "/auth/login",
        json={"email": FLOW_OWNER_EMAIL, "password": FLOW_OWNER_PASSWORD, "role": "owner"},
    )
    assert login_resp.status_code == 200, login_resp.text
    owner_token = login_resp.json()["accessToken"]
    h = bearer(owner_token)

    # -----------------------------------------------------------------
    # (c) El owner nuevo monta su catalogo: categoria -> servicio (30 min)
    # -> localidad -> horario semanal (lunes-viernes) -> 2 bloques de
    # disponibilidad en 2033 (el segundo para el reagendamiento del paso e).
    # -----------------------------------------------------------------
    category_resp = client.post(
        "/service-categories",
        json={"name": "ZZ E2E Flow Categoria", "description": "Categoria del flujo E2E completo"},
        headers=h,
    )
    assert category_resp.status_code == 201, category_resp.text
    category_id = category_resp.json()["categoryId"]

    service_resp = client.post(
        "/services",
        json={
            "categoryId": category_id,
            "name": "ZZ E2E Flow Servicio",
            "description": "Servicio de 30 minutos del flujo E2E completo",
            "durationMinutes": 30,
            "price": 8000,
            "showPrice": True,
        },
        headers=h,
    )
    assert service_resp.status_code == 201, service_resp.text
    service = service_resp.json()
    service_id = service["serviceId"]
    assert service["durationMinutes"] == 30

    location_resp = client.post(
        "/locations",
        json={
            "name": "ZZ E2E Flow Sede Central",
            "provincia": "San Jose",
            "canton": "Central",
            "distrito": "Carmen",
            "codigoPostal": "10101",
            "phone": "2200-7000",
        },
        headers=h,
    )
    assert location_resp.status_code == 201, location_resp.text
    location_id = location_resp.json()["locationId"]

    hours_resp = client.put(
        "/business-hours",
        json={
            "locationId": location_id,
            "hours": [
                {"dayOfWeek": 1, "openTime": "09:00:00", "closeTime": "17:00:00", "isClosed": False},
                {"dayOfWeek": 2, "openTime": "09:00:00", "closeTime": "17:00:00", "isClosed": False},
                {"dayOfWeek": 3, "openTime": "09:00:00", "closeTime": "17:00:00", "isClosed": False},
                {"dayOfWeek": 4, "openTime": "09:00:00", "closeTime": "17:00:00", "isClosed": False},
                {"dayOfWeek": 5, "openTime": "09:00:00", "closeTime": "17:00:00", "isClosed": False},
            ],
        },
        headers=h,
    )
    assert hours_resp.status_code == 200, hours_resp.text
    hours_body = hours_resp.json()
    assert len(hours_body) == 5
    assert {row["dayOfWeek"] for row in hours_body} == {1, 2, 3, 4, 5}

    block_a_resp = client.post(
        "/availability-blocks",
        json={
            "locationId": location_id,
            "blockDate": BLOCK_A_DATE,
            "startTime": "10:00:00",
            "endTime": "10:30:00",
        },
        headers=h,
    )
    assert block_a_resp.status_code == 201, block_a_resp.text
    block_a_id = block_a_resp.json()["availabilityBlockId"]

    block_b_resp = client.post(
        "/availability-blocks",
        json={
            "locationId": location_id,
            "blockDate": BLOCK_B_DATE,
            "startTime": "11:00:00",
            "endTime": "11:30:00",
        },
        headers=h,
    )
    assert block_b_resp.status_code == 201, block_b_resp.text
    block_b_id = block_b_resp.json()["availabilityBlockId"]

    # -----------------------------------------------------------------
    # (d) Cliente publico: slug -> servicios -> disponibilidad (el bloque A
    # aparece) -> crea la reserva -> 201 con trackingCode con formato vigente.
    # -----------------------------------------------------------------
    public_tenant_resp = client.get(f"/public/{FLOW_SLUG}")
    assert public_tenant_resp.status_code == 200, public_tenant_resp.text
    assert public_tenant_resp.json()["tenantId"] == tenant_id
    # Hallazgo (ver tests/reports/e2e_flows_report.md): TenantRepository
    # .get_active_by_slug (usado por GET /public/{slug}) solo hace SELECT
    # dominio_id/slug/nombre/descripcion/mensaje_publico - nunca
    # correo/telefono/logo_url/estado_nombre - asi que email/phone/logoUrl/
    # status SIEMPRE viajan null en este endpoint, aunque el dominio tenga
    # esos valores reales y el endpoint por definicion solo devuelva
    # dominios activos (fn_dominio_activo ya filtro por 'activo' antes de
    # llegar aqui). Confirmado tambien contra un dominio del seed
    # (GET /public/barberia-el-colocho -> status: null).
    assert public_tenant_resp.json()["status"] is None

    public_services_resp = client.get(f"/public/{FLOW_SLUG}/services")
    assert public_services_resp.status_code == 200
    assert service_id in [s["serviceId"] for s in public_services_resp.json()]

    public_availability_resp = client.get(
        f"/public/{FLOW_SLUG}/availability", params={"date": BLOCK_A_DATE}
    )
    assert public_availability_resp.status_code == 200
    assert block_a_id in [b["availabilityBlockId"] for b in public_availability_resp.json()]

    booking_resp = client.post(
        f"/public/{FLOW_SLUG}/bookings",
        json={
            "serviceId": service_id,
            "locationId": location_id,
            "availabilityBlockId": block_a_id,
            "customer": {
                "firstName": "Zz",
                "lastName": "Flow Cliente",
                "email": FLOW_CUSTOMER_EMAIL,
                "phone": "8888-7001",
            },
            "customerNotes": "Primera visita, flujo E2E completo",
        },
    )
    assert booking_resp.status_code == 201, booking_resp.text
    booking = booking_resp.json()
    assert booking["status"] == "pending"
    booking_id = booking["bookingId"]
    tracking_code = booking["trackingCode"]
    assert TRACKING_CODE_RE.match(tracking_code), f"trackingCode con formato inesperado: {tracking_code!r}"

    # -----------------------------------------------------------------
    # (e) Tracking: consulta -> reagenda al bloque B (el bloque A reaparece
    # libre) -> cancela (el bloque B reaparece libre).
    # -----------------------------------------------------------------
    track_resp = client.get(f"/track/{tracking_code}")
    assert track_resp.status_code == 200
    assert track_resp.json()["bookingId"] == booking_id
    assert track_resp.json()["status"] == "pending"

    reschedule_resp = client.post(
        f"/track/{tracking_code}/reschedule", json={"newAvailabilityBlockId": block_b_id}
    )
    assert reschedule_resp.status_code == 200, reschedule_resp.text
    assert reschedule_resp.json()["startTime"] == "11:00:00"
    assert reschedule_resp.json()["status"] == "rescheduled"

    avail_a_after_reschedule = client.get(
        f"/public/{FLOW_SLUG}/availability", params={"date": BLOCK_A_DATE}
    ).json()
    assert block_a_id in [b["availabilityBlockId"] for b in avail_a_after_reschedule]

    avail_b_after_reschedule = client.get(
        f"/public/{FLOW_SLUG}/availability", params={"date": BLOCK_B_DATE}
    ).json()
    assert block_b_id not in [b["availabilityBlockId"] for b in avail_b_after_reschedule]

    cancel_resp = client.post(f"/track/{tracking_code}/cancel")
    assert cancel_resp.status_code == 200, cancel_resp.text
    assert cancel_resp.json()["status"] == "cancelled"

    avail_b_after_cancel = client.get(
        f"/public/{FLOW_SLUG}/availability", params={"date": BLOCK_B_DATE}
    ).json()
    assert block_b_id in [b["availabilityBlockId"] for b in avail_b_after_cancel]

    # -----------------------------------------------------------------
    # (f) Owner: GET /bookings refleja la reserva cancelada; GET
    # /reports/dashboard muestra los conteos del dominio nuevo; superadmin:
    # GET /audit-logs?tenantId=<nuevo> contiene reserva_creada y
    # reserva_actualizada (generados por los triggers 2 y 3 de
    # 07-triggers.sql: 1 insercion + 2 actualizaciones de estado -
    # pendiente->reagendada, reagendada->cancelada).
    # -----------------------------------------------------------------
    owner_bookings_resp = client.get("/bookings", params={"pageSize": 100}, headers=h)
    assert owner_bookings_resp.status_code == 200
    owner_bookings = owner_bookings_resp.json()["items"]
    booking_row = next((b for b in owner_bookings if b["bookingId"] == booking_id), None)
    assert booking_row is not None, "la reserva no aparece en GET /bookings del dominio nuevo"
    assert booking_row["status"] == "cancelled"

    dashboard_resp = client.get("/reports/dashboard", headers=h)
    assert dashboard_resp.status_code == 200
    dashboard = dashboard_resp.json()
    assert dashboard["tenantId"] == tenant_id
    assert dashboard["totalBookings"] == 1
    assert dashboard["pendingBookings"] == 0
    assert dashboard["confirmedBookings"] == 0
    assert dashboard["cancelledBookings"] == 1
    assert dashboard["totalCustomers"] == 1
    assert dashboard["totalActiveServices"] == 1
    assert dashboard["totalActiveLocations"] == 1

    audit_resp = client.get(
        "/audit-logs", params={"tenantId": tenant_id, "pageSize": 100}, headers=sh
    )
    assert audit_resp.status_code == 200
    audit_items = audit_resp.json()["items"]
    assert all(item["tenantId"] == tenant_id for item in audit_items)
    actions = [item["action"] for item in audit_items]
    assert "reserva_creada" in actions
    assert "reserva_actualizada" in actions
    assert actions.count("reserva_creada") == 1
    assert actions.count("reserva_actualizada") == 2
    assert len(audit_items) == 3
