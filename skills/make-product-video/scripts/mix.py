#!/usr/bin/env python3
"""Mix voiceover, a music bed and sound effects, then master the mix onto a silent picture render.

    mix.py mix mix.json                               write stems and premix.wav
    mix.py master mix.json picture.mp4 out.mp4        gain to the target loudness, limit, mux

mix.json (file paths are relative to the JSON file; every section except "total" is optional):

    {
      "total": 86.4,
      "out": "render",
      "vo": {
        "dir": "vo",
        "clips": {"v01": 1.4, "v02": 11.55},
        "clip_lufs": -26.0,
        "gain_db": 11.0
      },
      "music": {
        "file": "music/bed.mp3",
        "trim": 4.8,
        "fade_in": 0.5,
        "gain_points": [[0, 0.5], [13.6, 0.5], [14.45, 0.36], [81.5, 0.36], [82.7, 0.6]],
        "fade_out": [85.2, 1.2],
        "duck": {"threshold": 0.02, "ratio": 2.2, "attack": 25, "release": 450}
      },
      "sfx": [
        {"file": "sfx/whoosh-soft.mp3", "at": 14.38, "gain_db": -19.0, "fade_in": 0.06}
      ],
      "master": {"lufs": -16.0, "ceiling": 0.79}
    }

vo.clips maps <id> (the file <dir>/<id>.mp3) to its start time in seconds. Every clip is first levelled to
clip_lufs so lines match each other, then the voice bus is compressed, raised by gain_db and limited.
music.gain_points is a list of [time, linear gain] joined by straight ramps; music.trim skips the start of
the file. The bed is ducked by the voice through a sidechain compressor. Each effect is peak-normalised,
then set to gain_db.

`mix` writes <out>/premix.wav plus stem-vo.wav, stem-music.wav and stem-sfx.wav (48 kHz stereo, exactly
"total" seconds) and prints the loudness of each. `master` measures the premix, applies one gain and a
limiter to reach master.lufs, muxes with the picture as AAC 256k, and prints the result's loudness and peak.
It stops if the picture and the premix differ in length by more than 0.1 s.
"""

import argparse
import json
import re
import subprocess
from pathlib import Path

FORMAT = "aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo"
DUCK = {"threshold": 0.02, "ratio": 2.2, "attack": 25, "release": 450}


def analyse(path: Path, filters: list[str]) -> str:
    result = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-vn", "-af", ",".join(filters), "-f", "null", "-"],
        capture_output=True, text=True, check=True,
    )
    return result.stderr


def loudness(path: Path, before: list[str] | None = None) -> tuple[float, float]:
    """Integrated loudness (LUFS) and true peak (dBFS)."""
    log = analyse(path, [*(before or []), "ebur128=peak=true"])
    integrated = float(re.findall(r"I:\s+(-?[\d.]+) LUFS", log)[-1])
    peak = float(re.findall(r"Peak:\s+(-?[\d.]+|-inf) dBFS", log)[-1])
    return integrated, peak


def duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        check=True, capture_output=True, text=True,
    )
    return float(out.stdout.strip())


def sample_peak(path: Path) -> float:
    return float(re.search(r"max_volume: (-?[\d.]+) dB", analyse(path, ["volumedetect"])).group(1))


def gain_expression(points: list[list[float]]) -> str:
    """Piecewise-linear gain over time as an ffmpeg expression (commas escaped for a filtergraph)."""
    expression = f"{points[0][1]}"
    for (t0, g0), (t1, g1) in zip(points, points[1:]):
        if t1 <= t0:
            raise SystemExit(f"music.gain_points times must increase: {t0} then {t1}")
        expression += f"+{g1 - g0}*clip((t-{t0})/{t1 - t0}\\,0\\,1)"
    return expression


def mix(config: dict, base: Path) -> None:
    total = config["total"]
    out = base / config.get("out", "render")
    out.mkdir(parents=True, exist_ok=True)
    inputs: list[str] = []
    chains: list[str] = []
    buses: list[str] = []
    stems: list[tuple[str, str]] = []

    def add_input(path: Path) -> int:
        inputs.extend(["-i", str(path)])
        return len(inputs) // 2 - 1

    vo = config.get("vo")
    music = config.get("music")
    if vo:
        labels = []
        for name, start in vo["clips"].items():
            clip = base / vo.get("dir", "vo") / f"{name}.mp3"
            level = vo.get("clip_lufs", -26.0) - loudness(clip)[0]
            chains.append(f"[{add_input(clip)}:a]{FORMAT},volume={level:.1f}dB,adelay={round(start * 1000)}:all=1[vo_{name}]")
            labels.append(f"[vo_{name}]")
        outputs = "[vo_mix][vo_stem]" + ("[vo_key]" if music else "")
        chains.append(
            f"{''.join(labels)}amix=inputs={len(labels)}:normalize=0,highpass=f=70,"
            f"acompressor=threshold=0.1:ratio=3:attack=5:release=100:makeup=1,volume={vo.get('gain_db', 11.0)}dB,"
            f"alimiter=limit=0.71:attack=4:release=80:level=0,apad,atrim=0:{total},asplit={3 if music else 2}{outputs}"
        )
        buses.append("[vo_mix]")
        stems.append(("vo_stem", "stem-vo"))

    if music:
        chain = f"[{add_input(base / music['file'])}:a]{FORMAT},atrim=start={music.get('trim', 0)},asetpts=PTS-STARTPTS"
        if music.get("fade_in"):
            chain += f",afade=t=in:d={music['fade_in']}"
        points = music.get("gain_points") or [[0, music.get("gain", 0.36)]]
        chain += f",volume='{gain_expression(points)}':eval=frame,apad,atrim=0:{total}"
        if vo:
            duck = {**DUCK, **music.get("duck", {})}
            chains.append(chain + "[bed]")
            chain = (
                f"[bed][vo_key]sidechaincompress=threshold={duck['threshold']}:ratio={duck['ratio']}:"
                f"attack={duck['attack']}:release={duck['release']}:makeup=1"
            )
        if music.get("fade_out"):
            start, length = music["fade_out"]
            chain += f",afade=t=out:st={start}:d={length}"
        chains.append(chain + ",asplit=2[music_mix][music_stem]")
        buses.append("[music_mix]")
        stems.append(("music_stem", "stem-music"))

    effects = config.get("sfx") or []
    if effects:
        labels = []
        for number, effect in enumerate(effects):
            path = base / effect["file"]
            level = effect.get("gain_db", -18.0) - sample_peak(path)
            fade = f"afade=t=in:d={effect['fade_in']}," if effect.get("fade_in") else ""
            chains.append(f"[{add_input(path)}:a]{FORMAT},{fade}volume={level:.1f}dB,adelay={round(effect['at'] * 1000)}:all=1[sfx_{number}]")
            labels.append(f"[sfx_{number}]")
        chains.append(f"{''.join(labels)}amix=inputs={len(labels)}:normalize=0,apad,atrim=0:{total},asplit=2[sfx_mix][sfx_stem]")
        buses.append("[sfx_mix]")
        stems.append(("sfx_stem", "stem-sfx"))

    if not buses:
        raise SystemExit("mix.json has no vo, music or sfx section")
    chains.append(f"{''.join(buses)}amix=inputs={len(buses)}:normalize=0,atrim=0:{total}[premix]")
    command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *inputs, "-filter_complex", ";".join(chains)]
    for label, name in [("premix", "premix"), *stems]:
        command += ["-map", f"[{label}]", "-c:a", "pcm_f32le", "-ar", "48000", str(out / f"{name}.wav")]
    subprocess.run(command, check=True)
    for name in ["premix", *(name for _, name in stems)]:
        integrated, peak = loudness(out / f"{name}.wav")
        print(f"{name:11s} {integrated:6.1f} LUFS  peak {peak:5.1f} dBFS")


def master(config: dict, base: Path, picture: Path, output: Path) -> None:
    settings = config.get("master", {})
    target, ceiling = settings.get("lufs", -16.0), settings.get("ceiling", 0.79)
    premix = base / config.get("out", "render") / "premix.wav"
    picture_length, mix_length = duration(picture), duration(premix)
    if abs(picture_length - mix_length) > 0.1:
        raise SystemExit(
            f"picture is {picture_length:.2f}s but the premix is {mix_length:.2f}s. "
            'Set "total" in the mix file to the picture\'s length and run `mix` again.'
        )
    limiter = f"alimiter=limit={ceiling}:attack=4:release=80:level=0"
    # Limiting pulls the loudness down slightly, so measure through the limiter and correct once.
    gain = target - loudness(premix)[0]
    gain += target - loudness(premix, [f"volume={gain:.2f}dB", limiter])[0]
    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(picture), "-i", str(premix),
            "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-af", f"volume={gain:.2f}dB,{limiter}",
            "-c:a", "aac", "-b:a", "256k", "-ar", "48000", "-movflags", "+faststart", "-shortest", str(output),
        ],
        check=True,
    )
    integrated, peak = loudness(output)
    print(f"master gain {gain:+.2f} dB -> {output}: {integrated:.1f} LUFS, true peak {peak:.1f} dBFS")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    mix_parser = commands.add_parser("mix")
    mix_parser.add_argument("config", type=Path)
    master_parser = commands.add_parser("master")
    master_parser.add_argument("config", type=Path)
    master_parser.add_argument("picture", type=Path)
    master_parser.add_argument("output", type=Path)
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    base = args.config.resolve().parent
    if args.command == "mix":
        mix(config, base)
    else:
        master(config, base, args.picture, args.output)


if __name__ == "__main__":
    main()
