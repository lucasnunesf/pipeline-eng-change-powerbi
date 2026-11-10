"""Unit tests for the cleaning functions in src/clean.py."""

import pandas as pd

from clean import clean_dates, clean_text, deduplicate, normalise, split_timing, CATEGORY_MAP


def test_clean_text_trims_and_collapses_spaces():
    result = clean_text(pd.Series(["  Buyer   1 ", "", None]))
    assert result[0] == "Buyer 1"
    assert pd.isna(result[1])
    assert pd.isna(result[2])


def test_dates_are_read_day_first():
    # 05/09 must be 5 September. A parser that guesses would say 9 May.
    result = clean_dates(pd.Series(["05/09/2025 10:00:00"]))
    assert result[0] == pd.Timestamp(2025, 9, 5, 10, 0, 0)


def test_unreadable_date_becomes_empty_instead_of_failing():
    result = clean_dates(pd.Series(["not a date", ""]))
    assert result.isna().all()


def test_category_spellings_fold_onto_one_value():
    raw = pd.Series(["Design", "design", "Desing", "  DESIGN "])
    assert set(normalise(raw, CATEGORY_MAP)) == {"Design"}


def test_unmapped_value_is_kept_not_dropped():
    result = normalise(pd.Series(["Something new"]), CATEGORY_MAP)
    assert result[0] == "Something new"


def test_timing_keeps_only_the_number_of_days():
    result = split_timing(pd.Series(["30 days", " 30 days", "150 days", None]))
    assert list(result[:3]) == [30, 30, 150]
    assert pd.isna(result[3])


def test_deduplicate_keeps_the_most_recent_version():
    old = pd.Timestamp("2026-01-01")
    new = pd.Timestamp("2026-03-01")
    df = pd.DataFrame(
        {
            "ECI_Number": ["A1", "A1", "B2"],
            "Created_Date": [old, old, old],
            "Step_Buyer_Deadline": [old, new, old],
            "Step_Buyer_Real": [None, new, None],
            "Step_Eng_Purchasing_Deadline": [None, None, None],
            "Step_Eng_Purchasing_Real": [None, None, None],
            "version": ["stale", "fresh", "only"],
        }
    )
    for column in df.columns[1:6]:
        df[column] = pd.to_datetime(df[column])

    result = deduplicate(df)

    assert result["ECI_Number"].is_unique
    assert result.set_index("ECI_Number").loc["A1", "version"] == "fresh"
