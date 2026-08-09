from __future__ import annotations

from typing import Any

import pyodbc

from app.db import query_view


class LocationRepository:
    """localidades. No stored procedure exists for this table - every write
    here is a direct parameterized statement, per the WP7b brief."""

    def __init__(self, conn: pyodbc.Connection) -> None:
        self._conn = conn

    # direcciones is a reutilizable catalog (provincia/canton/distrito/
    # codigo_postal) but, per the WP7c decision, localidades treats it as
    # append-only: every create/address-update INSERTs a fresh direcciones
    # row and points localidades.direccion_id at it. No matching/dedup.
    _SELECT_SQL = (
        "SELECT l.*, d.provincia, d.canton, d.distrito, d.codigo_postal, lt.telefono "
        "FROM localidades l "
        "JOIN direcciones d ON d.direccion_id = l.direccion_id "
        "OUTER APPLY ("
        "    SELECT TOP 1 t.telefono "
        "    FROM localidades_telefonos t "
        "    WHERE t.localidad_id = l.localidad_id "
        "    ORDER BY t.localidad_telefono_id"
        ") lt "
    )

    def create(
        self,
        *,
        tenant_id: int,
        name: str,
        provincia: str,
        canton: str,
        distrito: str,
        codigo_postal: str,
        phone: str | None,
        is_main: bool,
    ) -> dict[str, Any]:
        """WP7b correction: the real column is `principal` (the WP5 stub
        wrote `es_principal`, which does not exist - see
        docs/rename-map.csv).

        WP7c: `localidades` no longer has `direccion`/`telefono` columns -
        the territorial division lives in the `direcciones` catalog
        (direccion_id FK) and the phone in the 1:N `localidades_telefonos`
        table. Mirrors the insert-parent/get-id/insert-children pattern used
        by sp_crear_dueno/sp_crear_cliente in database/scripts/04-procedures.sql,
        translated to pyodbc since no stored procedure exists for this table.
        """
        try:
            direccion_rows = query_view(
                self._conn,
                "INSERT INTO direcciones (provincia, canton, distrito, codigo_postal) "
                "OUTPUT INSERTED.direccion_id VALUES (?, ?, ?, ?)",
                [provincia, canton, distrito, codigo_postal],
            )
            direccion_id = direccion_rows[0]["direccion_id"]

            location_rows = query_view(
                self._conn,
                "INSERT INTO localidades (dominio_id, direccion_id, nombre, principal) "
                "OUTPUT INSERTED.* VALUES (?, ?, ?, ?)",
                [tenant_id, direccion_id, name, is_main],
            )
            location = location_rows[0] if location_rows else {}
            location_id = location.get("localidad_id")

            if phone and location_id is not None:
                query_view(
                    self._conn,
                    "INSERT INTO localidades_telefonos (localidad_id, telefono) VALUES (?, ?)",
                    [location_id, phone],
                )

            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise

        if location_id is None:
            return {}
        return self.get_by_id(tenant_id, location_id) or {}

    def get_by_id(self, tenant_id: int, location_id: int) -> dict[str, Any] | None:
        sql = self._SELECT_SQL + "WHERE l.dominio_id = ? AND l.localidad_id = ?"
        rows = query_view(self._conn, sql, [tenant_id, location_id])
        return rows[0] if rows else None

    def list_by_tenant(
        self, tenant_id: int, *, page: int, page_size: int
    ) -> tuple[list[dict[str, Any]], int]:
        """WP7b correction: the real active-flag column is `activo` (the WP5
        stub filtered on the non-existent `esta_activo`)."""
        total_rows = query_view(
            self._conn,
            "SELECT COUNT(*) AS total FROM localidades WHERE dominio_id = ? AND activo = 1",
            [tenant_id],
        )
        total = int(total_rows[0]["total"]) if total_rows else 0
        sql = (
            self._SELECT_SQL + "WHERE l.dominio_id = ? AND l.activo = 1 "
            "ORDER BY l.nombre, l.localidad_id OFFSET ? ROWS FETCH NEXT ? ROWS ONLY"
        )
        rows = query_view(self._conn, sql, [tenant_id, (page - 1) * page_size, page_size])
        return rows, total

    def update(
        self,
        tenant_id: int,
        location_id: int,
        *,
        name: str | None = None,
        provincia: str | None = None,
        canton: str | None = None,
        distrito: str | None = None,
        codigo_postal: str | None = None,
        phone: str | None = None,
        is_main: bool | None = None,
        is_active: bool | None = None,
    ) -> dict[str, Any] | None:
        """PATCH /locations/{id} and the soft DELETE (is_active=False) both
        go through this dynamic UPDATE - same COALESCE-by-omission pattern
        as app.repositories.tenant_repository.update_tenant.

        WP7c: address fields (provincia/canton/distrito/codigo_postal) no
        longer live on `localidades` directly. `direcciones` is append-only
        (per the WP7c decision - no dedup), so any address-field change
        INSERTs a brand-new `direcciones` row (merged with the current
        values for the fields left unset) and repoints
        `localidades.direccion_id` at it. Phone is upserted into
        `localidades_telefonos`: the oldest existing row is updated in
        place, else one is inserted.
        """
        columns: dict[str, Any] = {}
        if name is not None:
            columns["nombre"] = name
        if is_main is not None:
            columns["principal"] = is_main
        if is_active is not None:
            columns["activo"] = is_active

        address_changed = any(
            value is not None for value in (provincia, canton, distrito, codigo_postal)
        )

        try:
            if address_changed:
                current = self.get_by_id(tenant_id, location_id)
                if current is None:
                    return None
                direccion_rows = query_view(
                    self._conn,
                    "INSERT INTO direcciones (provincia, canton, distrito, codigo_postal) "
                    "OUTPUT INSERTED.direccion_id VALUES (?, ?, ?, ?)",
                    [
                        provincia if provincia is not None else current["provincia"],
                        canton if canton is not None else current["canton"],
                        distrito if distrito is not None else current["distrito"],
                        codigo_postal if codigo_postal is not None else current["codigo_postal"],
                    ],
                )
                columns["direccion_id"] = direccion_rows[0]["direccion_id"]

            if columns:
                set_clause = ", ".join(f"{column} = ?" for column in columns)
                sql = (
                    f"UPDATE localidades SET {set_clause}, actualizado_en = SYSUTCDATETIME() "
                    "WHERE dominio_id = ? AND localidad_id = ?"
                )
                cursor = self._conn.cursor()
                cursor.execute(sql, [*columns.values(), tenant_id, location_id])
                cursor.close()

            if phone is not None:
                self._upsert_phone(location_id, phone)

            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise

        return self.get_by_id(tenant_id, location_id)

    def _upsert_phone(self, location_id: int, phone: str) -> None:
        """Same 1:N upsert shape other repositories use for their own
        *_telefonos child tables: update the oldest existing row if one
        exists, else insert a new one."""
        existing = query_view(
            self._conn,
            "SELECT TOP 1 localidad_telefono_id FROM localidades_telefonos "
            "WHERE localidad_id = ? ORDER BY localidad_telefono_id",
            [location_id],
        )
        if existing:
            query_view(
                self._conn,
                "UPDATE localidades_telefonos SET telefono = ? WHERE localidad_telefono_id = ?",
                [phone, existing[0]["localidad_telefono_id"]],
            )
        else:
            query_view(
                self._conn,
                "INSERT INTO localidades_telefonos (localidad_id, telefono) VALUES (?, ?)",
                [location_id, phone],
            )
