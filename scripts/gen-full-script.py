#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen-full-script.py - Regenera database/scripts/08-full-script.sql por
concatenacion literal de 01-07, con encabezados de seccion. Uso:

    python3 scripts/gen-full-script.py
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "database" / "scripts"
OUTPUT_PATH = SCRIPTS_DIR / "08-full-script.sql"

SOURCES = [
    ("01", "CREACION DE LA BASE DE DATOS", "01-create-database.sql"),
    ("02", "CREACION DE TABLAS Y RELACIONES", "02-create-tables.sql"),
    ("03", "DATOS DE PRUEBA (SEED)", "03-seed-data.sql"),
    ("04", "PROCEDIMIENTOS ALMACENADOS", "04-procedures.sql"),
    ("05", "FUNCIONES", "05-functions.sql"),
    ("06", "VISTAS", "06-views.sql"),
    ("07", "TRIGGERS", "07-triggers.sql"),
]

HEADER = """-- 08-full-script.sql
-- Proyecto: Citari
-- Contenido: script unico que reconstruye la base de datos completa
-- desde cero, en orden: creacion de la base, las 24 tablas y sus
-- relaciones, los datos de prueba (50 registros por tabla), los
-- procedimientos almacenados, las funciones, las vistas y los
-- triggers. Identificadores en espanol, ASCII.
"""


def main():
    parts = [HEADER]
    for num, title, filename in SOURCES:
        src = (SCRIPTS_DIR / filename).read_text(encoding="utf-8-sig")
        parts.append(
            f"\n-- SECCION {num}. {title}\n\n"
            f"{src.rstrip()}\n"
        )
    OUTPUT_PATH.write_text("".join(parts), encoding="utf-8-sig")
    print(f"[gen-full-script] generado {OUTPUT_PATH.relative_to(REPO_ROOT)} ... OK")


if __name__ == "__main__":
    main()
