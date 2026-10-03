"""
Ties orbit.py and companion.py together into one runnable "scenario":
given a delta-v and a ground site, produce the time-series data a sensor
would actually see -- angular separation (optical/angle-tracking view)
and Doppler shift (RF view) -- for two closely-spaced objects.

This module is the "exploration surface" -- every parameter here is
something we expect to want to tweak and immediately see the effect of
(e.g. in the Flask dashboard).
"""

from dataclasses import dataclass, field

import numpy as np
from skyfield.api import load, wgs84

from . import companion, orbit

# Speed of light, km/s -- used for the Doppler shift formula.
SPEED_OF_LIGHT_KM_S = 299_792.458


@dataclass
class ScenarioParams:
    """
    All the "knobs" a user can turn to explore different scenarios.
    This is the one place that defines what's explorable -- the Flask
    dashboard's input form should map directly to these fields.
    """

    # Delta-v applied to the primary object's velocity to create the
    # companion object, in km/s, as [dx, dy, dz]. Real cubesat ejections
    # are roughly 0.001-0.01 km/s (1-10 m/s) in magnitude -- default here
    # is a modest, realistic nudge.
    delta_v_km_s: np.ndarray = field(
        default_factory=lambda: np.array([0.003, 0.0, 0.0])
    )

    # Ground sensor site location (where we're "observing" from).
    ground_site_lat_deg: float = 47.6062  # Seattle, as a default/no particular reason
    ground_site_lon_deg: float = -122.3321
    ground_site_elevation_m: float = 0.0

    # How long to simulate, and how finely to sample it.
    duration_s: float = 3600.0  # 1 hour -- matches the "minutes-to-hours"
    # disambiguation window identified in the research (longer than that,
    # the objects have usually drifted apart enough to no longer be
    # "hard to tell apart").
    timestep_s: float = 5.0

    # Assumed downlink frequency for the Doppler calculation, in Hz.
    # This is a PHYSICS-ONLY stand-in (how much the frequency shifts due
    # to relative motion) -- NOT a claim about what either real object
    # actually transmits on. See docs/V1.md: transmission content itself
    # (actual frequency/modulation/beacon ID) is not something we
    # simulate as if it were real, only the Doppler/power physics are.
    assumed_downlink_hz: float = 437_000_000.0  # a common amateur-band value


@dataclass
class ScenarioResult:
    """What a scenario run hands back -- one row per timestep."""

    times_s: np.ndarray  # seconds since scenario start
    primary_position_km: np.ndarray  # shape (N, 3), Earth-centered inertial frame
    companion_position_km: np.ndarray  # shape (N, 3), same frame
    range_between_objects_km: np.ndarray  # shape (N,) -- straight-line distance
    # between the two objects (NOT to the ground site) -- this is the
    # "how close together are they" number.
    angular_separation_deg: np.ndarray  # shape (N,) -- as seen FROM the ground
    # site: the angle between the two objects in the observer's sky. This
    # is what an optical/angle-tracking sensor would actually perceive --
    # two objects can be far apart in km but still appear angularly close
    # (or vice versa) depending on geometry and range.
    doppler_shift_primary_hz: np.ndarray  # shape (N,)
    doppler_shift_companion_hz: np.ndarray  # shape (N,)


def run_scenario(params: ScenarioParams) -> ScenarioResult:
    """
    Runs one full scenario: fetch a real ISS TLE, derive a companion via
    delta-v, propagate both, and compute what a ground sensor would see.
    """
    ts = load.timescale(builtin=True)

    # Step 1: real orbit -> state vector at "now".
    line1, line2 = orbit.fetch_tle(orbit.ISS_NORAD_ID)
    primary_pos0_km, primary_vel0_km_s, epoch_time = orbit.get_initial_state(
        line1, line2
    )

    # Step 2: derive the companion's starting velocity via delta-v.
    # Position is identical at t=0 -- see companion.apply_delta_v() for why.
    companion_vel0_km_s = companion.apply_delta_v(
        primary_vel0_km_s, params.delta_v_km_s
    )

    # Step 3: propagate BOTH objects forward with the same two-body model
    # (see companion.py docstring for why this is the right apples-to-apples
    # comparison, and what it deliberately leaves out).
    times_s, primary_pos_km, primary_vel_km_s = companion.propagate_two_body(
        primary_pos0_km, primary_vel0_km_s, params.duration_s, params.timestep_s
    )
    _, companion_pos_km, companion_vel_km_s = companion.propagate_two_body(
        primary_pos0_km, companion_vel0_km_s, params.duration_s, params.timestep_s
    )

    # Step 4: distance between the two objects at each timestep -- this
    # is the "how hard to disambiguate" indicator (smaller = harder).
    range_between_objects_km = np.linalg.norm(
        primary_pos_km - companion_pos_km, axis=1
    )

    # Step 5: ground-site geometry. skyfield's wgs84.latlon(...).at(time)
    # gives the ground site's own position+velocity in the SAME inertial
    # frame as the satellites, correctly accounting for Earth's rotation
    # at each instant -- that rotation is exactly why we can't just treat
    # the ground site as a fixed point in this frame.
    ground_site = wgs84.latlon(
        params.ground_site_lat_deg,
        params.ground_site_lon_deg,
        params.ground_site_elevation_m,
    )

    n = len(times_s)
    angular_separation_deg = np.zeros(n)
    doppler_shift_primary_hz = np.zeros(n)
    doppler_shift_companion_hz = np.zeros(n)

    for i in range(n):
        t = ts.tt_jd(epoch_time.tt + times_s[i] / 86400.0)  # advance the
        # skyfield Time by this many seconds (converted to days, since
        # skyfield's "tt" epoch is in Julian days)

        site_geocentric = ground_site.at(t)
        site_pos_km = site_geocentric.position.km
        site_vel_km_s = site_geocentric.velocity.km_per_s

        # Line-of-sight vectors from the ground site to each object.
        los_primary = primary_pos_km[i] - site_pos_km
        los_companion = companion_pos_km[i] - site_pos_km

        # Angular separation = angle between the two line-of-sight
        # vectors, via the standard vector dot-product formula:
        # cos(theta) = (a . b) / (|a| |b|)
        cos_theta = np.dot(los_primary, los_companion) / (
            np.linalg.norm(los_primary) * np.linalg.norm(los_companion)
        )
        # clip guards against tiny floating-point overshoot past [-1, 1],
        # which would otherwise make arccos return NaN.
        cos_theta = np.clip(cos_theta, -1.0, 1.0)
        angular_separation_deg[i] = np.degrees(np.arccos(cos_theta))

        # Doppler shift: how fast each object's distance from the ground
        # site is changing (range-rate), projected along the line of
        # sight, converted to a frequency shift via the classic Doppler
        # formula: delta_f = -f0 * (range_rate / c).
        # (Negative sign: an object approaching, i.e. negative range-rate,
        # causes a positive/upward frequency shift.)
        for los, obj_vel_km_s, out_array in (
            (los_primary, primary_vel_km_s[i], doppler_shift_primary_hz),
            (los_companion, companion_vel_km_s[i], doppler_shift_companion_hz),
        ):
            relative_vel_km_s = obj_vel_km_s - site_vel_km_s
            unit_los = los / np.linalg.norm(los)
            range_rate_km_s = np.dot(relative_vel_km_s, unit_los)
            out_array[i] = (
                -params.assumed_downlink_hz * range_rate_km_s / SPEED_OF_LIGHT_KM_S
            )

    return ScenarioResult(
        times_s=times_s,
        primary_position_km=primary_pos_km,
        companion_position_km=companion_pos_km,
        range_between_objects_km=range_between_objects_km,
        angular_separation_deg=angular_separation_deg,
        doppler_shift_primary_hz=doppler_shift_primary_hz,
        doppler_shift_companion_hz=doppler_shift_companion_hz,
    )
