from __future__ import annotations

from typing import Any

import pyodbc

from app.db import query_view


class SuperadminRepository:
    """superadmins."""

    def __init__(self, conn: pyodbc.Connection) -> None:
        self._conn = conn

    def get_by_email(self, email: str) -> dict[str, Any] | None:
        """WP7a correction: the column is `correo` (rename-map row 20), not
        `email` - the WP5 stub's filter never matched any real row.

        Schema migration correction: `correo` was removed from `superadmins`
        and normalized into the 1:N child table `superadmins_correos` (see
        database/scripts/06-views.sql's OUTER APPLY pattern, reused here) -
        so the email lookup itself must now JOIN against that child table
        instead of filtering `superadmins.correo` directly. `sc.correo` is
        re-selected AS `correo` so the row shape app.mappers.user_mapper.
        map_superadmin_user expects (`row["correo"]`) still holds."""
        sql = (
            "SELECT s.*, sc.correo AS correo FROM superadmins s "
            "JOIN superadmins_correos sc ON sc.superadmin_id = s.superadmin_id "
            "AND sc.correo = ?"
        )
        rows = query_view(self._conn, sql, [email], label="superadmins")
        return rows[0] if rows else None

    def get_by_id(self, superadmin_id: int) -> dict[str, Any] | None:
        """Schema migration correction: `correo` no longer lives on
        `superadmins` - it must be resolved from `superadmins_correos` (1:N)
        the same way database/scripts/06-views.sql resolves `clientes_correos`
        for v_detalle_reservaciones: take the first-registered row as the
        canonical email. Aliased AS `correo` so the row shape app.mappers.
        user_mapper.map_superadmin_user expects (`row["correo"]`) still
        holds."""
        sql = (
            "SELECT s.*, sco.correo AS correo "
            "FROM superadmins s "
            "OUTER APPLY ("
            "SELECT TOP 1 sc.correo FROM superadmins_correos sc "
            "WHERE sc.superadmin_id = s.superadmin_id "
            "ORDER BY sc.superadmin_correo_id"
            ") sco "
            "WHERE s.superadmin_id = ?"
        )
        rows = query_view(self._conn, sql, [superadmin_id], label="superadmins")
        return rows[0] if rows else None
