"""
Fetches a real satellite's orbit (ISS by default) and turns it into a
usable starting point for simulation: a position + velocity vector at
one instant in time.

Background for readers new to this domain:

A TLE ("Two-Line Element set") is the standard text format used to publish
a satellite's orbit. It does NOT give you position/velocity directly --
it gives you orbital parameters (shape, tilt, orientation of the orbit)
as of one specific moment, called the "epoch". To get an actual
position/velocity, you have to run the TLE through a propagator (SGP4).

We use the `skyfield` library here, which wraps the SGP4 propagator and
also handles frame conversions for us (turning SGP4's raw output into a
usable 3D Cartesian position/velocity).
"""

import urllib.request

import numpy as np
from skyfield.api import EarthSatellite, load

# ISS NORAD catalog number -- its permanent, unique ID in the public
# satellite catalog. Used to fetch its current TLE from CelesTrak.
ISS_NORAD_ID = 25544

# CelesTrak's "GP" (General Perturbations) query endpoint. This returns a
# fresh, real TLE for whatever NORAD ID we ask for -- no API key, no auth.
CELESTRAK_TLE_URL = (
    "https://celestrak.org/NORAD/elements/gp.php?CATNR={norad_id}&FORMAT=TLE"
)


def fetch_tle(norad_id: int = ISS_NORAD_ID) -> tuple[str, str]:
    """
    Downloads a satellite's current TLE from CelesTrak.

    Returns:
        (line1, line2) -- the two raw TLE text lines, exactly as published.
        These two lines together ARE the orbit description; nothing else
        is needed to reconstruct position/velocity at any nearby time.
    """
    url = CELESTRAK_TLE_URL.format(norad_id=norad_id)
    with urllib.request.urlopen(url) as f:
        text = f.read().decode("utf-8").strip().splitlines()

    # CelesTrak's TLE format response is 3 lines: a name line, then
    # line 1 and line 2 of the actual TLE.
    name, line1, line2 = text[0].strip(), text[1].strip(), text[2].strip()
    return line1, line2


def get_initial_state(
    line1: str, line2: str, at_time=None
) -> tuple[np.ndarray, np.ndarray, "object"]:
    """
    Propagates a TLE to a specific time and returns a usable state vector.

    Args:
        line1, line2: the TLE lines (see fetch_tle()).
        at_time: a skyfield Time to evaluate at. If None, uses "now"
            (the moment this function is called).

    Returns:
        position_km: 3-element array [x, y, z] in kilometers, in an
            Earth-centered inertial frame (GCRS -- a frame that does NOT
            rotate with the Earth; this matters later when we compute
            ground-site-relative geometry, which DOES need to account for
            Earth's rotation).
        velocity_km_s: 3-element array [vx, vy, vz] in km/s, same frame.
        epoch_time: the skyfield Time object this state vector corresponds
            to. We need to carry this forward because every later
            calculation (companion object propagation, ground-site
            angles) has to be anchored to a specific point in time, not
            just a position in space.
    """
    ts = load.timescale(builtin=True)  # builtin=True: use skyfield's bundled
    # leap-second table instead of downloading one -- keeps this working
    # offline/in a sandboxed environment.

    satellite = EarthSatellite(line1, line2, "ISS (ZARYA)", ts)

    if at_time is None:
        at_time = ts.now()

    geocentric = satellite.at(at_time)  # runs SGP4 under the hood
    position_km = geocentric.position.km
    velocity_km_s = geocentric.velocity.km_per_s

    return position_km, velocity_km_s, at_time
