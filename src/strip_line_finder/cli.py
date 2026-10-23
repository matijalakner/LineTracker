import argparse
import sys
from types import SimpleNamespace

from .image import analyse_image, annotate_image
from .video import process_video, DEFAULT_PARAMS
from .video_slicer import slice_video

OVERRIDABLE = [
    ("step", int), ("margin", int), ("min_contrast", float), ("min_brightness", float),
    ("max_width", int), ("bg_window", int), ("gap", int),
    ("x_tolerance", int), ("min_strips", int),
]

def main():
    parser = argparse.ArgumentParser(description="Strip Line Finder CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    img_parser = subparsers.add_parser("image", help="Analyze single image.")
    img_parser.add_argument("image", help="path to input image")
    img_parser.add_argument("--step", type=int, default=DEFAULT_PARAMS["step"])
    img_parser.add_argument("--margin", type=int, default=DEFAULT_PARAMS["margin"])
    img_parser.add_argument("--min-contrast", type=float, default=DEFAULT_PARAMS["min_contrast"])
    img_parser.add_argument("--output", help="marked image output path")

    vid_parser = subparsers.add_parser(
        "video", help="Sample frames, analyze each one and write per-frame and "
                      "whole-video reports.")
    vid_parser.add_argument("video", help="path to input video")
    vid_parser.add_argument("--num-frames", type=int, default=10)
    vid_parser.add_argument("--output-dir", default="video_analysis_output")
    vid_parser.add_argument("--bin-size", type=int, default=None,
                            help="histogram bin width (default: automatic)")
    vid_parser.add_argument("--no-auto", action="store_true",
                            help="disable automatic per-frame parameters")
    vid_parser.add_argument("--no-report", action="store_true",
                            help="skip the whole-video report")
    for name, typ in OVERRIDABLE:
        vid_parser.add_argument("--" + name.replace("_", "-"), type=typ, default=None,
                                help="fixed value; overrides the automatic one")

    slice_parser = subparsers.add_parser("slice", help="Sample video and deposit frames.")
    slice_parser.add_argument("slice", help="path to input video")
    slice_parser.add_argument("--num-frames", type=int, default=100)
    slice_parser.add_argument("--output-dir", type=str, default="output/sliced_video")

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

    elif args.command == "video":
        try:
            overrides = {n: getattr(args, n) for n, _ in OVERRIDABLE
                         if getattr(args, n) is not None}
            results = process_video(
                args.video,
                num_frames=args.num_frames,
                output_dir=args.output_dir,
                bin_size=args.bin_size,
                auto_params=not args.no_auto,
                make_report=not args.no_report,
                **overrides,
            )
            msg = f"Analyzed {len(results)} frames. Per-frame reports are in '{args.output_dir}/'."
            if not args.no_report:
                msg += f" Whole-video report: {args.output_dir}/video_report.txt"
            print(msg)
        except Exception as e:
            sys.exit(f"Error: {e}")

    elif args.command == "slice":
        try:
            results = slice_video(
                args.slice, 
                output_dir=args.output_dir, 
                num_frames=args.num_frames
            )
        except Exception as e:
            sys.exit(f"Error: {e}")


if __name__ == "__main__":
    main()