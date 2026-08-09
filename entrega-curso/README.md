# Entrega del curso: SC-404 Fundamentos de Diseño de Bases de Datos Relacionales

Este documento reúne los entregables de la base de datos, organizados según la rúbrica del
curso, e indica la ubicación de cada uno en el repositorio. No se duplican archivos: cada
entrada enlaza a la fuente correspondiente. Los identificadores de la base de datos están en
español (ASCII); su equivalencia con inglés se encuentra en
[rename-map.csv](../docs/rename-map.csv).

El curso evalúa la base de datos. La API (FastAPI) y el frontend (Next.js) forman parte del
producto desarrollado por el equipo y no constituyen requisitos de la rúbrica; todos los
elementos evaluables se enlazan a continuación.

## II Avance (semana 12)

El II Avance requiere: normalización a la 3FN, creación de la base mediante DDL, tablas
(mínimo 10), 50 registros por tabla, 10 procedimientos almacenados y 5 vistas que integren
datos de múltiples tablas. La entrega actual cumple estos requisitos con margen (véase la
matriz). La convención de nombre del documento de entrega es `GX_SC404_KN_IIAvance`, donde X
corresponde al subgrupo y KN al horario del curso.

## III Entrega y Defensa (semana 14)

La Entrega final y Defensa requiere: al menos 5 funciones, al menos 5 triggers, y un
archivo con todos los scripts de la base para generar tablas, relaciones, procedimientos
y la totalidad de estructuras. La entrega actual cumple estos requisitos con margen (6
funciones, 7 triggers, `08-full-script.sql`). El guion de demostración para la defensa es
[database/scripts/09-defensa.sql](../database/scripts/09-defensa.sql): no crea ni altera
estructuras (todas sus sentencias son `CREATE OR ALTER`, re-ejecutables sin efecto
secundario). Sigue el mismo orden del enunciado del curso (procedimientos, vistas,
funciones, triggers) y tiene tres partes: visión general de la base completa, el código
de los 2 objetos más elaborados de cada categoría con su explicación, y una demostración
en vivo (reservar, consultar detalle, reagendar y comprobar que el sistema rechaza una
doble reserva).

> Nota de alineación (2026-08-08): la base de datos se actualizó de 15 a 24 tablas para
> quedar alineada con la normalización a 3FN presentada en el Avance #2 (correo y
> teléfono como atributos multivaluados en tablas propias por entidad, y una tabla
> `direcciones` para la división territorial de cada localidad). El detalle de las 9
> tablas nuevas está en [database/diagrams/MODELO-RELACIONAL.md](../database/diagrams/MODELO-RELACIONAL.md).
> Los prefijos de triggers y vistas también se alinearon a la convención del profesor
> (`tr_`/`v_` en vez de `trg_`/`vw_`). `apps/api` y `apps/frontend` (fuera del alcance de
> la rúbrica del curso, que evalúa únicamente la base de datos) también se actualizaron
> al esquema de 24 tablas y quedaron verificados funcionando end-to-end.

## Matriz de requisitos y evidencia

| # | Requisito | Mínimo | Entregado | Evidencia |
|---|-----------|--------|-----------|-----------|
| 1 | Propósito de la base de datos | N/A | Cumple | [docs/overview.md](../docs/overview.md) |
| 2 | Requerimientos definidos | N/A | Cumple | [docs/overview.md](../docs/overview.md), [docs/domain-questions.md](../docs/domain-questions.md) |
| 3 | Diagrama Entidad-Relación | N/A | Cumple | [infra/MultiTenantBookingManager.drawio](../infra/MultiTenantBookingManager.drawio) |
| 4 | Diagrama Relacional | N/A | Cumple | [database/diagrams/MODELO-RELACIONAL.md](../database/diagrams/MODELO-RELACIONAL.md) |
| 5 | Normalización a la 3FN | 3FN | Cumple | [database/diagrams/NormalizacionProyecto.xlsx](../database/diagrams/NormalizacionProyecto.xlsx), [docs/database-and-sql.md](../docs/database-and-sql.md) |
| 6 | Creación de la base mediante DDL | N/A | Cumple | [database/scripts/01-create-database.sql](../database/scripts/01-create-database.sql) |
| 7 | Tablas | ≥ 10 | 24 | [database/scripts/02-create-tables.sql](../database/scripts/02-create-tables.sql) |
| 8 | Registros por tabla | ≥ 50 | 50 por tabla | [database/scripts/03-seed-data.sql](../database/scripts/03-seed-data.sql); generador: [scripts/gen-seed.py](../scripts/gen-seed.py) |
| 9 | Procedimientos almacenados | ≥ 10 | 13 | [database/scripts/04-procedures.sql](../database/scripts/04-procedures.sql) |
| 10 | Vistas multi-tabla | ≥ 5 | 7 | [database/scripts/06-views.sql](../database/scripts/06-views.sql) |
| 11 | Funciones | ≥ 5 | 6 | [database/scripts/05-functions.sql](../database/scripts/05-functions.sql) |
| 12 | Triggers | ≥ 5 | 7 | [database/scripts/07-triggers.sql](../database/scripts/07-triggers.sql) |
| 13 | Script único con todas las estructuras | N/A | Cumple | [database/scripts/08-full-script.sql](../database/scripts/08-full-script.sql) |

## Referencias de apoyo

- Firmas de procedimientos, funciones, vistas y triggers, y códigos THROW: [docs/sql-signatures.md](../docs/sql-signatures.md)
- Base de datos construida (as-built), diagrama ER y ciclo de vida de una reserva: [docs/database-and-sql-implementado.md](../docs/database-and-sql-implementado.md)
- Cronograma, guion de defensa y matriz de requisitos R1-R6: [docs/plan-and-delivery.md](../docs/plan-and-delivery.md)
- Credenciales de desarrollo (seed): [database/docs/PASSWORDS.md](../database/docs/PASSWORDS.md)

## Montaje y verificación de la base de datos

Montaje de la base de datos (ejecuta los scripts 01-07 en orden):

```powershell
# Windows (PowerShell): principal
.\scripts\setup-db.ps1
```

```bash
# macOS / Linux
bash scripts/setup-db.sh
```

Verificación de los conteos por tabla y de la matriz de requisitos R3-R6:

```
sqlcmd -S localhost -U sa -P "<password>" -C -i scripts/check-all.sql
```

Prueba de humo del ciclo de vida completo de una reservación (12 casos, incluye 4
triggers):

```
sqlcmd -S localhost -U sa -P "<password>" -C -i scripts/smoke-db.sql
```

Auditoría exhaustiva que ejercita, sin excepción, cada uno de los 24 objetos
programables (los 13 procedimientos, las 6 funciones, las 7 vistas y los 7 triggers):

```
sqlcmd -S localhost -U sa -P "<password>" -C -i scripts/full-object-audit.sql
```

Como alternativa, el archivo [database/scripts/08-full-script.sql](../database/scripts/08-full-script.sql)
es equivalente a ejecutar los scripts 01-07 sobre un servidor limpio; se regenera con
`python3 scripts/gen-full-script.py` cada vez que cambie alguno de los scripts fuente.

## Nota sobre los catálogos de estado

Las tablas de catálogo `estados_dominios` y `estados_reservaciones`, así como la tabla
`superadmins`, alcanzan el mínimo de 50 registros mediante filas de relleno identificadas. El
requisito establece "50 registros por tabla según el objetivo o función de cada tabla", por lo
que un catálogo compuesto por pocos estados admite dicho mínimo. Esta decisión se documenta
para su justificación durante la defensa.
