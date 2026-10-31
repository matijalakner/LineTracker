import os
import platform
from datetime import datetime, timezone
from pathlib import Path
 
import numpy as np
from PIL import Image
 
from ..utils import write_csv
from .analysis import spacing_stats
from .detect import DetectionConfig
from .image import analyse_image

def _get_sort_time(path):
    stat = os.stat(path)
    if platform.system() == 'Windows':
        return stat.st_ctime
    try:
        return stat.st_birthtime
    except AttributeError:
        return stat.st_mtime

def photo_time_utc(path):
    t = datetime.fromtimestamp(_get_sort_time(path), timezone.utc)
    return t.isoformat(timespec="milliseconds").replace("+00:00", "Z")

def get_sorted_photos(
        path_to_folder: str|Path,
        allowed: tuple[str]|list[str]|set[str] = {'.jpg', '.jpeg', '.png', '.tif', '.tiff'}
    ) -> list[str|Path]:

    folder = Path(path_to_folder)
    if not folder.exists():
        raise FileNotFoundError(f"Path not found: {folder}")
    if not any(folder.iterdir()):
        raise ValueError(f"Folder is empty: {folder}")
    files = list(folder.iterdir())
    files.sort(key=lambda p: _get_sort_time(p))
    photos = [file for file in files if file.suffix.lower() in allowed and file.is_file()]
    if len(photos) < 1:
        raise ValueError(f"No photos in folder: {folder}")
    return photos

def tunne_parameters(tune_img, basse=None):
    return (base or DetectionConfig()), {"status": "default"}

RESULTS_HEADER = [
    "time_stamp", "photo", "file", "mean_spacing_px", "n_lines", "std_spacing_px", "warning"
]

def main_folder(
    path: str|Path = "input/folder",
    output_dir: str|Path = "output"
    ) -> list[tuple]:
    """Analyse every photo of a folder and write output/folder/<name>/results.csv.
    
    The first photo (oldest) is used to tune the detection settings, then every photo, include the first, is analysed with them.
    """
    path = Path(path)
    photos = get_sorted_photos(path)
    out_dir = Path(output_dir) / "folder" / path.name

    tune_img = np.asarray(Image.open(photos[0]).convert("RGB"))
    config, report = tune_parameters(tune_img)

    rows = []
    for n, photo, in enumerate(photos, start=1):
        warning = ""
        mean = std = ""
        n_lines = 0
        try:
            res = analyse_image(photo, out_dir, config, write_csv=False)
            n_lines = len(res["lines"])
            stats= spacing_stats(res["lines"])
            if stats is None:
                warning = "fewer than 2 lines"
            else:
                mean, std = round(stats[0], 3), ("" if np.isnan(stats[1]) else round(stats[1], 3))
        except Exception as e:
            warning = f"failed: {e}"
        rows.append((photo_time_utc(photo), n, photo.name, mean, n_lines, std, warning))
        print(f"[{n}/{len(photos)}] {photo.name}: {n_lines} lines {warning}")
    csv_path = write_csv(out_dir / "results.csv", RESULTS_HEADER, rows)
    print(f"Data:: {csv_path}")
    return rows