# Audio and timing analysis

Treat sound as parallel editorial structure.

## Listen and measure for

- dialogue starts and phrase endings;
- room tone and environmental ambience;
- music entrances, exits, ramps, and arrangement changes;
- percussion or pulse becoming explicit;
- sound effects that bridge or punctuate cuts;
- silence or near-silence;
- whether the picture cuts on a beat, before it, or after it.

RMS level describes energy, not perceived meaning. Beat tracking works best on rhythmic music and can be unreliable under speech, ambience, or rubato material. Use both as navigation aids.

## Useful relationships

- **Cut on beat:** feels decisive and reinforces pulse.
- **Cut before beat:** creates anticipation.
- **Cut after beat:** can feel relaxed, weighted, or intentionally late.
- **Audio lead / J-cut:** prepares the next space or speaker.
- **Audio carry / L-cut:** maintains continuity across new imagery.
- **Music dropout:** exposes dialogue, ambience, or vulnerability.
- **Ambient bridge:** preserves place through black or across discontinuous images.
- **Crescendo plus shortening shots:** compounds tension.
- **Score re-entry plus title:** turns a scene change into a chapter declaration.

## Evidence discipline

Write “RMS drops 13 dB and speech stops” as measured evidence. Write “the score appears to drop out, leaving waves” only after listening or after multiple signals support it. If the environment cannot audition audio, state that the sound description combines waveform evidence, transcript timing, and the user's observation.

## Hybrid semantic listening

Use a semantic audio model to describe musical character, dialogue, effects, ambience, and editorial function. Do not use it as the sole detector of continuity or silence.

Use this sequence:

1. Extract direct audio at good fidelity instead of relying on a low-bandwidth video-audio representation.
2. Run a long-context pass across the complete editorial movement so the model can recognize one cue continuing beneath different speakers and scenes.
3. Run focused passes around important transitions.
4. Compare the description with the loudness trace and spectrogram.
5. Use source separation when dialogue, music, and ambience overlap.
6. Record contradictions and lower confidence instead of forcing agreement.

In a July 2026 benchmark, Gemini Flash correctly recognized one electronic cue carrying across a long interview montage and explained its structural function. It still placed the quiet ending about four seconds too early and confidently mislabeled the remaining harmonic tail as crowd ambience. The spectrogram showed horizontal harmonic bands continuing across a cut to black and decaying several seconds later. The useful rule is general: semantic models are strong at meaning and weak at exact low-level boundaries.

The bundled `audio_listener.py` writes:

- the extracted audio excerpt;
- `spectrogram.png`;
- `audio-levels.json`;
- the raw model payload;
- `semantic-audio.md` containing the model's description.

Use `--prepare-only` when no model credential is available or when deterministic evidence is sufficient.
