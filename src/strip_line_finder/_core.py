from dataclasses import dataclass
import numpy as np

@dataclass
class Line:
    row: int
    start_px: int
    end_px: int
    center_px: int
    width_px: int
    polarity: str
    contrast: float
    track_id: int = -1

def moving_median(signal, window):
    window = max(3, window | 1)
    pad = window // 2
    padded = np.pad(signal, pad, mode="edge")
    views = np.lib.stride_tricks.sliding_window_view(padded, window)
    return np.median(views, axis=1)

def get_strip(img, row, margin):
    h = img.shape[0]
    return img[max(0, row - margin):min(h, row + margin + 1)]

def profile_signal(profile, bg_window):
    """Background-subtracted signal of a strip profile (independent of thresholds).

    Returns (mag, lum_dev, bg_lum): the largest per-channel deviation from the
    local background, the luminance deviation, and the background luminance.
    """
    dev = np.stack([profile[:, c] - moving_median(profile[:, c], bg_window)
                    for c in range(3)], axis=1)
    mag = np.abs(dev).max(axis=1)

    lum = profile.mean(axis=1)
    lum_dev = lum - moving_median(lum, bg_window)
    bg_lum = lum - lum_dev
    return mag, lum_dev, bg_lum



def find_lines_from_signal(mag, lum_dev, bg_lum, min_contrast, max_width,
                           min_width, gap, min_brightness):
    """Threshold a precomputed signal at multiple contrasts and return
    unique line detections.
    """
    n = mag.shape[0]
    contrasts = np.arange(2, min_contrast, 2)
    found = []

    for contrast in contrasts:
        mask = (mag >= contrast) & (bg_lum >= min_brightness)
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
                center = int(round(
                    np.average(idx, weights=mag[idx] + 1e-6)
                ))
                polarity = (
                    "bright" if lum_dev[idx].sum() > 0 else "dark"
                )
                found.append((
                    start,
                    end,
                    center,
                    polarity,
                    float(mag[idx].max())
                ))
            x = end + 1
    return found

def find_lines_in_profile(profile, min_contrast, max_width, min_width,
                          bg_window, gap, min_brightness):
    """Finds line profiles within a strip."""
    mag, lum_dev, bg_lum = profile_signal(profile, bg_window)
    return find_lines_from_signal(mag, lum_dev, bg_lum, min_contrast, max_width,
                                  min_width, gap, min_brightness)

def link_vertical_lines(lines, x_tolerance, min_strips):
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
