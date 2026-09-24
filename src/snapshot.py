"""
Keep a weekly photograph of where every change stood.

This is the part that answers the question the source system never could. It
only ever shows the present: when a deadline is pushed or a request is
cancelled, the old value is gone. Writing one row per document per run keeps
the past, and a month later the trend is a query instead of a memory.

    python src/snapshot.py                  take today's snapshot
    python src/snapshot.py --date 2026-06-01    take it for another date
    python src/snapshot.py --seed-history 12    build 12 weeks at once

Run it weekly, after the pipeline. Running it twice on the same date replaces
that date rather than doubling it.
"""

import argparse
import sqlite3
from datetime import date, timedelta

import pandas as pd

DATABASE = "data/eci.db"
SOURCE_TABLE = "clean_eci"
TARGET_TABLE = "fact_status_snapshot"

# Status codes that mean the step needs no further action. Kept in step with
# dim_status, where the same fact is recorded for SQL to use.
CLOSED_CODES = {2, 3}
NOT_STARTED_CODE = 1

# How bad each status is. The document takes the worst of its steps.
SEVERITY = {"Delayed": 1, "In analysis": 2, "Not started": 3, "Approved": 4}


def require_table(connection, name):
    """Stop with a useful message instead of a database error.

    The table is declared in sql/03_history.sql rather than here, so the
    structure lives in one place. That means build_sql.py has to have run
    first.
    """
    exists = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (name,)
    ).fetchone()

    if not exists:
        raise SystemExit(
            f"Table '{name}' does not exist yet.\n"
            "Run 'python src/build_sql.py' first, or use 'python src/run_pipeline.py'."
        )


def step_status(status_code, deadline, completed_at, as_of):
    """What one step's status was on a given date, read from the dates alone.

    Reading the dates instead of trusting today's status code is what makes a
    past date answerable. A step that closed three weeks late was 'Delayed' the
    week before it closed, and this returns that.
    """
    as_of = pd.Timestamp(as_of)

    if pd.notna(completed_at) and completed_at <= as_of:
        return "Approved"
    if pd.notna(deadline) and deadline < as_of:
        return "Delayed"
    if status_code == NOT_STARTED_CODE:
        return "Not started"
    return "In analysis"


def status_on(df, as_of):
    """One status per document, for the given date.

    A document is only as good as its worst step: one late step makes the whole
    change late.
    """
    steps = [
        ("Step_Buyer_Status", "Step_Buyer_Deadline", "Step_Buyer_Real"),
        (
            "Step_Eng_Purchasing_Status",
            "Step_Eng_Purchasing_Deadline",
            "Step_Eng_Purchasing_Real",
        ),
    ]

    worst = pd.Series(SEVERITY["Approved"], index=df.index)
    for code_col, deadline_col, real_col in steps:
        severity = df.apply(
            lambda row: SEVERITY[
                step_status(row[code_col], row[deadline_col], row[real_col], as_of)
            ],
            axis=1,
        )
        worst = worst.combine(severity, min)

    labels = {value: name for name, value in SEVERITY.items()}
    return worst.map(labels)


def take_snapshot(connection, df, as_of):
    """Write one date's worth of rows, replacing that date if it is already there."""
    snapshot = pd.DataFrame(
        {
            "snapshot_date": pd.Timestamp(as_of).strftime("%Y-%m-%d"),
            "ECI_Number": df["ECI_Number"],
            "status": status_on(df, as_of),
            "group_name": df["Group"],
            "vehicle": df["Vehicle"],
        }
    )

    connection.execute(
        f"DELETE FROM {TARGET_TABLE} WHERE snapshot_date = ?",
        (pd.Timestamp(as_of).strftime("%Y-%m-%d"),),
    )
    snapshot.to_sql(TARGET_TABLE, connection, if_exists="append", index=False)
    return snapshot


def main():
    parser = argparse.ArgumentParser(description="Take a status snapshot")
    parser.add_argument(
        "--date",
        type=lambda s: date.fromisoformat(s),
        default=date.today(),
        help="the date to record (default: today)",
    )
    parser.add_argument(
        "--seed-history",
        type=int,
        metavar="WEEKS",
        help=(
            "write one snapshot per week for the last N weeks. Only useful on a "
            "fresh database, so the history has something in it before the "
            "weekly runs start accumulating."
        ),
    )
    args = parser.parse_args()

    connection = sqlite3.connect(DATABASE)
    require_table(connection, TARGET_TABLE)

    df = pd.read_sql(f"SELECT * FROM {SOURCE_TABLE}", connection)
    for column in (
        "Step_Buyer_Deadline",
        "Step_Buyer_Real",
        "Step_Eng_Purchasing_Deadline",
        "Step_Eng_Purchasing_Real",
    ):
        df[column] = pd.to_datetime(df[column], errors="coerce")

    if args.seed_history:
        dates = [args.date - timedelta(weeks=n) for n in range(args.seed_history, 0, -1)]
    else:
        dates = [args.date]

    for as_of in dates:
        snapshot = take_snapshot(connection, df, as_of)
        counts = snapshot["status"].value_counts().to_dict()
        print(f"{as_of}  {len(snapshot):>4} documents  {counts}")

    connection.commit()

    total, first, last = connection.execute(
        f"SELECT COUNT(*), MIN(snapshot_date), MAX(snapshot_date) FROM {TARGET_TABLE}"
    ).fetchone()
    connection.close()

    print(f"\n{TARGET_TABLE} now holds {total:,} rows, from {first} to {last}")


if __name__ == "__main__":
    main()
