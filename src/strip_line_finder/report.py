"""Line the photo results up with the LED ramp and plot them.

Inputs
    ramp CSV     written by ``measurement control ramp``  (time_s, cycle, direction, current_A,
                 first line ``time_stamp,<UTC time of the ramp start>``)
    results CSV  written by ``measurement analysis folder`` (time_stamp, photo, mean_spacing_px, ...)

Both files carry UTC times, so every photo can be given the ramp current that
was set when it was taken.
"""
from pathlib import Path

import pandas as pd

from .calibration import COEFF, PX_TO_UM, THETA

COLUMNS = ["time[s]", "current[A]", "mean_spacing_px", "std_spacing_px", "warning", "n_lines"]


def read_ramp(path):
    """-> (t0, DataFrame) of a ramp CSV; t0 is the tz-aware UTC start time."""
    with open(path, encoding="utf-8") as f:
        first = f.readline().strip().split(",", 1)
    if len(first) != 2 or first[0] != "time_stamp":
        raise ValueError(f"{path}: the first line must be 'time_stamp,<UTC time>' "
                         "(is this a ramp file written by this package?)")
    t0 = pd.Timestamp(first[1])
    ramp = pd.read_csv(path, skiprows=1)
    missing = {"time_s", "current_A"} - set(ramp.columns)
    if missing:
        raise ValueError(f"{path}: missing columns {sorted(missing)}")
    return t0, ramp


def acquire(path_ramp, path_results, camera_offset_s=0.0):
    """Merge the ramp and the photo results by time.

    One row per photo taken while the ramp was running (from its start to its
    last row), with the columns time[s] (seconds since the ramp started),
    current[A], mean_spacing_px, std_spacing_px, warning and n_lines. Each photo
    gets the latest ramp current at or before its time (a step is held until
    the next one); where no current is known the last known value is kept.
    camera_offset_s is added to the photo times to correct a camera clock that
    is off.
    """
    t0, ramp = read_ramp(path_ramp)
    photos = pd.read_csv(path_results)
    photo_utc = pd.to_datetime(photos["time_stamp"], utc=True) \
        + pd.to_timedelta(camera_offset_s, unit="s")
    photos["time[s]"] = (photo_utc - t0).dt.total_seconds()
    photos = photos.sort_values("time[s]")

    ramp_cur = ramp[["time_s", "current_A"]].rename(
        columns={"time_s": "time[s]", "current_A": "current[A]"})
    table = pd.merge_asof(photos, ramp_cur, on="time[s]", direction="backward")
    table["current[A]"] = table["current[A]"].ffill()

    table = table[(table["time[s]"] >= 0) & (table["time[s]"] <= ramp["time_s"].max())].copy()
    table["warning"] = table["warning"].fillna("")
    return table[COLUMNS].reset_index(drop=True)


def plot_report(table, out_png, name="", objective="20x", theta="0.8wt", px_to_um=PX_TO_UM):
    """Average distance and pitch against current, intensity and time (one figure).

    Photos with a warning are left out of the plots. Returns the number of photos plotted.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    if objective not in COEFF:
        raise ValueError(f"unknown objective '{objective}'; choose from {sorted(COEFF)}")
    if theta not in THETA:
        raise ValueError(f"unknown sample '{theta}'; choose from {sorted(THETA)}")

    keep = (table["warning"] == "").to_numpy()
    if not keep.any():
        raise ValueError("every photo has a warning; nothing to plot.")
    current = table["current[A]"].to_numpy()[keep]
    time = table["time[s]"].to_numpy()[keep]
    distance = table["mean_spacing_px"].to_numpy(dtype=float)[keep] * px_to_um   # um
    intensity = current * COEFF[objective]                                       # W/um^2
    pitch = 2 * THETA[theta] * distance                                          # um

    l_dist, l_pitch = "average distance [µm]", "pitch [µm]"
    l_int, l_cur, l_time = "intensity [W/µm²]", "current [A]", "time [s]"
    fig, axes = plt.subplots(2, 3, figsize=(15, 8), sharey="row")
    panels = [
        (axes[0, 0], current, distance, l_cur, l_dist),
        (axes[0, 1], intensity, distance, l_int, None),
        (axes[0, 2], time, distance, l_time, None),
        (axes[1, 1], intensity, pitch, l_int, l_pitch),
        (axes[1, 2], time, pitch, l_time, None),
    ]
    for ax, x, y, xlabel, ylabel in panels:
        sc = ax.scatter(x, y, c=time, s=14, cmap="viridis")
        ax.set_xlabel(xlabel)
        if ylabel:
            ax.set_ylabel(ylabel)
        ax.grid(alpha=0.3)
        ax.tick_params(labelleft=True)
    axes[1, 0].axis("off")                      # there is no pitch vs current plot
    fig.colorbar(sc, ax=axes, label="time [s]", shrink=0.8)
    fig.suptitle(f"{name}: average distance and pitch ({objective}, {theta})")
    out_png = Path(out_png)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return int(keep.sum())


def plot_timeline(path_ramp, path_results, out_png, name="", objective="20x", theta="0.8wt",
                  px_to_um=PX_TO_UM, camera_offset_s=0.0, same_start=True, stretch=True):
    """Intensity of the ramp and pitch of the photos on one common time axis.

    same_start=True (default): both series are shifted to start at t = 0, the ramp
    at its first row and the photos at the first photo. With stretch=True (default)
    the shorter series is also stretched in time to the length of the longer one,
    so both span the whole axis (the time axis is then no longer real seconds for
    the stretched series). same_start=False keeps the real clock: the axis runs
    from the earlier of the two starts to the later of the two ends, t = 0 being
    that earlier start. All photos are used, also those outside the ramp, except
    the ones with a warning. Returns (start, end) as UTC timestamps of the axis.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    if objective not in COEFF:
        raise ValueError(f"unknown objective '{objective}'; choose from {sorted(COEFF)}")
    if theta not in THETA:
        raise ValueError(f"unknown sample '{theta}'; choose from {sorted(THETA)}")
    t0_ramp, ramp = read_ramp(path_ramp)
    photos = pd.read_csv(path_results)
    photo_utc = pd.to_datetime(photos["time_stamp"], utc=True) \
        + pd.to_timedelta(camera_offset_s, unit="s")

    ramp_start, ramp_end = t0_ramp, t0_ramp + pd.to_timedelta(ramp["time_s"].max(), unit="s")
    if same_start:
        start, end = min(ramp_start, photo_utc.min()), None
    else:
        start, end = min(ramp_start, photo_utc.min()), max(ramp_end, photo_utc.max())

    seconds = lambda t: (t - start).total_seconds() if isinstance(t, pd.Timestamp) \
        else (t - start).dt.total_seconds().to_numpy()
    t_ramp = ramp["time_s"].to_numpy() if same_start else seconds(t0_ramp) + ramp["time_s"].to_numpy()
    intensity = ramp["current_A"].to_numpy() * COEFF[objective]                 # W/um^2

    ok = (photos["warning"].fillna("") == "").to_numpy()
    t_photo = seconds(photo_utc)[ok]
    if same_start:
        t_photo = t_photo - seconds(photo_utc).min()
        end_s = max(t_ramp.max(), t_photo_all := seconds(photo_utc).max() - seconds(photo_utc).min())
        if stretch:                                   # shorter series -> same length as the longer
            if t_ramp.max() > 0:
                t_ramp = t_ramp * (end_s / t_ramp.max())
            if t_photo_all > 0:
                t_photo = t_photo * (end_s / t_photo_all)
    else:
        end_s = seconds(end)
    pitch = 2 * THETA[theta] * photos["mean_spacing_px"].to_numpy(dtype=float)[ok] * px_to_um

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 7), sharex=True)
    ax1.step(t_ramp, intensity, where="post", color="tab:orange")
    ax1.set_ylabel("power (intensity) [W/µm²]")
    ax2.scatter(t_photo, pitch, s=10, color="tab:blue")
    ax2.set_ylabel("pitch [µm]")
    ax2.set_xlabel(("time since the start of each series [s]" + (" (shorter series stretched)" if stretch else ""))
                   if same_start
                   else f"time [s] since {start:%Y-%m-%d %H:%M:%S} UTC")
    for ax in (ax1, ax2):
        ax.grid(alpha=0.3)
    ax1.set_xlim(0, end_s)
    fig.suptitle(f"{name}: power and pitch against time ({objective}, {theta})")
    fig.tight_layout()
    out_png = Path(out_png)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=150)
    plt.close(fig)
    return start, end_s


def find_ramp_csv(ramp=None, output_dir="output"):
    """The given ramp CSV, or the newest <output_dir>/ramp/ramp_*.csv."""
    if ramp:
        p = Path(ramp)
        if not p.exists():
            p = Path(output_dir) / "ramp" / p.name
        if not p.exists():
            raise FileNotFoundError(f"Ramp file not found: {ramp}")
        return p
    files = sorted((Path(output_dir) / "ramp").glob("ramp_*.csv"))
    if not files:
        raise FileNotFoundError(f"No ramp_*.csv in {Path(output_dir) / 'ramp'}. "
                                "Run 'control ramp' first or pass --ramp.")
    return files[-1]          # names contain the UTC time, so the last is the newest


def find_results_csv(results, output_dir="output"):
    """A results CSV, or the name of a photo folder analysed with 'analysis folder'."""
    p = Path(results)
    if p.is_file():
        return p
    q = Path(output_dir) / "folder" / results / "results.csv"
    if q.exists():
        return q
    raise FileNotFoundError(f"No results found for '{results}' (tried {p} and {q}). "
                            "Run 'analysis folder' first.")


def main_report(name, ramp=None, results=None, output_dir="output", objective="20x",
                theta="0.8wt", px_to_um=PX_TO_UM, camera_offset_s=0.0):
    """Align, save and plot. Writes <output_dir>/report/<name>/data.csv, plots.png and timeline.png.

    ``results`` defaults to ``name`` (the folder name used with 'analysis folder').
    Returns a dict with the table and the written paths.
    """
    ramp_path = find_ramp_csv(ramp, output_dir)
    results_path = find_results_csv(results or name, output_dir)
    table = acquire(ramp_path, results_path, camera_offset_s)
    if table.empty:
        raise ValueError("No photo was taken while the ramp was running. Check the "
                         "files, or the camera clock (--camera-offset).")
    out_dir = Path(output_dir) / "report" / name
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / "data.csv"
    table.to_csv(csv_path, index=False)
    png_path = out_dir / "plots.png"
    n_plotted = plot_report(table, png_path, name, objective, theta, px_to_um)
    timeline_path = out_dir / "timeline.png"
    plot_timeline(ramp_path, results_path, timeline_path, name, objective, theta, px_to_um,
                  camera_offset_s)
    return {"timeline_path": str(timeline_path), "table": table, "ramp_path": str(ramp_path), "results_path": str(results_path),
            "csv_path": str(csv_path), "plot_path": str(png_path),
            "photos": len(table), "plotted": n_plotted}
