# IMG_TEM_Model: Docker Desktop on this PC

Run TEM-XL/2 ImageNet image generation on an NVIDIA GPU (about 4 GB of GPU memory free) in Docker Desktop on the machine you work on, so other programs on it can call it.

## Requirements

- Docker Desktop with Compose v2 (Windows: WSL2 backend).
- An NVIDIA GPU with a current driver, and GPU support in Docker Desktop. Check it: `docker run --rm --gpus all nvidia/cuda:12.6.0-base-ubuntu24.04 nvidia-smi` must print your card.
- Network access for admin Download: Google Drive (checkpoint), Hugging Face (VAE `stabilityai/sd-vae-ft-mse`) and
  GitHub at image build (`tem.py`, pinned commit).
- GPU memory per replica: about 4 GB at 256x256 (measured: 3.9 GB peak). A 6 GB card runs one replica; replicas
  share the GPU, so more replicas only help a bigger card.
- Disk: 2.4 GB for the checkpoint plus the VAE, in the `img_tem_model_models` volume.

## Steps

1. Configure. In `IMG_TEM_Model/`:
   ```bash
   cp .env.example .env
   ```
   Set `SERVICE_ADMIN_PASSWORD` (empty = no auth and no admin page, fine for a local test). Leave `SERVICE_PORT=29240`. Leave `SERVICE_REPLICAS=1`.
2. Start:
   ```bash
   docker compose --env-file .env.compose up -d --build
   ```
   The admin Download installs the 2.4 GB checkpoint and VAE; `tools/fetch_tem.py` fetches `tem.py` into the `img_tem_model_models` volume. `img_tem_model_lb` starts only after the service is healthy
   (up to 300 s grace). Watch with `docker compose ps` and `docker compose logs -f img_tem_model`.
3. Check:
   ```bash
   curl http://127.0.0.1:29240/health
   ```
   `ready` is `false` until the model has loaded, then `true`.
4. Open the admin page: `http://127.0.0.1:29240/admin/` (see [guide-web-ui.md](guide-web-ui.md)) and make a token for each caller.
5. Try a call:
   ```bash
   curl -X POST http://127.0.0.1:29240/v1/generate -H "Content-Type: application/json" -H "X-Internal-Token: tem_..." -d '{"label":"golden retriever","seed":1}' -o dog.png
   ```
   Expect a PNG file, `dog.png`.
6. Callers connect to the published port. The caller holds the URL and token:
   - Caller on the host: `http://127.0.0.1:29240`.
   - Caller in another Docker stack on the same host: `http://host.docker.internal:29240`.

## Settings

In `.env.compose` next to `docker-compose.yml` (start with `docker compose --env-file .env.compose up -d --build`):

| Variable | Default | Effect |
|---|---|---|
| `SERVICE_REPLICAS` | `1` | Number of `img_tem_model` containers. Read by Compose. |
| `SERVICE_PORT` | `29240` | Host port `img_tem_model_lb` publishes. |
| `SERVICE_ADMIN_PASSWORD` | empty | Password for `/admin/`. When set, every call except `/health` must send a token as `X-Internal-Token`. Empty = no auth. |
| `SERVICE_NUM_THREAD` | torch decides | Starting value for the CPU threads card (the GPU does the sampling); a value saved on `/admin/` wins. |

On the **Settings** card of `/admin/` (saved in `settings.json` beside the tokens, shared by all replicas; a saved
value beats the environment variable named in brackets): update check hours (`SERVICE_UPDATE_CHECK_HOURS`, 6),
in-flight cap (`SERVICE_MAX_INFLIGHT`, 0 = 4), answers kept per replica (`SERVICE_CACHE_SIZE`, 32, 0 = off), most steps per
image (`SERVICE_MAX_STEPS`, 120), device (`SERVICE_DEVICE`, `cuda`, restart) and load at start (`SERVICE_WARM`, restart). Compose
does not pass these; add the variable under `environment:` of `img_tem_model` to use one as a starting value.

## Daily use

```bash
docker compose ps          # state
docker compose logs -f img_tem_model
docker compose down        # stop (the weights volume is kept)
docker compose --env-file .env.compose up -d --build && docker compose restart img_tem_model_lb   # after a code change
```

## Time it

Try it and time it:

```bash
python tools/bench.py http://127.0.0.1:29240 --save out
```

## Problems

| Symptom | Fix |
|---|---|
| `address already in use` on 29240 | Another copy (`run.bat`, or the same stack on another compose project) is running. Stop it or change `SERVICE_PORT`. |
| `/health` shows `ready: false` for minutes | Download weights from the Updates card, then wait for loading. Check `docker compose logs -f img_tem_model`. |
| 401 Invalid token | The caller's token is missing or revoked; make one on `/admin/`. |
| 503 `no GPU is visible here` | The container has no GPU. Enable GPU support in Docker Desktop and re-run the `nvidia-smi` check above. |
| Container restarts in a loop | Out of GPU memory. Close other GPU programs. |
| `img_tem_model_lb` never starts | No replica is healthy yet (startup failure, or no GPU). `docker compose logs img_tem_model`. |
| 503 "tem.py is missing" | `tools/fetch_tem.py` failed at build, or `SERVICE_CODE_DIR` is wrong. Rebuild. |
| CUDA out of memory | Too many replicas for the card (about 4 GB each). Lower `SERVICE_REPLICAS`. |
| 403 "may not use model" | The token's list on `/admin/` does not include `tem-xl-256`. |
| 404 on `label` | No class has that name. `GET /v1/classes?q=` lists them. |
| 422 on `steps` | Above the *Most Langevin steps* setting. |
| 429 | Over the token's rate limit, or too many calls waiting for the model. |
| nginx 502 after scaling | `img_tem_model_lb` not restarted after the replica count changed. |

The load balancer also joins external `citadel_core` as `img_tem_model_lb`. Start the Citadel stack first so that network exists; tool services on it use `http://img_tem_model_lb:29240`. Docker project and API image are `img_tem_model` and `img_tem_model:latest`; persistent volumes have explicit `img_tem_model_*` names. Volume migration and rollback instructions are in [CHANGELOG.md](../CHANGELOG.md).

Before first inference, follow [Downloaded weights](guide-web-ui.md#downloaded-weights): open `/admin/` → Updates → Download. Startup never downloads weights.
