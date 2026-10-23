from strip_line_finder import process_video

# Sample 12 uniform frames. Each one goes through the full image pipeline
# (detection, annotation, histogram + CSV, statistics) and gets its own
# text report inside ./analyzed_video_frames/frame_XXXXX/
results = process_video(
    video_path="input_footage.mp4",
    num_frames=100,
    output_dir="./analyzed_video_frames",
    bin_size=10,        # histogram bin width in pixels
    step=100,           # Sample every 100th row
    min_contrast=8,   # Adjust contrast sensitivity
    x_tolerance=10,
)

for frame_data in results:
    print(f"Frame {frame_data['frame_index']} (at {frame_data['timestamp_sec']}s): "
          f"{len(frame_data['tracks'])} vertical lines -> {frame_data['report_path']}")

print("Overall summary: ./analyzed_video_frames/summary.txt")