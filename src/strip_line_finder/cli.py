import argparse
import sys
from .image import analyse_image, annotate_image
from .video import process_video

def main():
    parser = argparse.ArgumentParser(description="Strip Line Finder CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    img_parser = subparsers.add_parser("image", help="Analyze single image.")
    img_parser.add_argument("image", help="path to input image")
    img_parser.add_argument("--step", type=int, default=100)
    img_parser.add_argument("--margin", type=int, default=4)
    img_parser.add_argument("--min-contrast", type=float, default=10.0)
    img_parser.add_argument("--x-tolerance", type=float, default=15.0)
    img_parser.add_argument("--output", help="marked image output path")

    vid_parser = subparsers.add_parser("video", help="Slice video into frames and analyze.")
    vid_parser.add_argument("video", help="path to input video")
    vid_parser.add_argument("--num-frames", type=int, default=10)
    vid_parser.add_argument("--output-dir", default="video_frames_output")

    args = parser.parse_args()

    if args.command == "image":
        try:
            class DummyArgs:
                pass
            # map args properly
            d = DummyArgs()
            for k, v in vars(args).items():
                setattr(d, k, v)
            for default_arg, val in [("min_width", 1), ("max_width", 14), ("bg_window", 41), 
                                     ("gap", 5), ("min_brightness", 15.0), ("x_tolerance", 10), 
                                     ("min_strips", 10), ("keep_all", False)]:
                if not hasattr(d, default_arg):
                    setattr(d, default_arg, val)

            width, height, lines, tracks = analyse_image(args.image, d)
            out = args.output or args.image.rsplit(".", 1)[0] + "_marked.png"
            annotate_image(args.image, lines, tracks, args.margin, out, args.step, args.x_tolerance)
            print(f"Successfully processed image. Marked image saved to: {out}")
        except Exception as e:
            sys.exit(f"Error: {e}")

    elif args.command == "video":
        try:
            results = process_video(args.video, num_frames=args.num_frames, output_dir=args.output_dir)
            print(f"Successfully analyzed {len(results)} frames from video. Results saved in '{args.output_dir}/'.")
        except Exception as e:
            sys.exit(f"Error: {e}")

if __name__ == "__main__":
    main()