"""The business rules: per-step status, worst step wins, and the SQL views."""

import sqlite3
from pathlib import Path

import pandas as pd
import pytest

from snapshot import status_on, step_status

ROOT = Path(__file__).resolve().parents[1]
T = pd.Timestamp


# --- one step, on a given date ----------------------------------------------

@pytest.mark.parametrize(
    "code, deadline, completed, as_of, expected",
    [
        (2, T("2026-03-10"), T("2026-03-31"), T("2026-04-07"), "Approved"),
        (2, T("2026-03-10"), T("2026-03-31"), T("2026-03-17"), "Delayed"),
        (2, T("2026-03-10"), T("2026-03-31"), T("2026-03-03"), "In analysis"),
        (4, T("2026-03-10"), pd.NaT, T("2026-03-17"), "Delayed"),
        (4, T("2026-03-10"), pd.NaT, T("2026-03-03"), "In analysis"),
        (1, pd.NaT, pd.NaT, T("2026-03-17"), "Not started"),
    ],
)
def test_step_status_on_a_date(code, deadline, completed, as_of, expected):
    assert step_status(code, deadline, completed, as_of) == expected


def test_the_same_date_always_gives_the_same_answer():
    # The old spreadsheet answered differently depending on when it was asked.
    args = (2, T("2026-03-10"), T("2026-03-31"), T("2026-03-17"))
    assert step_status(*args) == step_status(*args) == "Delayed"


# --- a whole change: the worst step decides ---------------------------------

def _change(buyer, eng):
    """Build one clean_eci row from two (code, deadline, completed) steps."""
    return {
        "Step_Buyer_Status": buyer[0],
        "Step_Buyer_Deadline": buyer[1],
        "Step_Buyer_Real": buyer[2],
        "Step_Eng_Purchasing_Status": eng[0],
        "Step_Eng_Purchasing_Deadline": eng[1],
        "Step_Eng_Purchasing_Real": eng[2],
    }


def test_one_late_step_makes_the_whole_change_late():
    approved = (2, T("2026-03-10"), T("2026-03-05"))
    late = (4, T("2026-03-10"), pd.NaT)
    df = pd.DataFrame([_change(approved, late)])
    assert status_on(df, T("2026-04-01"))[0] == "Delayed"


def test_change_is_approved_only_when_every_step_is():
    approved = (2, T("2026-03-10"), T("2026-03-05"))
    df = pd.DataFrame([_change(approved, approved)])
    assert status_on(df, T("2026-04-01"))[0] == "Approved"


# --- the same rules, written in SQL -----------------------------------------

@pytest.fixture
def database(tmp_path):
    """A small clean_eci with one change per status, and every sql/ file run."""
    connection = sqlite3.connect(tmp_path / "eci.db")
    base = {"Group": "Group 01", "Vehicle": "Model A", "Category": "Design",
            "Change_Type": "Type 1", "Created_Date": "2020-01-01", "Lead_Time_Days": 30}
    past, future = "2020-02-01 00:00:00", "2999-01-01 00:00:00"
    rows = [
        # number, buyer (code, deadline, real), eng (code, deadline, real)
        ("APPROVED", (2, past, past), (3, past, past)),
        ("LATE", (2, past, past), (4, past, None)),
        ("OPEN", (4, future, None), (1, None, None)),
        ("WAITING", (1, None, None), (1, None, None)),
    ]
    records = []
    for number, buyer, eng in rows:
        records.append({**base, "ECI_Number": number,
                        "Step_Buyer_Status": buyer[0], "Step_Buyer_Deadline": buyer[1],
                        "Step_Buyer_Real": buyer[2], "Step_Buyer_Responsible": "Buyer 1",
                        "Step_Eng_Purchasing_Status": eng[0],
                        "Step_Eng_Purchasing_Deadline": eng[1],
                        "Step_Eng_Purchasing_Real": eng[2],
                        "Step_Eng_Purchasing_Responsible": "Eng Purchasing 1"})
    pd.DataFrame(records).to_sql("clean_eci", connection, index=False)

    for path in sorted((ROOT / "sql").glob("*.sql")):
        connection.executescript(path.read_text(encoding="utf-8"))
    yield connection
    connection.close()


def test_sql_gives_every_change_exactly_one_status(database):
    result = dict(database.execute("SELECT ECI_Number, status FROM vw_eci_status"))
    assert result == {
        "APPROVED": "Approved",
        "LATE": "Delayed",
        "OPEN": "In analysis",
        "WAITING": "Not started",
    }


def test_sql_on_time_rate_only_counts_closed_steps(database):
    closed, = database.execute(
        "SELECT SUM(closed_steps) FROM vw_on_time_by_step"
    ).fetchone()
    assert closed == 3   # APPROVED x2 and LATE's buyer step


def test_snapshot_table_survives_a_rebuild(database):
    database.execute(
        "INSERT INTO fact_status_snapshot VALUES ('2026-01-05', 'LATE', 'Delayed', 'Group 01', 'Model A')"
    )
    database.commit()
    for path in sorted((ROOT / "sql").glob("*.sql")):
        database.executescript(path.read_text(encoding="utf-8"))
    count, = database.execute("SELECT COUNT(*) FROM fact_status_snapshot").fetchone()
    assert count == 1
