"""Analyse a video: a frame every N seconds, lines in every frame.

Run:  python 03_video_analysis.py input_footage.mp4

Output:
    output/video/frames/<name>/frame_XXXXX.png         raw frames
    output/video/<name>/frame_XXXXX_marked.png         marked frames
    output/video/<name>/lines.csv                      time, frame, lines
"""
import sys

from line_finder import DetectionConfig, process_video

video_path = sys.argv[1] if len(sys.argv) > 1 else "input_footage.mp4"

rows = process_video(video_path, output_dir="output", interval=5.0,
                     config=DetectionConfig())

for r in rows:
    print(f"t = {r['time']:>7.2f} s  frame {r['frame']:>6}: {len(r['lines'])} lines")
