#!/usr/bin/env python3
"""Portable smoke test for deterministic video and audio analysis."""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
ANALYZER = SKILL_DIR / "scripts" / "video_analyzer.py"
LISTENER = SKILL_DIR / "scripts" / "audio_listener.py"


def run(command: list[str]) -> None:
    subprocess.run(command, check=True)


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="video-analyzer-smoke-") as raw_temp:
        temp = Path(raw_temp)
        source = temp / "source.mp4"
        run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-f",
                "lavfi",
                "-i",
                "testsrc2=size=320x180:rate=24:duration=2",
                "-f",
                "lavfi",
                "-i",
                "sine=frequency=440:sample_rate=48000:duration=2",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-shortest",
                str(source),
            ]
        )

        analysis_dir = temp / "analysis"
        run(
            [
                "uv",
                "run",
                str(ANALYZER),
                "analyze",
                str(source),
                "--work-dir",
                str(analysis_dir),
                "--contact-frames",
                "2",
            ]
        )
        analysis = json.loads((analysis_dir / "analysis.json").read_text())
        assert analysis["media"]["width"] == 320
        assert analysis["media"]["height"] == 180
        assert analysis["media"]["audio_stream_count"] == 1
        assert (analysis_dir / "contact-sheet.jpg").is_file()
        assert (analysis_dir / "timeline.md").is_file()

        audio_dir = temp / "audio"
        run(
            [
                "python3",
                str(LISTENER),
                str(source),
                "--work-dir",
                str(audio_dir),
                "--start",
                "0",
                "--end",
                "2",
                "--prepare-only",
            ]
        )
        evidence = json.loads((audio_dir / "evidence.json").read_text())
        assert evidence["range"]["duration"] == 2
        assert (audio_dir / "audio-excerpt.mp3").is_file()
        assert (audio_dir / "spectrogram.png").is_file()
        assert (audio_dir / "audio-levels.json").is_file()
        print("video analyzer smoke test passed")


if __name__ == "__main__":
    main()
