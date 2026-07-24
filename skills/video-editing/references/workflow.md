# General editing workflow

## 1. Establish the brief

Identify audience, destination, aspect ratio, target length, desired tone, must-keep content, and whether the user expects a rough cut or polished master. Do not invent requirements that the delivery platform does not impose.

## 2. Observe the sources

Probe every file and keep the raw payload. Review contact sheets and listen to representative audio. Check rotation, variable frame rate, color range, clipped highlights, dropped frames, background noise, and whether multiple audio tracks have distinct roles.

If sources must synchronize, record both the numeric offset and the cue that proves it. A visible clap, tap, UI state change, or matching waveform is evidence; simultaneous creation dates are not.

## 3. Create an edit map

Keep three concepts separate:

- source selects: intervals from original files;
- output beats: semantic moments in the finished story;
- tracks: picture, inserts, graphics, captions, dialogue, music, and effects.

Start with content and pacing. Styling unstable timing wastes work.

## 4. Pick an engine

FFmpeg is ideal when the edit is primarily media transforms. Remotion is ideal when layout, typography, SVG, data, or browser rendering is central. A transparent overlay bridges them without forcing either tool to do the other's job.

## 5. Review progressively

Review source sheets, an assembly, a low-resolution draft, transition strips, representative stills, and only then the final. Review at delivery size and with sound.

Ask an independent reviewer to look for concrete problems: wrong content, broken continuity, unreadable text, sync drift, clipping, masks, ghosting, unexpected holds, and layout hierarchy.

## 6. Render and validate

Render to a candidate path. Fully decode it, inspect the actual output streams, verify the delivery contract, measure loudness when relevant, and compute a checksum. Promote only after it passes. Archive an existing target rather than deleting it.

## Handoff

Deliver:

- master video;
- edit source or render plan;
- source report and sync evidence;
- contact sheet, transition strips, and representative stills;
- validation report and checksum;
- fonts, graphics, prompts, and licensed asset provenance needed to reproduce the result.
