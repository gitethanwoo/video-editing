#!/usr/bin/env python3
"""Prepare audio evidence and optionally request a semantic editorial analysis."""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

INTERACTIONS_URL = "https://generativelanguage.googleapis.com/v1beta/interactions"
MAX_INLINE_AUDIO_BYTES = 14 * 1024 * 1024

MOVEMENT_PROMPT = """
Analyze this complete audio excerpt as an experienced film editor. Produce a
chronological timeline with timestamps relative to the excerpt. Track each
distinct music cue across the entire excerpt, including where it begins,
whether the same cue continues beneath dialogue and scene changes, changes in
intensity or instrumentation, and the exact nature and duration of its ending.
Separately identify dialogue, ambience, silence, sound effects, hard audio
cuts, fades, and audio bridges. Explain how sound motivates or extends edit
transitions. Describe only audible evidence, label genuine uncertainty, and do
not infer visual content.
""".strip()

TRANSITION_PROMPT = """
Perform a high-sensitivity analysis of this audio excerpt around an editorial
transition. Monitor the very quiet tail instead of treating low-level material
as silence. Track music, spoken words, tonal or reverberant residue, ambience,
sound effects, and actual silence second by second. Determine whether the same
musical material persists after its obvious full-volume portion, and precisely
characterize whether its end is a hard cut or gradual fade. Give timestamps
relative to the excerpt, state confidence for ambiguous low-level sounds, and
do not invent visual events.
""".strip()


def fail(message: str) -> None:
    raise SystemExit(message)


def run(
    command: list[str], *, capture: bool = False
) -> subprocess.CompletedProcess[str]:
    print("$", shlex.join(command), file=sys.stderr, flush=True)
    return subprocess.run(command, check=True, text=True, capture_output=capture)


def require_tools() -> None:
    missing = [tool for tool in ("ffmpeg", "ffprobe") if shutil.which(tool) is None]
    if missing:
        fail(f"Missing required tools: {', '.join(missing)}")


def probe(source: Path) -> dict:
    result = run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_format",
            "-show_streams",
            "-of",
            "json",
            str(source),
        ],
        capture=True,
    )
    payload = json.loads(result.stdout)
    if not isinstance(payload, dict):
        fail("Unexpected ffprobe payload type")
    streams = payload.get("streams")
    media_format = payload.get("format")
    if not isinstance(streams, list) or not isinstance(media_format, dict):
        fail("Unexpected ffprobe response shape")
    if not any(
        isinstance(stream, dict) and stream.get("codec_type") == "audio"
        for stream in streams
    ):
        fail("Source has no audio stream")
    return payload


def media_duration(payload: dict) -> float:
    media_format = payload["format"]
    value = media_format.get("duration")
    if not isinstance(value, str):
        fail("Source has no format duration")
    return float(value)


def timestamp(value: float) -> str:
    total_seconds = max(0, round(value))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return (
        f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        if hours
        else f"{minutes:02d}:{seconds:02d}"
    )


def extract_audio(source: Path, destination: Path, start: float, end: float) -> None:
    run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-ss",
            f"{start:.6f}",
            "-t",
            f"{end - start:.6f}",
            "-i",
            str(source),
            "-vn",
            "-ac",
            "2",
            "-ar",
            "44100",
            "-b:a",
            "192k",
            str(destination),
        ]
    )


def render_spectrogram(audio: Path, destination: Path) -> None:
    run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(audio),
            "-filter_complex",
            "showspectrumpic=s=1600x900:legend=1:color=rainbow:scale=log:win_func=hann",
            "-frames:v",
            "1",
            str(destination),
        ]
    )


def measure_levels(audio: Path) -> list[dict]:
    result = run(
        [
            "ffmpeg",
            "-hide_banner",
            "-nostats",
            "-i",
            str(audio),
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
    )
    frame_times = re.findall(r"pts_time:([0-9.]+)", result.stderr)
    rms_values = re.findall(
        r"lavfi\.astats\.Overall\.RMS_level=(-?(?:inf|[0-9.]+))",
        result.stderr,
    )
    return [
        {
            "time": float(frame_time),
            "rms_db": None if rms == "-inf" else float(rms),
        }
        for frame_time, rms in zip(frame_times, rms_values, strict=False)
    ]


def request_analysis(api_key: str, model: str, prompt: str, audio: Path) -> dict:
    encoded_audio = base64.b64encode(audio.read_bytes()).decode("ascii")
    request_payload = {
        "model": model,
        "input": [
            {"type": "text", "text": prompt},
            {
                "type": "audio",
                "data": encoded_audio,
                "mime_type": "audio/mp3",
            },
        ],
    }
    request = urllib.request.Request(
        INTERACTIONS_URL,
        data=json.dumps(request_payload).encode("utf-8"),
        headers={
            "content-type": "application/json",
            "x-goog-api-key": api_key,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        fail(f"Gemini request failed with HTTP {error.code}: {detail}")
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        fail("Unexpected Gemini payload type")
    return payload


def model_text(payload: dict) -> str:
    if payload.get("status") != "completed":
        fail(f"Gemini interaction did not complete: {payload.get('status')}")
    steps = payload.get("steps")
    if not isinstance(steps, list):
        fail("Unexpected Gemini response: steps is not a list")
    parts: list[str] = []
    for step in steps:
        if not isinstance(step, dict) or step.get("type") != "model_output":
            continue
        content = step.get("content")
        if not isinstance(content, list):
            fail("Unexpected Gemini model output: content is not a list")
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text = item.get("text")
                if not isinstance(text, str):
                    fail("Unexpected Gemini text content")
                parts.append(text)
    if not parts:
        fail("Gemini response contained no model text")
    return "\n\n".join(parts)


def listen(args: argparse.Namespace) -> None:
    require_tools()
    source = args.source.expanduser().resolve()
    if not source.is_file():
        fail(f"Source not found: {source}")
    work_dir = args.work_dir.expanduser().resolve()
    work_dir.mkdir(parents=True, exist_ok=True)

    payload = probe(source)
    duration = media_duration(payload)
    start = max(0.0, args.start)
    end = duration if args.end is None else min(duration, args.end)
    if end <= start:
        fail("End must be greater than start")

    excerpt = work_dir / "audio-excerpt.mp3"
    spectrogram = work_dir / "spectrogram.png"
    levels_path = work_dir / "audio-levels.json"
    extract_audio(source, excerpt, start, end)
    render_spectrogram(excerpt, spectrogram)
    levels = measure_levels(excerpt)
    levels_path.write_text(json.dumps(levels, indent=2) + "\n")

    metadata = {
        "source": str(source),
        "range": {
            "start": start,
            "end": end,
            "duration": end - start,
            "start_timestamp": timestamp(start),
            "end_timestamp": timestamp(end),
        },
        "audio_excerpt": str(excerpt),
        "spectrogram": str(spectrogram),
        "audio_levels": str(levels_path),
    }
    (work_dir / "evidence.json").write_text(json.dumps(metadata, indent=2) + "\n")

    if args.prepare_only:
        print(json.dumps(metadata, indent=2))
        return

    if excerpt.stat().st_size > MAX_INLINE_AUDIO_BYTES:
        fail(
            "Extracted audio is too large for an inline request. "
            "Analyze a narrower range."
        )
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        fail("GEMINI_API_KEY is required unless --prepare-only is used")

    prompt = MOVEMENT_PROMPT if args.mode == "movement" else TRANSITION_PROMPT
    if args.question:
        prompt = f"{prompt}\n\nAdditional editorial question:\n{args.question.strip()}"
    prompt = (
        f"Source excerpt: {timestamp(start)}–{timestamp(end)} "
        f"({end - start:.3f} seconds).\n\n{prompt}"
    )
    response = request_analysis(api_key, args.model, prompt, excerpt)
    raw_path = work_dir / "semantic-audio.raw.json"
    raw_path.write_text(json.dumps(response, indent=2) + "\n")
    text = model_text(response)
    markdown_path = work_dir / "semantic-audio.md"
    markdown_path.write_text(
        "\n".join(
            [
                "# Semantic audio analysis",
                "",
                f"- Model: `{args.model}`",
                f"- Source: `{source}`",
                f"- Range: {timestamp(start)}–{timestamp(end)}",
                "",
                text,
                "",
                "## Verification reminder",
                "",
                (
                    "Compare claims about continuity, silence, ambience, and fades "
                    "with `spectrogram.png` and `audio-levels.json`."
                ),
                "",
            ]
        )
    )
    result = {
        **metadata,
        "model": args.model,
        "raw_response": str(raw_path),
        "semantic_analysis": str(markdown_path),
    }
    print(json.dumps(result, indent=2))


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("source", type=Path)
    value.add_argument("--work-dir", type=Path, required=True)
    value.add_argument("--start", type=float, default=0.0)
    value.add_argument("--end", type=float)
    value.add_argument(
        "--mode",
        choices=("movement", "transition"),
        default="movement",
    )
    value.add_argument("--model", default="gemini-3.6-flash")
    value.add_argument("--question")
    value.add_argument("--prepare-only", action="store_true")
    return value


def main() -> None:
    listen(parser().parse_args())


if __name__ == "__main__":
    main()
