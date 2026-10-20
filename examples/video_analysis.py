from strip_line_finder import process_video

# Slice a video into 12 uniform frames and save annotated visuals in a folder
results = process_video(
    video_path="input_footage.mp4",
    num_frames=12,
    output_dir="./analyzed_video_frames",
    step=100,           # Sample every 100th row
    min_contrast=6.5,   # Adjust contrast sensitivity
    x_tolerance=20
)

# Inspect the results per frame
for frame_data in results:
    f_idx = frame_data["frame_index"]
    timestamp = frame_data["timestamp_sec"]
    num_tracks = len(frame_data["tracks"])
    
    print(f"Frame {f_idx} (at {timestamp}s): Found {num_tracks} vertical lines.")