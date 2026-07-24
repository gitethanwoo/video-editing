#!/usr/bin/env python3
"""General-purpose observation, review, rendering, and validation tools for video edits."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
import re
import shlex
import shutil
import subprocess
import sys
import uuid
from pathlib import Path


def fail(message: str) -> None:
    raise SystemExit(message)


def run(
    command: list[str], *, capture: bool = False, check: bool = True
) -> subprocess.CompletedProcess[str]:
    print("$", shlex.join(command), flush=True)
    return subprocess.run(command, check=check, text=True, capture_output=capture)


def require_media_tools() -> None:
    missing = [tool for tool in ("ffmpeg", "ffprobe") if shutil.which(tool) is None]
    if missing:
        fail(f"Missing required tools: {', '.join(missing)}")


def filtergraph_file_args(filtergraph: Path) -> list[str]:
    version_result = run(["ffmpeg", "-version"], capture=True)
    version_match = re.search(r"^ffmpeg version\s+([0-9]+)", version_result.stdout)
    if version_match and int(version_match.group(1)) >= 8:
        return ["-/filter_complex", str(filtergraph)]

    help_result = run(
        ["ffmpeg", "-hide_banner", "-h", "full"],
        capture=True,
        check=False,
    )
    help_text = help_result.stdout + help_result.stderr
    if "-filter_complex_script" in help_text:
        return ["-filter_complex_script", str(filtergraph)]
    fail("This FFmpeg build cannot load a complex filtergraph from a file")


def ffprobe(path: Path) -> dict:
    result = run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_format",
            "-show_streams",
            "-show_chapters",
            "-of",
            "json",
            str(path),
        ],
        capture=True,
    )
    payload = json.loads(result.stdout)
    if not isinstance(payload.get("streams"), list) or not isinstance(
        payload.get("format"), dict
    ):
        fail(f"Unexpected ffprobe payload for {path}")
    return payload


def streams(payload: dict, codec_type: str) -> list[dict]:
    return [
        stream
        for stream in payload["streams"]
        if stream.get("codec_type") == codec_type
    ]


def optional_duration(payload: dict) -> float | None:
    value = payload["format"].get("duration")
    return float(value) if value is not None else None


def duration(payload: dict) -> float:
    value = optional_duration(payload)
    if value is None:
        fail("Media payload has no format duration")
    return value


def normalized_facts(payload: dict) -> dict:
    video_facts: list[dict] = []
    for stream in streams(payload, "video"):
        side_data = stream.get("side_data_list", [])
        rotation = next(
            (
                item["rotation"]
                for item in side_data
                if isinstance(item, dict) and "rotation" in item
            ),
            stream.get("tags", {}).get("rotate"),
        )
        video_facts.append(
            {
                "index": stream.get("index"),
                "codec": stream.get("codec_name"),
                "width": stream.get("width"),
                "height": stream.get("height"),
                "pixel_format": stream.get("pix_fmt"),
                "average_frame_rate": stream.get("avg_frame_rate"),
                "real_frame_rate": stream.get("r_frame_rate"),
                "color_range": stream.get("color_range"),
                "color_space": stream.get("color_space"),
                "rotation": rotation,
            }
        )
    audio_facts = [
        {
            "index": stream.get("index"),
            "codec": stream.get("codec_name"),
            "sample_rate": stream.get("sample_rate"),
            "channels": stream.get("channels"),
            "channel_layout": stream.get("channel_layout"),
        }
        for stream in streams(payload, "audio")
    ]
    return {
        "duration_seconds": optional_duration(payload),
        "format": payload["format"].get("format_name"),
        "video_streams": video_facts,
        "audio_streams": audio_facts,
    }


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            value.update(chunk)
    return value.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def volume_scans(path: Path, payload: dict) -> list[dict]:
    results: list[dict] = []
    for stream in streams(payload, "audio"):
        stream_index = int(stream["index"])
        result = run(
            [
                "ffmpeg",
                "-hide_banner",
                "-nostats",
                "-i",
                str(path),
                "-map",
                f"0:{stream_index}",
                "-af",
                "volumedetect",
                "-f",
                "null",
                "-",
            ],
            capture=True,
            check=False,
        )
        results.append(
            {
                "stream_index": stream_index,
                "output": "\n".join(
                    line
                    for line in result.stderr.splitlines()
                    if "Parsed_volumedetect" in line
                ),
            }
        )
    return results


def make_sheet(
    source: Path,
    destination: Path,
    frame_count: int,
    columns: int,
    payload: dict | None = None,
) -> None:
    if frame_count <= 0 or columns <= 0:
        fail("Contact sheet frames and columns must be positive")
    if payload is None:
        payload = ffprobe(source)
    source_duration = duration(payload)
    rows = math.ceil(frame_count / columns)
    destination.parent.mkdir(parents=True, exist_ok=True)
    run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(source),
            "-vf",
            (
                f"fps={frame_count / source_duration:.12f},"
                f"scale='min(480,iw)':-2,tile={columns}x{rows}:nb_frames={frame_count}"
            ),
            "-frames:v",
            "1",
            str(destination),
        ]
    )


def make_strip(
    source: Path,
    destination: Path,
    center: float,
    window: float,
    frame_count: int,
    columns: int,
) -> None:
    if center < 0 or window <= 0 or frame_count <= 0 or columns <= 0:
        fail(
            "Strip center must be non-negative; window, frames, and columns must be positive"
        )
    payload = ffprobe(source)
    source_duration = duration(payload)
    start = max(0.0, center - window / 2)
    end = min(source_duration, center + window / 2)
    if end <= start:
        fail("Transition window does not intersect the video")
    rows = math.ceil(frame_count / columns)
    destination.parent.mkdir(parents=True, exist_ok=True)
    run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(source),
            "-vf",
            (
                f"trim=start={start}:end={end},setpts=PTS-STARTPTS,"
                f"fps={frame_count / (end - start):.12f},"
                f"scale='min(480,iw)':-2,tile={columns}x{rows}:nb_frames={frame_count}"
            ),
            "-frames:v",
            "1",
            str(destination),
        ]
    )


def make_still_preview(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(source),
            "-vf",
            "scale='min(960,iw)':-2",
            "-frames:v",
            "1",
            str(destination),
        ]
    )


def inspect_command(paths: list[Path], work_dir: Path, sheet_frames: int) -> None:
    require_media_tools()
    work_dir.mkdir(parents=True, exist_ok=True)
    items: list[dict] = []
    for index, path in enumerate(paths, start=1):
        source = path.expanduser().resolve()
        if not source.is_file():
            fail(f"Missing input: {source}")
        payload = ffprobe(source)
        item = {
            "path": str(source),
            "sha256": digest(source),
            "normalized": normalized_facts(payload),
            "probe": payload,
            "volume_scans": volume_scans(source, payload),
        }
        items.append(item)
        if streams(payload, "video"):
            safe_stem = re.sub(r"[^a-zA-Z0-9._-]+", "-", source.stem).strip("-")
            if optional_duration(payload) is None:
                make_still_preview(
                    source, work_dir / f"{index:02d}-{safe_stem}-preview.png"
                )
            else:
                make_sheet(
                    source,
                    work_dir / f"{index:02d}-{safe_stem}-contact.jpg",
                    sheet_frames,
                    4,
                    payload,
                )
    report = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "inputs": items,
    }
    write_json(work_dir / "source-report.json", report)
    print(f"Source report: {work_dir / 'source-report.json'}")


def stills_command(source: Path, output_dir: Path, timestamps: list[float]) -> None:
    require_media_tools()
    source = source.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    for index, timestamp in enumerate(timestamps, start=1):
        run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-ss",
                f"{timestamp:.6f}",
                "-i",
                str(source),
                "-frames:v",
                "1",
                str(output_dir / f"{index:02d}-{timestamp:.3f}.png"),
            ]
        )


def transcribe_command(source: Path, output_dir: Path, model: str) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    run(
        [
            sys.executable,
            "-m",
            "mlx_whisper",
            str(source.expanduser().resolve()),
            "--model",
            model,
            "--output-dir",
            str(output_dir.resolve()),
            "--output-format",
            "all",
        ]
    )


def loudness(
    path: Path,
    target_lufs: float,
    true_peak: float,
    loudness_range: float,
    audio_stream_index: int,
) -> dict | None:
    result = run(
        [
            "ffmpeg",
            "-hide_banner",
            "-nostats",
            "-i",
            str(path),
            "-map",
            f"0:a:{audio_stream_index}",
            "-af",
            f"loudnorm=I={target_lufs}:TP={true_peak}:LRA={loudness_range}:print_format=json",
            "-f",
            "null",
            "-",
        ],
        capture=True,
        check=False,
    )
    matches = re.findall(r"\{\s*\"input_i\".*?\}", result.stderr, flags=re.DOTALL)
    return json.loads(matches[-1]) if matches else None


def parse_rate(value: str) -> float:
    if "/" in value:
        numerator, denominator = value.split("/", maxsplit=1)
        return float(numerator) / float(denominator)
    return float(value)


def validate_media(
    source: Path,
    *,
    expected_width: int | None,
    expected_height: int | None,
    expected_duration: float | None,
    duration_tolerance: float,
    expected_fps: float | None,
    expected_audio_rate: int | None,
    target_lufs: float | None,
    true_peak: float,
    loudness_range: float,
    report_path: Path,
    expected_video_streams: int,
    expected_audio_streams: int | None,
    expected_subtitle_streams: int | None,
    expected_codec: str | None,
    expected_profile: str | None,
    expected_pixel_formats: list[str] | None,
    audio_stream_index: int,
) -> dict:
    require_media_tools()
    source = source.expanduser().resolve()
    if not source.is_file():
        fail(f"Missing output: {source}")
    payload = ffprobe(source)
    video_streams = streams(payload, "video")
    audio_streams = streams(payload, "audio")
    subtitle_streams = streams(payload, "subtitle")
    checks: dict[str, bool] = {
        "video_streams": len(video_streams) == expected_video_streams,
    }
    if expected_audio_streams is not None:
        checks["audio_streams"] = len(audio_streams) == expected_audio_streams
    if expected_subtitle_streams is not None:
        checks["subtitle_streams"] = len(subtitle_streams) == expected_subtitle_streams
    video = video_streams[0] if video_streams else {}
    if expected_width is not None:
        checks["width"] = int(video.get("width", -1)) == expected_width
    if expected_height is not None:
        checks["height"] = int(video.get("height", -1)) == expected_height
    if expected_duration is not None:
        checks["duration"] = (
            abs(duration(payload) - expected_duration) <= duration_tolerance
        )
    if expected_fps is not None:
        actual_rate = parse_rate(str(video.get("avg_frame_rate", "0")))
        checks["fps"] = abs(actual_rate - expected_fps) <= 0.02
    if expected_audio_rate is not None:
        checks["audio_sample_rate"] = (
            0 <= audio_stream_index < len(audio_streams)
            and int(audio_streams[audio_stream_index].get("sample_rate", -1))
            == expected_audio_rate
        )
    if expected_codec is not None:
        checks["video_codec"] = video.get("codec_name") == expected_codec
    if expected_profile is not None:
        checks["video_profile"] = video.get("profile") == expected_profile
    if expected_pixel_formats is not None:
        checks["pixel_format"] = video.get("pix_fmt") in expected_pixel_formats

    decode = run(
        [
            "ffmpeg",
            "-hide_banner",
            "-v",
            "error",
            "-xerror",
            "-i",
            str(source),
            "-map",
            "0:v",
            "-map",
            "0:a?",
            "-f",
            "null",
            "-",
        ],
        capture=True,
        check=False,
    )
    checks["full_decode"] = decode.returncode == 0 and not decode.stderr.strip()
    measured_loudness = None
    if target_lufs is not None:
        measured_loudness = (
            loudness(source, target_lufs, true_peak, loudness_range, audio_stream_index)
            if 0 <= audio_stream_index < len(audio_streams)
            else None
        )
        checks["loudness"] = (
            measured_loudness is not None
            and abs(float(measured_loudness["input_i"]) - target_lufs) <= 1.0
            and float(measured_loudness["input_tp"]) <= true_peak + 0.2
        )
    sha = digest(source)
    report = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "source": str(source),
        "checks": checks,
        "passed": all(checks.values()),
        "probe": payload,
        "decode_stderr": decode.stderr,
        "loudness": measured_loudness,
        "sha256": sha,
    }
    write_json(report_path, report)
    report_path.with_name("sha256.txt").write_text(f"{sha}  {source.name}\n")
    for name, passed in checks.items():
        print(f"{'PASS' if passed else 'FAIL'}  {name}")
    print(f"Validation report: {report_path}")
    return report


def validate_command(args: argparse.Namespace) -> None:
    report = validate_media(
        args.source,
        expected_width=args.width,
        expected_height=args.height,
        expected_duration=args.duration,
        duration_tolerance=args.duration_tolerance,
        expected_fps=args.fps,
        expected_audio_rate=args.audio_rate,
        target_lufs=args.lufs,
        true_peak=args.true_peak,
        loudness_range=args.loudness_range,
        report_path=args.report.expanduser().resolve(),
        expected_video_streams=args.video_streams,
        expected_audio_streams=None if args.allow_silent else args.audio_streams,
        expected_subtitle_streams=args.subtitle_streams,
        expected_codec=args.codec,
        expected_profile=args.profile,
        expected_pixel_formats=args.pixel_format,
        audio_stream_index=args.audio_stream_index,
    )
    raise SystemExit(0 if report["passed"] else 1)


def resolve_from(base: Path, value: str) -> Path:
    path = Path(value).expanduser()
    return path.resolve() if path.is_absolute() else (base / path).resolve()


def render_ffmpeg_command(plan_path: Path) -> None:
    require_media_tools()
    plan_path = plan_path.expanduser().resolve()
    plan = json.loads(plan_path.read_text())
    if not isinstance(plan, dict) or plan.get("version") != 1:
        fail("Render plan must be a version 1 JSON object")
    base = plan_path.parent
    required = ("inputs", "filtergraph", "output", "work_dir", "video")
    missing = [key for key in required if key not in plan]
    if missing:
        fail(f"Missing render plan keys: {', '.join(missing)}")
    inputs = [resolve_from(base, value) for value in plan["inputs"]]
    for source in inputs:
        if not source.is_file():
            fail(f"Missing render input: {source}")
    filtergraph = resolve_from(base, plan["filtergraph"])
    if not filtergraph.is_file():
        fail(f"Missing filtergraph: {filtergraph}")
    output = resolve_from(base, plan["output"])
    if any(output == source for source in inputs):
        fail("Render output must not be one of its inputs")
    work_dir = resolve_from(base, plan["work_dir"])
    work_dir.mkdir(parents=True, exist_ok=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    run_id = uuid.uuid4().hex
    candidate = (
        output.parent / f".{output.stem}-candidate-{run_id}{output.suffix or '.mp4'}"
    )
    lock_path = output.parent / f".{output.name}.video-workbench.lock"
    try:
        lock_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        fail(f"Another render holds the output lock: {lock_path}")
    os.write(lock_fd, f"pid={os.getpid()} run={run_id}\n".encode())
    os.close(lock_fd)
    try:
        command = ["ffmpeg", "-hide_banner", "-y"]
        for source in inputs:
            command.extend(["-i", str(source)])
        command.extend(filtergraph_file_args(filtergraph))
        command.extend(["-map", str(plan.get("video_map", "[vout]"))])
        if plan.get("audio_map") is not None:
            command.extend(["-map", str(plan["audio_map"])])
        video = plan["video"]
        command.extend(["-c:v", str(video["codec"])])
        command.extend(str(item) for item in video.get("args", []))
        if "pixel_format" in video:
            command.extend(["-pix_fmt", str(video["pixel_format"])])
        if "fps" in video:
            command.extend(["-r", str(video["fps"])])
        audio = plan.get("audio")
        if audio is not None and plan.get("audio_map") is not None:
            command.extend(["-c:a", str(audio["codec"])])
            command.extend(str(item) for item in audio.get("args", []))
            if "sample_rate" in audio:
                command.extend(["-ar", str(audio["sample_rate"])])
        command.extend(["-movflags", "+faststart", str(candidate)])
        (work_dir / "render-command.txt").write_text(shlex.join(command) + "\n")
        run(command)

        validation = plan.get("validation", {})
        pixel_formats = validation.get("pixel_formats")
        report = validate_media(
            candidate,
            expected_width=int(video["width"]) if "width" in video else None,
            expected_height=int(video["height"]) if "height" in video else None,
            expected_duration=float(validation["duration"])
            if "duration" in validation
            else None,
            duration_tolerance=float(validation.get("duration_tolerance", 0.12)),
            expected_fps=parse_rate(str(video["fps"])) if "fps" in video else None,
            expected_audio_rate=int(audio["sample_rate"])
            if audio and "sample_rate" in audio
            else None,
            target_lufs=float(validation["lufs"]) if "lufs" in validation else None,
            true_peak=float(validation.get("true_peak", -1.5)),
            loudness_range=float(validation.get("loudness_range", 11)),
            report_path=work_dir / "validation.json",
            expected_video_streams=1,
            expected_audio_streams=1
            if audio is not None and plan.get("audio_map") is not None
            else 0,
            expected_subtitle_streams=None,
            expected_codec=validation.get("codec"),
            expected_profile=validation.get("profile"),
            expected_pixel_formats=[str(item) for item in pixel_formats]
            if pixel_formats
            else None,
            audio_stream_index=int(validation.get("audio_stream_index", 0)),
        )
        if not report["passed"]:
            fail(f"Candidate failed validation and was not promoted: {candidate}")

        archive_dir = output.parent / ".video-workbench-archive"
        archived: Path | None = None
        if output.exists():
            archive_dir.mkdir(exist_ok=True)
            stamp = dt.datetime.now(tz=dt.UTC).strftime("%Y%m%d-%H%M%S-%f")
            archived = archive_dir / f"{output.stem}-{stamp}-{run_id}{output.suffix}"
            os.replace(output, archived)
            print(f"Archived prior output: {archived}")
        try:
            os.replace(candidate, output)
        except OSError:
            if archived is not None and archived.exists() and not output.exists():
                os.replace(archived, output)
            raise
        report["source"] = str(output)
        write_json(work_dir / "validation.json", report)
        (work_dir / "sha256.txt").write_text(f"{report['sha256']}  {output.name}\n")
        print(f"Promoted validated output: {output}")
    finally:
        if lock_path.exists():
            lock_path.unlink()


def init_motion_command(target: Path) -> None:
    template = (
        Path(__file__).resolve().parent.parent / "assets" / "remotion-edit-template"
    )
    if not template.is_dir():
        fail(f"Bundled motion template is missing: {template}")
    target = target.expanduser().resolve()
    if target.exists() and any(target.iterdir()):
        fail(f"Target directory must be absent or empty: {target}")
    target.mkdir(parents=True, exist_ok=True)
    shutil.copytree(template, target, dirs_exist_ok=True)
    print(f"Initialized motion project: {target}")


def init_project_command(target: Path) -> None:
    template = (
        Path(__file__).resolve().parent.parent / "assets" / "edit-project-template"
    )
    if not template.is_dir():
        fail(f"Bundled edit project template is missing: {template}")
    target = target.expanduser().resolve()
    if target.exists() and any(target.iterdir()):
        fail(f"Target directory must be absent or empty: {target}")
    target.mkdir(parents=True, exist_ok=True)
    shutil.copytree(template, target, dirs_exist_ok=True)
    print(f"Initialized edit project: {target}")


def parse_times(value: str) -> list[float]:
    timestamps = [float(item.strip()) for item in value.split(",") if item.strip()]
    if not timestamps or any(value < 0 for value in timestamps):
        fail("--times must be a comma-separated list of non-negative seconds")
    return timestamps


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    commands = result.add_subparsers(dest="command", required=True)

    init_parser = commands.add_parser("init", help="Create a neutral edit project")
    init_parser.add_argument("target", type=Path)

    inspect_parser = commands.add_parser(
        "inspect", help="Probe, hash, audio-scan, and contact-sheet sources"
    )
    inspect_parser.add_argument("inputs", nargs="+", type=Path)
    inspect_parser.add_argument("--work-dir", required=True, type=Path)
    inspect_parser.add_argument("--sheet-frames", type=int, default=12)

    sheet_parser = commands.add_parser("sheet", help="Create a uniform contact sheet")
    sheet_parser.add_argument("source", type=Path)
    sheet_parser.add_argument("output", type=Path)
    sheet_parser.add_argument("--frames", type=int, default=12)
    sheet_parser.add_argument("--columns", type=int, default=4)

    strip_parser = commands.add_parser(
        "strip", help="Create a frame strip around one output-time event"
    )
    strip_parser.add_argument("source", type=Path)
    strip_parser.add_argument("output", type=Path)
    strip_parser.add_argument("--center", required=True, type=float)
    strip_parser.add_argument("--window", type=float, default=1.6)
    strip_parser.add_argument("--frames", type=int, default=8)
    strip_parser.add_argument("--columns", type=int, default=4)

    stills_parser = commands.add_parser("stills", help="Extract review stills")
    stills_parser.add_argument("source", type=Path)
    stills_parser.add_argument("output_dir", type=Path)
    stills_parser.add_argument("--times", required=True, type=parse_times)

    transcribe_parser = commands.add_parser(
        "transcribe", help="Transcribe speech using optional mlx_whisper"
    )
    transcribe_parser.add_argument("source", type=Path)
    transcribe_parser.add_argument("output_dir", type=Path)
    transcribe_parser.add_argument("--model", default="mlx-community/whisper-small-mlx")

    validate_parser = commands.add_parser(
        "validate", help="Fully decode and validate a rendered video"
    )
    validate_parser.add_argument("source", type=Path)
    validate_parser.add_argument("--report", type=Path, default=Path("validation.json"))
    validate_parser.add_argument("--width", type=int)
    validate_parser.add_argument("--height", type=int)
    validate_parser.add_argument("--duration", type=float)
    validate_parser.add_argument("--duration-tolerance", type=float, default=0.12)
    validate_parser.add_argument("--fps", type=float)
    validate_parser.add_argument("--audio-rate", type=int)
    validate_parser.add_argument("--video-streams", type=int, default=1)
    validate_parser.add_argument("--audio-streams", type=int, default=1)
    validate_parser.add_argument("--subtitle-streams", type=int)
    validate_parser.add_argument("--codec")
    validate_parser.add_argument("--profile")
    validate_parser.add_argument("--pixel-format", action="append")
    validate_parser.add_argument("--audio-stream-index", type=int, default=0)
    validate_parser.add_argument("--lufs", type=float)
    validate_parser.add_argument("--true-peak", type=float, default=-1.5)
    validate_parser.add_argument("--loudness-range", type=float, default=11)
    validate_parser.add_argument("--allow-silent", action="store_true")

    render_parser = commands.add_parser(
        "render-ffmpeg", help="Render, validate, and safely promote a generic plan"
    )
    render_parser.add_argument("plan", type=Path)

    motion_parser = commands.add_parser(
        "init-motion", help="Copy the React/SVG/Remotion edit starter"
    )
    motion_parser.add_argument("target", type=Path)
    return result


def main() -> None:
    args = parser().parse_args()
    if args.command == "init":
        init_project_command(args.target)
    elif args.command == "inspect":
        inspect_command(
            args.inputs, args.work_dir.expanduser().resolve(), args.sheet_frames
        )
    elif args.command == "sheet":
        require_media_tools()
        make_sheet(
            args.source.expanduser().resolve(),
            args.output.expanduser().resolve(),
            args.frames,
            args.columns,
        )
    elif args.command == "strip":
        require_media_tools()
        make_strip(
            args.source.expanduser().resolve(),
            args.output.expanduser().resolve(),
            args.center,
            args.window,
            args.frames,
            args.columns,
        )
    elif args.command == "stills":
        stills_command(args.source, args.output_dir, args.times)
    elif args.command == "transcribe":
        transcribe_command(args.source, args.output_dir, args.model)
    elif args.command == "validate":
        validate_command(args)
    elif args.command == "render-ffmpeg":
        render_ffmpeg_command(args.plan)
    elif args.command == "init-motion":
        init_motion_command(args.target)


if __name__ == "__main__":
    main()
