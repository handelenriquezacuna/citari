from __future__ import annotations

from typing import Any

import pyodbc

from app.db import exec_sp, exec_sp_output, query_view


class ServiceRepository:
    """servicios."""

    def __init__(self, conn: pyodbc.Connection) -> None:
        self._conn = conn

    def create(
        self,
        *,
        tenant_id: int,
        category_id: int,
        name: str,
        description: str | None,
        duration_minutes: int,
        price: float | None,
        show_price: bool,
    ) -> dict[str, Any]:
        """WP7b correction: sp_crear_servicio's category parameter is
        `@categoria_id` (the WP5 stub sent the non-existent
        `categoria_servicio_id`), and the SP reports the new id via
        `@servicio_id OUTPUT` only - no final SELECT (docs/sql-signatures.md
        #5) - so this must go through exec_sp_output and then re-read the
        full row, like every other OUTPUT-param SP in this codebase."""
        service_id = exec_sp_output(
            self._conn,
            "sp_crear_servicio",
            {
                "dominio_id": tenant_id,
                "categoria_id": category_id,
                "nombre": name,
                "descripcion": description,
                "duracion_minutos": duration_minutes,
                "precio": price,
                "mostrar_precio": show_price,
            },
            output_param="servicio_id",
        )
        return self.get_by_id(tenant_id, service_id) or {}

    def update(
        self,
        tenant_id: int,
        service_id: int,
        *,
        category_id: int | None = None,
        name: str | None = None,
        description: str | None = None,
        duration_minutes: int | None = None,
        price: float | None = None,
        show_price: bool | None = None,
        is_active: bool | None = None,
    ) -> dict[str, Any] | None:
        """PATCH /services/{id} and the soft DELETE (is_active=False) both go
        through sp_actualizar_servicio (COALESCE pattern - a NULL/omitted
        parameter means "no change"). WP7b correction: that SP has neither a
        final SELECT nor an OUTPUT parameter (docs/sql-signatures.md #6), so
        this re-reads the row afterwards instead of trusting exec_sp's
        (always empty) return value."""
        params: dict[str, Any] = {"servicio_id": service_id, "dominio_id": tenant_id}
        if category_id is not None:
            params["categoria_id"] = category_id
        if name is not None:
            params["nombre"] = name
        if description is not None:
            params["descripcion"] = description
        if duration_minutes is not None:
            params["duracion_minutos"] = duration_minutes
        if price is not None:
            params["precio"] = price
        if show_price is not None:
            params["mostrar_precio"] = show_price
        if is_active is not None:
            params["activo"] = is_active

        exec_sp(self._conn, "sp_actualizar_servicio", params)
        return self.get_by_id(tenant_id, service_id)

    def get_by_id(self, tenant_id: int, service_id: int) -> dict[str, Any] | None:
        sql = "SELECT * FROM servicios WHERE dominio_id = ? AND servicio_id = ?"
        rows = query_view(self._conn, sql, [tenant_id, service_id])
        return rows[0] if rows else None

    def list_by_tenant(
        self, tenant_id: int, *, page: int, page_size: int, category_id: int | None = None
    ) -> tuple[list[dict[str, Any]], int]:
        """WP7b correction: the real active-flag column is `activo` (the WP5
        stub filtered on the non-existent `esta_activo`)."""
        conditions = ["dominio_id = ?", "activo = 1"]
        params: list[Any] = [tenant_id]
        if category_id is not None:
            conditions.append("categoria_id = ?")
            params.append(category_id)
        where = " AND ".join(conditions)

        total_rows = query_view(
            self._conn, f"SELECT COUNT(*) AS total FROM servicios WHERE {where}", params
        )
        total = int(total_rows[0]["total"]) if total_rows else 0

        sql = (
            f"SELECT * FROM servicios WHERE {where} ORDER BY nombre, servicio_id "
            "OFFSET ? ROWS FETCH NEXT ? ROWS ONLY"
        )
        rows = query_view(self._conn, sql, [*params, (page - 1) * page_size, page_size])
        return rows, total

    def list_public_by_slug(self, slug: str) -> list[dict[str, Any]]:
        """GET /public/{slug}/services (WP6). Correction: the WP5 stub
        filtered on `slug`, but v_servicios_publicos exposes the tenant
        slug as `dominio_slug` (docs/sql-signatures.md #2) - `slug` does not
        exist on that view, so this was a guaranteed runtime error. `SELECT
        *` already matches app.mappers.service_mapper.map_service's expected
        keys 1:1 (servicio_id/nombre/descripcion/duracion_minutos/precio/
        mostrar_precio), so no aliasing is needed here."""
        sql = "SELECT * FROM v_servicios_publicos WHERE dominio_slug = ? ORDER BY nombre"
        return query_view(self._conn, sql, [slug], label="v_servicios_publicos")
