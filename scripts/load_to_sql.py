"""
Clean the weekly export, load it into SQL and export the views for Power BI.

Steps:
  1. Read data/eci_export.xlsx with pandas.
  2. Clean:
     - dates stored as text ("05/09/2026") -> dates, day first
     - "design", "Desing"                  -> "Design"
     - rows exported twice                 -> kept once
  3. Load the changes into a SQLite database (eng_change.db), plus a list of
     Mondays: the weeks used to rebuild the history.
  4. Create the views (sql/views.sql).
  5. Save each view as a CSV in output/ for Power BI.

Run:  python scripts/load_to_sql.py
"""

import sqlite3
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA, SQL, OUTPUT = ROOT / "data", ROOT / "sql", ROOT / "output"
DB = ROOT / "eng_change.db"
EXPORT_DATE = "2026-10-30"           # the day the export was taken

# 1. Read
eci = pd.read_excel(DATA / "eci_export.xlsx", dtype=str)
rows_read = len(eci)

# 2. Clean
for col in ["Created", "Deadline", "Closed"]:
    eci[col] = pd.to_datetime(eci[col], format="%d/%m/%Y").dt.strftime("%Y-%m-%d")
eci["Category"] = eci["Category"].str.strip().str.capitalize().replace({"Desing": "Design"})
eci = eci.drop_duplicates()
eci = eci.rename(columns={"ECI Number": "eci_number", "Group": "group_name", "Project": "project",
                          "Owner": "owner", "Category": "category", "Created": "created",
                          "Deadline": "deadline", "Closed": "closed"})

# One row per Monday, from the first change to the export date
weeks = pd.DataFrame({"week": pd.date_range(eci["created"].min(), EXPORT_DATE, freq="W-MON")
                      .strftime("%Y-%m-%d")})

# 3 and 4. Load SQL and create the views
with sqlite3.connect(DB) as con:
    eci.to_sql("eci", con, if_exists="replace", index=False)
    weeks.to_sql("weeks", con, if_exists="replace", index=False)
    con.execute("DROP TABLE IF EXISTS params")
    con.execute("CREATE TABLE params AS SELECT ? AS export_date", (EXPORT_DATE,))
    con.executescript((SQL / "views.sql").read_text())

    # 5. Export for Power BI
    OUTPUT.mkdir(exist_ok=True)
    for view in ["v_eci_status", "v_status_by_group", "v_weekly_history"]:
        df = pd.read_sql(f"SELECT * FROM {view}", con)
        df.to_csv(OUTPUT / f"{view.removeprefix('v_')}.csv", index=False)
        print(f"{view}: {len(df)} rows")

print(f"{rows_read} rows read, {len(eci)} changes after cleaning")
