import cv2
import numpy as np
from pathlib import Path
from PIL import Image, ImageDraw
from .image import analyse_image_array

def process_video(video_path, num_frames=10, output_dir=None, **kwargs):
    """Slices a video into uniformly sampled frames and runs line analysis."""
    video_path = Path(video_path)
    if not video_path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")

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

    if output_dir:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

    results = []
    for idx in frame_indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ret, frame = cap.read()
        if not ret:
            continue

        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img_float = frame_rgb.astype(np.float32)

        width, height, kept_lines, tracks = analyse_image_array(img_float, **kwargs)
        timestamp = idx / fps if fps > 0 else 0.0

        results.append({
            "frame_index": int(idx),
            "timestamp_sec": round(timestamp, 2),
            "width": width,
            "height": height,
            "lines": kept_lines,
            "tracks": tracks
        })

        if output_dir:
            pil_img = Image.fromarray(frame_rgb)
            draw = ImageDraw.Draw(pil_img)
            red = (255, 0, 0)
            step = kwargs.get("step", 100)
            x_tolerance = kwargs.get("x_tolerance", 20)

            for members in tracks:
                ms = sorted(members, key=lambda m: m.row)
                for a, b in zip(ms, ms[1:]):
                    if (b.row - a.row <= 2 * step and abs(b.center_px - a.center_px) <= x_tolerance):
                        draw.line([(a.center_px, a.row), (b.center_px, b.row)], fill=red, width=3)
            pil_img.save(output_dir / f"frame_{idx:05d}_marked.png")

    cap.release()
    return results