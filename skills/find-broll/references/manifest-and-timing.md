# Manifest and timing

Store a project-local `broll-manifest.json`. Keep source time, transcript time, and output time explicit.

```json
{
  "version": 1,
  "project_fps": "30000/1001",
  "beats": [
    {
      "id": "b01",
      "narration": "Today we're using Example App.",
      "interpretation": "Introduce the current product interface.",
      "route": "product",
      "anchor": {
        "word": "Example",
        "transcript_start_seconds": 2.48,
        "placement_offset_seconds": 0.25
      },
      "output": {
        "start_seconds": 2.73,
        "end_seconds": 5.4
      },
      "source": {
        "url": "https://example.com/demo",
        "creator": "Example App",
        "title": "Official product demo",
        "published_at": "2026-06-10",
        "retrieved_at": "2026-07-29T02:00:00Z",
        "local_path": "assets/raw/b01-demo.mp4",
        "in_seconds": 14.2,
        "out_seconds": 16.87,
        "rights_note": "Verify intended use and attribution before publication."
      },
      "presentation": {
        "layout": "full-bleed",
        "audio": "strip",
        "credit": "Example App / official demo"
      },
      "status": "approved"
    }
  ]
}
```

## Invariants

- Every beat ID is stable across revisions.
- `output.start_seconds = anchor.transcript_start_seconds + placement_offset_seconds`, unless an editorial reason is recorded.
- Source intervals are measured from the source file; output intervals are measured from the final timeline.
- All intervals are converted from one project frame rate at render time.
- Every approved beat has provenance and a local asset.
- Every placed beat appears once in the rendered timeline.
- Dropped beats retain their reason; they do not silently vanish.
- External clip audio defaults to stripped.

## Timing review

For each entrance, inspect at least:

- 3–5 frames before the anchor word;
- the first B-roll frame;
- the midpoint;
- the last B-roll frame;
- 3–5 frames after the exit.

Check that the narration introduces the visual before or as it appears, the exit does not interrupt a readable receipt, and adjacent cutaways do not reveal a transient base frame. When transcript timestamps and lip movement disagree, trust the observed frame and audio waveform, then record the manual correction.
