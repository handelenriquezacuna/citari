"""Location schemas (localidades). No dedicated frontend/types file yet.

WP7c: `localidades` no longer has a free-text `direccion` column - the
territorial division (provincia/canton/distrito/codigo_postal) lives in the
`direcciones` catalog, so the flat `address: str` field is replaced with
those four structured fields (wire format: camelCase via CamelModel, e.g.
`codigoPostal`)."""

from __future__ import annotations

from app.schemas.common import CamelModel


class LocationResponse(CamelModel):
    location_id: int
    name: str
    provincia: str
    canton: str
    distrito: str
    codigo_postal: str
    phone: str | None = None
    is_main: bool = False
    is_active: bool = True


class LocationCreateRequest(CamelModel):
    name: str
    provincia: str
    canton: str
    distrito: str
    codigo_postal: str
    phone: str | None = None
    is_main: bool = False


class LocationUpdateRequest(CamelModel):
    name: str | None = None
    provincia: str | None = None
    canton: str | None = None
    distrito: str | None = None
    codigo_postal: str | None = None
    phone: str | None = None
    is_main: bool | None = None
    is_active: bool | None = None
