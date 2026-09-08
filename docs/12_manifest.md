# D2 Specification v1.0 — Provenance Capture and the Authorship Manifest

**Status: CANONICAL.**

**Companions:** `docs/09_provenance_ledger.md` ·
`docs/11_supabase.md` · `docs/04_agent_roster.md` ·
`docs/07_artie_persona.md`

**Legal basis:** the September 2026 research brief, Area 1. Current as of the
Supreme Court's denial of certiorari in *Thaler v. Perlmutter* (March 2, 2026) and
the Copyright Office's *Copyright and Artificial Intelligence, Part 2:
Copyrightability* (January 29, 2025).

**This is not legal advice, and neither is the manifest.**

---

## 1. The claim, stated precisely

**What the manifest does:** preserves and evidences human authorship, and produces
a disclosure-ready provenance record.

**What it does not do:** guarantee registrability, ensure compliance, or defeat a
determined forger.

Registrability is a case-by-case determination made solely by the Copyright
Office, and post-*Loper Bright* even the Office's own report does not bind a
court. No software can promise an outcome there. **Any product copy claiming
"total compliance with Copyright Office mandates" must be struck** — it overstates
both the guidance and any tool's power over it, and it is exactly the kind of
claim a judge or a lawyer will test first.

---

## 2. The unusual position — and it is a strong one

Most tools in this space need to disclose AI-**generated** content and disclaim it
from the claim.

**This system's screenplay contains none.** Artie has no screenplay text in his
context at all (04_agent_roster.md §1.1). The Supervisor emits verdicts, never prose. The Director
produces images, never words. Every character of the literary work was typed by
the writer.

So the disclosure is not *here is the machine's contribution, please exclude it.*
It is:

> **Artificial intelligence was used in the creation of this work. It supplied no
> expression. The complete record of what it did supply is attached.**

The D.C. Circuit in *Thaler* stated the point directly: the human authorship
requirement "does not prohibit copyrighting work that was made by or with the
assistance of artificial intelligence." A screenplay whose text is entirely human
is a traditional literary work regardless of how much AI assisted around it.

**The manifest's job is to make that verifiable rather than merely asserted.**

---

## 3. Capture architecture

Four emitters. Each writes to Confluent using the 09_provenance_ledger.md §2 envelope.

| Emitter | Runs in | Emits |
|---|---|---|
| **Editor client** | browser | `KEYSTROKE_BATCH` · `PASTE` · `COMPONENT_INSERTED` |
| **Backend** | Cloud Run | `SCENE_SAVED` · `SLOT_ANSWERED` · `BIBLE_VERSION_CREATED` · `COMMITMENT_CHANGED` · state events |
| **Agent wrapper** | Cloud Run | `AGENT_*` events · `AI_DELIBERATION` · `SCENE_DIAGNOSED` · `CANON_FINDING` · `FRAME_*` |
| **Export** | Cloud Run | `MANIFEST_EXPORTED` · `SCRIPT_EXPORTED` |

**The agent wrapper is the important one.** No agent emits its own provenance
event — a wrapper around every `Runner.run_async` call captures the full input and
output and emits it. If agents self-reported, an agent that failed to emit would
leave a silent gap in the evidence, and a gap in an evidentiary record is worse
than a recorded fault.

**Emission is not optional and not conditional.** If Confluent is unreachable,
buffer locally and retry (09_provenance_ledger.md §12). An event never produced cannot be
reconstructed.

---

## 4. The hash chain

Each keystroke batch stores a chained hash:

```
chain_hash₀ = SHA256(component_id)
chain_hashₙ = SHA256(chain_hashₙ₋₁ ‖ SHA256(content_after_batchₙ))
```

Chaining rather than independent hashing is what makes the sequence
**tamper-evident**: altering or inserting any intermediate batch breaks every
subsequent chain hash.

The final `chain_hash` for a component, recomputed against
`script_components.content_hash` in Supabase, must match. That closes the loop
from empty document to delivered script.

### What the chain honestly proves

**It evidences ordinary authorship. It does not defeat a determined forger.**

A person controlling the client could fabricate batches with valid chain hashes.
That limitation is inherent to any client-side capture and is worth stating
plainly, because the alternative — implying tamper-proofing — is the overclaim
this whole document exists to avoid.

The correct framing: the Copyright Office is not conducting an adversarial audit.
It is asking for a good-faith account of how a work was made. **The chain is a
detailed, internally consistent, contemporaneous account** — which is materially
better than an applicant's recollection, and that is the standard it should be
measured against.

---

## 5. Verification

Runs at export, not continuously.

| Check | Result |
|---|---|
| **Chain continuity** | For each component, recompute the chain and compare to the stored terminus |
| **Terminus match** | Final `chain_hash` equals the current `content_hash` in Supabase |
| **Paste reconciliation** | Every jump in `char_delta` larger than the batch threshold has a corresponding `PASTE` event |
| **Attribution completeness** | Every event carries a valid `actor`; no nulls, no defaults |
| **Agent payload audit** | No `AGENT_*` payload contains screenplay text (§7) |

**Discontinuities are reported, never hidden and never blocking.** A break is a
fact about the record. Suppressing it would make the whole document worthless;
blocking export over it would punish a writer for a bug.

---

## 6. Manifest structure

Seven sections.

### §1 — Summary
Title, writer of record, date range, session count. The core statement of §2.

### §2 — Composition record
Total characters typed · keystroke batches · sessions · elapsed working time ·
components by type · scenes.

### §3 — Chain verification
Per-component chain result. Verified, or discontinuities enumerated with
timestamps.

### §4 — Insertion log
Every `PASTE` with timestamp, `origin` (`INTERNAL` or `UNKNOWN`), character count,
and target component.

**`UNKNOWN` is not an accusation.** 09_provenance_ledger.md §6 explains why there is no `EXTERNAL`
label: the system cannot prove content came from outside, only fail to prove it
came from inside. The manifest states exactly that, in those terms.

### §5 — Artificial intelligence involvement
The disclosure section, and the one an examiner would read.

- Which models, by name and version
- What each agent did, by category, with counts: questions asked, findings
  delivered, curated examples shown, stories told, deliberations run
- The static library versions in force (`AGENT_EXAMPLE_SHOWN`,
  `AGENT_STORY_TOLD` carry `library_version` — 09_provenance_ledger.md §3.2)
- **The explicit statement that no agent supplied screenplay text**, with the
  audit result from §5 supporting it

**This section is why the ledger stores agent payloads in full.** A summary would
assert the claim; the payloads let someone check it.

### §6 — Machine-generated assets
Storyboard frames, listed and marked. Model, prompt, timestamp, and the note that
each carries a **SynthID** invisible watermark applied by Google independently of
this system.

**Explicit statement: these are pre-visualization reference, not part of the
literary work, and excluded from any claim in the screenplay.**

### §7 — Intent development
Bible version history. What changed, when, and the writer's stated reason where
given.

This section evidences Claim 3 from 09_provenance_ledger.md §1: **a machine does not change its mind at
scene 40 and revise backward.** Evolving intent over time is a signature of human
authorship, and it is the section most likely to be persuasive to someone
skeptical of the rest.

---

## 7. The agent payload audit

§5 lists it; it deserves its own treatment because it is the manifest's central
evidentiary claim.

**Every `AGENT_*` payload is scanned at export for screenplay content.** The
result appears in §5 of the manifest.

By construction this should always pass. Artie has no prose in context (04_agent_roster.md §1.1),
the Supervisor's `evidence` field is stripped at the backend boundary (05_orchestration.md §5.3),
and the deliberation poles are constrained to argue about response strategy only
(06_artie_mind.md §8).

**Run it anyway, and publish the result.** A claim that is checked and reported is
worth more than a claim that is architecturally guaranteed and unverified — and if
it ever fails, that is precisely the regression you need to know about.

---

## 8. Disclosure mapping

The practical payoff. The manifest generates suggested language for the Copyright
Office **Standard Application**, per the March 2023 registration guidance (88 Fed.
Reg. 16,190).

| Field | Suggested content |
|---|---|
| **Author Created** | *"Entire text of screenplay, including all dialogue, action, and scene description."* |
| **Material Excluded / Limitation of Claim** | For the screenplay alone: **nothing to exclude** — no AI-generated expression is present. If storyboard frames are included in the deposit, exclude them as machine-generated visual material. |

**Two things the manifest must say alongside this.**

The guidance imposes a **duty to disclose** AI-generated content, and failure can
support cancellation or a third-party validity challenge. A tool that helps a
writer disclose accurately is doing them a service; one that helps them under-
disclose is doing them harm.

And the Office's own suggested cleanest path is to **register only the
human-generated component**. For this system that is the entire screenplay, which
is a comfortable position — but it must be presented as suggested language for the
applicant's own review, never as a completed filing.

---

## 9. C2PA — referenced, not implemented

The C2PA Content Credentials specification (2.4) is the closest existing standard
for a provenance record, and it permits custom assertions. The manifest follows
its conceptual model: **assertions gathered into a claim**.

**Do not implement C2PA for the screenplay.** It is built for media assets, uses
JUMBF embedding and cryptographic signing, and is awkward for a text document.
Standing up signing infrastructure is not realistic in the remaining build window,
and a half-implemented signing scheme is worse than none.

**The natural path, noted for the roadmap:** the storyboard frames are images, and
C2PA is built for exactly that. They already carry SynthID. Adding Content
Credentials to generated frames is the obvious next step and should be named as
such in the writeup rather than implemented now.

One distinction the manifest must preserve: **C2PA proves provenance and history.
It does not establish legal authorship.** Conflating the two would be another
overclaim.

---

## 10. Format and export

**Two artifacts, one export action.**

**JSON** — machine-readable, complete, the full verification result. For anyone
who wants to check rather than read.

**PDF** — human-readable, structured for an examiner or an attorney. Generated
alongside the screenplay PDF so a writer gets script and manifest together.

Export emits `MANIFEST_EXPORTED` with a content hash, so the manifest itself
enters the record it describes.

---

## 11. Language constraints — binding on all copy

| Never | Instead |
|---|---|
| "ensures compliance" | "produces a disclosure-ready record" |
| "guarantees copyright" | "evidences human authorship" |
| "Copyright Office approved" | *(no equivalent — do not imply endorsement)* |
| "tamper-proof" | "tamper-evident" |
| "proves you wrote it" | "documents how it was written" |
| "legally verified" | *(strike entirely)* |

Every manifest carries this, verbatim:

> This document records how this work was created. It is not legal advice.
> Registrability is determined solely by the U.S. Copyright Office on a
> case-by-case basis. Consult an attorney regarding registration.

**Under a judging criterion that scores whether the case is credible, an
unbackable legal guarantee costs more than it gains.** The precise claim is also
the stronger one.

---

## 12. Open items

1. **The chain verifier is unimplemented.** 09_provenance_ledger.md §13.3 flagged it; it belongs here.
   Runs at export, walks every component, reports rather than blocks.
2. **Elapsed working time is not defined.** Sum of batch durations, or wall time
   between first and last event in a session? They differ by an order of
   magnitude and the manifest should say which it means.
3. **The screenplay content hash must be canonical.** Hash the Fountain source,
   not the rendered PDF — PDF generation is not byte-stable across runs and the
   terminus check would fail spuriously.
4. **Multi-writer collaboration is out of scope**, and the manifest's single
   `writer of record` assumes it. Note the limitation; do not solve it.
5. **The agent payload audit's detection method is unspecified.** Scanning for
   "screenplay text" needs a definition — probably a heuristic on Fountain
   markers and long prose spans in fields that should hold identifiers. Imperfect
   detection reported honestly beats perfect detection claimed.
6. **WGA MBA successor status unverified.** The 2023 agreement ran to May 1, 2026.
   If a successor is in force, its AI provisions should be checked before any
   product copy references guild rules.
