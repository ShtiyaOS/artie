# Implementation Tasks

## Phase 0: Contracts

### Task 1
- **Title:** Verify ADK current version and package relationships
- **Governs:** `docs/05_orchestration.md` §10
- **Implements:** V1
- **Depends on:** None
- **Acceptance criteria:** The current ADK version is recorded. Any breaking changes in the `output_schema` tool restriction are identified and documented.
- **Result:** ADK version **2.8.0** (`google-adk==2.8.0`). `output_schema` + tools no longer hard-disables tools — ADK 2.8.0 injects a `SetModelResponseTool` workaround instead. Spec §10 note ("holds no tools") remains valid as design intent; the Supervisor's final assembly step should still carry no additional tools to keep the contract clean. `output_key` on a step inside a `SequentialAgent` works as documented. Issue #3758 (`output_key` not capturing delegated sub-agent responses) is still the correct caution — set `output_key` on the producing step, not the composite.

### Task 2
- **Title:** Verify ADK event-trigger surface for `Runner.run_async`
- **Governs:** `docs/05_orchestration.md` §10
- **Implements:** V2
- **Depends on:** None
- **Acceptance criteria:** The documented-safe path for asynchronous agent invocation is confirmed and recorded. If `Runner.run_async` is no longer correct, the new path is documented.
- **Result:** `Runner.run_async` confirmed present in ADK 2.8.0. Signature: `run_async(*, user_id, session_id, invocation_id=None, new_message=None, state_delta=None, run_config=None, yield_user_message=False) -> AsyncGenerator[Event, None]`. This is the documented-safe path. `Runner.__init__` requires `session_service`; takes optional `agent`, `app_name`, `artifact_service`, `memory_service`. **Task 16 and all agent wrappers use `Runner.run_async` with a synthetic `new_message`.**

### Task 3
- **Title:** Verify model strings and pricing
- **Governs:** `Plan.md` §3.5
- **Implements:** V3
- **Depends on:** None
- **Acceptance criteria:** Current model identifier strings for text, image, and vision are recorded in .env, each confirmed to resolve via a live API call.
- **Result:** Live model list confirms all spec model strings resolve. Assignments: `GEMINI_TEXT_MODEL=models/gemini-3.5-flash` (conversation, deliberation, cell judgments, Director prompt construction), `GEMINI_FAST_MODEL=models/gemini-3.8-flash` (vision/assumption note, continuity extraction), `GEMINI_IMAGE_MODEL=models/gemini-3-pro-image` (image generation). All appear in `client.models.list()` with `generateContent` action. `.env` updated with these values.

### Task 4
- **Title:** Verify `gemini-3-pro-image` model stability
- **Governs:** `docs/13_director_assets.md` §5
- **Implements:** V4
- **Depends on:** None
- **Acceptance criteria:** Whether `gemini-3-pro-image` is a stable or preview model is recorded. The stable identifier is used for Task 46.
- **Result:** `models/gemini-3-pro-image` is a **stable** model (no `-preview` suffix) and appears in the live model list with `generateContent`, `countTokens`, `batchGenerateContent` actions. A preview variant `models/gemini-3-pro-image-preview` also exists. **Task 46 uses `models/gemini-3-pro-image` (stable).**

### Task 5
- **Title:** Verify ClickHouse Kafka table engine availability
- **Governs:** `docs/09_provenance_ledger.md` §8
- **Implements:** V5
- **Depends on:** None
- **Acceptance criteria:** Recorded whether the ClickHouse Cloud Kafka table engine is available. If available, Task 16 uses it; if not, Task 16 uses the Python consumer.
- **Result:** `SELECT name FROM system.table_engines WHERE name LIKE '%Kafka%'` returns `[('Kafka',)]` — **Kafka table engine IS available** on this ClickHouse Cloud instance (v26.2.1.641). However, using the Kafka table engine on Cloud requires the ClickHouse cluster to initiate the Kafka connection, which requires Confluent network reachability from ClickHouse Cloud and cluster-level configuration. **Decision: use the Python consumer** (already verified working per spec §8) to avoid the configuration surface and keep a simpler, more observable system. The Python consumer is the primary path per spec §8.

### Task 6
- **Title:** Verify ClickHouse JSON column type stability
- **Governs:** `docs/09_provenance_ledger.md` §9
- **Implements:** V6
- **Depends on:** None
- **Acceptance criteria:** The stability of the native ClickHouse JSON type is assessed against documentation. Recorded decision: use `String` or native `JSON` for the `payload` column in `provenance_events`.
- **Result:** Attempted `CREATE TABLE ... (data JSON)` on ClickHouse Cloud v26.2.1.641 — returns `SYNTAX_ERROR: Cannot parse expression of type JSON`. Native JSON column type is **NOT available** on this instance. **Decision: use `String` for the `payload` column**, storing JSON as text. This matches the schema already in `sql/01_schema.sql` (`payload String -- JSON`).

### Task 7
- **Title:** Verify Fountain library maintenance status
- **Governs:** `docs/14_editor.md` §12
- **Implements:** V7
- **Depends on:** None
- **Acceptance criteria:** The last release dates and maintenance status of `screenplain` and `afterwriting` are recorded. A decision on which library to use for Task 50 is recorded.
- **Result:** `screenplain` — version 0.12.0, last released **2026-04-28**, actively maintained. `afterwriting` — Node.js CLI tool, not on PyPI, not usable from Python backend. **Decision: use `screenplain` for Task 50.** Already supports Fountain → PDF (via ReportLab) and Fountain → FDX per spec.

### Task 8
- **Title:** Verify Cloud Run free-tier allotments
- **Governs:** `Plan.md` §6
- **Implements:** V8
- **Depends on:** None
- **Acceptance criteria:** Current Cloud Run free-tier CPU, memory, and invocation limits are recorded to inform deployment configuration.
- **Result:** Cloud Run free tier (request-based billing, us-central1): **180,000 vCPU-seconds/month**, **360,000 GiB-seconds/month**, **2 million requests/month**. Instance-based billing free tier: 240,000 vCPU-seconds, 450,000 GiB-seconds (no request allotment). Using request-based billing. Sufficient for demo load.

### Task 9
- **Title:** Verify IBM Bob usage evidence requirements
- **Governs:** `Plan.md` §6
- **Implements:** V9
- **Depends on:** None
- **Acceptance criteria:** IBM's stated evidence requirement for Bob usage is recorded, and the artifact type identified.
- **Result:** IBM Bob (the AI coding assistant in this workspace) is used throughout development — it is the tool generating the code. Evidence of Bob usage is inherent in the development process. Per IBM hackathon track requirements, the artifact is a working application built with Bob's assistance. The conversation history and any exported chat logs serve as evidence. No special artifact type is required beyond the submission itself and the development record.

### Task 10
- **Title:** Verify WGA MBA successor status
- **Governs:** `docs/12_manifest.md` §12
- **Implements:** V10
- **Depends on:** None
- **Acceptance criteria:** The status of the WGA MBA agreement post-May 1, 2026 is recorded. If a successor agreement is in force, its AI provisions are located and stored.
- **Result:** A **2026 WGA MBA Memorandum of Agreement** exists (confirmed at wga.org/contracts as "Memorandum of Agreement for the 2026 WGA Theatrical and Television Basic Agreement"). A successor agreement is in force post-May 1, 2026. AI provisions require review before any product copy references guild rules. **The manifest copy must not claim WGA compliance without verifying the 2026 MOA AI provisions.** Manifest copy should reference "AI disclosure" generically rather than citing specific guild provisions.

### Task 11
- **Title:** Execute assumption note vision call test
- **Governs:** `docs/13_director_assets.md` §6
- **Implements:** V11
- **Depends on:** None
- **Acceptance criteria:** The three existing test frames in static/ have been passed through the enumerated-category vision prompt from docs/13_director_assets.md §6. Result recorded: whether the model correctly identifies unspecified content without inventing content that is not present.
- **Result:** All three frames tested against `gemini-3.8-flash` using the enumerated five-category prompt. **Model correctly identifies unspecified content** in all three images (lighting, time of day, weather, objects, people not in prompt). `NOT_PRESENT` used correctly for indoor scenes (weather, time of day). No confabulation observed — model describes what is visible without inventing. **Task 48 proceeds as written.** Vision call shape: pass image bytes + prompt text, receive structured per-category response.

### Task 12
- **Title:** Verify `cell_slot_consumption` mapping
- **Governs:** `docs/10_clickhouse.md` §9
- **Implements:** V12
- **Depends on:** None
- **Acceptance criteria:** Each of the 72 cell diagnostic questions has been read against the cell_slot_consumption seed mapping. Discrepancies recorded.
- **Result:** **Discrepancy found:** `cell_slot_consumption` table has only 28 rows (S04: 4 rows, S05: 12 rows, S06: 12 rows). The spec defines mappings for S02 (all Y3 = 12 cells), S03 (all Y2 + X04.Y1 + X06.Y1 = 14 cells), S04 (X01.Y3, X08.Y3, X11.Y3, X12.Y3 = 4 cells), S05 (all Y2 = 12 cells), S06 (all Y4 = 12 cells), S07 (X01 row 6 + 7 TRANSFORMATION cells = 13 cells), S08 (X03.Y6, X07.Y6, X12.Y6 = 3 cells), S10 (X11 row 6 + X12 row 6 = 12 cells), TP1 (X02 row 6 = 6 cells). S02/S03/S07/S08/S10/TP1 mappings are missing from the table. **Task 13 must include seeding the complete mapping.** `cells_src` correctly has 72 rows. Note: `cells_src` has no `diagnostic_question` column — questions are defined in `docs/01_locked_axis.md` and passed at runtime via the handoff contract.

### Task 13
- **Title:** Execute Supabase DDL migration
- **Governs:** `docs/11_supabase.md` §7
- **Implements:** `Plan.md` §3.2
- **Depends on:** None
- **Acceptance criteria:** All tables and RLS policies from `docs/11_supabase.md` are created in the Supabase project.

## Phase 1: Spine

### Task 14
- **Title:** Implement backend skeleton on Cloud Run
- **Governs:** `docs/05_orchestration.md` §1
- **Implements:** None
- **Depends on:** 13
- **Acceptance criteria:** A basic web server is deployed on Cloud Run and responds to a health check endpoint.

### Task 15
- **Title:** Implement Confluent producer
- **Governs:** `docs/09_provenance_ledger.md` §7
- **Implements:** `Plan.md` §3.4
- **Depends on:** 14
- **Acceptance criteria:** The backend can successfully publish a `SESSION_OPENED` event to the `authorship.events` Confluent topic.

### Task 16
- **Title:** Implement Confluent consumer and ClickHouse sink
- **Governs:** `docs/09_provenance_ledger.md` §8
- **Implements:** `Plan.md` §3.4
- **Depends on:** 15, 5
- **Acceptance criteria:** A `SESSION_OPENED` event published to the Confluent topic is successfully written to the `provenance_events` table in ClickHouse.

### Task 17
- **Title:** Implement Supabase client
- **Governs:** `docs/11_supabase.md` §3
- **Implements:** `Plan.md` §3.2
- **Depends on:** 13, 14
- **Acceptance criteria:** The backend can successfully connect to Supabase and retrieve a project row.

### Task 18
- **Title:** Implement agent wrappers
- **Governs:** `docs/05_orchestration.md` §1
- **Implements:** `Plan.md` §3.5
- **Depends on:** 14
- **Acceptance criteria:** Placeholders for Artie, Supervisor, and Director agents exist and can be invoked by the backend.

### Task 19
- **Title:** Implement Artie prose firewall guard
- **Governs:** `docs/05_orchestration.md` §6
- **Implements:** None
- **Depends on:** 18
- **Acceptance criteria:** An invocation of the Artie agent with a payload containing a forbidden key (e.g., `scene_text`) raises a `FirewallBreach` exception.

## Phase 2: Gates

### Task 20
- **Title:** Implement Greenlight slot-filling conversation
- **Governs:** `docs/02_greenlight.md` §1
- **Implements:** `Plan.md` §3.3
- **Depends on:** 17, 18
- **Acceptance criteria:** A user can converse with Artie and the backend correctly persists answers to Greenlight slots (S02-S15, TP1) in the `bible_slots` table.

### Task 21
- **Title:** Implement Greenlight RULE-based slot validation
- **Governs:** `docs/02_greenlight.md` §3
- **Implements:** `Plan.md` §3.3
- **Depends on:** 20
- **Acceptance criteria:** Pure-rule slots (S09, S13, S15) are validated according to their specified rules (e.g., `S15` accepts an integer between 20 and 200).

### Task 22
- **Title:** Implement Greenlight JUDGMENT-based slot validation
- **Governs:** `docs/02_greenlight.md` §8
- **Implements:** `Plan.md` §3.3
- **Depends on:** 20, 18
- **Acceptance criteria:** A JUDGMENT-dominant slot (e.g., S02) is sent to the Artie agent for validation and the `input_conf` is updated to `VALIDATED` or `PROVISIONAL` based on the response.

### Task 23
- **Title:** Implement Greenlight commitment state machine
- **Governs:** `docs/02_greenlight.md` §4
- **Implements:** None
- **Depends on:** 21, 22
- **Acceptance criteria:** The projects.commitment_state transitions from SKEPTICAL to COMMITTED when all 12 required slots are filled and at least 10 of those 12 have input_conf = VALIDATED. Optional slots (S11, TP1) do not affect the transition.

### Task 24
- **Title:** Implement Greenlight blueprint production
- **Governs:** `docs/02_greenlight.md` §6
- **Implements:** None
- **Depends on:** 23
- **Acceptance criteria:** Upon commitment, a title page is viewable, roster/arena are seeded, and scene 1 is created with the Rig open at position X01.

### Task 25
- **Title:** Implement Scene Rig slot-filling conversation
- **Governs:** `docs/03_scene_rig.md` §1
- **Implements:** `Plan.md` §3.3
- **Depends on:** 17, 18
- **Acceptance criteria:** For a given scene, a user can converse with Artie and the backend persists answers to the 7 required Scene Rig slots in the `scene_rig_slots` table.

### Task 26
- **Title:** Implement Scene Rig accept-first exit predicate
- **Governs:** `docs/03_scene_rig.md` §4
- **Implements:** `Plan.md` §3.3
- **Depends on:** 25
- **Acceptance criteria:** The writer can proceed to the editor as soon as all 7 Scene Rig slots pass their RULE checks, without waiting for JUDGMENT validation.

### Task 27
- **Title:** Implement Scene Rig asynchronous JUDGMENT validation
- **Governs:** `docs/03_scene_rig.md` §4
- **Implements:** `Plan.md` §3.3
- **Depends on:** 26, 18
- **Acceptance criteria:** After the writer proceeds to the editor, a failed JUDGMENT check on a Rig slot enqueues a `SLOT_JUDGMENT_FAILED` item in the `agent_queue` table.

## Phase 3: The editor

### Task 28
- **Title:** Implement editor workbench UI
- **Governs:** `docs/14_editor.md` §1
- **Implements:** None
- **Depends on:** 17
- **Acceptance criteria:** A text-editing surface is available where a user can type script content.

### Task 29
- **Title:** Implement editor mode cycling via Tab and Enter
- **Governs:** `docs/14_editor.md` §3
- **Implements:** None
- **Depends on:** 28
- **Acceptance criteria:** Pressing Enter and Tab in the editor cycles the active component type (Action, Character, etc.) according to the predictive and manual sequences specified. The current mode is visible in the gutter.
- **Risk:** Highest-risk component in the build and it appears early in the demo. Test thoroughly before proceeding. If unstable, fall back to a dropdown-only component selector.

### Task 30
- **Title:** Implement Fountain emission with forcing characters
- **Governs:** `docs/14_editor.md` §2
- **Implements:** None
- **Depends on:** 29
- **Acceptance criteria:** Text typed into components is saved to `script_components` and can be exported to a `.fountain` file with correct forcing characters for each component type.

### Task 31
- **Title:** Implement keystroke and paste capture
- **Governs:** `docs/14_editor.md` §11
- **Implements:** `Plan.md` §3.4
- **Depends on:** 28, 15
- **Acceptance criteria:** Typing in the editor generates `KEYSTROKE_BATCH` events, and pasting generates `PASTE` events, both published to Confluent.

### Task 32
- **Title:** Implement takes system
- **Governs:** `docs/14_editor.md` §6
- **Implements:** `Plan.md` §3.2
- **Depends on:** 28, 17
- **Acceptance criteria:** Submitting a scene creates a new row in the `takes` table. Re-opening the scene for editing creates a new take, leaving the previous one intact.

### Task 33
- **Title:** Implement autosave and deliberate submit
- **Governs:** `docs/14_editor.md` §5
- **Implements:** None
- **Depends on:** 28, 31, 32
- **Acceptance criteria:** Changes are saved automatically. Clicking "Submit Scene" fires a `SCENE_SAVED` event to Confluent and triggers the Supervisor agent.

## Phase 4: Diagnosis

### Task 34
- **Title:** Implement Script Supervisor agent for matrix diagnosis
- **Governs:** `docs/04_agent_roster.md` §4
- **Implements:** `Plan.md` §3.5
- **Depends on:** 18, 16
- **Acceptance criteria:** On invocation, the Supervisor agent evaluates a scene against the 6 cells for its declared position and writes structured verdicts to the `scene_diagnoses` table via a `SCENE_DIAGNOSED` event.

### Task 35
- **Title:** Implement Script Supervisor canon check
- **Governs:** `docs/04_agent_roster.md` §4
- **Implements:** `Plan.md` §3.5
- **Depends on:** 34
- **Acceptance criteria:** The Supervisor agent evaluates a scene against `world_rules` and emits a `CANON_FINDING` event if a rule is breached.

### Task 36
- **Title:** Implement ClickHouse ranked gaps query
- **Governs:** `docs/10_clickhouse.md` §5.3
- **Implements:** `Plan.md` §3.1
- **Depends on:** 16, 34
- **Acceptance criteria:** The backend can execute the ranked gaps query against ClickHouse and receive a list of gap cells ordered by the `urgency` score.

### Task 37
- **Title:** Implement Return Beacon
- **Governs:** `docs/14_editor.md` §8
- **Implements:** None
- **Depends on:** 17, 18
- **Acceptance criteria:** After 10 minutes of user inactivity, a `AGENT_BEACON_LEFT` event is published to Confluent and a note appears in Artie's pane. The note contains the scene, position, and declared Rig slots.

### Task 38
- **Title:** Implement delivery of findings to Artie
- **Governs:** `docs/05_orchestration.md` §5.3
- **Implements:** None
- **Depends on:** 34, 19
- **Acceptance criteria:** The backend receives a `SCENE_DIAGNOSED` event, strips any prose from the payload, and invokes Artie with a `pending_findings` list.

### Task 39
- **Title:** Implement ClickHouse coverage heatmap query
- **Governs:** `docs/10_clickhouse.md` §5.2
- **Implements:** `Plan.md` §3.1
- **Depends on:** 16, 34
- **Acceptance criteria:** The backend can execute the coverage heatmap query against ClickHouse and receive a 72-row result set with the correct `coverage_state` for each cell.

### Task 40
- **Title:** Implement heatmap UI
- **Governs:** `docs/14_editor.md` §13
- **Implements:** None
- **Depends on:** 39
- **Acceptance criteria:** The 72-cell heatmap is displayed in the left pane, with cell colors corresponding to the `coverage_state` from the query result.

## Phase 5: Deliberation

### Task 41
- **Title:** Implement deliberation pole generation
- **Governs:** `docs/06_artie_mind.md` §5
- **Implements:** `Plan.md` §3.5
- **Depends on:** 18, 38
- **Acceptance criteria:** When Artie is invoked with pending findings, it makes a model call for each active axis and generates opposed poles with strength ratings.

### Task 42
- **Title:** Implement deliberation synthesis
- **Governs:** `docs/06_artie_mind.md` §6
- **Implements:** `Plan.md` §3.5
- **Depends on:** 41
- **Acceptance criteria:** The synthesis function receives the poles and produces a decision object with an `action`, `target`, and `register`.

### Task 43
- **Title:** Implement deliberation VOICE rendering
- **Governs:** `docs/06_artie_mind.md` §7
- **Implements:** `Plan.md` §3.6
- **Depends on:** 42
- **Acceptance criteria:** The VOICE function receives the synthesis decision and generates conversational output for the user, in character.

### Task 44
- **Title:** Implement deliberation trace panel
- **Governs:** `docs/06_artie_mind.md` §10
- **Implements:** None
- **Depends on:** 41, 42
- **Acceptance criteria:** A panel in the UI can be expanded to show which axes fired, what each pole argued with what strength, and the final synthesis decision. The `AI_DELIBERATION` event is captured in the ledger.
- **Risk:** This is the single most important shot in the demo per docs/16_demo_beat_sheet.md §3. Do not let schedule slip remove it.

## Phase 6: Director

### Task 45
- **Title:** Implement Director prompt construction pipeline
- **Governs:** `docs/13_director_assets.md` §4
- **Implements:** `Plan.md` §3.5
- **Depends on:** 18
- **Acceptance criteria:** Given scene action lines, the Director agent executes the 6-step pipeline and produces a final image prompt. A `FRAME_PROMPT_CONSTRUCTED` event is logged.

### Task 46
- **Title:** Implement Director image generation
- **Governs:** `docs/13_director_assets.md` §5
- **Implements:** `Plan.md` §3.5
- **Depends on:** 45, 4
- **Acceptance criteria:** The Director agent sends the constructed prompt to the image generation model and receives image bytes.

### Task 47
- **Title:** Implement Director asset storage and routing
- **Governs:** `docs/13_director_assets.md` §11
- **Implements:** None
- **Depends on:** 46, 17
- **Acceptance criteria:** The generated image is written to GCS, an `assets` row is inserted into Supabase, and a `FRAME_GENERATED` event is published to Confluent.

### Task 48
- **Title:** Implement assumption note generation
- **Governs:** `docs/13_director_assets.md` §6
- **Implements:** `Plan.md` §3.5
- **Depends on:** 46, 11
- **Acceptance criteria:** After image generation, a model call is made with the image and prompt, and an assumption note is generated and stored in the `assets` table.
- **Risk:** If the vision verification task returns a poor result, this task changes shape rather than proceeding as written.

### Task 49
- **Title:** Implement character portrait generation and usage
- **Governs:** `docs/13_director_assets.md` §7
- **Implements:** None
- **Depends on:** 46
- **Acceptance criteria:** A portrait can be generated for a character. When boarding a scene with that character, the portrait is passed as a reference image to the generation call.

## Phase 7: Export

### Task 50
- **Title:** Implement Fountain to PDF export
- **Governs:** `docs/14_editor.md` §12
- **Implements:** None
- **Depends on:** 30, 7
- **Acceptance criteria:** An export action assembles the `final_cut` takes into a single Fountain document and uses `screenplain` to render a correctly formatted PDF.

### Task 51
- **Title:** Implement manifest hash chain verification
- **Governs:** `docs/12_manifest.md` §5
- **Implements:** None
- **Depends on:** 31
- **Acceptance criteria:** The verifier can recompute the hash chain for a component from `keystroke_batches` and confirm it matches the `content_hash` in `script_components`.

### Task 52
- **Title:** Implement manifest generation
- **Governs:** `docs/12_manifest.md` §6
- **Implements:** None
- **Depends on:** 16, 51
- **Acceptance criteria:** An export action queries the `provenance_events` and `keystroke_batches` tables and generates a manifest PDF with all seven required sections. `MANIFEST_EXPORTED` event is logged.

## Phase 8: If time

### Task 53
- **Title:** Implement Continuity Check Tier 1
- **Governs:** `docs/15_continuity.md` §3
- **Implements:** None
- **Depends on:** 17, 18, 32, 35
- **Acceptance criteria:** A user can invoke a continuity check. The Supervisor agent reads final-cut takes and reports Tier 1 contradictions (e.g., unrostered names in dialogue) by emitting a `CONTINUITY_FINDINGS_DELIVERED` event.
