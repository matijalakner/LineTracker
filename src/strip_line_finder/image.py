"""Single-image analysis: detect, mark, save."""
import csv
from pathlib import Path

import numpy as np
from PIL import Image

from .detect import DetectionConfig, detect_lines, mark_image, plot_line_signal


def analyse_image(image_path, out_dir, config=None, plot=False, write_csv=True):
    """Detect the vertical lines in one image file and save the results.

    Writes into ``out_dir`` (created if needed):
        <name>_marked.png   the image (same size) with the lines painted red
        <name>_lines.csv    columns line, x_px, spacing_px   (write_csv=True)
        <name>_signal.png   line-strength plot                (plot=True)

    Returns a dict with the line positions and the written paths.
    """
    config = config or DetectionConfig()
    image_path, out_dir = Path(image_path), Path(out_dir)
    if not image_path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")
    out_dir.mkdir(parents=True, exist_ok=True)

    img = np.asarray(Image.open(image_path).convert("RGB"))
    height, width = img.shape[:2]
    xs, sig, threshold = detect_lines(img, config)

    name = image_path.stem
    marked_path = out_dir / f"{name}_marked.png"
    Image.fromarray(mark_image(img, xs, config.half_width)).save(marked_path)
    result = {"name": name, "width": width, "height": height, "lines": xs,
              "threshold": threshold, "marked_path": str(marked_path)}

    if write_csv:
        csv_path = out_dir / f"{name}_lines.csv"
        gaps = np.diff(xs)
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["line", "x_px", "spacing_px"])
            for i, x in enumerate(xs):
                w.writerow([i + 1, round(x, 1), "" if i == 0 else round(float(gaps[i - 1]), 1)])
        result["csv_path"] = str(csv_path)

    if plot:
        plot_path = out_dir / f"{name}_signal.png"
        plot_line_signal(sig, xs, threshold, plot_path)
        result["plot_path"] = str(plot_path)
    return result
