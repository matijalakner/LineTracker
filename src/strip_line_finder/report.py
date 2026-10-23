"""Video-level report: aggregates every analysed frame into one report.

Written automatically at the end of process_video():
    video_report.txt     human-readable report for the whole video
    video_report.json    the same numbers, machine-readable
    frames_summary.csv   one row per analysed frame
    tracks.csv           one row per detected vertical line track
"""
import csv
import json
from datetime import datetime
from pathlib import Path

import numpy as np

SPACING_CV_LIMIT = 0.25  # flag a frame if spacing std / mean exceeds this


def track_summary(tracks):
    """One row of summary numbers per vertical track."""
    rows = []
    for members in tracks:
        centres = [m.center_px for m in members]
        polarities = [m.polarity for m in members]
        rows.append({
            "track_id": members[0].track_id,
            "mean_x": float(np.mean(centres)),
            "x_min": int(min(centres)),
            "x_max": int(max(centres)),
            "strips": len(members),
            "mean_width": float(np.mean([m.width_px for m in members])),
            "mean_contrast": float(np.mean([m.contrast for m in members])),
            "polarity": max(set(polarities), key=polarities.count),
        })
    return rows


def _frame_row(r):
    ts = track_summary(r["tracks"])
    xs = [t["mean_x"] for t in ts]
    diffs = np.diff(xs) if len(xs) >= 2 else []
    m = r.get("measurements") or {}
    p = r.get("parameters") or {}
    return {
        "frame_index": r["frame_index"],
        "timestamp_sec": r["timestamp_sec"],
        "lightness": m.get("lightness"),
        "contrast": m.get("contrast"),
        "noise_sigma": m.get("noise_sigma"),
        "min_contrast": p.get("min_contrast"),
        "min_brightness": p.get("min_brightness"),
        "x_tolerance": p.get("x_tolerance"),
        "step": p.get("step"),
        "margin": p.get("margin"),
        "tracks": len(ts),
        "detections": len(r["lines"]),
        "mean_spacing": float(np.mean(diffs)) if len(diffs) else None,
        "std_spacing": float(np.std(diffs)) if len(diffs) else None,
        "flags": "",
    }


def _stats(values):
    v = [x for x in values if x is not None]
    if not v:
        return None
    return {"min": float(np.min(v)), "median": float(np.median(v)),
            "max": float(np.max(v)), "mean": float(np.mean(v)),
            "std": float(np.std(v))}


def _fmt(v, nd=2):
    if v is None:
        return "-"
    if isinstance(v, (int, np.integer)):
        return str(v)
    return f"{v:.{nd}f}"


def _flag_frames(rows):
    counts = [r["tracks"] for r in rows]
    typical = int(round(float(np.median(counts)))) if counts else 0
    for r in rows:
        flags = []
        if r["tracks"] == 0:
            flags.append("no lines found")
        elif r["tracks"] != typical:
            flags.append(f"line count {r['tracks']} vs typical {typical}")
        if r["mean_spacing"] and r["std_spacing"] is not None:
            if r["std_spacing"] / r["mean_spacing"] > SPACING_CV_LIMIT:
                flags.append("irregular spacing")
        r["flags"] = "; ".join(flags)
    return typical


def _line_positions(results, tolerance):
    """Group track positions of all frames into lines that recur across frames."""
    pts = sorted((t["mean_x"], r["frame_index"])
                 for r in results for t in track_summary(r["tracks"]))
    groups = []
    for x, f in pts:
        if groups and x - groups[-1][-1][0] <= tolerance:
            groups[-1].append((x, f))
        else:
            groups.append([(x, f)])
    out = []
    for g in groups:
        xs = [x for x, _ in g]
        out.append({"mean_x": float(np.mean(xs)), "std_x": float(np.std(xs)),
                    "x_min": float(min(xs)), "x_max": float(max(xs)),
                    "frames": len({f for _, f in g})})
    return out


def write_video_report(results, output_dir, video_info):
    """Write the video-level report files; returns a dict of their paths."""
    output_dir = Path(output_dir)
    rows = [_frame_row(r) for r in results]
    typical = _flag_frames(rows)
    n = len(rows)

    spacing_means = [r["mean_spacing"] for r in rows]
    agg = {
        "frames_analysed": n,
        "typical_track_count": typical,
        "tracks_per_frame": _stats([r["tracks"] for r in rows]),
        "detections_per_frame": _stats([r["detections"] for r in rows]),
        "mean_spacing_px": _stats(spacing_means),
        "within_frame_spacing_std_px": _stats([r["std_spacing"] for r in rows]),
        "lightness": _stats([r["lightness"] for r in rows]),
        "contrast": _stats([r["contrast"] for r in rows]),
        "noise_sigma": _stats([r["noise_sigma"] for r in rows]),
        "min_contrast": _stats([r["min_contrast"] for r in rows]),
        "min_brightness": _stats([r["min_brightness"] for r in rows]),
        "x_tolerance": _stats([r["x_tolerance"] for r in rows]),
        "flagged_frames": [r["frame_index"] for r in rows if r["flags"]],
    }
    tol = agg["x_tolerance"]["median"] if agg["x_tolerance"] else 20
    positions = _line_positions(results, tol)

    # ---- CSV files ----------------------------------------------------------
    paths = {
        "report": output_dir / "video_report.txt",
        "json": output_dir / "video_report.json",
        "frames_csv": output_dir / "frames_summary.csv",
        "tracks_csv": output_dir / "tracks.csv",
    }
    with open(paths["frames_csv"], "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["frame_index"])
        w.writeheader()
        for r in rows:
            w.writerow({k: ("" if v is None else v) for k, v in r.items()})

    with open(paths["tracks_csv"], "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["frame_index", "timestamp_sec", "track_id", "mean_x", "x_min",
                    "x_max", "strips", "mean_width", "mean_contrast", "polarity"])
        for r in results:
            for t in track_summary(r["tracks"]):
                w.writerow([r["frame_index"], r["timestamp_sec"], t["track_id"],
                            round(t["mean_x"], 2), t["x_min"], t["x_max"], t["strips"],
                            round(t["mean_width"], 2), round(t["mean_contrast"], 2),
                            t["polarity"]])

    # ---- JSON ---------------------------------------------------------------
    with open(paths["json"], "w", encoding="utf-8") as f:
        json.dump({"video": video_info, "aggregate": agg, "frames": rows,
                   "line_positions": positions}, f, indent=2, default=str)

    # ---- Text report --------------------------------------------------------
    L = []
    L.append("=" * 78)
    L.append("VIDEO ANALYSIS REPORT")
    L.append("=" * 78)
    L.append(f"Generated:        {datetime.now():%Y-%m-%d %H:%M:%S}")
    L.append(f"Video:            {video_info.get('path')}")
    L.append(f"Resolution:       {video_info.get('width')} x {video_info.get('height')} px")
    L.append(f"Frame rate:       {_fmt(video_info.get('fps'))} fps")
    L.append(f"Total frames:     {video_info.get('total_frames')}  "
             f"(duration {_fmt(video_info.get('duration_sec'))} s)")
    L.append(f"Frames analysed:  {n}")
    L.append(f"Parameters:       {'automatic per frame' if video_info.get('auto_params') else 'fixed'}")
    L.append("")

    def stat_line(label, s, nd=2, unit=""):
        if not s:
            L.append(f"  {label:<26} -")
        else:
            L.append(f"  {label:<26} min {s['min']:.{nd}f}   median {s['median']:.{nd}f}"
                     f"   max {s['max']:.{nd}f}   mean {s['mean']:.{nd}f}{unit}")

    L.append("Overall results")
    L.append("-" * 78)
    L.append(f"  Typical number of lines:   {typical}")
    stat_line("Lines per frame", agg["tracks_per_frame"], 1)
    stat_line("Detections per frame", agg["detections_per_frame"], 1)
    stat_line("Mean line spacing (px)", agg["mean_spacing_px"])
    if agg["mean_spacing_px"]:
        L.append(f"  Spacing variation between frames (std of means): "
                 f"{agg['mean_spacing_px']['std']:.2f} px")
    stat_line("In-frame spacing std (px)", agg["within_frame_spacing_std_px"])
    L.append("")

    L.append("Image conditions and parameters used")
    L.append("-" * 78)
    stat_line("Lightness", agg["lightness"])
    stat_line("Contrast (P95-P5)", agg["contrast"])
    stat_line("Noise sigma", agg["noise_sigma"], 3)
    stat_line("min_contrast", agg["min_contrast"])
    stat_line("min_brightness", agg["min_brightness"])
    stat_line("x_tolerance (px)", agg["x_tolerance"], 1)
    L.append("")

    L.append("Per-frame results")
    L.append("-" * 78)
    L.append(f"{'frame':>6} {'t (s)':>7} {'light':>6} {'contr':>6} {'sigma':>6} "
             f"{'minC':>5} {'xtol':>4} {'lines':>5} {'spacing':>8} {'std':>6}  notes")
    for r in rows:
        L.append(f"{r['frame_index']:>6} {_fmt(r['timestamp_sec']):>7} "
                 f"{_fmt(r['lightness'], 1):>6} {_fmt(r['contrast'], 1):>6} "
                 f"{_fmt(r['noise_sigma'], 2):>6} {_fmt(r['min_contrast'], 1):>5} "
                 f"{_fmt(r['x_tolerance']):>4} {r['tracks']:>5} "
                 f"{_fmt(r['mean_spacing'], 1):>8} {_fmt(r['std_spacing'], 1):>6}  {r['flags']}")
    L.append("")

    L.append("Line positions across frames")
    L.append("-" * 78)
    if positions:
        L.append(f"  (tracks closer than {tol:.0f} px are treated as the same line)")
        L.append(f"  {'mean x':>8} {'std':>6} {'range':>15} {'seen in frames':>16}")
        for p in positions:
            L.append(f"  {p['mean_x']:>8.1f} {p['std_x']:>6.1f} "
                     f"{p['x_min']:>7.0f}-{p['x_max']:<7.0f} {p['frames']:>9}/{n}")
    else:
        L.append("  No lines detected in any frame.")
    L.append("")

    L.append("Frames to review")
    L.append("-" * 78)
    flagged = [r for r in rows if r["flags"]]
    if flagged:
        for r in flagged:
            L.append(f"  frame {r['frame_index']} ({_fmt(r['timestamp_sec'])} s): {r['flags']}")
    else:
        L.append("  None - every frame matches the typical line count and spacing.")
    L.append("")

    L.append("Files")
    L.append("-" * 78)
    L.append("  Per-frame reports:  frame_XXXXX/frame_XXXXX_report.txt")
    for key in ("json", "frames_csv", "tracks_csv"):
        L.append(f"  {paths[key].name}")
    paths["report"].write_text("\n".join(L) + "\n", encoding="utf-8")
    return {k: str(v) for k, v in paths.items()}