"""Line spacing over time, from the lines.csv written by process_video."""
import csv
import json
from pathlib import Path

import numpy as np


def read_lines_csv(path):
    """Rows of lines.csv as dicts: time (float), frame (int), lines (list)."""
    with open(path, newline="", encoding="utf-8") as f:
        return [{"time": float(r["time"]), "frame": int(r["frame"]),
                 "lines": json.loads(r["lines"])} for r in csv.DictReader(f)]


def spacing_stats(xs):
    """(mean, std, n_lines) of the distances between neighbouring lines.

    Needs at least 2 lines. The std is the sample std (ddof=1) of the
    individual spacings, so it is NaN when the frame has only one spacing.
    """
    xs = np.sort(np.asarray(xs, dtype=float))
    if len(xs) < 2:
        return None
    d = np.diff(xs)
    std = float(np.std(d, ddof=1)) if len(d) > 1 else float("nan")
    return float(d.mean()), std, len(xs)


def find_video_dir(name, output_dir="output"):
    """output/video/<name>, or ``name`` itself if it is a folder with lines.csv."""
    p = Path(name)
    if (p / "lines.csv").exists():
        return p
    d = Path(output_dir) / "video" / name
    if not (d / "lines.csv").exists():
        raise FileNotFoundError(
            f"No lines.csv in {d}. Run 'analysis video' on '{name}' first.")
    return d


def analyse_spacing(name, output_dir="output"):
    """Plot the mean line spacing (error = std) against time.

    Reads <output_dir>/video/<name>/lines.csv and writes spacing.csv and
    spacing.png next to it. Frames with fewer than 2 lines are skipped.
    Returns a dict with the data and the written paths.
    """
    d = find_video_dir(name, output_dir)
    rows = []
    for r in read_lines_csv(d / "lines.csv"):
        s = spacing_stats(r["lines"])
        if s is not None:
            rows.append((r["time"], r["frame"], s[2], s[0], s[1]))
    if not rows:
        raise ValueError("No frame has at least 2 lines; nothing to plot.")

    t, frame, n, mean, std = (np.array(c) for c in zip(*rows))

    csv_path = d / "spacing.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["time", "frame", "n_lines", "mean_spacing_px", "std_spacing_px"])
        for row in rows:
            w.writerow([row[0], row[1], row[2], round(row[3], 3),
                        "" if np.isnan(row[4]) else round(row[4], 3)])

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.errorbar(t, mean, yerr=np.nan_to_num(std), fmt="o-", capsize=4,
                label="mean spacing, error = std of the spacings")
    ax.set_xlabel("time (s)")
    ax.set_ylabel("distance between lines (px)")
    ax.set_title(d.name)
    ax.grid(alpha=0.3)
    ax.legend()
    fig.tight_layout()
    png_path = d / "spacing.png"
    fig.savefig(png_path)
    plt.close(fig)

    return {"directory": str(d), "frames": len(rows), "time": t.tolist(),
            "mean_spacing": mean.tolist(), "std_spacing": std.tolist(),
            "csv_path": str(csv_path), "plot_path": str(png_path)}
