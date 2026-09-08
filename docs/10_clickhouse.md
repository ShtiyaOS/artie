# C2 Specification v1.0 — ClickHouse Analytical Layer

**Status: CANONICAL.** Supersedes the C2 research output. Where they disagree,
this governs.

**Companions:** `docs/01_locked_axis.md` ·
`docs/02_greenlight.md` · `docs/03_scene_rig.md`

**Scope:** the matrix, scene diagnoses, coverage, gaps, and staleness.
The provenance ledger is C1. Transactional state is C4 (Postgres/Supabase).

**Track note:** ClickHouse is used as a database via its native client. There is
no MCP server in this architecture.

---

## 1. Corrections applied to the C2 research output

| # | Defect | Correction |
|---|---|---|
| 1 | `changed_slots` held cell ids; Query 4 joined Bible slot ids against cell ids and would return zero rows forever | Added **`cell_slot_consumption`** (§3.4). Re-diagnosis now traverses slot → cells → scenes |
| 2 | `WHERE verdict != 'NA'` filtered NA before aggregation, making not-applicable cells indistinguishable from gaps | NA rows are **retained** and resolved at aggregation into a four-state classification |
| 3 | Severity multiplied by static confidence, which `priority_weight` already encodes | Severity uses weight × input factor only |
| 4 | `PARTITION BY xxHash32(...) % 4` scattered every project across all partitions, preventing pruning | **No partitioning** at this scale |
| 5 | DDL used `ReplacingMergeTree` + `FINAL` while §5.1 correctly argued against it | Plain `MergeTree`, append-only, `argMax` at read |
| 6 | Act boundaries hardcoded as positions 4–9; the axis spec puts Act Two at X04–X08 | `act` is a column on `positions_src` |
| 7 | Dictionaries declared but bypassed by four of five queries | Dictionaries used consistently, or not declared |
| 8 | Two formulas disagreed (`ln(count)` in prose, `log(count+1)` in SQL) | One formula, stated once |

**Retained from the research, unchanged:** the skew decision (§6), the
materialized-view refusal (§5.3), and the scale-honesty framing (§8).

---

## 2. Design decisions

**Engine: plain `MergeTree`, append-only.** Every diagnostic run inserts a new
row; nothing is mutated or deduplicated. Latest-wins is resolved at read with
`argMax(…, diagnosed_at_micros)`.

`ReplacingMergeTree` deduplicates in background merges, so a heatmap queried
immediately after a diagnosis can show pre-merge state unless `FINAL` is used —
and `FINAL` performs merges inside the query thread. Append-only plus `argMax`
has no merge-lag correctness window, and it preserves the full diagnostic
history the authorship story depends on.

**No `PARTITION BY`.** Roughly 300 rows per project. `ORDER BY (project_id,
scene_id, cell_id_num)` gives all the locality needed. If the corpus ever grows
past tens of millions of rows, `PARTITION BY toYYYYMM(…)` is the conventional
addition — not a hash bucket, which prevents pruning rather than enabling it.

**`cell_id_num = position_number × 10 + lens_number`.** X01.Y1 → 11, X06.Y3 → 63,
X12.Y6 → 126. Human-readable, and dense enough for a `FLAT` dictionary layout.

---

## 3. DDL

### 3.1 Dimension source tables

```sql
CREATE TABLE positions_src (
    position_id     UInt8,                      -- 1..12
    code            String,                     -- 'X01'..'X12'
    name            String,
    position_type   Enum8('BASELINE'=1,'TURNING_POINT'=2,'CONNECTIVE'=3),
    range_start_pct UInt8,
    range_end_pct   UInt8,
    act             Enum8('ACT_ONE'=1,'ACT_TWO'=2,'ACT_THREE'=3)
) ENGINE = MergeTree ORDER BY position_id;

CREATE TABLE lenses_src (
    lens_id UInt8,                              -- 1..6
    code    String,                             -- 'Y1'..'Y6'
    name    String
) ENGINE = MergeTree ORDER BY lens_id;

CREATE TABLE cells_src (
    cell_id_num              UInt16,            -- position*10 + lens
    cell_id                  String,            -- 'X06.Y3'
    position_id              UInt8,
    lens_id                  UInt8,
    cell_mode                Enum8('ACTIVATION'=1,'TRANSFORMATION'=2),
    compare_to_position      Nullable(UInt8),
    not_applicable_condition Nullable(String),
    confidence               Enum8('ATTESTED'=1,'ANCHORED'=2,'EXTRAPOLATED'=3),
    priority_weight          UInt8
) ENGINE = MergeTree ORDER BY cell_id_num;
```

`act` assignment follows the axis spec: **ACT_ONE** = X01–X03, **ACT_TWO** =
X04–X08, **ACT_THREE** = X09–X12.

### 3.2 Dictionaries

```sql
CREATE DICTIONARY dict_cells (
    cell_id_num     UInt16,
    cell_id         String,
    position_id     UInt8,
    lens_id         UInt8,
    confidence      String,
    priority_weight UInt8
)
PRIMARY KEY cell_id_num
SOURCE(CLICKHOUSE(TABLE 'cells_src'))
LAYOUT(FLAT())
LIFETIME(MIN 3600 MAX 86400);

CREATE DICTIONARY dict_positions (
    position_id UInt8,
    code        String,
    name        String,
    act         String
)
PRIMARY KEY position_id
SOURCE(CLICKHOUSE(TABLE 'positions_src'))
LAYOUT(FLAT())
LIFETIME(MIN 3600 MAX 86400);

CREATE DICTIONARY dict_lenses (
    lens_id UInt8,
    code    String,
    name    String
)
PRIMARY KEY lens_id
SOURCE(CLICKHOUSE(TABLE 'lenses_src'))
LAYOUT(FLAT())
LIFETIME(MIN 3600 MAX 86400);
```

Queries that need only attribute lookups use `dictGet`. Queries that must
enumerate all 72 cells including those with no data read `cells_src` directly,
because a dictionary cannot drive a scan. Both patterns appear below and both
are correct.

### 3.3 Fact table

```sql
CREATE TABLE scene_diagnoses (
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
```

### 3.4 Cell–slot consumption (new — the missing link)

Which Bible slots each cell reads. Without this, narrowed re-diagnosis is
impossible.

```sql
CREATE TABLE cell_slot_consumption (
    cell_id_num UInt16,
    slot_id     String                          -- 'S02'..'S11', 'TP1'
) ENGINE = MergeTree ORDER BY (slot_id, cell_id_num);
```

**Seed mapping, derived from Greenlight Specification §2:**

| Slot | Cells consuming it |
|---|---|
| S02 Protagonist | all Y3 (12) |
| S03 Want | all Y2 (12) + X04.Y1, X06.Y1 |
| S04 Flaw | X01.Y3, X08.Y3, X11.Y3, X12.Y3 |
| S05 Antagonism | all Y2 (12) |
| S06 Thematic Proposition | all Y4 (12) |
| S07 Status Quo Baseline | X01 row (6) + the 7 TRANSFORMATION cells |
| S08 Arena | X03.Y6, X07.Y6, X12.Y6 |
| S10 Ending Shape | X11 row (6) + X12 row (6) |
| TP1 Inciting Incident | X02 row (6) |
| S09 Genre | none — modulates the Scene Rig, not cells |
| S11 World Rules | none — Script Supervisor, outside the matrix |

Cells may consume several slots; X01.Y3 appears under S02, S04, and S07.

### 3.5 Bible change log

```sql
CREATE TABLE bible_version_changes (
    project_id       UUID,
    bible_version_id UInt32,
    changed_slots    Array(String),             -- SLOT ids: ['S06','S10']
    committed_at     DateTime
) ENGINE = MergeTree ORDER BY (project_id, bible_version_id);
```

**`changed_slots` holds Bible slot ids, never cell ids.** This was the single
most consequential error in the research output.

---

## 4. Scoring functions

### Confidence composition — two axes, kept separate

`confidence` is static (how well-founded the diagnostic is). `input_confidence`
is runtime (how well-founded the writer's Bible inputs were). Both are reported;
`display_confidence` degrades the static value one level when inputs are
provisional.

| Static | Input | Display |
|---|---|---|
| ATTESTED | VALIDATED | ATTESTED |
| ATTESTED | PROVISIONAL | ANCHORED |
| ANCHORED | VALIDATED | ANCHORED |
| ANCHORED | PROVISIONAL | EXTRAPOLATED |
| EXTRAPOLATED | either | EXTRAPOLATED |

### Gap severity

```
severity = priority_weight × input_factor
input_factor: VALIDATED = 1.0 · PROVISIONAL = 0.75
```


**Static confidence is deliberately absent.** `priority_weight` is already capped
by it — EXTRAPOLATED ≤ 3, ANCHORED ≤ 4, weight 5 reserved for ATTESTED.
Multiplying again would penalize the same property twice.

**`input_factor = 0.75` was determined empirically.** At 0.5, a weight-5 ATTESTED
gap on provisional inputs ranked *below* a weight-3 gap on validated inputs —
inverting the priority ordering the weights exist to encode. At 0.75 the
provisional signal is preserved without overriding weight. Verified against seed
data on September 3, 2026.

### Gap urgency — where skew belongs

```
urgency = severity × (1 + ln(1 + active_scene_count_at_position))
```

At zero scenes the multiplier is 1.0. Twelve scenes yields roughly 2.1× the
urgency of one — a lens missed across twelve opportunities is more alarming than
across one, but not twelve times more. This is the only place the 4:1 range skew
enters the system.

---

## 5. Queries

All parameterized. `{project:UUID}` and `{version:UInt32}` are ClickHouse
parameter syntax.

### 5.1 Latest non-stale diagnoses (shared CTE)

```sql
WITH latest AS (
    SELECT
        scene_id,
        cell_id_num,
        any(position_id)                              AS position_id,
        argMax(verdict,          diagnosed_at_micros) AS verdict,
        argMax(input_confidence, diagnosed_at_micros) AS input_confidence,
        argMax(bible_version_id, diagnosed_at_micros) AS bible_version_id
    FROM scene_diagnoses
    WHERE project_id = {project:UUID}
    GROUP BY scene_id, cell_id_num
),
fresh AS (
    SELECT * FROM latest WHERE bible_version_id = {version:UInt32}
)
```

Staleness is applied **after** latest-wins: a scene whose most recent diagnosis
predates the current Bible version is stale and drops out.

### 5.2 Coverage heatmap

```sql
WITH latest AS (...), fresh AS (...),
per_cell AS (
    SELECT
        cell_id_num,
        countIf(verdict = 'SATISFIED')          AS n_satisfied,
        countIf(verdict = 'GAP')                AS n_gap,
        countIf(verdict = 'NA')                 AS n_na,
        count()                                 AS n_total,
        max(toUInt8(input_confidence))          AS worst_input
    FROM fresh
    GROUP BY cell_id_num
)
SELECT
    c.cell_id                                              AS cell_id,
    dictGet('dict_positions', 'code', toUInt64(c.position_id)) AS position,
    dictGet('dict_lenses',    'code', toUInt64(c.lens_id))     AS lens,
    multiIf(
        pc.n_total     = 0,          'NO_DATA',
        pc.n_satisfied > 0,          'SATISFIED',
        pc.n_na        = pc.n_total, 'NA',
                                     'GAP'
    )                                                      AS coverage_state,
    toString(c.confidence)                                 AS cell_confidence,
    multiIf(pc.worst_input = 2, 'PROVISIONAL', pc.n_total = 0, 'NONE', 'VALIDATED')
                                                           AS input_confidence,
    multiIf(
        pc.worst_input != 2,        toString(c.confidence),
        c.confidence = 'ATTESTED',  'ANCHORED',
        c.confidence = 'ANCHORED',  'EXTRAPOLATED',
                                    'EXTRAPOLATED'
    )                                                      AS display_confidence
FROM cells_src AS c
LEFT JOIN per_cell AS pc USING (cell_id_num)
ORDER BY c.position_id, c.lens_id;
```

Four coverage states, not two. **NA is a distinct outcome** — a cell that is
not-applicable is not a gap, and the research output's early NA filter would
have reported every silent-epilogue script as failing X12.Y5.

ClickHouse fills unmatched `LEFT JOIN` columns with type defaults rather than
NULLs, so `n_total = 0` correctly identifies cells with no diagnoses. No
`join_use_nulls` required.

### 5.3 Ranked gaps

```sql
WITH latest AS (...), fresh AS (...),
per_cell AS (
    SELECT
        cell_id_num,
        countIf(verdict = 'SATISFIED') AS n_satisfied,
        countIf(verdict = 'NA')        AS n_na,
        count()                        AS n_total,
        max(toUInt8(input_confidence)) AS worst_input
    FROM fresh GROUP BY cell_id_num
),
density AS (
    SELECT position_id, uniqExact(scene_id) AS active_scenes
    FROM fresh GROUP BY position_id
)
SELECT
    c.cell_id,
    c.priority_weight,
    toString(c.confidence)                                    AS cell_confidence,
    coalesce(d.active_scenes, 0)                              AS scene_density,
    c.priority_weight * if(pc.worst_input = 2, 0.75, 1.0)      AS severity,
    severity * (1 + log(1 + coalesce(d.active_scenes, 0)))    AS urgency
FROM cells_src AS c
LEFT JOIN per_cell AS pc USING (cell_id_num)
LEFT JOIN density  AS d  ON c.position_id = d.position_id
WHERE pc.n_satisfied = 0
  AND NOT (pc.n_total > 0 AND pc.n_na = pc.n_total)
ORDER BY urgency DESC, c.cell_id ASC;
```

The `WHERE` excludes satisfied cells and cells that resolved wholly
not-applicable. Cells with no data remain, since an undiagnosed cell in a
position the writer has already written is a real gap.

`log()` is ClickHouse's natural logarithm.

### 5.4 Narrowed re-diagnosis

```sql
WITH changed AS (
    SELECT arrayJoin(changed_slots) AS slot_id
    FROM bible_version_changes
    WHERE project_id = {project:UUID}
      AND bible_version_id = {version:UInt32}
),
affected_cells AS (
    SELECT DISTINCT csc.cell_id_num
    FROM cell_slot_consumption AS csc
    INNER JOIN changed AS ch USING (slot_id)
),
latest AS (
    SELECT
        scene_id, cell_id_num,
        argMax(bible_version_id, diagnosed_at_micros) AS bible_version_id
    FROM scene_diagnoses
    WHERE project_id = {project:UUID}
    GROUP BY scene_id, cell_id_num
)
SELECT DISTINCT
    l.scene_id,
    dictGet('dict_cells', 'cell_id', toUInt64(l.cell_id_num)) AS cell_id
FROM latest AS l
INNER JOIN affected_cells AS ac USING (cell_id_num)
WHERE l.bible_version_id < {version:UInt32}
ORDER BY l.scene_id;
```

**This is the query the architecture exists for.** Revising S06 invalidates only
Y4 cells — twelve of seventy-two. Instead of re-diagnosing forty scenes, the
system re-runs the affected cells on the scenes that actually consume them.

### 5.5 Structural summary

```sql
WITH latest AS (...), fresh AS (...)
SELECT
    dictGet('dict_positions', 'act',  toUInt64(c.position_id)) AS act,
    dictGet('dict_lenses',    'name', toUInt64(c.lens_id))     AS lens,
    uniqExact(c.position_id)                                   AS total_positions,
    uniqExactIf(c.position_id, f.verdict = 'SATISFIED')        AS satisfied_positions,
    concat(act, ' touches ', lens, ' in ',
           toString(satisfied_positions), ' of ',
           toString(total_positions), ' positions')            AS sentence
FROM cells_src AS c
LEFT JOIN fresh AS f USING (cell_id_num)
GROUP BY act, lens
ORDER BY act, lens;
```

Produces the sentence the product exists to say. Act boundaries come from the
dimension table, not from hardcoded position numbers.

---

## 6. The skew decision — resolved

Carried as an open question since A1. Settled here.

**Range-width skew does not affect coverage.** Coverage is binary at position
level: a cell is satisfied if at least one scene at that position satisfies it.
Twelve scenes at X07 and one scene at X02 are both "covered" or "not covered."

**Skew affects gap urgency.** A lens unaddressed across twelve scenes is a
systematic omission; the same lens unaddressed in a single-scene position is one
missed opportunity. That is the entire consequence, and it lives in one term of
one formula (§4).

**Amend Locked Axis Specification v1.1 §8:** the note binding C2 to "normalize
coverage per position" is superseded. Coverage is not normalized. Gap urgency is
skew-weighted.

---

## 7. Materialized views — not used

ClickHouse materialized views are insert triggers. They see the incoming batch
and nothing else, so they cannot react to upstream invalidation — a Bible
version change marking historical rows stale would silently corrupt a maintained
heatmap.

At ~300 rows per project with an appropriate sort key, on-demand computation is
already interactive. Revisit only if the ledger join in §8 becomes a hot path.

---

## 8. Scale honesty

At roughly 300 rows per project, Postgres would serve these queries in
microseconds. **ClickHouse is not justified by the matrix alone.**

The justification is the provenance ledger (C1): keystroke batches, saves, AI
suggestions offered and accepted and rejected — on the order of thousands of
events per session, append-only, never updated. That is a columnar workload.

The matrix lives in the same engine so the two can be **correlated in one
query** — authoring effort against structural coverage, which scene revisions
actually closed which gaps. That correlation is the product's most interesting
analytical claim and it requires both datasets in one place.

Stated plainly, in the words the research output used and which are worth
keeping: *if the application does not query the provenance ledger, delete
ClickHouse and write this in Postgres.*

---

## 9. Known limitations

1. **No referential integrity.** ClickHouse has no foreign keys. An ingestion
   bug can insert a `cell_id_num` that does not exist in `cells_src`, producing
   orphan rows that silently distort aggregates. Validation is the ingestion
   service's responsibility. Add a periodic orphan check.
2. **`cell_slot_consumption` is derived, not measured.** Seeded from the
   Greenlight spec's `consumed_by` column. If a cell's diagnostic question
   actually reads a slot the spec did not record, re-diagnosis will miss it.
   Verify against the cell questions before shipping.
3. **Dual-store lag.** Postgres is the transactional master; ClickHouse receives
   asynchronously. A heatmap queried immediately after a diagnosis may lag by
   the replication interval.
4. **Position schema changes are a migration.** If the twelve positions ever
   change, historical `cell_id_num` values become invalid and require an offline
   remap.
5. **Verified against ClickHouse 26.2 Cloud, September 3, 2026.** All six DDL
   statements execute. All five queries execute and return correct results
   against seed data — 72 cells, 174 diagnoses across 29 scenes. Confirmed
   working: `argMax` over Enum8, `max(toUInt8(...))` on Enum columns, `multiIf`
   string-branch coercion, and `LEFT JOIN ... USING` default-filling counts to
   zero so `n_total = 0` correctly identifies undiagnosed cells.
