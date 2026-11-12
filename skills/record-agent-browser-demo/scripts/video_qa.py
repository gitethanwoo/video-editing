#!/usr/bin/env python3
"""Decode a browser demo, report metadata, and extract representative QA frames."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path


DURATION_RE = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")
VIDEO_RE = re.compile(r"Video:.*?(\d{2,5})x(\d{2,5})(?:[^\n]*?([\d.]+)\s+fps)?", re.IGNORECASE)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path, help="WebM, MP4, or MOV recording to verify")
    parser.add_argument("--out-dir", type=Path, required=True, help="Directory for extracted PNG frames")
    parser.add_argument("--frames", type=int, default=4, help="Number of representative frames (default: 4)")
    parser.add_argument("--min-width", type=int, default=960, help="Minimum accepted width (default: 960)")
    parser.add_argument("--min-height", type=int, default=540, help="Minimum accepted height (default: 540)")
    parser.add_argument("--min-duration", type=float, default=1.0, help="Minimum accepted seconds (default: 1)")
    parser.add_argument("--max-bytes", type=int, help="Optional upload-size ceiling")
    return parser.parse_args()


def fail(message: str) -> None:
    print(f"video QA failed: {message}", file=sys.stderr)
    raise SystemExit(1)


def run_ffmpeg(ffmpeg: str, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [ffmpeg, *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def main() -> None:
    args = parse_args()
    video = args.video.expanduser().resolve()
    if not video.is_file():
        fail(f"file does not exist: {video}")
    if video.suffix.lower() not in {".webm", ".mp4", ".mov"}:
        fail(f"unsupported video extension: {video.suffix}")
    size = video.stat().st_size
    if size <= 0:
        fail("file is empty")
    if args.max_bytes is not None and size > args.max_bytes:
        fail(f"file is {size} bytes, above --max-bytes {args.max_bytes}")
    if args.frames < 2 or args.frames > 12:
        fail("--frames must be between 2 and 12")

    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        fail("ffmpeg was not found on PATH")

    decoded = run_ffmpeg(ffmpeg, ["-hide_banner", "-i", str(video), "-f", "null", "-"])
    combined = decoded.stderr + "\n" + decoded.stdout
    if decoded.returncode != 0:
        fail("ffmpeg could not decode the full recording")

    duration_match = DURATION_RE.search(combined)
    video_match = VIDEO_RE.search(combined)
    if duration_match is None:
        fail("could not read video duration from ffmpeg output")
    if video_match is None:
        fail("could not read video resolution from ffmpeg output")

    hours, minutes, seconds = duration_match.groups()
    duration = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    width = int(video_match.group(1))
    height = int(video_match.group(2))
    fps = float(video_match.group(3)) if video_match.group(3) else None

    if duration < args.min_duration:
        fail(f"duration {duration:.2f}s is below minimum {args.min_duration:.2f}s")
    if width < args.min_width or height < args.min_height:
        fail(
            f"resolution {width}x{height} is below minimum "
            f"{args.min_width}x{args.min_height}"
        )

    out_dir = args.out_dir.expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    fractions = [(index + 1) / (args.frames + 1) for index in range(args.frames)]
    frame_paths: list[str] = []
    for index, fraction in enumerate(fractions, start=1):
        timestamp = max(0.0, min(duration - 0.05, duration * fraction))
        frame_path = out_dir / f"frame-{index:02d}-{timestamp:.2f}s.png"
        extracted = run_ffmpeg(
            ffmpeg,
            [
                "-loglevel",
                "error",
                "-ss",
                f"{timestamp:.3f}",
                "-i",
                str(video),
                "-frames:v",
                "1",
                "-y",
                str(frame_path),
            ],
        )
        if extracted.returncode != 0 or not frame_path.is_file() or frame_path.stat().st_size <= 0:
            fail(f"could not extract representative frame at {timestamp:.2f}s")
        frame_paths.append(str(frame_path))

    summary = {
        "video": str(video),
        "bytes": size,
        "duration_seconds": round(duration, 3),
        "width": width,
        "height": height,
        "fps": fps,
        "frames": frame_paths,
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
