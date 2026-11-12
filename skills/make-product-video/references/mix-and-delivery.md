# Mix and delivery

## Mix

Render the picture silent, mix with `scripts/mix.py`, and mux at the end. A sound change then needs no picture render, and each stem can be measured alone.

```bash
python3 scripts/mix.py mix mix.json
python3 scripts/mix.py master mix.json render/picture.mp4 output/film.mp4
```

The `mix.py` docstring documents `mix.json`. `master` stops if the picture and the mix differ in length.

## Starting levels

| Part | Setting |
| --- | --- |
| Each voice clip | levelled to -26 LUFS before the bus, so lines match each other |
| Voice bus | 70 Hz high-pass, 3:1 compressor, +11 dB, limiter at about -3 dBFS |
| Music under voice | linear gain 0.36, sidechain-ducked by the voice: threshold 0.02, ratio 2.2, attack 25 ms, release 450 ms |
| Music with no voice | gain 0.5 in a sparse opening, about 0.6 after the last line |
| Sound effects | peak-normalised, then -15 to -21 dB |
| Master | -16 LUFS integrated, limiter ceiling about -2 dBFS, AAC 256k, 48 kHz |

These give stems around -16 LUFS for voice, -27 for music and -32 for effects.

- **Walkthrough:** long stretches of talk over one bed. Duck harder (ratio near 8, release 600 ms), keep the bed at 0.3, and fade it out over the last four seconds.
- **Element film:** a quiet bed, about half these levels.

To lengthen a cue, repeat one of its phrases with FFmpeg (`atrim` and `concat` on phrase boundaries).

## Listening

Send the user the film, or an excerpt:

```bash
ffmpeg -ss 10 -t 20 -i output/film.mp4 -vn -c:a aac -b:a 160k output/listen-10s.m4a
```

## Validate

```bash
python3 video_workbench.py validate output/film.mp4 --width 1920 --height 1080 --fps 30 --audio-rate 48000 --lufs -16
python3 video_workbench.py sheet output/film.mp4 review/sheet.jpg --frames 24
```

`video_workbench.py` is in the `video-editing` skill's `scripts/` folder. Stills at each voice line's start time show whether the thing being named is on screen.

## File sizes

A 90 second 1080p master is about 40 MB. Uploads often cap file size: around 10 MB for some browser and agent upload paths, 25 to 30 MB for chat attachments. `fit_size.py` makes a copy under a limit:

```bash
python3 scripts/fit_size.py output/film.mp4 output/film-10mb.mp4 --mb 10
```

At 10 MB a 90 second 1080p film gets about 725 kbit/s of video, and interface text stays readable. `--height 720` suits longer films.
