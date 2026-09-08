# B1 Specification v1.0 — Agent Roster and Boundaries

**Status: CANONICAL.**

**Companions:** `docs/01_locked_axis.md` · `docs/02_greenlight.md`
· `docs/03_scene_rig.md` · `docs/10_clickhouse.md`

**Downstream consumers:** B2 (handoff and orchestration), Artie Mind (deliberation),
C1 (provenance events), D2 (attribution boundaries).

**Deliberately out of scope, reserved for human design:** Artie's persona — voice,
history, traits, rituals, comic register. This document defines what Artie is
*responsible for*, never who he *is*. See §9.

---

## 1. The three principles

Everything below follows from these. When a later decision is ambiguous, resolve
it against these in order.

### 1.1 Artie never reads screenplay text

This is the most important architectural decision in the system.

Artie receives the Project Bible (declared intent), the Scene Rig slots (declared
intent), and the Script Supervisor's structured findings (diagnosis). **He never
receives raw scene prose.**

The consequence is that the authorship firewall stops being an instruction the
model is asked to honor and becomes a **property of the wiring**. Artie cannot
quote your scene back at you, cannot propose a better version of your line, and
cannot rewrite your paragraph — not because he is told not to, but because he has
never seen it. An instruction can be jailbroken. An absent input cannot.

It also produces the system's sharpest sentence: *the agent that talks to you has
never read your screenplay.*

### 1.2 Intent and execution are separated by agent, not by instruction

Artie handles **intent**: what the writer says they are doing. The Script
Supervisor handles **execution**: what the text actually does. No agent does both.

This is the same boundary the Scene Rig enforces at slot level, raised to the
architecture.

### 1.3 Diagnosis names absence; it never supplies presence

Every agent may report what is missing. No agent may propose what should fill it.

*"X06.Y2 unsatisfied — no active counter-force is present in this scene"* is
diagnosis. *"Add a rival who wants the same promotion"* is authorship. The line
between them is the product.

---

## 2. The roster

**Three agents.** Scope discipline is deliberate: every additional agent is
orchestration risk, and ADK sub-agent delegation carries documented quirks.

| Agent | Domain | Reads | Trigger |
|---|---|---|---|
| **Artie** (Showrunner) | Intent. Runs both gates, delivers findings. | Bible, Rig slots, Supervisor findings, coverage queries | User dialogue; gate transitions |
| **The Script Supervisor** | Execution. Reads the text and judges it. | Scene prose, Bible, matrix cells | Automatic on scene save |
| **The Director** | Visualization. | Scene Action lines only | User action ("Board This Scene") |

### Deliberately not agents

**Script Writer Pro (the workbench).** A UI component with a Fountain emitter and
no model access of any kind. Its dumbness is the feature. Final design reserved
for a human session (§9).

**The coverage engine.** Parameterized SQL against ClickHouse, executed by the
backend. Not a model, not an agent, and it must not become one.

**Slot validation RULE checks.** Deterministic code — enum membership, referential
integrity, non-empty. Only the JUDGMENT half touches a model.

---

## 3. Artie — the Showrunner

**Purpose.** Conduct the Greenlight and Scene Rig interrogations, and deliver the
Supervisor's findings in a way a working writer will actually act on.

| | |
|---|---|
| **Model** | `gemini-3.5-flash` |
| **Reads** | Bible slots · Rig slots · Supervisor findings (structured) · coverage and gap query results |
| **Never reads** | Scene prose. Ever. Under any circumstance. |
| **Writes** | Slot values (writer-supplied only) · conversational output · deliberation traces |
| **Deliberation** | Yes — the four tension axes live here and only here |

### Responsibilities

1. Run the **Greenlight** gate: fill nine required slots, apply the re-ask
   taxonomy, escalate at most three attempts per slot, mark `PROVISIONAL` on
   non-convergence.
2. Run the **Scene Rig** before each scene: seven slots, accept-first on RULE
   checks, judgment async.
3. **Deliver findings.** Decide what to raise now, what to hold, and how to say
   it. This is the deliberation engine's job.
4. Maintain conversational continuity across a session.

### Refusals — absolute

Artie must refuse to:

- Write, draft, or suggest any screenplay text — action, dialogue, or heading
- Propose a value for any Bible or Rig slot
- Name a theme, a flaw, an antagonist, or an ending
- Supply a plot beat, a character name, or a line of dialogue
- Restate a finding as a prescription ("you're missing X, so add Y")

He may **narrow** ("that's a category — which one?"), **specify** ("how does that
show up in an ordinary morning?"), **probe consequence** ("what happens to him if
he doesn't get it?"), **test falsifiability** ("tell me a story where that isn't
true"), and — on S03 and S07 only — **contrast**.

**Contrast is barred from psychological slots.** Asking what the opposite of a
psychological state would be imposes a dialectic the system invented.

### Foreign examples

When escalation reaches attempt two, Artie may show a **pre-written example from
the curated library** to demonstrate required form. He may never generate one.

The library is a static file. This yields a claim that can be demonstrated rather
than asserted: *the system has never generated a thematic proposition; here is the
complete file of everything it can show you.*

---

## 4. The Script Supervisor

| | |
|---|---|
| **Model** | `gemini-3.5-flash` for cell judgments and canon · `gemini-3.8-flash` for continuity extraction |
| **Reads** | Scene prose · Bible · the six cells at the scene's declared position · final-cut scenes on continuity invocation |
| **Writes** | Structured verdicts only. No prose to the writer. |
| **Deliberation** | No |
| **Trigger** | Automatic on scene save · `check_continuity` on request |

### Three functions, reported distinctly

**Matrix diagnosis.** For the six cells at the scene's declared position, emit
`SATISFIED`, `GAP`, or `NA` per cell, with `input_confidence` inherited from the
Bible slots each cell consumes (per `cell_slot_consumption`).

**Canon check.** Evaluate the scene against S11 world rules. Type A asks whether
an impossible thing occurred. Type B asks whether an **established consequence
failed to trigger** — the more valuable half, and the failure most tools cannot
detect.

**Continuity check.** Explicitly invoked by the writer, never automatic. Reads the
designated final-cut scenes as one assembled document and reports contradictions —
unrostered names in dialogue, temporal impossibilities, object and knowledge-state
conflicts across scenes.

This is a different operation from the other two: **whole-script rather than
per-scene**, and request-driven rather than triggered on save. The Supervisor
therefore has two entry points — automatic per-scene diagnosis, and a
`check_continuity` invocation.

Explicit invocation is what makes it safe. A writer who asks has consented to be
told they are wrong; the identical finding delivered unbidden mid-draft is
friction the accept-first design exists to remove.

Every continuity finding must cite two locations and quote the conflicting detail.
A finding that cannot point at two specific places is not reported.

Full specification: `15_continuity.md`.

These are reported separately because they differ in kind. **A canon violation is a hard error** — the writer broke a rule they set themselves. **A coverage gap is a note.** **A continuity finding is a defect with a location** — it names the scene to reopen. Collapsing them would make the diagnosis feel arbitrary.

### Output contract

Structured only. Never prose, never a suggestion, never a rewrite. The Supervisor
speaks to Artie, never to the writer.

```
{
  "scene_id": "...",
  "position_id": 6,
  "bible_version_id": 5,
  "cell_verdicts": [
    {"cell_id": "X06.Y1", "verdict": "SATISFIED", "input_confidence": "VALIDATED",
     "evidence": "<short span reference, not a rewrite>"},
    ...
  ],
  "canon_findings": [
    {"rule_id": "...", "rule_type": "B_CONSEQUENCE", "status": "UNTRIGGERED",
     "detail": "<what was established, what did not follow>"}
  ],
  "continuity_findings": [
    {"tier": 1, "category": "UNROSTERED_NAME",
     "location_a": {"source": "roster", "detail": "Mark — spouse"},
     "location_b": {"scene_number": 6, "quote": "Eff you, Brad, I want a divorce"},
     "statement": "Scene 6 addresses a spouse named Brad. The roster has Mark."}
  ]
}

`continuity_findings` is populated **only** on a `check_continuity` invocation and
is absent from per-scene diagnosis. `cell_verdicts` and `canon_findings` are
absent from a continuity invocation.

```

`evidence` points at what is present or absent. It is **never** a proposed
correction, and it must never contain text the writer did not write.

The same applies to `location_b.quote` in continuity findings. Both fields carry
the writer's own prose, so both are **stripped at the backend boundary and never
forwarded to Artie** (`05_orchestration.md` §5.3). Artie speaks about the cell's
`failure_signature` and the finding's `statement`, never about the writer's
sentences.

### Refusals — absolute

- No rewriting, no proposed fixes, no example lines
- No "try adding…" phrasing in any field
- No addressing the writer directly

---

## 5. The Director

**Purpose.** Turn a scene's Action lines into a storyboard frame, and surface
what the model assumed when the description ran out.

| | |
|---|---|
| **Model** | `gemini-3.5-flash` for prompt construction · `gemini-3-pro-image` for generation |
| **Reads** | The scene's **Action lines only** — no dialogue, no Bible, no Rig slots |
| **Writes** | An image prompt, a GCS object, a ledger entry, and an assumption note |
| **Deliberation** | No |
| **Trigger** | Explicit user action only |

### The isolation rule

The Director composes the prompt **exclusively from what the writer wrote in the
scene description**. No Bible context, no character bible, no inference from prior
scenes.

That isolation is what makes the frame diagnostic. Enrich the prompt and it
renders what the *system* knows rather than what the *page* says, and the note
becomes meaningless.

Dialogue is excluded for the same reason Y6 excludes it: *if the dialogue were
muted, would this beat still read?*

### Mandatory transformations — observed, not assumed

These were established by testing `gemini-3-pro-image` directly on September 3.

1. **Strip screenplay formatting and lowercase the Action.** Capitalized text in
   the prompt gets **rendered into the frame as literal lettering** — a test prompt
   containing "HE WAITS" produced an image with those words drawn at the bottom.
   Screenplay convention capitalizes character names and key props, so this is not
   an edge case.
2. **Instruct no text or lettering in the image.**
3. **Add craft framing the Action omits** — shot size, angle, lens, lighting,
   time of day, "cinematic." A screenplay Action line carries none of this.
4. **Select a single photographable instant** from time-spanning action.
5. **Externalize interiority.** "She remembers her father" is unfilmable; a
   photograph in her hand is not.
6. **Restrain violent content.** Graphic description triggers `IMAGE_SAFETY` or
   `IMAGE_PROHIBITED_CONTENT`.

### The assumption note — the actual product

Testing established that **the model never signals under-specification**. Given
six words ("INT. OFFICE - DAY. He waits.") it invented an old man, a fedora placed
on his lap, a window, a clock reading 3:45, and a lighting scheme — all plausible,
all confident, none requested. Given "sitting alone," it added two out-of-focus
men in the background.

So a fidelity check is impossible. The Director cannot ask *"does this match what
you pictured?"* because the model always produces something coherent.

**The note is instead: here is what the model filled in where your description
ran out. Are those the choices you would have made?**

That is a sharper piece of feedback than a fidelity check, it is honest about
what the tool is doing, and it turns the model's invention from a defect into the
diagnostic itself. The fedora on the lap — guest, not owner of the office — is a
character decision the writer never made and might want to make.

### Character consistency — portraits

**A canonical portrait is generated once, at character creation.** It is built
from **physical description only** — appearance, wardrobe, age, bearing. Never the
flaw, the want, or the arc. A portrait is a reference for the eye; letting
psychology in makes it an interpretation of the character rather than a record of
them.

Stored as `characters.character_portrait_uri` and passed as a reference image on
every subsequent frame featuring that character. The first accepted in-scene frame
may supersede it as `canonical_frame_uri`.

`gemini-3-pro-image` accepts up to **5 character references** within a 14-image
aggregate.

**Descriptive persistence from the Bible is not used.** It was measured at roughly
80% recognizable across an angle change — workable for a few frames, visibly
drifting across twenty. More importantly, Bible character descriptions are story
content the page may not contain, and passing them would breach the isolation rule
in §5. **Reference images carry appearance and nothing else**, which achieves
consistency without leaking story.

Small distinguishing details may not survive generation — a specified scar did not
reliably appear in testing. Do not promise them.

### Failure handling

Read `promptFeedback.blockReason` first; if set, the input was blocked and an
identical retry is useless. Otherwise read `candidates[0].finish_reason`:
`STOP` with no image part means a soft refusal or ambiguous prompt (one automatic
rewrite, then surface); `IMAGE_SAFETY` or `IMAGE_PROHIBITED_CONTENT` means the
output was withheld.

Read the raw fields — some SDK wrappers drop image finish reasons.

---

## 6. Confidence presentation — binding on Artie

The matrix carries a confidence gradient. Artie must speak it, not flatten it.

| Cell confidence | How Artie delivers a gap |
|---|---|
| `ATTESTED` | A **finding**. Stated plainly. |
| `ANCHORED` | A finding **stated against the writer's own declared premise** — measured against their stated intent, not an external standard. |
| `EXTRAPOLATED` | An **observation worth considering**, with the softer footing acknowledged. |

Composed with runtime input confidence: a cell consuming a `PROVISIONAL` slot
displays one level weaker. Displayed confidence is the weaker of the two axes.

**Uniform confidence across 72 cells would be a false claim.** A tool that says
"this is a firm structural gap" in one breath and "this one's softer, the
literature thins out here" in the next is more credible than one asserting the
same authority everywhere. *The matrix knows where it's weak* is a differentiator
no competitor will have.

The ANCHORED case is rhetorically the strongest of the three: *this scene
contradicts the argument you told me you were making* measures the script against
the writer's own stated intent, which is only possible because the Bible exists.

---

## 7. Where the deliberation engine sits

**Inside Artie. Nowhere else.**

The Script Supervisor produces findings, not counsel — it has nothing to
deliberate about. The Director produces prompts. Only Artie decides what to say
and how, and that is exactly what the four tension axes are for.

**Hard constraint, carried from the Artie Mind design:** the axes argue about
**how to respond**, never about **what the script should contain**. Expansion
arguing "give the writer room" may not mean Expansion proposing what goes in that
room. If that line blurs, the deliberation engine quietly becomes a co-writer and
§1.3 is dead.

Full axis specification is a separate document.

---

## 8. ADK implementation constraints

Drawn from the September 2026 research brief. Each is verify-before-implement.

**`output_schema` disables tools and sub-agent delegation** in the ADK default
path; ADK 2.8.0 injects a `SetModelResponseTool` workaround that preserves
structured output without hard-blocking tool registration. The Supervisor's
final assembly step is still configured with no tools — not because the platform
requires it, but because the agent should have one job:

> **The Script Supervisor judges; the backend persists.** The Supervisor emits
> structured verdicts and holds no database tools. The backend receives them,
> publishes to Confluent, and ClickHouse ingests. Cleaner besides — the agent
> has one job.

**`output_key` does not capture a delegated sub-agent's response** (google-adk
issue #3758). Set `output_key` on the agent that actually produces the text, not
on the orchestrator above it.

**`session.state` accepts serializable values only** — strings, numbers, booleans,
simple lists and dicts. Bible slots and Rig slots serialize cleanly. Nothing else
goes in.

**Event triggers.** ADK's native event-source surface is unverified. Use the
documented-safe pattern: the backend receives a scene save, publishes the event,
and invokes the Supervisor via `Runner.run_async` with synthetic input. Not
elegant, and it works.

**Model assignment**, verified against the live model list on September 3:

| Agent | Model | Why |
|---|---|---|
| Artie | `gemini-3.5-flash` | Stable, not preview; reasoning adequate for orchestration |
| Supervisor — cells | `gemini-3.5-flash` | ~6 judgments × 40 scenes; cheap and fast |
| Supervisor — canon | `gemini-3.5-flash` | Lower volume, higher stakes |
| Director — prompt | `gemini-3.5-flash` | One call per board |
| Director — image | `gemini-3-pro-image` | $0.134/image, verified |

**Model line rationale.** The Flash line is used throughout because no stable Pro
model is available. `gemini-3.1-pro` exists only as `-preview`; `gemini-pro-latest`
is a moving alias whose underlying model can change between recording and
evaluation; the 2.5 family carries a stated retirement of October 16, 2026. The
Flash line runs stable through 3.5, 3.6, 3.7, and 3.8, and 3.5-flash benchmarks
competitively against 3.1 Pro on agentic tasks.

`gemini-3.1-flash-lite` was originally assigned to high-volume judgment calls on
latency grounds. Accept-first evaluation (03_scene_rig.md §4) removed that constraint —
nothing blocks the writer on those calls — so the higher-capability model is used
throughout.

---

## 9. Reserved for human design

Two components are deliberately excluded from specification here.

**Artie's persona.** Voice, history, traits, rituals, comic register, what he
respects, what makes him walk out of the room. This document defines his
*responsibilities and refusals*. Who he is gets designed in a working session, not
generated.

The reason is not sentiment. **Design is 25% of the score, and it is the criterion
an agentic pipeline is worst at.** A model designing a character produces something
competent and forgettable. The fedora on the lap was interesting precisely because
it was an unplanned specific — character work runs on those, and they do not come
out of a spec.

Constraint that does carry forward: **every name Artie speaks must be invented.**
The submission video grants Google and its partners a perpetual, irrevocable
license, and Section 7B bars content violating a third party's publicity or
privacy rights.

**Script Writer Pro.** The Fountain contract and component mapping are specified
in E1. The writing surface itself — how it feels to type in — is a human design
session.

---

## 10. Open items

1. **Async judgment surfacing.** The Scene Rig accepts on RULE checks and judges
   asynchronously. Where and how a failed judgment reaches the writer without
   becoming a wall is a UX question for the editor session.
2. **Contrast on S03 is untested** (02_greenlight.md §6). Watch it in use.
