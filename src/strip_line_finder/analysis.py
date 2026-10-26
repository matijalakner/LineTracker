from pathlib import Path

import numpy as np
import pandas as pd


def analyze_cleaned_data_from_csv(csv_path, cluster_gap=50):
    """Analyzes CSV outputs using statistical filters.

    cluster_gap: histogram bins whose start positions are further apart than
    this many pixels are treated as different lines (process_video derives it
    from the frame's x_tolerance).
    """
    df = pd.read_csv(csv_path)
    if df.shape[1] < 3:
        raise ValueError("CSV must have at least 3 columns: start, end, count")
    data = df.iloc[:, :3].to_numpy()
    data = data[data[:, 2] != 0]

    if data.shape[0] == 0:
        return {"total_lines": 0, "pixel_indexes": [], "stats": {}}

    clean_data = []
    starts, values = [], []
    previous_start = None  # None, not 0: a line in the first bin is valid

    for start, _stop, num in data:
        if previous_start is not None and start - previous_start > cluster_gap:
            clean_data.append(int(starts[int(np.argmax(values))]))
            starts, values = [], []
        starts.append(start)
        values.append(num)
        previous_start = start

    if starts:
        clean_data.append(int(starts[int(np.argmax(values))]))

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
        "stats": stats,
    }


def robust_polyfit(x, y, deg, n_sigma=3.0, n_iter=10):
    """Polynomial fit with iterative outlier rejection (median/MAD based).

    Returns (coefficients, inlier_mask)."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    if len(x) < deg + 2:
        raise ValueError(f"need at least {deg + 2} points for a degree-{deg} fit")
    mask = np.ones(len(y), dtype=bool)
    coef = np.polyfit(x, y, deg)
    for _ in range(n_iter):
        resid = y - np.polyval(coef, x)
        sigma = 1.4826 * np.median(np.abs(resid - np.median(resid)))
        if sigma == 0:  # (near-)perfect fit: nothing to reject
            break
        new_mask = np.abs(resid) < n_sigma * sigma
        if new_mask.sum() < deg + 2:  # would leave too few points to fit
            break
        if np.array_equal(new_mask, mask):
            break
        mask = new_mask
        coef = np.polyfit(x[mask], y[mask], deg)
    return coef, mask


def show_analysis(path, name, edit=True, deg=3, n_sigma=3.0, out_dir=None):
    """Plot mean_spacing (+ std_spacing as error bars) vs time with a
    robust polynomial fit, from a frames_summary.csv.

    edit=True  -> points rejected as outliers by the fit are removed before
                  plotting.
    edit=False -> all points are kept and outliers are only marked in red.
    out_dir    -> where to save ``<name>.png`` (default: next to the CSV).

    Returns a dict with the fit results (and the saved image path).
    """
    import matplotlib.pyplot as plt  # optional dependency, only needed here

    path = Path(path)
    data = pd.read_csv(path)
    # frames without >= 2 tracks have empty spacing values -> drop them
    data = data.dropna(subset=["timestamp_sec", "mean_spacing", "std_spacing"])
    time_s = data["timestamp_sec"].to_numpy(dtype=float)
    spacing = data["mean_spacing"].to_numpy(dtype=float)
    deltas = data["std_spacing"].to_numpy(dtype=float)
    if len(time_s) < deg + 2:
        raise ValueError(f"{name}: only {len(time_s)} usable frames, "
                         f"need at least {deg + 2} for degree {deg}")

    t0, ts = time_s.mean(), time_s.std()
    if ts == 0:
        raise ValueError(f"{name}: all timestamps are identical")
    z = (time_s - t0) / ts
    coef, inlier = robust_polyfit(z, spacing, deg, n_sigma)

    resid = spacing - np.polyval(coef, z)
    var = spacing[inlier].var()
    r2 = 1 - resid[inlier].var() / var if var > 0 else float("nan")
    rmse = resid[inlier].std()
    n_out = int(np.sum(~inlier))
    print(f"{name}: degree={deg} R2={r2:.3f} RMSE={rmse:.2f}px "
          f"outliers={n_out}/{len(inlier)}")

    if edit:  # drop the outliers
        time_s, spacing, deltas = time_s[inlier], spacing[inlier], deltas[inlier]
        inlier = np.ones(len(time_s), dtype=bool)

    t_fine = np.linspace(time_s.min(), time_s.max(), 400)
    fit_curve = np.polyval(coef, (t_fine - t0) / ts)

    fig, ax = plt.subplots()
    ax.errorbar(time_s[inlier], spacing[inlier], yerr=deltas[inlier], fmt="o",
                capsize=4, label="Spacing of the lines with the error")
    if not inlier.all():
        ax.errorbar(time_s[~inlier], spacing[~inlier], yerr=deltas[~inlier],
                    fmt="o", capsize=4, color="red", alpha=0.6,
                    label="Outliers (excluded from fit)")
    ax.plot(t_fine, fit_curve, "k", lw=2,
            label=f"Robust polynomial fit (deg {deg}, R²={r2:.2f})")
    ax.set_xlabel("time (s)")
    ax.set_ylabel("spacing (px)")
    ax.set_title(name)
    ax.legend()
    ax.grid()

    out_dir = Path(out_dir) if out_dir else path.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    out_png = out_dir / f"{name}.png"
    fig.savefig(out_png)
    plt.close(fig)
    return {"name": name, "degree": deg, "r2": float(r2), "rmse": float(rmse),
            "outliers": n_out, "points": int(len(inlier)), "image": str(out_png)}


if __name__ == "__main__":
    for _name in ("EHC", "A1", "A3"):
        _csv = Path("input_output") / _name / "CJG544_R_10X_0000_analysis" / "frames_summary.csv"
        if _csv.exists():
            show_analysis(_csv, _name, True)
        else:
            print(f"Skipping {_name}: {_csv} not found")