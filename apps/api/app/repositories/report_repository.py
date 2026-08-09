from __future__ import annotations

from datetime import date
from typing import Any

import pyodbc

from app.db import query_view
from app.repositories.booking_repository import DETAIL_SELECT_BASE


class ReportRepository:
    """Read-only access to the WP3 reporting views."""

    def __init__(self, conn: pyodbc.Connection) -> None:
        self._conn = conn

    def dashboard(self, tenant_id: int) -> dict[str, Any] | None:
        sql = "SELECT * FROM v_dashboard_dominio WHERE dominio_id = ?"
        rows = query_view(self._conn, sql, [tenant_id], label="v_dashboard_dominio")
        return rows[0] if rows else None

    def daily_agenda(self, tenant_id: int, agenda_date: date) -> list[dict[str, Any]]:
        """WP7b correction: v_agenda_diaria's date column is `fecha` (the
        WP5 stub filtered on the non-existent `fecha_reservacion`)."""
        sql = (
            "SELECT * FROM v_agenda_diaria WHERE dominio_id = ? AND fecha = ? ORDER BY fecha_inicio"
        )
        return query_view(self._conn, sql, [tenant_id, agenda_date], label="v_agenda_diaria")

    def bookings_detail(
        self, tenant_id: int, *, page: int, page_size: int
    ) -> tuple[list[dict[str, Any]], int]:
        """GET /reports/bookings-detail: same underlying view/row shape as
        GET /bookings (see app.repositories.booking_repository.
        DETAIL_SELECT_BASE), just without the status/date filters."""
        total_rows = query_view(
            self._conn,
            "SELECT COUNT(*) AS total FROM v_detalle_reservaciones WHERE dominio_id = ?",
            [tenant_id],
            label="v_detalle_reservaciones",
        )
        total = int(total_rows[0]["total"]) if total_rows else 0

        sql = (
            DETAIL_SELECT_BASE
            + " WHERE v.dominio_id = ? ORDER BY v.fecha_inicio DESC, v.reserva_id DESC "
            "OFFSET ? ROWS FETCH NEXT ? ROWS ONLY"
        )
        rows = query_view(
            self._conn,
            sql,
            [tenant_id, (page - 1) * page_size, page_size],
            label="v_detalle_reservaciones",
        )
        return rows, total

    def services_demand(self, tenant_id: int) -> list[dict[str, Any]]:
        sql = (
            "SELECT * FROM v_demanda_servicios WHERE dominio_id = ? "
            "ORDER BY total_reservaciones DESC"
        )
        return query_view(self._conn, sql, [tenant_id], label="v_demanda_servicios")

    def availability_status(self, tenant_id: int, status_date: date) -> list[dict[str, Any]]:
        """WP7b correction: v_estado_disponibilidad's date column is
        `fecha_de_bloque` (the WP5 stub filtered on the non-existent
        `fecha_bloque`)."""
        sql = (
            "SELECT * FROM v_estado_disponibilidad WHERE dominio_id = ? AND fecha_de_bloque = ? "
            "ORDER BY fecha_inicio"
        )
        return query_view(
            self._conn, sql, [tenant_id, status_date], label="v_estado_disponibilidad"
        )
