"""
Derives a "companion object" close to a primary satellite, and propagates
both objects forward in time using simple two-body physics.

Why not keep using SGP4/skyfield for the companion object too? Because
SGP4 only works on real, published TLEs -- it has no notion of "take this
orbit and nudge it a little." To create a physically-grounded nearby
object, we:

  1. Take the primary object's real state vector (position + velocity) at
     one instant (from orbit.py).
  2. Add a small delta-v (a sudden small velocity change) to get the
     companion's state vector at that same instant -- this mimics a real
     event like a cubesat ejection or a debris separation.
  3. Propagate BOTH objects forward from there using the same simple
     two-body model (gravity only, no drag, no J2 oblateness term).

Known simplification (intentional, for V1): the primary object is
normally propagated with full SGP4 (drag + J2 + more), but once we give
it a delta-v and switch to two-body propagation here, we're deliberately
dropping those higher-order effects for BOTH objects. This keeps the
comparison apples-to-apples (both objects propagated the same way) and is
a reasonable approximation over the short windows (minutes to hours) this
project cares about -- drag/J2 effects take longer than that to matter.
"""

import numpy as np

# Standard gravitational parameter of Earth (GM), in km^3/s^2.
# This single constant is what makes two-body propagation "two-body":
# it's the only force in the model (pure point-mass Earth gravity).
EARTH_MU_KM3_S2 = 398_600.4418


def apply_delta_v(velocity_km_s: np.ndarray, delta_v_km_s: np.ndarray) -> np.ndarray:
    """
    Applies an instantaneous velocity change (an "impulsive maneuver") to
    get the companion object's starting velocity.

    Args:
        velocity_km_s: the primary object's velocity at the maneuver instant.
        delta_v_km_s: the velocity change to apply, e.g. [0.0005, -0.0002, 0.0]
            for a 0.5 m/s nudge in x and -0.2 m/s in y (units are km/s, so
            real-world small maneuvers are tiny numbers here -- a typical
            cubesat ejection is on the order of 0.001-0.01 km/s, i.e. 1-10 m/s).

    Returns:
        The companion object's velocity at the same instant. Position is
        unchanged -- an impulsive maneuver changes velocity instantly, not
        position (the two objects start at the exact same point in space,
        then diverge as time passes).
    """
    return velocity_km_s + delta_v_km_s


def _two_body_acceleration(position_km: np.ndarray) -> np.ndarray:
    """
    Computes gravitational acceleration at a given position, assuming a
    spherical, point-mass Earth (no drag, no oblateness).

    This is Newton's law of gravitation in vector form:
    acceleration points toward Earth's center, with magnitude mu / r^2.
    """
    r = np.linalg.norm(position_km)
    return -EARTH_MU_KM3_S2 * position_km / r**3


def propagate_two_body(
    position_km: np.ndarray,
    velocity_km_s: np.ndarray,
    duration_s: float,
    timestep_s: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Propagates a state vector (position + velocity) forward in time using
    RK4 (4th-order Runge-Kutta) numerical integration under two-body
    gravity only.

    RK4 is a standard way to numerically step an ODE (ordinary
    differential equation) forward in time without needing a closed-form
    solution -- it's accurate enough for short windows like ours without
    needing a heavier physics library.

    Args:
        position_km, velocity_km_s: starting state vector.
        duration_s: how far forward in time to propagate, in seconds.
        timestep_s: the size of each integration step, in seconds. Smaller
            = more accurate but slower. A few seconds is plenty for the
            minutes-to-hours windows this project cares about.

    Returns:
        times_s: 1D array of time offsets (seconds from the start).
        positions_km: 2D array, shape (len(times_s), 3) -- position at each time.
        velocities_km_s: 2D array, same shape -- velocity at each time.
    """

    def derivative(state: np.ndarray) -> np.ndarray:
        # state = [x, y, z, vx, vy, vz]. Its time-derivative is
        # [vx, vy, vz, ax, ay, az] -- velocity is the derivative of
        # position, acceleration is the derivative of velocity.
        pos, vel = state[:3], state[3:]
        acc = _two_body_acceleration(pos)
        return np.concatenate([vel, acc])

    n_steps = int(duration_s // timestep_s) + 1
    times_s = np.arange(n_steps) * timestep_s

    positions_km = np.zeros((n_steps, 3))
    velocities_km_s = np.zeros((n_steps, 3))

    state = np.concatenate([position_km, velocity_km_s])
    positions_km[0], velocities_km_s[0] = state[:3], state[3:]

    for i in range(1, n_steps):
        # Classic RK4: sample the derivative at four points within the
        # step and combine them with the standard 1/6, 1/3, 1/3, 1/6
        # weights -- this is just the textbook RK4 formula, not anything
        # goTag-specific.
        h = timestep_s
        k1 = derivative(state)
        k2 = derivative(state + 0.5 * h * k1)
        k3 = derivative(state + 0.5 * h * k2)
        k4 = derivative(state + h * k3)
        state = state + (h / 6.0) * (k1 + 2 * k2 + 2 * k3 + k4)

        positions_km[i], velocities_km_s[i] = state[:3], state[3:]

    return times_s, positions_km, velocities_km_s
