"""
Sanity checks on the scenario simulation -- not testing exact physical
values (that would require a reference implementation to compare against),
but checking the basic physical/structural properties we know must hold
regardless of the specific delta-v or ground site chosen.
"""

import numpy as np

from goTag.simulation.scenario import ScenarioParams, run_scenario


def test_objects_start_coincident_and_separate():
    """
    An impulsive maneuver changes velocity, not position -- so at t=0 the
    primary and companion objects must be at the exact same point in
    space (range == 0), and should move apart as time passes (since any
    nonzero delta-v creates some relative drift, even if not perfectly
    monotonic over long windows).
    """
    params = ScenarioParams(
        delta_v_km_s=np.array([0.003, 0.0, 0.0]),
        duration_s=300,
        timestep_s=10,
    )
    result = run_scenario(params)

    assert result.range_between_objects_km[0] == 0.0
    # short window, radial-ish delta-v -> should be clearly separating,
    # not coincidentally back at ~0 again.
    assert result.range_between_objects_km[-1] > result.range_between_objects_km[0]


def test_result_arrays_are_consistent_length_and_finite():
    """
    Every output time series should have one entry per timestep, and no
    NaN/inf values -- a NaN here almost always means a divide-by-zero
    (e.g. range == 0 before any delta-v would make the angular separation
    formula divide by zero) or a frame mismatch.
    """
    params = ScenarioParams(duration_s=600, timestep_s=10)
    result = run_scenario(params)
    n = len(result.times_s)

    for array in (
        result.primary_position_km,
        result.companion_position_km,
        result.range_between_objects_km,
        result.angular_separation_deg,
        result.doppler_shift_primary_hz,
        result.doppler_shift_companion_hz,
    ):
        assert len(array) == n
        assert np.all(np.isfinite(array))


def test_angular_separation_is_nonnegative_and_small_for_close_objects():
    """
    Angular separation is an angle between two line-of-sight vectors --
    it's mathematically defined to be in [0, 180] degrees. For objects
    only kilometers apart at LEO ranges (hundreds of km from a ground
    site), it should be a small fraction of a degree, not some large
    arbitrary number -- a bug in the vector math (e.g. wrong frame) would
    tend to produce much larger, physically implausible angles.
    """
    params = ScenarioParams(duration_s=600, timestep_s=10)
    result = run_scenario(params)

    assert np.all(result.angular_separation_deg >= 0.0)
    assert np.all(result.angular_separation_deg <= 180.0)
    assert np.max(result.angular_separation_deg) < 5.0  # sanity ceiling for this scenario
