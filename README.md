# Video Editing Skills

[![skills.sh](https://skills.sh/b/gitethanwoo/video-editing)](https://skills.sh/gitethanwoo/video-editing)

General-purpose skills and deterministic tools for understanding and editing arbitrary videos.

## Skills

| Skill | Use it for |
|---|---|
| `analyze-video-editing` | Reverse-engineering shots, camera motion, titles, dialogue, music, sound design, pacing, and editorial structure |
| `find-broll` | Planning, sourcing, vetting, approving, and precisely placing authoritative B-roll against spoken words |
| `make-product-video` | Narrated product demos, walkthroughs, sizzle reels, and launch videos with ElevenLabs voiceover, music, and sound effects |
| `record-agent-browser-demo` | Recording rehearsed, review-ready web app walkthroughs with Agent Browser, with frame QA and optional GitHub attachment |
| `video-editing` | Cutting footage, compositing multiple sources, mixing audio, creating React/SVG/Remotion graphics, rendering, reviewing, and validating deliverables |

The repository deliberately separates analysis, sourcing, and production. Reference films become evidence and transferable principles; B-roll choices retain provenance and approval state; rendering remains deterministic and validated.

## Install

List the available skills:

```bash
npx skills add gitethanwoo/video-editing --list
```

Install all skills:

```bash
npx skills add gitethanwoo/video-editing
```

Or install one:

```bash
npx skills add gitethanwoo/video-editing --skill analyze-video-editing
npx skills add gitethanwoo/video-editing --skill find-broll
npx skills add gitethanwoo/video-editing --skill make-product-video
npx skills add gitethanwoo/video-editing --skill record-agent-browser-demo
npx skills add gitethanwoo/video-editing --skill video-editing
```

The open [`skills`](https://github.com/vercel-labs/skills) CLI supports Codex, Claude Code, Cursor, OpenCode, and other agents.

## What is included

- Source probing, checksums, contact sheets, event strips, and representative stills
- Shot-boundary, black-frame, quiet-interval, audio-level, beat, motion, subtitle, and optional OCR evidence
- Optional Gemini semantic audio analysis paired with spectrogram and loudness verification
- Transcript-first B-roll routing, provenance manifests, exact-word timing, and source-aware review
- A generic FFmpeg render-plan runner with candidate validation and reversible output promotion
- A typed Remotion starter for full-frame edits and transparent ProRes 4444 overlays
- Quality gates for geometry, duration, codec, frame rate, audio sample rate, loudness, full decode, and checksums

## Requirements

- Python 3.11 or newer
- [FFmpeg](https://ffmpeg.org/) and FFprobe
- [`uv`](https://docs.astral.sh/uv/) for the analysis script's declared Python dependencies
- Node.js and npm only when using the Remotion motion-graphics starter
- Node.js 22.20 or newer when installing through the current `skills` CLI
- `GEMINI_API_KEY` only for optional semantic audio listening
- Tesseract only when using optional frame OCR
- `mlx-whisper` only for optional Apple Silicon speech transcription
- `yt-dlp` only for authorized reference downloads
- A browser only when capturing or verifying public pages for B-roll
- The [`agent-browser`](https://github.com/vercel-labs/agent-browser) CLI only for recording web app demos
- The `elevenlabs` CLI, logged in, only for product-video voiceover, music, and sound effects

The bundled scripts inspect real media payloads before constructing timelines or parsing outputs. Model descriptions are treated as hypotheses whenever deterministic signal evidence disagrees.

Keep private footage and generated transcripts local unless the owner has explicitly authorized upload or publication. Download reference media only when permitted. The Remotion starter uses Remotion under its own licensing terms; consult [NOTICE.md](NOTICE.md) before commercial use.

## Development

```bash
npx skills add . --list
python3 skills/video-editing/tests/smoke_test.py
python3 skills/analyze-video-editing/tests/smoke_test.py
```

## License

MIT
