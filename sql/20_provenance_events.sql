-- Provenance ledger tables — docs/09_provenance_ledger.md §9
-- Run once against the ClickHouse Cloud cluster.

CREATE TABLE IF NOT EXISTS provenance_events (
    event_id         UUID,
    event_type       LowCardinality(String),
    project_id       UUID,
    scene_id         Nullable(UUID),
    bible_version_id UInt32,
    actor            Enum8('human'=1,'artie'=2,'supervisor'=3,
                           'director'=4,'system'=5),
    ts_micros        UInt64,
    payload          String,              -- JSON
    ingested_at      DateTime DEFAULT now()
) ENGINE = MergeTree
ORDER BY (project_id, ts_micros, event_id);

CREATE TABLE IF NOT EXISTS keystroke_batches (
    project_id      UUID,
    scene_id        UUID,
    component_id    UUID,
    ts_start_micros UInt64,
    ts_end_micros   UInt64,
    char_delta      Int32,
    content_hash    String
) ENGINE = MergeTree
ORDER BY (project_id, scene_id, ts_start_micros);
