"""
Flask dashboard for exploring goTag scenarios interactively.

This package is deliberately separate from `goTag.simulation` -- it is a
thin UI layer that imports the simulation's public API (ScenarioParams,
run_scenario) and never reaches into its internals. If you're looking for
the actual orbital-mechanics logic, it lives in `goTag.simulation`, not
here.
"""
