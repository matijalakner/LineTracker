import dataclasses
import json
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
 
import numpy as np
from PIL import Image
 
from ..utils import write_csv
from .analysis import spacing_stats
from .detect import DetectionConfig, check_config
from .image import analyse_image
from .tune import tune_candidates

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

_FIELD_TYPES = {"n_blocks": int, "bg_window": int, "k": float, "rel": float,
                "min_dist": int, "x_tol": int, "min_fraction": float,
                "band_rel": float, "smooth": int, "half_width": int}


def apply_overrides(text, config):
    """New DetectionConfig from text like ``k=4 rel=0.2`` (raises ValueError)."""
    changes = {}
    for token in text.replace(",", " ").split():
        name, sep, value = token.partition("=")
        if not sep or name not in _FIELD_TYPES:
            raise ValueError(f"'{token}' is not name=value with name one of: "
                             + ", ".join(_FIELD_TYPES))
        try:
            changes[name] = _FIELD_TYPES[name](value)
        except ValueError:
            raise ValueError(f"'{value}' is not a valid number for {name}") from None
    new = dataclasses.replace(config, **changes)
    check_config(new)
    return new


def _show_image(path):
    """Open an image in the system viewer; False if no viewer could be started."""
    try:
        if sys.platform.startswith("win"):
            os.startfile(path)
        else:
            cmd = "open" if sys.platform == "darwin" else "xdg-open"
            subprocess.Popen([cmd, str(path)], stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
        return True
    except Exception:
        return False


def _describe(config):
    shown = ("bg_window", "rel", "k", "min_dist", "x_tol")
    return ", ".join(f"{n}={getattr(config, n):.3g}" if isinstance(getattr(config, n), float)
                     else f"{n}={getattr(config, n)}" for n in shown)


def choose_parameters(first_photo, out_dir, base=None, interactive=True,
                      show=True, ask=input):
    """Tune the detection settings on one photo and let the user confirm them.

    The photo is analysed with the best suggestion of the tuner and the marked
    result is opened in the image viewer. Then:
      y  keep these settings
      n  next suggestion (Enter), or type settings such as ``k=4 rel=0.2``,
         which change the settings that were just shown
      q  stop
    Every attempt is saved as <out_dir>/tuning/try<N>_<name>_marked.png.
    With interactive=False the first suggestion is used without asking.

    Returns (config, info) or None if the user quit; info["status"] is the
    tuner's status ("ok", "check", "base", "fallback") or "manual".
    """
    first_photo, out_dir = Path(first_photo), Path(out_dir)
    img = np.asarray(Image.open(first_photo).convert("RGB"))
    cands = tune_candidates(img, base)
    if not interactive:
        return cands[0]["config"], cands[0]

    tuning_dir = out_dir / "tuning"
    index, config, info, label = 0, cands[0]["config"], cands[0], f"suggestion 1 of {len(cands)}"
    attempt = 0
    while True:
        attempt += 1
        res = analyse_image(first_photo, tuning_dir, config, write_csv=False)
        marked = tuning_dir / f"try{attempt}_{first_photo.stem}_marked.png"
        Path(res["marked_path"]).replace(marked)
        stats = spacing_stats(res["lines"])
        spacing = (f", mean spacing {stats[0]:.1f} px" +
                   ("" if np.isnan(stats[1]) else f" (std {stats[1]:.1f})")) if stats else ""
        print(f"\nAttempt {attempt} ({label}, status {info['status']}): "
              f"{len(res['lines'])} lines{spacing}")
        print(f"  settings: {_describe(config)}")
        print(f"  marked photo: {marked}")
        if show and not _show_image(marked):
            print("  (could not open an image viewer - open the file above yourself)")

        while True:
            answer = ask("Is this okay? [y = yes, n = no, q = quit] ").strip().lower()
            if answer in ("y", "yes"):
                return config, info
            if answer in ("q", "quit"):
                return None
            if answer in ("n", "no"):
                break
            print("Please answer y, n or q.")

        while True:
            more = index + 1 < len(cands)
            text = ask(("Enter = next suggestion, or type " if more else "Type ")
                       + "settings (name=value ..., e.g. k=4 rel=0.2), q = quit: ").strip()
            if text.lower() in ("q", "quit"):
                return None
            if not text:
                if not more:
                    print("No more suggestions - type settings or q.")
                    continue
                index += 1
                config, info = cands[index]["config"], cands[index]
                label = f"suggestion {index + 1} of {len(cands)}"
                break
            try:
                config = apply_overrides(text, config)
            except ValueError as e:
                print(e)
                continue
            info, label = {"status": "manual"}, "your settings"
            break


RESULTS_HEADER = [
    "time_stamp", "photo", "file", "mean_spacing_px", "n_lines", "std_spacing_px", "warning"
]

def _rolling_median(values, window):
    """Median of each value's neighbourhood (centred, shorter at the ends).

    window=None uses the whole series for every value.
    """
    values = np.asarray(values, dtype=float)
    if window is None:
        return np.full(len(values), np.median(values))
    half = max(1, int(window) // 2)
    return np.array([np.median(values[max(0, i - half):i + half + 1])
                     for i in range(len(values))])


def flag_unusual(rows, window=7, z_max=3.5, min_photos=3, tuning_failed=False):
    """Add warnings to the result rows; returns new rows (same format).

    Every photo is compared with its neighbours in time (a centred window of
    ``window`` photos; None = the whole folder), so a slow drift of the spacing
    or of the line count is not flagged, only sudden jumps are.

      * line count: flagged when it differs from the neighbours' median by 1 or more.
      * std: the ratio std / mean spacing is compared with the neighbours' median.
        The difference is scaled by a robust noise estimate (MAD of all
        differences, never below 5 % of the median ratio) and flagged when
        |z| > ``z_max``.
      * ``tuning_failed``: every row gets a note that default settings were used.

    "fewer than 2 lines" and "failed: ..." come from main_folder; photos with
    those are left out of the statistics. The comparisons need at least
    ``min_photos`` usable photos.
    """
    recs = [dict(zip(RESULTS_HEADER, r)) for r in rows]

    def add(rec, text):
        rec["warning"] = "; ".join(w for w in (rec["warning"], text) if w)

    if tuning_failed:
        for rec in recs:
            add(rec, "tuning fell back to default settings")

    usable = [r for r in recs if not r["warning"].startswith("failed")]
    if len(usable) >= min_photos:
        counts = np.array([r["n_lines"] for r in usable], dtype=float)
        for rec, c, m in zip(usable, counts, _rolling_median(counts, window)):
            if abs(c - m) >= 1:
                add(rec, f"{int(c)} lines vs median {m:g}")

    valid = [r for r in usable if r["mean_spacing_px"] != "" and r["std_spacing_px"] != ""]
    if len(valid) >= min_photos:
        ratio = np.array([r["std_spacing_px"] / r["mean_spacing_px"] for r in valid])
        resid = ratio - _rolling_median(ratio, window)
        scale = max(1.4826 * np.median(np.abs(resid - np.median(resid))),
                    0.05 * np.median(ratio))
        if scale > 0:
            for rec, z in zip(valid, resid / scale):
                if abs(z) > z_max:
                    add(rec, f"std {'high' if z > 0 else 'low'} (z={z:+.1f})")
    return [tuple(r[h] for h in RESULTS_HEADER) for r in recs]


def main_folder(
    path: str|Path = "input/folder",
    output_dir: str|Path = "output",
    window: int|None = 7,
    z_max: float = 3.5,
    interactive: bool = True,
    show: bool = True,
    ask=input
    ) -> list[tuple]:
    """Analyse every photo of a folder and write output/folder/<name>/results.csv.
    
    The first photo (oldest) is used to tune the detection settings (see
    choose_parameters): its marked result is shown and you confirm it with y, or
    answer n to try other settings. Then every photo, including the first, is
    analysed with the confirmed settings, which are saved to parameters.json.
    Unusual photos get a text in the ``warning`` column (see flag_unusual).
    interactive=False skips the question and uses the first suggestion.
    Returns the result rows, or [] if you quit.
    """
    path = Path(path)
    photos = get_sorted_photos(path)
    out_dir = Path(output_dir) / "folder" / path.name

    try:
        chosen = choose_parameters(photos[0], out_dir, interactive=interactive,
                                   show=show, ask=ask)
    except EOFError:
        print("\nNo input available (is stdin closed?). Use interactive=False to run without asking.")
        return []
    if chosen is None:
        print("Cancelled, nothing was analysed.")
        return []
    config, tuning = chosen
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "parameters.json").write_text(
        json.dumps(dataclasses.asdict(config), indent=2), encoding="utf-8")
    print(f"\nAnalysing {len(photos)} photos with: {_describe(config)}")

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

    rows = flag_unusual(rows, window=window, z_max=z_max,
                        tuning_failed=tuning["status"] == "fallback")
    flagged = [r for r in rows if r[6]]
    print(f"{len(flagged)} of {len(rows)} photos have a warning")
    for r in flagged:
        print(f"  photo {r[1]} ({r[2]}): {r[6]}")

    csv_path = write_csv(out_dir / "results.csv", RESULTS_HEADER, rows)
    print(f"Data: {csv_path}")
    return rows