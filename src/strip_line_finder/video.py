"""Video analysis: take a frame every N seconds and analyse each like an image."""
import csv
import json
from pathlib import Path

import cv2
import numpy as np

from .detect import DetectionConfig
from .image import analyse_image


def split_video(video_path, frames_dir, interval=1.0):
    """Save one frame every ``interval`` seconds (first frame at t = 0).

    Files are named ``frame_<index>.png`` where the number is the frame's index
    in the video. Returns a list of (frame_index, time_sec, path), in order.
    """
    video_path, frames_dir = Path(video_path), Path(frames_dir)
    if not video_path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")
    if interval <= 0:
        raise ValueError("interval must be > 0 seconds")

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise ValueError(f"Could not open video: {video_path}")
    try:
        fps = cap.get(cv2.CAP_PROP_FPS)
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if fps <= 0 or total <= 0:
            raise ValueError("Could not read frame rate / frame count from the video.")
        frames_dir.mkdir(parents=True, exist_ok=True)
        pad = max(5, len(str(total)))

        saved, seen = [], set()
        for t in np.arange(0.0, total / fps, interval):
            idx = min(int(round(t * fps)), total - 1)
            if idx in seen:                 # interval shorter than one frame
                continue
            seen.add(idx)
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ok, frame = cap.read()
            if not ok:
                continue
            path = frames_dir / f"frame_{idx:0{pad}d}.png"
            if not cv2.imwrite(str(path), frame):
                raise OSError(f"Could not write {path}")
            saved.append((idx, idx / fps, path))
        return saved
    finally:
        cap.release()


def process_video(video_path, output_dir="output", interval=1.0, config=None,
                  verbose=True):
    """Split a video every ``interval`` seconds and analyse every frame.

    Layout (name = video file name without extension):
        <output_dir>/video/frames/<name>/frame_XXXXX.png          raw frames
        <output_dir>/video/<name>/frame_XXXXX_marked.png          marked frames
        <output_dir>/video/<name>/lines.csv                       time, frame, lines

    ``lines`` holds the x positions of that frame's lines as a JSON array.
    Returns a list of dicts with time, frame and lines.
    """
    config = config or DetectionConfig()
    video_path = Path(video_path)
    name = video_path.stem
    root = Path(output_dir) / "video"
    frames_dir, out_dir = root / "frames" / name, root / name

    if verbose:
        print(f"Splitting {video_path.name} every {interval:g} s into {frames_dir}/ ...")
    frames = split_video(video_path, frames_dir, interval)
    if not frames:
        raise ValueError("No frames could be read from the video.")
    if verbose:
        print(f"Saved {len(frames)} frames. Analysing ...")

    out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for n, (idx, t, path) in enumerate(frames, start=1):
        res = analyse_image(path, out_dir, config, write_csv=False)
        rows.append({"time": round(t, 3), "frame": idx,
                     "lines": [round(x, 1) for x in res["lines"]]})
        if verbose:
            print(f"  [{n}/{len(frames)}] t = {t:.2f} s, frame {idx}: "
                  f"{len(res['lines'])} lines")

    csv_path = out_dir / "lines.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["time", "frame", "lines"])
        for r in rows:
            w.writerow([r["time"], r["frame"], json.dumps(r["lines"])])
    if verbose:
        print(f"Data: {csv_path}")
    return rows
