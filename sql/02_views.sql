-- ---------------------------------------------------------------------------
-- The business rules.
--
-- Everything below reads from clean_eci, which Python already made
-- trustworthy: dates are dates, spellings are folded, each document appears
-- once. What is left is deciding what the data means, and that lives here so
-- it can be read by someone who does not write Python.
-- ---------------------------------------------------------------------------


-- ---------------------------------------------------------------------------
-- 1. One row per document per workflow step.
--
-- The export puts the two steps side by side, in their own columns. That makes
-- the table wide and forces every rule to be written twice, once per step.
-- Stacking them into one row per step means the rule below is written once,
-- and a third step would only need another UNION ALL here.
-- ---------------------------------------------------------------------------

DROP VIEW IF EXISTS vw_eci_step;

CREATE VIEW vw_eci_step AS
SELECT
    ECI_Number,
    'buyer'                          AS step_key,
    Step_Buyer_Status                AS status_code,
    Step_Buyer_Deadline              AS deadline,
    Step_Buyer_Real                  AS completed_at,
    Step_Buyer_Responsible           AS responsible,
    "Group"                          AS group_name,
    Vehicle                          AS vehicle,
    Category                         AS category,
    Change_Type                      AS change_type,
    Created_Date                     AS created_at,
    Lead_Time_Days                   AS lead_time_days
FROM clean_eci

UNION ALL

SELECT
    ECI_Number,
    'eng_purchasing',
    Step_Eng_Purchasing_Status,
    Step_Eng_Purchasing_Deadline,
    Step_Eng_Purchasing_Real,
    Step_Eng_Purchasing_Responsible,
    "Group",
    Vehicle,
    Category,
    Change_Type,
    Created_Date,
    Lead_Time_Days
FROM clean_eci;


-- ---------------------------------------------------------------------------
-- 2. The status rule.
--
--   closed (2 or 3)            -> Approved
--   open, deadline passed      -> Delayed
--   open, deadline still ahead -> In analysis
--   not started (1)            -> Not started
--
-- Every document lands in exactly one of the four. Nothing is dropped, so a
-- report can filter to the ones it cares about and the totals still add up.
-- ---------------------------------------------------------------------------

DROP VIEW IF EXISTS vw_eci_step_status;

CREATE VIEW vw_eci_step_status AS
SELECT
    s.ECI_Number,
    s.step_key,
    d.step_name,
    d.step_order,
    s.status_code,
    st.status_label,
    s.group_name,
    s.vehicle,
    s.category,
    s.change_type,
    s.responsible,
    s.created_at,
    s.deadline,
    s.completed_at,
    s.lead_time_days,

    CASE
        WHEN st.is_closed = 1                        THEN 'Approved'
        WHEN s.status_code = 1                       THEN 'Not started'
        WHEN s.deadline IS NULL                      THEN 'In analysis'
        WHEN DATE(s.deadline) < DATE('now')          THEN 'Delayed'
        ELSE                                              'In analysis'
    END AS status,

    -- Whether a closed step made its deadline. NULL while it is still open,
    -- because there is nothing to judge yet.
    CASE
        WHEN s.completed_at IS NULL OR s.deadline IS NULL THEN NULL
        WHEN DATE(s.completed_at) <= DATE(s.deadline)     THEN 1
        ELSE                                                   0
    END AS on_time,

    -- Days between the deadline and either the closing date or today.
    CAST(
        JULIANDAY(COALESCE(DATE(s.completed_at), DATE('now')))
        - JULIANDAY(DATE(s.deadline))
    AS INTEGER) AS days_late

FROM vw_eci_step s
JOIN dim_status st ON st.status_code = s.status_code
JOIN dim_step   d  ON d.step_key     = s.step_key;


-- ---------------------------------------------------------------------------
-- 3. One status for the whole document.
--
-- A document is only as good as its worst step: one late step makes the whole
-- change late. MIN() over the ranking below picks that worst step.
-- ---------------------------------------------------------------------------

DROP VIEW IF EXISTS vw_eci_status;

CREATE VIEW vw_eci_status AS
SELECT
    ECI_Number,
    group_name,
    vehicle,
    category,
    change_type,
    created_at,
    MIN(deadline)    AS first_deadline,
    MAX(completed_at) AS last_completed_at,

    CASE MIN(
        CASE status
            WHEN 'Delayed'     THEN 1
            WHEN 'In analysis' THEN 2
            WHEN 'Not started' THEN 3
            ELSE                    4   -- Approved
        END
    )
        WHEN 1 THEN 'Delayed'
        WHEN 2 THEN 'In analysis'
        WHEN 3 THEN 'Not started'
        ELSE        'Approved'
    END AS status

FROM vw_eci_step_status
GROUP BY
    ECI_Number, group_name, vehicle, category, change_type, created_at;


-- ---------------------------------------------------------------------------
-- 4. The shapes the report reads.
-- ---------------------------------------------------------------------------

DROP VIEW IF EXISTS vw_status_by_group;

CREATE VIEW vw_status_by_group AS
SELECT
    group_name,
    status,
    COUNT(*) AS documents
FROM vw_eci_status
GROUP BY group_name, status;


DROP VIEW IF EXISTS vw_status_by_vehicle;

CREATE VIEW vw_status_by_vehicle AS
SELECT
    vehicle,
    status,
    COUNT(*) AS documents
FROM vw_eci_status
GROUP BY vehicle, status;


-- How well each step keeps its deadlines. on_time is NULL while a step is
-- still open, so AVG() ignores those rows and the rate covers closed work only.
DROP VIEW IF EXISTS vw_on_time_by_step;

CREATE VIEW vw_on_time_by_step AS
SELECT
    step_name,
    step_order,
    COUNT(on_time)                             AS closed_steps,
    SUM(on_time)                               AS on_time_steps,
    ROUND(AVG(on_time) * 100, 1)               AS on_time_rate,
    ROUND(AVG(CASE WHEN on_time = 0 THEN days_late END), 1) AS avg_days_late
FROM vw_eci_step_status
GROUP BY step_name, step_order;
