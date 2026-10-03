# SGP4, explained for someone new to orbital mechanics

## What it is

SGP4 (Simplified General Perturbations model 4) is the standard algorithm for predicting a satellite's position and velocity at a given time, given a compact description of its orbit. It's not AWS-specific or goTag-specific — it's the same algorithm NORAD/Space Force uses to publish tracking data for essentially every cataloged object, and it's what every satellite-tracking app (Heavens-Above, GPredict, N2YO) runs under the hood.

"Simplified" means it trades some accuracy for speed: it approximates the real forces acting on a satellite (Earth's non-spherical gravity, atmospheric drag, etc.) with a small set of closed-form equations instead of numerically integrating the real physics step by step. That's *why* it's fast enough to propagate thousands of objects in real time, and also *why* its accuracy decays the further you get from the time the input data was captured.

## The input: a TLE (Two-Line Element set)

SGP4 doesn't take "position and velocity" as input — it takes a TLE, a terse, fixed-column text format that encodes an orbit as a snapshot at one moment (the **epoch**). Example (ISS):

```
1 25544U 98067A   24275.50000000  .00016717  00000-0  10270-3 0  9994
2 25544  51.6400 208.9163 0006703  69.9862 290.2454 15.49560532123456
```

Line 1 fields (the ones that matter day-to-day):
- **NORAD catalog number** (`25544`) — ISS's permanent ID.
- **Epoch** (`24275.50000000`) — year 2024, day-of-year 275.5 (noon on day 275). This is the single most important field: it's the "as of when" timestamp this whole TLE describes. Age matters — see below.
- **Mean motion derivative / B\* drag term** — crude stand-ins for atmospheric drag. B\* in particular is why SGP4 can account for drag at all without full atmospheric modeling.

Line 2 fields — the actual orbit shape, all **as of the epoch**, not fixed constants forever:
- **Inclination** — tilt of the orbit relative to the equator (ISS: ~51.6°).
- **RAAN** (Right Ascension of Ascending Node) — where the orbital plane crosses the equator, drifts over time due to Earth's oblateness (nodal regression) — SGP4 models this drift.
- **Eccentricity** — how circular vs. elliptical (ISS: nearly 0, i.e. nearly circular).
- **Argument of perigee** — orientation of the ellipse within the orbital plane.
- **Mean anomaly** — where the satellite is *along* its orbit at the epoch (like a clock position).
- **Mean motion** — revolutions per day (ISS: ~15.5, i.e. ~92-minute orbit).

## What you get out

Given a TLE and a target time, SGP4 returns **position and velocity in TEME** (True Equator, Mean Equinox — an Earth-centered inertial frame, not latitude/longitude). You then need a second step — a frame transform plus your ground site's location — to get the practically useful things: altitude/azimuth/elevation from a sensor, range, range-rate (needed for Doppler), lat/lon/alt, etc. This is exactly the gap `skyfield` fills — it wraps `sgp4`'s raw TEME output and gives you topocentric (ground-site-relative) geometry directly.

## Strengths

- **Fast** — closed-form, no numerical integration; can propagate many objects over long time spans almost instantly.
- **Standard** — it's what the TLEs you'll pull from CelesTrak/Space-Track are *designed* to be used with. Mixing TLEs with a different propagator produces wrong answers; the model and the data format are a matched pair.
- **Self-contained** — one TLE (a few hundred bytes) is enough to propagate an orbit; no need for a full force-model/ephemeris pipeline.

## Limitations — the ones that actually matter for goTag

- **Accuracy degrades with time-since-epoch.** At epoch, typical TLE-based accuracy is on the order of ~1 km; this grows to several km within a day or two, worse for objects with higher drag (lower altitude, less predictable atmosphere). **For a close-approach/disambiguation scenario, this is critical**: if your two objects are separated by less than the propagation error, SGP4 alone can't tell you which is which — the uncertainty swamps the signal. This is *why* real disambiguation needs actual sensor observations, not just orbit propagation — directly consistent with the observation-based approach already chosen for goTag.
- **No maneuver awareness.** If a satellite burns a thruster, every published TLE before that burn is now wrong until a new one is issued. Fine for ISS/debris (no maneuvers, or well-tracked ones); matters if you ever model active satellites.
- **Approximate drag model.** B\* is a single fudge-factor, not a real atmospheric density model — fine for short propagation windows, increasingly wrong over weeks.
- **Doesn't model close-proximity perturbations between the two objects themselves** — SGP4 propagates each object independently under Earth's gravity/drag only. It has no notion that object A's gravity might (negligibly, but still) affect object B, or that they're near each other at all. For goTag that's actually fine — you *want* two independent propagations that you then compare — just know SGP4 won't ever surprise you with new physics; any "closeness" dynamics come entirely from how you set up the two TLEs/state vectors yourself.

## Practical takeaway for goTag

1. Get the ISS's real, current TLE from CelesTrak (free, no auth).
2. Convert it to a state vector (position + velocity), apply a small, realistic delta-v to create the "companion" object's state vector — this is a one-time step at your chosen epoch, not a TLE edit.
3. Propagate *both* independently with SGP4 going forward in time (via `skyfield`, which also handles the TEME → ground-site-relative conversion for you).
4. Keep propagation windows short (minutes to hours) both because that's the physically realistic "hard to disambiguate" window, and because SGP4's own error growth means long propagations stop being trustworthy anyway — the two concerns point the same direction.
