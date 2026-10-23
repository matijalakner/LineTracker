import argparse
import sys
from pathlib import Path
from types import SimpleNamespace

from .image import analyse_image, annotate_image
from .video import process_video, split_video, DEFAULT_PARAMS

OVERRIDABLE = [
    ("step", int), ("margin", int), ("min_contrast", float), ("min_brightness", float),
    ("max_width", int), ("bg_window", int), ("gap", int),
    ("x_tolerance", int), ("min_strips", int),
]


def main():
    parser = argparse.ArgumentParser(description="Strip Line Finder CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # ---- image -------------------------------------------------------------
    img_parser = subparsers.add_parser("image", help="Analyze single image.")
    img_parser.add_argument("image", help="path to input image")
    img_parser.add_argument("--step", type=int, default=DEFAULT_PARAMS["step"])
    img_parser.add_argument("--margin", type=int, default=DEFAULT_PARAMS["margin"])
    img_parser.add_argument("--min-contrast", type=float, default=DEFAULT_PARAMS["min_contrast"])
    img_parser.add_argument("--output", help="marked image output path")

    # ---- split (slice only) --------------------------------------------------
    split_parser = subparsers.add_parser(
        "split", help="Only slice a video into frame images (no analysis).")
    split_parser.add_argument("video", help="path to input video")
    split_parser.add_argument("--output-dir", default=None,
                              help="folder to create (default: <video name>_frames)")
    split_parser.add_argument("--num-frames", type=int, default=None,
                              help="number of evenly spaced frames (default: every frame)")
    split_parser.add_argument("--format", dest="image_format", choices=["png", "jpg"],
                              default="png", help="frame image format")

    # ---- video (slice, then analyse every frame) --------------------------------
    vid_parser = subparsers.add_parser(
        "video", help="Slice a video into frames, then analyse each frame like a "
                      "single image and write per-frame and whole-video reports.")
    vid_parser.add_argument("video", help="path to input video")
    vid_parser.add_argument("--output-dir", default=None,
                            help="results folder (default: <video name>_analysis)")
    vid_parser.add_argument("--num-frames", type=int, default=None,
                            help="number of evenly spaced frames (default: EVERY frame - "
                                 "needs a lot of disk space for long videos)")
    vid_parser.add_argument("--format", dest="image_format", choices=["png", "jpg"],
                            default="png", help="frame image format")
    vid_parser.add_argument("--bin-size", type=int, default=None,
                            help="histogram bin width (default: automatic)")
    vid_parser.add_argument("--no-auto", action="store_true",
                            help="disable automatic per-frame parameters")
    vid_parser.add_argument("--no-report", action="store_true",
                            help="skip the whole-video report")
    vid_parser.add_argument("--quiet", action="store_true",
                            help="do not print progress")
    for name, typ in OVERRIDABLE:
        vid_parser.add_argument("--" + name.replace("_", "-"), type=typ, default=None,
                                help="fixed value; overrides the automatic one")

    args = parser.parse_args()

    if args.command == "image":
        try:
            cfg = SimpleNamespace(**{**DEFAULT_PARAMS,
                                     "step": args.step,
                                     "margin": args.margin,
                                     "min_contrast": args.min_contrast})
            width, height, lines, tracks = analyse_image(args.image, cfg)
            out = args.output or args.image.rsplit(".", 1)[0] + "_marked.png"
            annotate_image(args.image, lines, tracks, cfg.margin, out, cfg.step, cfg.x_tolerance)
            print(f"Successfully processed image. Marked image saved to: {out}")
        except Exception as e:
            sys.exit(f"Error: {e}")

    elif args.command == "split":
        try:
            frames = split_video(args.video, args.output_dir, args.num_frames,
                                 args.image_format)
            where = frames[0].parent if frames else args.output_dir
            print(f"Saved {len(frames)} frames to '{where}/'.")
        except Exception as e:
            sys.exit(f"Error: {e}")

    elif args.command == "video":
        try:
            overrides = {n: getattr(args, n) for n, _ in OVERRIDABLE
                         if getattr(args, n) is not None}
            results = process_video(
                args.video,
                output_dir=args.output_dir,
                num_frames=args.num_frames,
                image_format=args.image_format,
                bin_size=args.bin_size,
                auto_params=not args.no_auto,
                make_report=not args.no_report,
                verbose=not args.quiet,
                **overrides,
            )
            out_dir = Path(results[0]["frame_path"]).parent.parent
            msg = f"Analysed {len(results)} frames. Results are in '{out_dir}/'."
            if not args.no_report:
                msg += f" Whole-video report: {out_dir}/video_report.txt"
            print(msg)
        except Exception as e:
            sys.exit(f"Error: {e}")


if __name__ == "__main__":
    main()