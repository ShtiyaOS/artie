# E2 / E3 Specification v1.0 — The Director and Asset Pipeline

**Status: CANONICAL.**

**Companions:** `docs/04_agent_roster.md` ·
`docs/05_orchestration.md` · `docs/09_provenance_ledger.md`
· `docs/11_supabase.md`

**Grounding.** Every behavioral claim below was **observed by direct testing of
`gemini-3-pro-image` on September 3, 2026**, not taken from documentation. Where
testing and the research brief disagreed, testing wins.

---

## 1. What the Director is for

Not a storyboard gallery. A **"show, don't tell" diagnostic.**

The Director composes an image prompt exclusively from what the writer wrote in
the scene, generates a frame, and reports **what the model filled in where the
description ran out.**

That last part is the product. Everything else is plumbing.

---

## 2. Three findings that determine the design

### 2.1 The model never signals under-specification

Given six words — *"INT. OFFICE - DAY. He waits."* — it produced an old man, a
fedora placed on his lap, a window, a clock reading 3:45, and a full lighting
scheme. All plausible, all confident, none requested.

Given *"sitting alone"* it added two out-of-focus men in the background —
compositionally literate, and a direct contradiction of an explicit instruction.

**Consequence: a fidelity check is impossible.** The Director cannot ask *"does
this match what you pictured?"* because the model always produces something
coherent. The note must instead be *here is what I filled in.*

### 2.2 Capitalized text renders into the frame

A prompt containing "HE WAITS" produced an image with those words drawn at the
bottom. Text rendering is a headline capability of this model, and screenplay
convention capitalizes character names, key props, and sounds.

**This is not an edge case. It is most Action lines.**

### 2.3 Descriptive persistence holds character at roughly 80%

The same character block, copied verbatim into a second scene at a different
angle, produced a recognizably similar but not identical person. Small specified
details — a scar — did not reliably appear.

Good enough for a few frames. It would drift visibly across twenty.

---

## 3. The isolation rule

The Director reads **the scene's Action lines and its scene heading. Nothing
else.**

No Bible. No Rig slots. No dialogue. No prior scenes.

Enrich the prompt and it renders what the *system* knows rather than what the
*page* says, and the note becomes meaningless.

Dialogue is excluded for the same reason Y6 excludes it: *if the dialogue were
muted, would this beat still read?*

### The one permitted enrichment

**Reference images only** — prior accepted frames of the same character.

Those carry no story information; they are the system's own prior output. Bible
character descriptions are **not** passed, even though they would help
consistency, because they are story content the page may not contain.

---

## 4. The prompt construction pipeline

Six steps. Model: `gemini-3.5-flash`.

### Step 1 — Extract

Take `ACTION` components and the `SCENE_HEADING` for the scene.

**Parse the heading; never pass it raw.** `INT. DINER - NIGHT` becomes structured
inputs — interior, a diner, night — because passing the slugline verbatim invites
§2.2's failure.

### Step 2 — Normalize capitalization

Convert ALL-CAPS words to title case. `MARLA` → `Marla`. `HE WAITS` → `He waits`.

**Do not lowercase everything** — that would strip proper nouns. The target is the
all-caps trigger specifically.

### Step 3 — Select the moment

Action often spans time: *"She crosses the room, opens the drawer, finds the
gun."* That is three moments; a frame is one.

The model selects the decisive instant.

**This is the closest the Director comes to authoring**, and it is why selection
is **always disclosed in the assumption note**. Choosing *finds the gun* over
*crosses the room* is a dramatic emphasis the writer did not explicitly make.
Surfaced, it is a question worth asking. Hidden, it is a liberty taken.

### Step 4 — Drop interiority, never replace it

*"She remembers her father"* is unfilmable. Drop it.

**Do not invent a filmable correlate.** If the writer supplied one — a photograph
in her hand — use theirs. If they did not, the frame will be weak.

**That weakness is the diagnostic working.** The Director must never compensate
for a thin description. Compensation destroys the instrument.

### Step 5 — Apply fixed baseline framing

Craft framing is added, and it is **identical on every frame**:

> cinematic still, natural framing, 35mm lens equivalent, lighting consistent with
> the described time and location, no text, lettering, captions, or writing
> anywhere in the image

**Fixed rather than tailored, and this is deliberate.** Tailored framing would
make weak descriptions produce good images and mask under-specification. Holding
craft constant means **the writer's description is the only variable**, which
makes the frames comparable to each other and the diagnostic meaningful.

Shot size, angle, and lens are cinematographic choices, not story choices — Y6
explicitly excludes them from the writer's domain — so supplying them is not
authoring.

### Step 6 — Restrain violence

Graphic description triggers `IMAGE_SAFETY` or `IMAGE_PROHIBITED_CONTENT`.
Sanitize toward restraint: a defeated figure in shadow rather than the injury.

**Disclose the sanitization in the note.** The writer should know their beat was
softened.

---

## 5. Generation

| | |
|---|---|
| Model | `gemini-3-pro-image` |
| Call | `client.models.generate_content(model=..., contents=prompt)` |
| Aspect | `16:9` |
| Size | `1K` for drafts, `2K` for demo frames |
| Cost | **$0.134 per image, verified** — 1,120 image tokens at $120/1M |

Note that ~252 thinking tokens were observed on Pro and thinking is not
disableable via the API. Budget for it.

The standard `generate_content` path works. The research brief described a newer
Interactions API with `response_format`; it is not required.

Output arrives as `image/jpeg` regardless of the requested filename extension —
name files by the actual mime type.

---

## 6. The assumption note

Two sources, combined.

**Deterministic — what the pipeline did:**

- which moment was selected, and from what span
- capitalization normalized
- interiority dropped, and which lines
- content sanitized, if any

**Model-generated — what the image contains that the prompt did not specify:**

One additional call to `gemini-3.8-flash`, passing the generated image and the
prompt. **The question is enumerated, never open-ended:**

> For each category below, state what the image shows and whether the prompt
> specified it. If the image does not show a category, answer `NOT_PRESENT`.
>
> - people present
> - objects held or worn
> - light source
> - time of day
> - weather

**Open-ended listing invites confabulation**, and an invented object would tell a
writer their description was thin where it was not — the machine-causes-the-human-
to-hallucinate failure the persona's value 6 exists to prevent. Fixed categories
with a forced `NOT_PRESENT` option give the model somewhere to go other than
inventing.

### How it is delivered

Never as *"does this match?"* Always as:

> **Here is what the model filled in where your description ran out. Are those the
> choices you would have made?**

The fedora placed on the lap rather than worn reads as *guest, not owner of this
office* — a character decision the writer never made and might want to make
deliberately. That is a better note than a fidelity check would have produced,
and it is honest about what the tool is doing.

**Cost per frame: 3 calls** — construction, generation, note. Roughly $0.14.

---

## 7. Character consistency

## 7. Character consistency — portraits

**A canonical portrait is generated once, at character creation**, from physical
description only — appearance, wardrobe, age, bearing. Never the flaw, the want,
or the arc. A portrait is a reference for the eye; letting psychology in makes it
an interpretation rather than a record.

Stored as `characters.character_portrait_uri`, passed as a reference image on
every subsequent frame featuring that character. The first accepted in-scene frame
may supersede it as `canonical_frame_uri`.

`gemini-3-pro-image` accepts up to **5 character references** within a 14-image
aggregate.

**Descriptive persistence from the Bible is not used.** Measured at roughly 80%
recognizable across an angle change — workable for a few frames, drifting visibly
across twenty. More importantly, Bible character descriptions are story content
the page may not contain, and passing them would breach §3's isolation rule.
**Reference images carry appearance and nothing else.**

Small distinguishing details may not survive generation — a specified scar did not
reliably appear in testing. Do not promise them. deliver.

### Considered and rejected

A free-form concept mode — the writer supplies a prompt, the Director offers
twenty candidate elements to include — was considered and rejected.

Once the system supplies candidate content, you can no longer tell whether a gap
was in the writer's description or filled from a menu. **Every frame must derive
from what the writer wrote, or the assumption note's claim does not hold.**

---

## 8. Failure handling

Read the **raw** response fields — some SDK wrappers drop image finish reasons.

| Condition | Meaning | Action |
|---|---|---|
| `promptFeedback.blockReason` set | Input blocked | Do not retry identically. Surface, offer a restrained rewrite. |
| `finish_reason == STOP`, no image part | Soft refusal or ambiguous prompt | One automatic rewrite, then surface |
| `finish_reason == IMAGE_SAFETY` | Output withheld | Surface. Identical retry is useless. |
| `finish_reason == IMAGE_PROHIBITED_CONTENT` | Output withheld | Surface. Do not retry. |
| `finish_reason == STOP`, image present | Success | Proceed |

**Every outcome emits `FRAME_GENERATED`** with the finish reason, including
failures. A blocked generation is a fact about the session and belongs in the
ledger.

Artie delivers a block as *"couldn't visualize that one"* — never as a
content-policy lecture.

---

## 9. Cost control

At $0.134 per Pro image, budget discipline is the one place spend can surprise
you.

| Rule | |
|---|---|
| Explicit trigger only | One button, on a completed scene. Never automatic. |
| One image per call | The model will not reliably produce an exact count |
| `1K` for iteration, `2K` for demo frames | |
| Downgrade path | `gemini-3.1-flash-image` at roughly half the cost, if drafts multiply |
| Budget alert | ~$50 threshold on the billing account |

A demo needing 20 frames costs under $3. A runaway loop is the only real risk, and
the explicit-trigger rule removes it.

---

# E3 — Asset Routing

Deliberately minimal. The original blueprint proposed event-driven serverless
media routing; that was cut as scope with no demo value.

## 10. Storage

**One bucket, `us-central1`**, matching every other service.

```
gs://{bucket}/projects/{project_id}/scenes/{scene_id}/{asset_id}.jpg
```

**Private. No public access.** The frontend displays frames via **time-limited
signed URLs** generated by the backend, typically one hour.

## 11. Write path

1. Director returns image bytes
2. Backend writes to GCS at the path above
3. Backend inserts the `assets` row (11_supabase.md §2.9) — `gcs_uri`, `model`, `prompt`,
   `assumption_note`, `finish_reason`
4. Backend publishes `FRAME_GENERATED` to Confluent
5. Supabase realtime notifies the frontend (11_supabase.md §6)

**Synchronous, in the request path.** No Cloud Functions, no Eventarc, no
pub/sub fan-out. At one image per explicit click, indirection buys nothing and
costs a day.

## 12. Retention

**Keep everything.** Storage is negligible and a deleted frame breaks the
manifest's asset record (12_manifest.md §6).

Frames survive scene deletion for the same reason — 11_supabase.md §8.6 flags the absence of
soft delete, and assets are the case where hard delete is clearly wrong.

---

## 13. Open items

1. **Moment selection is a model judgment presented as pipeline.** §4.3 discloses
   it in the note, which is the right mitigation, but it remains the one place the
   Director exercises editorial choice over the writer's scene.
2. **The assumption note's vision call is unmeasured.** Whether
   `gemini-3.5-flash` reliably identifies unspecified content in an image is
   untested. Test with the three existing frames before building on it.
3. **Fixed baseline framing may be too neutral for a compelling demo.** The
   diagnostic argument is sound and the visual argument may lose. Test both and
   decide with frames in hand.
4. **Reference-image drift across a long sequence is unmeasured.** 80% was
   measured at two frames. Twenty may be worse.
5. **Signed URL expiry versus manifest longevity.** The manifest records
   `gcs_uri`, which is not directly accessible later. Export should either bundle
   the images or record the path with a note on retrieval.
