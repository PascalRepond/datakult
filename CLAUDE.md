# Datakult Claude guide

## Overview

Datakult is a personal Django web app to track and rate media consumed: films, TV series, books, video games, music, podcasts, etc. It includes a rating system, markdown reviews, and filtering by type/status/year. Media metadata can be fetched from external APIs (TMDB, Google Books, MusicBrainz, OpenLibrary, IGDB). It is developed for personal and educational use.

**Stack**: Python 3.14, Django 6.x, SQLite, HTMX, Tailwind CSS (django-tailwind), DaisyUI, Lucide icons, Pillow, WhiteNoise
**Package manager**: `uv` with `poethepoet` for task running

## Commands

During development, all commands are run through uv's virtual env with `uv run`.

### Daily development

```bash
uv run poe server           # Start dev server (Django + Tailwind watch via honcho)
uv run poe migrate          # Apply database migrations
uv run poe makemigrations   # Generate new migrations
uv run poe shell            # Open Django shell
```

### Linting and formatting

**IMPORTANT:** After editing files, make sure that there are no errors in the formatting and linting.

```bash
uv run poe lint     # ruff check ./src
uv run poe format   # ruff format ./src
```

### Setup (done by humans)

Human developers will run the app setup and the server on their own terms.

## Architecture

```text
src/
├── config/         # Django settings, urls, wsgi/asgi
├── core/           # Main app: Media model, views, forms, filters, queries
│   ├── services/   # External API clients: tmdb, googlebooks, musicbrainz, openlibrary, igdb
│   ├── templates/  # Core-specific templates
│   └── templatetags/
├── accounts/       # Custom user model (accounts.CustomUser), auth views
├── templates/      # Project-wide base templates and partials
├── static/         # Project-wide static files (JS, images)
├── theme/          # Tailwind CSS configuration (django-tailwind)
├── locale/         # Translation files (en, fr)
└── tests/          # Tests split into tests/core/ and tests/accounts/
```

Key design choices:

- Single `Media` model covers all media types via a `media_type` field.
- `Agent` model represents any contributor (author, director, artist, etc.).
- Custom user model from the start (`accounts.CustomUser`).
- Views use function-based views (FBVs); HTMX handles dynamic interactions without full-page reloads.

## Code Style

- Always write docstrings and comments in English.
- Be clear and concise in the docstrings and do not over-comment the code.
- Prefer existing DaisyUI classes before adding custom CSS.

### Python/Django

- Use function-based views (FBVs) unless a class-based view is clearly more appropriate.
- Models must define an explicit `__str__` method.

### Templates

- Use partials in `templates/partials/` for reusable components.
- Prefer HTMX for dynamic interactions over vanilla JavaScript.
- Use DaisyUI classes for styling.

### JavaScript

- Keep JavaScript minimal; prefer HTMX.
- JS files live in `static/js/`.

### Translations

The app supports **English** (`en`) and **French** (`fr`) via Django's i18n framework (`gettext_lazy`, `.po`/`.mo` files in `src/locale/`). During standard development, make sure any end-user-facing strings are marked for translation in the code. Run `uv run poe makemessages` after adding new strings, then `uv run poe compilemessages` before testing translations.

## Testing Notes

- Tests use function-based style (no class-based tests).
- Tests are split into `src/tests/core/` and `src/tests/accounts/`.
- The project follows a test-driven development methodology. Each commit must be accompanied by tests that ensure that the functionality works as intended. Tests must follow DRY principles and should only test specific app behaviour and not the behaviour of external modules (e.g. Django or Python dependencies).
- Shared fixtures are in `src/tests/conftest.py` (provides `agent`, `media`, `media_factory`, `user`, `logged_in_client`).
- Sample fixture data is in `src/core/fixtures/sample_data.json`.

## Behavioral guidelines

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

### 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:

- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

### 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

### 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:

- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:

- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

### 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:

- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:

```text
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.
