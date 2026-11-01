import pandas as pd

def read_ramp(path):
    """-> (t0, DataFrame[time_s, cycle, direction, current_A, time_utc])"""
    with open(path, encoding="utf-8") as f:
        t0 = pd.Timestamp(f.readline().strip().split(",", 1)[1])      # tz-aware UTC
    ramp = pd.read_csv(path, skiprows=1)
    ramp["time_utc"] = (t0 + pd.to_timedelta(ramp["time_s"], unit="s")).astype("datetime64[ns, UTC]")
    return t0, ramp

def align(ramp_path, results_path, camera_offset_s=0.0, max_gap_s=None):
    t0, ramp = read_ramp(ramp_path)
    photos = pd.read_csv(results_path)
    photos["time_utc"] = (pd.to_datetime(photos["time_stamp"], utc=True) + pd.to_timedelta(camera_offset_s, unit="s")).astype("datetime64[ns, UTC]")
    photos["time_s"] = (photos["time_utc"] - t0).dt.total_seconds()      # seconds since ramp start
    # a step is held from its row until the next one -> take the latest ramp row at or before the photo
    out = pd.merge_asof(photos.sort_values("time_utc"),
                        ramp[["time_utc", "cycle", "direction", "current_A"]].rename(columns={"time_utc": "step_start_utc"}),
                        left_on="time_utc", right_on="step_start_utc", direction="backward")
    ramp_end = ramp["time_s"].iloc[-1] + ramp["time_s"].diff().median()   # end of the last step
    out.loc[(out["time_s"] < 0) | (out["time_s"] >= ramp_end), ["cycle", "direction", "current_A"]] = pd.NA
    out["in_ramp"] = out["current_A"].notna()
    if max_gap_s is not None:
        out.loc[(out["time_utc"] - out["step_start_utc"]).dt.total_seconds() > max_gap_s, "current_A"] = pd.NA
    return out

if __name__ == "__main__":
    import sys
    a = align(sys.argv[1], sys.argv[2])
    a.to_csv("aligned.csv", index=False)
    print(a[["time_stamp","photo","time_s","current_A","direction","n_lines","mean_spacing_px","in_ramp"]].iloc[[0,1,2,100,200,300,400,479]].to_string())
    print("in ramp:", int(a.in_ramp.sum()), "of", len(a), "| first/last in-ramp photo:", a[a.in_ramp].photo.min(), a[a.in_ramp].photo.max())