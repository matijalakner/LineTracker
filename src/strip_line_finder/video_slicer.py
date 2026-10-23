from pathlib import Path

import cv2
import numpy as np


def slice_video(video_path, output_dir=None, num_frames=None, image_format="png"):
    """Split a video into frames and save them in a new directory.

    Parameters
    ----------
    video_path : str or Path
        The video file to split.
    output_dir : str or Path, optional
        Directory to create for the frames. Default: a folder named
        ``<video name>_frames`` next to the video. It is created if missing
        (existing folders are reused; files with the same names are overwritten).
    num_frames : int, optional
        None (default) saves every frame. An integer saves that many frames,
        evenly spaced across the video.
    image_format : str
        "png" (lossless, default) or "jpg".

    Returns
    -------
    list of Path
        The saved frame files, in order. Files are named ``frame_00000.png``,
        ``frame_00001.png`` ... where the number is the frame's index in the video.
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
            # Every frame: read straight through (fast, no seeking)
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
