-- Three views for the Power BI report. Each one becomes a CSV.
-- Status rule:
--   Approved  = the change has a closed date
--   Delayed   = still open and the deadline has passed
--   Analysis  = still open and inside the deadline

-- 1. Status of every change on the export date, with its owner.
DROP VIEW IF EXISTS v_eci_status;
CREATE VIEW v_eci_status AS
SELECT
    e.eci_number,
    e.group_name,
    e.project,
    e.owner,
    e.category,
    e.created,
    e.deadline,
    e.closed,
    CASE
        WHEN e.closed IS NOT NULL                   THEN 'Approved'
        WHEN e.deadline < (SELECT export_date FROM params) THEN 'Delayed'
        ELSE 'Analysis'
    END AS status
FROM eci e;


-- 2. How many changes in each status, per group.
DROP VIEW IF EXISTS v_status_by_group;
CREATE VIEW v_status_by_group AS
SELECT group_name, status, COUNT(*) AS changes
FROM v_eci_status
GROUP BY group_name, status;


-- 3. The history the system did not keep: the status of every change
--    on each Monday, worked out from its dates.
DROP VIEW IF EXISTS v_weekly_history;
CREATE VIEW v_weekly_history AS
SELECT
    w.week,
    CASE
        WHEN e.closed IS NOT NULL AND e.closed <= w.week THEN 'Approved'
        WHEN e.deadline < w.week                        THEN 'Delayed'
        ELSE 'Analysis'
    END AS status,
    COUNT(*) AS changes
FROM weeks w
JOIN eci e ON e.created <= w.week
GROUP BY w.week, status;
