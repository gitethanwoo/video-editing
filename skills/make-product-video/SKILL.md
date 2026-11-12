---
name: make-product-video
description: Make a narrated product video from a working app, such as a demo, walkthrough, how-to tutorial, sizzle reel, launch video or feature announcement. Picture comes from agent-browser recordings or Remotion; voiceover (Eleven v4), music and sound effects come from the ElevenLabs CLI. Covers four styles, v4 voice direction, mixing and delivery.
---

# Make a product video

This skill helps produce narrated product videos. It leans on two other skills:

- `record-agent-browser-demo` (this repository) for recording real UI with the `agent-browser` CLI.
- `video-editing` (this repository) for contact sheets, the Remotion starter (`video_workbench.py init-motion`) and validating the final file (`video_workbench.py validate`).

## Styles

There are four. They differ in where the picture comes from, how long they run, and what drives the timing.

| Style | What the viewer sees | Typical length | Picture source | Timing follows |
| --- | --- | --- | --- | --- |
| **Walkthrough** | Whole real screens, flows played start to finish, a title card per act | 2 to 6 minutes | Screen recordings of the running app | Each recorded segment is sped up or held to fit its narration line |
| **Sizzle reel** | Real screens inside a designed frame, camera moves, a few title lines | 60 to 90 seconds | Screen recordings composited in Remotion | Scenes sit on the music's phrases; voice lines are placed in them |
| **Element film** | One thing at a time, centered on a plain background: a line of text or a single UI element lifted out of the product | 20 to 60 seconds | The element rebuilt as React/SVG in Remotion | Every animation is keyed to a word in the voiceover |
| **Tutorial** | The real product doing one task, from navigation to result, with zooms, rings on what changed and numbered step chips | 45 to 75 seconds | One scripted take, captured as timestamped frames, composited in Remotion | Each step's footage is retimed to its voice line from marks logged during the take |

[references/styles.md](references/styles.md) describes how each one is built.

## Order of work

1. **One sentence.** What the viewer should believe afterwards, and who the viewer is.
2. **Script.** About 150 to 160 spoken words per minute. Share it with the user.
3. **Silent cut.** Picture only: a rough Remotion render, or a contact sheet of recorded takes for a walkthrough. A sizzle reel also gets a draft music cue here, since its scenes cut on the music's phrases.
4. **Voice sample.** 15 to 20 seconds of the script in the chosen voice, for the user to hear.
5. **Voiceover.** `scripts/voiceover.py` generates it and checks it against the script by transcription.
6. **Re-time** the picture to the voiceover.
7. **Music** at the final length.
8. **Mix and master** with `scripts/mix.py`.
9. **Deliver** the master and any smaller copies the destination needs.

Agents can't hear the result. The user's ears are the check on voice, music and effects, so send them the voice sample and the first full mix.

## Voice

Voiceover uses `eleven_v4`. v4 has no speed setting and no SSML; pace, pauses and delivery are written into the text as tags. [references/voice-music-sfx.md](references/voice-music-sfx.md) covers tags, music and sound effects.

## Timing

Timings come from the generated audio. `voiceover.py` writes each clip's length to `manifest.json` and its word times to `<id>.words.json`. Keep scene times, clip start times and the total length in one timeline file, and generate both the picture's timing and the mix file from it.

## Scripts

Plain Python 3, in this skill's `scripts/` folder. They need `ffmpeg`; `voiceover.py` also needs the `elevenlabs` CLI, logged in. Each docstring describes its input file.

```bash
python3 scripts/voiceover.py vo.json vo/                                  # generate, transcribe, check, write word timings
python3 scripts/mix.py mix mix.json                                       # stems and premix
python3 scripts/mix.py master mix.json picture.mp4 output/film.mp4        # loudness, limiter, mux
python3 scripts/fit_size.py output/film.mp4 output/film-10mb.mp4 --mb 10  # a copy under a size limit
```

[references/mix-and-delivery.md](references/mix-and-delivery.md) has starting levels, validation and file sizes.
