from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from align import read_ramp

COEFF = {
    "5x": 4.356367310904955e-08,
    "10x": 9.257685271674028e-08,
    "20x": 1.2076428929397266e-07,
    "40x": 8.824088200840021e-08
}

THETA = {
    "0.2wt": 0.011327835,
    "0.4wt": 0.011372214,
    "0.6wt": 0.0115,
    "0.8wt": 0.01147779,
    "1.0wt": 0.00198943,
    "1.5wt": 0.00280895
}

BASE = "output/folder"
OUT_DIR = Path("output/pitch")

PX_TO_UM = 0.1813   # micrometers per pixel

COLUMNS = ["time[s]", "current[A]", "mean_spacing_px", "std_spacing_px", "warning", "n_lines"]


def acquire(path_ramp, path_img, camera_offset_s=0.0):
    """Merge the ramp file and the photo results by time.

    Returns one row per photo taken while the ramp was running (from its start
    to its last row) with the columns time[s] (seconds since the ramp started),
    current[A], mean_spacing_px, std_spacing_px, warning and n_lines.
    Each photo gets the latest ramp current at or before its time; where no
    current is known the last known value is kept.
    camera_offset_s corrects a camera clock that is off (added to the photo times).
    """
    t0, ramp = read_ramp(path_ramp)
    photos = pd.read_csv(path_img)

    photo_utc = pd.to_datetime(photos["time_stamp"], utc=True) + pd.to_timedelta(camera_offset_s, unit="s")
    photos["time[s]"] = (photo_utc - t0).dt.total_seconds()
    photos = photos.sort_values("time[s]")

    # current at each photo time = last ramp row at or before it (the step is held)
    ramp_cur = ramp[["time_s", "current_A"]].rename(columns={"time_s": "time[s]", "current_A": "current[A]"})
    table = pd.merge_asof(photos, ramp_cur, on="time[s]", direction="backward")
    table["current[A]"] = table["current[A]"].ffill()           # keep the last known value

    # only the part when the ramp was running: start .. last ramp row
    table = table[(table["time[s]"] >= 0) & (table["time[s]"] <= ramp["time_s"].max())]
    table["warning"] = table["warning"].fillna("")
    return table[COLUMNS].reset_index(drop=True)


if __name__ == "__main__":
    path_img = Path("output/folder/results.csv")
    path_lamp = Path("output/ramp/ramp_20261030T171836Z.csv")
    df = acquire(path_lamp, path_img)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_DIR / "experimental_data.csv", index=False)

    current = df["current[A]"].to_numpy()
    time = df["time[s]"].to_numpy()
    distance = df["mean_spacing_px"].to_numpy() * PX_TO_UM          # micrometers
    std_dist = df["std_spacing_px"].to_numpy() * PX_TO_UM
    intensity = current * COEFF["20x"]                              # W/um^2
    pitch = 2 * THETA["0.8wt"] * distance                           # um
    flagged = (df["warning"] != "").to_numpy()     # photos the line finder was unsure about

    L_DIST, L_PITCH = "average distance [µm]", "pitch [µm]"
    L_INT, L_CUR, L_TIME = "intensity [W/µm²]", "current [A]", "time [s]"
    keep = ~flagged                                  # leave out photos with a warning

    # columns: current, intensity, time | row 1: average distance, row 2: pitch
    fig, axes = plt.subplots(2, 3, figsize=(15, 8), sharey="row")
    panels = [
        (axes[0, 0], current, distance, L_CUR, L_DIST),
        (axes[0, 1], intensity, distance, L_INT, None),
        (axes[0, 2], time, distance, L_TIME, None),
        (axes[1, 0], current, pitch, L_CUR, L_PITCH),
        (axes[1, 1], intensity, pitch, L_INT, None),
        (axes[1, 2], time, pitch, L_TIME, None),
    ]
    for ax, x, y, xlabel, ylabel in panels:
        sc = ax.scatter(x[keep], y[keep], c=time[keep], s=14, cmap="viridis")
        ax.set_xlabel(xlabel)
        if ylabel:
            ax.set_ylabel(ylabel)
        ax.grid(alpha=0.3)
        ax.tick_params(labelleft=True)
    fig.colorbar(sc, ax=axes, label="time [s]", shrink=0.8)
    fig.suptitle("average distance and pitch")
    fig.savefig(OUT_DIR / f"plots.png", dpi=150, bbox_inches="tight")
    plt.show()