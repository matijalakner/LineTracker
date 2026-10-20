from dataclasses import dataclass
import numpy as np

@dataclass
class Line:
    row: int           # the sampled (centre) row of the strip
    start_px: int      # first pixel (x) of the line[cite: 2, 3]
    end_px: int        # last pixel (x) of the line[cite: 2, 3]
    center_px: int     # pixel (x) where the line is strongest[cite: 2, 3]
    width_px: int      # line thickness along the strip[cite: 2, 3]
    polarity: str      # "dark" or "bright" relative to surroundings[cite: 2, 3]
    contrast: float    # strength of the line (0-255 levels)[cite: 2, 3]
    track_id: int = -1 # vertical line this detection belongs to[cite: 2, 3]

def moving_median(signal, window):
    """Median filter (edge padded): the local 'background' level[cite: 2, 3]."""
    window = max(3, window | 1)
    pad = window // 2
    padded = np.pad(signal, pad, mode="edge")
    views = np.lib.stride_tricks.sliding_window_view(padded, window)
    return np.median(views, axis=1)

def get_strip(img, row, margin):
    """Rows [row-margin, row+margin], clamped to the image borders[cite: 2, 3]."""
    h = img.shape[0]
    return img[max(0, row - margin):min(h, row + margin + 1)]

def find_lines_in_profile(profile, min_contrast, max_width, min_width,
                          bg_window, gap, min_brightness):
    """Finds line profiles within a strip[cite: 2, 3]."""
    n = profile.shape[0]
    dev = np.stack([profile[:, c] - moving_median(profile[:, c], bg_window)
                    for c in range(3)], axis=1)
    mag = np.abs(dev).max(axis=1)

    lum = profile.mean(axis=1)
    lum_dev = lum - moving_median(lum, bg_window)
    bg_lum = lum - lum_dev

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

def link_vertical_lines(lines, x_tolerance, min_strips):
    """Links detections across multiple strips into unified vertical tracks[cite: 2, 3]."""
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