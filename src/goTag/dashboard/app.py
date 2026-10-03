"""
goTag dashboard -- a small Flask app for interactively exploring
cross-tagging scenarios without having to edit Python code by hand.

What this app does, end to end:
  1. GET /        -> renders a form pre-filled with ScenarioParams defaults.
  2. POST /       -> reads the form fields, builds a ScenarioParams, calls
                      run_scenario() (the one function that does all the
                      real work -- see goTag.simulation.scenario), and
                      renders the same page again with plots + headline
                      numbers appended below the form.

This file intentionally contains NO orbital mechanics. Its only job is:
form fields <-> ScenarioParams fields <-> plots of ScenarioResult fields.
If you want to understand the physics, read goTag/simulation/scenario.py,
orbit.py, and companion.py -- this file just displays what they produce.

Why matplotlib images instead of a JS charting library? This dashboard is
for one person's own exploratory tinkering (per the project README), not a
production UI -- server-side PNGs rendered to base64 and embedded directly
in the HTML keep this a single Flask app with no JS build step, no extra
client-side dependencies, and no static files to serve besides this one.
"""

import base64
import io
import sys
import traceback
from pathlib import Path

# Running this file directly (`python app.py`) only puts this file's own
# directory on sys.path, not src/ -- so `import goTag...` below would fail
# with ModuleNotFoundError unless we add src/ ourselves. (Same fix as
# tests/conftest.py uses for the same reason.)
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import matplotlib

# "Agg" is matplotlib's non-interactive, file/buffer-only backend. We need
# this because Flask runs with no display attached (no X server) -- the
# default backend would try to open a GUI window and crash.
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from flask import Flask, render_template, request

from goTag.simulation.scenario import ScenarioParams, run_scenario

app = Flask(__name__)


# ---------------------------------------------------------------------------
# Form <-> ScenarioParams plumbing
# ---------------------------------------------------------------------------

# One entry per *scalar* ScenarioParams field (the delta-v vector is handled
# separately below since it's 3 numbers packed into one array field).
# Each tuple is: (form field name, dataclass default, human label, help text).
# Keeping this as one list is what makes "every ScenarioParams field is an
# editable input" easy to guarantee -- the template just loops over it.
_DEFAULTS = ScenarioParams()

SCALAR_FIELDS = [
    (
        "ground_site_lat_deg",
        _DEFAULTS.ground_site_lat_deg,
        "Ground site latitude (deg)",
        "Where the simulated ground sensor sits. Default is Seattle.",
    ),
    (
        "ground_site_lon_deg",
        _DEFAULTS.ground_site_lon_deg,
        "Ground site longitude (deg)",
        "Negative = west. Default is Seattle.",
    ),
    (
        "ground_site_elevation_m",
        _DEFAULTS.ground_site_elevation_m,
        "Ground site elevation (m)",
        "Height above sea level. Small effect on the geometry; 0 is fine for most exploration.",
    ),
    (
        "duration_s",
        _DEFAULTS.duration_s,
        "Duration (s)",
        "How long to simulate. Longer than ~1 hour and the two objects usually drift apart enough to no longer be hard to tell apart.",
    ),
    (
        "timestep_s",
        _DEFAULTS.timestep_s,
        "Timestep (s)",
        "How finely to sample. Smaller = smoother/more accurate plots but slower to compute.",
    ),
    (
        "assumed_downlink_hz",
        _DEFAULTS.assumed_downlink_hz,
        "Assumed downlink frequency (Hz)",
        "Physics-only stand-in used for the Doppler-shift calculation -- not a claim about what either object really transmits on.",
    ),
]

# delta_v is a 3-vector; broken into dx/dy/dz inputs for the form, each in
# km/s. Realistic small maneuvers (e.g. a cubesat ejection) are roughly
# 0.001-0.01 km/s in magnitude -- called out explicitly in the template so
# the user doesn't accidentally type something like "3" and get a wildly
# unrealistic result.
DELTA_V_DEFAULTS = _DEFAULTS.delta_v_km_s


def _parse_params(form) -> ScenarioParams:
    """
    Reads the submitted form and builds a ScenarioParams out of it.

    Any field left blank or invalid falls back to the dataclass default
    rather than raising -- this is a tinkering tool, not a strict API, so
    being forgiving here matters more than being strict.
    """
    def _get_float(name: str, default: float) -> float:
        raw = form.get(name, "").strip()
        if raw == "":
            return default
        try:
            return float(raw)
        except ValueError:
            return default

    dx = _get_float("delta_v_dx", float(DELTA_V_DEFAULTS[0]))
    dy = _get_float("delta_v_dy", float(DELTA_V_DEFAULTS[1]))
    dz = _get_float("delta_v_dz", float(DELTA_V_DEFAULTS[2]))

    kwargs = {name: _get_float(name, default) for name, default, _, _ in SCALAR_FIELDS}
    kwargs["delta_v_km_s"] = np.array([dx, dy, dz])

    return ScenarioParams(**kwargs)


# ---------------------------------------------------------------------------
# Plotting helpers
# ---------------------------------------------------------------------------

def _fig_to_base64(fig) -> str:
    """
    Renders a matplotlib figure to a PNG held in memory, then base64-encodes
    it so it can be embedded directly in the HTML as
    <img src="data:image/png;base64,...">. This avoids needing to write
    files to disk or wire up a static-file route for generated plots.
    """
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", dpi=100)
    plt.close(fig)  # free the figure's memory -- otherwise these pile up
    # across requests since matplotlib keeps figures alive until closed.
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("ascii")


def _make_orbit_plots(result) -> dict:
    """
    Builds the spatial-trajectory plots (Pane 2: "real + simulated orbit
    view") from a ScenarioResult. Unlike the scalar diagnostic plots in
    _make_plots() below (range/angle/Doppler, all derived numbers), these
    plots show the actual 3D positions -- primary_position_km and
    companion_position_km -- so a person can SEE the two trajectories,
    not just read numbers about them.

    Design decision -- 2D vs 3D, and absolute vs relative frame:

    This dashboard deliberately has no JS charting library (see the
    module docstring above) -- every plot here is a single static
    matplotlib PNG, server-rendered, with one fixed camera angle. That
    constraint rules out an interactive 3D globe-style view; a static
    3D render only buys a "yes, these are orbits in 3D space" sanity
    check, not real spatial insight, since you can't rotate it.

    More importantly: the primary and companion orbit at ~6700+ km from
    Earth's center (low Earth orbit), but a realistic delta-v (per
    ScenarioParams docs, ~0.001-0.01 km/s) only pulls them apart by
    single-digit-to-tens of km over an hour. Plotted in absolute
    Earth-Centered-Inertial (ECI) coordinates, the companion's track
    would be visually INDISTINGUISHABLE from the primary's -- it would
    just look like one orbit line, because a few km of separation is
    invisible against a plot spanning ~7000 km. An absolute-frame plot
    would be honest about the orbit shape but dishonest about the thing
    this project actually cares about (divergence).

    So we build two plots:
      1. A quick absolute-frame 3D plot (cheap, uses matplotlib's
         built-in mplot3d toolkit -- no new dependency) just to orient
         the viewer: "yes, this is a real orbit around Earth, and the
         two objects are so close together at this scale that they
         overlap." The overlap itself is the point being illustrated.
      2. The RELATIVE-position plot (companion position minus primary
         position, in km, at each timestep) -- this is the priority
         plot. Zooming into the relative frame is what actually makes
         the divergence this project studies visible: the two objects
         start exactly coincident (relative position = origin) and
         trace out a small, growing path in km as time goes on.

    Returns a dict of {plot_name: base64_png_string} for the template.
    """
    plots = {}
    times_min = result.times_s / 60.0

    # --- 1. Absolute-frame 3D plot: orientation only ----------------------
    # Real ISS trajectory (primary, SGP4) and the simulated companion
    # (two-body + delta-v) plotted in the same Earth-Centered-Inertial
    # frame they were computed in. Different color AND linestyle for
    # each, per the task's "make it visually obvious which is real"
    # requirement -- even though at this zoomed-out scale the two lines
    # will appear to sit right on top of each other (that's expected and
    # is itself the lesson: without zooming into the relative frame
    # below, these two objects look identical from the outside).
    fig = plt.figure(figsize=(6.5, 6))
    ax = fig.add_subplot(111, projection="3d")
    ax.plot(
        result.primary_position_km[:, 0],
        result.primary_position_km[:, 1],
        result.primary_position_km[:, 2],
        color="tab:blue",
        linestyle="-",
        linewidth=1.8,
        label="Real (ISS, SGP4)",
    )
    ax.plot(
        result.companion_position_km[:, 0],
        result.companion_position_km[:, 1],
        result.companion_position_km[:, 2],
        color="tab:red",
        linestyle="--",
        linewidth=1.8,
        label="Simulated (companion, two-body + Δv)",
    )
    # Mark the shared starting point -- both objects begin at the exact
    # same position (only velocity differs at t=0, per companion.py).
    ax.scatter(
        [result.primary_position_km[0, 0]],
        [result.primary_position_km[0, 1]],
        [result.primary_position_km[0, 2]],
        color="black",
        s=25,
        label="Shared start position",
    )
    ax.set_xlabel("ECI X (km)")
    ax.set_ylabel("ECI Y (km)")
    ax.set_zlabel("ECI Z (km)")
    ax.set_title(
        "Absolute orbit (ECI frame) -- at this scale the two tracks\n"
        "overlap almost exactly; see the relative-position plot below\n"
        "for the actual divergence between them."
    )
    ax.legend(loc="upper left", fontsize=8)
    plots["orbit_absolute"] = _fig_to_base64(fig)

    # --- 2. Relative-position plot: the actual divergence (priority) -----
    # Companion position minus primary position, at each timestep, in
    # km. This is a RELATIVE vector in the same ECI axes, but with the
    # primary's own motion subtracted out -- so instead of two near-
    # identical ~7000 km orbit tracks, we see just the companion's small
    # drift away from the primary, starting at the origin (0,0,0) at
    # t=0 (both objects coincide there) and growing outward over time.
    # This is the plot that actually shows "how hard would these be to
    # tell apart", in the same spatial units (km) as the headline
    # min/max range numbers already reported below.
    relative_position_km = result.companion_position_km - result.primary_position_km

    # 2D projection onto the plane of greatest spread (we don't know in
    # advance which two of X/Y/Z the drift will mostly happen in -- it
    # depends on the delta-v direction and orbit geometry -- so rather
    # than guess, pick the two axes with the largest range of motion.
    # This keeps the plot a simple, static 2D image (consistent with the
    # rest of this dashboard) while still showing the dominant drift
    # direction rather than an arbitrarily-chosen pair of axes.
    spans = np.ptp(relative_position_km, axis=0)  # peak-to-peak range per axis
    axis_labels = ["X", "Y", "Z"]
    # Indices of the two axes with the largest spread, in ascending order
    # (so e.g. "X" is always plotted before "Y" regardless of magnitude).
    top_two = sorted(np.argsort(spans)[-2:])
    i_a, i_b = top_two[0], top_two[1]

    fig, ax = plt.subplots(figsize=(6, 5.5))
    # Color each point by elapsed time so the DIRECTION of drift over
    # time is visible, not just the final shape of the path.
    sc = ax.scatter(
        relative_position_km[:, i_a],
        relative_position_km[:, i_b],
        c=times_min,
        cmap="viridis",
        s=10,
    )
    ax.plot(
        relative_position_km[:, i_a],
        relative_position_km[:, i_b],
        color="gray",
        alpha=0.3,
        linewidth=0.8,
        zorder=0,
    )
    ax.scatter(
        [0], [0], color="black", marker="x", s=80, zorder=5,
        label="t=0 (both objects coincide here)",
    )
    ax.scatter(
        [relative_position_km[-1, i_a]],
        [relative_position_km[-1, i_b]],
        color="red",
        marker="o",
        s=50,
        zorder=5,
        label="End of simulation",
    )
    cbar = fig.colorbar(sc, ax=ax)
    cbar.set_label("Time (minutes)")
    ax.set_xlabel(f"Relative position, ECI {axis_labels[i_a]} (km)")
    ax.set_ylabel(f"Relative position, ECI {axis_labels[i_b]} (km)")
    ax.set_title(
        "Companion position relative to primary (companion − primary)\n"
        "Simulated (companion) drift away from Real (ISS primary), starting at 0"
    )
    ax.axhline(0, color="black", linewidth=0.5, alpha=0.3)
    ax.axvline(0, color="black", linewidth=0.5, alpha=0.3)
    ax.set_aspect("equal", adjustable="datalim")
    ax.legend(loc="best", fontsize=8)
    ax.grid(True, alpha=0.3)
    plots["orbit_relative"] = _fig_to_base64(fig)

    return plots


def _make_plots(result) -> dict:
    """
    Builds the four diagnostic plots from a ScenarioResult, each annotated
    with what it physically means (not just what's being plotted) -- this
    is the "ground truth" view a ground sensor would ultimately be trying
    to reconstruct from noisy real data.

    Returns a dict of {plot_name: base64_png_string} for the template.
    """
    times_min = result.times_s / 60.0  # minutes read easier than raw seconds
    # over a ~1 hour window.

    plots = {}

    # --- Range between objects -------------------------------------------
    # The straight-line 3D distance between the two objects themselves
    # (NOT their distance from the ground site). This is the most direct
    # "how hard is this to tell apart" signal: the smaller this gets, the
    # more the two objects' tracks/signals will overlap and be confusable.
    fig, ax = plt.subplots(figsize=(7, 3.5))
    ax.plot(times_min, result.range_between_objects_km)
    ax.set_xlabel("Time (minutes)")
    ax.set_ylabel("Range between objects (km)")
    ax.set_title("Separation distance between primary and companion")
    ax.grid(True, alpha=0.3)
    plots["range"] = _fig_to_base64(fig)

    # --- Angular separation ----------------------------------------------
    # How far apart the two objects APPEAR in the sky from the ground
    # site -- i.e. the angle between the two line-of-sight vectors, not
    # their physical distance in km. This is what an optical/angle-
    # tracking sensor would actually see: two objects can be physically
    # far apart in km but still look angularly close together (or vice
    # versa) depending on range and viewing geometry.
    fig, ax = plt.subplots(figsize=(7, 3.5))
    ax.plot(times_min, result.angular_separation_deg, color="tab:orange")
    ax.set_xlabel("Time (minutes)")
    ax.set_ylabel("Angular separation (deg)")
    ax.set_title("Apparent separation as seen from the ground site (not physical distance)")
    ax.grid(True, alpha=0.3)
    plots["angular"] = _fig_to_base64(fig)

    # --- Doppler shift, both objects on one plot -------------------------
    # How much each object's RF signal frequency appears shifted due to
    # its relative motion toward/away from the ground site (classic
    # Doppler effect). Plotting both together is the point: if their
    # Doppler *tracks* are close together/crossing, that's exactly the
    # scenario where an RF sensor could mix up which signal belongs to
    # which object -- the core "cross-tagging" problem this project
    # studies.
    fig, ax = plt.subplots(figsize=(7, 3.5))
    ax.plot(times_min, result.doppler_shift_primary_hz, label="Primary")
    ax.plot(times_min, result.doppler_shift_companion_hz, label="Companion")
    ax.set_xlabel("Time (minutes)")
    ax.set_ylabel("Doppler shift (Hz)")
    ax.set_title("Doppler shift of each object's downlink, as seen from the ground site")
    ax.legend()
    ax.grid(True, alpha=0.3)
    plots["doppler"] = _fig_to_base64(fig)

    return plots


def _headline_numbers(result) -> dict:
    """
    A handful of plain-English summary numbers pulled out of the full
    time series, so the user doesn't have to eyeball the plots to answer
    "so... how close did they get?"
    """
    return {
        "min_range_km": float(np.min(result.range_between_objects_km)),
        "max_range_km": float(np.max(result.range_between_objects_km)),
        "max_angular_separation_deg": float(np.max(result.angular_separation_deg)),
        "min_angular_separation_deg": float(np.min(result.angular_separation_deg)),
        "max_abs_doppler_primary_hz": float(
            np.max(np.abs(result.doppler_shift_primary_hz))
        ),
        "max_abs_doppler_companion_hz": float(
            np.max(np.abs(result.doppler_shift_companion_hz))
        ),
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/", methods=["GET", "POST"])
def index():
    """
    Single-page app: GET shows the (pre-filled) form only; POST runs the
    scenario and re-renders the same template with results appended.

    This is a synchronous request/response -- run_scenario() fetches a
    live TLE over the network and does a few seconds of numeric
    integration, so a POST here will visibly take a few seconds before
    the page comes back. For V1 that's an acceptable, simple tradeoff (see
    project instructions) -- we just make sure the page says so rather
    than looking stuck.
    """
    # Pre-filled values for the form: either the submitted values (so a
    # resubmit after an error doesn't lose what the user typed) or the
    # dataclass defaults on first load.
    if request.method == "POST":
        form_values = {
            "delta_v_dx": request.form.get("delta_v_dx", str(DELTA_V_DEFAULTS[0])),
            "delta_v_dy": request.form.get("delta_v_dy", str(DELTA_V_DEFAULTS[1])),
            "delta_v_dz": request.form.get("delta_v_dz", str(DELTA_V_DEFAULTS[2])),
        }
        for name, default, _, _ in SCALAR_FIELDS:
            form_values[name] = request.form.get(name, str(default))
    else:
        form_values = {
            "delta_v_dx": str(DELTA_V_DEFAULTS[0]),
            "delta_v_dy": str(DELTA_V_DEFAULTS[1]),
            "delta_v_dz": str(DELTA_V_DEFAULTS[2]),
        }
        for name, default, _, _ in SCALAR_FIELDS:
            form_values[name] = str(default)

    plots = None
    headline = None
    error = None

    if request.method == "POST":
        try:
            params = _parse_params(request.form)
            # The actual physics -- everything above/below this line is
            # just UI plumbing around this one call.
            result = run_scenario(params)
            # Scalar diagnostic plots (range/angle/Doppler) plus the
            # spatial orbit-view plots (Pane 2) are merged into one dict
            # keyed by plot name -- the template just looks up whichever
            # keys it needs for each pane.
            plots = {**_make_plots(result), **_make_orbit_plots(result)}
            headline = _headline_numbers(result)
        except Exception as exc:  # noqa: BLE001 -- deliberately broad: this
            # is a tinkering tool, and the most common failure mode is a
            # network hiccup fetching the live TLE from CelesTrak, which
            # we want to surface as a readable message rather than a 500.
            error = f"{exc}\n\n{traceback.format_exc()}"

    return render_template(
        "index.html",
        scalar_fields=SCALAR_FIELDS,
        form_values=form_values,
        plots=plots,
        headline=headline,
        error=error,
    )


if __name__ == "__main__":
    port = 5050
    print(f"goTag dashboard starting on http://0.0.0.0:{port}/")
    # debug=False in general for this kind of exploratory script is fine
    # either way, but keeping it off avoids the auto-reloader spawning a
    # second process, which is unnecessary here.
    app.run(host="0.0.0.0", port=port, debug=False)
