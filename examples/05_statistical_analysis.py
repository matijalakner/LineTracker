"""Spacing statistics from a histogram CSV (written by export_pixel_histogram).

Run:  python 05_statistical_analysis.py sample_photo_histogram.csv
"""
import sys

from line_finder import analyze_cleaned_data_from_csv

csv_path = sys.argv[1] if len(sys.argv) > 1 else "sample_photo_histogram.csv"

# Bins further apart than cluster_gap pixels belong to different lines
result = analyze_cleaned_data_from_csv(csv_path, cluster_gap=50)

print(f"Lines found:    {result['total_lines']}")
print(f"Pixel indexes:  {result['pixel_indexes']}")

stats = result["stats"]
if stats:
    print(f"Mean spacing:   {stats['mean_diff']:.2f} px")
    print(f"Std deviation:  {stats['std_diff']:.2f} px")
    print(f"Min / max:      {stats['min_diff']} / {stats['max_diff']} px")
else:
    print("Not enough lines to compute spacing statistics.")
