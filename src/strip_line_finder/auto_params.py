"""Data-driven parameter selection for the strip line finder.

``auto_parameters(img)`` looks at the frame itself and returns a full set of
detection parameters plus the measurements they were derived from.

Pass 1 - geometry from resolution (defaults were tuned for 1920 x 1080)
    sx = width / 1920,  sy = height / 1080
    step       = height / 11              (about 11 strips per frame)
    margin     = 3  * sy
    max_width  = 14 * sx
    gap        = 2  * sx
    bg_window  = max(41 * sx, 3 * max_width)   (odd; must dwarf a line)
    min_brightness = clip(0.2 * lightness, 5, 60)

Pass 2 - min_contrast by stability search (not a fixed fraction of anything)
    Try a geometric ladder of thresholds from max(3, 3*noise) to 60. For each,
    detect lines on the strips and count the vertical tracks. Too low a
    threshold lets noise create extra or merged tracks; too high a threshold
    loses real lines. In between the track count stays roughly constant
    (a plateau; it may wobble by +-1 track or 10 %).
    The longest plateau is chosen and the threshold is placed 40 % of the way
    (geometrically) from its lower end, so there is margin on the noise side
    and tolerance for lines that fade along their length.
    Fallback if there is no plateau:
        min_contrast = clip(max(5 * noise_sigma, 0.03 * contrast), 3, 25)

Pass 3 - tracking from the chosen threshold
    spacing     typical distance between neighbouring tracked lines
    drift       90th percentile of how far a tracked line moves between strips
    x_tolerance = clip(min(max(2 * drift + 1, 0.3 % of width, 3),
                           0.45 * spacing_lower_quartile), 2, 5 % of width)
                  wide enough to follow a tilted line, always below half the
                  spacing so neighbours never merge. Fallback: 20 * sx.
    min_strips  = clip(round(0.25 * strips per frame), 2, 6)

All constants are collected below so they can be tuned for your footage.
"""
import numpy as np

from ._core import (Line, get_strip, link_vertical_lines, moving_median,
                    profile_signal, find_lines_from_signal)

# --- reference frame the library defaults were tuned for -------------------
REF_WIDTH = 1920.0
REF_HEIGHT = 1080.0

# --- geometry (scaled with resolution) --------------------------------------
TARGET_STRIPS = 11
REF_MARGIN = 3
REF_MAX_WIDTH = 14
REF_GAP = 2
REF_BG_WINDOW = 41
BG_WINDOW_PER_MAX_WIDTH = 3

# --- contrast / brightness ---------------------------------------------------
LADDER_LOW = 3.0
LADDER_HIGH = 60.0
LADDER_STEPS = 14
PLATEAU_POSITION = 0.4           # 0 = lower end of the plateau, 1 = upper end
PLATEAU_REL_TOL = 0.1            # a plateau may wobble by 10 % of its track count
PLATEAU_MIN_TOL = 1              # ... and by at least +-1 track
MAX_DENSITY_SPACING = 3          # reject thresholds giving lines closer than
                                 # this many max_widths on average (pure noise)
NOISE_K = 5.0                    # fallback: threshold = NOISE_K * noise sigma
LADDER_NOISE_K = 3.0             # ladder never starts below this * sigma
GLOBAL_CONTRAST_FRACTION = 0.03
FALLBACK_CONTRAST_RANGE = (3.0, 25.0)
BRIGHTNESS_FRACTION = 0.2
MIN_BRIGHTNESS_RANGE = (5.0, 60.0)
MAD_TO_SIGMA = 1.4826

# --- tracking -----------------------------------------------------------------
REF_X_TOLERANCE = 20
DRIFT_PERCENTILE = 90
SPACING_PERCENTILE = 25
SPACING_FRACTION = 0.45
X_TOL_MAX_FRACTION = 0.05
MIN_STRIP_FRACTION = 0.25


def _odd(n):
    n = int(round(n))
    return n if n % 2 else n + 1


def _as_rgb_float(img):
    arr = np.asarray(img, dtype=np.float32)
    if arr.ndim == 2:
        arr = np.stack([arr] * 3, axis=2)
    return arr


def measure_image(img):
    """Return (lightness, contrast) of an HxWx3 or HxW array with values 0-255.

    Works for RGB or BGR, because the luminance is the plain channel mean.
    """
    arr = np.asarray(img, dtype=np.float32)
    lum = arr.mean(axis=2) if arr.ndim == 3 else arr
    lum = lum[::4, ::4]
    lightness = float(lum.mean())
    p5, p95 = np.percentile(lum, [5, 95])
    return lightness, float(p95 - p5)


def _detect(signals, threshold, max_width, gap, min_brightness):
    """Detections on all strips at one threshold -> list of Line."""
    lines = []
    for row, (mag, lum_dev, bg_lum) in signals:
        for start, end, center, pol, contrast in find_lines_from_signal(
                mag, lum_dev, bg_lum, threshold, max_width, 1, gap, min_brightness):
            lines.append(Line(row, start, end, center, end - start + 1,
                              pol, round(contrast, 1)))
    return lines


def _noise_sigma(signals):
    mags = np.concatenate([mag for _, (mag, _, _) in signals])
    return float(MAD_TO_SIGMA * np.median(mags))


def _select_min_contrast(signals, lo, width, max_width, gap, min_brightness,
                         x_tol, min_strips):
    """Stability search. Returns (threshold or None, counts, ladder)."""
    ladder = np.geomspace(lo, LADDER_HIGH, LADDER_STEPS)
    counts, density = [], []
    for t in ladder:
        lines = _detect(signals, t, max_width, gap, min_brightness)
        counts.append(len(link_vertical_lines(lines, x_tol, min_strips)))
        density.append(len(lines) / len(signals))

    max_density = width / (MAX_DENSITY_SPACING * max_width)
    best = None
    i = 0
    while i < len(ladder):
        # extend the run while the count stays within tolerance of its start
        tol = max(PLATEAU_MIN_TOL, PLATEAU_REL_TOL * counts[i])
        j = i
        while j + 1 < len(ladder) and abs(counts[j + 1] - counts[i]) <= tol:
            j += 1
        level = float(np.median(counts[i:j + 1]))
        if level > 0 and j > i and max(density[i:j + 1]) <= max_density:
            key = (j - i, level)
            if best is None or key > best[0]:
                best = (key, i, j)
        i = j + 1 if j > i else i + 1
    if best is None:
        return None, counts, ladder
    _, i, j = best
    a, b = ladder[i], ladder[j]
    return float(a * (b / a) ** PLATEAU_POSITION), counts, ladder


def _spacing_and_drift(rows_centres, width):
    """Neighbour spacing and strip-to-strip drift from tracked line centres."""
    rows = sorted(rows_centres)
    diffs = []
    for r in rows:
        c = sorted(rows_centres[r])
        if len(c) >= 2:
            diffs.extend(np.diff(c))
    spacing_typ = spacing_close = None
    if len(diffs) >= 3:
        spacing_typ = float(np.median(diffs))
        spacing_close = float(np.percentile(diffs, SPACING_PERCENTILE))

    limit = 0.5 * spacing_typ if spacing_typ else 0.1 * width
    shifts = []
    for a, b in zip(rows, rows[1:]):
        if not rows_centres[a] or not rows_centres[b]:
            continue
        nxt = np.asarray(rows_centres[b])
        for x in rows_centres[a]:
            d = float(np.abs(nxt - x).min())
            if d <= limit:
                shifts.append(d)
    drift = float(np.percentile(shifts, DRIFT_PERCENTILE)) if len(shifts) >= 3 else None
    return spacing_typ, spacing_close, drift


def auto_parameters(img, overrides=None):
    """Return (params, measurements) for one frame.

    overrides: optional dict of values the caller fixes (e.g. {"step": 80}).
    They are used while measuring, so the other parameters adapt to them.

    params        step, margin, min_contrast, max_width, gap, bg_window,
                  min_brightness, x_tolerance, min_strips
    measurements  lightness, contrast, noise_sigma, threshold_method,
                  line_strength, line_spacing, line_drift, trial_detections
    """
    o = overrides or {}
    arr = _as_rgb_float(img)
    height, width = arr.shape[:2]
    sx, sy = width / REF_WIDTH, height / REF_HEIGHT

    # Pass 1: geometry from resolution, brightness floor from lightness
    step = int(o.get("step", np.clip(round(height / TARGET_STRIPS), 10, 400)))
    margin = int(o.get("margin", np.clip(round(REF_MARGIN * sy), 1, 10)))
    max_width = int(o.get("max_width", np.clip(round(REF_MAX_WIDTH * sx), 4, 60)))
    gap = int(o.get("gap", np.clip(round(REF_GAP * sx), 1, 6)))
    bg_window = int(o.get("bg_window", _odd(max(round(REF_BG_WINDOW * sx),
                                                BG_WINDOW_PER_MAX_WIDTH * max_width, 15))))
    lightness, contrast = measure_image(arr)
    min_brightness = float(o.get("min_brightness", np.clip(
        BRIGHTNESS_FRACTION * lightness, *MIN_BRIGHTNESS_RANGE)))

    rows = list(range(0, height, step))
    signals = [(row, profile_signal(get_strip(arr, row, margin).mean(axis=0), bg_window))
               for row in rows]
    min_strips_prov = int(np.clip(round(MIN_STRIP_FRACTION * len(rows)), 2, 6))
    x_tol_prov = REF_X_TOLERANCE * sx

    # Pass 2: min_contrast
    sigma = _noise_sigma(signals)
    if "min_contrast" in o:
        min_contrast, method = float(o["min_contrast"]), "fixed"
    else:
        lo = max(LADDER_LOW, LADDER_NOISE_K * sigma)
        chosen, _, _ = _select_min_contrast(signals, lo, width, max_width, gap,
                                            min_brightness, x_tol_prov, min_strips_prov)
        if chosen is not None:
            min_contrast, method = chosen, "stability plateau"
        else:
            min_contrast = float(np.clip(max(NOISE_K * sigma, GLOBAL_CONTRAST_FRACTION * contrast),
                                         *FALLBACK_CONTRAST_RANGE))
            method = "noise fallback"

    # Pass 3: tracking tolerance from tracked lines at the chosen threshold
    lines = _detect(signals, min_contrast, max_width, gap, min_brightness)
    tracks = link_vertical_lines(lines, x_tol_prov, min_strips_prov)
    centres = {row: [] for row in rows}
    strengths = []
    for t in tracks:
        for m in t:
            centres[m.row].append(m.center_px)
            strengths.append(m.contrast)
    spacing_typ, spacing_close, drift = _spacing_and_drift(centres, width)

    floor = max(3.0, 0.003 * width)
    x_tol = REF_X_TOLERANCE * sx if drift is None else max(floor, 2.0 * drift + 1.0)
    if spacing_close:
        x_tol = min(x_tol, SPACING_FRACTION * spacing_close)
    x_tolerance = int(round(np.clip(x_tol, 2, X_TOL_MAX_FRACTION * width)))

    params = {
        "step": step,
        "margin": margin,
        "min_contrast": round(min_contrast, 2),
        "max_width": max_width,
        "gap": gap,
        "bg_window": bg_window,
        "min_brightness": round(min_brightness, 2),
        "x_tolerance": x_tolerance,
        "min_strips": min_strips_prov,
    }
    measurements = {
        "lightness": round(lightness, 2),
        "contrast": round(contrast, 2),
        "noise_sigma": round(sigma, 3),
        "threshold_method": method,
        "line_strength": round(float(np.median(strengths)), 1) if strengths else None,
        "line_spacing": None if spacing_typ is None else round(spacing_typ, 1),
        "line_drift": None if drift is None else round(drift, 2),
        "trial_detections": len(lines),
    }
    return params, measurements