# TEMImageModel: Docker Desktop on this PC

Run TEM-XL/2 ImageNet image generation on an NVIDIA GPU (about 4 GB of GPU memory free) in Docker Desktop on the machine you work on, so other programs on it can call it.

## Requirements
- Docker Desktop with Compose v2 (Windows: WSL2 backend).
- An NVIDIA GPU with a current driver, and GPU support in Docker Desktop. Check it: `docker run --rm --gpus all nvidia/cuda:12.6.0-base-ubuntu24.04 nvidia-smi` must print your card.
- Internet on the first start (the 2.4 GB checkpoint and the VAE, and `tools/fetch_tem.py` fetches `tem.py`).

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

## Daily use
```bash
docker compose ps          # state
docker compose logs -f tem
docker compose down        # stop (the weights volume is kept)
docker compose up -d --build && docker compose restart tem_lb   # after a code change
```

## Problems
| Symptom | Fix |
|---|---|
| `address already in use` on 9190 | Another copy (`run.bat`, or the same stack on another compose project) is running. Stop it or change `TEM_PORT`. |
| `/health` shows `ready: false` for minutes | First start: the weights are downloading or loading. Check `docker compose logs -f tem`. |
| 401 Invalid token | The caller's token is missing or revoked; make one on `/admin/`. |
| 503 `no GPU is visible here` | The container has no GPU. Enable GPU support in Docker Desktop and re-run the `nvidia-smi` check above. |
| Container restarts in a loop | Out of GPU memory. Close other GPU programs. |
