from strip_line_finder.image import analyse_image, annotate_image, export_pixel_histogram

# Create a lightweight configuration class/object for parameters
class AnalysisConfig:
    step = 100
    margin = 3
    min_contrast = 7.0
    min_width = 1
    max_width = 14
    bg_window = 41
    gap = 2
    min_brightness = 25.0
    x_tolerance = 20
    min_strips = 3
    keep_all = False

config = AnalysisConfig()
image_path = "sample_photo.jpg"

# 1. Analyze the image
width, height, lines, tracks = analyse_image(image_path, config)
print(f"Detected {len(tracks)} vertical line tracks across a {width}x{height} image.")

# 2. Annotate and save the marked image
output_image_path = "sample_photo_marked.png"
annotate_image(image_path, lines, tracks, config.margin, output_image_path, config.step, config.x_tolerance)

# 3. Export pixel distribution histogram and CSV data
export_pixel_histogram(image_path, lines, bin_size=10, out_path="sample_photo_histogram.png")