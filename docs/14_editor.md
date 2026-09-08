# Script Writer Pro — Editor Specification v1.0

**Status: CANONICAL.** Supersedes Editor Design v0.1.

**Companions:** `docs/04_agent_roster.md` ·
`docs/09_provenance_ledger.md` · `docs/11_supabase.md`
· `docs/03_scene_rig.md` · `docs/02_greenlight.md`

**Amends:** 11_supabase.md §2.5 and §8.6 — see §6.

---

## 1. Principles

**The workbench is the only surface with a text cursor, and nothing generated ever
appears in it.** Not a suggestion, not a completion, not a beacon note. The
writer's pane holds the writer's words.

**Structure is a mode, not a form.** The writer types; the component model happens
around them.

**Artie never reads the text.** On submit, the Script Supervisor reads and emits
findings; Artie receives findings. The writer experiences *"Artie looked at my
scene"* and that experience is fully preserved — only the wiring differs, and the
wiring is what makes *"the agent you're talking to has never read your
screenplay"* true.

---

## 2. The component model

| Component | Fountain output | Forcing char |
|---|---|---|
| Scene Heading | `INT. DINER - NIGHT` | `.` |
| Action | plain paragraph | `!` |
| Character | `MARLA` | `@` |
| Dialogue | text beneath a cue | — |
| Parenthetical | `(quietly)` | — |
| Transition | `CUT TO:` | `>` |
| Note | `[[thought]]` | — |

**Always emit the forcing character.** The type is known, so there is no reason to
rely on Fountain's inference. This single decision determines output correctness.

`NOTE` is retained in the Fountain source and excluded from the PDF.

---

## 3. Mode cycling

The editor's state is **which component type the cursor is in.** Three ways it
changes.

### 3.1 Enter advances predictively

| Current | Enter → | Rationale |
|---|---|---|
| Scene Heading | Action | Something always happens next |
| Action | Action | Paragraphs run on |
| Character | Dialogue | A cue exists to be spoken |
| Dialogue | Character | Exchanges are the common case |
| Parenthetical | Dialogue | Returns to the line |
| Transition | Scene Heading | A transition ends a scene |

**Fall-through on empty.** Enter on an *empty* component of the predicted type
falls to the next likely one: an empty Character cue plus Enter means you did not
want dialogue, so you land in Action.

**That fall-through is what keeps prediction from trapping the writer**, and it is
the difference between this feeling like typing and feeling like a form.

### 3.2 Tab cycles manually

`Action → Character → Parenthetical → Dialogue → Transition → Scene Heading →
Action`

Override without leaving the keyboard.

### 3.3 Typing patterns switch implicitly

Beginning a line with `INT.`, `EXT.`, `EST.`, or `I/E` enters Scene Heading. An
opening parenthesis directly beneath dialogue enters Parenthetical.

### 3.4 The mode indicator

The current type is **always visible in the gutter.** The writer sees `ACTION`
sitting beside their cursor and learns the vocabulary by osmosis.

### 3.5 Instructional mode — default on a first project

The type palette is **docked open by default** for a writer's first project, each
type showing its keyboard shortcut.

It collapses automatically once the writer has used Tab several times, with a
one-line note saying where to reopen it. Toggleable at any time.

**Teach, then get out of the way.** Making it a buried setting would mean most
writers never discover the mode model at all.

---

## 4. The scene heading builder

Three inline controls when a Scene Heading opens:

| Control | Input |
|---|---|
| **INT / EXT** | toggle, plus `INT./EXT.` and `I/E` |
| **Location** | autocomplete from project locations; new entries accrete to the roster |
| **Time** | DAY · NIGHT · DAWN · DUSK · CONTINUOUS · LATER · MOMENTS LATER |

Produces a correct slugline every time without the writer memorizing the
convention — and makes it structurally obvious that a location or time change
requires a new heading, which is the most common formatting error a new
screenwriter makes.

---

## 5. Save and Submit

**Save is continuous and invisible.** Autosave on the 09_provenance_ledger.md §5 rhythm — 2 seconds
idle or 200 characters. Keystroke batches flow to the ledger. The writer never
thinks about it.

**Submit Scene is deliberate.** It closes a take (§6), fires `SCENE_SAVED`,
triggers the Supervisor, and queues findings for Artie.

Diagnosis on every autosave would be expensive, noisy, and would judge a
half-written scene. **Submit is the writer saying *I'm ready to be read*.**

Per-scene granularity is the unit throughout — a scene is a commit. It also keeps
Artie's context clean: the scene goes to storage and returns as findings, so no
prose accumulates anywhere near him. **Firewall and context management are the
same decision.**

---

## 6. Takes — amends 11_supabase.md §2.5 and §8.6

**Every submission of a scene is a take. Nothing is ever deleted or overwritten.**

- Scene 3, **Take 1** — submitted, diagnosed, findings delivered
- Reopening starts **Take 2**. Take 1 remains whole, with its diagnosis intact.
- The **current take** renders to PDF. Prior takes stay readable.

### Why takes

**It is the industry's own vocabulary**, so it teaches production grammar the way
the slug lines do — the director calls cut, and the slate reads *Scene 3, Take 2*.

**It removes deletion from the model.** 11_supabase.md §8.6 flagged the absence of soft delete
as probably wrong for a product about preserving a writer's work. Takes make hard
delete unnecessary rather than adding a delete-and-recover mechanism.

**It is excellent provenance.** The manifest can show *Scene 3 went four takes,
and here is what changed each time* — authorship development made visible, which
is D2's Claim 3.

### Final cut and history

**The writer designates one take per scene as the final cut.** Changeable at any
time.

Final cuts are what render to PDF, what the continuity check reads, and what
appears in the scene navigator's current view. Every other take lives in history,
organized by scene and take number.

That split answers §15.4's navigation problem: forty scenes at five takes is two
hundred component sets, and only forty of them are the script. Current view shows
the script; history is there when you want it.

The `takes` table carries `is_final_cut`, with a partial unique index enforcing
one per scene (`11_supabase.md` §2.4).

### Schema

A `takes` table sits between `scenes` and `script_components`:

```sql
create table takes (
    take_id      uuid primary key default gen_random_uuid(),
    scene_id     uuid not null references scenes on delete cascade,
    take_number  integer not null,
    is_current   boolean not null default true,
    submitted_at timestamptz,
    created_at   timestamptz not null default now(),
    unique (scene_id, take_number)
);
```

`script_components.scene_id` becomes `script_components.take_id`. Diagnoses attach
to a take, not a scene.

### Findings persist per take

Take 1's findings remain visible while writing Take 2. **The writer can see the
notes they are answering** — which is the entire point of a second take.

---

## 7. The Multi-Layered Scene Builder

Optional, on demand, when the writer asks for help setting up a scene.

**Sized to the scene, capped at 20 questions.**

The Scene Rig's seven slots are always required. The Builder adds depth-questions
based on what the scene actually contains:

| Signal | Adds |
|---|---|
| Multiple characters present | relationship and knowledge-state questions |
| New location | environment and sensory questions |
| Turning-point position (X02, X04, X06, X08, X11) | consequence and reversal questions |
| Active world rules | canon-consistency questions |
| Genre modulation class | the class's additional slots |

A man walking down a street who gets a phone call needs six. A three-hander at the
crisis needs eighteen. **Same slot logic as everywhere else — ask only what is
still empty.**

### The constraint that governs it

**Artie asks. The writer's words go on the page verbatim. Artie never rephrases
an answer into the script.**

The output is *the writer wrote fourteen sentences, one per question.* Not *Artie
assembled a paragraph from fourteen answers.* The question is scaffolding; the
sentence is theirs.

Get that backwards and the manifest shows machine composition over human
keystrokes, which is the thing eleven specifications exist to prevent.

**Lives in Artie's pane.** The answers land in the workbench as the writer types
them.

---

## 8. The Return Beacon

**Trigger:** 10 minutes with no keystroke, no slot activity, no chat.

Artie leaves a note in **his own pane** — never the workbench — assembled from
data he already holds:

- Scene and narrative position
- The Rig slots the writer declared
- Which component type was active
- Any finding queued but undelivered

> *You stepped out mid-action-line on twelve — the crisis. You'd told me she wants
> the letter and he won't hand it over. Pick it up there.*

He is reading their **declared intent** back to them, never their prose. Same
principle as Ideation Chat recall (02_greenlight.md §7): recalling what the writer said
is not authoring.

**It does not trip A3.** Stepping away is not struggling. Ten minutes idle means
absent; repeated short pauses *with edits between them* means stuck, and that is
what the friction counters measure. Conflating them would have Artie pressing
someone who went to make coffee.

Fires **once per absence**, waiting on return rather than pinging during.

Rendered through VOICE from structured facts. Register is warm — one of the few
places the caring layer surfaces unprompted.

New ledger event: **`AGENT_BEACON_LEFT`**, actor `artie`, under 09_provenance_ledger.md §3.2.

---

## 9. What Artie can see while you write

**Not the text. Ever.**

| Signal | Feeds |
|---|---|
| Active component type | conversational context |
| Character count and delta | A3 friction counters |
| Time since last keystroke | A3 counters · Return Beacon |
| Scene and declared position | Rig context |

Artie can know **that** you are stuck without knowing **what** you wrote. The
firewall and the character reinforce each other rather than compete.

---

## 10. Autocomplete — narrow and deliberate

| Where | Source |
|---|---|
| Character component | project roster (11_supabase.md §2.6); new names accrete |
| Scene heading location | project locations (11_supabase.md §2.7); new locations accrete |

**Nothing else autocompletes.** These are the writer's own names and places
recalled back to them. Recalling what they wrote is not authoring; predicting what
they might write is.

**Spell check is permitted** — a deterministic dictionary. **No model-driven
grammar, style, or continuation suggestions anywhere in the workbench.** Not as a
setting, not as an opt-in.

---

## 11. Capture

**Keystroke batches** — close on 2s idle or 200 characters. Store `component_id`,
`char_delta`, `chain_hash`. **Never the characters** (09_provenance_ledger.md §5).

**Paste** — logged, never blocked. `origin: INTERNAL | UNKNOWN`, character count,
target component (09_provenance_ledger.md §6). Blocking breaks screen readers, voice input, and motor
accessibility, and prevention is theatre. Artie notices a large `UNKNOWN` paste
and states the consequence without accusing (07_artie_persona.md §9.2).

---

## 12. Export

**Fountain is the source of truth.** Everything renders from it.

| Format | Purpose |
|---|---|
| **PDF** | The industry deliverable — `screenplain` + ReportLab |
| **Fountain** | Plain text, portable, re-importable. The writer's escape hatch. |
| **FDX** | Final Draft interchange. `screenplain` emits it at near-zero cost. |
| **Authorship manifest** | 12_manifest.md §10, exports alongside |

**Discarded:** markdown (cannot represent screenplay format — no indent
positions, no fixed-width layout), docx, Google Docs. All roadmap or dropped.

The manifest's content hash derives from the **Fountain source**, never the
rendered PDF — PDF generation is not byte-stable and the terminus check would
fail spuriously (12_manifest.md §12.3).

---

## 13. Layout

| Pane | Holds |
|---|---|
| **Left** | Scene navigator (with takes) · blueprint view · coverage heatmap · assets |
| **Center** | Artie — chat, findings, Scene Builder, Return Beacon |
| **Right** | The workbench |

---

## 14. What the editor must never do

- Accept AI-generated text into a component
- Autocomplete content
- Suggest a continuation
- Offer a model-driven rewrite
- Block paste
- Delete a take
- Place a beacon, note, or finding in the workbench
- Silently alter what the writer typed

---

## 15. Open items

1. **Mode-cycling fall-through needs live testing.** §3.1 is the design's central
   risk; whether it feels like typing is answerable only in the hands.
2. **Instructional-mode collapse threshold is a guess** — "several Tab presses"
   needs a number.
3. **Scene Builder question ordering is unspecified.** Which depth-questions come
   first likely matters to whether it feels like help or interrogation.
4. **Concurrent takes are impossible by design** — one current take per scene.
   Fine for single-writer; note it for collaboration.
5. **Mobile is out of scope**, deferred to the October update as a reading surface.
