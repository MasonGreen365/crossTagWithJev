# Using jev (TypeSafe AI) in goTag

## What jev actually is (verified against docs.typesafe.ai/primitives)

jev is a decision-primitive API: you hand it a **state** (a JSON object — the
content being evaluated, e.g. a record with multiple fields) and ask it
one or more **typed questions** against that state. Each question is one
of three primitives:

| Primitive | Answers | Returns |
|---|---|---|
| **Choice** | "Which of these options?" | `choice`, `probabilities`, `confidence` — pick one from a fixed, unordered list |
| **Score** | "Which level?" | `score`, `legend`, `probabilities`, `confidence` — rate along an ordered rubric |
| **Noul** | "Is this true?" | `noul` — probability (0-1) that a yes/no statement holds |

**Important correction vs. an earlier assumption**: jev is **not** a
state-machine framework. There is no built-in notion of an object's
identity persisting and transitioning across observations. Per the docs:
"Questions in the same request are independent: one answer does not
become context for another question. If a later judgment depends on an
earlier answer, make a second request in code." Any sequencing —
e.g. "track candidate identity across this whole close-approach
event" — has to be logic *we* write; jev evaluates one state snapshot
at a time, stateless per call.

This matters for goTag: jev is a **decision layer**, not a signal-processing
or tracking layer. It doesn't replace the orbit propagation, feature
extraction, or any state-tracking logic in `src/goTag/simulation` or
`src/goTag/identification` — it sits on top of features *we* compute,
and answers specific typed questions about them.

## "System One" design philosophy (verified against docs.typesafe.ai/concepts/how-to-build-with-system-one)

**Correction vs. an earlier guess**: "System One" is a *product name* for
this model line, explicitly contrasted with **agents** — it is NOT the
Kahneman fast/slow-thinking framing I initially assumed. Quoting the docs
directly: "System One is TypeSafe's model for building AI-powered
software, not agents. It does not generate code or choose its own next
action. It provides AI primitives that embed into software, so code
remains in control while the model handles common-sense judgments over
unstructured data."

The docs frame three architectures and are explicit about which one goTag
should be: **not** a traditional hand-coded decision tree, **not** an
agent loop ("every loop introduces another opportunity to go off the
rails"), but **AI-powered software**: "Code handles deterministic work
and owns the control flow. The model appears only where the system needs
programmable common sense... Each AI task is kept atomic and
constrained."

**Concrete implication for goTag's architecture**: our own code (the
simulation + feature extraction + a deterministic orchestration loop)
must always own control flow. jev is called for narrow, specific
judgments only — never to decide "what should we check next" or to drive
the pipeline itself.

## How to actually write the calls (stated best practices)

**The single most important rule in the docs**: decompose. "Broad
questions hide several judgments behind one answer. Atomic questions
expose those judgments so you can inspect, tune, and combine them in
code." The docs' own worked anti-pattern/pattern pair: a single broad
`is_spam` Noul (bad) vs. six decomposed, independently-answerable Nouls
like `requests_credentials`, `sender_identity_mismatch`,
`creates_time_pressure` (good) — each referencing a specific nested
state path.

This directly changes the examples below from the first draft of this
doc — the original "is this a genuine cross-tagging event" Noul and
"which object does this belong to" Choice were too broad by the docs'
own standard, and have been rewritten decomposed.

**Noul**: `instructions` is an object with a `question`, plus optional
`compare`/`inspect` (naming which backticked state paths to look at) and
`focus` (narrowing scope). `criteria` is `NoulCriteria(true={...},
false={...})` — each side gets `what` (what it covers), optional
`not_for` (what it explicitly excludes), and `examples`. This contrastive
true/false structure is deliberate — it's what lets the model distinguish
genuinely ambiguous cases from superficially similar ones.

**Choice**: `criteria` is a dict of options, each with `what`, `not_for`,
`examples` — "Use the same field names across options so the model can
compare them directly."

**Score**: `criteria` is a list of ordered level objects, each with `what`
and `signals` (concrete observable indicators of that level).

**Reference state by name, not by splicing values into text** — use
backtick-delimited paths, e.g. `` `observation.doppler_curve_summary` ``,
and "include the backtick characters around each path inside the
question" so references stay unambiguous.

## Where jev fits in the goTag pipeline

```
physics simulation (or real sensor data)
        -> feature extraction (our code: range, angular separation,
           Doppler trend, signal power trend, etc. -- the numeric stuff
           jev does not do)
        -> build a "state" JSON per decision point (our code)
        -> jev primitive call(s) (Choice / Score / Noul)
        -> typed decision + calibrated probability (consumed by our code)
```

jev only ever sees the summarized feature state we hand it, never raw
time-series arrays directly — its primitives are built for discrete typed
questions against a record-shaped state, not for crunching a Doppler
curve itself. That crunching (everything currently in
`src/goTag/simulation/scenario.py`) stays ours; jev consumes its output.

## Proposed uses, mapped to goTag's actual problem (decomposed per the docs' core rule)

### 1. Detecting a cross-tagging event (several atomic Nouls, not one broad one)

Rather than one broad "is this ambiguous" Noul, decompose into the
distinct judgments that actually make a close pass hard to disambiguate
— each independently answerable, each referencing a specific state path:

- `separation_below_sensor_resolution` — compares
  `` `observation.angular_separation_deg` `` against the sensor's known
  angular resolution limit (itself part of state, not hardcoded in the
  question).
- `range_closing_not_opening` — looks at `` `observation.range_trend` ``
  to judge whether the objects are still converging (harder to tag) vs.
  already diverging (easier).
- `signatures_overlap_in_frequency` — compares
  `` `observation.doppler_shift_primary_hz` `` and
  `` `observation.doppler_shift_companion_hz` `` for the two objects.

Each gets its own `NoulCriteria(true={what, examples}, false={what,
not_for, examples})`. Combine the three afterward in **our own code**
(per the docs' recommended pattern, see below) rather than asking jev to
judge "ambiguous" as one lump sum — e.g.
`cross_tagging_risk = 0.4*separation_below_sensor_resolution + 0.3*range_closing_not_opening + 0.3*signatures_overlap_in_frequency`.

### 2. Attributing a signature to an object (Choice, with contrastive criteria)

```python
Choice(
    instructions="Which known object does the observed signature in "
                 "`observation.doppler_curve_summary` most likely belong to?",
    criteria={
        "primary": {
            "what": "Doppler/power profile matching the primary object's "
                     "known orbit and expected signature.",
            "not_for": "Signatures matching the companion's post-separation trajectory.",
            "examples": ["..."],
        },
        "companion": {
            "what": "Doppler/power profile matching the companion object's "
                     "known (simulated) orbit after the delta-v separation event.",
            "not_for": "Signatures matching the primary's unperturbed trajectory.",
            "examples": ["..."],
        },
    },
)
```

Using the same field names (`what`/`not_for`/`examples`) across both
options is the docs' explicit guidance for making them comparable. This
is the actual tagging decision — Choice returns which candidate it
picked plus a per-candidate probability distribution.

### 3. Rating ambiguity / signature quality (Score, ordered rubric with signals)

```python
Score(
    instructions="How separable are the two objects' signatures in "
                 "`observation.doppler_curve_summary`?",
    criteria=[
        {"what": "Clearly separable", "signals": ["distinct Doppler curves", "no frequency overlap"]},
        {"what": "Partially overlapping", "signals": ["curves cross at least once", "brief frequency overlap"]},
        {"what": "Fully blended, low confidence", "signals": ["curves nearly coincide", "sustained overlap"]},
    ],
)
```

Useful for logging/evaluation rather than the tagging decision itself —
building a dataset of *how hard* each simulated or real scenario actually
was, which is exactly the kind of ground-truth-difficulty labeling this
project doesn't have anywhere else yet (per the earlier open-data
research — no one publishes this).

## Composing these calls (per docs.typesafe.ai/concepts/how-to-build-with-system-one)

The recommended pattern is **not** sequential chaining. Calls are
stateless/independent, but the docs are explicit that this is a feature,
not a limitation to work around: "Ask many narrow, independent questions
about the same state in one request... Decomposition does not require
more round trips. Questions over the same state run in parallel."

So the right shape for goTag's per-observation evaluation is: **one
request, many atomic questions, against one state object** (e.g. all
three Nouls from use-case 1 above, asked together against the same
observation snapshot) — then combine the answers with a deterministic
formula in our own code, same as the docs' own worked examples
(`spam_risk = 0.45*requests_credentials + 0.30*sender_identity_mismatch + 0.25*unexpected_reward`).

**Confidence gating, not chaining, for anything genuinely sequential.**
Rather than letting one jev answer trigger another jev call, the
pattern is to branch in *our* code on confidence: "Make code take
different actions for confident and unconfident answers. Escalate
uncertain cases to a person or a more expensive reasoning model" — e.g.
`if cross_tagging_risk between 0.4 and 0.6: flag_for_manual_review()`.
This maps well onto goTag: a clearly-confident Choice attribution gets
auto-logged; a borderline one gets flagged rather than silently trusted.

## Explicit limitations and anti-patterns (stated directly in the docs)

- **Never let jev own control flow.** It must not choose what to check
  next or drive the pipeline — our deterministic code always decides
  what to ask and what to do with the answer. This is the core
  distinction the docs draw between "AI-powered software" (what we
  should build) and "agents" (what we should not).
- **Never ask broad/compound questions.** This is called out as
  *the* primary anti-pattern — decompose into atomic, independently
  checkable judgments every time (see the rewritten examples above).
- **Don't rely on the model's own background knowledge for facts that
  should come from our own data.** Everything about the specific
  objects/orbits/signatures in play belongs in `state`, not assumed from
  model weights — directly relevant since jev has no inherent knowledge
  of orbital mechanics or any particular satellite's real signature.
- **Text-only input.** No images/audio/video — so any waterfall/spectrogram
  imagery (e.g. from SatNOGS) would need to be reduced to text/numeric
  features before it can be part of a jev `state`; it can't be handed an
  image directly.
- **Always confidence-gate borderline answers** rather than auto-acting
  on them — route uncertain cases (the docs' example band is roughly
  0.4-0.6) to manual review or a stronger model.
- **No stated hard size limit on `state`**, but the docs still warn
  against bloated/unfocused state ("avoid context rot") — include only
  what's relevant to the current batch of questions, trimmed per request.

## Remaining open questions (not addressed by the docs reviewed so far)

- **Verification against ground truth is still on us.** jev's
  `confidence`/`probabilities` are the model's calibrated belief, not a
  verified correctness signal. Since our simulation always knows which
  object is actually which, we should compare jev's Choice output
  against that known ground truth before trusting it on real/ambiguous
  data — the docs don't cover this evaluation step, it's our own
  responsibility.
- **Access/cost**: not yet checked — API key/auth model, rate limits,
  and cost per call for TypeSafe AI are unverified. Should confirm
  before planning high-volume use (e.g. one request per observation
  across a whole simulated pass).
