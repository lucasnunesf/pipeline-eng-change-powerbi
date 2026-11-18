"""
Create the fake input file: the weekly export of engineering changes.

At work, the system exported the engineering changes (ECI) to Excel every
week. This script builds a file that looks like that:

  data/eci_export.xlsx   one row per engineering change

Like the real export, it has mistakes: dates stored as text, the same
category written in different ways and some rows exported twice.

All names and codes are invented. The random seed is fixed, so the file is
the same every time.

Run:  python scripts/generate_data.py
"""

import random
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

random.seed(42)
DATA = Path(__file__).resolve().parent.parent / "data"
DATA.mkdir(exist_ok=True)

EXPORT_DATE = date(2026, 10, 30)      # the day the export was taken
GROUPS = [f"Group {i}" for i in range(1, 7)]
PROJECTS = [f"Project {i}" for i in range(1, 5)]
OWNERS = [f"Buyer {i}" for i in range(1, 9)] + [f"Eng Purchasing {i}" for i in range(1, 6)]
CATEGORIES = ["Design", "design", "Desing", "Project", "project"]   # same values, typed differently
CATEGORY_WEIGHTS = [55, 5, 5, 30, 5]

rows = []
for n in range(600):
    created = EXPORT_DATE - timedelta(days=random.randint(5, 300))
    deadline = created + timedelta(days=random.choice([15, 30, 60, 90]))
    closed = created + timedelta(days=random.randint(3, 120))
    if closed > EXPORT_DATE:
        closed = None                                         # still open
    rows.append({
        "ECI Number": f"{random.randint(100, 999)}{random.choice('ABCDEFGHJK')}{random.choice('LMNPQRSTUW')}{n:04d}",
        "Group": random.choice(GROUPS),
        "Project": random.choice(PROJECTS),
        "Owner": random.choice(OWNERS),
        "Category": random.choices(CATEGORIES, CATEGORY_WEIGHTS)[0],
        "Created": created.strftime("%d/%m/%Y"),               # dates come as text, day first
        "Deadline": deadline.strftime("%d/%m/%Y"),
        "Closed": closed.strftime("%d/%m/%Y") if closed else "",
    })

rows += random.sample(rows, 12)                               # 12 rows exported twice
random.shuffle(rows)
pd.DataFrame(rows).to_excel(DATA / "eci_export.xlsx", index=False)
print(f"{len(rows)} rows written to {DATA / 'eci_export.xlsx'}")
