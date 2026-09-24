"""
Run the whole pipeline, in order, with one command.

    python src/run_pipeline.py              the weekly run
    python src/run_pipeline.py --fresh      start from an empty database
    python src/run_pipeline.py --help       the options

Each step is a script that also runs on its own, so a step can be re-run in
isolation while a rule is being fixed. This file only decides the order and
stops everything if a step fails.
"""

import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path

DATABASE = Path("data/eci.db")
RAW_FILE = Path("data/raw/eci_export.xlsx")

# Weeks of history to write when starting from scratch, so the trend views
# have something in them before the weekly runs begin.
SEED_WEEKS = 12


def run(description, arguments):
    """Run one step and stop the pipeline if it fails."""
    print(f"\n{'=' * 70}\n{description}\n{'=' * 70}")

    started = time.perf_counter()
    result = subprocess.run([sys.executable, *arguments])
    elapsed = time.perf_counter() - started

    if result.returncode != 0:
        print(f"\nFAILED after {elapsed:.1f}s: {' '.join(arguments)}")
        # Stopping here matters: a later step running on half-written data
        # would produce a report that looks fine and is wrong.
        sys.exit(result.returncode)

    print(f"-- done in {elapsed:.1f}s")


def main():
    parser = argparse.ArgumentParser(description="Run the ECI pipeline")
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="delete the database and the generated export, then build both again",
    )
    parser.add_argument(
        "--skip-snapshot",
        action="store_true",
        help="do not record a snapshot (useful while testing a rule)",
    )
    args = parser.parse_args()

    if args.fresh:
        for path in (DATABASE, RAW_FILE):
            if path.exists():
                path.unlink()
                print(f"removed {path}")

    started = time.perf_counter()

    # 1. The export. Only generated when it is missing, because regenerating it
    #    every run would hide the fact that the pipeline reads a real file.
    if not RAW_FILE.exists():
        run("1/5  generate the export", ["src/generate_raw.py"])
    else:
        print(f"\n1/5  using the existing export at {RAW_FILE}")

    # 2. Land it, untouched.
    run("2/5  load it into the staging table", ["src/load_raw.py"])

    # 3. Make it trustworthy.
    run("3/5  clean and deduplicate", ["src/clean.py"])

    # 4. Apply the rules. This runs before the snapshot so the snapshot records
    #    the status the rules produce, not the one from the previous run.
    run("4/5  build the tables and views", ["src/build_sql.py"])

    # 5. Record where everything stands today.
    if args.skip_snapshot:
        print("\n5/5  snapshot skipped")
    elif args.fresh:
        run(
            f"5/5  seed {SEED_WEEKS} weeks of history",
            ["src/snapshot.py", "--seed-history", str(SEED_WEEKS)],
        )
        # Rebuild so the history views exist over the rows just written.
        run("     rebuild the views over the new history", ["src/build_sql.py"])
    else:
        run("5/5  take today's snapshot", ["src/snapshot.py"])

    elapsed = time.perf_counter() - started
    size = DATABASE.stat().st_size / 1024 if DATABASE.exists() else 0

    print(f"\n{'=' * 70}")
    print(f"Pipeline finished in {elapsed:.1f}s")
    print(f"{DATABASE} is {size:,.0f} KB and ready for Power BI")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
