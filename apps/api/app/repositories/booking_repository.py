from __future__ import annotations

from typing import Any

import pyodbc

from app.db import exec_sp, exec_sp_output, query_view

# Shared SELECT for the WP7b owner-facing flows (/bookings, /reports/*):
# aliases v_detalle_reservaciones' own columns (it already exposes
# codigo_rastreo via its own LEFT JOIN onto codigos_de_rastreos - see
# database/scripts/06-views.sql - so no re-join is needed here, unlike
# _DETAIL_SELECT below) into the same intermediate row shape
# app.mappers.booking_mapper.map_booking_detail expects. Reused by
# get_by_id/list_by_tenant here and by app.repositories.report_repository's
# bookings_detail (GET /reports/bookings-detail).
DETAIL_SELECT_BASE = """
SELECT
    v.reserva_id                  AS reservacion_id,
    v.dominio_id                  AS dominio_id,
    v.localidad_id                AS localidad_id,
    v.localidad_nombre            AS nombre_localidad,
    v.cliente_nombre              AS nombre_cliente,
    v.servicio_nombre             AS nombre_servicio,
    CAST(v.fecha_inicio AS DATE)  AS fecha_reservacion,
    CAST(v.fecha_inicio AS TIME)  AS hora_inicio,
    CAST(v.fecha_final AS TIME)   AS hora_fin,
    v.estado                      AS estado,
    v.nota_cliente                AS nota_cliente,
    v.codigo_rastreo               AS codigo_rastreo,
    v.creado_en                   AS creado_en
FROM v_detalle_reservaciones v
"""

# Shared SELECT for the WP6 public/track detail flows. Aliases
# v_detalle_reservaciones' real column names (reserva_id, cliente_nombre,
# servicio_nombre, fecha_inicio, fecha_final, ...) into the intermediate row
# shape app.mappers.booking_mapper.map_booking_detail expects (reservacion_id,
# nombre_cliente, nombre_servicio, fecha_reservacion, hora_inicio, ...) -
# that intermediate contract is what tests/unit/test_mappers.py locks in, not
# the view's own column names. Also translates the Spanish `estado`
# (estados_reservaciones.nombre) to the English slug the frontend expects
# (see app.mappers.booking_mapper._STATUS_ES_TO_EN for the same table kept in
# sync on the Python side) and re-joins codigos_de_rastreos by reserva_id to
# expose `expira_en`/`activo` (the view itself only exposes `codigo_rastreo`,
# not the code's own expiry/active flag).
_DETAIL_SELECT = """
SELECT
    v.reserva_id                                    AS reservacion_id,
    v.dominio_id                                     AS dominio_id,
    v.dominio_slug                                   AS dominio_slug,
    v.localidad_id                                   AS localidad_id,
    v.localidad_nombre                               AS nombre_localidad,
    v.cliente_nombre                                 AS nombre_cliente,
    v.servicio_nombre                                AS nombre_servicio,
    CAST(v.fecha_inicio AS DATE)                     AS fecha_reservacion,
    CAST(v.fecha_inicio AS TIME)                     AS hora_inicio,
    CAST(v.fecha_final AS TIME)                      AS hora_fin,
    CASE v.estado
        WHEN N'pendiente'  THEN N'pending'
        WHEN N'confirmada' THEN N'confirmed'
        WHEN N'cancelada'  THEN N'cancelled'
        WHEN N'completada' THEN N'completed'
        WHEN N'reagendada' THEN N'rescheduled'
        ELSE v.estado
    END                                               AS estado,
    v.nota_cliente                                   AS nota_cliente,
    v.codigo_rastreo                                 AS codigo_rastreo,
    cr.expira_en                                     AS expira_en,
    cr.activo                                        AS codigo_activo
FROM v_detalle_reservaciones v
JOIN codigos_de_rastreos cr ON cr.reserva_id = v.reserva_id
"""


class BookingRepository:
    """reservaciones + codigos_de_rastreos (via v_detalle_reservaciones)."""

    def __init__(self, conn: pyodbc.Connection) -> None:
        self._conn = conn

    # -- WP7b (/bookings, owner-authenticated) ------------------------------
    # Not called by public.py/track.py. WP7b correction: sp_crear_reservacion
    # has no `fecha_reservacion`/`hora_inicio`/`notas_cliente` parameters -
    # its real signature (docs/sql-signatures.md #9) takes
    # cliente_id (existing customer) OR the cliente_nombre/apellido_1/
    # apellido_2/correo/telefono/notas branch (new customer, delegated
    # internally to sp_crear_cliente), plus servicio_id/localidad_id/
    # bloque_disponibilidad_id/nota_cliente, and reports the new id via
    # `@reserva_id OUTPUT` only (no result set) - like sp_crear_bloque_
    # disponibilidad in app.repositories.availability_repository, this must
    # go through exec_sp_output.
    def create(
        self,
        *,
        tenant_id: int,
        service_id: int,
        location_id: int,
        availability_block_id: int,
        customer_id: int | None = None,
        first_name: str | None = None,
        last_name_1: str | None = None,
        last_name_2: str | None = None,
        email: str | None = None,
        phone: str | None = None,
        customer_notes: str | None = None,
    ) -> int:
        """Returns the new `reserva_id`. Neither `customer_id` nor the
        contact fields are validated here - an incomplete combination is
        rejected by the SP itself (THROW 50005 -> 400), same as the WP6
        public flow relies on for its own required contact fields."""
        return exec_sp_output(
            self._conn,
            "sp_crear_reservacion",
            {
                "dominio_id": tenant_id,
                "servicio_id": service_id,
                "localidad_id": location_id,
                "bloque_disponibilidad_id": availability_block_id,
                "cliente_id": customer_id,
                "cliente_nombre": first_name,
                "cliente_apellido_1": last_name_1,
                "cliente_apellido_2": last_name_2,
                "cliente_correo": email,
                "cliente_telefono": phone,
                "nota_cliente": customer_notes,
            },
            output_param="reserva_id",
        )

    def confirm(self, tenant_id: int, booking_id: int) -> None:
        exec_sp(
            self._conn,
            "sp_confirmar_reservacion",
            {"reserva_id": booking_id, "dominio_id": tenant_id},
        )

    def complete(self, tenant_id: int, booking_id: int) -> None:
        exec_sp(
            self._conn,
            "sp_completar_reservacion",
            {"reserva_id": booking_id, "dominio_id": tenant_id},
        )

    def get_by_id(self, tenant_id: int, booking_id: int) -> dict[str, Any] | None:
        """WP7b correction: the WP5 stub did `SELECT * FROM
        v_detalle_reservaciones ...`, which returns the view's own column
        names (reserva_id, cliente_nombre, ...) - not the intermediate keys
        map_booking_detail expects. Uses DETAIL_SELECT_BASE, same as
        list_by_tenant."""
        sql = DETAIL_SELECT_BASE + " WHERE v.dominio_id = ? AND v.reserva_id = ?"
        rows = query_view(self._conn, sql, [tenant_id, booking_id], label="v_detalle_reservaciones")
        return rows[0] if rows else None

    def list_by_tenant(
        self,
        tenant_id: int,
        *,
        page: int,
        page_size: int,
        status: str | None = None,
        booking_date: Any | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        """GET /bookings. `status`, if given, must already be the Spanish
        estados_reservaciones.nombre value (see
        app.mappers.booking_mapper.translate_status_to_spanish) - the English
        API-facing slug never reaches SQL directly."""
        conditions = ["v.dominio_id = ?"]
        params: list[Any] = [tenant_id]
        if status is not None:
            conditions.append("v.estado = ?")
            params.append(status)
        if booking_date is not None:
            conditions.append("CAST(v.fecha_inicio AS DATE) = ?")
            params.append(booking_date)
        where = " AND ".join(conditions)

        count_sql = f"SELECT COUNT(*) AS total FROM v_detalle_reservaciones v WHERE {where}"
        total_rows = query_view(self._conn, count_sql, params, label="v_detalle_reservaciones")
        total = int(total_rows[0]["total"]) if total_rows else 0

        # reserva_id DESC as tiebreaker: fecha_inicio can repeat, and
        # OFFSET/FETCH pagination needs a total order.
        sql = (
            DETAIL_SELECT_BASE + f" WHERE {where} ORDER BY v.fecha_inicio DESC, v.reserva_id DESC "
            "OFFSET ? ROWS FETCH NEXT ? ROWS ONLY"
        )
        rows = query_view(
            self._conn,
            sql,
            [*params, (page - 1) * page_size, page_size],
            label="v_detalle_reservaciones",
        )
        return rows, total

    # -- WP6 public storefront + tracking-code self-service ----------------------

    def create_public_booking(
        self,
        *,
        tenant_id: int,
        service_id: int,
        location_id: int,
        availability_block_id: int,
        first_name: str,
        last_name_1: str,
        last_name_2: str | None,
        email: str,
        phone: str,
        customer_notes: str | None,
    ) -> int:
        """POST /public/{slug}/bookings. Always takes the customer-contact
        branch of sp_crear_reservacion (no `cliente_id` - the public flow
        never has one, only contact info); the SP creates-or-reuses the
        client by (dominio_id, correo) internally via sp_crear_cliente.
        Returns the new `reserva_id` (an OUTPUT param - see
        app.db.exec_sp_output)."""
        return exec_sp_output(
            self._conn,
            "sp_crear_reservacion",
            {
                "dominio_id": tenant_id,
                "servicio_id": service_id,
                "localidad_id": location_id,
                "bloque_disponibilidad_id": availability_block_id,
                "cliente_nombre": first_name,
                "cliente_apellido_1": last_name_1,
                "cliente_apellido_2": last_name_2,
                "cliente_correo": email,
                "cliente_telefono": phone,
                "nota_cliente": customer_notes,
            },
            output_param="reserva_id",
        )

    def get_detail_by_id(self, reserva_id: int) -> dict[str, Any] | None:
        sql = _DETAIL_SELECT + " WHERE v.reserva_id = ?"
        rows = query_view(self._conn, sql, [reserva_id], label="v_detalle_reservaciones")
        return rows[0] if rows else None

    def get_by_tracking_code(self, tracking_code: str) -> dict[str, Any] | None:
        """Correction (WP6): the WP5 stub did `SELECT * FROM
        v_detalle_reservaciones WHERE codigo_rastreo = ?`, which returns the
        view's real column names (reserva_id, cliente_nombre, ...) - not the
        intermediate keys map_booking_detail expects (reservacion_id,
        nombre_cliente, ...; locked by
        tests/unit/test_mappers.py::test_map_booking_detail). See
        _DETAIL_SELECT's docstring for the full rationale."""
        sql = _DETAIL_SELECT + " WHERE v.codigo_rastreo = ?"
        rows = query_view(self._conn, sql, [tracking_code], label="v_detalle_reservaciones")
        return rows[0] if rows else None

    def cancel(self, tenant_id: int, booking_id: int) -> None:
        """Correction (WP6): sp_cancelar_reservacion's parameters are
        `@reserva_id`/`@dominio_id` - the WP5 stub sent `reservacion_id`,
        which is not a real parameter name and would fail at the ODBC layer.
        No result set/OUTPUT param on this SP; callers re-fetch the updated
        detail row afterwards (tr_liberar_bloque_al_cancelar already freed
        the block and the estado flip is visible by the time this returns)."""
        exec_sp(
            self._conn,
            "sp_cancelar_reservacion",
            {"reserva_id": booking_id, "dominio_id": tenant_id},
        )

    def reschedule(self, tenant_id: int, booking_id: int, *, availability_block_id: int) -> None:
        """Correction (WP6): sp_reagendar_reservacion's parameters are
        `@reserva_id`/`@dominio_id`/`@nuevo_bloque_id` - it has no
        booking_date/start_time parameters at all (like sp_crear_reservacion,
        it takes the new block's own fecha_inicio/fecha_final). The WP5 stub
        invented `fecha_reservacion`/`hora_inicio` params and used the wrong
        name (`bloque_disponibilidad_id` instead of `nuevo_bloque_id`) for
        the new block. Fixed and simplified to match the real signature."""
        exec_sp(
            self._conn,
            "sp_reagendar_reservacion",
            {
                "reserva_id": booking_id,
                "dominio_id": tenant_id,
                "nuevo_bloque_id": availability_block_id,
            },
        )
