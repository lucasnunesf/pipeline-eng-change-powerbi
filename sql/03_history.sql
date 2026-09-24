-- ---------------------------------------------------------------------------
-- Reading the history.
--
-- fact_status_snapshot holds one row per document per run date, written by
-- snapshot.py. These views turn that pile of rows into the two questions
-- people actually asked: how is it trending, and what moved this week.
-- ---------------------------------------------------------------------------


-- How many documents sat in each status, on each date the snapshot ran.
-- This is the trend line the source system could never produce.
DROP VIEW IF EXISTS vw_status_history;

CREATE VIEW vw_status_history AS
SELECT
    snapshot_date,
    status,
    COUNT(*) AS documents
FROM fact_status_snapshot
GROUP BY snapshot_date, status;


-- The same, split by group, for finding which area is drifting.
DROP VIEW IF EXISTS vw_status_history_by_group;

CREATE VIEW vw_status_history_by_group AS
SELECT
    snapshot_date,
    group_name,
    status,
    COUNT(*) AS documents
FROM fact_status_snapshot
GROUP BY snapshot_date, group_name, status;


-- Which documents changed status between one snapshot and the one before it.
--
-- LAG() reaches back to the previous row for the same document, ordered by
-- date, which is what makes a before-and-after comparison possible without
-- joining the table to itself.
DROP VIEW IF EXISTS vw_status_changes;

CREATE VIEW vw_status_changes AS
WITH with_previous AS (
    SELECT
        snapshot_date,
        ECI_Number,
        group_name,
        vehicle,
        status,
        LAG(status) OVER (
            PARTITION BY ECI_Number
            ORDER BY snapshot_date
        ) AS previous_status
    FROM fact_status_snapshot
)
SELECT
    snapshot_date,
    ECI_Number,
    group_name,
    vehicle,
    previous_status,
    status AS new_status
FROM with_previous
WHERE previous_status IS NOT NULL
  AND previous_status <> status;


-- A count of those movements per date, so the report can show
-- "12 went late this week, 8 were approved".
DROP VIEW IF EXISTS vw_weekly_movement;

CREATE VIEW vw_weekly_movement AS
SELECT
    snapshot_date,
    previous_status,
    new_status,
    COUNT(*) AS documents
FROM vw_status_changes
GROUP BY snapshot_date, previous_status, new_status;
