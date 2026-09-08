# Artie Mind v1.0 — The Deliberation Engine

**Status: CANONICAL for mechanism. Voice reserved for human design (§7).**

**Companions:** `docs/04_agent_roster.md` ·
`docs/05_orchestration.md` · `docs/02_greenlight.md`

**Scope:** how Artie decides what to say. Not what he says, and not who he is.

---

## 1. What this is, and what it is not

Single-valued advice is what makes an AI sound like a tool. *"Cut this scene."*
A working showrunner does not think that way. They hold *cut it* and *expand it*
at once and resolve by context — how far along the writer is, whether the problem
is this scene or the two around it, whether today is a day for pressing.

**The mechanism: Artie's response is produced by weighing opposed positions, not
by a single inference pass.** Four tension axes argue. A synthesis function
decides what to do. A voice function decides how to say it.

**What it is not:**

- Not a mood detector. No sentiment analysis, no inference about how the writer
  feels. Every trigger below is an observable counter.
- Not a co-writer. See §8 — the constraint that makes this safe.
- Not always on. Most turns fire nothing. A producer who agonizes over every
  sentence is exhausting.

---

## 2. Naming

**In code, in the repository, and in the submission writeup, use the craft terms
only.** They stand on their own engineering merits and need no defense.

| Axis | Poles |
|---|---|
| A1 | `EXPANSION` ↔ `RESTRICTION` |
| A2 | `INSIGHT` ↔ `ANALYSIS` |
| A3 | `PERSISTENCE` ↔ `YIELDING` |
| A4 | `INTENTION` ↔ `MANIFESTATION` |

Resolution functions: `SYNTHESIS` and `VOICE`.

> **Private note, not for the repository.** The structure derives from the
> Sephirotic tree — Chesed/Gevurah, Chochmah/Binah, Netzach/Hod, and
> Keter/Malchut on the axes, with Tiferet synthesizing and Yesod transmitting.
> Three of those pairs are already dramaturgical: expansion against restriction
> is editing; the flash against the architecture is idea versus structure;
> persistence against yielding is when to press. Keter↔Malchut — *their end is
> wedged in their beginning* — is intent against what actually reached the page,
> which is every note ever given.
>
> This is Artie's private logic and the reason he thinks the way he does. It
> makes him far more interesting to write. It is an Easter egg for whoever finds
> it, not a claim the architecture makes.

---

## 3. The four axes

### A1 — Expansion ↔ Restriction

*Give the writer room, or hold the line.*

**Trigger:** `pending_findings` is non-empty. The most frequently active axis.

`EXPANSION` argues for letting it go — the writer has momentum, the gap is small,
the scene is early. `RESTRICTION` argues for holding the line — this is a
weight-5 ATTESTED gap at a turning point and letting it pass now means a rewrite
in three weeks.

### A2 — Insight ↔ Analysis

*The flash, against whether it structurally holds.*

**Trigger:** the writer has just supplied a slot value or a new idea.

`INSIGHT` argues from the instinct — this is alive, it has heat, do not
interrogate it into a corpse. `ANALYSIS` argues from the structure — this want
cannot be opposed, this proposition cannot be falsified, it will not carry the
weight the matrix will put on it.

### A3 — Persistence ↔ Yielding

*Keep pressing, or back off.*

**Trigger — observable counters only, never inferred emotional state:**

| Signal | Source |
|---|---|
| `reask_count ≥ 2` on the current slot | Greenlight schema |
| ≥ 2 consecutive slots marked `PROVISIONAL` | Bible slots |
| `pending_findings` depth ≥ 4 unaddressed | queue |
| No scene completed in the current session | scene events |

This axis was the design risk — its subject is the writer's state, and I did not
want a mood-detection system inside a screenwriting tool. Counters solve it.
*This is the third re-ask on this slot* is a fact. *The writer seems frustrated*
is a guess, and guessing about a person's emotional state in order to decide how
hard to push them is not something this system should do.

### A4 — Intention ↔ Manifestation

*What you meant, against what reached the page.*

**Trigger:** declared intent diverges from diagnosed execution. Directly
detectable — an `ANCHORED` finding is definitionally this axis, and a Rig slot
contradicted by a verdict is the scene-level case.

`INTENTION` argues that the writer's stated aim is sound and the execution is
catching up. `MANIFESTATION` argues that the page is the only evidence that
exists and the page says otherwise.

This is the most useful axis for screenwriting and the one no competitor will
have, because it requires a declared Bible to measure against.

---

## 4. Activation gating

**Most turns activate nothing.** The writer answers a question, a slot fills, the
next question comes. That is not a moment that carries weight and it should not
cost three model calls.

| Situation | Active axes |
|---|---|
| Ordinary slot fill, validated, no findings | **none** — respond directly |
| Slot value arrives, thin or contestable | A2 |
| Findings pending after a scene save | A1 |
| Findings pending, one or more `ANCHORED` | A1 + A4 |
| Friction counters tripped (§3, A3) | A3, plus whatever else applies |
| Gate completion, scene completion, session open | A1 |

**Cap: two axes per turn.** If three would qualify, take the two with the
strongest triggers — an `ANCHORED` finding and a tripped friction counter
outrank a routine pending gap.

---

## 5. Pole mechanics

### One call per active axis

Both poles are generated in a single constrained call with a forced structure and
a required strength rating. This is a deliberate compromise: separate calls per
pole would double cost and latency, and models asked to produce a single balanced
view tend to hedge into mush. **Forcing an explicit two-sided structure with
numeric strengths gets the argument without the hedge.**

Typical turn: one or two pole calls plus one synthesis call.

**Model:** `gemini-3.5-flash`. Pole quality matters more than latency — two hedged paraphrases instead of genuine opposition would make the whole mechanism decorative.

### Output contract

```json
{
  "axis": "A1",
  "poles": [
    {"pole": "EXPANSION",   "position": "hold it back this turn",
     "reason": "first scene of the session, momentum matters more",
     "strength": 3},
    {"pole": "RESTRICTION", "position": "raise it now",
     "reason": "weight-5 ATTESTED gap at a turning point; deferring compounds",
     "strength": 4}
  ]
}
```

`strength` is 1–5. It exists so synthesis can weigh rather than merely pick, and
so the trace shows a decision rather than a coin flip.

### The pole constraint — verbatim in the prompt template

> You are arguing about **how to respond to the writer**, never about **what
> their story should contain**. You may not propose story content: no character
> names, no plot beats, no themes, no dialogue, no scene descriptions. If your
> argument requires proposing content, it is out of scope — argue about approach
> instead.

---

## 6. Synthesis

**Input:** the active axes' pole positions with strengths, plus the findings and
slot state.

**Output:** a decision about what to *do* this turn. Not what to say.

```json
{
  "action": "RAISE_FINDING | PRESS_SLOT | RELEASE | ACKNOWLEDGE_ONLY",
  "target": "X06.Y2",
  "hold": ["X03.Y1", "X05.Y4"],
  "register": "DIRECT | GENTLE | WRY",
  "rationale": "one line, for the trace"
}
```

`register` is the handoff to VOICE. It constrains delivery without writing it —
synthesis decides *that this lands hard*, voice decides *how a 72-year-old
producer says something hard*.

`hold` matters as much as `target`. A showrunner who dumps every note at once is
useless; deferring is a decision and the trace should record it.

**Model:** `gemini-3.5-flash`. Synthesis is the reasoning step.

---

## 7. Voice — reserved for human design

**Input:** the synthesis decision, plus the persona.
**Output:** what Artie actually says.

This is the layer where the persona work lands, and it is deliberately not
specified here. The interface is fixed; the content is written by hand.

**What VOICE may not do, and this is absolute:**

- Introduce a finding synthesis did not select
- Propose a slot value, a theme, a name, a beat, or a line
- Write, quote, or paraphrase screenplay text — it has none, per 04_agent_roster.md §1.1
- Escalate `register` beyond what synthesis set

VOICE renders a decision. It does not make one.

**Why this is human-written.** Design is 25% of the score, and it is the criterion
an agentic pipeline is worst at. A model designing a character produces something
competent and forgettable. The fedora placed on the lap in our Nano Banana test —
guest, not owner of the office — was interesting precisely because it was an
unplanned specific. Character runs on those and they do not come out of a spec.

**The one constraint that does carry forward: every name Artie speaks is
invented.** The submission grants Google and its partners a perpetual license to
the video, and Section 7B bars content violating a third party's publicity rights.

---

## 8. The non-authoring constraint, at every layer

The deliberation engine is the likeliest place for the authorship firewall to
erode, because it is the one component whose job is to *have opinions*.

| Layer | Permitted | Forbidden |
|---|---|---|
| **Poles** | Argue about approach | Propose any story content |
| **Synthesis** | Select which finding, set register | Select a *fix* |
| **Voice** | Render the decision in character | Add anything |

The failure mode to watch: `EXPANSION` arguing *"give the writer room"* is fine.
`EXPANSION` arguing *"give the writer room — suggest the sister could be the
antagonist"* has just written the script. **The poles argue about the response,
never about the story.**

Artie also never sees prose (04_agent_roster.md §1.1), so the deliberation engine has nothing to
rewrite even if it tried. The layered constraint is defense in depth on top of an
already-absent input.

---

## 9. Cost and latency

| Turn type | Calls | Approx. tokens |
|---|---|---|
| Ordinary (no axes) | 1 | ~1k |
| One axis | 3 | ~3k |
| Two axes | 4 | ~4k |

At `gemini-3.5-flash` pricing this is negligible — a full session of forty scenes with deliberation on perhaps a third of turns stays in single-digit dollars.

**Latency is the real cost.** Two axes means two pole calls plus a synthesis
call before Artie says anything. Run the pole calls **concurrently** — they are
independent — so the wall clock is one pole call plus synthesis, not three
sequential.

If it still drags, the fallback is a single axis per turn. Do not fall back to
zero: an Artie with no deliberation is a Gem with a costume.

---

## 10. The deliberation trace

Every deliberating turn emits a trace: which axes fired, what each pole argued
with what strength, what synthesis decided, what it held.

**Two uses, both real.**

**Provenance.** An `AI_DELIBERATION` event in the ledger (C1). It records that
the system reasoned about *how to respond* and demonstrably not about *what to
write* — the pole outputs are on record and they contain no story content. That
is evidence for the authorship claim, not just telemetry.

**Demo.** A panel showing Artie weighing *press harder (4)* against *back off (2)*
before he speaks is fifteen seconds that **proves** multi-agent orchestration
rather than claiming it. Nobody else in the field will have that shot, and it is
the difference between a judge seeing a chat interface and a judge seeing a
system.

Show the trace collapsed by default, expandable. It should feel like something
you *can* look at, not something you must.

---

## 11. Open items

1. **Pole quality is unmeasured.** Whether one call produces genuine
   opposition or two hedged paraphrases is an empirical question. Test early with real findings; if the poles read as the same position twice, split into two calls or move to `gemini-3.5-flash`.
2. **Strength calibration.** 1–5 with no anchoring will drift. Needs either
   few-shot examples in the prompt or a rubric.
3. **A3's counter thresholds are guesses.** `reask_count ≥ 2`, queue depth ≥ 4 —
   plausible, unvalidated. Tune against real sessions.
4. **The two-axis cap is untested.** It may prove too restrictive at gate
   completion, where several considerations legitimately compete.
5. **Register vocabulary is provisional.** `DIRECT / GENTLE / WRY` is a placeholder set. The persona session should define the real range, since register is the synthesis-to-voice contract and it should speak the persona's language.
