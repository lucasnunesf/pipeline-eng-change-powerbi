"""
Run the .sql files against the database.

The files in sql/ hold the lookup tables and the business rules. This script
just executes them, in filename order, which is why they are numbered.

Running it again is safe: every statement drops what it is about to create.

Run:
    python src/build_sql.py
"""

import sqlite3
from pathlib import Path

DATABASE = "data/eci.db"
SQL_DIR = Path("sql")


def main():
    files = sorted(SQL_DIR.glob("*.sql"))
    if not files:
        raise SystemExit(f"No .sql files found in {SQL_DIR}/")

    connection = sqlite3.connect(DATABASE)

    for path in files:
        script = path.read_text(encoding="utf-8")
        # executescript runs every statement in the file, separated by ';'.
        connection.executescript(script)
        print(f"ran {path.name}")

    connection.commit()

    # List what the database holds now, so the result is visible.
    rows = connection.execute(
        "SELECT type, name FROM sqlite_master "
        "WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name"
    ).fetchall()

    print("\nDatabase now contains:")
    for kind, name in rows:
        count = connection.execute(f"SELECT COUNT(*) FROM \"{name}\"").fetchone()[0]
        print(f"  {kind:5} {name:24} {count:>6,} rows")

    connection.close()


if __name__ == "__main__":
    main()
