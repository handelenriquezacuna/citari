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

HEADER = """﻿-- ============================================================
-- 08-full-script.sql
-- Proyecto: Citari - Citari
-- Contenido: script unico y equivalente a correr, en orden y sobre
-- un servidor limpio, 01-create-database.sql + 02-create-tables.sql
-- + 03-seed-data.sql + 04-procedures.sql + 05-functions.sql +
-- 06-views.sql + 07-triggers.sql. Generado por concatenacion; no
-- editar secciones individuales aqui, editar el archivo fuente
-- correspondiente en database/scripts/ y regenerar este archivo.
-- Identificadores en espanol, ASCII. Ver docs/rename-map.csv para
-- la equivalencia con los nombres en ingles y docs/sql-signatures.md
-- para la referencia compacta de firmas (SP/vistas/funciones/THROW).
-- ============================================================
"""


def main():
    parts = [HEADER]
    for num, title, filename in SOURCES:
        src = (SCRIPTS_DIR / filename).read_text(encoding="utf-8-sig")
        parts.append(
            f"\n-- ============================================================\n"
            f"-- SECCION {num}. {title}\n"
            f"-- Fuente: database/scripts/{filename}\n"
            f"-- ============================================================\n\n"
            f"{src.rstrip()}\n"
        )
    OUTPUT_PATH.write_text("".join(parts), encoding="utf-8-sig")
    print(f"[gen-full-script] generado {OUTPUT_PATH.relative_to(REPO_ROOT)} ... OK")


if __name__ == "__main__":
    main()
