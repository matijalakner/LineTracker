import warnings
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np

from .analysis import analyze_cleaned_data_from_csv
from .image import analyse_image, annotate_image, export_pixel_histogram

# Same defaults as the single-image tool (see examples/single_image.py)
DEFAULT_PARAMS = dict(
    step=100,
    margin=3,
    min_contrast=7.0,
    min_width=1,
    max_width=14,
    bg_window=41,
    gap=2,
    min_brightness=25.0,
    x_tolerance=20,
    min_strips=3,
    keep_all=False,
)


def _track_summary(tracks):
    """One row of summary numbers per vertical track."""
    rows = []
    for members in tracks:
        centres = [m.center_px for m in members]
        rows.append({
            "track_id": members[0].track_id,
            "mean_x": float(np.mean(centres)),
            "x_min": int(min(centres)),
            "x_max": int(max(centres)),
            "strips": len(members),
            "mean_width": float(np.mean([m.width_px for m in members])),
            "mean_contrast": float(np.mean([m.contrast for m in members])),
            "polarity": max({m.polarity for m in members},
                            key=[m.polarity for m in members].count),
        })
    return rows


def _write_frame_report(path, video_path, frame_index, timestamp, width, height,
                        params, bin_size, lines, tracks, hist_stats, files):
    summary = _track_summary(tracks)
    out = []
    out.append("=" * 64)
    out.append(f"FRAME REPORT - frame {frame_index}")
    out.append("=" * 64)
    out.append(f"Video:       {video_path}")
    out.append(f"Frame index: {frame_index}")
    out.append(f"Timestamp:   {timestamp:.2f} s")
    out.append(f"Resolution:  {width} x {height} px")
    out.append("")

    out.append("Parameters")
    out.append("-" * 64)
    for k, v in params.items():
        out.append(f"  {k:<15} {v}")
    out.append(f"  {'bin_size':<15} {bin_size}")
    out.append("")

    out.append("Detection summary")
    out.append("-" * 64)
    out.append(f"  Strip detections kept: {len(lines)}")
    out.append(f"  Vertical line tracks:  {len(tracks)}")
    out.append("")

    out.append("Tracks (left to right)")
    out.append("-" * 64)
    if summary:
        out.append(f"  {'ID':>3} {'mean x':>8} {'x range':>11} {'strips':>7} "
                   f"{'width':>6} {'contrast':>9}  polarity")
        for s in summary:
            out.append(
                f"  {s['track_id']:>3} {s['mean_x']:>8.1f} "
                f"{str(s['x_min']) + '-' + str(s['x_max']):>11} "
                f"{s['strips']:>7} {s['mean_width']:>6.1f} "
                f"{s['mean_contrast']:>9.1f}  {s['polarity']}")
    else:
        out.append("  No vertical lines found.")
    out.append("")

    out.append("Spacing between tracks (from track centres)")
    out.append("-" * 64)
    if len(summary) >= 2:
        diffs = np.diff([s["mean_x"] for s in summary])
        out.append(f"  Mean:   {diffs.mean():.2f} px")
        out.append(f"  Std:    {diffs.std():.2f} px")
        out.append(f"  Min:    {diffs.min():.2f} px")
        out.append(f"  Max:    {diffs.max():.2f} px")
    else:
        out.append("  Not enough tracks to compute spacing.")
    out.append("")

    out.append("Histogram-based statistics (analyze_cleaned_data_from_csv)")
    out.append("-" * 64)
    out.append(f"  Cleaned lines:  {hist_stats.get('total_lines', 0)}")
    out.append(f"  Pixel indexes:  {hist_stats.get('pixel_indexes', [])}")
    stats = hist_stats.get("stats") or {}
    if stats:
        out.append(f"  Mean spacing:   {stats['mean_diff']:.2f} px")
        out.append(f"  Std deviation:  {stats['std_diff']:.2f} px")
        out.append(f"  Min spacing:    {stats['min_diff']} px")
        out.append(f"  Max spacing:    {stats['max_diff']} px")
    else:
        out.append("  Not enough lines to compute spacing statistics.")
    out.append("")

    out.append("Output files")
    out.append("-" * 64)
    for label, p in files.items():
        out.append(f"  {label:<10} {p}")
    out.append("")

    Path(path).write_text("\n".join(out), encoding="utf-8")


def process_video(video_path, num_frames=10, output_dir="video_analysis_output",
                  bin_size=10, **kwargs):
    """Sample frames uniformly from a video and run the full image analysis
    pipeline on every one of them.

    For each sampled frame a sub-folder ``frame_XXXXX/`` is created inside
    ``output_dir`` containing:
        frame_XXXXX.png            the extracted frame
        frame_XXXXX_marked.png     annotated detections (annotate_image)
        frame_XXXXX_histogram.png  pixel histogram     (export_pixel_histogram)
        frame_XXXXX_histogram.csv  histogram data
        frame_XXXXX_report.txt     text report for the frame

    A ``summary.txt`` listing all frames is written to ``output_dir``.

    Extra keyword arguments (step, margin, min_contrast, min_width, max_width,
    bg_window, gap, min_brightness, x_tolerance, min_strips, keep_all) are
    passed on to the image analysis exactly as in the single-image tool.
    """
    unknown = set(kwargs) - set(DEFAULT_PARAMS)
    if unknown:
        raise TypeError(f"Unknown analysis parameter(s): {', '.join(sorted(unknown))}")
    params = {**DEFAULT_PARAMS, **kwargs}
    config = SimpleNamespace(**params)

    video_path = Path(video_path)
    if not video_path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(str(video_path))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)

    if total_frames <= 0:
        cap.release()
        raise ValueError("Could not read frame count from video.")

    if num_frames >= total_frames:
        frame_indices = list(range(total_frames))
    else:
        frame_indices = np.linspace(0, total_frames - 1, num_frames, dtype=int)

    results = []
    for idx in frame_indices:
        idx = int(idx)
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ret, frame = cap.read()
        if not ret:
            warnings.warn(f"Could not read frame {idx}; skipping.")
            continue

        timestamp = idx / fps if fps > 0 else 0.0
        stem = f"frame_{idx:05d}"
        frame_dir = output_dir / stem
        frame_dir.mkdir(parents=True, exist_ok=True)

        frame_path = frame_dir / f"{stem}.png"
        marked_path = frame_dir / f"{stem}_marked.png"
        hist_path = frame_dir / f"{stem}_histogram.png"
        csv_path = frame_dir / f"{stem}_histogram.csv"
        report_path = frame_dir / f"{stem}_report.txt"

        # Save the frame so the image tools can work on it as a normal image
        cv2.imwrite(str(frame_path), frame)

        # 1. Image analysis
        width, height, lines, tracks = analyse_image(str(frame_path), config)

        # 2. Annotated image
        annotate_image(str(frame_path), lines, tracks, config.margin,
                       str(marked_path), config.step, config.x_tolerance)

        # 3. Histogram + CSV (the CSV is written next to the PNG)
        export_pixel_histogram(str(frame_path), lines, bin_size, str(hist_path))

        # 4. Statistical post-processing of the histogram CSV
        hist_stats = analyze_cleaned_data_from_csv(str(csv_path))

        # 5. Text report for this frame
        files = {
            "frame": frame_path,
            "marked": marked_path,
            "histogram": hist_path,
            "csv": csv_path,
        }
        _write_frame_report(report_path, video_path, idx, timestamp, width, height,
                            params, bin_size, lines, tracks, hist_stats, files)

        results.append({
            "frame_index": idx,
            "timestamp_sec": round(timestamp, 2),
            "width": width,
            "height": height,
            "lines": lines,
            "tracks": tracks,
            "statistics": hist_stats,
            "frame_path": str(frame_path),
            "marked_path": str(marked_path),
            "histogram_path": str(hist_path),
            "csv_path": str(csv_path),
            "report_path": str(report_path),
        })

    cap.release()

    # Overall summary across all analysed frames
    summary = [f"Video: {video_path}",
               f"Frames analysed: {len(results)}", "",
               f"{'frame':>7} {'time (s)':>9} {'tracks':>7} {'detections':>11}  report"]
    for r in results:
        summary.append(f"{r['frame_index']:>7} {r['timestamp_sec']:>9.2f} "
                       f"{len(r['tracks']):>7} {len(r['lines']):>11}  {r['report_path']}")
    (output_dir / "summary.txt").write_text("\n".join(summary) + "\n", encoding="utf-8")

    return results