# Uploading a browser demo to GitHub

Read this only when the user explicitly asks to attach, upload, post, or embed the video in a GitHub issue or pull request.

## Authorization boundary

Posting a comment and uploading a file are external mutations. The user's request must authorize both the destination and the attachment. If it does not, stop after producing the local artifact and ask for direction.

Authentication is not part of the recording. If GitHub requires login, start the normal CLI/device authorization flow and hand authentication, password, OTP, CAPTCHA, or account-choice steps to the user. Never capture authentication in the demo video.

## Preflight

1. Confirm the exact repository and PR/issue number or URL.
2. Confirm the final video passed QA and is the file being attached—not a rehearsal, failed take, or QA frame.
3. Verify the current GitHub CLI supports the requested flag:

```text
gh --version
gh pr comment --help
```

The help output must list `--attach`. If it does not, update GitHub CLI through an authorized path; do not invent a manual upload API.

4. Verify GitHub currently accepts the file extension and size. WebM, MP4, and MOV are commonly supported, but limits can change and differ by plan. Check current official GitHub documentation when accuracy matters.
5. Run `gh auth status` without printing or copying tokens.

## Attach to a pull request comment

Use a short factual body that says what the reviewer can verify:

```text
gh pr comment <number-or-url> \
  --repo <owner/repository> \
  --body "Agent Browser walkthrough: <start> → <changed interaction> → <final result>." \
  --attach <path/to/final-video.webm>
```

Do not add claims the video does not show. Do not describe hidden test results as visually verified.

When precise placement is required, a body file may reference the same local video as an otherwise-empty Markdown media paragraph, and `--attach` can rewrite that local reference to the hosted URL. Prefer the simpler appended attachment unless the user requests custom Markdown layout.

Do not add image alt text syntax after `#` to video paths; video attachments do not support image alt text.

## Verify the mutation

Capture the comment URL printed by `gh`. Then read the created comment back with GitHub CLI or the API and confirm:

- The comment is on the requested repository and PR/issue.
- The factual description is correct.
- The body contains a hosted `github.com/user-attachments/assets/...` URL or the current equivalent.
- Only the intended final video was attached.

Example readback when the comment ID is known:

```text
gh api repos/<owner>/<repo>/issues/comments/<comment-id> \
  --jq '{url: .html_url, body: .body}'
```

If upload succeeds but comment creation is uncertain, inspect the remote discussion before retrying. Do not create duplicate comments blindly.

## Completion report

Return the verified GitHub comment URL and the local artifact path. State that the attachment was uploaded with `--attach`. Do not expose authentication details or token scopes.
