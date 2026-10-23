import warnings
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np

from .analysis import analyze_cleaned_data_from_csv
from .auto_params import auto_parameters
from .image import analyse_image, annotate_image, export_pixel_histogram
from .report import track_summary, write_video_report

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

MEASUREMENT_LABELS = {
    "lightness": "Lightness (mean luminance)",
    "contrast": "Contrast (P95 - P5)",
    "noise_sigma": "Noise level (sigma)",
    "threshold_method": "min_contrast chosen by",
    "line_strength": "Typical line strength",
    "line_spacing": "Typical line spacing (px)",
    "line_drift": "Line drift between strips (px)",
    "trial_detections": "Trial detections",
}


def _write_frame_report(path, video_path, frame_index, timestamp, width, height,
                        params, bin_size, cluster_gap, lines, tracks, hist_stats,
                        files, measurements=None, auto_keys=()):
    summary = track_summary(tracks)
    out = []
    out.append("=" * 64)
    out.append(f"FRAME REPORT - frame {frame_index}")
    out.append("=" * 64)
    out.append(f"Video:       {video_path}")
    out.append(f"Frame index: {frame_index}")
    out.append(f"Timestamp:   {timestamp:.2f} s")
    out.append(f"Resolution:  {width} x {height} px")
    out.append("")

    if measurements:
        out.append("Measured image properties")
        out.append("-" * 64)
        for k, label in MEASUREMENT_LABELS.items():
            v = measurements.get(k)
            out.append(f"  {label:<34} {'-' if v is None else v}")
        out.append("")

    out.append("Parameters")
    out.append("-" * 64)
    for k, v in params.items():
        tag = "  (auto)" if k in auto_keys else ""
        out.append(f"  {k:<15} {v}{tag}")
    out.append(f"  {'bin_size':<15} {bin_size}{'  (auto)' if 'x_tolerance' in auto_keys else ''}")
    out.append(f"  {'cluster_gap':<15} {cluster_gap}{'  (auto)' if 'x_tolerance' in auto_keys else ''}")
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
                  bin_size=None, auto_params=True, make_report=True, **kwargs):
    """Sample frames uniformly from a video, run the full image analysis
    pipeline on each one and write reports automatically.

    Per sampled frame, a sub-folder ``frame_XXXXX/`` inside ``output_dir`` holds:
        frame_XXXXX.png, frame_XXXXX_marked.png,
        frame_XXXXX_histogram.png/.csv, frame_XXXXX_report.txt

    When ``make_report`` is True, the whole-video report is also written to
    ``output_dir``: video_report.txt, video_report.json, frames_summary.csv
    and tracks.csv (see report.py).

    Parameters
    ----------
    auto_params : bool
        True (default): every frame gets its own parameters measured from its
        lightness, contrast, noise level and line geometry (see
        auto_params.py). Any analysis parameter passed explicitly as a keyword
        argument overrides the automatic value and the rest adapt to it.
        False: fixed defaults, as in the single-image tool.
    bin_size : int or None
        Histogram bin width. None (default) = half the frame's x_tolerance.
    **kwargs
        step, margin, min_contrast, min_width, max_width, bg_window, gap,
        min_brightness, x_tolerance, min_strips, keep_all.
    """
    unknown = set(kwargs) - set(DEFAULT_PARAMS)
    if unknown:
        raise TypeError(f"Unknown analysis parameter(s): {', '.join(sorted(unknown))}")
    base_params = {**DEFAULT_PARAMS, **kwargs}

    video_path = Path(video_path)
    if not video_path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(str(video_path))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    vid_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    vid_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

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

        # Parameters for this frame: defaults < automatic values < explicit kwargs
        measurements, auto_keys = None, ()
        params = dict(base_params)
        if auto_params:
            auto, measurements = auto_parameters(frame, overrides=kwargs)
            auto_keys = tuple(k for k in auto if k not in kwargs)
            params.update({k: auto[k] for k in auto_keys})
        config = SimpleNamespace(**params)

        frame_bin = bin_size or max(2, int(round(config.x_tolerance / 2)))
        cluster_gap = int(round(2.5 * config.x_tolerance))

        # Save the frame so the image tools can work on it as a normal image
        cv2.imwrite(str(frame_path), frame)

        # 1. Image analysis
        width, height, lines, tracks = analyse_image(str(frame_path), config)

        # 2. Annotated image
        annotate_image(str(frame_path), lines, tracks, config.margin,
                       str(marked_path), config.step, config.x_tolerance)

        # 3. Histogram + CSV (the CSV is written next to the PNG)
        export_pixel_histogram(str(frame_path), lines, frame_bin, str(hist_path))

        # 4. Statistical post-processing of the histogram CSV
        hist_stats = analyze_cleaned_data_from_csv(str(csv_path), cluster_gap=cluster_gap)

        # 5. Text report for this frame
        files = {
            "frame": frame_path,
            "marked": marked_path,
            "histogram": hist_path,
            "csv": csv_path,
        }
        _write_frame_report(report_path, video_path, idx, timestamp, width, height,
                            params, frame_bin, cluster_gap, lines, tracks, hist_stats,
                            files, measurements, auto_keys)

        results.append({
            "frame_index": idx,
            "timestamp_sec": round(timestamp, 2),
            "width": width,
            "height": height,
            "lines": lines,
            "tracks": tracks,
            "statistics": hist_stats,
            "parameters": params,
            "measurements": measurements,
            "frame_path": str(frame_path),
            "marked_path": str(marked_path),
            "histogram_path": str(hist_path),
            "csv_path": str(csv_path),
            "report_path": str(report_path),
        })

    cap.release()

    # 6. Whole-video report, written automatically
    if make_report and results:
        video_info = {
            "path": str(video_path),
            "width": vid_w,
            "height": vid_h,
            "fps": fps,
            "total_frames": total_frames,
            "duration_sec": total_frames / fps if fps > 0 else None,
            "auto_params": auto_params,
        }
        report_files = write_video_report(results, output_dir, video_info)
        for r in results:
            r["video_report_path"] = report_files["report"]

    return results