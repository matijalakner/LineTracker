import os
import platform
from pathlib import Path
from PIL import image
from PIL.ExifTags import TAGS

from .detect import DetectionConfig

def _get_sort_time(path):
    stat = os.stat(path)
    if platform.system() == 'Windows':
        return stat.st_ctime
    try:
        return stat.st_birthtime
    except AttributeError:
        return stat.st_mtime

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
    photos = [file for file in files if file.split('.')[-1] in allowed]
    if len(photos) < 1:
        raise ValueError(f"No photos in folder: {folder}")
    return photos

def tune_ing(tune_img):
    

def main_folder(
    path: str|Path = 'input/folder'
    ):
    photos = get_sorted_photos(path)
    params = tune_parameters(tune_img=photo[0])



