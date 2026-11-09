# IMG_TEM_Model

TEM image generation, served over HTTP so projects ask for a picture instead of loading a model themselves. TEM
(Transformer Energy Model, [paper](https://arxiv.org/abs/2610.31889), [code](https://github.com/int-lee/TEM)) is a
class-conditional ImageNet model: you name one of 1000 classes ("volcano", "golden retriever") and get a 256x256 PNG.
There are **no text prompts**. The service has the same admin page, tokens, rate limits, metrics, settings and update
checks as `DSC_Laya_Model`, `CNV_MiniCPM52B_Model`, `CNV_BitNet2B_Model`, `TTS_Piper_Model` and `TTS_Paradee_Model`.

The model runs in this process on an **NVIDIA GPU** (about 4 GB of GPU memory, 6.8 s per image on a laptop RTX 4050).
The weights are a 2.4 GB file published by the authors on Google Drive; the admin Download installs it and checks its
SHA-256. **The TEM code and weights have no stated license**: use this for your own projects and ask the authors before
anything else. This repository does not contain `tem.py`; `tools/fetch_tem.py` downloads it at a pinned commit.

## API

| Call | Purpose |
|---|---|
| `POST /v1/generate` | `{"class_id" or "label", "steps", "step_size", "seed"}` returns a PNG (`image/png`, 256x256). Headers: `X-Class-Id`, `X-Class-Label`, `X-Seed`, `X-Steps`, `X-Duration-Ms`, `X-Cache` (`hit` when the kept image was sent). |
| `GET /v1/classes?q=` | `{"classes": [{"id", "name"}]}`; `q` keeps the names containing that text. |
| `GET /health` | `{"status": "ok", "model", "ready", "num_thread", "device"}`; `ready` is true once the model is loaded. No token needed. |

Send exactly one of `class_id` (0 to 999) or `label` (an ImageNet class name; exact, else the one class that contains
the text; 404 if none, 422 if several, with a hint to use `class_id`). `steps` is the number of Langevin steps (default
60 as in the paper, at most the *Most Langevin steps* setting, default 120; more steps are slower). `step_size`
defaults to 500. `seed` makes the call repeatable: the same request with the same seed gives the same picture (up to
GPU rounding); without a seed one is drawn and sent back in `X-Seed`. Other fields are refused with 422.

Every call starts from fresh noise. The paper's best FID uses a shared buffer of earlier results; this service does not,
so the pictures can differ in quality from the paper's (they looked good in tests, with no FID measured).

**Cache.** The *Answers kept per replica* setting (`SERVICE_CACHE_SIZE`, default 32, 0 = off) keeps the last images made
**with a seed**; the same class, steps, step size and seed is sent again without sampling (`X-Cache: hit`).
Calls without a seed are never kept. An image over 1 MB is not kept. The cache is per replica and is emptied when the
weights are reloaded.

A token's *projects* list on the admin page limits the models it may use; there is one model, `tem-xl-256`.

## Admin page

`/admin/` (password `SERVICE_ADMIN_PASSWORD`): tokens with model scope, rate limit and expiry, usage numbers, CPU threads,
the Settings card (update check hours, in-flight cap, answers kept, most steps, device, load at start), and the
Updates card. The weights are one pinned file, so **Check now** only finds a missing file and **Download new weights**
downloads it again (after checking the hash). `/metrics` (admin password) is Prometheus text per token;
`tem_request_seconds` is a histogram of how long each `/v1` call took on that replica.

## Run

Weights load only from downloaded files. An empty installation still serves `/admin/` and `/health` with `ready: false`; inference returns 503. Open `/admin/` → **Updates** → **Download** before the first inference. Checks run online without downloading; only an admin Download replaces weights and reloads replicas.

```bash
docker compose --env-file .env.compose up -d --build        # http://<host>:29240, needs the NVIDIA Container Toolkit
```

Without Docker: `run.bat` (uv, listens on `127.0.0.1:29240`). Setup fetches `tem.py`; admin Download installs the 2.4 GB
checkpoint and the VAE. Time and try it: `python tools/bench.py http://127.0.0.1:29240 --save out`. See `deployment.md`.

## Tests

```bash
uv sync
uv run pytest
```

`tests/test_real_model.py` runs the real model and is skipped without `_tem_code/`, the checkpoint (`SERVICE_MODELS_DIR`)
and a GPU.

## Limits worth knowing

- ImageNet classes only, 256x256 only (the authors published no 512 checkpoint). No text prompts, no editing.
- One generation at a time per replica (batching four images on a 6 GB card was slower per image, so there is none);
  extra calls wait, and more than the in-flight cap get 429.
- No streaming. The reply is the finished PNG.
- 60 steps took about 7 s on a laptop RTX 4050; a CPU takes minutes.
- The rate limit is per replica.

## Try it from the admin page

Open `/admin/` and use **Try it** to call the public API with a service token held only in memory. Runs use normal token scopes, limits and caches; the panel shows HTTP status, latency, responses, cancellation and a curl equivalent with a token placeholder. See [the web UI guide](docs/guide-web-ui.md#try-it-send-a-real-request).

Generate sends exactly one ImageNet class label or class ID to `POST /v1/generate`, with steps, step size and an optional seed. TEM does not accept a freeform image prompt. The PNG result is shown inline with a download. Only seeded calls are cached; a token's projects list limits the model name `tem-xl-256`.

## Documentation

- [Purpose: input, output and what it is for](docs/purpose.md)
- [Deployment](deployment.md)
- [Changelog](CHANGELOG.md)
- [Docker on another machine](docs/guide-docker-deployment-device.md)
- [Docker on this PC](docs/guide-docker-same-device.md)
- [Run without Docker](docs/guide-no-docker-same-device.md)
- [Test it from the command line](docs/guide-cli.md)

## Admin pages and navigation

Open `/admin/` and sign in. Overview opens first; each sidebar destination has its own URL fragment and supports browser Back/Forward and direct links:

- `#overview`: health, model readiness, replicas, active tokens and request counts.
- `#playground`: service-specific request forms and streamed or media responses.
- `#tokens`: create, edit, expire and revoke scoped access tokens.
- `#runtime`: CPU threads where supported, replica information and live/restart settings.
- `#updates`: check versions and explicitly download weights.
- `#connections`: caller addresses and public endpoints.
- `#models` and `#voices`: project models and cloned voices, shown only when supported.

Collapse/Expand switches between labeled sidebar and icon rail on desktop and mobile. The non-secret sidebar preference is saved per service in this browser. Navigation preserves form drafts and active Playground requests; sign-out still clears credentials and cancels work. Page names appear once in the main header. No preview data or cross-service selector ships in the real admin UI. Existing authentication, quotas, settings precedence and explicit-download policy remain in effect.
