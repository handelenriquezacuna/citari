"""Row from `localidades` (joined to `direcciones`, OUTER APPLY'd against
`localidades_telefonos`) -> Location contract.

No dedicated frontend/types file yet (see app.schemas.location). WP7c: the
old free-text `direccion`/`telefono` columns are gone from `localidades`.
LocationRepository's SELECT (get_by_id/list_by_tenant) now JOINs
`direcciones` (via direccion_id) for provincia/canton/distrito/
codigo_postal, and OUTER APPLYs `localidades_telefonos` for telefono - see
that repository's `_SELECT_SQL`.
"""

from __future__ import annotations

from typing import Any


def map_location(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "location_id": row["localidad_id"],
        "name": row["nombre"],
        "provincia": row["provincia"],
        "canton": row["canton"],
        "distrito": row["distrito"],
        "codigo_postal": row["codigo_postal"],
        "phone": row.get("telefono"),
        "is_main": bool(row["principal"]),
        "is_active": bool(row["activo"]),
    }
