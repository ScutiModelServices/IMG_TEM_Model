# TEMImageModel: Docker Desktop on this PC

Run TEM-XL/2 ImageNet image generation on an NVIDIA GPU (about 4 GB of GPU memory free) in Docker Desktop on the machine you work on, so other programs on it can call it.

## Requirements

- Docker Desktop with Compose v2 (Windows: WSL2 backend).
- An NVIDIA GPU with a current driver, and GPU support in Docker Desktop. Check it: `docker run --rm --gpus all nvidia/cuda:12.6.0-base-ubuntu24.04 nvidia-smi` must print your card.
- Network access on the first start: Google Drive (checkpoint), Hugging Face (VAE `stabilityai/sd-vae-ft-mse`) and
  GitHub at image build (`tem.py`, pinned commit).
- GPU memory per replica: about 4 GB at 256x256 (measured: 3.9 GB peak). A 6 GB card runs one replica; replicas
  share the GPU, so more replicas only help a bigger card.
- Disk: 2.4 GB for the checkpoint plus the VAE, in the `models` volume.

## Steps

1. Configure. In `TEMImageModel/`:
   ```bash
   cp .env.example .env
   ```
   Set `TEM_ADMIN_PASSWORD` (empty = no auth and no admin page, fine for a local test). Leave `TEM_PORT=9190`. Leave `TEM_REPLICAS=1`.
2. Start:
   ```bash
   docker compose up -d --build
   ```
   The first start downloads the 2.4 GB checkpoint and the VAE, and `tools/fetch_tem.py` fetches `tem.py` into the `models` volume. `tem_lb` starts only after the service is healthy
   (up to 300 s grace). Watch with `docker compose ps` and `docker compose logs -f tem`.
3. Check:
   ```bash
   curl http://127.0.0.1:9190/health
   ```
   `ready` is `false` until the model has loaded, then `true`.
4. Open the admin page: `http://127.0.0.1:9190/admin/` (see [guide-web-ui.md](guide-web-ui.md)) and make a token for each caller.
5. Try a call:
   ```bash
   curl -X POST http://127.0.0.1:9190/v1/generate -H "Content-Type: application/json" -H "X-Internal-Token: tem_..." -d '{"label":"golden retriever","seed":1}' -o dog.png
   ```
   Expect a PNG file, `dog.png`.
6. Callers connect to the published port. The caller holds the URL and token:
   - Caller on the host: `http://127.0.0.1:9190`.
   - Caller in another Docker stack on the same host: `http://host.docker.internal:9190`.

## Settings

In `.env` next to `docker-compose.yml`:

| Variable | Default | Effect |
|---|---|---|
| `TEM_REPLICAS` | `1` | Number of `tem` containers. Read by Compose. |
| `TEM_PORT` | `9190` | Host port `tem_lb` publishes. |
| `TEM_ADMIN_PASSWORD` | empty | Password for `/admin/`. When set, every call except `/health` must send a token as `X-Internal-Token`. Empty = no auth. |
| `TEM_NUM_THREAD` | torch decides | Starting value for the CPU threads card (the GPU does the sampling); a value saved on `/admin/` wins. |

On the **Settings** card of `/admin/` (saved in `settings.json` beside the tokens, shared by all replicas; a saved
value beats the environment variable named in brackets): update check hours (`TEM_UPDATE_CHECK_HOURS`, 6),
in-flight cap (`TEM_MAX_INFLIGHT`, 0 = 4), answers kept per replica (`TEM_CACHE_SIZE`, 32, 0 = off), most steps per
image (`TEM_MAX_STEPS`, 120), device (`TEM_DEVICE`, `cuda`, restart) and load at start (`TEM_WARM`, restart). Compose
does not pass these; add the variable under `environment:` of `tem` to use one as a starting value.

## Daily use

```bash
docker compose ps          # state
docker compose logs -f tem
docker compose down        # stop (the weights volume is kept)
docker compose up -d --build && docker compose restart tem_lb   # after a code change
```

## Time it

Try it and time it:

```bash
python tools/bench.py http://127.0.0.1:9190 --save out
```

## Problems

| Symptom | Fix |
|---|---|
| `address already in use` on 9190 | Another copy (`run.bat`, or the same stack on another compose project) is running. Stop it or change `TEM_PORT`. |
| `/health` shows `ready: false` for minutes | First start: the weights are downloading or loading. Check `docker compose logs -f tem`. |
| 401 Invalid token | The caller's token is missing or revoked; make one on `/admin/`. |
| 503 `no GPU is visible here` | The container has no GPU. Enable GPU support in Docker Desktop and re-run the `nvidia-smi` check above. |
| Container restarts in a loop | Out of GPU memory. Close other GPU programs. |
| `tem_lb` never starts | No replica is healthy yet (first download, or no GPU). `docker compose logs tem`. |
| 503 "tem.py is missing" | `tools/fetch_tem.py` failed at build, or `TEM_CODE_DIR` is wrong. Rebuild. |
| CUDA out of memory | Too many replicas for the card (about 4 GB each). Lower `TEM_REPLICAS`. |
| 403 "may not use model" | The token's list on `/admin/` does not include `tem-xl-256`. |
| 404 on `label` | No class has that name. `GET /v1/classes?q=` lists them. |
| 422 on `steps` | Above the *Most Langevin steps* setting. |
| 429 | Over the token's rate limit, or too many calls waiting for the model. |
| nginx 502 after scaling | `tem_lb` not restarted after the replica count changed. |
