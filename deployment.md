# Deploying TEMImageModel

TEMImageModel is one HTTP service (port 9190). It runs as `tem` replicas behind an nginx load balancer, `tem_lb`.
Callers use `http://<host>:9190`; they never reach a replica directly.

## Requirements

- Docker with Compose v2, an NVIDIA GPU, the NVIDIA driver and the NVIDIA Container Toolkit on the host. The CUDA
  libraries come with the torch wheel inside the image (the image is several GB).
- GPU memory per replica: about 4 GB at 256x256 (measured: 3.9 GB peak). A 6 GB card runs one replica; replicas
  share the GPU, so more replicas only help a bigger card.
- Disk: 2.4 GB for the checkpoint plus the VAE, in the `models` volume.
- Network access on the first start: Google Drive (checkpoint), Hugging Face (VAE `stabilityai/sd-vae-ft-mse`) and
  GitHub at image build (`tem.py`, pinned commit).

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

## Start

```bash
docker compose up -d --build
curl http://127.0.0.1:9190/health
```

Expect `"ready": true` once a replica has loaded the model. The first start downloads about 2.7 GB into the `models`
volume, so `tem_lb` can take several minutes to appear (the health check allows 300 s before failures count; run
`docker compose ps` and wait; on a slow link raise `start_period`).

Try it and time it:

```bash
python tools/bench.py http://127.0.0.1:9190 --save out
```

## Scaling

```bash
TEM_REPLICAS=2 docker compose up -d --build
docker compose restart tem_lb
```

The restart is needed because nginx resolves replica addresses once at start. Check that the GPU has about 4 GB per
replica (`nvidia-smi`).

## Updating the files

The weights are one pinned file (SHA-256 in `src/engine.py`). The **Updates** card shows it as current when the file is
there, and **Download new weights** fetches it again, checks the hash, and makes every replica drop its loaded copy.
A new TEM release needs a new pin in `src/engine.py` and `tools/fetch_tem.py`. Updating the service itself:
`docker compose up -d --build`, then `docker compose restart tem_lb`.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| `tem_lb` never starts | No replica is healthy yet (first download, or no GPU). `docker compose logs tem`. |
| 503 "no GPU is visible" | The container has no GPU: check the NVIDIA Container Toolkit, or set the device to `cpu` for a test. |
| 503 "tem.py is missing" | `tools/fetch_tem.py` failed at build, or `TEM_CODE_DIR` is wrong. Rebuild. |
| CUDA out of memory | Too many replicas for the card (about 4 GB each). Lower `TEM_REPLICAS`. |
| 401 "Invalid token" | The caller sends no token, or a revoked one. |
| 403 "may not use model" | The token's list on `/admin/` does not include `tem-xl-256`. |
| 404 on `label` | No class has that name. `GET /v1/classes?q=` lists them. |
| 422 on `steps` | Above the *Most Langevin steps* setting. |
| 429 | Over the token's rate limit, or too many calls waiting for the model. |
| nginx 502 after scaling | `tem_lb` not restarted after the replica count changed. |

## Releasing

A plain publish (`tools\deploy.bat` option 1) only updates the `live` branch. For a release set `VERSION` (and
`pyproject.toml` to the same number), commit, then run `tools\deploy.bat` option R or
`py tools\publish_live.py --release`. `tools\make_zip.bat` then builds `zip_versions\TEMImageModel-<VERSION>.zip`.


## Verify with Try it

After deployment, open `/admin/` and use **Try it** with a public service token to exercise the deployed public route. It uses normal scope, admission/rate limits and cache behavior, so busy or unauthorized requests remain visible as HTTP errors. No new environment setting or admin-to-public auth bypass is introduced. Deploy the complete `web/` directory, including `playground.js`. See [the web UI guide](docs/guide-web-ui.md#try-it-send-a-real-request) for input formats, limits and token handling.
