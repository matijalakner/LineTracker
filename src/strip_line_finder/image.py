import csv
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from ._core import get_strip, find_lines_in_profile, link_vertical_lines, Line

def analyse_image(path, args):
    """Loads an image file and processes line detection tracks[cite: 2, 3]."""
    img = np.asarray(Image.open(path).convert("RGB"), dtype=np.float32)
    height, width = img.shape[:2]
    lines = []
    for row in range(0, height, args.step):
        strip = get_strip(img, row, args.margin)
        profile = strip.mean(axis=0)
        for start, end, center, pol, contrast in find_lines_in_profile(
                profile, args.min_contrast, args.max_width, args.min_width,
                args.bg_window, args.gap, args.min_brightness):
            lines.append(Line(row, start, end, center, end - start + 1,
                              pol, round(contrast, 1)))
    tracks = link_vertical_lines(lines, args.x_tolerance, args.min_strips)
    kept = [l for l in lines if l.track_id > 0] if not args.keep_all else lines
    return width, height, kept, tracks

def analyse_image_array(img_np, step=100, margin=3, min_contrast=7.0,
                        min_width=1, max_width=14, bg_window=41,
                        gap=2, min_brightness=25.0, x_tolerance=20,
                        min_strips=3, keep_all=False):
    """Processes a NumPy image array directly (useful for video frames)."""
    height, width = img_np.shape[:2]
    lines = []
    for row in range(0, height, step):
        strip = get_strip(img_np, row, margin)
        profile = strip.mean(axis=0)
        for start, end, center, pol, contrast in find_lines_in_profile(
                profile, min_contrast, max_width, min_width,
                bg_window, gap, min_brightness):
            lines.append(Line(row, start, end, center, end - start + 1,
                              pol, round(contrast, 1)))
    tracks = link_vertical_lines(lines, x_tolerance, min_strips)
    kept = [l for l in lines if l.track_id > 0] if not keep_all else lines
    return width, height, kept, tracks

def annotate_image(path, lines, tracks, margin, out_path, step, x_tolerance):
    """Annotates detected lines onto a copy of the image[cite: 2, 3]."""
    img = Image.open(path).convert("RGB")
    w, h = img.size
    draw = ImageDraw.Draw(img)
    red = (255, 0, 0)

    for members in tracks:
        ms = sorted(members, key=lambda m: m.row)
        for a, b in zip(ms, ms[1:]):
            if (b.row - a.row <= 2 * step
                    and abs(b.center_px - a.center_px) <= x_tolerance):
                draw.line([(a.center_px, a.row), (b.center_px, b.row)],
                          fill=red, width=3)

    px = img.load()
    for l in lines:
        top, bottom = max(0, l.row - margin), min(h - 1, l.row + margin)
        for y in range(top, bottom + 1):
            for x in range(l.start_px, l.end_px + 1):
                px[x, y] = red
        draw.rectangle([max(0, l.start_px - 4), max(0, top - 4),
                        min(w - 1, l.end_px + 4), min(h - 1, bottom + 4)],
                        outline=red, width=2)
    img.save(out_path)

def export_pixel_histogram(image_path, lines, bin_size, out_path):
    """Exports pixel distribution histograms[cite: 3]."""
    if bin_size < 1:
        raise ValueError("--bin-size must be at least 1")
    image_width = Image.open(image_path).size[0]
    starts = list(range(0, image_width, bin_size))
    counts = [0] * len(starts)
    for line in lines:
        idx = line.center_px // bin_size
        if 0 <= idx < len(counts):
            counts[idx] += 1

    csv_path = out_path.rsplit(".", 1)[0] + ".csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["pixel_interval_start", "pixel_interval_end", "number_of_points"])
        for start, count in zip(starts, counts):
            writer.writerow([start, min(start + bin_size, image_width) - 1, count])

    plot_w, plot_h = 1200, 650
    left, right, top, bottom = 75, 25, 40, 70
    chart_w, chart_h = plot_w - left - right, plot_h - top - bottom
    canvas = Image.new("RGB", (plot_w, plot_h), "white")
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default()
    ymax = max(1, max(counts, default=0))
    draw.line((left, top, left, top + chart_h), fill="black", width=2)
    draw.line((left, top + chart_h, left + chart_w, top + chart_h), fill="black", width=2)
    for value in range(ymax + 1):
        y = top + chart_h - value / ymax * chart_h
        draw.line((left, y, left + chart_w, y), fill=(225, 225, 225))
        if value == 0 or value == ymax or ymax <= 10:
            draw.text((left - 25, y - 5), str(value), fill="black", font=font)
    bar_w = chart_w / max(1, len(counts))
    for i, count in enumerate(counts):
        x0 = left + i * bar_w
        x1 = left + (i + 1) * bar_w - 1
        y0 = top + chart_h - count / ymax * chart_h
        draw.rectangle((int(x0), int(y0), max(int(x0), int(x1)), top + chart_h),
                       fill=(70, 130, 180))
    draw.text((left, 12), f"Number of detected points per {bin_size}-px interval", fill="black", font=font)
    label_every = max(1, int(np.ceil(len(starts) / 12)))
    for i in range(0, len(starts), label_every):
        draw.text((int(left + i * bar_w), top + chart_h + 8), str(starts[i]), fill="black", font=font)
    canvas.save(out_path)