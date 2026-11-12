#!/usr/bin/env python3
"""Encode screencast.mjs frames to constant-frame-rate MP4, timed by each frame's timestamp.

Time 0 in the output is the first frame. Each frame is shown until the next one arrives, and
the last frame is held for --hold seconds, so the video's clock matches the capture's clock and
marks logged during the take (relative to the first frame) line up with the encoded video.

    python3 frames_to_mp4.py raw/ raw.mp4 --fps 30 --hold 2.5
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("frames_dir", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--hold", type=float, default=2.0, help="seconds to hold the last frame")
    ap.add_argument("--crf", type=int, default=12)
    a = ap.parse_args()
    if not shutil.which("ffmpeg"):
        sys.exit("ffmpeg not found on PATH")
    frames = json.loads((a.frames_dir / "frames.json").read_text())
    if not frames:
        sys.exit("frames.json is empty")
    t0 = frames[0]["t"]
    lines = []
    for i, f in enumerate(frames):
        end = frames[i + 1]["t"] if i + 1 < len(frames) else f["t"] + a.hold
        lines += [f"file '{f['file']}'", f"duration {end - f['t']:.4f}"]
    # The concat demuxer ignores the last entry's duration unless the file is repeated, and the
    # repeat adds extra time, so the output is trimmed to the exact length below.
    lines.append(f"file '{frames[-1]['file']}'")
    (a.frames_dir / "list.txt").write_text("\n".join(lines) + "\n")
    total = frames[-1]["t"] - t0 + a.hold
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", "list.txt",
         "-vf", f"fps={a.fps},format=yuv420p", "-c:v", "libx264", "-crf", str(a.crf),
         "-preset", "medium", "-t", f"{total:.3f}", str(a.out.resolve())],
        cwd=a.frames_dir, check=True,
    )
    print(json.dumps({"frames": len(frames), "t0": t0, "duration": round(total, 3)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
