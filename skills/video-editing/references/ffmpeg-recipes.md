# FFmpeg building blocks

Put non-trivial graphs in a file and pass them with `-/filter_complex graph.ffgraph`. Keep each operation on its own labeled line.

## Cut and concatenate

```text
[0:v]trim=start=3.2:end=8.7,setpts=PTS-STARTPTS[v0];
[0:v]trim=start=12.0:end=18.5,setpts=PTS-STARTPTS[v1];
[v0][v1]concat=n=2:v=1:a=0[vout];
[0:a]atrim=start=3.2:end=8.7,asetpts=PTS-STARTPTS[a0];
[0:a]atrim=start=12.0:end=18.5,asetpts=PTS-STARTPTS[a1];
[a0][a1]concat=n=2:v=0:a=1[aout]
```

Select actual streams explicitly when the inspected payload shows that video or audio is not the default stream.

## Fit footage to a canvas

Cover:

```text
[0:v]scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080[base]
```

Contain:

```text
[0:v]scale=1920:1080:force_original_aspect_ratio=decrease,
pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=black[base]
```

Padding color is visible by definition. Do not use a visible pad merely to create space for a rounded overlay.

## Alpha overlay

```text
[0:v]format=yuv420p[base];
[1:v]format=rgba[graphic];
[base][graphic]overlay=x=80:y=80:eof_action=pass:repeatlast=0[vout]
```

Choose end-of-file behavior deliberately:

- `pass`, `repeatlast=0`: remove the overlay when it ends;
- `repeat`, `repeatlast=1`: hold the last overlay frame;
- `shortest=1`: end the composite with the shorter input.

## Rounded rectangle mask

Create a grayscale mask and attach it as alpha:

```text
[1:v]scale=520:-2,format=rgba[layer];
color=white:s=520x900,format=gray,
geq=lum='if(lte(hypot(max(28-X,0)+max(X-(W-28),0),max(28-Y,0)+max(Y-(H-28),0)),28),255,0)'[mask];
[layer][mask]alphamerge[rounded]
```

Review the corners against both dark and light backgrounds.

## Time-varying placement

Cosine ease from `x=1400` to `x=700` between 5 and 5.6 seconds:

```text
x='if(lt(t,5),1400,if(lt(t,5.6),1400+(700-1400)*(0.5-0.5*cos(PI*(t-5)/0.6)),700))'
```

When two different representations of the same subject change scale, prefer a cut between them over overlapping crossfades.

## Crossfade clips

Normalize timebases and frame rate first:

```text
[0:v]fps=30,settb=AVTB,setpts=PTS-STARTPTS[a];
[1:v]fps=30,settb=AVTB,setpts=PTS-STARTPTS[b];
[a][b]xfade=transition=fade:duration=0.5:offset=4.5[vout]
```

The offset is output time and requires adequate handles on both clips.

## Dialogue finishing

```text
[dialogue]loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000[aout]
```

Measure the rendered output. The order above avoids an unexpected sample-rate change from the loudness filter.

For a fixed-duration delivery, add `atrim=start=0:end=DURATION,asetpts=PTS-STARTPTS` after resampling. `loudnorm` may otherwise extend the audio/container slightly.

## Mix and duck

Simple mix:

```text
[dialogue]volume=1.0[d];
[music]volume=0.18[m];
[d][m]amix=inputs=2:duration=longest:normalize=0[aout]
```

For ducking, inspect the installed FFmpeg documentation for `sidechaincompress`, then test a short range with real dialogue and music. Threshold and ratio are content-dependent; do not copy arbitrary values.
