# goTag dashboard

A small Flask app for interactively exploring goTag cross-tagging scenarios --
edit the simulation parameters in a web form, run the scenario, and see the
resulting plots and headline numbers.

This is a thin UI layer only. All of the actual orbital-mechanics / physics
logic lives in `goTag.simulation` (`scenario.py`, `orbit.py`, `companion.py`)
and is unmodified by this app -- the dashboard just imports `ScenarioParams`
and `run_scenario()` from it.

## Running it

There's a `uv`-managed virtualenv already set up at `~/goTag/.venv` with
`flask` and `matplotlib` installed (from `~/goTag/requirements.txt`). From
the `~/goTag` project root:

```bash
~/goTag/.venv/bin/python src/goTag/dashboard/app.py
```

This starts the dashboard on port 5050. Open:

```
http://localhost:5050/
```

(or `http://<this machine's address>:5050/` if accessing remotely.)

## What to expect

- The form is pre-filled with the same defaults as `ScenarioParams` in
  `goTag/simulation/scenario.py`.
- Submitting the form runs a real scenario: it fetches a live ISS TLE from
  CelesTrak over the network, then numerically propagates both the primary
  and companion objects. This takes a few seconds -- the page will pause
  until the response comes back; that's expected, not a hang.
- Results are three plots (range between objects, angular separation as
  seen from the ground site, and Doppler shift of both objects) plus a
  small table of headline min/max numbers.
- If the TLE fetch fails (e.g. no network access, or CelesTrak is
  unreachable), the page shows the error message and traceback instead of
  crashing the server.
