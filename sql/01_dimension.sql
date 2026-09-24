-- ---------------------------------------------------------------------------
-- Lookup tables.
--
-- The source system stores a status as a number. Keeping the meaning of those
-- numbers in a table, instead of writing it into every query, means a label
-- changes in one place and every report follows.
-- ---------------------------------------------------------------------------

DROP TABLE IF EXISTS dim_status;

CREATE TABLE dim_status (
    status_code  INTEGER PRIMARY KEY,
    status_label TEXT    NOT NULL,
    is_closed    INTEGER NOT NULL   -- 1 when the step needs no further action
);

INSERT INTO dim_status (status_code, status_label, is_closed) VALUES
    (1, 'Not started',    0),
    (2, 'Completed',      1),
    (3, 'Approved',       1),
    (4, 'Under approval', 0);


DROP TABLE IF EXISTS dim_step;

CREATE TABLE dim_step (
    step_key   TEXT PRIMARY KEY,
    step_name  TEXT    NOT NULL,
    step_order INTEGER NOT NULL   -- the order the workflow runs in
);

INSERT INTO dim_step (step_key, step_name, step_order) VALUES
    ('buyer',          'Buyer',          1),
    ('eng_purchasing', 'Eng Purchasing', 2);
