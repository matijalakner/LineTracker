"""Only slice a video into frame images (no analysis).

Run:  python 03_split_video.py input_footage.mp4
"""
import sys

from line_finder import split_video

video_path = sys.argv[1] if len(sys.argv) > 1 else "input_footage.mp4"

# num_frames=None saves EVERY frame (large for long videos);
# an integer saves that many evenly spaced frames.
frames = split_video(video_path, output_dir="video_frames",
                     num_frames=20, image_format="png")
print(f"Saved {len(frames)} frames, first: {frames[0] if frames else '-'}")
