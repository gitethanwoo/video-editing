# Voice, music and sound effects with ElevenLabs

Everything here uses the `elevenlabs` CLI. Every command takes `--help` and `--format json`.

## Setup

```bash
brew install elevenlabs/tap/elevenlabs        # or: npm i -D @elevenlabs/cli, then ./node_modules/.bin/elevenlabs
elevenlabs auth login                         # opens a browser for the user to sign in
elevenlabs auth status
elevenlabs models list --format json
```

- An `ELEVENLABS_API_KEY` in the shell takes precedence over the login. `env -u ELEVENLABS_API_KEY elevenlabs ...` or `voiceover.py --ignore-env-key` uses the login.
- Commands run in the background need `</dev/null`; some wait on stdin.

## Voice

Use `eleven_v4`. ElevenLabs documents it here:

- https://elevenlabs.io/docs/overview/capabilities/text-to-speech/eleven-v4.md
- https://elevenlabs.io/docs/overview/capabilities/text-to-speech/best-practices.md ("Prompting Eleven v4")

### What v4 does

- Its voice settings are Stability and Similarity. Lower stability gives a more varied, expressive read.
- `voice_settings.speed` and `style` are accepted and ignored. Pace is set with tags.
- `--seed` is rejected, so every generation is a new performance.
- SSML is unsupported; `<break>` does nothing.
- One request takes 10,000 characters, enough for a whole script.
- A read runs about 18% longer than Multilingual v2 with the same voice.
- A cloned voice is reproduced closely, level jumps and plosives included. `mix.py` levels each clip.
- `eleven_v4_turbo` is the low-latency variant for live agents.

### Choosing a voice

The voice sets the film's length, so settle it before the full read. Generate the same 15 to 20 seconds of the script in a few candidates (`elevenlabs voices search` lists voices with their labels) and let the user pick. Voices used before:

- `kPzsL2i3teMYv0FxEYQ6`: younger, quick, "social".
- `c6SfcYrb2t09NHXiT80T`: warm and steady.

Tags land best when the voice already has that delivery in it.

### Tags

A tag is a direction in square brackets inside the text. Tags are free text; these are examples.

- **Delivery:** `[confidently]`, `[warmly]`, `[flatly]`, `[matter-of-fact]`, `[questioning]`, `[excited]`, `[curious]`, `[reassuring]`, `[whispers]`.
- **Descriptive phrases**, combined with commas: `[quiet, measured narration]`, `[gradually building energy]`, `[warm, conversational tone]`, `[low, steady voice]`.
- **Pauses:** `[short pause]`, `[long pause]` (about 1 s between sentences). At the very start of a clip a pause tag adds no silence.
- **Non-verbal sounds:** `[laughs]`, `[sighs]`, `[exhales]`, `[clears throat]`. These are performed audibly, about half a second each.
- **Sound effects and accents:** `[applause]`, `[strong French accent]`, `[sings]`.

Place a tag just before the words it shapes. A leading tag carries through a short clip; add another where the delivery changes. A tag that names a sound may be performed as that sound, so describe the voice.

### Pace

The same 25-word line:

| Text | Length |
| --- | --- |
| no tag | 8.3 s |
| `[quick, energetic pace]` at the start | 7.0 s |
| `[slow, deliberate pace]` at the start | 9.2 s |
| `[slow, deliberate pace]` before each of three clauses | 10.3 s |

A pace tag moves a read by 10 to 25 percent. Pause tags and ellipses add silence.

### Emphasis and structure

- CAPITALS emphasise a word: `That's YOUR call.`
- Ellipses add a pause and weight: `One page... no surprises.` A dash gives a short break.
- Write one sentence or thought per line, with a question mark where the voice should rise.
- A line reading can be directed: "rise on the first word, flat on the rest" is `[questioning] This? ... [flatly] was billing.`

```text
[confidently] We redesigned billing.
[short pause] Clearer. Cleaner.
[long pause] See what you've used, and what you'll likely pay.
[short pause] And when you run out of replies? That's YOUR call.
[long pause] One page. No surprises.
```

### Names and numbers

- v4 reads IPA written between slashes inside double quotes: `Meet "/luˈmɔːrə/", the new home for your invoices.` Include the stress marks. List the spelling under `pronunciations` in the voiceover file (`{"/luˈmɔːrə/": "Lumora"}`) so the check and the word timings use the real word. A plain respelling (`Loo-MOR-ah`) also works.
- Write numbers and symbols as they are said: `One hundred four percent`, `two-thirds`.

### Generating and checking

`scripts/voiceover.py` takes a small JSON file (format in its docstring) and for each line:

1. calls `text-to-speech convert_with_timestamps` and saves the audio;
2. transcribes it with `speech-to-text convert --model-id scribe_v1` and compares it with the script, tags removed, word for word;
3. writes `<id>.words.json` as `[{ "w", "s", "e" }]` and a `manifest.json` with each line's length, words per minute and any non-speech sounds heard.

A mismatch is a mispronounced or dropped word, or a tag read aloud. Fix the text and run it again; unchanged lines are cached. Word times come from the transcript, which follows the audio more closely than the timings returned with the generation.

- **One take of the whole script** (element film) flows naturally between sentences, and the picture follows the word timings.
- **One clip per line** (sizzle reel, walkthrough) lets each line be placed and replaced alone. Neighbouring lines are passed as context so the reads connect.

Two speakers in conversation is `elevenlabs text-to-dialogue`, with a voice per turn and tags inside each turn's text.

## Music

Compose from a plan so sections land where the film needs them.

```bash
elevenlabs music composition-plan create --prompt "warm felt piano and soft pulse, minimal product film, instrumental, 96 BPM" \
  --music-length-ms 26000 --model-id music_v2_5 --format json > music/plan.json
# edit section styles and durations in plan.json, then:
elevenlabs music compose --json "$(python3 -c 'import json;print(json.dumps({"composition_plan":json.load(open("music/plan.json")),"model_id":"music_v2_5"}))')" -o music/bed.mp3
```

- The plan's shape depends on the model. `music_v2_5` plans are `{"chunks": [{"text", "duration_ms", "positive_styles", "negative_styles", ...}]}`; `music_v1` plans use `sections` with global and local style lists. Edit the plan the API returns.
- Pass the whole body with `--json`. `--force-instrumental` works only with `--prompt`; with a plan, put "vocals" and "lyrics" in the negative styles.
- A section is at least 3000 ms.
- Set the plan's total to the film's length. For an ending that holds, ask for a final section at steady volume with "fade out" and "silence" as negative styles, and fade it in the mix. `ffmpeg -af silencedetect` shows whether a cue drops out early.
- Each generation is a new piece. Save cues under separate names.

## Sound effects

```bash
elevenlabs text-to-sound-effects convert --text "soft airy whoosh, short, no tonal content" --duration-seconds 1.2 -o sfx/whoosh-soft.mp3
```

Generated effects vary widely in loudness. `mix.py` peak-normalises each one before applying its gain.
