# C4 Specification v1.0 — Supabase Transactional Layer

**Status: CANONICAL.**

**Companions:** `docs/09_provenance_ledger.md` ·
`docs/10_clickhouse.md` · `docs/05_orchestration.md` ·
`docs/02_greenlight.md` · `docs/03_scene_rig.md`

**Resolves:** 05_orchestration.md §11.1 (unbounded canon check cost).

---

## 1. The boundary rules

Stated first because they govern every decision below. The two-engine split is
the architecture's central claim, and a violation here is not a preference
mistake — it collapses the argument.

### Supabase holds

State read on the interaction path, needing single-row latency.

Projects · scenes · **live script text** · current Bible slot values · current
Scene Rig slot values · character roster · locations · world rules · assets ·
the delivery queue · sessions.

### ClickHouse holds

Append-only analytical data, never read while a writer waits.

Scene diagnoses · provenance events · keystroke batches · Bible **version
history** · coverage and gap computation · staleness and narrowed re-diagnosis.

### Never in Supabase

| Forbidden | Belongs in |
|---|---|
| Scene diagnoses or cell verdicts | ClickHouse (C2) |
| Provenance events | ClickHouse (C1) |
| Keystroke batches | ClickHouse (C1) |
| Bible version history | ClickHouse (09_provenance_ledger.md §3.3) |
| Any coverage, gap, or urgency computation | ClickHouse (10_clickhouse.md §5) |

### Never in ClickHouse

| Forbidden | Belongs in |
|---|---|
| Live script text | Supabase — ClickHouse holds **hashes only** |
| Current Bible or Rig slot values | Supabase |
| Anything on the interaction path | Supabase |

**If a coverage query starts being computed in Postgres because it is convenient,
the architecture has failed.** That is the specific drift to watch for.

---

## 2. Schema

### 2.1 Projects

```sql
create type commitment_state as enum ('SKEPTICAL', 'COMMITTED');

create table projects (
    project_id            uuid primary key default gen_random_uuid(),
    writer_id             uuid,                    -- null in demo mode
    working_title         text not null default 'Untitled',
    commitment_state      commitment_state not null default 'SKEPTICAL',
    current_bible_version integer not null default 1,
    target_scene_count    integer,                 -- denormalized from S15
    scenes_completed      integer not null default 0,
    created_at            timestamptz not null default now(),
    updated_at            timestamptz not null default now()
);
```

`working_title` and `target_scene_count` are **denormalized from S13 and S15** so
the project list and the progress ratio do not require a slot join. Updated on
slot write. The Bible remains authoritative.

`writer_id` is nullable and unused in demo mode. Skipping auth saves most of a
day and no judge will dock you for it.

### 2.2 Bible slots — current state only

```sql
create type input_confidence as enum ('VALIDATED', 'PROVISIONAL');

create table bible_slots (
    project_id       uuid not null references projects on delete cascade,
    slot_id          text not null,               -- 'S02'..'S15', 'TP1'
    value            jsonb not null,
    is_filled        boolean not null default false,
    input_conf       input_confidence not null default 'VALIDATED',
    reask_count      smallint not null default 0,
    filled_at        timestamptz,
    updated_at       timestamptz not null default now(),
    primary key (project_id, slot_id)
);
```

**Current values only. History lives in ClickHouse** (§4).

`value` is `jsonb` because slot shapes differ — S02 is a string, S05 is three
fields, S11 is a list, S10 is two enums. One column, shape validated at the
application layer against 02_greenlight.md §3.

### 2.3 Scenes

```sql
create type scene_status as enum ('RIG_OPEN', 'DRAFTING', 'COMPLETE');

create table scenes (
    scene_id                  uuid primary key default gen_random_uuid(),
    project_id                uuid not null references projects on delete cascade,
    position_id               smallint,            -- 1..12, narrative position
    sequence_order            integer not null,    -- running order on the page
    status                    scene_status not null default 'RIG_OPEN',
    diagnosed_at_bible_version integer,
    created_at                timestamptz not null default now(),
    updated_at                timestamptz not null default now()
);

create index on scenes (project_id, sequence_order);
create index on scenes (project_id, position_id);
```

**`position_id` and `sequence_order` are different things and both are required.**
Position is the writer's declared narrative position (X01–X12). Sequence order is
where the scene sits on the page. 03_scene_rig.md §7 permits declaring positions out of
order and permits several scenes sharing a position — a writer may draft X09
before X02, and X07 will hold many scenes while X02 holds one.

Collapsing them would break the coverage model.

`diagnosed_at_bible_version` is a convenience mirror of the authoritative value in
ClickHouse, so the UI can flag staleness without an analytical query.

### 2.4 Takes

Every submission of a scene is a **take**. Nothing is deleted or overwritten.

```sql
create table takes (
    take_id      uuid primary key default gen_random_uuid(),
    scene_id     uuid not null references scenes on delete cascade,
    take_number  integer not null,
    is_final_cut boolean not null default false,
    submitted_at timestamptz,
    created_at   timestamptz not null default now(),
    unique (scene_id, take_number)
);

create index on takes (scene_id, take_number);
create unique index takes_one_final_cut
    on takes (scene_id) where is_final_cut;
```

The partial unique index enforces **one final cut per scene**, changeable at any
time. Final cuts render to PDF and appear in the current view; other takes live in
history, organized by scene and take.

Takes are the industry's own vocabulary — the director calls cut, the slate reads
*Scene 3, Take 2* — so the mechanic teaches production grammar the way the slug
lines do.

### 2.5 Scene Rig slots

```sql
create table scene_rig_slots (
    scene_id    uuid not null references scenes on delete cascade,
    slot_id     text not null,                    -- 'N01'..'N07' + genre additions
    value       jsonb not null,
    is_filled   boolean not null default false,
    input_conf  input_confidence not null default 'VALIDATED',
    reask_count smallint not null default 0,
    updated_at  timestamptz not null default now(),
    primary key (scene_id, slot_id)
);
```

### 2.6 Script components — the writer's text

```sql
create type component_type as enum (
    'SCENE_HEADING', 'ACTION', 'CHARACTER', 'DIALOGUE',
    'PARENTHETICAL', 'TRANSITION', 'NOTE'
);

create table script_components (
    component_id   uuid primary key default gen_random_uuid(),
    take_id        uuid not null references takes on delete cascade,
    sequence_order integer not null,
    comp_type      component_type not null,
    content        text not null default '',
    content_hash   text,                          -- SHA-256, chains to 09_provenance_ledger.md §5
    created_at     timestamptz not null default now(),
    updated_at     timestamptz not null default now()
);

create index on script_components (take_id, sequence_order);
```

**This is the only place the screenplay text exists.** ClickHouse holds hashes;
the ledger never duplicates it.

`content_hash` is the terminus of the keystroke chain in 09_provenance_ledger.md §5. The manifest
verifier walks the chain and confirms it lands here.

`NOTE` maps to Fountain's `[[double brackets]]` — retained in the file, excluded
from the PDF. Writers need somewhere to park a thought.

### 2.7 Characters — the accreting roster

```sql
create type character_role   as enum ('PROTAGONIST','ANTAGONIST','PRINCIPAL','SECONDARY');
create type roster_source    as enum ('BLUEPRINT','SCENE_RIG');

create table characters (
    character_id         uuid primary key default gen_random_uuid(),
    project_id           uuid not null references projects on delete cascade,
    name                 text not null,
    role                 character_role not null,
    description          text,
    source               roster_source not null,
    canonical_frame_uri  text,                    -- Director reference image
    character_portrait_uri text,             -- generated at character creation
    created_at           timestamptz not null default now(),
    unique (project_id, name)
);

`character_portrait_uri` holds a portrait generated once at character creation
from **physical description only**. It is the reference anchor passed to the
Director on every subsequent frame. `canonical_frame_uri` may supersede it once an
in-scene frame is accepted.
```

`BLUEPRINT` entries come from S14 at Greenlight completion. `SCENE_RIG` entries
accrete as scenes demand them (03_scene_rig.md §2).

`canonical_frame_uri` holds the first accepted frame per character, passed as a
reference image on later generations. Testing measured descriptive persistence at
roughly 80% across an angle change; references are the upgrade path (04_agent_roster.md §5).

### 2.8 Locations

```sql
create table locations (
    location_id uuid primary key default gen_random_uuid(),
    project_id  uuid not null references projects on delete cascade,
    name        text not null,
    source      roster_source not null,
    created_at  timestamptz not null default now(),
    unique (project_id, name)
);
```

### 2.9 World rules — with the cap

```sql
create type world_rule_type as enum ('A_POSSIBILITY', 'B_CONSEQUENCE');

create table world_rules (
    rule_id    uuid primary key default gen_random_uuid(),
    project_id uuid not null references projects on delete cascade,
    rule_type  world_rule_type not null,
    condition  text not null,
    outcome    text not null,
    is_active  boolean not null default true,
    created_at timestamptz not null default now()
);

create unique index world_rules_active_cap
    on world_rules (project_id, rule_id) where is_active;
```

See §5 for the cap enforcement.

### 2.10 Assets

```sql
create table assets (
    asset_id        uuid primary key default gen_random_uuid(),
    scene_id        uuid not null references scenes on delete cascade,
    gcs_uri         text not null,
    model           text not null,
    prompt          text not null,
    assumption_note text,
    finish_reason   text,
    created_at      timestamptz not null default now()
);
```

`prompt` and `assumption_note` are stored because the Director's isolation rule
is auditable from them — the prompt should derive only from Action lines (04_agent_roster.md §5).

### 2.11 Delivery queue

Implements 05_orchestration.md §8: async judgments and findings age, but never interrupt.

```sql
create type queue_item as enum ('FINDING','SLOT_JUDGMENT_FAILED','CANON_FINDING');

create table agent_queue (
    queue_id     uuid primary key default gen_random_uuid(),
    project_id   uuid not null references projects on delete cascade,
    scene_id     uuid references scenes on delete cascade,
    item_type    queue_item not null,
    payload      jsonb not null,
    created_at   timestamptz not null default now(),
    delivered_at timestamptz
);

create index on agent_queue (project_id, delivered_at) where delivered_at is null;
```

The partial index makes "what is undelivered for this project" a single index
scan, which is the only query this table serves on the hot path.

### 2.12 Sessions

```sql
create table sessions (
    session_id   uuid primary key default gen_random_uuid(),
    project_id   uuid not null references projects on delete cascade,
    opened_at    timestamptz not null default now(),
    closed_at    timestamptz,
    opening_slug text                             -- 07_artie_persona.md §8 generated slug
);
```
### 2.13 Continuity checks

```sql
create table continuity_checks (
    check_id       uuid primary key default gen_random_uuid(),
    project_id     uuid not null references projects on delete cascade,
    ran_at         timestamptz not null default now(),
    scenes_covered integer not null,
    take_ids       uuid[] not null,
    findings       jsonb not null,
    tiers_run      smallint[] not null
);

create index on continuity_checks (project_id, ran_at desc);
```

`take_ids` records exactly which takes were read. **A check is stale when any
listed take is no longer the final cut** — same staleness logic as Bible
versioning.

---

## 3. Row-level security

**RLS on every table. No policies granting access.** The backend uses the secret
key, which bypasses RLS entirely; the publishable key reaches nothing.

```sql
alter table projects           enable row level security;
alter table bible_slots        enable row level security;
alter table scenes             enable row level security;
alter table scene_rig_slots    enable row level security;
alter table script_components  enable row level security;
alter table characters         enable row level security;
alter table locations          enable row level security;
alter table world_rules        enable row level security;
alter table assets             enable row level security;
alter table agent_queue        enable row level security;
alter table sessions           enable row level security;
alter table takes              enable row level security;
alter table continuity_checks  enable row level security;
```

Deny-by-default is the correct posture for a public repository where a leaked
publishable key is a plausible accident. When auth arrives, policies get added;
until then, nothing is reachable without the secret key.

**The secret key never leaves the backend.** Not the frontend, not the repo, not
a chat window.

---

## 4. The dual-write pattern

Every Bible or Rig slot write does two things, **in this order**:

1. **Upsert to Supabase.** The read path is immediately correct.
2. **Publish to Confluent** — `SLOT_ANSWERED`, and `BIBLE_VERSION_CREATED` when
   the write constitutes a revision.

Order matters. Supabase first means the writer is never blocked on the analytical
path. If Confluent is unreachable, buffer and retry (09_provenance_ledger.md §12) — the user's write
already succeeded.

**This opens a window where Supabase holds state ClickHouse has not yet seen.**
That is acceptable and by design: ClickHouse is never on the interaction path.
The only visible consequence is that a coverage query run immediately after a
slot change may lag by the ingestion interval, which is invisible at human
timescales.

**Version increment rule.** A slot write increments `current_bible_version` only
when the slot was already filled and the value changed. First fills during the
Greenlight do not each create a version — otherwise a twelve-slot blueprint would
produce twelve versions before the writer had written a word.

---

## 5. The canon check cap — resolving 05_orchestration.md §11.1

B2 flagged canon checking as O(scenes × rules) and unbounded. Two mechanisms
close it.

**Cap: 10 active world rules per project**, enforced at the application layer with
a clear message rather than a silent failure. A writer needing an eleventh is
almost certainly describing plot events rather than systemic laws — which
02_greenlight.md §4's S11 judgment already rejects.

**Batch: one model call per scene, not one per rule.** All active rules go into a
single prompt asking which are violated and which established consequences failed
to trigger. Ten rules in one prompt is a small prompt.

Cost per scene save is therefore **one canon call plus six cell judgments**, flat
regardless of rule count. The unbounded term is gone.

---

## 6. Realtime

Supabase realtime subscriptions on four tables:

| Table | Purpose |
|---|---|
| `scenes` | status transitions drive UI state |
| `agent_queue` | new undelivered items reach the chat |
| `bible_slots` | slot fills update the blueprint view live |
| `assets` | frame ready notification |

**Deliberately not on `script_components`.** The editor owns its local state and
syncs on save. Realtime on every batch save would be chatty for no benefit — the
writer is the only one editing.

---

## 7. Migrations

Numbered SQL files in `sql/`, matching the ClickHouse pattern:

```
sql/
  01_schema.sql              -- ClickHouse (existing)
  02_seed_dimensions.sql     -- ClickHouse (existing)
  10_supabase_types.sql      -- enums
  11_supabase_tables.sql     -- tables + indexes
  12_supabase_rls.sql        -- RLS enable
  13_supabase_realtime.sql   -- publication membership
```

Run in order. No migration framework — at this scale it is overhead.

---

## 8. Open items

1. **`value jsonb` shape validation is application-layer only.** A malformed S05
   would insert successfully. Consider `jsonb` check constraints per slot, or
   accept and validate in code. Code is faster to build; constraints are safer.
2. **`sequence_order` reordering strategy is unspecified.** Renumbering 40–120
   scenes is trivial, so integer with full renumber on reorder is fine — but
   concurrent reorder and insert would race. Single-writer demo makes this moot;
   note it for multi-user.
3. **`scenes_completed` is a maintained counter** and can drift from reality. It
   should be recomputable from `scenes where status = 'COMPLETE'`, and there
   should be a reconciliation path.
4. **The 10-rule cap is unvalidated.** Plausible, untested. A dense speculative
   world may legitimately need more, in which case relevance filtering becomes
   necessary rather than a cap.
5. **Genre-modulated Rig slot ids are unenumerated.** `scene_rig_slots.slot_id`
   is free text to accommodate them; the actual ids should be fixed when the
   modulation additions are implemented.
6. **No soft delete anywhere.** A deleted scene cascades away its components and
   Rig slots. The provenance ledger retains the record, so authorship evidence
   survives — but the text does not. Confirm that is intended before shipping.
