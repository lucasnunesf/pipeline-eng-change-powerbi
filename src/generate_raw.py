"""
Generate a fake raw export, the way the source system would produce it.

The real export is internal company data, so the repository ships this
generator instead. It reproduces the shape of the real file AND its defects,
because cleaning those defects is what the pipeline is for.

Run:
    python src/generate_raw.py
"""

import random
from datetime import datetime, timedelta

import pandas as pd

# Fixed seed = the same file every time it runs, so results are reproducible.
SEED = 42
N_DOCUMENTS = 600
OUTPUT = "data/raw/eci_export.xlsx"

GROUPS = ["Group 01", "Group 02", "Group 03", "Group 04", "Group 05", "Group 06"]
VEHICLES = ["Model A", "Model B", "Model C", "Model D", "Model E", "Model F"]

# Who opened the document, and who owns each of the two workflow steps.
CREATORS = [f"Creation {i}" for i in range(1, 11)]
BUYERS = [f"Buyer {i}" for i in range(1, 16)]
ENG_PURCHASING = [f"Eng Purchasing {i}" for i in range(1, 13)]

# The three lists below carry the defects on purpose.
# Same value, typed differently by whoever filled the form.
CATEGORIES = ["Design", "design", "Desing", "Project", "project", "Both"]
CATEGORY_WEIGHTS = [50, 4, 3, 35, 3, 5]

CHANGE_TYPES = ["Type 1", "Type 2", "Type 3", "type 1", "TYPE 2"]
CHANGE_WEIGHTS = [50, 27, 18, 3, 2]

# Note the leading spaces on some values - they come from the source system.
TIMINGS = ["15 days", "30 days", " 30 days", "60 days", "90 days", "150 days"]
TIMING_WEIGHTS = [20, 30, 12, 18, 12, 8]

# Workflow status codes used by the source system.
#   1 = not started, 2 = completed, 3 = approved, 4 = under approval
STATUS_CODES = [1, 2, 3, 4]
STATUS_WEIGHTS = [18, 60, 12, 10]

# Descriptions are a free-text field, so they are built by combining generic
# words at random. This keeps them varied without carrying any real content.
DESC_SUBJECTS = ["Component", "Process", "Material", "Tooling", "Layout",
                 "Packaging", "Assembly", "Fixture", "Coating", "Fastener"]
DESC_ACTIONS = ["update", "revision", "replacement", "adjustment",
                "standardisation", "correction", "removal"]


def make_description(rng):
    """Free-text field: a random subject + action, sometimes with a reference."""
    text = f"{rng.choice(DESC_SUBJECTS)} {rng.choice(DESC_ACTIONS)}"
    if rng.random() < 0.3:
        text += f" - REF {rng.randint(1000, 9999)}"
    return text


def make_eci_number(rng, vehicle):
    """Build a document number that looks like the real ones: 006JF0512."""
    prefix = f"{rng.randint(1, 999):03d}{rng.choice('JWD')}"
    return f"{prefix}{rng.choice('EFMQWX')}{rng.randint(0, 9999):04d}"


def make_step(rng, created, code, owners):
    """Return the four columns of one workflow step.

    A step that was never started has no dates at all. A completed step has a
    deadline and a real date, and about a third of those land late.
    """
    if code in (2, 3):
        deadline = created + timedelta(days=rng.randint(7, 120))
        if rng.random() < 0.35:
            real = deadline + timedelta(days=rng.randint(1, 60))   # late
        else:
            real = deadline - timedelta(days=rng.randint(0, 30))   # on time
        responsible = rng.choice(owners)
    elif code == 4:
        # Still under approval: it has a deadline but was never closed.
        deadline = created + timedelta(days=rng.randint(-60, 90))
        real = None
        responsible = rng.choice(owners)
    else:
        deadline = real = None
        responsible = ""

    return {
        "Status": code,
        # Dates leave the source system as text, in dd/mm/yyyy format.
        "Deadline": deadline.strftime("%d/%m/%Y %H:%M:%S") if deadline else "",
        "Real": real.strftime("%d/%m/%Y %H:%M:%S") if real else "",
        "Responsible": responsible,
    }


def generate():
    rng = random.Random(SEED)
    today = datetime(2026, 6, 23)          # the date the export was taken
    rows = []

    for _ in range(N_DOCUMENTS):
        vehicle = rng.choice(VEHICLES)
        created = today - timedelta(
            days=rng.randint(10, 700), minutes=rng.randint(0, 1440)
        )

        # Step 1 of the workflow belongs to the buyer, step 2 to engineering
        # purchasing. Each has its own status, deadline and owner.
        buyer = make_step(rng, created, rng.choices(STATUS_CODES, STATUS_WEIGHTS)[0], BUYERS)
        eng = make_step(rng, created, rng.choices(STATUS_CODES, STATUS_WEIGHTS)[0], ENG_PURCHASING)

        rows.append({
            "ECI_Number": make_eci_number(rng, vehicle),
            # A quarter of the documents were saved with no description.
            "Description": "" if rng.random() < 0.25 else make_description(rng),
            "Created_Date": created.strftime("%d/%m/%Y %H:%M:%S"),
            # Some names were pasted into the form with a leading space.
            "Created_By": (" " if rng.random() < 0.15 else "") + rng.choice(CREATORS),
            "Group": rng.choice(GROUPS),
            "Vehicle": vehicle,
            "Change_Type": rng.choices(CHANGE_TYPES, CHANGE_WEIGHTS)[0],
            "Category": rng.choices(CATEGORIES, CATEGORY_WEIGHTS)[0],
            "Timing": rng.choices(TIMINGS, TIMING_WEIGHTS)[0],
            "Step_Buyer_Status": buyer["Status"],
            "Step_Buyer_Deadline": buyer["Deadline"],
            "Step_Buyer_Real": buyer["Real"],
            "Step_Buyer_Responsible": buyer["Responsible"],
            "Step_Eng_Purchasing_Status": eng["Status"],
            "Step_Eng_Purchasing_Deadline": eng["Deadline"],
            "Step_Eng_Purchasing_Real": eng["Real"],
            "Step_Eng_Purchasing_Responsible": eng["Responsible"],
        })

    df = pd.DataFrame(rows)

    # Defect 1: a few documents were exported twice, as happens after a revision.
    duplicates = df.sample(n=12, random_state=SEED)
    df = pd.concat([df, duplicates], ignore_index=True)

    # Defect 2: the export ends with empty rows.
    blanks = pd.DataFrame([{c: None for c in df.columns}] * 20)
    df = pd.concat([df, blanks], ignore_index=True)

    # Defect 3: the rows come out in no particular order.
    df = df.sample(frac=1, random_state=SEED).reset_index(drop=True)

    return df


if __name__ == "__main__":
    df = generate()
    df.to_excel(OUTPUT, index=False, sheet_name="Sheet1")
    print(f"Wrote {OUTPUT}")
    print(f"  {len(df):,} rows ({df['ECI_Number'].nunique():,} unique ECIs)")
