"""Plot line spacing vs time with a robust polynomial fit.

Needs matplotlib:  pip install -e ".[plots]"
Run:  python 06_plot_spacing_over_time.py video_results/frames_summary.csv MySample
"""
import sys

from line_finder import show_analysis

csv_path = sys.argv[1] if len(sys.argv) > 1 else "video_results/frames_summary.csv"
name = sys.argv[2] if len(sys.argv) > 2 else "spacing"

result = show_analysis(
    csv_path, name,
    edit=True,      # True: drop outliers from the plot; False: mark them in red
    deg=3,          # polynomial degree (needs at least deg + 2 usable frames)
    n_sigma=3.0,    # outlier threshold in robust standard deviations
    # out_dir="plots",   # default: next to the CSV
)
print(f"R2 = {result['r2']:.3f}, RMSE = {result['rmse']:.2f} px, "
      f"outliers = {result['outliers']}/{result['points']}")
print(f"Plot saved to {result['image']}")
