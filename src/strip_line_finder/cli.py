import argparse
import sys
from types import SimpleNamespace

from .image import analyse_image, annotate_image
from .video import process_video, DEFAULT_PARAMS


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
        "video", help="Sample frames, analyze each one and write a text report per frame.")
    vid_parser.add_argument("video", help="path to input video")
    vid_parser.add_argument("--num-frames", type=int, default=10)
    vid_parser.add_argument("--output-dir", default="video_analysis_output")
    vid_parser.add_argument("--bin-size", type=int, default=10)
    vid_parser.add_argument("--step", type=int, default=DEFAULT_PARAMS["step"])
    vid_parser.add_argument("--margin", type=int, default=DEFAULT_PARAMS["margin"])
    vid_parser.add_argument("--x-tolerance", type=int, default=DEFAULT_PARAMS["x_tolerance"])
    vid_parser.add_argument("--min-contrast", type=float, default=None,
                            help="fixed value; overrides the automatic one")
    vid_parser.add_argument("--min-brightness", type=float, default=None,
                            help="fixed value; overrides the automatic one")
    vid_parser.add_argument("--no-auto", action="store_true",
                            help="disable automatic lightness/contrast parameters")

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
            overrides = {}
            if args.min_contrast is not None:
                overrides["min_contrast"] = args.min_contrast
            if args.min_brightness is not None:
                overrides["min_brightness"] = args.min_brightness
            results = process_video(
                args.video,
                num_frames=args.num_frames,
                output_dir=args.output_dir,
                bin_size=args.bin_size,
                auto_params=not args.no_auto,
                step=args.step,
                margin=args.margin,
                x_tolerance=args.x_tolerance,
                **overrides,
            )
            print(f"Analyzed {len(results)} frames. Per-frame reports and "
                  f"summary.txt are in '{args.output_dir}/'.")
        except Exception as e:
            sys.exit(f"Error: {e}")


if __name__ == "__main__":
    main()