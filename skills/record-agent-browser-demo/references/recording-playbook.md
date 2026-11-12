# Agent Browser recording playbook

Use this procedure for every final Agent Browser demo. Adapt commands to the host shell, but preserve the phase order and validation gates.

## Phase A: inspect before changing state

1. Inspect the repository status, current branch, remotes, and repository-level instructions.
2. Read the PR or issue description and changed-file list when one is supplied.
3. Identify the smallest supported application startup path and the exact route to record.
4. Write a shot list before launching the recorder. Each shot must demonstrate one reviewer-relevant fact.

A good shot list usually contains three to six states:

1. The recognizable starting page.
2. The transition into the changed surface.
3. The primary new interaction.
4. A required alternate, validation, or keyboard state.
5. The completed visible result.

Do not attempt to show the entire application. Review videos are evidence, not product tours.

## Phase B: isolate code and runtime

When the named code is a PR or branch:

1. Run `git status --short --branch`.
2. If the current checkout contains unrelated work, create a separate worktree or clone at the requested commit.
3. Confirm `git rev-parse HEAD` matches the requested PR/branch commit.
4. Run the repository's documented startup path. Prefer an isolated port, Compose project, database, and data directory when existing services are running.
5. Wait until the target route renders successfully before opening the recording session.

Never use destructive Git cleanup to make room for the recording.

## Phase C: tool preflight

Run these checks before the rehearsal:

```text
agent-browser --version
agent-browser record start --help
agent-browser doctor --offline --quick
ffmpeg -version
```

Important compatibility rules:

- Trust the installed command help over examples from a newer `main` branch. Do not pass an option that the installed help does not list.
- Agent Browser may require FFmpeg only when finalizing. A missing encoder can invalidate a completed take, so verify it before `record start`.
- Keep FFmpeg on `PATH` for both `record start` and `record stop`.
- Confirm the output directory exists and is writable.
- If Agent Browser is unavailable and the user explicitly requested it, install or update Agent Browser with the user's normal authorization flow; do not substitute another browser recorder.

## Phase D: create an isolated rehearsal session

Derive a session name scoped to the worktree:

```text
agent-browser session id --scope worktree --prefix demo-rehearsal
```

Use that session for every rehearsal command:

```text
agent-browser --session <rehearsal-session> open <url>
agent-browser --session <rehearsal-session> set viewport 1440 1000
agent-browser --session <rehearsal-session> wait --load networkidle
agent-browser --session <rehearsal-session> snapshot -i
```

Complete the full flow once without recording. Follow the core loop:

1. Snapshot.
2. Act on a current ref or a stable semantic locator.
3. Wait for an observable condition such as text, URL, or element—not an arbitrary delay when a condition exists.
4. Re-snapshot after navigation, modal changes, portal-based dropdowns, and major rerenders.

During rehearsal, determine:

- Which state transitions invalidate refs.
- Whether dropdown items are covered or virtualized and require keyboard navigation.
- Which controls need scrolling into view.
- Whether keyboard typeahead actually works using `press`, `keydown`/`keyup`, or `keyboard type`.
- Whether a route creates persistent data; use unique synthetic identifiers for each take.
- Whether the final viewport contains browser/dev overlays that should be closed or avoided.

Close the rehearsal session after the path is proven.

## Phase E: plan visible cues

### Cursor

Headless recordings do not normally show a native pointer. Add a DOM cursor only when clicks would otherwise be difficult to follow. Inject it after the page is stable and re-inject after every navigation because page replacement destroys it. Move the synthetic cursor with `agent-browser mouse move <x> <y>` before each click.

Do not let the cursor cover labels or selected values. Use a small, high-contrast circle with `pointer-events:none` and a very high `z-index`.

### Safe key overlay

Agent Browser has no built-in keystroke-display flag in releases where it is absent from `--help`. If keyboard visibility matters, inject a DOM overlay that listens only for an explicit allowlist of demonstration keys.

Use this pattern, replacing the allowlist with only the keys the shot list requires:

```javascript
(() => {
  const allowed = new Set(["b", "Enter", "End"]);
  const badge = document.createElement("div");
  badge.setAttribute("data-agent-demo-keys", "");
  badge.style.cssText = [
    "position:fixed",
    "right:24px",
    "bottom:24px",
    "z-index:2147483647",
    "padding:10px 14px",
    "border-radius:10px",
    "background:rgba(17,24,39,.9)",
    "color:white",
    "font:600 16px/1.2 system-ui",
    "box-shadow:0 6px 24px rgba(0,0,0,.25)",
    "pointer-events:none",
    "opacity:0",
    "transition:opacity .12s ease"
  ].join(";");
  document.body.appendChild(badge);
  let timer;
  document.addEventListener("keydown", event => {
    if (!allowed.has(event.key)) return;
    badge.textContent = event.key.length === 1 ? event.key.toUpperCase() : event.key;
    badge.style.opacity = "1";
    clearTimeout(timer);
    timer = setTimeout(() => { badge.style.opacity = "0"; }, 700);
  }, true);
  return "key overlay installed";
})()
```

Inject through `agent-browser eval` using stdin or another quoting-safe mechanism supported by the shell.

Never display arbitrary printable keys. In particular, never echo password, token, email, search, or personal-data input. Use `fill` for sensitive or irrelevant fields and exclude those keys from the overlay.

## Phase F: record the final take

Create a new session with a different prefix, for example `demo-final`. Do not reuse cookies or draft state from rehearsal unless the requested flow specifically requires authenticated state.

Recommended setup:

```text
agent-browser --session <final-session> open <url>
agent-browser --session <final-session> set viewport 1440 1000
agent-browser --session <final-session> wait --load networkidle
agent-browser --session <final-session> snapshot -i
agent-browser --session <final-session> record start <output.webm>
```

Some releases create a fresh browser context at `record start`. Immediately wait for the page and take a new snapshot after starting so the final commands use refs from the recorded context.

Execute only the rehearsed actions. Prefer one short command chain per page so tool-call latency does not become dead air. Split at navigations so overlays can be re-injected and refs refreshed.

Pacing rules:

- Show the starting state briefly.
- Keep input changes orderly; avoid instant unrelated field changes on the same frame.
- Open a menu long enough for its contents to appear.
- Use real key events when demonstrating keyboard behavior.
- Hold the selected state and final state visually.
- Do not depend on `wait 2000` to create two seconds of encoded footage. Some versions record changed frames rather than wall-clock idle time.
- If the encoded video is too fast, first improve visual choreography. If post-processing is necessary, preserve the untouched Agent Browser source and disclose the timing adjustment.

Always call `record stop`, including on error. Confirm the command reports the exact saved path.

## Phase G: deterministic QA

Run:

```text
python scripts/video_qa.py <output.webm> --out-dir <qa-directory>
```

The helper decodes the entire video, reports duration/resolution/frame rate and size, and extracts evenly spaced frames. Inspect those frame images with the available image-viewing tool.

Reject and re-record when:

- The file is missing, empty, corrupt, or reports `No frames captured`.
- The wrong environment, branch, user, or data appears.
- The first frame is an error page, loading screen, or partially compiled route.
- A dropdown opens outside the viewport or the selected value is not visible.
- The final result is absent or appears only too briefly to understand.
- Debug tools, terminal windows, notifications, or unrelated tabs are visible.
- Sensitive or identifying data appears.
- The video requires a written explanation to determine whether the requested behavior worked.

Do not upload QA frames unless the user separately asks for them.

## Phase H: cleanup and handoff

After QA and any requested upload:

1. Close rehearsal and final Agent Browser sessions.
2. Stop the local app process started for the demo.
3. Stop only isolated containers/services created for the demo; preserve data volumes unless removal was requested.
4. Check the demo worktree for unintended changes.
5. Retain the final video and the worktree unless the user requests cleanup.

Report the artifact path, dimensions, duration, recorded commit/environment, and remote URL when uploaded.
