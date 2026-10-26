from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

def analyze_cleaned_data_from_csv(csv_path, cluster_gap=50):
    """Analyzes CSV outputs using statistical filters.

    cluster_gap: histogram bins whose start positions are further apart than
    this many pixels are treated as different lines (was a fixed 50 before;
    process_video now derives it from the frame's x_tolerance).
    """
    df = pd.read_csv(csv_path)
    data = df.to_numpy()

    if data.shape[0] == 0:
        return {"total_lines": 0, "pixel_indexes": [], "clean_data": [], "stats": {}}

    cleaned_data = data[np.where(data[:, 2] != 0)]

    previous_start = 0
    values = []
    starts = []
    clean_data = []

    for [start, stop, num] in cleaned_data:
        if previous_start == 0:
            previous_start = start

        condition = (start - previous_start > cluster_gap) and values and starts

        if condition:
            clean_data.append(starts[np.argmax(np.array(values))])
            starts.clear()
            values.clear()

        starts.append(start)
        values.append(num)
        previous_start = start

    if values and starts:
        clean_data.append(starts[np.argmax(np.array(values))])

    clean_data = sorted(clean_data)
    differences = np.diff(clean_data)
    
    
    stats = {}
    if len(differences) > 0:
        stats = {
            "mean_diff": float(np.mean(differences)),
            "std_diff": float(np.std(differences)),
            "min_diff": int(np.min(differences)),
            "max_diff": int(np.max(differences)),
        }

    return {
        "total_lines": len(clean_data),
        "pixel_indexes": clean_data,
        "stats": stats
    }

def robust_polyfit(x, y, deg, n_sigma=3.0, n_iter=10):
    """Polynomial fit with iterative outlier rejection (median/MAD based).

    Returns (coefficients, inlier_mask)."""
    mask = np.ones(len(y), dtype=bool)
    for _ in range(n_iter):
        coef = np.polyfit(x[mask], y[mask], deg)
        resid = y - np.polyval(coef, x)
        sigma = 1.4826 * np.median(np.abs(resid - np.median(resid)))
        new_mask = np.abs(resid) < n_sigma * sigma
        if np.array_equal(new_mask, mask):
            break
        mask = new_mask
    return coef, mask


def show_analysis(path, name, edit=True, deg=3, n_sigma=3.0):
    """Plot mean_spacing (+ std_spacing as error bars) vs time with a
    robust polynomial fit.

    edit=True  -> points rejected as outliers by the fit are removed from the
                  data before plotting (replaces the old moving-average filter).
    edit=False -> all points are kept and outliers are only marked in red.
    """
    data = pd.read_csv(Path(path))
    time = data["timestamp_sec"].to_numpy(dtype=float)
    spacing = data["mean_spacing"].to_numpy(dtype=float)
    deltas = data["std_spacing"].to_numpy(dtype=float)

    z = (time - time.mean()) / time.std()
    coef, inlier = robust_polyfit(z, spacing, deg, n_sigma)

    resid = spacing - np.polyval(coef, z)
    r2 = 1 - resid[inlier].var() / spacing[inlier].var()
    rmse = resid[inlier].std()
    print(f"{name}: degree={deg} R2={r2:.3f} RMSE={rmse:.2f}px "
          f"outliers={np.sum(~inlier)}/{len(inlier)}")

    if edit:  # drop the outliers
        time, spacing, deltas, z = time[inlier], spacing[inlier], deltas[inlier], z[inlier]
        inlier = np.ones(len(time), dtype=bool)

    t_fine = np.linspace(time.min(), time.max(), 400)
    fit_curve = np.polyval(coef, (t_fine - data["timestamp_sec"].mean())
                           / data["timestamp_sec"].std())

    fig, ax = plt.subplots()
    ax.errorbar(time[inlier], spacing[inlier], yerr=deltas[inlier], fmt="o",
                capsize=4, label="Spacing of the lines with the error.")
    if not inlier.all():
        ax.errorbar(time[~inlier], spacing[~inlier], yerr=deltas[~inlier],
                    fmt="o", capsize=4, color="red", alpha=0.6,
                    label="Outliers (excluded from fit).")
    ax.plot(t_fine, fit_curve, "k", lw=2,
            label=f"Robust polynomial fit (deg {deg}, R²={r2:.2f}).")

    ax.set_xlabel("time (s)")
    ax.set_ylabel("spacing (px)")
    ax.set_title(name)
    ax.legend()
    ax.grid()
    
    out_dir = "input_output/" + name + "/CJG544_R_10X_0000_analysis"
    
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    fig.savefig(Path(out_dir) / f"{name}.png")
    plt.close(fig)


if __name__ == "__main__":
    show_analysis("input_output/EHC/CJG544_R_10X_0000_analysis/frames_summary.csv", "EHC", True)
    show_analysis("input_output/A1/CJG544_R_10X_0000_analysis/frames_summary.csv", "A1", True)
    show_analysis("input_output/A3/CJG544_R_10X_0000_analysis/frames_summary.csv", "A3", True)
    
    
    
    
    
