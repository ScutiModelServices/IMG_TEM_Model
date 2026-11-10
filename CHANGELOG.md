# Changelog

## Unreleased

### Playground works behind a path-prefix proxy

The Try it panel built its request URLs from the page origin, so behind ServiceHub (`/s/<id>/`) it called the hub's root and got 404 Not Found. It now resolves routes against the service root (`../` from the admin page). Same-origin checking is unchanged.


### Playground: no token to paste

The Try it panel signs in with a temporary public token made from the admin session (named `playground (temporary)`, valid 1 day, revoked on sign-out or when the tab closes), so the service token field is hidden and choices such as voices load by themselves. The token shows in the tokens list while it lives.


- Env files: `run.bat` (`--dotenv`) now loads `.env.local`, then `.env`; the first file to set a name wins and a real environment variable still beats both, so a host run can keep `SERVICE_OLLAMA_URL=http://127.0.0.1:11434` in `.env.local` while Docker uses `http://host.docker.internal:11434`. `.env.compose` is for Docker Desktop on this device (`docker compose --env-file .env.compose up -d --build`). `.env` stays the file Deploy option 2 pushes to the deployment device, where a plain `docker compose up -d --build` reads it. `.env.local` and `.env.compose` are git-ignored and Docker-ignored (`.env.*`). New shared `settings.load_env_files`.
- Admin page and shared styles: polish layer in `web/index.html` (focus ring, hover and pressed states, layered shadow on the sign-in card and dialogs, tabular numbers, one entrance motion per page, themed scrollbars, `prefers-reduced-motion`). No behaviour change.

- Admin page: a closeable warning on the Overview appears while no weights are downloaded, with a button to the Updates page. While **Download new weights** runs, the Updates card shows a progress bar with megabytes downloaded (`progress` in `GET /admin/updates`; new shared `src/progress.py`). Replicas share the numbers through a small file next to the weights marker; where that folder is not shared (Ollama services) the bar shows on the replica doing the download.

- Admin UI: separate hash-routed pages in a collapsible sidebar; health-first Overview, one main-header page title, capability-specific navigation, draft-preserving navigation and responsive desktop/mobile layout. Existing admin and public API actions are preserved.

- Admin page: the CPU threads card and tile are hidden when `CONFIG.tags` has `host-threads`, and the Project models card is shown only with `project-models`.

- Admin page: `CONFIG.tags` (same tags as `docs/purpose.md`) switch tag-driven notes: `gpu` shows a CPU-threads note, `license-restricted` shows a licence note on the Updates card.

- Fix: after Download, a CPU threads change or a sync from another replica drops the loaded model, the service now reloads it in the background (when "Load the model at start" is on) instead of showing "Starting" on `/admin/` until the first request.
- Breaking: startup, warm-up and inference load downloaded weights only. Before first inference open `/admin/` → Updates → Download; an empty installation keeps health/admin available and returns 503 for inference.

- `SERVICE_MODELS_DIR` sets where a local (no Docker) run keeps downloaded model weights: `settings.apply_models_dir()` maps it to `HF_HOME` and `OLLAMA_MODELS` at start.
- Docs: `docs/guide-cli.md`, a PowerShell-only way to test the service.

### Breaking: common service environment variables

Service-owned environment variables now use `SERVICE_*`. Old names are no longer read.
Rename old names once in your real `.env`, Compose `environment:` block, and CI/secret settings.

| Old name | New name |
|---|---|
| `TEM_ADMIN_PASSWORD` | `SERVICE_ADMIN_PASSWORD` |
| `TEM_CACHE_SIZE` | `SERVICE_CACHE_SIZE` |
| `TEM_CODE_DIR` | `SERVICE_CODE_DIR` |
| `TEM_DEVICE` | `SERVICE_DEVICE` |
| `TEM_HOST` | `SERVICE_HOST` |
| `TEM_MAX_INFLIGHT` | `SERVICE_MAX_INFLIGHT` |
| `TEM_MAX_STEPS` | `SERVICE_MAX_STEPS` |
| `TEM_MODELS_DIR` | `SERVICE_MODELS_DIR` |
| `TEM_NUM_THREAD` | `SERVICE_NUM_THREAD` |
| `TEM_PORT` | `SERVICE_PORT` |
| `TEM_REPLICAS` | `SERVICE_REPLICAS` |
| `TEM_TOKENS_FILE` | `SERVICE_TOKENS_FILE` |
| `TEM_UPDATE_CHECK_HOURS` | `SERVICE_UPDATE_CHECK_HOURS` |
| `TEM_WARM` | `SERVICE_WARM` |
| `TEM_WEB_DIR` | `SERVICE_WEB_DIR` |
| `TEM_WEIGHTS_MARKER` | `SERVICE_WEIGHTS_MARKER` |

- Default HTTP port moves from 9190 to 29240. Update explicit old ports in your real `.env`, saved tool-service `backends.json` connections, and browser/MCP client configurations once. Compose now uses 29240 inside API replicas and nginx; deployments using the old Compose default must recreate containers. A custom host-port override stays in effect until you change it; container ports still move to 29240.

- Renamed `TEMImageModel` to `IMG_TEM_Model`; Docker project, API image, services, load balancer and volumes now use `img_tem_model` names. Callers on `citadel_core` connect to `img_tem_model_lb` at the existing port.
- Docker volume migration: existing volumes with old names are orphaned; renaming does not move data. Stop the old stack before copying; never use `down -v`. The commands below assume the previous default Compose project name; substitute actual volume names if `-p` or `COMPOSE_PROJECT_NAME` overrode it.
  - `tem_models` → `img_tem_model_models`: `docker volume inspect tem_models && docker volume create img_tem_model_models && docker run --rm -v tem_models:/from:ro -v img_tem_model_models:/to alpine:3.21 sh -c "cd /from && cp -a . /to/"`
  - `tem_tokens` → `img_tem_model_data`: `docker volume inspect tem_tokens && docker volume create img_tem_model_data && docker run --rm -v tem_tokens:/from:ro -v img_tem_model_data:/to alpine:3.21 sh -c "cd /from && cp -a . /to/"`
- To retain an old volume instead, set its top-level volume definition to `external: true` and `name: <old-volume-name>` in a local Compose override. Rollback: stop the renamed stack, restore the previous checkout and folder name, and restart the old stack with its original volumes; copy back newer data first if the renamed stack accepted writes.

- `run.bat` loads `.env` from the service folder for a local run: it passes `--dotenv`, the service prints which variable names it loaded (never the values), and a real environment variable still wins. A plain `python src/app.py` and Docker never read `.env`.
- Untracked folders now start with `.` or `_`: `zip_versions/` is `_zip_versions/`, `tem_code/` to `_tem_code/`. A local `voices`, `tem_code` or `zip_versions` folder from an older checkout needs renaming by hand.
- `run.bat` is now a menu (run the service, deploy, build the release ZIP) and `run.bat run|deploy|zip` skips it. `tools/deploy.bat`, `tools/make_zip.bat` and `tools/deploy.local.example.bat` are gone; the local deploy target is `tools/deploy.local.ini` (copy `tools/deploy.local.example.ini`).
- Admin page: **Connect to this service** card with the addresses other services can use (this page's address, same PC, Docker network, `host.docker.internal`) and every endpoint, each with a Copy button.
- Admin **Try it** panel: descriptor-driven public API requests, live text streams, JSON/media output, status and latency, cancellation and redacted curl. Auth choice (b): pasted public token stays in memory; normal scope, limits and caches apply. Shared `web/playground.js` is copied across all model and tool services.

- `run.bat`: runs `uv sync` directly; `python -m uv` failed when uv was installed only as a program (winget).
- Docker: `.dockerignore` keeps `.git`, `.venv`, tests and local state out of the build context (the same file in every model service).
- First version: TEM-XL/2 class-conditional ImageNet image generation (256x256) on the GPU, with the admin page, tokens
  (scope, rate limit, expiry), metrics, Settings card and update checks shared with the other model services.
- `POST /v1/generate` takes `class_id` or `label`, `steps`, `step_size` and `seed` and returns a PNG. `GET /v1/classes` lists the classes.
- Answer cache for images made with a seed (`SERVICE_CACHE_SIZE`, default 32, 0 = off; `X-Cache` header). No streaming.
- The weights are one pinned file downloaded from the authors' Google Drive and checked by SHA-256; `tem.py` is fetched at a pinned commit by `tools/fetch_tem.py` and is not part of this repository (no license stated upstream).
- `tools/bench.py` times a service and saves the pictures.
