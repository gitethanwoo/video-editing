#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "librosa>=0.11,<0.12",
#   "numpy>=2,<3",
#   "opencv-python-headless>=4.11,<5",
#   "soundfile>=0.13,<0.14",
# ]
# ///
"""Extract evidence for editorial reverse-engineering of a video."""

from __future__ import annotations

import argparse
import csv
import html
import itertools
import json
import math
import re
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import TypedDict

import cv2
import librosa
import numpy as np


class Cue(TypedDict):
    start: float
    end: float
    text: str


def fail(message: str) -> None:
    raise SystemExit(message)


def run(
    command: list[str], *, capture: bool = False, check: bool = True
) -> subprocess.CompletedProcess[str]:
    print("$", shlex.join(command), flush=True)
    return subprocess.run(command, check=check, text=True, capture_output=capture)


def require_tools(ocr: bool) -> None:
    required = ["ffmpeg", "ffprobe"]
    if ocr:
        required.append("tesseract")
    missing = [tool for tool in required if shutil.which(tool) is None]
    if missing:
        fail(f"Missing required tools: {', '.join(missing)}")


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def probe(source: Path) -> dict:
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
            str(source),
        ],
        capture=True,
    )
    payload = json.loads(result.stdout)
    if not isinstance(payload.get("streams"), list) or not isinstance(
        payload.get("format"), dict
    ):
        fail("Unexpected ffprobe response shape")
    return payload


def media_duration(payload: dict) -> float:
    value = payload["format"].get("duration")
    if value is None:
        fail("Source has no format duration")
    return float(value)


def video_stream(payload: dict) -> dict:
    candidates = [
        stream for stream in payload["streams"] if stream.get("codec_type") == "video"
    ]
    if not candidates:
        fail("Source has no video stream")
    return candidates[0]


def audio_streams(payload: dict) -> list[dict]:
    return [
        stream for stream in payload["streams"] if stream.get("codec_type") == "audio"
    ]


def section_args(start: float, end: float) -> list[str]:
    return ["-ss", f"{start:.6f}", "-t", f"{end - start:.6f}"]


def timestamp(value: float) -> str:
    milliseconds = round(value * 1000)
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, millis = divmod(remainder, 1000)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{millis:03d}"
    return f"{minutes:02d}:{seconds:02d}.{millis:03d}"


def scene_changes(
    source: Path, start: float, end: float, threshold: float, raw_dir: Path
) -> list[dict]:
    result = run(
        [
            "ffmpeg",
            "-hide_banner",
            "-nostats",
            *section_args(start, end),
            "-i",
            str(source),
            "-vf",
            f"select='gt(scene,{threshold})',metadata=print",
            "-an",
            "-f",
            "null",
            "-",
        ],
        capture=True,
        check=False,
    )
    (raw_dir / "scene-detection.log").write_text(result.stderr)
    times = re.findall(r"pts_time:([0-9.]+)", result.stderr)
    scores = re.findall(r"lavfi\.scene_score=([0-9.]+)", result.stderr)
    candidates = [
        {"time": start + float(time), "score": float(score)}
        for time, score in zip(times, scores, strict=False)
    ]
    consolidated: list[dict] = []
    for candidate in candidates:
        if consolidated and candidate["time"] - consolidated[-1]["time"] < 0.20:
            if candidate["score"] > consolidated[-1]["score"]:
                consolidated[-1] = candidate
        else:
            consolidated.append(candidate)
    return consolidated


def interval_events(
    source: Path, start: float, end: float, raw_dir: Path, has_audio: bool
) -> tuple[list[dict], list[dict]]:
    filters = ["-vf", "blackdetect=d=0.10:pix_th=0.10"]
    if has_audio:
        filters.extend(["-af", "silencedetect=n=-38dB:d=0.20"])
    result = run(
        [
            "ffmpeg",
            "-hide_banner",
            "-nostats",
            *section_args(start, end),
            "-i",
            str(source),
            *filters,
            "-f",
            "null",
            "-",
        ],
        capture=True,
        check=False,
    )
    (raw_dir / "black-and-silence.log").write_text(result.stderr)
    black = [
        {
            "start": start + float(match.group(1)),
            "end": start + float(match.group(2)),
            "duration": float(match.group(3)),
        }
        for match in re.finditer(
            r"black_start:([0-9.]+) black_end:([0-9.]+) black_duration:([0-9.]+)",
            result.stderr,
        )
    ]
    silence_starts = [
        float(value)
        for value in re.findall(r"silence_start:\s*([0-9.]+)", result.stderr)
    ]
    silence_ends = [
        (float(match.group(1)), float(match.group(2)))
        for match in re.finditer(
            r"silence_end:\s*([0-9.]+)\s*\|\s*silence_duration:\s*([0-9.]+)",
            result.stderr,
        )
    ]
    quiet = [
        {
            "start": start + quiet_start,
            "end": start + quiet_end,
            "duration": quiet_duration,
        }
        for quiet_start, (quiet_end, quiet_duration) in zip(
            silence_starts, silence_ends, strict=False
        )
    ]
    return black, quiet


def audio_levels(
    source: Path, start: float, end: float, raw_dir: Path, has_audio: bool
) -> list[dict]:
    if not has_audio:
        return []
    result = run(
        [
            "ffmpeg",
            "-hide_banner",
            "-nostats",
            *section_args(start, end),
            "-i",
            str(source),
            "-vn",
            "-af",
            (
                "aresample=48000,asetnsamples=n=24000,"
                "astats=metadata=1:reset=1,"
                "ametadata=print:key=lavfi.astats.Overall.RMS_level"
            ),
            "-f",
            "null",
            "-",
        ],
        capture=True,
        check=False,
    )
    (raw_dir / "audio-levels.log").write_text(result.stderr)
    frame_times = re.findall(r"pts_time:([0-9.]+)", result.stderr)
    rms_values = re.findall(
        r"lavfi\.astats\.Overall\.RMS_level=(-?(?:inf|[0-9.]+))", result.stderr
    )
    values: list[dict] = []
    for frame_time, rms in zip(frame_times, rms_values, strict=False):
        values.append(
            {
                "time": start + float(frame_time),
                "rms_db": None if rms == "-inf" else float(rms),
            }
        )
    return values


def beat_analysis(
    source: Path, start: float, end: float, raw_dir: Path, has_audio: bool
) -> dict | None:
    if not has_audio:
        return None
    wav = raw_dir / "analysis-audio.wav"
    run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            *section_args(start, end),
            "-i",
            str(source),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "22050",
            str(wav),
        ]
    )
    samples, sample_rate = librosa.load(wav, sr=22050, mono=True)
    onset_envelope = librosa.onset.onset_strength(y=samples, sr=sample_rate)
    tempo_value, beat_frames = librosa.beat.beat_track(
        onset_envelope=onset_envelope, sr=sample_rate
    )
    onset_frames = librosa.onset.onset_detect(
        onset_envelope=onset_envelope, sr=sample_rate, backtrack=False
    )
    tempo = float(np.asarray(tempo_value).reshape(-1)[0])
    beats = [
        start + float(value)
        for value in librosa.frames_to_time(beat_frames, sr=sample_rate)
    ]
    onsets = [
        start + float(value)
        for value in librosa.frames_to_time(onset_frames, sr=sample_rate)
    ]
    return {
        "estimated_tempo_bpm": tempo,
        "beat_times": beats,
        "onset_times": onsets,
        "warning": "Beat and onset estimates are navigation aids, especially under speech.",
    }


def parse_vtt(path: Path, range_start: float, range_end: float) -> list[Cue]:
    content = path.read_text(errors="replace")
    cues: list[Cue] = []
    timing_pattern = re.compile(
        r"(?P<start>\d{2}:\d{2}:\d{2}\.\d{3})\s+-->\s+"
        r"(?P<end>\d{2}:\d{2}:\d{2}\.\d{3})"
    )
    lines = content.splitlines()
    timing_indices = [
        index for index, line in enumerate(lines) if timing_pattern.search(line)
    ]
    for cue_index, timing_line in enumerate(timing_indices):
        match = timing_pattern.search(lines[timing_line])
        if not match:
            continue
        cue_start = parse_clock(match.group("start"))
        cue_end = parse_clock(match.group("end"))
        if cue_end - cue_start < 0.05:
            continue
        next_timing_line = (
            timing_indices[cue_index + 1]
            if cue_index + 1 < len(timing_indices)
            else len(lines)
        )
        text_lines: list[str] = []
        for line in lines[timing_line + 1 : next_timing_line]:
            cleaned = re.sub(r"<\d{2}:\d{2}:\d{2}\.\d{3}>", "", line)
            cleaned = re.sub(r"<[^>]+>", "", cleaned)
            cleaned = html.unescape(cleaned)
            cleaned = re.sub(r"\s+", " ", cleaned).strip()
            if cleaned:
                text_lines.append(cleaned)
        text = text_lines[-1] if text_lines else ""
        if text and cue_end >= range_start and cue_start <= range_end:
            cues.append({"start": cue_start, "end": cue_end, "text": text})
    deduped: list[Cue] = []
    for cue in cues:
        if deduped and cue["text"] == deduped[-1]["text"]:
            deduped[-1]["end"] = max(deduped[-1]["end"], cue["end"])
        else:
            deduped.append(cue)
    return deduped


def parse_clock(value: str) -> float:
    hours, minutes, seconds = value.split(":")
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def shot_ranges(start: float, end: float, changes: list[dict]) -> list[dict]:
    boundaries = [start]
    boundaries.extend(event["time"] for event in changes if start < event["time"] < end)
    boundaries.append(end)
    boundaries = sorted(set(boundaries))
    return [
        {
            "index": index + 1,
            "start": shot_start,
            "end": shot_end,
            "duration": shot_end - shot_start,
            "cut_in_score": (
                next(
                    (
                        event["score"]
                        for event in changes
                        if abs(event["time"] - shot_start) < 0.002
                    ),
                    None,
                )
                if index
                else None
            ),
        }
        for index, (shot_start, shot_end) in enumerate(itertools.pairwise(boundaries))
    ]


def read_frame(capture: cv2.VideoCapture, time_seconds: float) -> np.ndarray | None:
    capture.set(cv2.CAP_PROP_POS_MSEC, time_seconds * 1000)
    ok, frame = capture.read()
    return frame if ok else None


def write_representative_frames(
    source: Path, shots: list[dict], frames_dir: Path
) -> None:
    frames_dir.mkdir(parents=True, exist_ok=True)
    capture = cv2.VideoCapture(str(source))
    if not capture.isOpened():
        fail("OpenCV could not open the video")
    for shot in shots:
        midpoint = (shot["start"] + shot["end"]) / 2
        frame = read_frame(capture, midpoint)
        if frame is None:
            continue
        path = frames_dir / f"shot-{shot['index']:04d}-{midpoint:010.3f}.jpg"
        cv2.imwrite(str(path), frame, [cv2.IMWRITE_JPEG_QUALITY, 88])
        shot["representative_frame"] = str(path)
    capture.release()


def estimate_motion(source: Path, shot: dict) -> dict:
    duration = shot["duration"]
    if duration < 0.35:
        return {"label": "too short to classify", "confidence": "low"}
    capture = cv2.VideoCapture(str(source))
    times = np.linspace(
        shot["start"] + min(0.12, duration * 0.1),
        shot["end"] - min(0.12, duration * 0.1),
        num=min(10, max(3, math.ceil(duration * 2))),
    )
    frames: list[np.ndarray] = []
    for value in times:
        frame = read_frame(capture, float(value))
        if frame is not None:
            width = 640
            height = round(frame.shape[0] * width / frame.shape[1])
            frames.append(cv2.resize(frame, (width, height)))
    capture.release()
    if len(frames) < 3:
        return {"label": "insufficient frames", "confidence": "low"}

    orb = cv2.ORB_create(nfeatures=1400)
    matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
    scales: list[float] = []
    translations_x: list[float] = []
    translations_y: list[float] = []
    rotations: list[float] = []
    valid_pairs = 0
    for previous, current in itertools.pairwise(frames):
        gray_previous = cv2.cvtColor(previous, cv2.COLOR_BGR2GRAY)
        gray_current = cv2.cvtColor(current, cv2.COLOR_BGR2GRAY)
        keypoints_a, descriptors_a = orb.detectAndCompute(gray_previous, None)
        keypoints_b, descriptors_b = orb.detectAndCompute(gray_current, None)
        if descriptors_a is None or descriptors_b is None:
            continue
        matches = sorted(
            matcher.match(descriptors_a, descriptors_b), key=lambda item: item.distance
        )[:250]
        if len(matches) < 12:
            continue
        points_a = np.float32(
            [keypoints_a[item.queryIdx].pt for item in matches]
        ).reshape(-1, 1, 2)
        points_b = np.float32(
            [keypoints_b[item.trainIdx].pt for item in matches]
        ).reshape(-1, 1, 2)
        matrix, inliers = cv2.estimateAffinePartial2D(
            points_a,
            points_b,
            method=cv2.RANSAC,
            ransacReprojThreshold=3.0,
        )
        if matrix is None or inliers is None or int(inliers.sum()) < 8:
            continue
        a, b, tx = matrix[0]
        _, _, ty = matrix[1]
        scales.append(math.sqrt(float(a * a + b * b)))
        rotations.append(math.degrees(math.atan2(float(b), float(a))))
        translations_x.append(float(tx) / previous.shape[1])
        translations_y.append(float(ty) / previous.shape[0])
        valid_pairs += 1

    if valid_pairs < 2:
        return {"label": "insufficient stable features", "confidence": "low"}

    cumulative_scale = float(np.prod(scales) - 1)
    cumulative_x = float(np.sum(translations_x))
    cumulative_y = float(np.sum(translations_y))
    jitter = float(
        np.std(translations_x) + np.std(translations_y) + np.std(rotations) / 100
    )
    labels: list[str] = []
    if cumulative_scale > 0.025:
        labels.append("possible push-in")
    elif cumulative_scale < -0.025:
        labels.append("possible pull-out")
    if abs(cumulative_x) > 0.045:
        labels.append("possible pan or lateral track")
    if abs(cumulative_y) > 0.045:
        labels.append("possible tilt or vertical travel")
    if jitter > 0.025:
        labels.append("handheld or high subject motion")
    elif not labels and jitter < 0.008:
        labels.append("locked-off or stabilized")
    elif not labels:
        labels.append("subtle movement")
    return {
        "label": ", ".join(labels),
        "confidence": "medium",
        "valid_frame_pairs": valid_pairs,
        "cumulative_scale_change": cumulative_scale,
        "cumulative_x_frame_widths": cumulative_x,
        "cumulative_y_frame_heights": cumulative_y,
        "jitter_score": jitter,
        "warning": "Global feature motion can be fooled by subject motion, parallax, and lens breathing.",
    }


def ocr_frame(path: Path) -> list[dict]:
    result = run(
        ["tesseract", str(path), "stdout", "tsv"],
        capture=True,
        check=False,
    )
    rows = csv.DictReader(result.stdout.splitlines(), delimiter="\t")
    words: list[dict] = []
    for row in rows:
        confidence = float(row["conf"])
        text = row["text"].strip()
        if text and confidence >= 55:
            words.append(
                {
                    "text": text,
                    "confidence": confidence,
                    "left": int(row["left"]),
                    "top": int(row["top"]),
                    "width": int(row["width"]),
                    "height": int(row["height"]),
                }
            )
    return words


def make_contact_sheet(
    source: Path,
    destination: Path,
    start: float,
    end: float,
    frame_count: int,
) -> None:
    columns = min(6, frame_count)
    rows = math.ceil(frame_count / columns)
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
                f"scale='min(480,iw)':-2,"
                f"tile={columns}x{rows}:nb_frames={frame_count}"
            ),
            "-frames:v",
            "1",
            str(destination),
        ]
    )


def make_strip(source: Path, destination: Path, center: float) -> None:
    strip_start = max(0.0, center - 1.0)
    strip_end = center + 1.0
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
                f"trim=start={strip_start}:end={strip_end},setpts=PTS-STARTPTS,"
                "fps=6,scale='min(400,iw)':-2,tile=6x2:nb_frames=12"
            ),
            "-frames:v",
            "1",
            str(destination),
        ]
    )


def attach_cues(shots: list[dict], cues: list[Cue]) -> None:
    for shot in shots:
        shot["transcript"] = [
            cue
            for cue in cues
            if cue["end"] >= shot["start"] and cue["start"] <= shot["end"]
        ]


def write_timeline(path: Path, analysis: dict) -> None:
    shots = analysis["shots"]
    lines = [
        "# Machine evidence timeline",
        "",
        (
            "Scene boundaries, motion, beats, and OCR are candidates for human review. "
            "They are not editorial conclusions."
        ),
        "",
        "| Shot | Range | Dur. | Cut score | Motion estimate | Transcript | OCR |",
        "|---:|---|---:|---:|---|---|---|",
    ]
    for shot in shots:
        transcript = " ".join(cue["text"] for cue in shot.get("transcript", []))
        transcript = transcript.replace("|", "\\|")
        ocr = " ".join(word["text"] for word in shot.get("ocr", []))
        ocr = ocr.replace("|", "\\|")
        score = shot.get("cut_in_score")
        lines.append(
            "| "
            + " | ".join(
                [
                    str(shot["index"]),
                    f"{timestamp(shot['start'])}–{timestamp(shot['end'])}",
                    f"{shot['duration']:.3f}s",
                    "" if score is None else f"{score:.3f}",
                    shot.get("motion", {}).get("label", ""),
                    transcript[:140],
                    ocr[:80],
                ]
            )
            + " |"
        )
    path.write_text("\n".join(lines) + "\n")


def analyze(args: argparse.Namespace) -> None:
    source = args.source.expanduser().resolve()
    if not source.is_file():
        fail(f"Source not found: {source}")
    require_tools(args.ocr)
    work_dir = args.work_dir.expanduser().resolve()
    raw_dir = work_dir / "raw"
    frames_dir = work_dir / "frames"
    strips_dir = work_dir / "strips"
    for directory in (raw_dir, frames_dir, strips_dir):
        directory.mkdir(parents=True, exist_ok=True)

    payload = probe(source)
    write_json(raw_dir / "ffprobe.json", payload)
    source_duration = media_duration(payload)
    start = max(0.0, args.start)
    end = source_duration if args.end is None else min(source_duration, args.end)
    if end <= start:
        fail("Analysis end must be greater than start")
    stream = video_stream(payload)
    has_audio = bool(audio_streams(payload))

    changes = scene_changes(source, start, end, args.scene_threshold, raw_dir)
    black, quiet = interval_events(source, start, end, raw_dir, has_audio)
    levels = audio_levels(source, start, end, raw_dir, has_audio)
    beats = beat_analysis(source, start, end, raw_dir, has_audio)
    shots = shot_ranges(start, end, changes)
    cues = (
        parse_vtt(args.subtitles.expanduser().resolve(), start, end)
        if args.subtitles
        else []
    )
    attach_cues(shots, cues)
    write_representative_frames(source, shots, frames_dir)

    for shot in shots:
        shot["motion"] = estimate_motion(source, shot)
        if args.ocr and shot.get("representative_frame"):
            shot["ocr"] = ocr_frame(Path(shot["representative_frame"]))

    make_contact_sheet(
        source,
        work_dir / "contact-sheet.jpg",
        start,
        end,
        min(args.contact_frames, max(1, math.ceil(end - start))),
    )
    event_times = [event["time"] for event in changes if event["score"] >= 0.45]
    event_times.extend(event["start"] for event in black)
    event_times.extend(event["end"] for event in black)
    for index, event_time in enumerate(sorted(set(event_times)), start=1):
        make_strip(
            source,
            strips_dir / f"event-{index:03d}-{event_time:010.3f}.jpg",
            event_time,
        )

    durations = [shot["duration"] for shot in shots]
    analysis = {
        "source": str(source),
        "range": {"start": start, "end": end, "duration": end - start},
        "media": {
            "duration": source_duration,
            "width": stream.get("width"),
            "height": stream.get("height"),
            "frame_rate": stream.get("avg_frame_rate"),
            "audio_stream_count": len(audio_streams(payload)),
        },
        "detectors": {
            "scene_threshold": args.scene_threshold,
            "black": {"minimum_duration": 0.10, "pixel_threshold": 0.10},
            "silence": {"threshold_db": -38, "minimum_duration": 0.20},
            "audio_level_window_seconds": 0.50,
        },
        "summary": {
            "shot_count": len(shots),
            "average_shot_length": float(np.mean(durations)),
            "median_shot_length": float(np.median(durations)),
            "minimum_shot_length": min(durations),
            "maximum_shot_length": max(durations),
        },
        "scene_changes": changes,
        "black_intervals": black,
        "quiet_intervals": quiet,
        "audio_levels": levels,
        "beat_analysis": beats,
        "transcript_cues": cues,
        "shots": shots,
    }
    write_json(work_dir / "analysis.json", analysis)
    write_timeline(work_dir / "timeline.md", analysis)
    print(f"Wrote analysis to {work_dir}")


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(
        description="Extract machine evidence for editorial video analysis."
    )
    subparsers = value.add_subparsers(dest="command", required=True)
    analyze_parser = subparsers.add_parser("analyze")
    analyze_parser.add_argument("source", type=Path)
    analyze_parser.add_argument("--work-dir", type=Path, required=True)
    analyze_parser.add_argument("--start", type=float, default=0.0)
    analyze_parser.add_argument("--end", type=float)
    analyze_parser.add_argument("--scene-threshold", type=float, default=0.20)
    analyze_parser.add_argument("--subtitles", type=Path)
    analyze_parser.add_argument("--ocr", action="store_true")
    analyze_parser.add_argument("--contact-frames", type=int, default=48)
    analyze_parser.set_defaults(func=analyze)
    return value


def main() -> None:
    args = parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
