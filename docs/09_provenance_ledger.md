# C1 Specification v1.0 — The Provenance Ledger

**Status: CANONICAL.**

**Companions:** `docs/04_agent_roster.md` ·
`docs/05_orchestration.md` · `docs/10_clickhouse.md` ·
`docs/02_greenlight.md`

**Downstream consumers:** D2 (manifest export), C4 (Supabase boundary).

**Track note.** Confluent is the ingestion path. It is also the one IBM-track
technology that is imported and called at runtime, which satisfies Section 7B's
general requirement that a Bob-only submission leaves exposed. This is not the
reason it is here — it is the right architecture for an append-only event stream —
but it is a useful coincidence.

---

## 1. What the ledger proves

Three claims, and every design decision below serves one of them.

**Claim 1 — the screenplay text was typed by a human.**
Keystroke batches with content hashes form a verifiable chain from empty document
to final script. Paste events are logged with origin and size.

**Claim 2 — the AI never supplied screenplay content.**
This is the interesting one. The ledger does not merely record *that* an agent
spoke; it records **what the agent said, in full**. Every question Artie asked,
every finding delivered, every curated example shown, every deliberation trace.
Those payloads are inspectable, and an auditor can verify that no story content
was ever offered.

That is categorically stronger than *we promise the AI didn't write it.*

**Claim 3 — the writer's intent developed over time.**
Bible versions show what the writer believed the story was at scene 12 versus
scene 40. Evolving intent is a signature of human authorship — a machine does not
change its mind at scene 40 and revise backward.

**Binding consequence: agent event payloads are stored in full, never
summarized.** A summary would destroy the evidence. Storage is trivial at this
volume and the payloads are the product's central claim.

---

## 2. Event envelope

Per 05_orchestration.md §2, unchanged.

```json
{
  "event_id": "uuid",
  "event_type": "SCENE_SAVED",
  "project_id": "uuid",
  "scene_id": "uuid | null",
  "bible_version_id": 5,
  "actor": "human | artie | supervisor | director | system",
  "ts_micros": 1788422648388531,
  "payload": { }
}
```

**Partition key: `scene_id`**, falling back to `project_id`. Confluent guarantees
per-partition ordering, so a scene's events arrive in the order they occurred.

---

## 3. Event taxonomy

### 3.1 Authorship events — `actor: human`

| Event | Payload | Proves |
|---|---|---|
| `KEYSTROKE_BATCH` | see §5 — never the characters themselves | Claim 1 |
| `PASTE` | `origin`, `char_count`, `target_component_id` | Claim 1 |
| `COMPONENT_INSERTED` | `component_type`, `scene_id` | Human chose the structure |
| `SCENE_SAVED` | `scene_id`, `content_hash`, `char_count` | Chain checkpoint |
| `SCENE_DELETED` | `scene_id`, `content_hash` | Chain continuity |
| `SLOT_ANSWERED` | `slot_id`, `value`, `attempt_number` | The writer's own words filled the slot |
| `CONTINUITY_CHECK_REQUESTED` | `scenes_covered`, `tiers_run` | The writer asked to be checked |

`SLOT_ANSWERED` stores the value **because it is the writer's text**, and because
the Bible is authored material.

### 3.2 Agent events — `actor: artie | supervisor | director`

**Stored in full. These payloads are the evidence for Claim 2.**

| Event | Actor | Payload |
|---|---|---|
| `AGENT_QUESTION` | artie | `slot_id`, `question_text`, `reask_move`, `attempt_number` |
| `AGENT_FINDING_DELIVERED` | artie | `cell_id`, `display_confidence`, `priority_weight`, `delivered_text` |
| `AGENT_EXAMPLE_SHOWN` | artie | `example_id`, `library_version`, `full_text` |
| `AGENT_STORY_TOLD` | artie | `story_id`, `attribution_mode`, `full_text` |
| `AGENT_REFUSAL` | artie | `refusal_type`, `trigger`, `response_text` |
| `AI_DELIBERATION` | artie | active axes, both poles with strengths, synthesis decision, `hold` list |
| `SCENE_DIAGNOSED` | supervisor | full `cell_verdicts` array |
| `CANON_FINDING` | supervisor | `rule_id`, `rule_type`, `status`, `detail` |
| `FRAME_PROMPT_CONSTRUCTED` | director | `source_action_lines`, `constructed_prompt`, transformations applied |
| `FRAME_GENERATED` | director | `asset_uri`, `model`, `finish_reason`, `assumption_note` |
| `AGENT_BEACON_LEFT` | artie | scene, position, declared Rig slots, active component type |
| `CONTINUITY_FINDINGS_DELIVERED` | supervisor | full findings array with citations |

**`AGENT_EXAMPLE_SHOWN` and `AGENT_STORY_TOLD` carry `library_version`.** Because
both libraries are static files, the ledger can prove which exact file was in
force — the claim *the system has never generated a story or an example* becomes
verifiable rather than asserted.

**`AI_DELIBERATION` is unusually load-bearing.** It records that the system
reasoned about *how to respond* and demonstrably not about *what to write* — the
pole outputs are on record and contain no story content. It is evidence, not
telemetry.

**`FRAME_PROMPT_CONSTRUCTED` records the isolation rule holding.** The payload
shows the prompt derived only from Action lines, which is auditable against 04_agent_roster.md §5.

### 3.3 State events — `actor: system`

| Event | Payload |
|---|---|
| `SESSION_OPENED` / `SESSION_CLOSED` | `session_id`, opening slug line |
| `BIBLE_VERSION_CREATED` | `bible_version_id`, `changed_slots`, `change_reason` |
| `SLOT_PROVISIONAL` | `slot_id`, `reask_count`, failure mode |
| `COMMITMENT_CHANGED` | `from_state`, `to_state`, validated slot count |
| `SCENE_STALE_MARKED` | `scene_id`, `diagnosed_against`, `current_version` |
| `MANIFEST_EXPORTED` / `SCRIPT_EXPORTED` | `format`, `content_hash` |

---

## 4. Attribution — the `actor` field

**This field is the entire authorship claim.** It must be correct on every event
without exception, and it must be set by the emitting code path, never inferred
downstream.

| Actor | Means |
|---|---|
| `human` | The writer performed this. Typing, pasting, saving, answering. |
| `artie` | The orchestrating agent spoke or reasoned. |
| `supervisor` | The diagnostic agent judged. |
| `director` | The visualization agent produced. |
| `system` | Deterministic code with no model involvement — state transitions, exports, version creation. |

**`system` is not a catch-all.** If a model was involved, the actor is the agent
that ran it. Misattributing a model call as `system` would understate AI
involvement in the manifest, which is the precise failure the ledger exists to
prevent.

---

## 5. Keystroke batching

Raw per-keystroke capture is high-volume, invasive, and — because per-keystroke
timing enables behavioral biometric fingerprinting — more personal data than this
system has any business holding.

### Batching rule

A batch closes on **2 seconds of inactivity** or **200 characters**, whichever
comes first.

### What is stored, and what is not

```
project_id · scene_id · component_id
ts_start_micros · ts_end_micros
char_delta        (net characters added or removed)
content_hash      (SHA-256 of the component after this batch)
```

**The characters themselves are never stored in the ledger.** The text lives in
Supabase; duplicating it here would double the exposure surface for no gain.

### Why hashes prove authorship

The sequence of `content_hash` values forms a **chain**. Each batch's hash is the
state of the component after that batch. The final hash must equal the hash of
the exported script.

An auditor can therefore verify that the delivered screenplay is the terminus of
a continuous sequence of human-attributed edits — without the ledger ever holding
a second copy of the text.

Any break in the chain — a hash that does not follow from its predecessor —
indicates content arrived by some path other than typing. That is a detection
mechanism, not a prevention mechanism, which is the correct posture.

---

## 6. Paste events

**Paste is logged, never blocked.** Blocking is theatre and it breaks screen
readers, voice input, motor accessibility, and the legitimate case of moving a
line between scenes.

```
origin: INTERNAL | UNKNOWN
char_count: int
target_component_id: uuid
```

### On `origin`, and why there is no `EXTERNAL`

The browser clipboard API does not reliably report a source. What the application
*can* know is what it put on the clipboard itself.

So: content matching a recent application-originated copy is `INTERNAL`.
Everything else is **`UNKNOWN`**, not `EXTERNAL`.

That distinction is deliberate and it is the honest one. **We cannot prove content
came from outside; we can only fail to prove it came from inside.** A manifest
claiming `EXTERNAL` would be asserting something the system did not observe, and
overclaiming in an evidentiary document is worse than the gap it papers over.

Artie's response to a large `UNKNOWN` paste is specified in 07_artie_persona.md §9.2: he
notices, states the consequence, and never accuses.

---

## 7. Confluent topology

**Single topic: `authorship.events`.** Partition key `scene_id`, falling back to
`project_id`.

At this scale — one writer, a few thousand events per project — a single topic is
correct. Splitting keystroke batches into their own topic would decouple retention
but would also split a scene's event stream across topics and complicate ordering
for no present benefit.

**Scaling path, if volume ever demands it:** split to `authorship.keystrokes`
with shorter retention, keeping semantic events on the long-retention topic.

### Retention

**7 days on the topic.** ClickHouse is the durable store; topic retention only
needs to cover consumer downtime. Seven days is generous for that.

### Delivery semantics

At-least-once. The consumer commits offsets **after** a successful ClickHouse
insert, so a crash between insert and commit produces a duplicate on restart.

**Duplicates are tolerated, not prevented.** `event_id` is generated at production
time, so any query that counts must use `uniqExact(event_id)`. This is preferable
to a deduplicating table engine — the ledger is append-only by nature, and a
duplicate is visible and explicable where a silent merge is neither.

---

## 8. The consumer

**Primary: a Python consumer using `confluent-kafka`,** already verified working
against this cluster. It reads the topic, routes by `event_type`, and batch-inserts
into ClickHouse via `clickhouse-connect`.

Batch on 500 events or 5 seconds, whichever first. Row-by-row inserts into
ClickHouse are an anti-pattern.

**`[VERIFY]` — the better answer, if available.** ClickHouse's native Kafka table
engine consumes directly, eliminating the consumer process entirely, and would be
a stronger technical story in the demo. Whether it is enabled on ClickHouse Cloud
is unconfirmed. **Check it; if available, upgrade. If not, the Python consumer
ships.** Do not spend a build day discovering it is unavailable.

---

## 9. ClickHouse schema

Two tables. Different shapes, different volumes, different query patterns.

```sql
CREATE TABLE provenance_events (
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

CREATE TABLE keystroke_batches (
    project_id      UUID,
    scene_id        UUID,
    component_id    UUID,
    ts_start_micros UInt64,
    ts_end_micros   UInt64,
    char_delta      Int32,
    content_hash    String
) ENGINE = MergeTree
ORDER BY (project_id, scene_id, ts_start_micros);
```

**`LowCardinality(String)` on `event_type`** is the idiomatic ClickHouse treatment
for a small closed set of strings — dictionary-encoded, and it keeps the taxonomy
extensible without a schema migration.

**`payload` is `String` holding JSON**, extracted with `JSONExtract*` functions.
ClickHouse's native JSON type has been through several iterations; `String` plus
extraction is the safe choice and it costs nothing at this volume. **`[VERIFY]`
whether the current JSON type is stable enough to prefer.**

**No `actor` column on `keystroke_batches`.** A keystroke batch is human by
definition. Adding the column would imply the possibility of a non-human one,
which is exactly what this table exists to deny.

No partitioning, consistent with 10_clickhouse.md §2.

---

## 10. Correlation queries — what justifies ClickHouse

10_clickhouse.md §8 conceded that the matrix alone does not justify a columnar engine. **These
queries are the justification**, and they require both datasets in one place.

### 10.1 Effort against structural improvement

```sql
SELECT
    kb.scene_id,
    sum(abs(kb.char_delta))                             AS chars_worked,
    (max(kb.ts_end_micros) - min(kb.ts_start_micros)) / 1e6 AS seconds_elapsed,
    countIf(sd.verdict = 'SATISFIED')                   AS cells_satisfied
FROM keystroke_batches AS kb
LEFT JOIN scene_diagnoses AS sd USING (scene_id)
WHERE kb.project_id = {project:UUID}
GROUP BY kb.scene_id
ORDER BY chars_worked DESC
```

*Which scenes cost the most effort, and did that effort close gaps?* No other
tool in this space can answer that, because no other tool holds both streams.

### 10.2 Did the writer act on the note?

```sql
WITH findings AS (
    SELECT scene_id,
           JSONExtractString(payload, 'cell_id') AS cell_id,
           ts_micros                             AS delivered_at
    FROM provenance_events
    WHERE project_id = {project:UUID}
      AND event_type = 'AGENT_FINDING_DELIVERED'
)
SELECT f.cell_id,
       f.delivered_at,
       min(kb.ts_start_micros) AS first_edit_after,
       (first_edit_after - f.delivered_at) / 1e6 AS seconds_to_action
FROM findings AS f
LEFT JOIN keystroke_batches AS kb
       ON kb.scene_id = f.scene_id
      AND kb.ts_start_micros > f.delivered_at
GROUP BY f.cell_id, f.delivered_at
ORDER BY seconds_to_action ASC
```

*Which notes landed?* Directly measures whether Artie is useful, and it is the
kind of question the deliberation engine should eventually learn from.

### 10.3 Authorship composition — feeds the manifest

```sql
SELECT actor, event_type, uniqExact(event_id) AS n
FROM provenance_events
WHERE project_id = {project:UUID}
GROUP BY actor, event_type
ORDER BY actor, n DESC
```

---

## 11. Privacy

The ledger records how a person works. That deserves restraint.

| Decision | Reason |
|---|---|
| Never store keystroke characters | The text lives in Supabase; a second copy doubles exposure for nothing |
| Batch at 2s / 200 chars | Per-keystroke timing enables behavioral biometric fingerprinting. Batch granularity does not. |
| No `EXTERNAL` paste label | The system did not observe it (§6) |
| Manifest is user-exported | The writer decides who sees it. It is their evidence. |

**Do not add per-keystroke timing later for a "better" chain.** The hash chain
already proves what needs proving, and finer timing would collect biometric data
this product has no reason to hold.

---

## 12. Failure modes

| Failure | Behavior |
|---|---|
| Consumer down | Events accumulate on the topic. Offsets resume on restart. 7-day retention covers realistic downtime. |
| ClickHouse insert fails | Do not commit the offset. The batch is redelivered. Duplicates are visible and deduped at query. |
| Confluent unreachable at produce time | **Buffer locally and retry.** Never drop an authorship event. A gap in the chain is worse than latency. |
| Hash chain break | Surfaced in the manifest as a discontinuity. Not blocked, not hidden. Detection, not prevention. |

The buffer-on-unreachable rule matters more than it looks: **an event that is
never produced cannot be reconstructed**, and the chain it belonged to is
permanently weakened.

---

## 13. Open items

1. **Kafka table engine availability on ClickHouse Cloud is unverified** (§8).
   Check early; do not build around it before confirming.
2. **The JSON column type decision is unverified** (§9). `String` ships.
3. **Hash chain verification is unimplemented.** The chain is recorded but nothing
   walks it. D2 needs a verifier for the manifest, and it should run at export
   rather than continuously.
4. **Clipboard origin matching is unspecified in detail.** How long an
   application-originated copy remains matchable, and how matching is performed,
   belongs to the editor session.
5. **`AGENT_FINDING_DELIVERED` stores `delivered_text`,** which is Artie's phrasing
   of a finding. It contains no screenplay prose by construction (04_agent_roster.md §1.1) — but
   there should be an assertion confirming that, since the payload is evidence
   for Claim 2 and a leak there would undermine it.
6. **Session boundary definition.** What closes a session — explicit logout, a
   timeout, a tab close — is undefined, and `SESSION_CLOSED` needs one.
