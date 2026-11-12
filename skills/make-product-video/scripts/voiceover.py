#!/usr/bin/env python3
"""Generate ElevenLabs voiceover clips, then check each one by transcribing it.

Input file (JSON):

    {
      "voice_id": "c6SfcYrb2t09NHXiT80T",
      "model_id": "eleven_v4",
      "voice_settings": {"stability": 0.5},
      "pronunciations": {"/luˈmɔːrə/": "Lumora"},
      "lines": [
        {"id": "v01", "text": "[confidently] We redesigned billing. [short pause] Clearer. Cleaner."},
        {"id": "v02", "text": "One page. No surprises."}
      ]
    }

Use one line holding the whole script for a single continuous take, or one line per beat.
Text may carry Eleven v4 direction tags in [square brackets]; they are removed before checking.
voice_settings and pronunciations are optional. Eleven v4 ignores speed and style; pace is set with
tags. pronunciations maps a spelling used in the text, such as an IPA
transcription between slashes, to the word a listener should hear; the check and the word timings use
that word.

For every line this writes, into the output directory:

    <id>.mp3          the audio
    <id>.raw.json     text, request fingerprint, generation alignment, transcript
    <id>.words.json   [{"w": word, "s": start seconds, "e": end seconds}], tags removed
    manifest.json     per line: duration, word count, words per minute, verified, timing source,
                      and other_events: sounds that are not words (a laugh, a sigh, an effect)

Word times come from the transcript when it matches the script word for word, otherwise from the
generation alignment. Lines whose text, voice, model and settings are unchanged are not regenerated.
Neighbouring lines are sent as context for a connected read, but a change to a neighbour does not
regenerate a line; use --force with line ids when a line should be re-read against new neighbours.

Usage:
    voiceover.py vo.json out_dir [line_id ...] [--no-verify] [--force] [--ignore-env-key]

Exit status is 1 when any checked line's words do not match its script. Tags performed as sounds are
listed in the output.
Needs ffprobe and the `elevenlabs` CLI, logged in. Set ELEVENLABS_CLI to use another binary,
for example ELEVENLABS_CLI="./node_modules/.bin/elevenlabs".
"""

import argparse
import base64
import difflib
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

REQUIRED_MODEL = "eleven_v4"
TRANSCRIBE_MODEL = "scribe_v1"


def cli_command() -> list[str]:
    override = os.environ.get("ELEVENLABS_CLI")
    if override:
        return shlex.split(override)
    found = shutil.which("elevenlabs")
    if not found:
        raise SystemExit("elevenlabs CLI not found. Install it (brew install elevenlabs/tap/elevenlabs) and run `elevenlabs auth login`.")
    return [found]


def run_cli(args: list[str], env: dict[str, str]) -> dict:
    result = subprocess.run([*cli_command(), *args, "--format", "json"], capture_output=True, text=True, stdin=subprocess.DEVNULL, env=env)
    if result.returncode != 0:
        raise SystemExit(f"elevenlabs {' '.join(args[:2])} failed ({result.returncode}):\n{result.stderr.strip() or result.stdout.strip()}")
    return json.loads(result.stdout)


def probe_duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        check=True, capture_output=True, text=True,
    )
    return float(out.stdout.strip())


def strip_tags(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"\[[^\]]*\]", " ", text)).strip()


def normalise(word: str) -> str:
    return re.sub(r"[^a-z0-9']", "", word.lower().replace("\u2019", "'"))


def alignment_words(alignment: dict) -> list[dict]:
    """Group the per-character alignment into words, leaving out [direction tags]."""
    words: list[dict] = []
    current, start, end, in_tag = "", None, 0.0, False

    def flush() -> None:
        nonlocal current, start
        if current and normalise(current):
            words.append({"w": current, "s": round(start, 3), "e": round(end, 3)})
        current, start = "", None

    for chars, char_start, char_end in zip(
        alignment["characters"], alignment["character_start_times_seconds"], alignment["character_end_times_seconds"]
    ):
        for char in chars:
            if char == "[":
                flush()
                in_tag = True
            elif char == "]":
                in_tag = False
            elif in_tag or char.isspace():
                flush()
            else:
                if start is None:
                    start = char_start
                current += char
                end = char_end
    flush()
    return words


def group_heard(want: list[str], heard: list[dict]) -> list[list[dict]] | None:
    """Give each script word the transcript words that spell it; None when a transcript word spans two script words."""
    groups, position = [], 0
    for word in want:
        group, spelled = [], ""
        while spelled != word:
            if position == len(heard) or not word.startswith(spelled):
                return None
            group.append(heard[position])
            spelled += normalise(heard[position]["text"])
            position += 1
        groups.append(group)
    return groups


def check_against_transcript(script_words: list[dict], transcript: dict) -> dict:
    heard = [item for item in transcript["words"] if item["type"] == "word" and normalise(item["text"])]
    other = [
        {"type": item["type"], "text": item["text"], "s": round(item["start"], 3), "e": round(item["end"], 3)}
        for item in transcript["words"] if item["type"] not in ("word", "spacing")
    ]
    want = [normalise(word["w"]) for word in script_words]
    got = [normalise(item["text"]) for item in heard]
    report: dict = {"other_events": other, "differences": []}
    if want == got:
        drift = max((abs(a["s"] - b["start"]) for a, b in zip(script_words, heard)), default=0.0)
        report.update(verified=True, timing_source="transcript", max_start_drift=round(drift, 3))
        report["words"] = [{"w": a["w"], "s": round(b["start"], 3), "e": round(b["end"], 3)} for a, b in zip(script_words, heard)]
        return report
    if "".join(want) == "".join(got):  # same words, split differently (for example "two-thirds" / "two thirds")
        report["verified"] = True
        grouped = group_heard(want, heard)
        if grouped:
            report["timing_source"] = "transcript"
            report["words"] = [{"w": a["w"], "s": round(g[0]["start"], 3), "e": round(g[-1]["end"], 3)} for a, g in zip(script_words, grouped)]
        else:
            report["timing_source"] = "alignment"
            report["words"] = script_words
        return report
    report["words"] = script_words
    report["timing_source"] = "alignment"
    report["verified"] = False
    matcher = difflib.SequenceMatcher(a=want, b=got, autojunk=False)
    for op, a0, a1, b0, b1 in matcher.get_opcodes():
        if op != "equal":
            report["differences"].append({"script": " ".join(want[a0:a1]), "heard": " ".join(got[b0:b1])})
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("spec", type=Path)
    parser.add_argument("out_dir", type=Path)
    parser.add_argument("line_ids", nargs="*")
    parser.add_argument("--no-verify", action="store_true", help="skip the transcription check")
    parser.add_argument("--force", action="store_true", help="regenerate even when nothing changed")
    parser.add_argument("--ignore-env-key", action="store_true", help="drop ELEVENLABS_API_KEY so the CLI login is used")
    args = parser.parse_args()

    spec = json.loads(args.spec.read_text())
    model = spec.get("model_id", REQUIRED_MODEL)
    if model != REQUIRED_MODEL:
        print(f"warning: model_id is {model}, not {REQUIRED_MODEL}.", file=sys.stderr)
    settings = spec.get("voice_settings") or {}
    ignored = sorted(set(settings) & {"speed", "style", "use_speaker_boost"})
    if model.startswith("eleven_v4") and ignored:
        print(f"warning: {model} ignores voice_settings {', '.join(ignored)}. Set pace and delivery with tags in the text.", file=sys.stderr)
    pronunciations = spec.get("pronunciations") or {}
    env = dict(os.environ)
    if args.ignore_env_key:
        env.pop("ELEVENLABS_API_KEY", None)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    lines = spec["lines"]
    manifest, failed = [], []

    for index, line in enumerate(lines):
        audio_path = args.out_dir / f"{line['id']}.mp3"
        raw_path = args.out_dir / f"{line['id']}.raw.json"
        request = {
            "voice_id": spec["voice_id"],
            "model_id": model,
            "text": line["text"],
            "voice_settings": settings,
            "previous_text": strip_tags(lines[index - 1]["text"]) if index > 0 else None,
            "next_text": strip_tags(lines[index + 1]["text"]) if index + 1 < len(lines) else None,
        }
        cache_key = {key: request[key] for key in ("voice_id", "model_id", "text", "voice_settings")}
        fingerprint = hashlib.sha256(json.dumps(cache_key, sort_keys=True).encode()).hexdigest()
        raw = json.loads(raw_path.read_text()) if raw_path.exists() else None
        wanted = not args.line_ids or line["id"] in args.line_ids
        stale = not (raw and raw["fingerprint"] == fingerprint and audio_path.exists())
        if wanted and (stale or args.force):
            command = [
                "text-to-speech", "convert_with_timestamps",
                "--voice-id", request["voice_id"], "--model-id", model, "--text", request["text"],
            ]
            if settings:
                command += ["--voice-settings", json.dumps(settings)]
            if request["previous_text"]:
                command += ["--previous-text", request["previous_text"]]
            if request["next_text"]:
                command += ["--next-text", request["next_text"]]
            payload = run_cli(command, env)
            audio_path.write_bytes(base64.b64decode(payload["audio_base64"]))
            raw = {"fingerprint": fingerprint, "text": line["text"], "alignment": payload["alignment"]}
            raw_path.write_text(json.dumps(raw))
            print(f"generated {line['id']}")
        if raw is None:
            print(f"{line['id']}: not generated yet, skipped")
            continue

        script_words = alignment_words(raw["alignment"])
        for word in script_words:
            for written, spoken in pronunciations.items():
                word["w"] = word["w"].replace(written, spoken)
        entry = {"id": line["id"], "text": line["text"], "duration": round(probe_duration(audio_path), 3), "words": len(script_words)}
        if args.no_verify:
            words, entry["verified"], entry["timing_source"] = script_words, None, "alignment"
        else:
            if "transcript" not in raw:
                raw["transcript"] = run_cli(
                    ["speech-to-text", "convert", "--model-id", TRANSCRIBE_MODEL, "--file", str(audio_path),
                     "--tag-audio-events", "true", "--timestamps-granularity", "word"],
                    env,
                )
                raw_path.write_text(json.dumps(raw))
            report = check_against_transcript(script_words, raw["transcript"])
            words = report.pop("words")
            entry.update(report)
            if not report["verified"]:
                failed.append(line["id"])
        (args.out_dir / f"{line['id']}.words.json").write_text(json.dumps(words))
        spoken = words[-1]["e"] - words[0]["s"] if words else 0.0
        entry["words_per_minute"] = round(len(words) / spoken * 60) if spoken > 0 else None
        manifest.append(entry)
        mark = {True: "ok", False: "MISMATCH", None: "unchecked"}[entry["verified"]]
        print(f"{line['id']} {entry['duration']:6.2f}s {entry['words']:3d} words {mark:9s} {strip_tags(line['text'])[:60]}")
        for difference in entry.get("differences", []):
            print(f"    script: {difference['script']!r}  heard: {difference['heard']!r}")
        for event in entry.get("other_events", []):
            print(f"    non-speech sound heard: {event['text']} at {event['s']:.2f}-{event['e']:.2f}s")

    (args.out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"total audio {sum(item['duration'] for item in manifest):.2f}s")
    if failed:
        raise SystemExit(f"transcript does not match the script for: {', '.join(failed)}")


if __name__ == "__main__":
    main()
