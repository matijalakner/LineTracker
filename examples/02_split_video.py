"""Only take frames from a video (no analysis): one frame every N seconds.

Run:  python 02_split_video.py input_footage.mp4
"""
import sys

from line_finder import split_video

video_path = sys.argv[1] if len(sys.argv) > 1 else "input_footage.mp4"

frames = split_video(video_path, "video_frames", interval=5.0)   # every 5 s
print(f"Saved {len(frames)} frames, first: {frames[0][2] if frames else '-'}")
