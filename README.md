# Artie Spiegel

An AI-orchestrated screenwriting studio. The system interrogates, diagnoses, and
visualizes. The writer writes.

**The agent you talk to has never read your screenplay.** That is not a policy,
it is the wiring. Artie's payload has no field for prose, and an assertion
fails loudly if one ever appears.

## What it does

**The Greenlight** fills twelve slots through conversation. Complete it and
Artie moves from skeptical to committed, the title page formats itself, and you
land on scene one.

**The Scene Rig** runs before each scene. Seven slots, reset every time,
clearing on deterministic checks so no model call blocks the writer.

**The workbench** formats screenplay components as you type. Enter after a
character cue puts you in dialogue; Enter on an empty cue falls through to
action.

**The Script Supervisor** scores each scene against a 72-cell matrix of twelve
narrative positions by six craft lenses, anchored in published corpora of film
structure, with a visible confidence gradient.

**The Director** boards a scene from its action lines alone, then reports what
the model filled in where the description ran out.

**The manifest** records how the work was created: composition record, a
hash-chained keystroke history, every agent action with counts, and a payload
audit backing the claim that no agent supplied screenplay text.

## Architecture

Three agents, deliberately flat. Artie is never the parent of the Supervisor or
the Director, because delegation would pass scene prose down the tree and break the
reading boundary.

| Layer | Technology |
|---|---|
| Agents and models | Google Gemini via ADK and google-genai |
| Hosting | Cloud Run |
| Analytical | ClickHouse Cloud: matrix, diagnoses, provenance ledger |
| Event stream | Confluent Cloud |
| Transactional | Supabase / Postgres |
| Assets | Cloud Storage |

## Documentation

Fifteen specifications in [`docs/`](docs/). Start with
[`Plan.md`](Plan.md), then the spec for whatever you are reading about.

## Setup

See `.env.example` for required configuration.

```
./setup.sh
```

Schema in `sql/`, applied in numeric order. Tests: `python -m pytest -q`.

## License

MIT.
