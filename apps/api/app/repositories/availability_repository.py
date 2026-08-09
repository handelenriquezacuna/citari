from __future__ import annotations

from datetime import date, datetime, time
from typing import Any

import pyodbc

from app.db import exec_sp_output, query_view


class AvailabilityRepository:
    """bloques_de_disponibilidad / v_estado_disponibilidad."""

    def __init__(self, conn: pyodbc.Connection) -> None:
        self._conn = conn

    def create_block(
        self,
        *,
        tenant_id: int,
        location_id: int,
        block_date: date,
        start_time: time,
        end_time: time,
    ) -> int:
        """Correction (WP6): sp_crear_bloque_disponibilidad's parameters are
        `@fecha_de_bloque` / `@fecha_inicio` / `@fecha_final` (the latter two
        full DATETIME2, combining block_date with start/end_time), and it
        reports the new id via `@bloque_id OUTPUT` - see
        docs/sql-signatures.md #1. The WP5 stub used non-existent parameter
        names (`fecha_bloque`/`hora_inicio`/`hora_fin`) and never retrieved
        the OUTPUT value at all (exec_sp cannot - see app.db.exec_sp_output).
        Returns the new `bloque_id` (previously returned an always-empty
        dict). Used by /public and /track only indirectly, as the fixture
        that creates availability blocks for the integration tests.
        """
        start_dt = datetime.combine(block_date, start_time)
        end_dt = datetime.combine(block_date, end_time)
        return exec_sp_output(
            self._conn,
            "sp_crear_bloque_disponibilidad",
            {
                "dominio_id": tenant_id,
                "localidad_id": location_id,
                "fecha_de_bloque": block_date,
                "fecha_inicio": start_dt,
                "fecha_final": end_dt,
            },
            output_param="bloque_id",
        )

    # -- WP7b /availability-blocks (owner-authenticated) --------------------
    _OWNER_SELECT = (
        "SELECT "
        "bloque_id AS bloque_disponibilidad_id, "
        "CAST(fecha_de_bloque AS DATE) AS fecha_bloque, "
        "CAST(fecha_inicio AS TIME) AS hora_inicio, "
        "CAST(fecha_final AS TIME) AS hora_fin, "
        "reservado AS esta_reservado "
        "FROM v_estado_disponibilidad"
    )

    def get_by_id(self, tenant_id: int, block_id: int) -> dict[str, Any] | None:
        sql = self._OWNER_SELECT + " WHERE dominio_id = ? AND bloque_id = ?"
        rows = query_view(self._conn, sql, [tenant_id, block_id], label="v_estado_disponibilidad")
        return rows[0] if rows else None

    def list_owner(
        self,
        tenant_id: int,
        *,
        page: int,
        page_size: int,
        block_date: date | None = None,
        location_id: int | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        """GET /availability-blocks: paginated, with optional ?date/
        ?locationId filters (WP7b brief).

        `bloque_activo = 1` excludes soft-deleted blocks (see `deactivate`) -
        without it, DELETE /availability-blocks/{id} would not actually
        remove the block from this listing (defect D1, test/e2e-backend-
        validation)."""
        conditions = ["dominio_id = ?", "bloque_activo = 1"]
        params: list[Any] = [tenant_id]
        if block_date is not None:
            conditions.append("fecha_de_bloque = ?")
            params.append(block_date)
        if location_id is not None:
            conditions.append("localidad_id = ?")
            params.append(location_id)
        where = " AND ".join(conditions)

        total_rows = query_view(
            self._conn,
            f"SELECT COUNT(*) AS total FROM v_estado_disponibilidad WHERE {where}",
            params,
            label="v_estado_disponibilidad",
        )
        total = int(total_rows[0]["total"]) if total_rows else 0

        sql = (
            self._OWNER_SELECT
            + f" WHERE {where} ORDER BY fecha_de_bloque, fecha_inicio, bloque_id "
            "OFFSET ? ROWS FETCH NEXT ? ROWS ONLY"
        )
        rows = query_view(
            self._conn,
            sql,
            [*params, (page - 1) * page_size, page_size],
            label="v_estado_disponibilidad",
        )
        return rows, total

    def deactivate(self, tenant_id: int, block_id: int) -> None:
        """Soft delete: activo = 0. No SP exists for this - callers must
        have already checked for an active reservation (see
        app.services.availability_service.AvailabilityService.delete_block)
        since this table has no CHECK against that on its own."""
        cursor = self._conn.cursor()
        try:
            cursor.execute(
                "UPDATE bloques_de_disponibilidad SET activo = 0, actualizado_en = SYSUTCDATETIME() "
                "WHERE dominio_id = ? AND bloque_disponibilidad_id = ?",
                [tenant_id, block_id],
            )
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise
        finally:
            cursor.close()

    def list_public(
        self,
        slug: str,
        *,
        block_date: date | None = None,
        location_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """GET /public/{slug}/availability (WP6). Correction: the WP5 stub
        filtered on `slug`/`fecha_bloque` - v_estado_disponibilidad has
        neither column (the real names are `dominio_slug`/`fecha_de_bloque`,
        docs/sql-signatures.md #2) - and never restricted to free blocks.
        Rewritten to require `bloque_activo = 1 AND reservado = 0` (the WP6
        brief's criterion for "available"), apply the optional date/location
        filters, and alias the view's real columns into the intermediate row
        shape app.mappers.availability_mapper.map_availability_block expects
        (bloque_disponibilidad_id/fecha_bloque/hora_inicio/hora_fin/
        esta_reservado - locked by tests/unit/test_mappers.py). Since this
        query already filters reservado = 0, `esta_reservado` always comes
        back 0/false here, which is exactly the "isReserved siempre false
        aqui" rule from the WP6 brief.
        """
        conditions = ["dominio_slug = ?", "bloque_activo = 1", "reservado = 0"]
        params: list[Any] = [slug]
        if block_date is not None:
            conditions.append("fecha_de_bloque = ?")
            params.append(block_date)
        if location_id is not None:
            conditions.append("localidad_id = ?")
            params.append(location_id)

        sql = (
            "SELECT "
            "bloque_id AS bloque_disponibilidad_id, "
            "CAST(fecha_de_bloque AS DATE) AS fecha_bloque, "
            "CAST(fecha_inicio AS TIME) AS hora_inicio, "
            "CAST(fecha_final AS TIME) AS hora_fin, "
            "reservado AS esta_reservado, "
            "localidad_id "
            "FROM v_estado_disponibilidad "
            "WHERE " + " AND ".join(conditions) + " "
            "ORDER BY fecha_de_bloque, fecha_inicio"
        )
        return query_view(self._conn, sql, params, label="v_estado_disponibilidad")
