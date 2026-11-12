---
name: record-agent-browser-demo
description: Record polished, review-ready web application walkthroughs with Agent Browser, including safe branch/app setup, rehearsal, visible interaction cues, video QA, and optional GitHub PR or issue attachment. Use when a user asks for an Agent Browser video, browser demo, recorded web flow, or video evidence; do not use for general desktop or native-app recording.
---

# Record Agent Browser Demo

Produce a concise video that lets a reviewer understand and verify a web change without reconstructing the workflow themselves.

## Required reading

- Before running Agent Browser, read [references/recording-playbook.md](references/recording-playbook.md) completely and follow its phase order.
- If the user asks to upload, attach, or post the video to GitHub, also read [references/github-upload.md](references/github-upload.md) completely before the upload.

## Non-negotiable invariants

1. If the user names Agent Browser, use Agent Browser for both browser interaction and the source recording. Do not silently substitute Playwright, computer-use automation, or a synthetic video.
2. Preserve existing work. Inspect Git status before branch operations. If the checkout is dirty or on unrelated work, use an isolated worktree or clone; never reset, clean, or overwrite the user's changes.
3. Reproduce the requested code or deployment exactly. Record the named PR/branch/build, not a nearby environment assumed to be equivalent.
4. Rehearse the entire flow in a disposable Agent Browser session before the final take. A first attempt is not a final take.
5. Use a fresh named session for the final take. Never use Agent Browser's shared unnamed session.
6. Run `agent-browser record start --help` and `ffmpeg -version` before the final take. Installed releases can lag the documentation, and missing FFmpeg may not be reported until `record stop`.
7. Treat every navigation, modal opening, and major rerender as invalidating element references. Re-snapshot before the next reference-based action.
8. Do not expose real passwords, tokens, personal information, or production data. Use documented local fixtures or clearly synthetic demo values.
9. Do not upload until the artifact passes visual QA. A successful `record stop` alone is insufficient.
10. Upload or post only when the user explicitly requested it. Verify the resulting remote comment or body after mutation.

## Required workflow

### 1. Establish the review story

Read the request, PR/issue description, changed files, existing screenshots, test plan, and repository instructions. Convert them into a short shot list with one purpose per state. Prefer a beginning, the changed interaction, its important alternate/error state, and the final result.

Do not record setup work, dependency installation, compilation, authentication, exploratory clicks, or retries.

### 2. Prepare and verify the application

Create an isolated code checkout when needed, install dependencies, start the smallest supported local stack, and wait for the target URL to be healthy. Keep unrelated existing services untouched. Record the exact commit and URL used.

### 3. Preflight the recording tools

Confirm the installed Agent Browser version, supported recording syntax, browser health, FFmpeg availability, writable output path, and expected GitHub size/type constraints when an upload is requested. Resolve all failures before recording.

### 4. Rehearse

Use a disposable named session to complete the whole shot list. Capture `snapshot -i` output after each meaningful UI change, identify stable semantic locators or fresh refs, confirm keyboard behavior, and note any overlays, scrolling, or viewport changes required.

The rehearsal must prove that the intended final state is reachable. If it exposes a product defect, stop and report it instead of disguising the defect in the recording.

### 5. Record a clean take

Use a new named session and a desktop viewport appropriate to the page; default to `1440x1000` when no product-specific viewport is required. Navigate and stabilize the page before `record start`. Record only the rehearsed sequence.

Make actions legible: keep the relevant control in view, show menu contents before selecting, use real keyboard events for keyboard behavior, and pause visually on important states. Do not rely on sleep duration alone to control the encoded video's pace; some Agent Browser versions encode only changed frames.

Use a visible DOM cursor or safe key overlay when it materially improves comprehension. Re-inject overlays after navigation. A key overlay must use an explicit allowlist and must never echo arbitrary text or password-field input.

### 6. Finalize and inspect

Stop the recording while FFmpeg remains available on `PATH`. Verify that the file exists, is non-empty, decodes successfully, has the intended resolution, and is within the target upload limit.

Run the deterministic helper:

```text
python scripts/video_qa.py path/to/demo.webm --out-dir path/to/qa-frames
```

Visually inspect every extracted frame. At minimum, confirm the start, changed interaction, alternate/error state if present, and final result. Re-record if any important state is missing, clipped, unreadable, too fast, or contaminated by setup/debug UI.

### 7. Upload when requested

Follow [references/github-upload.md](references/github-upload.md). Post a brief factual description of what the video demonstrates, attach the final video with the requested mechanism, and verify the returned comment/body contains the hosted attachment URL.

### 8. Clean up narrowly

Close the Agent Browser sessions and stop only the temporary servers or containers created for the recording. Preserve the worktree and artifact unless the user asked for their removal. Never tear down unrelated services.

## Completion gate

Do not report success until all applicable items are true:

- The recorded code/version and target URL are identified.
- The worktree or checkout is clean of unintended edits.
- The final take came from Agent Browser in a fresh named session.
- The video exists and decodes.
- Representative frames were visually inspected.
- No sensitive or unrelated content is visible.
- The video communicates the requested behavior without explanation from the operator.
- If uploaded, the remote comment/body and hosted attachment URL were verified.

In the final response, lead with the result and provide the remote URL, local artifact path, recorded commit/environment, and any cleanup state. Mention retries or tooling workarounds only when they affect reproducibility.
