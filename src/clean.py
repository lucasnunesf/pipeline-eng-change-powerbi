"""
Clean the raw export and write it back to the database.

Reads the staging table exactly as it landed, fixes the four things the source
system gets wrong, and writes the result to a new table. Nothing is deleted
along the way: the staging table stays untouched, so a rule can be changed and
this script re-run without downloading the export again.

Run:
    python src/clean.py
"""

import sqlite3

import pandas as pd

DATABASE = "data/eci.db"
SOURCE_TABLE = "stg_eci_export"
TARGET_TABLE = "clean_eci"

# The source system lets people type these fields by hand, so the same value
# arrives spelled several ways. Everything here is lowercased and trimmed
# before being looked up, so "  DESIGN " and "design" both match "design".
CATEGORY_MAP = {
    "design": "Design",
    "desing": "Design",      # typo people make often enough to matter
    "project": "Project",
    "both": "Both",
}

CHANGE_TYPE_MAP = {
    "type 1": "Type 1",
    "type 2": "Type 2",
    "type 3": "Type 3",
}

# Columns holding a date written as text, in day/month/year order.
DATE_COLUMNS = [
    "Created_Date",
    "Step_Buyer_Deadline",
    "Step_Buyer_Real",
    "Step_Eng_Purchasing_Deadline",
    "Step_Eng_Purchasing_Real",
]

TEXT_COLUMNS = [
    "ECI_Number",
    "Description",
    "Created_By",
    "Group",
    "Vehicle",
    "Step_Buyer_Responsible",
    "Step_Eng_Purchasing_Responsible",
]


def clean_text(series):
    """Trim the ends, collapse repeated spaces, and blank out empty values."""
    return (
        series.astype("string")
        .str.strip()
        .str.replace(r"\s+", " ", regex=True)
        .replace({"": None, "nan": None, "None": None})
    )


def clean_dates(series):
    """Turn dd/mm/yyyy text into a real date.

    dayfirst matters: 05/09/2025 is 5 September, not 9 May. Getting this wrong
    silently moves half the dates and the report looks fine while being wrong.
    Anything that cannot be read becomes empty instead of raising.
    """
    return pd.to_datetime(series, format="%d/%m/%Y %H:%M:%S", errors="coerce")


def normalise(series, mapping):
    """Fold spelling variants onto one agreed value.

    A value with no entry in the mapping is kept as it arrived rather than
    dropped, so the report below can show it and the mapping can be extended.
    """
    key = series.astype("string").str.strip().str.lower()
    return key.map(mapping).fillna(series.astype("string").str.strip())


def split_timing(series):
    """'30 days' -> the number 30.

    The field is text, and the useful part is the number of days allowed. The
    leading spaces some values carry ("  30 days") disappear with it.
    """
    return pd.to_numeric(
        series.astype("string").str.extract(r"(\d+)", expand=False), errors="coerce"
    ).astype("Int64")


def main():
    connection = sqlite3.connect(DATABASE)
    df = pd.read_sql(f"SELECT * FROM {SOURCE_TABLE}", connection)
    print(f"Read {len(df):,} rows from {SOURCE_TABLE}")

    # Count the mess before touching it, so the effect is visible.
    before = {
        "Category": df["Category"].nunique(),
        "Change_Type": df["Change_Type"].nunique(),
        "Timing": df["Timing"].nunique(),
        "Created_By": df["Created_By"].nunique(),
    }

    for column in TEXT_COLUMNS:
        df[column] = clean_text(df[column])

    for column in DATE_COLUMNS:
        df[column] = clean_dates(df[column])

    df["Category"] = normalise(df["Category"], CATEGORY_MAP)
    df["Change_Type"] = normalise(df["Change_Type"], CHANGE_TYPE_MAP)

    df["Timing"] = clean_text(df["Timing"])
    df["Lead_Time_Days"] = split_timing(df["Timing"])

    # Status codes arrive as text because the whole export was read as text.
    for column in ("Step_Buyer_Status", "Step_Eng_Purchasing_Status"):
        df[column] = pd.to_numeric(df[column], errors="coerce").astype("Int64")

    after = {
        "Category": df["Category"].nunique(),
        "Change_Type": df["Change_Type"].nunique(),
        "Timing": df["Timing"].nunique(),
        "Created_By": df["Created_By"].nunique(),
    }

    print("\nDistinct values, before -> after")
    for column in before:
        print(f"  {column:16} {before[column]:3} -> {after[column]:3}")

    df.to_sql(TARGET_TABLE, connection, if_exists="replace", index=False)
    count = connection.execute(f"SELECT COUNT(*) FROM {TARGET_TABLE}").fetchone()[0]
    connection.close()

    print(f"\nWrote {count:,} rows into {DATABASE} -> {TARGET_TABLE}")


if __name__ == "__main__":
    main()
