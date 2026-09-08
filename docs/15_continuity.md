# Continuity Check — Specification v1.0

**Status: CANONICAL.**

**Amends:** `docs/04_agent_roster.md` §4 (Script Supervisor) ·
`docs/11_supabase.md` (new table) ·
`Editor_Specification_v1.0.md` §13 (left pane) ·
`docs/09_provenance_ledger.md` §3.2 (new events)

---

## 1. What it is

A **whole-script consistency check**, invoked explicitly by the writer, run by the
Script Supervisor against the designated final-cut scenes.

It is not the canon check. The canon check evaluates a single scene against
declared world rules on every submit. **Continuity reads the assembled script and
finds contradictions.**

No existing screenwriting tool does this. It is a genuine differentiator, and the
production role it is named for — the script supervisor — exists precisely because
this job is hard for humans.

---

## 2. Three design decisions, and why each one matters

### 2.1 Explicit invocation only

**Never automatic. Never during drafting.**

A writer who asks for a continuity check has consented to be told they are wrong.
The identical finding delivered unbidden mid-draft is Artie interrupting to say a
prop moved — exactly the friction accept-first was designed to remove.

**Consent also solves the false-positive problem.** An unsolicited wrong finding
is an accusation. A requested wrong finding is a suggestion the writer dismisses.

### 2.2 Final-cut scenes only

Continuity across drafts is noise. If scene 4 take 1 has the letter and take 2
does not, that is not an error — that is revision.

Checking only designated final cuts means checking **the script**, not the
workspace.

### 2.3 Bounded to the last final cut in sequence

Scenes 1 through the last designated final cut, in `sequence_order`. Twelve locked
scenes and three drafts means the check covers twelve.

Naturally bounded, predictable in cost, and never operating on partial state.

### 2.4 The consequence nobody planned

**Continuity is a whole-script read; diagnosis is a per-scene read.** They are
different operations and belong in different entry points.

The Supervisor therefore gains a second invocation path. Automatic per-scene
diagnosis stays as specified. `check_continuity` assembles final cuts in sequence
order and reads them as **one document**.

---

## 3. Three tiers of finding

Ascending cost, descending confidence.

### Tier 1 — Declared contradictions

Checkable against the database. **No extraction, near-zero false positives.**

| Check | Source |
|---|---|
| A name addressed in dialogue that is not in the roster | `characters` |
| A character speaking who is not present per the Rig | `scene_rig_slots` N02 |
| A location referenced that contradicts the scene heading | `locations`, heading |
| Knowledge asserted that the Information-state modulation says was not yet learned | genre modulation slots |

**Worked example.** The roster has Mark as the spouse. Scene 6 dialogue reads
*"Eff you, Brad, I want a divorce."* Brad is not in the roster. Flagged.

This tier is nearly free and should ship first.

### Tier 2 — Intra-scene extraction

Contradictions **inside one scene**. Cheapest extraction tier, because the context
is a single scene.

| Check | Example |
|---|---|
| Temporal impossibility | Heading says DAY, dialogue says one o'clock, action describes sunset |
| Physical state | Character is described as seated, then described crossing the room without rising |
| Prop appearance | An object is used that was never brought in or established |

### Tier 3 — Cross-scene extraction

The expensive tier. Requires accumulating established facts across the assembled
script.

| Check | Example |
|---|---|
| Object persistence | She pockets the letter in scene 4; scene 9 has her hands empty at the door |
| Knowledge state | He learns of the affair in scene 12; he is surprised by it in scene 17 |
| Physical state across scenes | Injured in scene 8, walking unaided in scene 9 with no time passing |
| Location detail | The diner has a back door in scene 3 and none in scene 20 |
| Elapsed time arithmetic | Scene 11 ends at noon; 12 says "next morning"; 13 says "that afternoon" |

**Scope the prompt.** Check a scene only against facts involving the characters
and locations present in it. Checking every scene against every fact ever
established grows without limit and produces noise.

---

## 4. The grounding constraint — the thing that prevents confabulation

**Every continuity finding must cite two locations and quote the conflicting
detail. A finding that cannot point at two specific places is not reported.**

```json
{
  "finding_type": "CONTINUITY",
  "tier": 1,
  "category": "UNROSTERED_NAME",
  "location_a": { "source": "roster", "detail": "Mark — spouse" },
  "location_b": { "scene_id": "...", "scene_number": 6,
                  "quote": "Eff you, Brad, I want a divorce" },
  "statement": "Scene 6 addresses a spouse named Brad. The roster has Mark."
}
```

Requiring two grounded citations forces the model to produce **evidence rather
than a conclusion**, which kills most confabulation structurally.

This is the same discipline as the Supervisor's `evidence` field — and it carries
the same handling rule: **quotes are the writer's prose, so they go to the writer
directly and are stripped before anything reaches Artie** (05_orchestration.md §5.3).

Without this constraint, Tier 3 would be actively dangerous. Artie confidently
telling a writer they broke continuity when they did not is the
machine-causes-the-human-to-hallucinate failure that Persona value 6 exists to
prevent.

---

## 5. The debugging loop

Continuity is **a work queue, not a report.**

```
Check → findings → Artie → open the named scene → Take 2 → re-check
```

Each finding names a scene. Acting on it means opening that scene into a new
take. **The take mechanic and the continuity check are the same system** — one
produces the reason, the other absorbs the fix.

The provenance record here is unusually good: *Take 1 had Brad. Continuity flagged
it. Take 2 has Mark.* A documented correction cycle is authorship development made
visible, which is D2's Claim 3.

### Staleness

A check runs against a specific set of takes. When any of those takes is
superseded, **the check is stale.**

The tab shows when it last ran, against how many scenes, and whether any have
changed since. Same logic as Bible versioning staleness. **Information, not
nagging** — the writer decides when to re-run.

---

## 6. Delivery

Findings reach the writer through Artie, in **Diagnostic Unsparing** (07_artie_persona.md §5).
Mechanical faults get named plainly in architectural terms, criticism stays on the
material.

> *You've got a husband named Mark in scene two and a husband named Brad in scene
> six. One of them's wrong.*

Depersonalized, specific, no cushioning. The register exists for exactly this.

---

## 7. Where it lives

**A Continuity tab in the left pane**, beside the coverage heatmap.

Both are whole-script views. Both are consulted rather than interrupting. The
heatmap answers *what is structurally missing*; continuity answers *what
contradicts*. They belong together.

The tab shows: last run timestamp, scene count covered, staleness state, and the
current finding list grouped by scene.

---

## 8. Schema

```sql
create table continuity_checks (
    check_id       uuid primary key default gen_random_uuid(),
    project_id     uuid not null references projects on delete cascade,
    ran_at         timestamptz not null default now(),
    scenes_covered integer not null,
    take_ids       uuid[] not null,          -- staleness comparison basis
    findings       jsonb not null,
    tiers_run      smallint[] not null
);

create index on continuity_checks (project_id, ran_at desc);
```

`take_ids` records exactly which takes were read. A check is stale when any listed
take is no longer current.

---

## 9. Cost

**One call per check** on the Flash line, with the assembled final cuts in
context. A 90-scene feature is roughly 40k tokens — negligible.

Cheap enough that it needs no metering, and a writer can run it as often as they
like.

**Model:** `gemini-3.8-flash`. Extraction with a grounding requirement is the same
class of task as the assumption note, and it is the place a hallucination does the
most damage.

---

## 10. Build order

| Tier | When | Why |
|---|---|---|
| **Tier 1 — Declared** | September 9 | Half a day. Zero false positives. Uses data already in the schema. |
| **Tier 2 — Intra-scene** | September 9 if time permits | Bounded context, moderate confidence |
| **Tier 3 — Cross-scene** | October | The hard version. Needs validation against real scripts before it is trusted. |

**Not in the demo beat sheet**, so per 16_demo_beat_sheet.md §10 it does not get polished for
camera. But Tier 1 is cheap enough to be running in the hosted prototype — a judge
who opens the URL and gets a real continuity note has learned something the video
did not tell them.

---

## 11. Ledger events — amends 09_provenance_ledger.md §3.2

| Event | Actor | Payload |
|---|---|---|
| `CONTINUITY_CHECK_REQUESTED` | human | `scenes_covered`, `tiers_run` |
| `CONTINUITY_FINDINGS_DELIVERED` | supervisor | full findings array with citations |

The findings payload is stored in full, consistent with 09_provenance_ledger.md §1's rule that agent
payloads are evidence and are never summarized.

---

## 12. Open items

1. **Tier 3 extraction accuracy is unmeasured.** Validate against a real
   screenplay with known continuity errors before shipping it.
2. **The scoping heuristic is unspecified in detail** — "facts involving the
   characters and locations present" needs an implementable definition.
3. **Findings the writer dismisses should not recur.** A dismissal state is needed,
   or every re-run re-reports what they already rejected.
4. **Tier 1 name matching is naive.** Nicknames, diminutives, and characters
   addressed by title rather than name will produce false positives — *"Eff you,
   Doc"* against a roster containing Mark. Needs an alias field on `characters`,
   or a confidence downgrade on unmatched single names.
