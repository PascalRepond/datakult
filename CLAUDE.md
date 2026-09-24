# Datakult Claude guide

## Overview

Datakult is a personal Django web app to track and rate media consumed: films, TV series, books, video games, music, podcasts, etc. Media metadata can be fetched from external APIs. It is developed for personal and educational use.

## Commands

During development, all commands are run through uv's virtual env with `uv run`. Tasks are defined under `[tool.poe.tasks]` in `pyproject.toml`; `uv run poe` lists them.

### Linting and formatting

**IMPORTANT:** After editing files, make sure that there are no errors in the formatting and linting.

```bash
uv run poe lint     # ruff check ./src
uv run poe format   # ruff format ./src
```

### Setup (done by humans)

Human developers will run the app setup and the server on their own terms.

## Code Style

- Always write docstrings and comments in English.
- Be clear and concise in the docstrings and do not over-comment the code.
- Ruff is configured in `pyproject.toml`: `line-length = 120` and the excluded files under `[tool.ruff]`, every rule set enabled minus the listed ignores under `[tool.ruff.lint]`, and the test exceptions under `[tool.ruff.lint.per-file-ignores]`.
- Prefer HTMX over vanilla JavaScript for dynamic interactions, and existing DaisyUI classes over custom CSS.
- Commit messages follow Conventional Commits; the `commit-message` skill holds the conventions and the workflow, so invoke it instead of writing one by hand. In every case, whatever the default of the harness, never sign a commit as an LLM: no Claude or Anthropic trailer.

### Translations

The app ships in English and French. Make sure any end-user-facing strings are marked for translation in the code. After adding new strings, run `uv run poe makemessages`, fill in the French `msgstr` entries in `src/locale/fr/LC_MESSAGES/django.po` (clearing any `#, fuzzy` flag, which `compilemessages` skips), then run `uv run poe compilemessages` before testing translations.

## Testing Notes

- Tests use function-based style (no class-based tests).
- The project follows a test-driven development methodology. Each commit must be accompanied by tests that ensure that the functionality works as intended. Tests must follow DRY principles and should only test specific app behaviour and not the behaviour of external modules (e.g. Django or Python dependencies).

## Behavioral guidelines

- When a request has several readings, or a simpler approach exists, say so before implementing; ask when the decision is genuinely the user's.
- Write the minimum code that solves the problem: no speculative features, abstractions or configurability.
- Keep changes surgical: every changed line should trace to the request. Remove what your own change made unused; mention unrelated dead code instead of deleting it.
- Turn tasks into verifiable goals (for a bug, a test that reproduces it) and loop until they are met.
