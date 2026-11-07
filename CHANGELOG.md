# Changelog

## Unreleased

- Admin page: **Connect to this service** card with the addresses other services can use (this page's address, same PC, Docker network, `host.docker.internal`) and every endpoint, each with a Copy button.
- Admin **Try it** panel: descriptor-driven public API requests, live text streams, JSON/media output, status and latency, cancellation and redacted curl. Auth choice (b): pasted public token stays in memory; normal scope, limits and caches apply. Shared `web/playground.js` is copied across all model and tool services.

- `run.bat`: runs `uv sync` directly; `python -m uv` failed when uv was installed only as a program (winget).
- Docker: `.dockerignore` keeps `.git`, `.venv`, tests and local state out of the build context (the same file in every model service).
- First version: TEM-XL/2 class-conditional ImageNet image generation (256x256) on the GPU, with the admin page, tokens
  (scope, rate limit, expiry), metrics, Settings card and update checks shared with the other model services.
- `POST /v1/generate` takes `class_id` or `label`, `steps`, `step_size` and `seed` and returns a PNG. `GET /v1/classes` lists the classes.
- Answer cache for images made with a seed (`TEM_CACHE_SIZE`, default 32, 0 = off; `X-Cache` header). No streaming.
- The weights are one pinned file downloaded from the authors' Google Drive and checked by SHA-256; `tem.py` is fetched at a pinned commit by `tools/fetch_tem.py` and is not part of this repository (no license stated upstream).
- `tools/bench.py` times a service and saves the pictures.
