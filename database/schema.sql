PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS schema_versions (
    version INTEGER PRIMARY KEY,
    applied_at_utc TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS record_sets (
    name TEXT PRIMARY KEY,
    source_path TEXT,
    source_sha256 TEXT,
    row_count INTEGER NOT NULL CHECK (row_count >= 0),
    updated_at_utc TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS records (
    record_set_name TEXT NOT NULL,
    row_index INTEGER NOT NULL CHECK (row_index >= 0),
    payload_json TEXT NOT NULL CHECK (json_valid(payload_json)),
    PRIMARY KEY (record_set_name, row_index),
    FOREIGN KEY (record_set_name) REFERENCES record_sets(name) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS records_by_set
    ON records(record_set_name, row_index);

CREATE TABLE IF NOT EXISTS project_facts (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    unit TEXT,
    source TEXT NOT NULL,
    updated_at_utc TEXT NOT NULL
);

INSERT OR IGNORE INTO schema_versions(version, applied_at_utc)
VALUES (1, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'));

-- These views expose the most frequently queried result sets as typed SQL.
-- Less common records remain queryable with json_extract(payload_json, ...).
CREATE VIEW IF NOT EXISTS quality_ablation AS
SELECT
    row_index,
    json_extract(payload_json, '$.method') AS method,
    json_extract(payload_json, '$.training_loss') AS training_loss,
    CAST(NULLIF(json_extract(payload_json, '$.checkpoint_epoch'), '') AS INTEGER) AS checkpoint_epoch,
    CAST(json_extract(payload_json, '$.psnr') AS REAL) AS psnr,
    CAST(json_extract(payload_json, '$.ssim') AS REAL) AS ssim,
    CAST(json_extract(payload_json, '$.lpips') AS REAL) AS lpips,
    CAST(json_extract(payload_json, '$.test_images') AS INTEGER) AS test_images,
    json_extract(payload_json, '$.test_scene') AS test_scene,
    json_extract(payload_json, '$.provisional') = 'true' AS provisional
FROM records
WHERE record_set_name = 'results.quality.training_ablation';

CREATE VIEW IF NOT EXISTS latency_comparison AS
SELECT
    row_index,
    json_extract(payload_json, '$.method') AS method,
    json_extract(payload_json, '$.backend') AS backend,
    CAST(json_extract(payload_json, '$.average_ms') AS REAL) AS average_ms,
    CAST(json_extract(payload_json, '$.median_ms') AS REAL) AS median_ms,
    CAST(json_extract(payload_json, '$.p95_ms') AS REAL) AS p95_ms,
    CAST(json_extract(payload_json, '$.p99_ms') AS REAL) AS p99_ms,
    CAST(json_extract(payload_json, '$.fps') AS REAL) AS fps
FROM records
WHERE record_set_name = 'results.latency.comparison';

