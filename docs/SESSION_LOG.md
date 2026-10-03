# goTag Session Log (auto-generated)

> This is an auto-generated historical record of what was prompted and done in
> this working session, including background-agent usage stats. It is **not**
> a design document — for the actual living design/decisions, see
> `docs/V1.md`, `docs/JEV_INTEGRATION.md`, `docs/SGP4_GUIDE.md`, and
> `docs/ARCHITECTURE.md`. This file exists purely so the sequence of prompts
> and the cost/time of each background agent dispatch is preserved.

The session began with brief, unrelated context (an AWS AgentCore workshop /
"ferry tracker" project) before the user pivoted to starting this entirely
new, unrelated project, goTag. That earlier context is omitted below.

---

## 1. "Create a separate work environment... utilize agents and AWS resources"

- Initial ask was ambiguous (still framed around the prior ferry-tracker
  project's temp-environment problem). Clarifying questions were asked and
  rejected by the user pending more context.

## 2. "I am creating a new project entirely; goTag... tagging satellites when two are nearby"

- User reframed entirely: new standalone project, satellite cross-tagging
  identification, nothing to do with the prior workshop.
- Clarified via AskUserQuestion: location `~/goTag`, approach =
  observation-based identification (not orbital-propagation/TLE
  correlation), AWS research = AWS documentation MCP tools.
- Actions taken:
  - Created `~/goTag` git repo with `src/goTag/{ingestion,identification,models,api}`, `tests/`, `docs/`, `data/{raw,processed}`.
  - Wrote `README.md`, `.gitignore`, package `__init__.py` files.
  - Saved memory `project_gotag.md` and updated `MEMORY.md` index.
  - Dispatched background agent to research AWS services for the pipeline.
    - **"Research AWS services for satellite observation data pipeline"** — 70,811 tokens, 5 tool uses, 29.4s.
- Wrote `docs/ARCHITECTURE.md` from that agent's findings (Kinesis → Timestream/Lambda/SageMaker → DynamoDB; ruled out Ground Station and Rekognition).

## 3. "You are moving too fast... research the problem first" (open data vs. simulation)

- User pushed back on jumping to solutioning before the problem was understood. Asked for research on two paths: (1) open data sources with real cross-tagging events (e.g. Starlink), (2) simulating ISS + a nearby object and its radio signature.
- Dispatched two parallel background research agents:
  - **"Research simulating a satellite pair and RF signature"** — 58,258 tokens, 0 tool uses, 28.7s.
  - **"Research open data sources for satellite conjunction/tagging events"** — 61,874 tokens, 8 tool uses, 50.9s.
- Findings relayed to user as each landed: simulation findings first (orbit tools, realistic separation/velocity, Doppler/power are physics-derived and legitimate, transmission content is not), then open-data findings (CDMs gated/prediction-only, CelesTrak/SOCRATES prediction-only, no source anywhere packages a real identification/disambiguation dataset).

## 4. "Dig deeper into SatNOGS... write a high-level guide of sgp4"

- User had independently checked `db.satnogs.org` and found it metadata-only; asked for a deeper check, plus an SGP4 primer since they're new to orbital mechanics.
- Dispatched background agent:
  - **"Deep-dive SatNOGS observation data contents"** — 71,271 tokens, 6 tool uses, 138.9s.
  - Finding: `db.satnogs.org` (metadata only, user's read was correct) vs `network.satnogs.org` (real downloadable audio/waterfall/decoded-frame artifacts, open API, no auth) are different products; Network can't natively capture two-object overlap (single-target scheduling).
- Wrote `docs/SGP4_GUIDE.md` directly (TLE fields, what SGP4 outputs, why accuracy degrades with time-since-epoch, why that supports the observation-based approach already chosen).

## 5. "Recap sites visited, packages/frameworks evaluated, pathways forward under a V1 section"

- Wrote `docs/V1.md`: table of every data source evaluated with verdicts, table of packages evaluated (sgp4/skyfield primary, poliastro for the one-time delta-v step, GMAT/STK/Rekognition/Ground Station ruled out), key assumptions, and a 6-step V1 build order (orbit layer → realistic companion via delta-v → angular/optical as first observable → RF Doppler/power only as second observable → SatNOGS as a realism anchor, not a dataset → AWS infra explicitly deferred).

## 6. "What are our next steps?"

- Text-only answer: recommended starting with the orbit propagation layer (real ISS TLE + skyfield), then the delta-v companion, then the angular-separation observable, before touching RF. No files/agents.

## 7. "Before we proceed, what tech stack do you recommend?"

- Text-only recommendation: Python 3.11+ via `uv`, skyfield/sgp4, poliastro, numpy/pandas, matplotlib, pytest. Explicitly deferred any AWS/service-shaped infra until a working simulation exists.

## 8. "Python is good. Use Flask for a dashboard. Instruct an agent to build it. Proceed with simulation dev, heavily commented. Check in frequently."

- Wrote `requirements.txt`; `uv venv` + install hit a build failure (poliastro/astropy incompatible with modern setuptools on this Python/arch) — poliastro dropped, replaced with a self-written two-body RK4 integrator.
- Wrote `src/goTag/simulation/orbit.py` (real ISS TLE fetch from CelesTrak + SGP4 propagation via skyfield), `companion.py` (delta-v + two-body RK4 propagation), `scenario.py` (`ScenarioParams`/`ScenarioResult`/`run_scenario` tying it together: range, angular separation from a ground site, Doppler for each object).
- Hit and fixed two bugs during manual verification: wrong venv receiving `uv pip install` (fixed with `--python .venv/bin/python`), and `skyfield`'s `load` object having no `urlopen` (switched to `urllib.request`).
- Verified end-to-end against a real live ISS TLE (sanity-checked range/angle/Doppler magnitudes).
- Checked in with the user on the `ScenarioParams`/`ScenarioResult` contract before dispatching the Flask-building agent (per "check in frequently").

## 9. "Pause dev — have an agent figure out how to use jev from Typesafe for cross-tagging + radio signature evaluation; write a markdown of its primitives/states"

- "jev"/"Typesafe" was unfamiliar; clarified via AskUserQuestion rather than guessing (public product w/ unusual name; a state-machine/statistical-inference framework was the user's working description).
- Dispatched background agent:
  - **"Research jev product from Typesafe"** — 31,360 tokens, 8 tool uses, 70.3s.
  - Finding: name collision — the Scala/Akka "Typesafe" has no such product; a *different*, newer company also calling itself "TypeSafe AI" (typesafe.ai) makes "Jev," with primitives Choice/Score/and a third one the agent rendered as "Noul" (flagged as possibly a parsing artifact).
- Relayed findings and asked the user to confirm the match and the "Noul" naming before writing anything down.
- User confirmed jev was correct and pointed to `docs.typesafe.ai/primitives`. Fetched that page directly (WebFetch) and confirmed Choice/Score/**Noul** (real name, not an artifact) and that jev is stateless per-call (no built-in state machine — corrected the user's/earlier framing).
- Wrote `docs/JEV_INTEGRATION.md` (pipeline placement, 3 proposed primitive uses, key assumptions/open questions).

## 10. "Resume paused simulation dev and flask agent"

- Wrote `tests/conftest.py` and `tests/test_scenario.py` (3 sanity tests: objects start coincident and separate, result arrays consistent/finite, angular separation within physically sane bounds) — all passing.
- Dispatched background agent:
  - **"Build Flask exploratory dashboard for goTag simulation"** — 47,612 tokens, 19 tool uses, 153.5s.
  - Built `src/goTag/dashboard/` (`app.py`, `templates/index.html`, `README.md`) exposing every `ScenarioParams` field as a form, rendering `ScenarioResult` plots as base64 PNGs plus a headline-numbers table.

## 11. "Have an agent review jev docs, specifically how-to-build-with-system-one, for coding patterns"

- Dispatched background agent (while the Flask dashboard agent above was still outstanding):
  - **"Review jev System One build-guide docs"** — 47,264 tokens, 7 tool uses, 177.2s.
  - Finding/correction: "System One" is a product name contrasted with *agents* (code must own control flow, model never picks next action) — not a Kahneman fast/slow framing as earlier assumed. Core rule: decompose broad questions into atomic ones. Composition pattern: many parallel atomic questions in one request against shared state, combined via deterministic formulas in code; branch on confidence rather than chaining calls.
- Flask dashboard agent's hand-back also landed around this point: independently re-verified its claimed success, found a real bug (`ModuleNotFoundError: No module named 'goTag'` when run exactly per its documented command — its own self-verification had not caught this), fixed with a `sys.path` insert matching the existing `tests/conftest.py` pattern, re-verified (HTTP 200, all 9 form fields present).
- Rewrote `docs/JEV_INTEGRATION.md` substantially using the System One findings: corrected the "System One" framing, rewrote all three example use-cases as properly decomposed atomic questions, added the composition/confidence-gating pattern, and tightened the limitations section to the docs' actual stated anti-patterns.

## 12. "Let's live run the dashboard"

- Started the Flask server in the background; did a live `GET /` and a real `POST /` (triggering an actual live ISS TLE fetch + propagation) via curl to confirm the full path works end-to-end — confirmed HTTP 200, 3 rendered plots, headline table, no errors (the only "error" string match was an unused CSS class, not a real error).

## 13. "How do I open it?"

- Looked up `$WORKSHOP_URL` and gave the direct clickable link (`https://de07jgxp9hhbo.cloudfront.net/app/5050/`) per this environment's CloudFront port-proxy convention.

## 14. "Make the two orbits more obvious — but first, show TRUE ISS orbit info and its REAL radio signature, researched by an agent; ground the sim in ONE ground station"

- Dispatched background agent:
  - **"Research real ISS orbit data and radio signature from one ground station"** — 40,851 tokens, 15 tool uses, 132.9s.
  - Findings: ISS's real documented amateur-radio downlinks (145.800 MHz voice, 145.825 MHz APRS, 437.550/437.800 MHz SSTV/voice repeater) sourced from SatNOGS DB's transmitter catalog (ariss.org/amsat.org were unreachable); a specific real SatNOGS Network observation (ID 15106541, station "MAUSyagi", 437.550 MHz SSTV) with its ground station location, exact timestamps, and the TLE SatNOGS used — but payload/waterfall artifacts were null (only a decoded SSTV image existed), and the agent flagged a credible concern that the observation data might be from a live/synthetic SatNOGS test environment rather than genuine historical data (inconsistent "good" vs "future" statuses for same-day timestamps).
- Findings relayed to the user along with the authenticity caveat and a choice of which transmitter mode to ground the simulation in (SSTV vs. APRS/voice) — awaiting user direction on this at time of this log's writing.

## 15. "List sources for ISS radar information, and links to where SatNOGS has actually recorded it, in a distilled markdown"

- Dispatched background agent:
  - **"Find and verify ISS radar/tracking sources and SatNOGS recordings"** — 43,620 tok / 27 tool uses / 366.7s. Completed: distilled into `docs/ISS_SOURCES.md`.
- Scope given: verified (actually-fetched, not recalled) links for real-time tracking (N2YO/Heavens-Above/NASA Spot the Station), real radar imaging sources if any exist publicly (e.g. Fraunhofer FHR TIRA), direct CelesTrak/Space-Track ISS pages, the SatNOGS Network web UI observation list for the ISS, 2-3 real observations with actual non-null audio/waterfall artifacts, and the SatNOGS DB satellite page.

## 16. "Have a sub-agent refine the Flask app to show simulated vs. real orbits — research 3D vs. 2D feasibility — create 3 panes: variable setup, real+simulated view, radio-signal evaluation (not yet set up)"

- Dispatched background agent:
  - **"Refine Flask dashboard into 3-pane layout with orbit visualization"** — 53,445 tok / 19 tool uses / 178.2s. Completed: 3-pane layout built, independently re-verified by the main session (GET 200 w/ all pane headers, live-run POST 200 w/ 5 rendered plots, simulation tests still passing).
- Scope given: research/decide 2D vs 3D within the existing no-JS-framework matplotlib-PNG stack, prioritizing a relative-position (companion-minus-primary) plot since absolute-frame separation would be visually imperceptible on a ~400km-radius orbit; restructure the dashboard into three labeled panes (variable setup / real+simulated orbit view / radio-signal evaluation placeholder referencing `docs/JEV_INTEGRATION.md` and `docs/V1.md`); verify via a live server run before reporting back.

## 17. "Have an agent write a markdown of this console log..." (this document)

- This file. Produced by a forked agent per that directive.
