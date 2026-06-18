#!/usr/bin/env python3
import argparse
import os
import sys
from pathlib import Path

import psycopg2

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply ORDER database migrations")
    parser.add_argument("--dry-run", action="store_true", help="List pending migrations without applying them")
    args = parser.parse_args()

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("DATABASE_URL is required", file=sys.stderr)
        return 2

    migrations = sorted(MIGRATIONS_DIR.glob("*.sql"))
    with psycopg2.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """CREATE TABLE IF NOT EXISTS schema_migrations (
                       version varchar(255) PRIMARY KEY,
                       applied_at timestamptz NOT NULL DEFAULT now()
                   )"""
            )
            cur.execute("SELECT version FROM schema_migrations")
            applied = {row[0] for row in cur.fetchall()}
            pending = [path for path in migrations if path.name not in applied]

            for path in pending:
                print(f"pending: {path.name}")
                if args.dry_run:
                    continue
                cur.execute("SELECT pg_advisory_xact_lock(hashtext('order-schema-migrations'))")
                cur.execute(path.read_text(encoding="utf-8"))
                cur.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (path.name,))
                print(f"applied: {path.name}")

    if not pending:
        print("database is up to date")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
