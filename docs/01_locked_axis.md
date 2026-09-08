# Narrative Diagnostic Matrix — Locked Axis Specification v1.0

**Status: CANONICAL.** 

---

## 1. Model

A screenplay is evaluated against a grid of **72 diagnostic cells**. Each cell
is the intersection of a **narrative position** (X axis, 12 values) and a
**craft lens** (Y axis, 6 values).

**Derivation.** The twelve positions resolve as: one baseline state, five
empirically attested turning points (Papalampidi et al., TRIPOD), and six
connective phases spanning the intervals between them. This reconciles against
Cutting's four measured acts of approximately equal length.

**Honest caveat, to be repeated wherever this is described:** the target of
twelve was known before derivation began. The derivation is mathematically
sound and evidence-anchored, but it cannot be certified free of confirmation
bias. State it as *"reconciled to twelve across eight structural models and two
empirical corpora,"* never as *"twelve emerged empirically."*

**Scope boundary.** Linear, single-strand, classical narrative feature
screenplays. Non-linear, ensemble, multi-strand, and episodic structures are
out of scope and require a different topology.

---

## 2. X Axis — Narrative Positions

Ranges are contiguous, non-overlapping, integer, and cover 0–100 exactly.
Position is **declared by the writer** during Scene Rig interrogation. Range is
**advisory only** — a sanity check the system may surface, never a parsing rule.

| ID | Name | Type | Range | Definition | Empirical Anchor | Tier |
|---|---|---|---|---|---|---|
| **X01** | Status Quo | BASELINE | 0–9 | The protagonist's equilibrium, governing world logic, and latent flaw prior to disruption. | Cutting: Setup | 1 |
| **X02** | Disturbance | TURNING_POINT | 10–14 | The event that irreparably fractures the baseline equilibrium. | TRIPOD TP1: Opportunity (~10%) | 1 |
| **X03** | Deliberation | CONNECTIVE | 15–24 | Resistance, denial, or preparation following the disturbance. | Vogler: Refusal; Snyder: Debate | 2 |
| **X04** | First Threshold | TURNING_POINT | 25–29 | Irrevocable commitment to the narrative goal; entry into the complication phase. | TRIPOD TP2: Change of Plans (~25%) | 1 |
| **X05** | Rising Action | CONNECTIVE | 30–45 | Exploration of the new paradigm; accumulation of secondary conflict; initial tactics fail. | Cutting: Complication | 1 |
| **X06** | Midpoint Reversal | TURNING_POINT | 46–50 | Revelation or contextual shift that forces strategic change; reactive posture becomes active. | **TRIPOD TP3: Point of No Return (~50%)** | 1 |
| **X07** | Deterioration | CONNECTIVE | 51–70 | Antagonistic forces optimize; the protagonist's advantages and false assumptions decay. | Cutting: Development | 1 |
| **X08** | Acute Crisis | TURNING_POINT | 71–77 | Catastrophic collapse of the current strategy; profound loss; external supports stripped. | **TRIPOD TP4: Major Setback (~75%)** | 1 |
| **X09** | Realignment | CONNECTIVE | 78–82 | The crisis is processed; a paradigm-shifting strategy is synthesized. | Snyder: Dark Night; Truby: Self-Revelation | 2 |
| **X10** | Final Threshold | CONNECTIVE | 83–87 | The synthesized strategy is committed to and launched. | Vogler: Resurrection; Snyder: Break into Three | 2 |
| **X11** | Climax | TURNING_POINT | 88–95 | The apex of conflict; the dramatic question is definitively resolved through action. | TRIPOD TP5: Climax (~90%) | 1 |
| **X12** | Resolution | CONNECTIVE | 96–100 | A new equilibrium reflecting the consequences of the climax. | Cutting: Epilog | 1 |

**Count reconciliation:** 1 baseline (X01) + 5 turning points (X02, X04, X06,
X08, X11) + 6 connective (X03, X05, X07, X09, X10, X12) = 12.

**Act alignment (Cutting):** Setup ≈ X01–X03 · Complication ≈ X04–X06 ·
Development ≈ X07–X08 · Climax ≈ X09–X12.

---

## 3. Y Axis — Craft Lenses

The six lenses correspond to Aristotle's elements of tragedy — Plot/*mythos*,
Character/*ethos*, Theme/*dianoia*, Dialogue/*lexis*, Spectacle/*opsis* — with
Conflict added for modern dramaturgy. Cite this alignment; it is a genuine
justification rather than a convenient count.

| ID | Name | Definition | Explicitly Excludes | Disambiguating Question |
|---|---|---|---|---|
| **Y1** | Structure | Causal placement of the scene within the narrative sequence, **and** whether the scene itself turns — changes state between entry and exit. | The force applied (Conflict); canon consistency. | *Does this concern the scene's causal necessity, or whether it changes state?* |
| **Y2** | Conflict | The mechanics of opposition: active counter-force, obstacle severity, stakes, and tactical escalation within the scene. | Where the scene sits in the plot (Structure); the protagonist's inner flaw (Character). | *Does this concern the strength of the opposition or what stands to be lost?* |
| **Y3** | Character | Psychological motivation, decision logic, behavioral consistency, and arc progression of individuals. | The universal argument (Theme); the words spoken (Dialogue). | *Does this concern the internal logic driving a specific person's choices?* |
| **Y4** | Theme | The socio-moral or philosophical argument the narrative advances, tests, or proves. | Individual psychology (Character); interpersonal plot mechanics (Structure). | *Does this concern a universal claim rather than one person's psychology?* |
| **Y5** | Dialogue | The craft of verbal action: subtext, voice differentiation, rhythm, and the distribution of verbal exposition. | The information conveyed (Structure); the underlying desire (Character). | *Does this target the words spoken and the manner of their expression?* |
| **Y6** | Visual | Physical action, environment, props, and juxtaposed imagery used to convey story information **as written on the page**. | **Camera angles, lighting, lens, and all cinematographic or directorial specification**; dialogue-driven exposition. | *If the dialogue were muted, would this beat still be comprehensible?* |

**Y6 scope warning.** Y6 evaluates visual storytelling *the screenwriter
controls*. A note such as "the lighting is too bright for a thriller" is a
cinematographer's concern and must not route here. Any Y6 diagnostic that could
only be executed by a director or DP is out of scope and must be rewritten.

**Y1 scope note.** Structure operates at two levels: inter-scene causal
placement, and intra-scene turn. A scene in which nothing changes state is a
Structure failure, not a Conflict failure. Conflict supplies the force;
Structure asks whether the force produced a change.

### Excluded from the matrix

**World/Rules (canon consistency)** is deliberately not a lens. It is a binary
check against the Project Bible, owned by the Script Supervisor agent, running
parallel to the matrix. A prohibited spell in scene 40 is a continuity
violation, not a structural defect, and scoring it as one would pollute
Structure coverage.

**Pacing, Subtext, Stakes, Emotion, Point of View** are excluded as non-
orthogonal: each is an emergent property of, or fully subsumed by, a lens above.

---

## 4. Cell Mode

Two cells were found testing for the *absence* of a lens. They are not isolated they cluster at the terminal positions, where certain lenses legitimately discharge rather than activate. The schema resolves this rather than apologizing per cell.

Every cell carries a **mode**:

| Mode | Semantics | Question form |
|---|---|---|
| **ACTIVATION** | The lens must be present and doing work at this position. | *Does X occur / is X established?* |
| **TRANSFORMATION** | The lens must demonstrably differ in state from an earlier named position. | *Is X at this position demonstrably different from X at position N?* |

**No cell may test for absence.** A terminal cell tests changed state against a
prior baseline, which is a positive, falsifiable condition.

**Pre-assigned TRANSFORMATION cells (7):** all six X12 cells (X12.Y1–Y6),
measured against X01; plus X11.Y3 (Climax/Character), measured against X01.
All remaining 65 cells are ACTIVATION.

---

## 5. Seed Schema

```
positions
  position_id        TEXT  PK        -- 'X01'..'X12'
  name               TEXT
  definition         TEXT
  position_type      ENUM            -- BASELINE | TURNING_POINT | CONNECTIVE
  range_start_pct    UInt8
  range_end_pct      UInt8
  structural_function TEXT
  empirical_anchor   TEXT NULL
  evidence_tier      UInt8           -- 1 | 2
  model_concordance  TEXT

lenses
  lens_id            TEXT  PK        -- 'Y1'..'Y6'
  name               TEXT
  definition         TEXT
  excludes           TEXT
  disambiguating_question TEXT

cells
  cell_id            TEXT  PK        -- 'X06.Y3'
  position_id        TEXT  FK
  lens_id            TEXT  FK
  cell_mode          ENUM            -- ACTIVATION | TRANSFORMATION
  compare_to_position TEXT NULL      -- required when TRANSFORMATION
  diagnostic_question TEXT           -- A2
  satisfaction_criteria TEXT         -- A2
  failure_signature  TEXT            -- A2
  priority_weight    UInt8           -- A2
```

**Coverage normalization — binding on C2.** Ranges are unequal by design.
X07 spans 20 points; X02, X04, X06, X09, and X10 span 5 each. Expected raw
scene-count skew is approximately **4:1**. Coverage must be normalized per
position. Raw counts will produce false "bloat" at X05/X07 and false
"underdevelopment" at every turning point.

---

## 6. Design decisions

1. **Papalampidi turning points.** In TRIPOD, Point of No Return is the ~50%
   turning point and Major Setback is ~75%. X06 is TP3; X08 is TP4 at 71–77%;
   X10 is CONNECTIVE at Tier 2. The 1 baseline + 5 turning points + 6 connective
   derivation holds.
2. **Y6 Visual is scoped to screenwriting.** "What the camera sees" would admit
   cinematography notes, which a screenwriter does not control. The muted-dialogue
   disambiguator governs, with an explicit directorial exclusion.
3. **Y1 Structure covers intra-scene turn** as well as inter-scene causal
   placement. A scene where nothing changes state would otherwise have no home.
4. **Cell mode** resolves the terminal-position absence cluster at schema level.
   No cell tests for absence, and there is no exception clause.
5. **Ranges** are contiguous, non-overlapping, and cover 0–100. Expected scene
   count skew is approximately 4:1.

## 7. Known open items

- **Orthogonality is imperfect.** An adversarial routing test using twenty
  boundary-stressing observations resolved 6 cleanly and left 14 showing lens
  ambiguity. The lenses are usable but not cleanly separable at the margins.
- No empirical baseline exists for expected scene count per position. Flagged
  for C2; do not fabricate thresholds.
- One [UNSUPPORTED] claim regarding Deliberation
  bloat. Retain the flag; do not promote it to a finding.
