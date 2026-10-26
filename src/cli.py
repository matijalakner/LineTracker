import argparse
import sys
from pathlib import Path
from types import SimpleNamespace

from .strip_line_finder.image import analyse_image, annotate_image
from .strip_line_finder.video import process_video, split_video, DEFAULT_PARAMS
from .Thorlabs.DC2200 import main_ramp
from .Thorlabs.PM40 import main_power_measurement
from .Thorlabs.PM40_DC2200 import main_liv_measurement

OVERRIDABLE = [
    ("step", int), ("margin", int), ("min_contrast", float), ("min_brightness", float),
    ("max_width", int), ("bg_window", int), ("gap", int),
    ("x_tolerance", int), ("min_strips", int),
]


def main(argv=None):
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

    # ---- ThorLabs DC2200 ---------------------------------------------------------
    ramp_parser = subparsers.add_parser(
        "ramp", help="Ramp the DC2200 LED current up and down (currents in amperes).")
    ramp_parser.add_argument("--i-min", type=float, default=0.0,
                             help="Current to start from, in A (default: 0.0).")
    ramp_parser.add_argument("--i-max", type=float, default=0.8,
                             help="Current to ramp up to, in A (default: 0.8).")
    ramp_parser.add_argument("--ramp-duration", type=float, default=300.0,
                             help="Duration of each up or down ramp, in seconds.")
    ramp_parser.add_argument("--update-rate", "--update-ramp", dest="update_rate",
                             type=float, default=20.0,
                             help="Current updates per second.")
    ramp_parser.add_argument("--cycles", type=int, default=1,
                             help="Number of up/down cycles.")

    # ---- Thorlabs PM40 -----------------------------------------------------------
    pm_parser = subparsers.add_parser(
        "pm", help="Detect light power with PM40 powermeter.")
    pm_parser.add_argument("--wavelength", type=float, default=None,
                           help="Set the detection wavelength in nm (default: 633.0).")
    pm_parser.add_argument("--averaging-count", type=int, default=None,
                           help="Number of samples to average (default: 10).")
    pm_parser.add_argument("--sample-duration", type=float, default=None,
                           help="Total measurement duration in seconds (default: 5.0).")
    pm_parser.add_argument("--sample-rate", type=float, default=None,
                           help="Sampling frequency in Hz (default: 10.0).")

    # ---- Combined LIV (DC2200 + PM40) -------------------------------------------
    liv_parser = subparsers.add_parser(
        "liv", help="Simultaneously ramp DC2200 current and log power with PM40.")
    liv_parser.add_argument("--i-min", type=float, default=0.0)
    liv_parser.add_argument("--i-max", type=float, default=0.05)
    liv_parser.add_argument("--ramp-duration", type=float, default=10.0)
    liv_parser.add_argument("--update-rate", type=float, default=10.0)
    liv_parser.add_argument("--cycles", type=int, default=1)
    liv_parser.add_argument("--wavelength", type=float, default=633.0)
    liv_parser.add_argument("--averaging-count", type=int, default=10)

    args = parser.parse_args(argv)

    if args.command == "image":
        try:
            cfg = SimpleNamespace(**{**DEFAULT_PARAMS,
                                     "step": args.step,
                                     "margin": args.margin,
                                     "min_contrast": args.min_contrast})
            width, height, lines, tracks = analyse_image(args.image, cfg)
            p = Path(args.image)
            out = args.output or str(p.with_name(p.stem + "_marked.png"))
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
            if not results:
                sys.exit("Error: no frames could be read from the video.")
            out_dir = Path(results[0]["frame_path"]).parent.parent
            msg = f"Analysed {len(results)} frames. Results are in '{out_dir}/'."
            if not args.no_report:
                msg += f" Whole-video report: {out_dir}/video_report.txt"
            print(msg)
        except Exception as e:
            sys.exit(f"Error: {e}")

    elif args.command == "ramp":
        try:
            cfg = SimpleNamespace(
                i_min=args.i_min,
                i_max=args.i_max,
                ramp_duration=args.ramp_duration,
                update_rate=args.update_rate,
                cycles=args.cycles,
            )
            main_ramp(cfg)
            print("Ramp completed.")
        except KeyboardInterrupt:
            sys.exit("Ramp interrupted; LED output was switched off.")
        except Exception as e:
            sys.exit(f"Error: {e}")

    elif args.command == "pm":
        try:
            cfg = SimpleNamespace(
                wavelength=args.wavelength,
                averaging_count=args.averaging_count,
                sample_duration=args.sample_duration,
                sample_rate=args.sample_rate,
            )
            main_power_measurement(cfg)
            print("Power measurement completed.")
        except KeyboardInterrupt:
            sys.exit("Power measurement interrupted.")
        except Exception as e:
            sys.exit(f"Error: {e}")
    elif args.command == "liv":
        try:
            cfg = SimpleNamespace(
                i_min=args.i_min,
                i_max=args.i_max,
                ramp_duration=args.ramp_duration,
                update_rate=args.update_rate,
                cycles=args.cycles,
                wavelength=args.wavelength,
                averaging_count=args.averaging_count,
            )
            main_liv_measurement(cfg)
        except KeyboardInterrupt:
            sys.exit("Measurement interrupted; LED output was switched off.")
        except Exception as e:
            sys.exit(f"Error: {e}")

if __name__ == "__main__":
    main()