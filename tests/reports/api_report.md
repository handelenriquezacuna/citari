# Reporte E2E de API - Citari (Agente 2, Tester funcional de API)

Branch: `test/e2e-backend-validation`. API real en `localhost:8000` (compose
citari), base `citari` en SQL Server via `docker exec db sqlcmd`.

## Comando de re-ejecucion

```bash
apps/api/.venv/bin/pytest tests/e2e -q
```

(equivalente a `make test-e2e` desde la raiz del repo). Todos los archivos
de este agente tienen prefijo `test_api_` y estan marcados `@pytest.mark.e2e`.

## Resultado (DoD)

- Corrida 1: `111 passed in 19.98s` (tambien confirmado en una corrida previa idéntica de `19.97s`).
- Corrida 2 (inmediatamente despues, sin tocar nada): `111 passed in 20.23s`.
- Corrida 3 de control (orden de archivos invertido, para verificar independencia de orden): `111 passed in 20.01s`.
- Conteos de seed verificados iguales a 50 antes y despues de **cada** corrida
  (`dominios`, `reservaciones`, `bloques_de_disponibilidad`, `clientes`,
  `categorias_servicios`, `servicios`, `localidades`, `horarios`,
  `duenos_de_dominios`, `codigos_de_rastreos`, `registros`), y
  `dominios.telefono` del dominio 1 restaurado a su valor de seed
  (`2278-1001`) tras los tests de `PATCH /tenant/current`.
- Total: **111 tests, 111 PASS, 0 FAIL**, 0 skipped.

## Archivos creados

- `tests/e2e/test_api_helpers.py` - helpers compartidos (sin tests propios): `unique_tag()`, `assert_rfc7807()`, `assert_page_envelope()`.
- `tests/e2e/test_api_public_track.py` (13 tests) - grupo 1 (publico/track) + ciclo de re-reserva (grupo 6).
- `tests/e2e/test_api_auth.py` (13 tests) - grupo 2 (auth).
- `tests/e2e/test_api_catalog_crud.py` (17 tests) - grupo 3: service-categories, services, locations, business-hours.
- `tests/e2e/test_api_scheduling_crud.py` (17 tests) - grupo 3: availability-blocks, customers, bookings.
- `tests/e2e/test_api_tenant_isolation.py` (14 tests) - grupo 4 (aislamiento multi-tenant, critico).
- `tests/e2e/test_api_roles_admin.py` (24 tests) - grupo 5 (roles) + admin/tenants + tenant/current + audit-logs + reports.
- `tests/e2e/test_api_soft_delete.py` (5 tests) - grupo 6 (soft delete, resto de la matriz).
- `tests/e2e/test_api_errors_rfc7807.py` (8 tests) - grupo 7 (envelope RFC 7807).

No se modifico `apps/**` ni `tests/e2e/conftest.py`.

## Matriz endpoint x escenario

Catalogo de referencia: `docs/api-handover.md` (60 operaciones, 43 paths).
`GET /health` y `GET /ready` se marcan N/A: ya verificados por la
infraestructura antes de esta corrida (fuera del alcance funcional de
negocio de este agente).

| Endpoint | Escenario(s) | Resultado | Test(s) |
| --- | --- | --- | --- |
| GET /health, GET /ready | liveness/readiness | N/A | verificado por infra previa |
| GET /business-types | listado publico, shape | PASS | test_api_public_track.py::test_business_types_list_shape |
| POST /auth/login | owner ok, superadmin ok, password malo (401 generico), email inexistente (mismo 401 generico), campos faltantes (422) | PASS | test_api_auth.py::test_login_* (6 tests) |
| GET /auth/me | con token owner, con token superadmin, sin token (401), token basura (401) | PASS | test_api_auth.py::test_auth_me_* (4 tests) |
| POST /auth/register-owner | 201 + limpieza, slug duplicado (400), campos faltantes (422), login del owner recien creado (403 por dominio pendiente) | PASS | test_api_auth.py::test_register_owner_* (3 tests) |
| POST /auth/logout | 204 sin body | PASS | test_api_auth.py::test_logout_returns_204 |
| GET/POST /admin/tenants | 401 sin token, owner token 403, paginacion, POST=501 stub | PASS | test_api_roles_admin.py::test_admin_tenants_* |
| GET /admin/tenants/{id} | detalle, 404 inexistente | PASS | test_api_roles_admin.py::test_admin_tenant_get_nonexistent_404, test_admin_tenant_activate_and_suspend_cycle |
| POST /admin/tenants/{id}/activate, /suspend | ciclo pendiente->activo->suspendido (dominio temporal), 404 inexistente | PASS | test_api_roles_admin.py::test_admin_tenant_activate_and_suspend_cycle, test_admin_tenant_activate_nonexistent_404 |
| GET/PATCH /tenant/current | shape, PATCH parcial + restauracion, PATCH con null (COALESCE), superadmin token 403, sin token 401 | PASS | test_api_roles_admin.py::test_tenant_current_* |
| GET /service-categories | crear->leer->actualizar, 422 (2 casos), 401, paginacion, aislamiento (listado + get/patch/delete cruzado), soft delete completo | PASS | test_api_catalog_crud.py::test_service_category_*, test_api_tenant_isolation.py::test_category_*, test_api_soft_delete.py::test_service_category_soft_delete_full_behavior |
| GET/POST/PATCH/DELETE /services | crear->leer->actualizar, 422 (2 casos), categoria inexistente (404), 401, paginacion + filtro categoryId, aislamiento (get/patch/delete cruzado + filtro categoryId ajeno + listado), soft delete (sin isActive expuesto) | PASS | test_api_catalog_crud.py::test_service_*, test_api_tenant_isolation.py::test_service_*, test_api_soft_delete.py::test_service_soft_delete_full_behavior |
| GET/POST/PATCH/DELETE /locations | crear->leer->actualizar, 422 (2 casos), 401, paginacion, aislamiento (get/patch/delete cruzado + listado), soft delete completo | PASS | test_api_catalog_crud.py::test_location_*, test_api_tenant_isolation.py::test_location_*, test_api_soft_delete.py::test_location_soft_delete_full_behavior |
| GET/PUT /business-hours | PUT reemplaza semana completa + GET, 422 (2 casos), localidad inexistente (404), 401 | PASS | test_api_catalog_crud.py::test_business_hours_* |
| GET/POST/DELETE /availability-blocks | crear->leer, 422 (2 casos), rango invalido (400), 401, paginacion, aislamiento (get/delete cruzado + listado + filtro locationId ajeno), soft delete completo (get sigue 200; ya no aparece en el listado, ver defectos corregidos) | PASS | test_api_scheduling_crud.py::test_availability_block_*, test_api_tenant_isolation.py::test_availability_block_*, test_api_soft_delete.py::test_availability_block_* |
| GET/POST/PATCH /customers, GET /customers/{id}/bookings | crear->leer->actualizar, reuso por correo (sp_crear_cliente), 422 (2 casos), 401, paginacion, aislamiento (get/patch/bookings cruzado + listado) | PASS | test_api_scheduling_crud.py::test_customer_*, test_api_tenant_isolation.py::test_customer_* |
| GET/POST /bookings, GET /bookings/{id}, confirm/cancel/complete/reschedule | crear->leer, ciclo confirm->complete->cancel invalido (400), reschedule (libera bloque anterior), sin datos de cliente (400, THROW 50005), 422 (2 casos), 404 inexistente, 401, paginacion, aislamiento (get + las 4 acciones + listado), doble reserva del mismo bloque (409) | PASS | test_api_scheduling_crud.py::test_booking_*, test_api_tenant_isolation.py::test_booking_*, test_api_errors_rfc7807.py::test_409_conflict_envelope_double_booking |
| GET /audit-logs | 401, owner token 403, paginacion + shape, filtro tenantId | PASS | test_api_roles_admin.py::test_audit_logs_* |
| GET /reports/dashboard | shape, 401 | PASS | test_api_roles_admin.py::test_reports_dashboard_shape, test_reports_requires_auth_401 |
| GET /reports/daily-agenda | date requerido (422), shape con date | PASS | test_api_roles_admin.py::test_reports_daily_agenda_* |
| GET /reports/bookings-detail | paginacion | PASS | test_api_roles_admin.py::test_reports_bookings_detail_pagination |
| GET /reports/services-demand | shape | PASS | test_api_roles_admin.py::test_reports_services_demand_shape |
| GET /reports/availability-status | date requerido (422) | PASS | test_api_roles_admin.py::test_reports_availability_status_requires_date_422 |
| GET /public/{slug} | shape, slug inexistente (404) | PASS | test_api_public_track.py::test_public_tenant_* |
| GET /public/{slug}/services | shape, slug inexistente (**200 lista vacia, no 404** - documentado) | PASS | test_api_public_track.py::test_public_services_* |
| GET /public/{slug}/availability | shape, filtrado por fecha, se vacia mientras hay reserva activa, vuelve a aparecer tras cancelar | PASS | test_api_public_track.py::test_public_availability_shape, test_public_book_track_cancel_frees_block_for_rebooking |
| POST /public/{slug}/bookings | 201 (camelCase, trackingCode), 422 payload invalido, slug inexistente (404), doble ciclo reserva->cancelar->re-reservar (clave natural) | PASS | test_api_public_track.py::test_public_booking_*, test_public_book_track_cancel_frees_block_for_rebooking |
| GET /track/{code} | shape, codigo inexistente (404) | PASS | test_api_public_track.py::test_track_get_invalid_code_404, (shape cubierto dentro del ciclo completo) |
| POST /track/{code}/cancel | cancela + libera bloque, codigo inexistente (404) | PASS | test_api_public_track.py::test_track_cancel_invalid_code_404, test_public_book_track_cancel_frees_block_for_rebooking |
| POST /track/{code}/reschedule | mueve la reserva, libera el bloque anterior, codigo inexistente (404) | PASS | test_api_public_track.py::test_track_reschedule_moves_booking_and_frees_old_block, test_track_reschedule_invalid_code_404 |
| Envelope RFC 7807 (transversal) | 400, 401, 403, 404, 409, 422, 501 - shape {type,title,status,detail,traceId}; formato real de 422 (detail = lista de Python stringificada, no JSON) | PASS | test_api_errors_rfc7807.py (8 tests) |

## Resumen por grupo

1. **Publico/track** (grupo 1): 13/13 PASS. Shapes camelCase correctos en
   los 4 endpoints publicos y los 3 de track; 404 consistente para slug y
   codigo inexistentes; 422 para reserva publica invalida.
2. **Auth** (grupo 2): 13/13 PASS. Login, `/auth/me`, `register-owner` +
   limpieza, `logout`. Un hallazgo de comportamiento real (login recien
   registrado -> 403, ver abajo), no un defecto.
3. **CRUD owner** (grupo 3): 34/34 PASS entre `test_api_catalog_crud.py` y
   `test_api_scheduling_crud.py`. Cubre las 7 familias de recursos
   (service-categories, services, locations, business-hours,
   availability-blocks, customers, bookings) con crear->leer->actualizar
   (o transiciones de estado para bookings), 422 representativos con
   `detail` util (nombra el campo faltante), 401 sin token, y envelope de
   paginacion `{items,page,pageSize,total}` verificado con datos propios
   (2 recursos + pageSize=1).
4. **Aislamiento multi-tenant** (grupo 4, critico): 14/14 PASS, **cero
   fugas encontradas**. Todas las combinaciones GET/PATCH/DELETE cruzado
   dan 404 y no modifican el recurso (verificado por SQL); los listados de
   un tenant nunca incluyen recursos del otro; los filtros `categoryId` y
   `locationId` con un id real del otro tenant devuelven `total: 0`, nunca
   los datos ajenos.
5. **Roles** (grupo 5): 4/4 PASS de guardas cruzadas + 20 tests mas de
   admin/tenant-current/audit-logs/reports. `owner` sobre `/admin/tenants`
   y `/audit-logs` -> 403 `"superadmin role required"`; `superadmin` sobre
   `/tenant/current` y `/bookings` -> 403 `"owner role required"`.
6. **Soft delete** (grupo 6): 5/5 PASS + el ciclo completo de re-reserva
   en `test_api_public_track.py`. Comportamiento real documentado por
   recurso (ver tabla de defectos/desviaciones): categories/locations
   exponen `isActive:false` via GET; services no expone `isActive` en
   absoluto; availability-blocks tambien sale correctamente del listado
   del owner tras el DELETE (defecto ya corregido, ver abajo).
7. **RFC 7807** (grupo 7): 8/8 PASS. Envelope consistente en 400/401/403/
   404/409/422/501. El detail del 422 ya es JSON valido (defecto menor
   corregido, ver abajo).

## Defectos encontrados

### 1. [CORREGIDO] `GET /availability-blocks` no filtraba bloques desactivados (soft-deleted) del listado del owner

- **Ubicacion**: `apps/api/app/repositories/availability_repository.py`,
  metodo `AvailabilityRepository.list_owner`.
- **Estado actual**: corregido. El `WHERE` ahora exige `bloque_activo = 1`
  contra `v_estado_disponibilidad`, igual que `ServiceCategoryRepository`,
  `LocationRepository` y `ServiceRepository`. Un bloque desactivado ya no
  aparece en `GET /availability-blocks` para el owner.
- **Test que lo confirma**:
  `test_api_soft_delete.py::test_availability_block_soft_delete_disappears_from_owner_listing`.

### 2. [CORREGIDO] El envelope 422 no era JSON valido dentro de `detail`

- **Ubicacion**: `apps/api/app/main.py`, `validation_error_handler`.
- **Estado actual**: corregido. Ahora usa `json.dumps(exc.errors(),
  default=str)` en vez de `str(exc.errors())`. `detail` sigue siendo un
  string (cumple RFC 7807), pero su contenido es JSON valido: una lista
  de objetos `{"loc": [...], "msg": ..., "type": ...}` que un cliente
  puede parsear con `JSON.parse`/`json.loads` si lo necesita.
- **Test**: `test_api_errors_rfc7807.py::test_422_envelope_shape_differs_from_fastapi_default`
  (confirma explicitamente que `json.loads(detail)` produce esa lista).

### 3. [MENOR] `detail` expone el mensaje crudo del driver ODBC para errores de negocio (THROW de SQL)

- **Ubicacion**: `apps/api/app/errors.py::domain_error_from_pyodbc_message`
  + `apps/api/app/main.py::pyodbc_error_handler` - extraen el numero de
  THROW (50005/50040/etc.) para el status HTTP, pero pasan el mensaje
  *completo* de pyodbc como `detail`, sin recortar el preambulo del
  driver.
- **Repro**: `POST /bookings` sin `customerId` ni `customer` ->
  `400` con `detail`: `"[42000] [Microsoft][ODBC Driver 18 for SQL
  Server][SQL Server]Debe proporcionar cliente_id o los datos completos
  del cliente... (50005) (SQLExecDirectW)"`.
- **Inconsistencia**: los 404 lanzados directamente en Python (patron
  `_require()` de cada router, ej. `NotFoundError(f"La localidad {id} no
  existe...")`) SI llegan limpios, sin ruido de driver. Solo los errores
  que dependen de un `THROW` de la propia stored procedure (400/409 de
  reglas de negocio: 50003, 50004, 50005, 50040, 50041, 50042) arrastran
  el prefijo ODBC.
- **Tests que lo documentan**: `test_api_scheduling_crud.py::test_booking_create_missing_customer_info_400`,
  `test_api_errors_rfc7807.py::test_400_bad_request_envelope`,
  `test_api_errors_rfc7807.py::test_409_conflict_envelope_double_booking`
  (los tres pasan verificando solo el envelope RFC7807 + status, sin
  exigir un `detail` limpio, para no atarse a un mensaje que puede
  cambiar).

No se encontraron defectos de severidad **bloqueante**.

## Comportamiento real documentado (donde difiere de lo esperado por la matriz)

- **Login de un owner recien registrado -> 403, no 200.** `POST
  /auth/register-owner` crea el dominio en estado `pendiente`; el login
  de ese owner con credenciales correctas devuelve `403` con
  `detail` explicando que el dominio esta pendiente de activacion (no es
  un bug: `AuthService._ensure_tenant_active`, comentado explicitamente en
  el codigo). Documentado en `test_api_auth.py::test_register_owner_creates_pending_tenant_and_cleans_up`.
- **PATCH sigue el patron COALESCE-by-omision en todos los recursos**
  (tenant, categorias, servicios, localidades, clientes): un campo
  omitido significa "sin cambio"; enviar explicitamente `null` **tampoco**
  lo borra, tambien se interpreta como "sin cambio" (el repositorio solo
  arma el `SET` para columnas cuyo valor Python no es `None`). Un cliente
  REST que espere que `null` limpie un campo se llevaria una sorpresa.
  Documentado en `test_api_roles_admin.py::test_tenant_current_patch_null_field_means_no_change`.
- **Asimetria 404 vs lista vacia en el storefront publico**: `GET
  /public/{slug}` (detalle del dominio) da `404` si el slug no existe;
  `GET /public/{slug}/services` y `GET /public/{slug}/availability` (listas)
  dan `200` con `[]` para el mismo slug inexistente, en vez de `404`.
  Consistente y bastante razonable (subrecursos de listado no necesitan
  4xx para "nada que listar"), pero es una asimetria real dentro de la
  misma familia de endpoints. Documentado en
  `test_api_public_track.py::test_public_services_unknown_slug_returns_empty_list`.
- **`ServiceResponse` no expone `isActive`** (a diferencia de
  `ServiceCategoryResponse`/`LocationResponse`, que si lo hacen): tras un
  `DELETE /services/{id}`, `GET /services/{id}` sigue en `200` pero no hay
  forma de saber por el JSON si el servicio quedo activo o no (solo
  desapareciendo del listado, o consultando la base). Documentado en
  `test_api_soft_delete.py::test_service_soft_delete_full_behavior`.
- **DELETE en general responde `200 {"status":"deleted"}`, no `204`** (a
  diferencia de `POST /auth/logout`, que si usa `204` sin body). Es
  consistente dentro de las 4 familias con soft delete (categories,
  services, locations, availability-blocks), solo se documenta la
  eleccion de diseño.

## Notas de infraestructura (no son defectos de la API)

- `tests/e2e/conftest.py::run_sql` invoca `sqlcmd` sin la flag `-b`; un
  `THROW`/violacion de constraint dentro de un `DELETE` de limpieza
  **no** hace que el proceso `sqlcmd` termine con codigo de salida
  distinto de cero, por lo que `cleanup_sql` no lanzaria una excepcion de
  Python visible aunque una sentencia de limpieza fallara silenciosamente
  contra una FK. Se descubrio empiricamente durante el desarrollo de este
  agente (un orden de `DELETE` invertido en dos tests dejo filas huerfanas
  sin que ningun test fallara) y se corrigio ajustando el orden de
  registro en `cleanup_sql(...)` (padre-antes-que-hijo en el orden de
  creacion, para que el LIFO del teardown borre hijo-antes-que-padre). No
  se toco `conftest.py` (fuera de mi alcance de escritura); se deja como
  nota para quien mantenga la infraestructura de E2E, por si conviene
  agregar `-b` al comando `sqlcmd` para que las fallas de limpieza sean
  ruidosas en el futuro.

## Verificacion de aislamiento (detalle, grupo 4)

Todas las combinaciones probadas con `owner1_token` (dominio 1,
`barberia-el-colocho`) contra recursos de `owner2_token` (dominio 2,
`salon-elegance`), y viceversa donde aplica:

| Recurso | GET cruzado | PATCH cruzado | DELETE cruzado | Fuga en listado | Fuga por filtro |
| --- | --- | --- | --- | --- | --- |
| service-categories | 404 | 404 + sin cambio en SQL | 404 + `activo` intacto | no | N/A |
| services | 404 | 404 + sin cambio en SQL | 404 + `activo` intacto | no | `categoryId` ajeno -> `total:0` |
| locations | 404 | 404 + sin cambio en SQL | 404 + `activo` intacto | no | N/A |
| availability-blocks | 404 | N/A (sin PATCH) | 404 + `activo` intacto | no | `locationId` ajeno -> `total:0` |
| customers | 404 | 404 + `notas` intacta | N/A (sin DELETE) | no | N/A |
| bookings | 404 | N/A (sin PATCH) | confirm/cancel/complete/reschedule -> 404, estado sigue `pendiente` | no | N/A |

Cero excepciones encontradas.
