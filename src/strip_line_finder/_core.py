from dataclasses import dataclass
import numpy as np


@dataclass
class AnalysisConfig:
    """Detection parameters shared by the image, video and CLI entry points."""
    step: int = 100
    margin: int = 3
    min_contrast: float = 7.0
    min_width: int = 1
    max_width: int = 14
    bg_window: int = 41
    gap: int = 2
    min_brightness: float = 25.0
    x_tolerance: int = 20
    min_strips: int = 3
    keep_all: bool = False


@dataclass
class Line:
    row: int            # the sampled (centre) row of the strip
    start_px: int       # first pixel (x) of the line
    end_px: int         # last pixel (x) of the line
    center_px: int      # pixel (x) where the line is strongest
    width_px: int       # line thickness along the strip
    polarity: str       # "dark" or "bright" relative to surroundings
    contrast: float     # strength of the line (0-255 levels)
    track_id: int = -1  # vertical line this detection belongs to


def moving_median(signal, window):
    """Median filter (edge padded): the local 'background' level."""
    window = max(3, window | 1)
    pad = window // 2
    padded = np.pad(signal, pad, mode="edge")
    views = np.lib.stride_tricks.sliding_window_view(padded, window)
    return np.median(views, axis=1)


def get_strip(img, row, margin):
    """Rows [row-margin, row+margin], clamped to the image borders."""
    h = img.shape[0]
    return img[max(0, row - margin):min(h, row + margin + 1)]


def profile_signal(profile, bg_window):
    """Per-pixel deviation signals of a strip profile (n x 3 array).

    Returns (mag, lum_dev, bg_lum): colour-deviation magnitude, luminance
    deviation from the local background, and the background luminance.
    """
    dev = np.stack([profile[:, c] - moving_median(profile[:, c], bg_window)
                    for c in range(3)], axis=1)
    mag = np.abs(dev).max(axis=1)
    lum = profile.mean(axis=1)
    lum_dev = lum - moving_median(lum, bg_window)
    return mag, lum_dev, lum - lum_dev


def find_lines_from_signal(mag, lum_dev, bg_lum, min_contrast, max_width,
                           min_width, gap, min_brightness):
    """Finds lines in precomputed signals (see profile_signal).

    Returns a list of (start, end, center, polarity, contrast).
    """
    n = mag.shape[0]
    mask = (mag >= min_contrast) & (bg_lum >= min_brightness)

    found = []
    x = 0
    while x < n:
        if not mask[x]:
            x += 1
            continue
        start = end = x
        while True:
            nxt = None
            for k in range(1, gap + 2):
                if end + k < n and mask[end + k]:
                    nxt = end + k
                    break
            if nxt is None:
                break
            end = nxt
        width = end - start + 1
        if min_width <= width <= max_width:
            idx = np.arange(start, end + 1)
            center = int(round(np.average(idx, weights=mag[idx] + 1e-6)))
            polarity = "bright" if lum_dev[idx].sum() > 0 else "dark"
            found.append((start, end, center, polarity, float(mag[idx].max())))
        x = end + 1
    return found


def find_lines_in_profile(profile, min_contrast, max_width, min_width,
                          bg_window, gap, min_brightness):
    """Finds line profiles within a strip."""
    mag, lum_dev, bg_lum = profile_signal(profile, bg_window)
    return find_lines_from_signal(mag, lum_dev, bg_lum, min_contrast, max_width,
                                  min_width, gap, min_brightness)


def link_vertical_lines(lines, x_tolerance, min_strips):
    """Links detections across multiple strips into unified vertical tracks."""
    groups = []
    for line in sorted(lines, key=lambda l: l.center_px):
        if groups and line.center_px - groups[-1][-1].center_px <= x_tolerance:
            groups[-1].append(line)
        else:
            groups.append([line])

    tracks = []
    for g in groups:
        if len({m.row for m in g}) < min_strips:
            continue
        med = float(np.median([m.center_px for m in g]))
        per_row = {}
        for m in g:
            if m.row not in per_row or abs(m.center_px - med) < abs(
                    per_row[m.row].center_px - med):
                per_row[m.row] = m
        tracks.append([per_row[r] for r in sorted(per_row)])

    tracks.sort(key=lambda t: np.mean([m.center_px for m in t]))
    for tid, t in enumerate(tracks, start=1):
        for m in t:
            m.track_id = tid
    return tracks