# B2 Specification v1.0 — Orchestration, Handoff, and Shared State

**Status: CANONICAL.**

**Companions:** `docs/04_agent_roster.md` ·
`docs/02_greenlight.md` · `docs/03_scene_rig.md` ·
`docs/10_clickhouse.md`

**Downstream consumers:** C1 (ledger), C4 (Supabase), D2 (manifest), F1 (deploy).

**Amends:** Greenlight Specification v1.1 §12 — see §3.4.

---

## 1. Topology — the backend orchestrates, not Artie

### The decision

**Artie is not the parent of any other agent.** The three agents are peers,
invoked independently by the backend. ADK workflow agents are used *inside*
the Supervisor and the Director, never across the top level.

### Why, and this is forced rather than chosen

04_agent_roster.md §1.1 holds that Artie never reads screenplay text, and that the firewall is a
property of the wiring rather than an instruction.

If the Supervisor were an ADK `sub_agent` of Artie, ADK's delegation passes the
`InvocationContext` — including session state and the triggering message —
down the tree. Scene prose would necessarily transit Artie's context to reach
the Supervisor. **The delegation mechanism would silently break the firewall.**

So the top level is flat. The backend receives events and calls
`Runner.run_async` against whichever agent owns that event, each with its own
session. Artie's session never contains prose because nothing ever puts it there.

This is still a multi-agent network in the sense that matters: agents trigger
each other through events and write to shared state. It is simply
**event-driven rather than LLM-routed**, which is also more deterministic — and
determinism is what the brief asks for.

### Where ADK workflow agents do get used

| Composite | Type | Pipeline |
|---|---|---|
| **Supervisor** | `SequentialAgent` | canon check → cell judgments → verdict assembly |
| **Director** | `SequentialAgent` | prompt construction → image generation → assumption note |
| **Artie** | `LlmAgent`, no sub-agents | tools only |

Genuine ADK workflow usage, contained inside two agents whose inputs are already
scoped, so no boundary is crossed.

```
                    ┌──────────────┐
   user turn ──────►│              │
   findings  ──────►│    ARTIE     │──► conversational output
   coverage  ──────►│  (LlmAgent)  │    slot writes
                    └──────────────┘
                           ▲
                           │ findings only (never prose)
                    ┌──────┴───────────────────────────┐
                    │          BACKEND                 │
                    │  event router · Runner.run_async │
                    └──────┬────────────────────┬──────┘
                           │ scene prose        │ action lines
                    ┌──────▼──────┐      ┌──────▼──────┐
                    │ SUPERVISOR  │      │  DIRECTOR   │
                    │ Sequential  │      │ Sequential  │
                    └─────────────┘      └─────────────┘
```

---

## 2. Event envelope

Every event on the Confluent topic shares one envelope. C1 owns the full
taxonomy; this is the contract all producers honor.

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

**Partition key: `scene_id`**, falling back to `project_id` when null. Confluent
guarantees per-partition ordering, so all events for a scene arrive in the order
they occurred. The provenance ledger depends on this.

**`actor` is the field D2's manifest is built on.** It must be accurate on every
event without exception — it is the difference between *the human wrote this* and
*the machine produced this*, and it is the evidence the whole authorship claim
rests on.

---

## 3. State partitioning

Three stores, three jobs. Writing to the wrong one is a defect, not a preference.

### 3.1 `session.state` — ephemeral

ADK working state for a single invocation. Serializable values only: strings,
numbers, booleans, simple lists and dicts.

Holds the current gate, which slots remain empty, the re-ask attempt counter.
**Nothing here is durable.** Anything that must survive a restart belongs below.

### 3.2 Supabase — transactional truth

Read on nearly every turn, so it must be fast.

Projects · scenes · live script text · **current** Bible slot values · roster ·
locations · current `bible_version_id` per project.

### 3.3 ClickHouse — append-only analytical

Never read on the interaction path.

Scene diagnoses · provenance ledger · Bible version history · coverage and gap
queries · the narrowed re-diagnosis query.

### 3.4 The Bible lives in both — amendment to 02_greenlight.md §12

Greenlight Specification v1.1 §12 placed `bible_versions` and `bible_slots` in
ClickHouse. That is half right and needs splitting.

| Store | Holds | Why |
|---|---|---|
| **Supabase** | Current slot values, current version id | Read on every Rig turn; needs single-row latency |
| **ClickHouse** | Full version history, `changed_slots` per version | Append-only; feeds staleness and narrowed re-diagnosis |

Every slot write does both: **upsert current state to Supabase, publish an append
event to Confluent** which lands in ClickHouse. Standard CQRS, and it is the same
two-engine argument the architecture already makes.

---

## 4. Trigger map

| Trigger | Event | Invokes | Consumes |
|---|---|---|---|
| Writer saves a scene | `SCENE_SAVED` | **Supervisor** | scene prose, Bible, 6 cells at declared position |
| Supervisor completes | `SCENE_DIAGNOSED` | **Artie** (notification) | structured findings only |
| Canon rule breached or untriggered | `CANON_FINDING` | **Artie** (notification) | rule id, status, detail |
| Writer revises a Bible slot | `BIBLE_VERSION_CREATED` | **backend** → re-diagnosis queue | `changed_slots` |
| Writer clicks *Board This Scene* | `BOARD_REQUESTED` | **Director** | Action lines only |
| Director completes | `FRAME_GENERATED` | **Artie** (notification) | assumption note, asset uri |
| Async slot judgment fails | `SLOT_JUDGMENT_FAILED` | queued for Artie | slot id, failure mode |
| Writer turn | — | **Artie** directly | Bible, Rig slots, queued notifications |

Artie is never invoked *by* another agent. He is invoked by the backend, with
findings already in hand.

---

## 5. Handoff contracts

Typed payloads. Any field not listed is a defect.

### 5.1 Backend → Supervisor

```json
{
  "scene_id": "uuid",
  "position_id": 6,
  "scene_text": "<full scene, Fountain source>",
  "bible_version_id": 5,
  "bible_slots": { "S02": ..., "S04": ..., "S11": [...] },
  "cells": [ { "cell_id": "X06.Y1", "cell_mode": "ACTIVATION",
               "diagnostic_question": "...", "satisfaction_criteria": "...",
               "consumes_slots": ["S03"] }, ... ],
  "rig_slots": { "N03": ..., "N05": {...} }
}
```

### 5.2 Supervisor → Backend

Per 04_agent_roster.md §4. Structured verdicts and canon findings. **No prose, no suggestions,
no proposed corrections.**

### 5.3 Backend → Artie

**The critical contract. Note what is absent.**

```json
{
  "project_id": "uuid",
  "gate": "GREENLIGHT | SCENE_RIG | REVIEW",
  "bible_slots": { },
  "rig_slots": { },
  "pending_findings": [
    { "cell_id": "X06.Y2", "verdict": "GAP",
      "cell_confidence": "ATTESTED", "input_confidence": "VALIDATED",
      "display_confidence": "ATTESTED", "priority_weight": 5,
      "failure_signature": "<from the cell definition>" }
  ],
  "canon_findings": [ ],
  "coverage_summary": { },
  "user_message": "<the writer's current turn>"
}
```

**There is no `scene_text` field. There is no `evidence` field.** The Supervisor's
`evidence` — which points at spans of the writer's prose — is stripped at the
backend boundary and never forwarded.

Artie speaks about a cell's `failure_signature`, which is craft language written
into the matrix at design time, not about the writer's actual sentences.

### 5.4 Backend → Director

```json
{
  "scene_id": "uuid",
  "action_lines": ["<Action elements only, dialogue excluded>"],
  "character_refs": [ { "name": "...", "canonical_frame_uri": "..." } ]
}
```

No Bible. No Rig slots. No dialogue. Per 04_agent_roster.md §5's isolation rule.

`character_refs` is the only enrichment permitted, and only because it carries
prior *generated* frames rather than story information.

---

## 6. Enforcing the reading boundary

04_agent_roster.md §10.1 flagged that §1.1 is only true if the wiring makes it true. Here is the
mechanism.

**A guard runs before every Artie invocation and raises rather than strips.**

```python
FORBIDDEN_KEYS = {"scene_text", "script", "prose", "evidence",
                  "action_lines", "dialogue", "draft", "content"}

def assert_no_prose(payload: dict, path: str = "") -> None:
    for k, v in payload.items():
        here = f"{path}.{k}" if path else k
        if k in FORBIDDEN_KEYS:
            raise FirewallBreach(f"Prose field '{here}' reached Artie's payload")
        if isinstance(v, dict):
            assert_no_prose(v, here)
        if isinstance(v, list):
            for i, item in enumerate(v):
                if isinstance(item, dict):
                    assert_no_prose(item, f"{here}[{i}]")
```

**It must raise, never sanitize.** A silent strip would let the wiring drift and
the firewall would erode without anyone noticing. A loud failure surfaces the
regression the moment it is introduced.

This function is also a demo artifact. *Here is the assertion that fails if the
screenplay ever reaches the agent you talk to* is a stronger claim than any
paragraph of policy.

---

## 7. Conflict resolution

| Conflict | Resolution |
|---|---|
| Supervisor says GAP; the writer's Rig slot declared the opposite | **Execution wins for the verdict; intent is preserved as the comparison target.** This is not a conflict but the ANCHORED model working — the finding is precisely *"this contradicts what you told me you were doing."* |
| Canon finding and coverage gap on one scene | Both reported. **Canon first.** A hard error the writer created for themselves outranks a note. |
| Two diagnoses of the same scene-cell | `argMax(diagnosed_at_micros)` — latest wins, history preserved. Already in 10_clickhouse.md §5.1. |
| Director's frame contradicts a Bible fact | **Not a conflict.** The Director does not read the Bible by design. Divergence is the diagnostic reporting that the page did not say what the writer believed it said. |
| Two findings compete for the same conversational turn | Artie's deliberation decides. Not a data problem. |

---

## 8. Async judgment surfacing

The Scene Rig accepts on RULE checks and judges asynchronously (03_scene_rig.md §4).
A failed judgment must reach the writer without becoming the wall accept-first
removed.

**Queue it. Deliver at the next natural pause — scene completion, never mid-draft.**

`SLOT_JUDGMENT_FAILED` enters a per-project queue. On the next scene-completion
event, queued items are attached to Artie's `pending_findings` payload. Artie's
deliberation then decides whether this is the moment.

Interrupting a drafting writer to say their Active Want was vague is precisely
the friction the reset exists to prevent. **The queue may age; it may not
interrupt.**

---

## 9. Re-diagnosis orchestration

The most valuable path in the system, and the one C2 Q3 proved works.

1. Writer revises a Bible slot → `BIBLE_VERSION_CREATED` with `changed_slots`
2. Backend runs C2 Q3 (narrowed re-diagnosis) → returns affected `(scene_id, cell_id_num)` pairs
3. Backend queues one Supervisor run per affected scene, **scoped to the affected cells only**
4. New verdicts append; unaffected verdicts keep their original timestamps
5. Scenes with no affected cells are never touched

**Re-judge only affected cells, not the whole position row.** Token cost is
dominated by the scene text either way, but preserving unaffected verdicts at
their original timestamps is materially better provenance — the ledger shows
exactly what the Bible change actually invalidated.

Verified against seed data: an S06 revision produced **one** scene-cell pair
requiring re-diagnosis out of 174 total diagnoses.

---

## 10. ADK implementation notes

Each is verify-before-implement against current ADK.

**`output_schema` disables tools and sub-agent delegation** in the ADK default
path; ADK 2.8.0 injects a `SetModelResponseTool` workaround that preserves
structured output without hard-blocking tool registration. The Supervisor's
final assembly step is still configured with no tools — the agent should have
one job, and the backend persists the result. The constraint is a design choice,
not a platform imposition.

**`output_key` does not capture a delegated sub-agent's response** (issue #3758).
Inside the `SequentialAgent` pipelines, set `output_key` on the step that produces
the value, not on the composite.

**`ParallelAgent` racing.** If cell judgments run in parallel, each writes a
distinct `output_key`. Never a shared one.

**Event triggers.** ADK's native event-source surface is unverified. Backend
receives the event, publishes to Confluent, invokes via `Runner.run_async` with
synthetic input. Documented-safe.

**Sessions.** Cloud Run scales to zero and has no cross-instance memory. Session
state persists in Supabase, not in process.

---

## 11. Open items

1. **Canon check cost is unbounded** (carried from 04_agent_roster.md §10.4). Every scene against
   every rule is O(scenes × rules). A writer declaring thirty rules makes each
   save expensive. Needs a cap — 10 rules maximum, or a relevance pre-filter — and
   the decision belongs to C4 when S11 storage is designed.
2. **`evidence` stripping needs a test, not just a contract.** §5.3 removes it at
   the backend boundary. There should be a test asserting a Supervisor payload
   containing `evidence` produces an Artie payload that does not.
3. **Queue aging.** §8 says the queue may age but not interrupt. If a writer never
   completes another scene, queued judgments never surface. Acceptable; note it.
4. **Confluent consumer durability.** If the ClickHouse consumer is down, events
   accumulate in the topic. Retention and replay behavior on restart are
   unspecified — C1's problem.
5. **Cold start on first request.** Cloud Run scales to zero. The first save after
   idle pays cold start plus model latency. Measure before the demo; consider a
   warm ping during recording.
