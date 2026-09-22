"""
Load the raw export into the database, exactly as it came.

Nothing is cleaned here on purpose. This is the landing zone: if a rule turns
out to be wrong later, it can be fixed and re-run against this table without
downloading the export again.

Run:
    python src/load_raw.py
"""

import sqlite3
from datetime import datetime

import pandas as pd

EXCEL_FILE = "data/raw/eci_export.xlsx"
DATABASE = "data/eci.db"
TABLE = "stg_eci_export"


def load():
    # Read every column as text. The export mixes real dates with dates written
    # as text in the same column, and letting pandas guess gives a different
    # answer depending on which rows happen to be in the file. Parsing happens
    # later, once, where it can be tested.
    df = pd.read_excel(EXCEL_FILE, dtype=str)
    print(f"Read {len(df):,} rows from {EXCEL_FILE}")

    # Drop rows that are completely empty - the export ends with a few of them.
    df = df.dropna(how="all")
    print(f"{len(df):,} rows left after dropping empty ones")

    # Provenance: which file this row came from, and when it was loaded.
    # Without this, a wrong number in the report cannot be traced back.
    df["_source_file"] = EXCEL_FILE.split("/")[-1]
    df["_loaded_at"] = datetime.now().isoformat(timespec="seconds")

    # sqlite3 ships with Python - nothing to install.
    # Connecting to a file that does not exist creates it.
    connection = sqlite3.connect(DATABASE)

    # if_exists="replace" drops the table and writes it again, so re-running
    # this script never piles the same rows on top of each other.
    df.to_sql(TABLE, connection, if_exists="replace", index=False)

    # Read it back to prove the rows really landed.
    count = connection.execute(f"SELECT COUNT(*) FROM {TABLE}").fetchone()[0]
    connection.close()

    print(f"Wrote {count:,} rows into {DATABASE} -> {TABLE}")


if __name__ == "__main__":
    load()
