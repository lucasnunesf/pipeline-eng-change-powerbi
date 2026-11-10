"""The synthetic export has to look like a real one, defects included."""

import pandas as pd

from generate_raw import EXPORT_DATE, N_DOCUMENTS, generate


def test_export_has_the_planned_defects():
    df = generate()
    assert df["ECI_Number"].nunique() == N_DOCUMENTS
    assert df.dropna(how="all")["ECI_Number"].duplicated().sum() == 12
    assert df.isna().all(axis=1).sum() == 20


def test_nothing_was_completed_after_the_export_was_taken():
    # A real export cannot contain a step closed in the future.
    df = generate()
    for column in ("Step_Buyer_Real", "Step_Eng_Purchasing_Real"):
        dates = pd.to_datetime(df[column], format="%d/%m/%Y %H:%M:%S", errors="coerce")
        assert (dates.dropna() <= EXPORT_DATE).all(), column


def test_not_started_steps_have_no_dates():
    df = generate().dropna(how="all")
    not_started = df[df["Step_Buyer_Status"] == 1]
    assert (not_started["Step_Buyer_Deadline"] == "").all()
    assert (not_started["Step_Buyer_Real"] == "").all()
