from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np

from ._core import AnalysisConfig
from .analysis import analyze_cleaned_data_from_csv
from .auto_params import auto_parameters
from .image import analyse_image, annotate_image, export_pixel_histogram
from .report import track_summary, write_video_report

# Same defaults as the single-image tool: AnalysisConfig is the single source of truth
DEFAULT_PARAMS = asdict(AnalysisConfig())

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
                        files, measurements=None, auto_keys=(), bin_auto=True):
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
    out.append(f"  {'bin_size':<15} {bin_size}{'  (auto)' if bin_auto else ''}")
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


def _video_info(video_path):
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise ValueError(f"Could not open video: {video_path}")
    info = {
        "path": str(video_path),
        "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
        "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        "fps": cap.get(cv2.CAP_PROP_FPS),
        "total_frames": int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
    }
    cap.release()
    fps, total = info["fps"], info["total_frames"]
    info["duration_sec"] = total / fps if fps > 0 and total > 0 else None
    return info


# ---------------------------------------------------------------------------
# Step 1: slice the video into frame files
# ---------------------------------------------------------------------------
def split_video(video_path, output_dir=None, num_frames=None, image_format="png"):
    """Split a video into frames and save them in a new directory.

    num_frames=None saves every frame; an integer saves that many evenly
    spaced frames. Files are named ``frame_00000.png`` ... where the number is
    the frame's index in the video. Returns the list of saved paths, in order.
    """
    video_path = Path(video_path)
    if not video_path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    ext = image_format.lower().lstrip(".")
    if ext == "jpeg":
        ext = "jpg"
    if ext not in ("png", "jpg"):
        raise ValueError("image_format must be 'png' or 'jpg'")

    if output_dir is None:
        output_dir = video_path.with_name(f"{video_path.stem}_frames")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise ValueError(f"Could not open video: {video_path}")

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    pad = max(5, len(str(max(total_frames, 1))))

    def save(idx, frame):
        path = output_dir / f"frame_{idx:0{pad}d}.{ext}"
        if not cv2.imwrite(str(path), frame):
            raise OSError(f"Could not write {path}")
        return path

    saved = []
    try:
        if num_frames is None:
            idx = 0
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                saved.append(save(idx, frame))
                idx += 1
        else:
            if total_frames <= 0:
                raise ValueError("Could not read frame count from video.")
            if num_frames < 1:
                raise ValueError("num_frames must be at least 1")
            if num_frames >= total_frames:
                indices = range(total_frames)
            else:
                indices = np.linspace(0, total_frames - 1, num_frames, dtype=int)
            for idx in indices:
                idx = int(idx)
                cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
                ret, frame = cap.read()
                if ret:
                    saved.append(save(idx, frame))
    finally:
        cap.release()
    return saved


# ---------------------------------------------------------------------------
# Step 2: analyse one frame file exactly like a single image
# ---------------------------------------------------------------------------
def analyse_frame(frame_path, out_dir, params, bin_size=None, timestamp=0.0,
                  video_path=None, measurements=None, auto_keys=()):
    """Run the single-image pipeline on one saved frame.

    analyse_image -> annotate_image -> export_pixel_histogram ->
    analyze_cleaned_data_from_csv -> text report. Same calls, same order as
    examples/single_image.py.
    """
    frame_path = Path(frame_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    stem = frame_path.stem
    idx = int(stem.split("_")[-1])
    marked_path = out_dir / f"{stem}_marked.png"
    hist_path = out_dir / f"{stem}_histogram.png"
    csv_path = out_dir / f"{stem}_histogram.csv"
    report_path = out_dir / f"{stem}_report.txt"

    config = SimpleNamespace(**params)
    frame_bin = bin_size or max(2, int(round(config.x_tolerance / 2)))
    cluster_gap = int(round(2.5 * config.x_tolerance))

    # 1. Analyse the image
    width, height, lines, tracks = analyse_image(str(frame_path), config)

    # 2. Annotate and save the marked image
    annotate_image(str(frame_path), lines, tracks, config.margin, str(marked_path),
                   config.step, config.x_tolerance)

    # 3. Pixel histogram and CSV (the CSV is written next to the PNG)
    export_pixel_histogram(str(frame_path), lines, frame_bin, str(hist_path))

    # 4. Statistics from the histogram CSV
    hist_stats = analyze_cleaned_data_from_csv(str(csv_path), cluster_gap=cluster_gap)

    # 5. Text report for this frame
    files = {"frame": frame_path, "marked": marked_path,
             "histogram": hist_path, "csv": csv_path}
    _write_frame_report(report_path, video_path, idx, timestamp, width, height,
                        params, frame_bin, cluster_gap, lines, tracks, hist_stats,
                        files, measurements, auto_keys, bin_auto=not bin_size)

    return {
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
    }


# ---------------------------------------------------------------------------
# Whole pipeline: slice first, then analyse frame by frame
# ---------------------------------------------------------------------------
def process_video(video_path, output_dir=None, num_frames=None, image_format="png",
                  bin_size=None, auto_params=True, make_report=True, verbose=True,
                  **kwargs):
    """Slice a video into frames, then analyse every frame like a single image.

    Output layout (``output_dir`` defaults to ``<video name>_analysis`` next to
    the video):
        frames/                  every sliced frame (frame_00000.png ...)
        analysis/frame_XXXXX/    marked image, histogram png/csv, text report
        video_report.txt/.json, frames_summary.csv, tracks.csv  (make_report)

    Parameters
    ----------
    num_frames : int or None
        None (default) slices and analyses EVERY frame. Give a number to use
        that many evenly spaced frames. Note: every frame is stored as an image,
        so long videos need a lot of disk space (a 4K PNG is roughly 10 MB).
    auto_params : bool
        True (default): parameters are measured per frame (see auto_params.py).
        Anything given in ``kwargs`` overrides the automatic value.
        False: fixed defaults, as in the single-image tool.
    bin_size : int or None
        Histogram bin width; None = half of the frame's x_tolerance.
    **kwargs
        step, margin, min_contrast, min_width, max_width, bg_window, gap,
        min_brightness, x_tolerance, min_strips, keep_all.

    Returns a list with one result dict per analysed frame.
    """
    unknown = set(kwargs) - set(DEFAULT_PARAMS)
    if unknown:
        raise TypeError(f"Unknown analysis parameter(s): {', '.join(sorted(unknown))}")
    base_params = {**DEFAULT_PARAMS, **kwargs}

    video_path = Path(video_path)
    if not video_path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")
    info = _video_info(video_path)
    fps = info["fps"]

    output_dir = Path(output_dir) if output_dir else video_path.with_name(
        f"{video_path.stem}_analysis")
    frames_dir = output_dir / "frames"
    analysis_dir = output_dir / "analysis"

    # Step 1: slice the video
    if verbose:
        print(f"Slicing {video_path.name} into {frames_dir}/ ...")
    frame_paths = split_video(video_path, frames_dir, num_frames, image_format)
    if not frame_paths:
        raise ValueError("No frames could be read from the video.")
    if verbose:
        print(f"Saved {len(frame_paths)} frames. Analysing ...")

    # Step 2: analyse frame by frame
    results = []
    for n, frame_path in enumerate(frame_paths, start=1):
        idx = int(frame_path.stem.split("_")[-1])
        params = dict(base_params)
        measurements, auto_keys = None, ()
        if auto_params:
            image = cv2.imread(str(frame_path))
            if image is None:
                raise OSError(f"Could not read frame image: {frame_path}")
            auto, measurements = auto_parameters(image, overrides=kwargs)
            auto_keys = tuple(k for k in auto if k not in kwargs)
            params.update({k: auto[k] for k in auto_keys})

        result = analyse_frame(
            frame_path, analysis_dir / frame_path.stem, params, bin_size=bin_size,
            timestamp=idx / fps if fps > 0 else 0.0, video_path=video_path,
            measurements=measurements, auto_keys=auto_keys)
        results.append(result)
        if verbose:
            print(f"  [{n}/{len(frame_paths)}] frame {idx}: "
                  f"{len(result['tracks'])} lines")

    # Step 3: whole-video report
    if make_report:
        video_info = {**info, "auto_params": auto_params}
        report_files = write_video_report(results, output_dir, video_info)
        for r in results:
            r["video_report_path"] = report_files["report"]
        if verbose:
            print(f"Report: {report_files['report']}")

    return results