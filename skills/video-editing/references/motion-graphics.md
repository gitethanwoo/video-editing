# HTML, React, SVG, and Remotion graphics

Use the bundled starter for full-frame graphics or transparent overlays:

```bash
python3 "$SKILL_DIR/scripts/video_workbench.py" init-motion ./motion
cd motion
npm install
npm run dev
```

## Model

Keep composition settings, design tokens, media paths, and edit beats in typed data. Components own local animation; the timeline owns sequencing. Use local assets with known dimensions and duration.

The starter resolves `media.video`, `media.image`, and `media.audio` with Remotion's `staticFile()`. Those paths are relative to the project's `public/` directory, such as `media/clip.mp4`; copy or link inspected local assets there before rendering. Visual video layers are muted by default so audio ownership stays explicit. Add an `Audio` layer when source sound should be heard.

Drive all motion from `useCurrentFrame()` and the composition frame rate. Use `interpolate()`, `spring()`, and SVG path or mask animation. Do not use CSS keyframes, transitions, timers, wall-clock time, runtime network calls, or unseeded randomness.

React layout and inline SVG are good for:

- titles, lower thirds, captions, and callouts;
- diagrams, charts, maps, and data-driven graphics;
- device or browser interface treatments;
- masks, paths, highlights, and animated typography;
- mixed footage and designed panels.

## Output modes

`npm run render:video` creates an opaque H.264 master.

`npm run render:overlay` uses `project.overlay.example.json` to create a silent transparent ProRes 4444 `.mov` with PNG frame rendering and an alpha-capable pixel format. Composite that file over footage in FFmpeg or another editor. Keep `transparent: true` and a null canvas background in overlay props; a normal full-frame props file can otherwise flatten the alpha channel.

Render stills and short frame ranges before a full sequence:

```bash
npx remotion still src/index.ts VideoEdit output/frame-120.png --frame=120
npx remotion render src/index.ts VideoEdit output/range.mp4 --props=project.example.json --frames=100-160
```

## Performance

Resize media that materially exceeds delivery resolution. Avoid huge SVG node counts, full-frame blur on every layer, and repeated per-frame parsing. Test the heaviest representative range at target resolution early.

## Verification

Typecheck, render key stills, inspect transparency against checkerboard and light/dark footage, render transition ranges, then render a draft and master. Probe the overlay and require ProRes 4444 plus an alpha-capable pixel format. The requested `yuva444p10le` may decode as `yuva444p12le`; validate an explicit allowlist rather than one guessed exact string.

```bash
python3 "$SKILL_DIR/scripts/video_workbench.py" validate output/overlay.mov \
  --audio-streams 0 --codec prores --profile 4444 \
  --pixel-format yuva444p10le --pixel-format yuva444p12le
```
