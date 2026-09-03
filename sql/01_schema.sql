CREATE TABLE IF NOT EXISTS positions_src (
    position_id     UInt8,
    code            String,
    name            String,
    position_type   Enum8('BASELINE'=1,'TURNING_POINT'=2,'CONNECTIVE'=3),
    range_start_pct UInt8,
    range_end_pct   UInt8,
    act             Enum8('ACT_ONE'=1,'ACT_TWO'=2,'ACT_THREE'=3)
) ENGINE = MergeTree ORDER BY position_id;

CREATE TABLE IF NOT EXISTS lenses_src (
    lens_id UInt8,
    code    String,
    name    String
) ENGINE = MergeTree ORDER BY lens_id;

CREATE TABLE IF NOT EXISTS cells_src (
    cell_id_num              UInt16,
    cell_id                  String,
    position_id              UInt8,
    lens_id                  UInt8,
    cell_mode                Enum8('ACTIVATION'=1,'TRANSFORMATION'=2),
    compare_to_position      Nullable(UInt8),
    not_applicable_condition Nullable(String),
    confidence               Enum8('ATTESTED'=1,'ANCHORED'=2,'EXTRAPOLATED'=3),
    priority_weight          UInt8
) ENGINE = MergeTree ORDER BY cell_id_num;

CREATE TABLE IF NOT EXISTS scene_diagnoses (
    project_id          UUID,
    scene_id            UUID,
    position_id         UInt8,
    cell_id_num         UInt16,
    bible_version_id    UInt32,
    verdict             Enum8('SATISFIED'=1,'GAP'=2,'NA'=3),
    input_confidence    Enum8('VALIDATED'=1,'PROVISIONAL'=2),
    diagnosed_at_micros UInt64
) ENGINE = MergeTree
ORDER BY (project_id, scene_id, cell_id_num, diagnosed_at_micros);

CREATE TABLE IF NOT EXISTS cell_slot_consumption (
    cell_id_num UInt16,
    slot_id     String
) ENGINE = MergeTree ORDER BY (slot_id, cell_id_num);

CREATE TABLE IF NOT EXISTS bible_version_changes (
    project_id       UUID,
    bible_version_id UInt32,
    changed_slots    Array(String),
    committed_at     DateTime
) ENGINE = MergeTree ORDER BY (project_id, bible_version_id);
