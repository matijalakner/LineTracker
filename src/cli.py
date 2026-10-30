"""Command line interface.

    strip-line-finder control  {ramp, pm, set, liv}      instrument control (data -> output/<ramp|pm|liv>/)
    strip-line-finder analysis {image, video, analyse}   line detection
"""
import argparse
import sys
from pathlib import Path
from types import SimpleNamespace

from .strip_line_finder.analysis import analyse_spacing
from .strip_line_finder.detect import DetectionConfig
from .strip_line_finder.image import analyse_image
from .strip_line_finder.video import process_video
from .ThorLabs.DC2200 import main_ramp, main_set_current
from .ThorLabs.PM400 import main_power_measurement
from .ThorLabs.PM400_DC2200 import main_liv_measurement
from .utils import output_csv_path

DETECTION_OPTIONS = [
    ("n_blocks", int, "horizontal bands that must agree (default 8)"),
    ("bg_window", int, "background filter width in px (default: from image width)"),
    ("k", float, "noise floor in sigmas (default 3)"),
    ("rel", float, "threshold as a fraction of the strong responses (default 0.25)"),
    ("min_dist", int, "minimum distance between lines in px (default: from image width)"),
    ("x_tol", int, "max x shift between bands for one line in px (default: from image width)"),
    ("min_fraction", float, "fraction of bands a line must appear in (default 0.6)"),
    ("band_rel", float, "per-band visibility as a fraction of the threshold (default 0.5)"),
    ("smooth", int, "smoothing width in px (default 5)"),
    ("half_width", int, "painted half-width of a line in px (default 1)"),
]


def add_detection_options(parser):
    group = parser.add_argument_group("detection options")
    for name, typ, text in DETECTION_OPTIONS:
        group.add_argument("--" + name.replace("_", "-"), dest=name, type=typ,
                           default=None, help=text)


def add_output_options(parser, kind):
    parser.add_argument("--output-dir", default="output",
                        help=f"root output folder; data goes to <output-dir>/{kind}/ "
                             "(default: output)")
    parser.add_argument("--output-csv", default=None,
                        help=f"CSV file name (default: {kind}_<UTC time>.csv). A plain name "
                             f"is saved in <output-dir>/{kind}/.")


def config_from_args(args):
    return DetectionConfig(**{n: getattr(args, n) for n, _, _ in DETECTION_OPTIONS
                              if getattr(args, n) is not None})


def build_parser():
    parser = argparse.ArgumentParser(
        prog="strip-line-finder", description="Strip Line Finder CLI")
    groups = parser.add_subparsers(dest="group", required=True)

    # ======================================================================
    # control
    # ======================================================================
    control = groups.add_parser("control", help="Control the Thorlabs instruments.")
    ctl = control.add_subparsers(dest="command", required=True)

    ramp = ctl.add_parser(
        "ramp", help="Step the DC2200 LED current from min to max and back; every step "
                     "is held for step-time seconds (currents in amperes).")
    ramp.add_argument("--min", dest="i_min", type=float, required=True,
                      help="Current to start from, in A.")
    ramp.add_argument("--max", dest="i_max", type=float, required=True,
                      help="Current to step up to, in A (at most 2 A).")
    ramp.add_argument("--step", type=float, required=True,
                      help="Current increase per step, in A.")
    ramp.add_argument("--step-time", type=float, required=True,
                      help="How long every step is held, in seconds.")
    ramp.add_argument("--cycles", type=int, default=1,
                      help="Number of min -> max -> min cycles (default: 1).")
    add_output_options(ramp, "ramp")

    pm = ctl.add_parser("pm", help="Detect light power with the PM40 power meter.")
    pm.add_argument("--wavelength", type=float, default=450.0,
                    help="Set the detection wavelength in nm (default: 450.0).")
    pm.add_argument("--averaging-count", type=int, default=10,
                    help="Number of samples to average (default: 10).")
    pm.add_argument("--sample-duration", type=float, default=5.0,
                    help="Total measurement duration in seconds (default: 5.0).")
    pm.add_argument("--sample-rate", type=float, default=10.0,
                    help="Sampling frequency in Hz (default: 10.0).")
    add_output_options(pm, "pm")

    st = ctl.add_parser(
        "set", help="Set the DC2200 light output to a constant current and leave it on "
                    "(0 switches the output off).")
    st.add_argument("current", type=float, help="LED current in amperes (0 - 2 A).")

    liv = ctl.add_parser(
        "liv", help="Simultaneously ramp DC2200 current and log power with the PM40.")
    liv.add_argument("--i-min", type=float, default=0.0)
    liv.add_argument("--i-max", type=float, default=0.05)
    liv.add_argument("--ramp-duration", type=float, default=10.0)
    liv.add_argument("--update-rate", type=float, default=10.0)
    liv.add_argument("--cycles", type=int, default=1)
    liv.add_argument("--wavelength", type=float, default=450.0)
    liv.add_argument("--averaging-count", type=int, default=10)
    liv.add_argument("--settle-time", type=float, default=None,
                     help="seconds to wait after each current step (default: automatic)")
    add_output_options(liv, "liv")

    # ======================================================================
    # analysis
    # ======================================================================
    analysis = groups.add_parser("analysis", help="Detect and analyse vertical lines.")
    ana = analysis.add_subparsers(dest="command", required=True)

    img = ana.add_parser(
        "image", help="Analyse one image; saves the marked image and the line data "
                      "in <output-dir>/image/<name>/.")
    img.add_argument("image", help="path to input image")
    img.add_argument("--output-dir", default="output",
                     help="root output folder (default: output)")
    img.add_argument("--plot", action="store_true",
                     help="also save the line-strength plot")
    add_detection_options(img)

    vid = ana.add_parser(
        "video", help="Take a frame every N seconds and analyse each frame. Frames go "
                      "to <output-dir>/video/frames/<name>/, marked frames and lines.csv "
                      "to <output-dir>/video/<name>/.")
    vid.add_argument("video", help="path to input video")
    vid.add_argument("-n", "--interval", type=float, default=1.0,
                     help="seconds between analysed frames (default: 1.0)")
    vid.add_argument("--output-dir", default="output",
                     help="root output folder (default: output)")
    vid.add_argument("--quiet", action="store_true", help="do not print progress")
    add_detection_options(vid)

    an = ana.add_parser(
        "analyse", help="Plot the mean distance between the lines (error = std) "
                        "against time, from <output-dir>/video/<name>/lines.csv.")
    an.add_argument("name", help="video name (folder under <output-dir>/video/)")
    an.add_argument("--output-dir", default="output",
                    help="root output folder (default: output)")
    return parser


def run_control(args):
    if args.command == "ramp":
        main_ramp(SimpleNamespace(
            i_min=args.i_min, i_max=args.i_max, step=args.step,
            step_time=args.step_time, cycles=args.cycles,
            output_csv=output_csv_path(args.output_dir, "ramp", args.output_csv)))
        print("Ramp completed.")
    elif args.command == "pm":
        main_power_measurement(SimpleNamespace(
            wavelength=args.wavelength, averaging_count=args.averaging_count,
            sample_duration=args.sample_duration, sample_rate=args.sample_rate,
            output_csv=output_csv_path(args.output_dir, "pm", args.output_csv)))
    elif args.command == "set":
        main_set_current(SimpleNamespace(current=args.current))
    elif args.command == "liv":
        main_liv_measurement(SimpleNamespace(
            i_min=args.i_min, i_max=args.i_max, ramp_duration=args.ramp_duration,
            update_rate=args.update_rate, cycles=args.cycles,
            wavelength=args.wavelength, averaging_count=args.averaging_count,
            settle_time=args.settle_time,
            output_csv=output_csv_path(args.output_dir, "liv", args.output_csv)))


def run_analysis(args):
    if args.command == "image":
        name = Path(args.image).stem
        out_dir = Path(args.output_dir) / "image" / name
        res = analyse_image(args.image, out_dir, config_from_args(args), plot=args.plot)
        print(f"{len(res['lines'])} lines at x = {[int(x) for x in res['lines']]}")
        print(f"Results are in '{out_dir}/'.")
    elif args.command == "video":
        rows = process_video(args.video, output_dir=args.output_dir,
                             interval=args.interval, config=config_from_args(args),
                             verbose=not args.quiet)
        name = Path(args.video).stem
        print(f"Analysed {len(rows)} frames. Results are in "
              f"'{Path(args.output_dir) / 'video' / name}/'.")
    elif args.command == "analyse":
        res = analyse_spacing(args.name, args.output_dir)
        print(f"{res['frames']} frames used. Plot: {res['plot_path']}  "
              f"Data: {res['csv_path']}")


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        if args.group == "control":
            run_control(args)
        else:
            run_analysis(args)
    except KeyboardInterrupt:
        if args.group == "control" and args.command in ("ramp", "liv"):
            sys.exit("Interrupted; LED output was switched off.")
        sys.exit("Interrupted.")
    except Exception as e:
        sys.exit(f"Error: {e}")


if __name__ == "__main__":
    main()
