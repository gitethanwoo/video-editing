# Generic FFmpeg render plan

The workbench accepts a JSON plan that points to an arbitrary FFmpeg filtergraph. The plan owns delivery and validation; the graph owns the edit.

```json
{
  "version": 1,
  "inputs": ["camera.mov", "graphics.mov"],
  "filtergraph": "edit.ffgraph",
  "output": "output/final.mp4",
  "work_dir": "output/work",
  "video_map": "[vout]",
  "audio_map": "[aout]",
  "video": {
    "codec": "h264_videotoolbox",
    "args": ["-b:v", "14M", "-maxrate", "20M", "-bufsize", "28M"],
    "pixel_format": "yuv420p",
    "fps": "30000/1001",
    "width": 1920,
    "height": 1080
  },
  "audio": {
    "codec": "aac",
    "args": ["-b:a", "192k"],
    "sample_rate": 48000
  },
  "validation": {
    "duration": 82.75,
    "duration_tolerance": 0.12,
    "codec": "h264",
    "pixel_formats": ["yuv420p"],
    "lufs": -16,
    "true_peak": -1.5,
    "loudness_range": 11
  }
}
```

Paths are relative to the plan file unless absolute. `inputs` are passed to FFmpeg in order. The filtergraph must produce `video_map` and, when present, `audio_map`.

The workbench detects the installed FFmpeg major version. It uses FFmpeg 8's `-/filter_complex` file-loading syntax when available and the older `-filter_complex_script` syntax on compatible earlier releases.

For a silent render, omit `audio` and `audio_map`.

`video.codec` names the encoder passed to FFmpeg. `validation.codec` names the decoded codec reported by FFprobe; for example, `h264_videotoolbox` produces `h264`. Use `validation.profile` when a codec profile matters. Use a list for `pixel_formats` when more than one observed alpha-capable representation is acceptable.

Filters such as `loudnorm` can extend an audio stream slightly. For a fixed-duration edit, trim the final audio branch explicitly after normalization and resampling:

```text
[dialogue]loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000,
atrim=start=0:end=82.75,asetpts=PTS-STARTPTS[aout]
```

The tool writes the exact command, obtains a per-output lock, renders a uniquely named candidate adjacent to the destination, performs the validation contract, archives an existing output on the same filesystem, and promotes transactionally only after success.
