from __future__ import annotations

from typing import Any

import pyodbc

from app.db import exec_sp_output, query_view


class TenantOwnerRepository:
    """duenos_de_dominios."""

    def __init__(self, conn: pyodbc.Connection) -> None:
        self._conn = conn

    def create_owner(
        self,
        *,
        tenant_id: int,
        first_name: str,
        last_name_1: str,
        last_name_2: str | None,
        email: str,
        password_hash: str,
        phone: str | None,
    ) -> int:
        """WP7a correction: sp_crear_dueno reports the new id via
        `@dueno_id OUTPUT` only (no final SELECT - docs/sql-signatures.md
        #2), so this must go through exec_sp_output (plain exec_sp has no
        way to read an OUTPUT param back). The WP6 stub also used
        non-existent parameter names (`nombre_completo`/`email`/
        `hash_contrasena`) instead of the real
        nombre/apellido_1/apellido_2/correo/contrasena_encriptada/telefono.
        Returns the new dueno_id.
        """
        return exec_sp_output(
            self._conn,
            "sp_crear_dueno",
            {
                "dominio_id": tenant_id,
                "nombre": first_name,
                "apellido_1": last_name_1,
                "apellido_2": last_name_2,
                "correo": email,
                "contrasena_encriptada": password_hash,
                "telefono": phone,
            },
            output_param="dueno_id",
        )

    def get_by_email(self, email: str) -> dict[str, Any] | None:
        """Schema migration correction: `correo` was removed from
        `duenos_de_dominios` and normalized into the 1:N child table
        `duenos_de_dominios_correos` (see database/scripts/06-views.sql's
        OUTER APPLY pattern, reused here) - so the email lookup itself must
        now JOIN against that child table instead of filtering
        `duenos_de_dominios.correo` directly. `dc.correo` is re-selected AS
        `correo` so the row shape app.mappers.user_mapper.map_owner_user
        expects (`row["correo"]`) still holds. (Owner phone is not needed
        here: app.mappers.user_mapper.map_owner_user never reads
        `row["telefono"]`, and app.schemas.auth.UserResponse has no phone
        field.)"""
        sql = (
            "SELECT d.*, dc.correo AS correo FROM duenos_de_dominios d "
            "JOIN duenos_de_dominios_correos dc ON dc.dueno_id = d.dueno_id "
            "AND dc.correo = ?"
        )
        rows = query_view(self._conn, sql, [email], label="duenos_de_dominios")
        return rows[0] if rows else None

    def get_by_id(self, owner_id: int) -> dict[str, Any] | None:
        """Schema migration correction: `correo` no longer lives on
        `duenos_de_dominios` - it must be resolved from
        `duenos_de_dominios_correos` (1:N) the same way
        database/scripts/06-views.sql resolves `clientes_correos` for
        v_detalle_reservaciones: take the first-registered row as the
        canonical email. Aliased AS `correo` so the row shape
        app.mappers.user_mapper.map_owner_user expects (`row["correo"]`)
        still holds."""
        sql = (
            "SELECT d.*, dco.correo AS correo "
            "FROM duenos_de_dominios d "
            "OUTER APPLY ("
            "SELECT TOP 1 dc.correo FROM duenos_de_dominios_correos dc "
            "WHERE dc.dueno_id = d.dueno_id "
            "ORDER BY dc.dueno_correo_id"
            ") dco "
            "WHERE d.dueno_id = ?"
        )
        rows = query_view(self._conn, sql, [owner_id], label="duenos_de_dominios")
        return rows[0] if rows else None
