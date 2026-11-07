"""Tiny idempotent schema upgrades for columns added after first deploy (no Alembic yet).

create_all never alters existing tables. Each upgrade first checks whether it is needed, so a normal
startup issues no locking DDL, and any real ALTER gives up after a few seconds rather than hanging
behind a long transaction.
"""
from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

# (table, column, DDL type clause)
COLUMN_UPGRADES = [
    ("invoices", "is_disputed", "BOOLEAN NOT NULL DEFAULT FALSE"),
    ("users", "clerk_user_id", "VARCHAR(64)"),
]
INDEX_UPGRADES = [
    ("ux_users_clerk_user_id", "users", "clerk_user_id"),
]


def apply_schema_upgrades(engine: Engine) -> None:
    insp = inspect(engine)
    for table, column, ddl in COLUMN_UPGRADES:
        if not insp.has_table(table):
            continue
        if column in {c["name"] for c in insp.get_columns(table)}:
            continue
        with engine.begin() as conn:
            conn.execute(text("SET LOCAL lock_timeout = '5s'"))
            conn.execute(text(f'ALTER TABLE "{table}" ADD COLUMN IF NOT EXISTS "{column}" {ddl}'))

    for name, table, column in INDEX_UPGRADES:
        if not insp.has_table(table):
            continue
        covered = any(column in i["column_names"] for i in insp.get_indexes(table)) or any(
            column in c["column_names"] for c in insp.get_unique_constraints(table)
        )
        if covered:  # fresh databases get a unique constraint from create_all
            continue
        with engine.begin() as conn:
            conn.execute(text("SET LOCAL lock_timeout = '5s'"))
            conn.execute(text(f'CREATE UNIQUE INDEX IF NOT EXISTS "{name}" ON "{table}" ("{column}")'))
