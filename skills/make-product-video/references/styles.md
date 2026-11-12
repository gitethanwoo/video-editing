# The three styles

- [Walkthrough](#walkthrough)
- [Sizzle reel](#sizzle-reel)
- [Element film](#element-film)
- [Recording real UI](#recording-real-ui)

## Walkthrough

Shows a product working end to end, for people who want proof and will watch for minutes: evaluators, clients, a team learning a new system.

**Shape.** One continuous story told through the people who use the product. Pick a spine the audience already knows (a season, an order, a case) and hand it from person to person, showing each hand-off working. A title card opens the film and each act.

**Script.** Short present-tense sentences, one per visible step: who this is, what they are doing, what the screen shows. A one-page narrative (audience, the one belief, the acts in order, tone) comes before the lines.

**Picture.** Whole screens recorded with `agent-browser`, one take per act, at the output size (1440x1000 at 30 fps). Phone flows are recorded at a phone viewport and placed in a device frame on a white canvas. A narrow viewport records horizontally squeezed, because the browser window has a minimum width wider than a phone; scale the capture back to the window width and crop.

**Timing.** The footage is fitted to the narration, act by act:

1. Record each act at a natural pace, pausing on important states.
2. Mark a cue for each narration line, the time in the raw take where the line begins, in one file: `{"act1": [[0.0, "line"], [11.5, "line"]]}`.
3. List dead time (spinners, stalls) as raw-take ranges to drop. The build removes them and shifts the cues by the time removed.
4. Generate one voiceover clip per line.
5. For each segment between two cues, `speed = segment length / (clip length + 0.45 s)`, clamped to between 1.0 and 1.6. When the line runs longer than the sped-up segment, hold the last frame.

Assemble with FFmpeg (`trim`, `setpts`, `tpad`, `concat`). Title cards are stills rendered from an HTML template.

**Sound.** Voice over one instrumental bed, ducked under the voice and faded out over the last few seconds.

## Sizzle reel

Makes stakeholders feel what the product is for in 60 to 90 seconds: a pitch, a progress update, an internal launch.

**Shape.** A problem the audience recognises, the product's name, a promise, three or four real moments of the product, one principle line, a close. When the requester has described the product in a memo or a recording, build the script from their phrases.

**Script.** One voice line per beat, eight to ten lines, each generated as its own clip so it can be placed and replaced alone.

**Picture.** Screen recordings at 3200x1800 placed in a designed Remotion composition at 1920x1080 and 30 fps, with camera moves, cuts between shots and full-screen type. `video_workbench.py init-motion` starts the project.

**Timing.** Scenes are cut on the music. Find the draft cue's phrase length (a phrase is one musical sentence, for example two bars: 4.8 s at 100 BPM), put scene changes on phrase boundaries, and place each voice line inside its scene. Choose each shot's source offset so the thing being named is on screen as it is named; a contact sheet at each line's start time shows this. Scenes are a whole number of phrases, long enough for their lines, so their final lengths are set once the voice exists. To lengthen the cue, repeat two of its consecutive phrases.

**Sound.** Voice, music, and sound effects on scene changes and moves.

## Element film

Announces one change to people who already use the product, in 20 to 60 seconds.

**Shape.** One message said plainly, two to four things that show it, the message again as a close. For example: "We redesigned billing. Clearer. Cleaner." → what you can now see → what you can now control → "One page. No surprises."

**Picture.** A plain background with one thing centered at a time: a line of type, or one element of the product (a card, a chart, a control) drawn large and animated to show what it does. Rebuild the element in React and SVG inside Remotion, with sizes, colours and type taken from the real component, so it can draw itself, count up and respond to a cursor. 1920x1080 at 60 fps. Linear's product videos are a good reference.

Useful pieces:

- `Scene` shows its children centered between two times, with a short fade and a slight scale-in.
- `Line` is large centered type for statements.
- One component per element, each animating from word anchors.
- A cursor with a click ripple.
- A helper `p(t, start, duration, ease)` returning 0 to 1, used for every move.

**Timing.** The voiceover is one take of the whole script, and every animation is keyed to the moment a word is spoken. `voiceover.py` writes `<id>.words.json` for the take; import it and look words up:

```ts
import words from "./words.json";            // [{ w, s, e }]
const norm = (x: string) => x.toLowerCase().replace(/’/g, "'").replace(/[^a-z0-9']/g, "");
// Start of the nth time a word is spoken.
export const at = (word: string, nth = 1) => {
  const hit = words.filter((x) => norm(x.w) === norm(word))[nth - 1];
  if (!hit) throw new Error(`voiceover has no "${word}" #${nth}`);
  return hit.s;
};
// The film ends 1.9 s after the last word. The mix file's "total" is this same number.
export const DURATION_S = Math.ceil((words[words.length - 1].e + 1.9) * 10) / 10;
```

Scenes are windows such as `[at("line") - 0.3, at("run") - 0.3]`, so regenerating the voice re-times the film. For the silent cut, rough durations stand in for the anchors.

**Sound.** Voice over a quiet bed, with the cursor's clicks.

## Recording real UI

`record-agent-browser-demo` has the procedure. For footage that goes into a produced video:

- **Data.** Seed people and records with an idempotent script so every take starts from the same state.
- **Resolution.** `agent-browser set viewport 1600 900 2` records 3200x1800, enough for push-ins.
- **Clean frame.** An init script can inject CSS to hide dev toolbars and scrollbars; `opacity: 0` keeps a hidden control clickable. Init scripts run in a JavaScript context separate from the page's: their CSS applies, but `window` globals they define are invisible to `eval`.
- **Motion.** `record start --cursor`, `mouse move --duration --human`, a pause before each click, and scrolling with an eased `requestAnimationFrame` loop run through `eval`.
- **Display.** Screenshots and recordings hang when the display sleeps. `caffeinate -d -u` in a background shell keeps it awake.
- **zsh.** `VAR=x source lib.sh` does not keep `VAR`; export it first.
- **Takes.** One small re-runnable script per shot or act.
