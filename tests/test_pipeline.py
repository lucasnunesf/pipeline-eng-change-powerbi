"""End to end: run the pipeline in an empty folder, the way someone who clones it would."""

import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def run(folder, *arguments):
    return subprocess.run(
        [sys.executable, *arguments], cwd=folder, capture_output=True, text=True
    )


@pytest.fixture
def project(tmp_path):
    shutil.copytree(ROOT / "src", tmp_path / "src")
    shutil.copytree(ROOT / "sql", tmp_path / "sql")
    (tmp_path / "data" / "raw").mkdir(parents=True)
    result = run(tmp_path, "src/run_pipeline.py", "--fresh")
    assert result.returncode == 0, result.stdout + result.stderr
    return tmp_path


def count(folder, table):
    with sqlite3.connect(folder / "data" / "eci.db") as connection:
        return connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def test_fresh_run_builds_every_layer(project):
    assert count(project, "stg_eci_export") == 612
    assert count(project, "clean_eci") == 600
    assert count(project, "vw_eci_status") == 600
    assert count(project, "fact_status_snapshot") == 600 * 12


def test_weekly_run_adds_history_and_keeps_the_old_weeks(project):
    run(project, "src/run_pipeline.py")
    assert count(project, "fact_status_snapshot") == 600 * 13


def test_snapshot_twice_on_one_date_does_not_double(project):
    for _ in range(2):
        run(project, "src/snapshot.py", "--date", "2026-01-05")
    assert count(project, "fact_status_snapshot") == 600 * 13


def test_snapshot_before_build_stops_with_a_clear_message(tmp_path):
    shutil.copytree(ROOT / "src", tmp_path / "src")
    (tmp_path / "data").mkdir()
    result = run(tmp_path, "src/snapshot.py")
    assert result.returncode != 0
    assert "build_sql.py" in result.stdout + result.stderr


def test_python_and_sql_give_the_same_status_today(project):
    # The rule is written twice: in snapshot.py for past dates, in SQL for
    # today. If they ever disagree, the trend and the report stop matching.
    run(project, "src/snapshot.py")
    with sqlite3.connect(project / "data" / "eci.db") as connection:
        mismatches = connection.execute(
            """
            SELECT COUNT(*)
            FROM vw_eci_status v
            JOIN fact_status_snapshot s
              ON s.ECI_Number = v.ECI_Number
             AND s.snapshot_date = DATE('now', 'localtime')
            WHERE s.status <> v.status
            """
        ).fetchone()[0]
    assert mismatches == 0
