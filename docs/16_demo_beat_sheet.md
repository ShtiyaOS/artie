# Demo Beat Sheet v1.0 — The Governing Document

**Status: CANONICAL. This document decides what gets built.**

Judges watch three minutes and may never open the hosted URL. **Any hour spent on
something that does not appear on screen is an hour spent on nothing.**

When something runs long on the 6th, this table decides what dies.

---

## 1. The premise

**Do not show onboarding.** Open mid-project, with Artie already committed and a
working relationship established.

Showing a writer *at work* is faster, more credible, and skips the entire
blueprint sequence. A judge who sees someone using the tool well learns more than
one who watches an account get created.

---

## 2. The beats

| Time | Beat | Proves |
|---|---|---|
| **0:00–0:20** | **Cold open.** Artie's session slug line renders — `INT. ARTIE'S OFFICE — 11:38 PM`. He speaks, in character, about the scene waiting. | **Design.** Establishes the character and the fact that *everything is scripted*, in twenty seconds. |
| **0:20–0:50** | **Scene Rig.** Seven slots fill through conversation, accept-first. **One re-ask where Artie refuses to supply the answer** and narrows instead. Writer types in the workbench; components format to Fountain live. | **Quality of the Idea.** The thesis made visible: the agent interrogates, the human writes. |
| **0:50–1:20** | **Save fires the Supervisor automatically.** The deliberation trace opens — two poles weighing with strengths, synthesis deciding. Artie delivers **one** finding. | **Technological Implementation.** Multi-agent orchestration *proven*, not claimed. |
| **1:20–1:40** | **Coverage heatmap updates** from a live ClickHouse query. The structural sentence appears: *"Act Two touches Theme in two of five positions."* | **Technological Implementation.** Analytical layer doing real work. |
| **1:40–2:05** | **Board This Scene.** Frame generates. **The assumption note:** *here is what the model filled in where your description ran out.* | **Quality of the Idea.** Non-obvious use of image generation. |
| **2:05–2:35** | **Export.** Screenplay PDF *and* authorship manifest. Cut to the manifest's AI section: **"No agent supplied screenplay text."** | **Potential Impact.** A real problem, a real artifact. |
| **2:35–3:00** | **Close.** Architecture card. Narration lands the points no beat had room for. | All four. |

---

## 3. The single most important shot

**0:50–1:20, the deliberation trace.**

Fifty submissions will show a chat interface. One will show an agent visibly
weighing *press harder (4)* against *back off (2)* before it speaks.

That is the difference between a judge seeing a wrapper and a judge seeing a
system. If any beat gets extra seconds, it is this one.

**Second most important: 2:05–2:35.** The manifest is the only thing on screen
that addresses a problem a working screenwriter has today.

---

## 4. The line that has to be said

In the 0:50 beat or the close, verbatim or close to it:

> **The agent you're talking to has never read your screenplay.**

That is the whole architecture in nine words. It is structurally true — Artie's
payload has no prose field and an assertion fails loudly if one appears — and it
is checkable in the repo.

---

## 5. Close narration

Three things no beat had room for, said over the architecture card in 25 seconds:

1. **Narrowed re-diagnosis.** *"Revise your theme at scene 40 and the system
   re-runs twelve cells on the six scenes that actually consume it — not all
   forty."*
2. **The two-engine split.** *"Postgres for state, ClickHouse for the authorship
   ledger and the coverage matrix, Confluent between them."*
3. **What it refuses.** *"It will not write your scene. That's the point."*

---

## 6. Cut list — everything below is out of the video

| Cut | Why |
|---|---|
| Greenlight / blueprint sequence | Costs 40s of setup. Open mid-project instead. |
| Skeptical → Committed moment | The emotional peak, and it needs the blueprint to land. |
| Narrowed re-diagnosis as a sequence | 30s to set up for an engineer-only payoff. **Narrated in the close.** |
| Canon check | Needs world rules established first. |
| Character portraits | Infrastructure, not spectacle. |
| Bible versioning | Invisible without a revision sequence. |
| Genre modulation | Requires two projects to contrast. |
| Ideation chat | Not on the critical path. |
| Shabbat easter egg | Delightful, unshowable in three minutes. |

**These still get built** where they serve the product. They do not get *polished*
for the camera.

---

## 7. Production notes

**Cold start.** Cloud Run scales to zero. **Warm every service with a real request
five minutes before recording.** A twelve-second first response would eat the cold
open.

**Image latency.** Nano Banana Pro with thinking takes several seconds. **Show the
loading state honestly** — it is a real product doing real work, and the beat has
room. Do not fake it with a pre-generated reveal.

**The demo screenplay must be original.** Section 7B requires the submission be
original and unpublished, containing no third-party-owned material. Write the
scene yourself.

**Every name Artie speaks is invented.** Section 7B bars content violating
publicity rights, and the video license to Google and its partners is perpetual
and irrevocable.

**No third-party logos or branding** beyond incidental console UI. Section 7B bars
displayed third-party marks.

**Record at a real pace.** Do not speed up footage of the agent thinking. A judge
who sees an honest three-second wait trusts the rest more than one who sees
suspiciously instant responses.

---

## 8. Video compliance checklist

- [ ] ≤ 3:00. Only the first three minutes are evaluated.
- [ ] English, or English subtitles
- [ ] Public on YouTube or Vimeo
- [ ] Shows the project **functioning** — not a cinematic trailer. The overview
      page says this twice.
- [ ] Original and unpublished; no third-party content
- [ ] No real named individuals
- [ ] No third-party marks, logos, or slogans
- [ ] Nothing derogatory, offensive, or otherwise barred under 7B
- [ ] Link on the Devpost submission form

---

## 9. Schedule

| Date | |
|---|---|
| **Sep 6** | Build complete. Feature freeze. |
| **Sep 7** | Record. Multiple takes of the cold open and the deliberation beat. |
| **Sep 8** | Cut, caption, upload, publish. Devpost writeup. |
| **Sep 9 AM** | Submit with hours to spare before 2:00pm PDT. |

**Do not put recording on the 8th.** The video is the thing being judged, and a
good three minutes with a coherent cold open is a half day minimum including
retakes.

---

## 10. The rule

**Any feature that does not earn a shot in §2 is cut without further debate.**

That is what this document is for.
