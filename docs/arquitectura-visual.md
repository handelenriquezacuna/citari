# Arquitectura visual: como se conecta todo

> Guía rápida para cualquier desarrollador del equipo. Los diagramas se renderizan
> automáticamente en GitHub. Versión detallada de la API en [api-handover.md](api-handover.md).

## 1. El mapa completo en un vistazo

Tres contenedores orquestados por `docker compose up --build`:

```mermaid
flowchart LR
    subgraph Navegador
        B[Browser del usuario]
    end

    subgraph frontend [frontend :3000]
        N[Next.js App Router]
        A[lib/api.ts<br/>apiGet / apiPost / apiPatch / apiDelete]
    end

    subgraph api [api :8000]
        R[Routers /api/v1<br/>solo HTTP]
        S[Services<br/>orquestacion]
        P[Repositories<br/>unico lugar con SQL]
    end

    subgraph db [sqlserver :1433]
        SP[13 stored procedures]
        VW[7 vistas]
        TR[7 triggers<br/>tracking, auditoria,<br/>liberar bloques]
        T[(24 tablas<br/>en español)]
    end

    B --> N
    N --> A
    A -- "JSON camelCase<br/>Authorization: Bearer" --> R
    R --> S --> P
    P -- pyodbc --> SP
    P -- pyodbc --> VW
    SP --> T
    VW --> T
    T -. disparan .-> TR
```

Reglas de oro:

| Regla | Que significa |
|---|---|
| El frontend habla inglés | JSON camelCase (`serviceId`, `firstName`) |
| La base habla español | tablas/columnas (`servicios`, `nombre`) |
| La API traduce | los mappers convierten español -> camelCase, en un solo lugar |
| La lógica vive en SQL | escrituras vía stored procedures, lecturas vía vistas |
| Los triggers hacen la magia | código de rastreo, auditoría y liberación de bloques son AUTOMÁTICOS: nunca los programes en la API ni en el frontend |

## 2. Que puerto es que

| URL | Que hay ahí |
|---|---|
| http://localhost:3000 | Frontend Next.js |
| http://localhost:8000/api/v1/... | API (todos los endpoints) |
| http://localhost:8000/docs | OpenAPI interactivo (probar endpoints sin frontend) |
| localhost:1433 | SQL Server (DBeaver/Azure Data Studio, credenciales en `.env`) |

## 3. JWT en 3 pasos (así funciona el login)

```mermaid
sequenceDiagram
    participant U as Usuario
    participant F as Frontend (lib/api.ts)
    participant API as API (/api/v1)
    participant DB as SQL Server

    Note over U,DB: PASO 1 - Login
    U->>F: escribe email + password
    F->>API: POST /auth/login {email, password}
    API->>DB: busca por correo, verifica bcrypt
    DB-->>API: usuario valido (dueno del dominio 1)
    API-->>F: { accessToken: "eyJ...", user: {...} }
    F->>F: setAuthToken(token)  // localStorage "citari_token"

    Note over U,DB: PASO 2 - Cualquier peticion privada
    F->>API: GET /bookings + header Authorization: Bearer eyJ...
    API->>API: guard CurrentOwner decodifica el token<br/>y extrae tenantId DEL TOKEN (nunca del request)
    API->>DB: v_detalle_reservaciones WHERE dominio_id = 1
    DB-->>API: solo reservas del dominio 1
    API-->>F: { items: [...], total, page, pageSize }

    Note over U,DB: PASO 3 - Logout
    F->>F: clearAuthToken()  // se borra el token y listo
```

Dentro del token viajan tres datos: `sub` (id del usuario), `role` (`owner` o
`superadmin`) y `tenantId` (solo owners). Expira en 60 minutos; al expirar la API
devuelve 401 y el frontend debe redirigir al login.

## 4. Como se usa desde el código del frontend

Todo ya está implementado en `apps/frontend/lib/api.ts`. Solo se usa así:

```ts
// LOGIN (una sola vez): guarda el token
import { apiPost, setAuthToken } from "@/lib/api";
import { endpoints } from "@/lib/endpoints";

const res = await apiPost<LoginResponse>(endpoints.auth.login, {
  email, password, role: "owner",
});
setAuthToken(res.accessToken);   // queda en localStorage "citari_token"
```

```ts
// CUALQUIER LLAMADA PRIVADA despues del login:
// el header Authorization: Bearer se agrega SOLO si hay token guardado
import { apiGet, apiPost } from "@/lib/api";

const page = await apiGet<Page<Booking>>("/bookings?page=1&pageSize=20");
const nuevo = await apiPost<Service>("/services", {
  categoryId: 1, name: "Corte premium", durationMinutes: 45,
});
```

```ts
// ERRORES: la API responde RFC 7807 y api.ts lo convierte en ApiError
try {
  await apiPost("/public/barberia-el-colocho/bookings", body);
} catch (e) {
  if (e instanceof ApiError && e.status === 409) {
    // el bloque ya fue reservado por otra persona
    mostrarMensaje(e.detail);
  }
}
```

```ts
// LOGOUT
import { clearAuthToken } from "@/lib/api";
clearAuthToken();
router.push("/login");
```

## 5. Público vs privado: quien necesita token

```mermaid
flowchart TD
    Q{La pantalla es...}
    Q -->|"reservar o consultar<br/>(cliente final)"| PUB[SIN token<br/>/public/slug/...<br/>/track/codigo/...]
    Q -->|"panel del negocio<br/>(dueno)"| OWN[Token role=owner<br/>/services /bookings /customers<br/>/reports /tenant/current ...]
    Q -->|"administracion de la plataforma"| ADM[Token role=superadmin<br/>/admin/tenants /audit-logs]
```

- El flujo público de reserva nunca pide login: el cliente recibe un **código de
  rastreo** (`CITARI-XXXXXX`, lo genera un trigger) y con el consulta/cancela/reagenda.
- Un owner solo ve SU dominio: el `tenantId` sale del token, por eso es imposible
  pedir datos de otro negocio (la API responde 404).

## 6. Receta: conectar una pantalla nueva en 5 pasos

1. Busca el endpoint en [api-handover.md](api-handover.md) o en http://localhost:8000/docs.
2. Si no existe el tipo TS, agregalo en `apps/frontend/types/` (camelCase, igual al JSON).
3. Llama con los helpers de `lib/api.ts` (`apiGet`/`apiPost`/...) usando la constante de `lib/endpoints.ts`.
4. Si la pantalla es privada, no hagas nada especial: el Bearer se agrega solo si hay token; maneja el 401 redirigiendo a login.
5. Los listados vienen paginados: lee `res.items` y `res.total` (no asumas array plano).

## 7. Levantar todo desde cero (2 comandos)

```bash
cp .env.example .env          # y genera JWT_SECRET: openssl rand -hex 32
bash scripts/setup-db.sh      # SQL Server + 24 tablas + seed + SPs + vistas + triggers
docker compose up --build     # API :8000 + frontend :3000
```

Credenciales de prueba en `database/docs/PASSWORDS.md`. Dominio demo: `barberia-el-colocho`.
