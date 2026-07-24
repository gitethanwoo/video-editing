#!/usr/bin/env python3
"""Portable end-to-end smoke test for the generic FFmpeg workbench."""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
WORKBENCH = SKILL_DIR / "scripts" / "video_workbench.py"


def run(command: list[str]) -> None:
    subprocess.run(command, check=True)


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="video-workbench-smoke-") as raw_temp:
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
                "testsrc2=size=320x180:rate=24:duration=1",
                "-f",
                "lavfi",
                "-i",
                "sine=frequency=440:sample_rate=48000:duration=1",
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
        graph = temp / "edit.ffgraph"
        graph.write_text(
            "[0:v]format=yuv420p[vout];"
            "[0:a]loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000[aout]\n"
        )
        plan = {
            "version": 1,
            "inputs": ["source.mp4"],
            "filtergraph": "edit.ffgraph",
            "output": "final.mp4",
            "work_dir": "work",
            "video_map": "[vout]",
            "audio_map": "[aout]",
            "video": {
                "codec": "libx264",
                "args": ["-preset", "veryfast", "-crf", "25"],
                "pixel_format": "yuv420p",
                "fps": "24",
                "width": 320,
                "height": 180,
            },
            "audio": {
                "codec": "aac",
                "args": ["-b:a", "128k"],
                "sample_rate": 48000,
            },
            "validation": {
                "duration": 1,
                "duration_tolerance": 0.05,
                "codec": "h264",
                "pixel_formats": ["yuv420p"],
                "lufs": -16,
            },
        }
        plan_path = temp / "render-plan.json"
        plan_path.write_text(json.dumps(plan))
        run(["python3", str(WORKBENCH), "render-ffmpeg", str(plan_path)])
        run(["python3", str(WORKBENCH), "render-ffmpeg", str(plan_path)])
        run(
            [
                "python3",
                str(WORKBENCH),
                "inspect",
                "--work-dir",
                str(temp / "inspection"),
                str(source),
            ]
        )
        run(
            [
                "python3",
                str(WORKBENCH),
                "sheet",
                str(temp / "final.mp4"),
                str(temp / "contact.jpg"),
                "--frames",
                "6",
                "--columns",
                "3",
            ]
        )
        report = json.loads((temp / "work" / "validation.json").read_text())
        assert report["passed"] is True
        assert (temp / "final.mp4").is_file()
        assert (temp / "contact.jpg").is_file()
        assert (temp / "inspection" / "source-report.json").is_file()
        assert len(list((temp / ".video-workbench-archive").glob("final-*.mp4"))) == 1
        print("video workbench smoke test passed")


if __name__ == "__main__":
    main()
