#!/usr/bin/env python3
"""Re-encode a finished video to fit under a size limit, for uploads that cap file size.

    fit_size.py master.mp4 small.mp4 --mb 10 [--height 720] [--audio-kbps 128]

--mb is the limit in megabytes of 1,000,000 bytes. The video bitrate is whatever the limit leaves after
audio and a 4% container margin, encoded two-pass with x264 so the size is predictable. Exit status is 1
when the result is still over the limit. Check a few frames of the result for readable text; below about
500 kbit/s at 1080p, pass --height 720.
"""

import argparse
import subprocess
import tempfile
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--mb", type=float, required=True)
    parser.add_argument("--height", type=int, help="scale to this height (width follows, kept even)")
    parser.add_argument("--audio-kbps", type=int, default=128)
    args = parser.parse_args()

    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(args.source)],
        check=True, capture_output=True, text=True,
    )
    duration = float(probe.stdout.strip())
    video_kbps = int(args.mb * 8000 * 0.96 / duration - args.audio_kbps)
    if video_kbps < 150:
        raise SystemExit(f"only {video_kbps} kbit/s left for video at {args.mb} MB over {duration:.0f}s; raise --mb or shorten the video")
    scale = ["-vf", f"scale=-2:{args.height}:flags=lanczos"] if args.height else []
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as work:
        common = [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(args.source), *scale,
            "-c:v", "libx264", "-preset", "slow", "-b:v", f"{video_kbps}k", "-pix_fmt", "yuv420p",
            "-passlogfile", str(Path(work) / "pass"),
        ]
        subprocess.run([*common, "-pass", "1", "-an", "-f", "null", "-"], check=True)
        subprocess.run(
            [*common, "-pass", "2", "-c:a", "aac", "-b:a", f"{args.audio_kbps}k", "-movflags", "+faststart", str(args.output)],
            check=True,
        )
    size = args.output.stat().st_size
    print(f"{args.output}: {size / 1e6:.2f} MB, video {video_kbps} kbit/s, {duration:.1f}s")
    if size > args.mb * 1e6:
        raise SystemExit(f"still over {args.mb} MB")


if __name__ == "__main__":
    main()
