"""Row from `dominios` -> Tenant contract.

Matches apps/frontend/types/tenant.ts:
    { tenantId, slug, name, description, publicMessage }

WP7a addition: GET/PATCH /tenant/current select the full `dominios` row
(including correo/telefono/logo_url), unlike the WP6 public endpoint's
narrower SELECT - when those columns are present in the input row they are
surfaced too, as email/phone/logoUrl. This is intentionally conditional (only
added when the key is present) so the WP6 shape - and
tests/unit/test_mappers.py::test_map_tenant, which asserts exact dict
equality on a row without those keys - keeps passing unmodified.

Schema-migration note: correo/telefono no longer live on `dominios` itself
(moved to dominios_correos/dominios_telefonos, 1:N); the repository queries
that need them now resolve them via an OUTER APPLY and alias the result back
onto the row AS correo/AS telefono (see
app.repositories.tenant_repository.get_by_id/get_by_slug/list_tenants), so
the "is the key present on this row" check below still means exactly what it
always did - whether *this* query bothered to select the column, not
whether the row was fully hydrated. get_active_by_slug (the WP6 public path)
deliberately still doesn't select them at all, so this stays conditional
rather than becoming an unconditional `row["correo"]`.

WP7b addition: GET /admin/tenants and GET /admin/tenants/{id} join
estados_dominios and pass through `estado_nombre` (see
app.repositories.tenant_repository.get_by_id/list_tenants) - surfaced here as
`status`, same conditional-field technique.
"""

from __future__ import annotations

from typing import Any


def map_tenant(row: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "tenant_id": row["dominio_id"],
        "slug": row["slug"],
        "name": row["nombre"],
        "description": row.get("descripcion"),
        "public_message": row.get("mensaje_publico"),
    }
    if "correo" in row:
        result["email"] = row["correo"]
    if "telefono" in row:
        result["phone"] = row["telefono"]
    if "logo_url" in row:
        result["logo_url"] = row["logo_url"]
    if "estado_nombre" in row:
        result["status"] = row["estado_nombre"]
    return result
