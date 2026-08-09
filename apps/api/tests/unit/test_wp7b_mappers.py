"""Mapper tests for the WP7b additions: locations, business hours, reports
(dashboard/agenda/demand/availability-status), audit logs, and the tenant
mapper's conditional `status` field."""

from __future__ import annotations

from datetime import date, datetime, time

from app.mappers.audit_log_mapper import map_audit_log
from app.mappers.hours_mapper import map_business_hour
from app.mappers.location_mapper import map_location
from app.mappers.report_mapper import (
    map_availability_status,
    map_daily_agenda_item,
    map_dashboard,
    map_service_demand,
)
from app.mappers.tenant_mapper import map_tenant


def test_map_location() -> None:
    row = {
        "localidad_id": 3,
        "dominio_id": 1,
        "nombre": "Sucursal Centro",
        "provincia": "San Jose",
        "canton": "Central",
        "distrito": "Carmen",
        "codigo_postal": "10101",
        "telefono": "2222-0000",
        "principal": 1,
        "activo": 1,
    }

    result = map_location(row)

    assert result == {
        "location_id": 3,
        "name": "Sucursal Centro",
        "provincia": "San Jose",
        "canton": "Central",
        "distrito": "Carmen",
        "codigo_postal": "10101",
        "phone": "2222-0000",
        "is_main": True,
        "is_active": True,
    }


def test_map_business_hour_closed_day() -> None:
    row = {
        "horario_id": 8,
        "dominio_id": 1,
        "localidad_id": 3,
        "dia_semana": 7,
        "hora_apertura": None,
        "hora_cerrado": None,
        "cerrado": 1,
    }

    result = map_business_hour(row)

    assert result["business_hour_id"] == 8
    assert result["day_of_week"] == 7
    assert result["open_time"] is None
    assert result["close_time"] is None
    assert result["is_closed"] is True


def test_map_dashboard() -> None:
    row = {
        "dominio_id": 1,
        "nombre": "Barberia El Colocho",
        "total_reservaciones": 12,
        "reservaciones_pendientes": 3,
        "reservaciones_confirmadas": 5,
        "reservaciones_canceladas": 4,
        "total_clientes": 9,
        "total_servicios_activos": 6,
        "total_localidades_activas": 2,
    }

    result = map_dashboard(row)

    assert result == {
        "tenant_id": 1,
        "name": "Barberia El Colocho",
        "total_bookings": 12,
        "pending_bookings": 3,
        "confirmed_bookings": 5,
        "cancelled_bookings": 4,
        "total_customers": 9,
        "total_active_services": 6,
        "total_active_locations": 2,
    }


def test_map_daily_agenda_item_narrows_datetimes_to_times() -> None:
    row = {
        "dominio_id": 1,
        "fecha": date(2032, 5, 1),
        "fecha_inicio": datetime(2032, 5, 1, 9, 0),
        "fecha_final": datetime(2032, 5, 1, 9, 30),
        "servicio_nombre": "Corte",
        "cliente_nombre": "Ana Rodriguez",
        "localidad_nombre": "Centro",
        "estado": "pendiente",
    }

    result = map_daily_agenda_item(row)

    assert result["booking_date"] == date(2032, 5, 1)
    assert result["start_time"] == time(9, 0)
    assert result["end_time"] == time(9, 30)
    assert result["status"] == "pendiente"


def test_map_service_demand_with_zero_bookings() -> None:
    row = {
        "servicio_id": 4,
        "dominio_id": 1,
        "servicio_nombre": "Manicura",
        "total_reservaciones": 0,
        "ultima_reserva": None,
    }

    result = map_service_demand(row)

    assert result == {
        "service_id": 4,
        "service_name": "Manicura",
        "total_bookings": 0,
        "last_booking_at": None,
    }


def test_map_availability_status() -> None:
    row = {
        "bloque_id": 77,
        "dominio_id": 1,
        "dominio_slug": "barberia",
        "localidad_id": 3,
        "localidad_nombre": "Centro",
        "fecha_de_bloque": date(2032, 5, 1),
        "fecha_inicio": datetime(2032, 5, 1, 9, 0),
        "fecha_final": datetime(2032, 5, 1, 9, 30),
        "bloque_activo": 0,
        "reservado": 1,
        "reserva_id": 200,
    }

    result = map_availability_status(row)

    assert result == {
        "availability_block_id": 77,
        "location_id": 3,
        "location_name": "Centro",
        "block_date": date(2032, 5, 1),
        "start_time": time(9, 0),
        "end_time": time(9, 30),
        "is_active": False,
        "is_reserved": True,
        "booking_id": 200,
    }


def test_map_audit_log() -> None:
    row = {
        "registro_id": 501,
        "dominio_id": 1,
        "dueno_id": None,
        "superadmin_id": None,
        "accion": "reserva_creada",
        "nombre_entidad": "reservaciones",
        "entidad_id": 200,
        "valor_anterior": None,
        "nuevo_valor": None,
        "creado_en": datetime(2032, 5, 1, 9, 0),
    }

    result = map_audit_log(row)

    assert result["audit_id"] == 501
    assert result["tenant_id"] == 1
    assert result["action"] == "reserva_creada"
    assert result["entity_name"] == "reservaciones"
    assert result["entity_id"] == 200
    assert result["created_at"] == datetime(2032, 5, 1, 9, 0)


def test_map_tenant_surfaces_status_only_when_present() -> None:
    base_row = {
        "dominio_id": 1,
        "slug": "salon-bella",
        "nombre": "Salon Bella",
        "descripcion": None,
        "mensaje_publico": None,
    }

    without_status = map_tenant(base_row)
    with_status = map_tenant({**base_row, "estado_nombre": "suspendido"})

    assert "status" not in without_status
    assert with_status["status"] == "suspendido"
