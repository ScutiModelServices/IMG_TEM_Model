# TEMImageModel

TEM-XL/2 ImageNet image generation served over HTTP on an NVIDIA GPU, behind the shared model-service admin page, tokens and settings. Port 9190, env prefix `TEM_`, token prefix `tem_`.

## Agent instructions
This file is the one instruction file for every coding agent; `CLAUDE.md` only imports it (`@AGENTS.md`). Edit this file, never `CLAUDE.md`.

## Commands (from this folder, venv `.venv`, managed by uv)
- Install: `uv sync` (`winget install astral-sh.uv` if uv is missing)
- Test: `uv run pytest -q`. `tests/test_admin_ui.py` needs Playwright and its browser and is skipped without it. On Windows, if uv fails with "cannot move the file to a different disk drive", set `UV_CACHE_DIR` to a folder on the same drive and `UV_LINK_MODE=copy`.
- Run: `run.bat run`, or `uv run python src/app.py` (add `--dotenv` to load `.env`), or `docker compose up -d --build`

## Rules
- Follow the `model-service-parity` skill and `AI/ModelServices/_docs/SHARED-FEATURES.md` (what must match in every model service) and `AI/ModelServices/_docs/SERVICE-SPECIFIC.md` (what differs on purpose). A change to a shared feature goes to every service; a new difference goes into `SERVICE-SPECIFIC.md` in the same change.
- `web/index.html`, `src/tokens.py`, `src/settings.py`, `src/updates.py` and `.dockerignore` are copies shared with the other model services. Change one, copy it to the others, run `python tools/check_sync.py` in each repo.
- `POST /v1/generate` returns a PNG; `GET /v1/classes` lists the classes. A token's "projects" list limits models (one: `tem-xl-256`). The cache keeps only calls with a `seed`; `src/images.py` is its own copy of the TTS `AudioCache`.
- `tem.py` is not in the repo (no upstream licence): `tools/fetch_tem.py` downloads it at a pinned commit into `_tem_code/`. The weights are one pinned Google Drive file checked by SHA-256.
- Needs an NVIDIA GPU (`device` setting, compose reserves one). `tests/test_real_model.py` runs the real model and is skipped without the code, the checkpoint and a GPU.
- Behaviour changes update `README.md`, `deployment.md`, `docs/guide-web-ui.md`, `.env.example` and `CHANGELOG.md` in the same commit.
- Never read or print `.env`, `tokens.json` or `settings.json`.
- Commit with the noreply author email `214214011+scutiii2@users.noreply.github.com` (another address is rejected on push). Push `main`, then run `python tools/publish_live.py`. Build Docker only when the Dockerfile or the dependencies changed.
