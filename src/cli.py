"""Command line interface.

    measurement control  {ramp, pm, set, liv}      instrument control (data -> output/<ramp|pm|liv>/)
    measurement control  ramp ... --camera NAME    ramp with photos (photos -> input/folder/NAME/)
    measurement control  camera {info, photo, timelapse, video}
                                                   Canon EOS R10 (files -> input/folder/<name>/)
    measurement analysis {image, video, folder, report, analyse}   line detection
"""
import argparse
import sys
from pathlib import Path
from types import SimpleNamespace

from .strip_line_finder.analysis import analyse_spacing
from .strip_line_finder.calibration import COEFF, PX_TO_UM, THETA
from .strip_line_finder.detect import DetectionConfig
from .strip_line_finder.folder import main_folder
from .strip_line_finder.image import analyse_image
from .strip_line_finder.video import process_video
from .Canon.capture import main_camera_info, main_photo, main_timelapse, main_video
from .Canon.ramp_camera import main_ramp_camera
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
    ("strip_height", int, "analyse only this many rows around the image middle (default 200; 0 = all rows)"),
    ("min_threshold", float, "absolute floor of the threshold, 0-255 levels (default 2; lower it for dark images)"),
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


def add_camera_options(parser, settings=True):
    parser.add_argument("--sync-clock", action="store_true",
                        help="set the camera clock to the computer clock first")
    if not settings:
        return
    group = parser.add_argument_group(
        "camera settings (not given = keep the value set on the camera; "
        "see 'control camera info' for the allowed values)")
    group.add_argument("--shutter", default=None,
                       help="shutter speed, e.g. 1/250, 1/30, 0.5, 2 (mode dial on M or Tv)")
    group.add_argument("--iso", default=None, help="ISO, e.g. 100, 400, Auto")
    group.add_argument("--wb", dest="whitebalance", default=None,
                       help="white balance, e.g. Auto, Daylight, Tungsten, \"Color Temperature\"")
    group.add_argument("--color-temp", dest="colortemperature", default=None,
                       help="colour temperature in K, e.g. 5200 (also sets the white "
                            "balance to colour temperature)")
    group.add_argument("--picture-style", dest="picturestyle", default=None,
                       help="picture style, e.g. Standard, Neutral, Faithful")
    group.add_argument("--image-format", dest="imageformat", default=None,
                       help="image quality, e.g. \"Large Fine JPEG\" (photos must include a JPEG)")


def add_capture_options(parser):
    parser.add_argument("name", help="measurement name: files are saved as "
                                     "<input-dir>/folder/<name>/<name>_XXXX.jpg")
    parser.add_argument("--input-dir", default="input",
                        help="root folder for the captured files (default: input)")
    add_output_options(parser, "camera")
    add_camera_options(parser)


def camera_cfg(args, **extra):
    keys = ("name", "input_dir", "sync_clock", "shutter", "iso", "whitebalance",
            "colortemperature", "picturestyle", "imageformat")
    cfg = {k: getattr(args, k, None) for k in keys}
    if hasattr(args, "output_csv"):
        cfg["output_csv"] = output_csv_path(args.output_dir, "camera", args.output_csv)
    cfg.update(extra)
    return cfg


def config_from_args(args):
    return DetectionConfig(**{n: getattr(args, n) for n, _, _ in DETECTION_OPTIONS
                              if getattr(args, n) is not None})


def build_parser():
    parser = argparse.ArgumentParser(
        prog="measurement", description="Strip Line Finder CLI")
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
    cam_ramp = ramp.add_argument_group(
        "camera (optional): take photos with the Canon EOS R10 during the ramp")
    cam_ramp.add_argument("--camera", metavar="NAME", default=None,
                          help="take photos during the ramp, saved as "
                               "<input-dir>/folder/NAME/NAME_XXXX.jpg; a photo log "
                               "goes next to the ramp CSV (ramp_<UTC>_photos.csv)")
    cam_ramp.add_argument("--photo-delay", type=float, default=None,
                          help="one photo per step, this many seconds after the step "
                               "starts (default: half the step time)")
    cam_ramp.add_argument("--photo-interval", type=float, default=None,
                          help="instead: a photo every N seconds from the ramp start")
    cam_ramp.add_argument("--input-dir", default="input",
                          help="root folder for the photos (default: input)")
    cam_ramp.add_argument("--keep-on-card", action="store_true",
                          help="also keep the photos on the camera's memory card")
    add_camera_options(ramp)

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

    cam = ctl.add_parser(
        "camera", help="Canon EOS R10 over USB: manual photos, a photo every N seconds, "
                       "or video. Files go to <input-dir>/folder/<name>/<name>_XXXX.jpg "
                       "(.mp4 for video); a capture log to <output-dir>/camera/.")
    cmd = cam.add_subparsers(dest="camera_command", required=True)

    info = cmd.add_parser("info", help="Show the current settings and their allowed values.")
    add_camera_options(info, settings=False)

    ph = cmd.add_parser("photo", help="Take one photo now (with -i: a photo on every Enter).")
    add_capture_options(ph)
    ph.add_argument("-i", "--interactive", action="store_true",
                    help="keep the camera open: Enter takes a photo, q + Enter quits")
    ph.add_argument("--keep-on-card", action="store_true",
                    help="also keep the photos on the camera's memory card")

    tl = cmd.add_parser("timelapse", help="Take a photo every N seconds.")
    add_capture_options(tl)
    tl.add_argument("-n", "--interval", type=float, required=True,
                    help="seconds between photos (first photo at t = 0)")
    tl.add_argument("--count", type=int, default=None, help="number of photos")
    tl.add_argument("--duration", type=float, default=None,
                    help="total time in seconds (without --count/--duration: until Ctrl+C)")
    tl.add_argument("--keep-on-card", action="store_true",
                    help="also keep the photos on the camera's memory card")

    vd = cmd.add_parser("video", help="Record a video on the camera card and download it "
                                      "(camera switch on movie, memory card inserted).")
    add_capture_options(vd)
    vd.add_argument("--duration", type=float, default=None,
                    help="recording time in seconds (default: until Enter)")
    vd.add_argument("--delete-from-card", action="store_true",
                    help="delete the video from the card after the download")

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

    fol = ana.add_parser(
        "folder", help="Analyse every photo of a folder. The first photo is tuned and "
                       "shown, you confirm it with y (or answer n for other settings), "
                       "then all photos are analysed. Results go to "
                       "<output-dir>/folder/<name>/results.csv.")
    fol.add_argument("path", help="folder with the photos")
    fol.add_argument("--output-dir", default="output",
                     help="root output folder (default: output)")
    fol.add_argument("--yes", action="store_true",
                     help="do not ask: use the first suggestion for the settings")
    fol.add_argument("--no-show", action="store_true",
                     help="do not open the marked photo in the image viewer")
    fol.add_argument("--window", type=int, default=7,
                     help="photos compared with each other for the warnings (default: 7)")

    rep = ana.add_parser(
        "report", help="Line the photo results of 'analysis folder' up with a DC2200 ramp "
                       "by time and plot average distance and pitch against current, "
                       "intensity and time. Output: <output-dir>/report/<name>/ "
                       "(data.csv, plots.png, timeline.png).")
    rep.add_argument("name", help="name of the photo folder analysed with 'analysis folder' "
                                  "(results are read from <output-dir>/folder/<name>/results.csv)")
    rep.add_argument("--ramp", default=None,
                     help="ramp CSV (default: the newest <output-dir>/ramp/ramp_*.csv)")
    rep.add_argument("--results", default=None,
                     help="results CSV to use instead of the one found from the name")
    rep.add_argument("--objective", choices=sorted(COEFF), default="20x",
                     help="objective, sets the intensity per ampere (default: 20x)")
    rep.add_argument("--sample", choices=sorted(THETA), default="0.8wt",
                     help="sample concentration, sets the angle for the pitch (default: 0.8wt)")
    rep.add_argument("--px-um", type=float, default=PX_TO_UM,
                     help=f"micrometers per pixel (default: {PX_TO_UM})")
    rep.add_argument("--camera-offset", type=float, default=0.0,
                     help="seconds added to the photo times if the camera clock is off (default: 0)")
    rep.add_argument("--output-dir", default="output",
                     help="root output folder (default: output)")

    an = ana.add_parser(
        "analyse", help="Plot the mean distance between the lines (error = std) "
                        "against time, from <output-dir>/video/<name>/lines.csv.")
    an.add_argument("name", help="video name (folder under <output-dir>/video/)")
    an.add_argument("--output-dir", default="output",
                    help="root output folder (default: output)")
    return parser


def run_control(args):
    if args.command == "ramp":
        ramp_cfg = dict(i_min=args.i_min, i_max=args.i_max, step=args.step,
                        step_time=args.step_time, cycles=args.cycles,
                        output_csv=output_csv_path(args.output_dir, "ramp", args.output_csv))
        if args.camera:
            if args.photo_delay is not None and args.photo_interval is not None:
                raise ValueError("use either --photo-delay or --photo-interval, not both")
            main_ramp_camera({**camera_cfg(args), **ramp_cfg, "camera": args.camera,
                              "photo_delay": args.photo_delay,
                              "photo_interval": args.photo_interval,
                              "keep_on_card": args.keep_on_card})
        else:
            main_ramp(SimpleNamespace(**ramp_cfg))
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
    elif args.command == "camera":
        run_camera(args)


def run_camera(args):
    c = args.camera_command
    if c == "info":
        main_camera_info(camera_cfg(args))
    elif c == "photo":
        main_photo(camera_cfg(args, interactive=args.interactive,
                              keep_on_card=args.keep_on_card))
    elif c == "timelapse":
        main_timelapse(camera_cfg(args, interval=args.interval, count=args.count,
                                  duration=args.duration, keep_on_card=args.keep_on_card))
    elif c == "video":
        main_video(camera_cfg(args, duration=args.duration,
                              delete_from_card=args.delete_from_card))


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
    elif args.command == "folder":
        rows = main_folder(args.path, args.output_dir, window=args.window,
                           interactive=not args.yes, show=not args.no_show)
        if rows:
            print(f"Analysed {len(rows)} photos. Results are in "
                  f"'{Path(args.output_dir) / 'folder' / Path(args.path).name}/'.")
    elif args.command == "report":
        from .strip_line_finder.report import main_report      # pandas is only needed here
        res = main_report(args.name, ramp=args.ramp, results=args.results,
                          output_dir=args.output_dir, objective=args.objective,
                          theta=args.sample, px_to_um=args.px_um,
                          camera_offset_s=args.camera_offset)
        print(f"Ramp: {res['ramp_path']}\nPhotos: {res['results_path']}")
        print(f"{res['photos']} photos were taken during the ramp, {res['plotted']} plotted "
              "(photos with a warning are left out).")
        print(f"Data: {res['csv_path']}  Plots: {res['plot_path']}  {res['timeline_path']}")
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
        if args.group == "control" and args.command == "camera":
            sys.exit("Interrupted; files captured so far are kept"
                     + (" and recording was stopped." if args.camera_command == "video" else "."))
        sys.exit("Interrupted.")
    except Exception as e:
        sys.exit(f"Error: {e}")


if __name__ == "__main__":
    main()
