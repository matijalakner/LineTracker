"""Analyse a video: slice it, analyse every frame, write the reports.

Run:  python 04_video_analysis.py input_footage.mp4

Output folder layout:
    video_results/frames/                 sliced frames
    video_results/analysis/frame_XXXXX/   marked image, histogram, frame report
    video_results/video_report.txt/.json  whole-video report
    video_results/frames_summary.csv      one row per frame (used by example 06)
    video_results/tracks.csv              one row per detected track
"""
import sys

from line_finder import process_video

video_path = sys.argv[1] if len(sys.argv) > 1 else "input_footage.mp4"

results = process_video(
    video_path,
    output_dir="video_results",
    num_frames=12,       # None = every frame
    auto_params=True,    # measure parameters per frame; False = fixed defaults
    # Anything below overrides the automatic value:
    # min_contrast=6.5,
    # x_tolerance=20,
)

for frame in results:
    spacing = frame["statistics"]["stats"].get("mean_diff")
    spacing_txt = f"{spacing:.1f} px" if spacing is not None else "-"
    print(f"frame {frame['frame_index']:>5} ({frame['timestamp_sec']:>6.2f} s): "
          f"{len(frame['tracks'])} lines, mean spacing {spacing_txt}")

print("\nWhole-video report: video_results/video_report.txt")
