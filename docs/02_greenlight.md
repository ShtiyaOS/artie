# Greenlight Specification v1.2 — The Blueprint Gate

**Status: CANONICAL.**

**Companions:** `docs/01_locked_axis.md` · `docs/03_scene_rig.md`
· `docs/04_agent_roster.md` · `docs/05_orchestration.md`
· `docs/06_artie_mind.md`

**Changes in v1.2:** three blueprint slots added (S13, S14, S15) · the
Skeptical → Committed state machine · blueprint output contract · Ideation Chat ·
register gating · the amendment from 05_orchestration.md §3.4 folded in.

---

## 1. What the Greenlight is, restated

Twelve slots filled through conversation before a writer drafts anything. The
filled slots are the **Project Bible**, and their completed form is the
**Blueprint**.

**The reframe matters.** In v1.1 this was a gate the writer endured. It is now the
threshold at which Artie commits to the project. Same nine core slots, same exit
predicate, entirely different experience — friction becomes something earned.

Never a form. Artie asks; the writer answers; slots fill. A writer arriving with
a developed pitch answers few questions. One arriving with a fragment answers
many. **Determinism lives in the schema and the exit predicate, not in a question
count.**

**The agent interrogates; it never authors.**

### Structural metadata is not story content

A clarification this version needs, because S15 raises it.

Telling a writer that features typically run 40 to 120 scenes is **information
about the form**. Telling them their protagonist should be a detective is
**authoring their story**. Artie may freely supply the former and never the
latter.

The test: does the statement concern *screenwriting*, or does it concern *this
screenplay*?

---

## 2. Slot set

**12 required · 2 optional.** S01 retired, S12 relocated to the Scene Rig.

| ID | Slot | Required | Depends on | Consumed by |
|---|---|---|---|---|
| **S02** | Protagonist | Yes | — | Y3 all; X01 row; all TRANSFORMATION comparisons; seeds S14 |
| **S03** | Protagonist Want | Yes | S02 | Y2 active goal; Y1 at X04, X06; Scene Rig |
| **S04** | Protagonist Flaw | Yes | S02 | Y3 at X01, X08; X11.Y3; X12.Y3 |
| **S05** | Antagonism | Yes | S03 | Y2 all 12 cells; seeds S14 when locus = AGENT |
| **S06** | Thematic Proposition | Yes | S04 | Y4 all 12 cells |
| **S07** | Status Quo Baseline | Yes | S02, S04, S08 | X01 row; `compare_to` for TRANSFORMATION cells |
| **S08** | Arena | Yes | — | Y6 environment cells |
| **S09** | Genre | Yes | — | Scene Rig modulation |
| **S10** | Ending Shape Hypothesis | Yes | S03, S06 | X11 row, X12 row |
| **S13** | Working Title | Yes | — | Title page · export · manifest |
| **S14** | Principal Characters | Yes | S02, S05 | Y5 voice differentiation · Y4 surrogates · Scene Rig roster seed |
| **S15** | Target Scene Count | Yes | — | Progression milestones · commitment state · blueprint view |
| **S11** | World Rules | Optional | — | Script Supervisor canon check |
| **TP1** | Inciting Incident | Optional | S07 | X02 row; Y1 causal trigger |

Structured forms for S05, S06, S07, S09, S10, S11 are unchanged from v1.1 §3.

---

## 3. The new slots

### S13 — Working Title

Plain text. **No JUDGMENT.**

Working titles are provisional by trade convention, and "Untitled" is a
legitimate answer. Artie does not litigate a title.

| RULE | non-empty; ≤ 15 words |
|---|---|
| JUDGMENT | none — pure rule |
| Minimum viable | any non-empty string |

### S14 — Principal Characters

A list. **Auto-seeded, not asked twice.**

S02 populates the protagonist entry. S05 populates an antagonist entry when
`locus = AGENT`. The writer adds the remaining principals. Artie never asks who
the protagonist is a second time.

| Field | Type |
|---|---|
| `name` | text |
| `role` | enum: `PROTAGONIST` · `ANTAGONIST` · `PRINCIPAL` |
| `description` | text — one line |

| RULE | ≥ 1 entry (always true after seeding); ≤ 8 entries; every entry has all three fields non-empty |
|---|---|
| JUDGMENT | Are these distinct people with distinguishable narrative functions, or restatements of one role? |
| Minimum viable | protagonist plus one other named character |

**The cap is 8 and it is deliberate.** These are principals. The waiter in scene
fourteen instantiates through the Scene Rig when the scene demands him — the
roster accretes, and a writer who knows every character before scene one has
probably not left themselves room to discover any.

### S15 — Target Scene Count

Integer. **No JUDGMENT.**

| RULE | integer, 20 ≤ n ≤ 200 |
|---|---|
| JUDGMENT | none — pure rule |
| Minimum viable | any integer in range |

Outside 40–120, Artie notes the norm without objecting. Some writers work in long
fragments and some in short ones; that is a craft choice, not an error.

If the writer does not know, Artie supplies the range as **information about the
form** (§1) and lets them choose. He may not choose for them.

**Three pure-rule slots now exist** — S09, S13, S15 — up from one in v1.1. The
determinism map in §5 improves accordingly.

---

## 4. The commitment state machine

Artie mirrors the writer's effort. This makes that legible and mechanical.

### States

| State | Meaning |
|---|---|
| `SKEPTICAL` | Default at project creation. Reserved and watchful. Investment withheld, respect not withheld. |
| `COMMITTED` | The blueprint is complete and sound. Artie wants to see this finished. |

Stored on the project in Supabase. **Visible to the writer** — crossing the
threshold should be something they notice.

### Transition

`SKEPTICAL → COMMITTED` when:

```
all 12 required slots is_filled = TRUE
AND count(required slots WHERE input_confidence = VALIDATED) >= 10
```

**Ten of twelve validated, not twelve.** A blueprint answered entirely in
provisional values is precisely the case Artie is skeptical of. Requiring all
twelve would trap a writer who genuinely cannot sharpen S06; allowing all twelve
provisional would make commitment meaningless.

Two soft slots are permitted. Three are not.

**When the writer is at eleven of twelve, Artie names what is holding it.** *"Two
of these are still soft. Sharpen them and I'm in."* That converts commitment from
something that happens to the writer into something they can deliberately earn.

**The transition is one-way.** A later revision that drops a slot to PROVISIONAL
does not revoke commitment. Artie does not withdraw from a project he has
committed to over a revision — that would make him unreliable, which is the
opposite of the character.

### Progression within COMMITTED

```
progress_ratio = scenes_completed / S15
```

Continuous, not a state. Modulates warmth, story unlocks, and how directly Artie
presses. The further in, the more invested — and the more willing to be blunt,
because the relationship can carry it.

---

## 5. Register gating

The five registers from the vocabulary research, gated by state.

| Register | SKEPTICAL | COMMITTED |
|---|---|---|
| **Mentorial Anecdotal** | ✓ | ✓ |
| **Diagnostic Unsparing** | ✓ | ✓ |
| **Borscht Belt Deflection** | ✓ | ✓ |
| **Transactional Boundary** | ✓ | ✓ |
| **Enthusiastic Advocacy** | **locked** | ✓ |

**Enthusiasm is the earned register.** Artie does not advocate for a project he
has not committed to, and the register the writer most wants is the one the
blueprint buys.

This is the `register` enum 06_artie_mind.md §6 passes from synthesis to voice. It
replaces the placeholder set.

One note carried from the research: veteran enthusiasm is **grounded in execution
and market mechanics, not superlatives.** Not *"this is wonderful"* but *"they
won't be able to look away from your third act."* Enthusiastic Advocacy that
reads as generic praise is the register implemented wrongly.

---

## 6. What the blueprint produces

The moment the exit predicate clears, the gate pays off visibly.

1. **Title page formatted and populated** — S13, writer of record, date. Fountain
   title-page block, rendered.
2. **Roster seeded** from S14 into the Scene Rig's character list.
3. **Arena seeded** from S08 into the location list.
4. **Scene 1 created**, Scene Rig opened at position X01.
5. **Blueprint view** available in the left pane — the twelve slots as a readable
   document, and the reference Artie steers against.
6. **Commitment announced.** In character, in the newly unlocked register.

**The writer lands on the opening scene with the title page already correct.**
Everything they said became structure without them formatting anything.

---

## 7. Ideation Chat

A conversational surface with no gate, no slots, and no editor attached. The
writer thinks aloud; Artie talks back.

**No write access to the Bible.** Ideation cannot fill slots, and talk does not
earn commitment. That is the point — Artie mirrors effort, and conversation is
not effort.

**It does keep a transcript**, and this is where it earns its place. During the
Greenlight, Artie may **cite the writer's own prior words back to them**:

> *"Couple of weeks ago you said the thing he actually wants is the house. Still
> true?"*

That is quoting the writer to themselves. The writer confirms, revises, or
rejects — and their words fill the slot. **Artie never proposes; he recalls.**

The distinction is exact and it must survive implementation: recalling something
the writer said is not authoring. Composing something they might have said is.

---

## 8. Validation, re-asks, escalation

Unchanged from v1.1 §4 and §6, extended to the new slots.

**Determinism map, updated:**

| Mode | Slots |
|---|---|
| **Pure rule** | S09, S13, S15 |
| **Structurally gated, semantically judged** | S05, S06, S07, S10, S11, S14 |
| **Judgment-dominant** | S02, S03, S04, S08, TP1 |

The honest claim is unchanged: **the gate is deterministic** — twelve slots, one
exit predicate, no advancement until they validate. Several **predicates are
model-evaluated**. Claiming full determinism will not survive the first question
from an engineering judge, and the routing determinism is sufficient.

Re-ask taxonomy, the three-attempt ladder, the metacognitive probe, PROVISIONAL
on non-convergence, and the curated foreign-example library all carry forward
unchanged. **Contrast remains barred from psychological slots.**

---

## 9. Exit predicate

```
S02 ∧ S03 ∧ S04 ∧ S05 ∧ S06 ∧ S07 ∧ S08 ∧ S09 ∧ S10 ∧ S13 ∧ S14 ∧ S15
```

S11 and TP1 optional. No required slot may be deferred. A slot may exit as
`PROVISIONAL` and still satisfy the predicate — but see §4, where PROVISIONAL
count gates commitment.

---

## 10. Bible storage — amendment carried from 05_orchestration.md §3.4

v1.1 §12 placed the Bible entirely in ClickHouse. Corrected:

| Store | Holds | Why |
|---|---|---|
| **Supabase** | Current slot values, current `bible_version_id`, commitment state | Read on every turn; needs single-row latency |
| **ClickHouse** | Full version history, `changed_slots` per version | Append-only; feeds staleness and narrowed re-diagnosis |

Every slot write does both: upsert current to Supabase, publish an append event
to Confluent which lands in ClickHouse.

**Bible versioning is unchanged and remains binding.** Revising any slot writes a
new version; scenes diagnosed against an older version are stale and offered for
re-diagnosis; the version history is authorship evidence showing what the writer
believed the story was at scene 12 versus scene 40.

---

## 11. Known limitations

1. **S06, S07, S10 are extrapolated forms.** The craft literature discusses theme,
   opening state, and endings, but not in these rigid structures.
2. **The gate is hostile to discovery writers.** Hypothesis framing on S10
   mitigates; it does not remove. The commitment reframe helps more than the
   framing does.
3. **Five slots are judgment-dominant.** Do not overstate determinism.
4. **The 10-of-12 threshold is unvalidated.** Plausible, untested. Watch whether
   real writers cluster just below it.
5. **S15 will often be wrong**, and that is fine. It is a milestone measure, not a
   constraint. A writer who declares 60 and writes 95 has not failed; the
   progress ratio simply becomes less meaningful. Do not enforce it.
6. **One-way commitment could be exploited.** A writer could rush a thin blueprint,
   earn commitment, then revise everything. Accepted — the alternative makes
   Artie unreliable, and unreliability costs more than the exploit.
7. **Contrast on S03 remains untested.**
