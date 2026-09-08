# Artie Spiegel — Master Blueprint v1.0
---

## 1. The system in one page

A browser-based screenwriting studio in which an AI showrunner runs the process
and the human writer retains sole authorship.

**Three agents.** Artie orchestrates and interrogates. The Script Supervisor reads
the text and judges it. The Director visualizes.

**One architectural decision above all others: Artie never reads screenplay
text.** He receives the Project Bible, the Scene Rig slots, and the Supervisor's
structured findings. Never prose. The authorship firewall is therefore a property
of the wiring rather than an instruction — an instruction can be jailbroken, an
absent input cannot.

*The agent you're talking to has never read your screenplay.*

**Two gates.** The **Greenlight** fills twelve slots once per project and produces
the Blueprint; completing it moves Artie from SKEPTICAL to COMMITTED. The **Scene
Rig** fills seven slots before each scene and resets every time.

**One diagnostic.** A 72-cell matrix — twelve narrative positions × six craft
lenses — scoring each scene, with an honest confidence gradient.

**One record.** An append-only provenance ledger producing a disclosure-ready
authorship manifest.

**Track:** IBM. Bob in development, Confluent at runtime. ClickHouse and Supabase
as permitted non-AI services.

---

## 2. Canonical document set

| Document | Governs |
|---|---|
| `docs/01_locked_axis.md` | The 72 cells, positions, lenses, confidence, weights |
| `docs/02_greenlight.md` | 12 blueprint slots, commitment state, register gating |
| `docs/03_scene_rig.md` | 7 scene slots, accept-first, genre modulation |
| `docs/04_agent_roster.md` | Agent boundaries, refusals, the reading boundary |
| `docs/05_orchestration.md` | Topology, events, handoff contracts, state partitioning |
| `docs/06_artie_mind.md` | Four axes, synthesis, voice interface |
| `docs/07_artie_persona.md` | Values, disposition weights, duality, libraries |
| `docs/08_artie_system_prompt.md` | The prompt itself — runtime asset |
| `docs/09_provenance_ledger.md` | Event taxonomy, hash chain, Confluent ingestion |
| `docs/10_clickhouse.md` | Matrix schema, coverage and gap queries |
| `docs/11_supabase.md` | Transactional schema, takes, RLS, boundary rules |
| `docs/12_manifest.md` | Capture, verification, disclosure mapping |
| `docs/13_director_assets.md` | Prompt pipeline, assumption note, portraits, GCS |
| `docs/14_editor.md` | Mode cycling, takes, scene builder, beacon |
| `docs/15_continuity.md` | Three tiers, grounding constraint, staleness |
| `docs/16_demo_beat_sheet.md` | **What gets built. Governs every cut decision.** |

---


## 3. Frozen contracts

**Freeze these before any construction. Every task references them; no task
regenerates them.**

### 3.1 ClickHouse — verified against v26.2 on Sep 3

| Table | Purpose |
|---|---|
| `positions_src` | 12 narrative positions |
| `lenses_src` | 6 craft lenses |
| `cells_src` | 72 cells: mode, confidence, weight, N/A condition |
| `scene_diagnoses` | Per-scene cell verdicts, append-only |
| `cell_slot_consumption` | Which Bible slots each cell reads — **required for narrowed re-diagnosis** |
| `bible_version_changes` | `changed_slots` per version |
| `provenance_events` | The ledger |
| `keystroke_batches` | Hash chain, `char_delta`, never characters |

DDL and all five queries executed successfully. `MergeTree` throughout, no
partitioning, `argMax` for latest-wins.

### 3.2 Supabase

`projects` · `bible_slots` · `scenes` · `takes` · `scene_rig_slots` ·
`script_components` · `characters` · `locations` · `world_rules` · `assets` ·
`agent_queue` · `sessions` · `continuity_checks`

RLS enabled on all, no policies. Backend uses the secret key.

**`script_components.take_id`**, not `scene_id` — per A4.

### 3.3 Slot inventory

**Greenlight — 12 required, 2 optional**

`S02` Protagonist · `S03` Want · `S04` Flaw · `S05` Antagonism · `S06` Thematic
Proposition · `S07` Status Quo Baseline · `S08` Arena · `S09` Genre · `S10`
Ending Shape · `S13` Working Title · `S14` Principal Characters · `S15` Target
Scene Count · *(optional)* `S11` World Rules · `TP1` Inciting Incident

**Scene Rig — 7 required**

`N01` Position · `N02` Alignment Character · `N03` Active Want · `N04` Obstacle ·
`N05` Scene Frame (`entry_state` → Y1, `value_at_stake` → Y2) · `N06` Location ·
`N07` Temporal Urgency

Plus at most two genre additions, **prompted but never gating**.

### 3.4 Event taxonomy

**Human:** `KEYSTROKE_BATCH` · `PASTE` · `COMPONENT_INSERTED` · `SCENE_SAVED` ·
`SLOT_ANSWERED` · `CONTINUITY_CHECK_REQUESTED`

**Agents:** `AGENT_QUESTION` · `AGENT_FINDING_DELIVERED` · `AGENT_EXAMPLE_SHOWN` ·
`AGENT_STORY_TOLD` · `AGENT_REFUSAL` · `AGENT_BEACON_LEFT` · `AI_DELIBERATION` ·
`SCENE_DIAGNOSED` · `CANON_FINDING` · `CONTINUITY_FINDINGS_DELIVERED` ·
`FRAME_PROMPT_CONSTRUCTED` · `FRAME_GENERATED`

**System:** `SESSION_OPENED` / `CLOSED` · `BIBLE_VERSION_CREATED` ·
`SLOT_PROVISIONAL` · `COMMITMENT_CHANGED` · `SCENE_STALE_MARKED` ·
`MANIFEST_EXPORTED` · `SCRIPT_EXPORTED`

**Agent payloads are stored in full, never summarized.** They are the evidence
that no agent supplied screenplay text.

### 3.5 Model assignment

| Component | Model |
|---|---|
| Artie conversation, synthesis, deliberation poles | `gemini-3.5-flash` |
| Cell judgments, canon check, slot predicates | `gemini-3.5-flash` |
| Director prompt construction | `gemini-3.5-flash` |
| **Assumption note (vision)**, continuity extraction | `gemini-3.8-flash` |
| Image generation | `gemini-3-pro-image` — $0.134/image verified |

### 3.6 The five registers

`Mentorial Anecdotal` · `Diagnostic Unsparing` · `Enthusiastic Advocacy`
(locked until COMMITTED) · `Borscht Belt Deflection` · `Transactional Boundary`

---

## 4. Verification list — confirm before implementing

| # | Item | Where |
|---|---|---|
| V1 | ADK current version, package relationships, `output_schema` tool restriction | 05_orchestration.md §10 |
| V2 | ADK event-trigger surface — is `Runner.run_async` still the documented-safe path? | 05_orchestration.md §10 |
| V3 | Model strings resolve; prices current | A1 |
| V4 | `gemini-3-pro-image` stable vs `-preview` | 13_director_assets.md §5 |
| V5 | ClickHouse Kafka table engine on Cloud — if available, drop the Python consumer | 09_provenance_ledger.md §8 |
| V6 | ClickHouse JSON column type stability — `String` ships if unclear | 09_provenance_ledger.md §9 |
| V7 | Fountain library maintenance — `screenplain`, `afterwriting` last release | Editor §12 |
| V8 | Cloud Run free-tier allotments | F1 |
| V9 | **What IBM accepts as evidence of Bob usage** | Track requirement |
| V10 | WGA MBA successor status after May 1, 2026 | 12_manifest.md §12.6 |
| V11 | **Assumption note vision call** — test on the three existing frames | 13_director_assets.md §13.2 |
| V12 | `cell_slot_consumption` mapping verified against the 72 cell questions | 10_clickhouse.md §9.3 |

---

## 5. Build order

**Phase 0 — Contracts.** Freeze §4. ClickHouse DDL already verified; run the
Supabase DDL. Nothing downstream regenerates these.

**Phase 1 — Spine.** Backend skeleton on Cloud Run. Confluent producer and
consumer. Supabase client. Three agent wrappers with the **firewall guard**
(05_orchestration.md §6) raising, not stripping.

**Phase 2 — Gates.** Greenlight and Scene Rig. Slot validation split into RULE and
JUDGMENT. Accept-first on the Rig.

**Phase 3 — The editor.** **Mode cycling first and tested hard** — it is the
highest-risk component and a broken one poisons everything after it in the demo.
Fountain emission with forcing characters. Takes.

**Phase 4 — Diagnosis.** Supervisor, cell judgments, canon check. Coverage
heatmap from live ClickHouse.

**Phase 5 — Deliberation.** Four axes, synthesis, voice. **The trace panel** — the
single most important shot in the demo.

**Phase 6 — Director.** Prompt pipeline, generation, assumption note, character
portraits.

**Phase 7 — Export.** Fountain → PDF, manifest, chain verification.

**Phase 8 — If time.** Continuity Tier 1. Nothing else.

---

## 6. Compliance

- [ ] Public repo, **OSI license visible in the About panel** — done
- [ ] Google Cloud SDK imported and called at runtime
- [ ] **Confluent imported and called at runtime** — satisfies the general 7B
      clause that a Bob-only submission leaves exposed
- [ ] IBM Bob used in development, with evidence per V9
- [ ] Hosted URL, reachable
- [ ] Demo video ≤ 3:00, English, public, **shows the product functioning**
- [ ] No non-Google, non-partner AI anywhere in the runtime
- [ ] Devpost writeup: features, technologies, data sources, **findings and
      learnings**
- [ ] IBM track selected
- [ ] **No real named individuals anywhere in product copy, persona output, or
      video**
- [ ] Original, unpublished demo screenplay
- [ ] No third-party marks or logos
- [ ] $100 credit secured — **$142.97 confirmed available**

---

## 7. Limitations to carry honestly

State these plainly rather than defending them. A conceded limitation you
identified yourself is more convincing than a defense.

1. **The matrix models one tradition.** Kishōtenketsu fails the Conflict column.
   Slow cinema fails X05.Y1. It is anchored in empirical corpora of classical
   Hollywood narrative and it **measures departure rather than judging it.**
2. **Isolated-protagonist survival narratives are systematically disadvantaged** —
   *Cast Away*, *All Is Lost*. Dialogue and Theme assume a populated world. **We
   could not answer this.** Concede it.
3. **The gate is deterministic; several predicates are model-evaluated.** Five
   Greenlight slots and three Rig slots are judgment-dominant. Do not claim full
   determinism.
4. **The hash chain is tamper-evident, not tamper-proof.** Client-side capture
   cannot defeat a determined forger. It evidences ordinary authorship, which is
   the standard the Copyright Office actually applies.
5. **Sixteen of 72 cells are EXTRAPOLATED or ANCHORED**, not attested. The matrix
   knows where it is weak, and says so.
6. **The Greenlight is hostile to discovery writers.** Hypothesis framing
   mitigates; the commitment reframe helps more.

**Never say:** ensures compliance · guarantees copyright · tamper-proof · proves
you wrote it · legally verified.

**Say:** preserves and evidences human authorship, and produces a
disclosure-ready provenance record.

---

## 8. Not built, and named as roadmap

Mobile reading surface · copyright filing assistance · script marketplace and
collaboration · C2PA Content Credentials on generated frames · continuity Tiers 2
and 3 · book-writing adaptation · docx and Google Docs export · multi-writer
collaboration.

The manifest is the enabling primitive for the marketplace: **a script with a
verified authorship record is a script you can hand to a buyer without a
provenance conversation.** Worth naming in the writeup — it shows where the
product goes.

---

## 9. Outstanding

1. **Demo lines** — session open, the refusing re-ask, the ANCHORED finding, the
   assumption note. Written by hand; these appear on camera.
2. **Commitment announcement** — the SKEPTICAL → COMMITTED beat, where *kid*
   becomes a first name.
3. **Craft Parables** — sources identified in `docs/07_artie_persona.md` §7.2;
   transpositions not yet drafted.
4. **War Stories** — four minimum. Trigger is an easter-egg phrase, not a core
   interaction.
5. **Invented-name registry** — approximately twenty entries, each with an
   attached detail so recurrence stays consistent.
