# Timeline and compositing

## Time

Choose one project frame rate. Convert between seconds and frames through shared helpers. Do not mix source timestamps, output timestamps, and local clip frames in the same field.

For every placed clip, preserve:

- stable identifier;
- source file and source in/out;
- output start and duration;
- track or z-order;
- crop, fit, position, opacity, and audio role;
- transition handles.

Variable-frame-rate inputs may need normalization before frame-exact work. Verify actual behavior instead of converting reflexively.

## Tracks and attention

The uppermost visual track should usually own attention. A layout transition should communicate a change in subject, scale, place, time, or hierarchy. If it communicates nothing, prefer a cut or no transition.

Maintain spatial context around aggressive crops. Use full-frame cutaways or pullbacks when a detail view hides information the viewer needs.

## Compositing

Use alpha-capable assets for graphics. Decide how every overlay behaves before its first frame, after its last frame, and when its source ends.

Rounded masks, shadows, blur, and borders are independent operations. Do not accidentally create a border by padding with a visible color. Review edges against both light and dark frames.

Crossfading differently scaled or positioned copies of the same subject often creates ghosting. Animate a single layer or make a motivated cut between representations.

## Audio

Classify every audio track as dialogue, ambience, music, effect, or utility/sync. Establish dialogue first, then mix supporting tracks around it.

Use fades at cuts, remove unused source audio intentionally, and check mono compatibility when relevant. Apply loudness normalization before the final sample-rate conversion. Measure the final file rather than trusting filter settings.

Typical web dialogue delivery starts near -16 integrated loudness units relative to full scale (LUFS), but the actual platform or user brief wins.
