import numpy as np
import pandas as pd

def analyze_cleaned_data_from_csv(csv_path):
    """Analyzes CSV outputs using statistical filters[cite: 1]."""
    df = pd.read_csv(csv_path)
    data = df.to_numpy()

    if data.shape[0] == 0:
        return {"total_lines": 0, "clean_data": [], "stats": {}}

    cleaned_data = data[np.where(data[:, 2] != 0)]

    previous_start = 0
    values = []
    starts = []
    clean_data = []

    for [start, stop, num] in cleaned_data:
        if previous_start == 0:
            previous_start = start

        condition = (start - previous_start > 50) and values and starts

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