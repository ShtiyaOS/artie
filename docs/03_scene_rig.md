# Scene Rig Specification v1.0

**Status: CANONICAL.**
**Companions:** `docs/01_locked_axis.md` · `docs/02_greenlight.md`

**Downstream consumers:** B1 (agent boundaries), B2 (handoff), C1 (provenance
ledger), C2 (ClickHouse matrix and coverage), C4 (Supabase schema).

---

## 1. What the Scene Rig is

A short interrogation run before every scene, **resetting each time**.

**Two constraints govern every decision below.**

**Anti-paralysis is why it resets.** Writers abandon projects when forced to
hold the whole structure in view. The Rig shows only the current scene's slots.
Any change that reintroduces global scope defeats its purpose.

**The Rig captures intent; the matrix diagnoses execution.** *What is at risk in
this scene* is intent and belongs here. *Whether the scene turned* is diagnosis
and belongs to Y1. No slot may ask the writer to declare an outcome. This is the
load-bearing distinction of the entire system.

Three violations of this rule were identified and corrected below — N05's exit
state,
and two genre modulations. All three are corrected below.

---

## 2. Slot set

**7 required, resetting per scene.** Plus at most two genre additions (§5), which
are prompted but never gating.

| ID | Slot | Type | Consumed by |
|---|---|---|---|
| **N01** | Narrative Position | enum `X01`–`X12` | Selects the matrix row for this scene |
| **N02** | Alignment Character | ref to roster, or new | Y3; Y5 voice differentiation |
| **N03** | Active Want | text | Y2 — the goal opposed within this scene |
| **N04** | Obstacle | `locus` enum + text | Y2 counter-force |
| **N05** | Scene Frame | `entry_state` + `value_at_stake` | `entry_state` → Y1 · `value_at_stake` → Y2 |
| **N06** | Location | ref to arena, or new | Y6 environment cells |
| **N07** | Temporal Urgency | text | Y1, Y2 |

### N05 — Scene Frame

Declaring where a scene *starts* is intent. Declaring where it *ends* is
execution.

Declaring where a scene *starts* is intent. Declaring where it *ends* is
execution. An earlier design removed both, which eliminated Y1's only scene-level input and
then misattributed Value at Stake to Y1 — but Y2's own disambiguating question
is *"the strength of the opposition, or what stands to be lost."* Value at stake
is Y2 by definition.

| Field | Type | Consumer |
|---|---|---|
| `entry_state` | text — the condition, relationship, or standing as the scene opens | **Y1** |
| `value_at_stake` | text — what may be lost, gained, or irrevocably altered | **Y2** |

Y1 then measures the text's actual exit against the writer's **declared entry**.
That is the same pattern the axis spec already uses for ANCHORED cells:
diagnose execution against stated intent rather than an external standard.

**`entry_state` is declared fresh every scene and never pre-fills from a prior
scene's outcome.** The Rig does not track execution, so it has no exit state to
inherit. This must not be relaxed for convenience.

### Roster and Arena accrete

N02 and N06 either reference an existing entity or instantiate a new one. The
roster and location list grow silently across scenes and populate autocomplete.
The writer is never shown the full list unless they ask for it.

This is where the Character Roster lives. It was moved out of the Greenlight
because secondary characters are discourse-level and appear when scenes demand
them.

---

## 3. Validation predicates

**RULE** is deterministic and evaluable in code. **JUDGMENT** is model-evaluated,
with the question stated.

| Slot | RULE | JUDGMENT question |
|---|---|---|
| **N01** | value ∈ `X01`–`X12` | **None — pure rule** |
| **N02** | resolves to an existing roster ID, or creates one | Does this name a distinct agent capable of anchoring focalization? |
| **N03** | non-empty | Is this a specific actionable objective rather than a passive emotional state? |
| **N04** | `locus` ∈ enum; text non-empty | Does this describe a tangible force directly countering N03? |
| **N05** | both fields non-empty | (1) Does `entry_state` describe a condition at the scene's opening rather than its outcome? (2) Does `value_at_stake` state a **risk** rather than a **result**? |
| **N06** | resolves to an existing arena ID, or creates one | Does this describe a spatial environment capable of containing the action? |
| **N07** | non-empty | Does this articulate a trigger or deadline forcing the action to occur now rather than later? |

**N05's second judgment catches execution leaking into intent.** *"Their
marriage, which ends here"* is an outcome wearing an intent's clothes. The
judgment must catch execution leaking into the intent slot.

**No regexes over natural language.** Where form is the constraint, use a
structured field so the interface supplies syntax and the writer supplies
semantics — as with S06 and S11 at the Greenlight.

### Determinism distribution

| Mode | Slots |
|---|---|
| Pure rule | N01 |
| Referentially gated, semantically judged | N02, N04, N06 |
| Judgment-dominant | N03, N05, N07 |

Same honest claim as the Greenlight: the **gate** is deterministic; several
**predicates** are model-evaluated.

---

## 4. Exit predicate — accept-first

**The Rig clears on RULE checks alone.**

```
N01 ∈ enum
∧ N02 resolves or instantiates
∧ N03 non-empty
∧ N04.locus ∈ enum ∧ N04.text non-empty
∧ N05.entry_state non-empty ∧ N05.value_at_stake non-empty
∧ N06 resolves or instantiates
∧ N07 non-empty
```

All deterministic. All instant. No model call blocks the writer.

**JUDGMENT runs asynchronously** after the writer enters the drafting surface.
Failures surface as a nudge after the scene, never as a wall before it.

**Why this differs from the Greenlight.** The Greenlight runs once per project
and can afford to gate hard on model judgment. The Rig runs forty-plus times.
Six judgment calls before a writer can type is
roughly 240 blocking calls across a feature, and precisely the friction its own
adversarial section concedes is a hard biological limit.

The deterministic gate survives. The latency wall does not. An earlier undefined
"confidence score above threshold" is removed with it.

**A slot failing async judgment is marked `PROVISIONAL`**, exactly as at the
Greenlight, and composes into displayed confidence per Greenlight spec §11.

---

## 5. Genre modulation

Genre is declared once at the Greenlight and persists. The writer never
re-declares it. **Primary governs Y1/Y2 modulation; secondary is restricted to
Y5/Y6.** This relocates any collision from the structural spine to surface
discourse, where it is manageable.

| Class | Genres | Addition |
|---|---|---|
| Baseline | Drama, Historical, War, Western | none |
| Speculative | SF, Fantasy, Supernatural Horror | World rule invoked or tested in this scene |
| Information-state | Mystery, Thriller, Crime | **Information sought vs. information protected** |
| Comedic | Comedy, Comedy-Drama | Primary incongruity source |
| Relational | Romance, Romantic Comedy | **Relational goal or vulnerability risked** |
| Kinetic | Action, Adventure | Escalation vector relative to the prior set piece |

The two bolded entries are corrections. The candidate asked for a "knowledge
delta" and a "relationship-state delta"; both are outcome measurements and both
violated the intent/execution separation.

**Genre additions are prompted but never gating.** This was previously ambiguous — the
exit predicate named only N01–N07 while §7.2 said the Rig "appends" genre slots.
Resolved: additions are offered, may be skipped, and never block drafting. A
Speculative Comedy would otherwise put nine questions in front of every scene,
which is the paralysis the reset exists to prevent.

---

## 6. Carry-over rules

| Behavior | Applies to |
|---|---|
| **Accretes** | Roster (N02), Arena (N06) — silently, into autocomplete |
| **Persists** | Genre from the Bible; never re-declared |
| **Pre-fills** | N01 defaults to the prior scene's position or the next in sequence; freely overwritten |
| **Resets fully** | N03, N04, N05, N07 — every scene, always |

The full reset on N03/N04/N05/N07 is deliberate. Even across a long sequence
pursuing one macro-goal, the immediate tactic, obstacle, and stakes must change.
Repeating a beat without altering tactic or stakes is a structural failure, and
a pre-filling Rig would quietly encourage it.

---

## 7. Position declaration semantics

- **Multiple scenes may share a position.** X07 spans twenty percentage points;
  X02 spans five. Expect the 4:1 skew already noted in the axis spec.
- **Positions may be declared out of order.** A writer may draft X09 before X02.
  Presentation order is not composition order.
- **The Rig is agnostic to running order.** If a writer declares X08 for a scene
  sitting on page fifteen, the Rig records the intent without objection. The
  matrix diagnoses the compression later. The Rig captures what the writer
  believes they are doing; judging it is not its job.

---

## 8. Revision

Re-entering the Rig for an existing scene pre-fills all seven slots from the
prior pass.

**Changing N01 re-runs judgment on N03, N04, and N05** against the new
positional context, and warns: *the structural weight of this position differs
— check that the want and the stakes still fit.* The writer's text is never
erased and, under accept-first, they are never blocked; the re-judgment surfaces
as a nudge.

---

## 9. Resolved: one alignment character per scene

An open question asked what happens with two equally weighted alignment
characters holding opposed intents.

**Force the choice.** One N02 per scene, one N03–N07 vector.

A scene that genuinely carries two co-equal perspectives is usually two scenes,
or one scene whose dominant perspective the writer has not yet identified.
Making the writer choose is itself diagnostic, and it keeps the vector singular
for Y3 and Y5.

---

## 10. Known limitations

1. **Context-switching cost is real and unmitigated.** Moving between the
   associative state of drafting and the analytical state of slot-filling
   imposes a genuine cognitive tax. Accept-first reduces it; nothing removes it.
   Concede this when challenged rather than defending against it.
2. **Y1 depends on a declared `entry_state`.** If a writer supplies a thin one,
   the intra-scene turn diagnosis degrades. Marked PROVISIONAL when judgment
   fails, which propagates to displayed confidence.
3. **No enforced relationship between N03 and the Bible's S03.** Deliberate: a
   scene pursuing something off the spine may be a B-story beat or a
   digression, and the Rig cannot tell which. Y1 and Y4 diagnose that later.
   The cost is that genuine drift goes unflagged until diagnosis.
4. **Async judgment means a writer can draft an entire scene on invalid intent**
   before being told. Accepted trade; the alternative is the latency wall.

---

