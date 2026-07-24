# Repository guidance

This repository contains portable agent skills for arbitrary video analysis and editing.

- Keep each skill under `skills/<skill-name>/` with a valid `SKILL.md`.
- Keep `SKILL.md` concise and move detailed material into directly linked `references/`.
- Inspect real command and API payloads before writing parsers.
- Never commit source media, generated renders, API keys, transcripts containing private material, or machine-specific absolute paths.
- Keep analysis evidence distinct from editorial interpretation.
- Treat semantic audio output as a hypothesis when it conflicts with spectrogram, loudness, or source-separation evidence.
- Test scripts on synthetic media before publishing.
- Prefer deterministic review artifacts and validation reports over claims that a render “looks right.”
