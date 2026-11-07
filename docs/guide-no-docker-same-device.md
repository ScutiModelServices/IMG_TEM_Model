# IMG_TEM_Model: without Docker, on Windows

Run TEM-XL/2 ImageNet image generation on an NVIDIA GPU (about 4 GB of GPU memory free) directly with Python: one process, no load balancer, listening on `127.0.0.1:29240`.

## Requirements
- Windows with Python 3.11 or newer and uv (`winget install astral-sh.uv`).
- An NVIDIA GPU with a current driver. The `uv.lock` pins a CUDA build of torch, so no extra CUDA toolkit is needed.
- Internet on the first start (the 2.4 GB checkpoint and the VAE, and `tools/fetch_tem.py` fetches `tem.py`).

## Start
Double-click `run.bat`, or run it in a terminal from `IMG_TEM_Model\`. Choose **1 Run the service** in the menu, or run `run.bat run` to skip the menu. It runs `uv sync` to create or update `.venv`, then starts
`python src/app.py`. It also fetches `tem.py` into `_tem_code/` on the first run. The first start downloads the 2.4 GB checkpoint and the VAE, and `tools/fetch_tem.py` fetches `tem.py`.

Linux or macOS:
```bash
cd IMG_TEM_Model
uv sync
uv run python src/app.py
```
On macOS there is no NVIDIA GPU, so this service cannot run there.

## Settings
`run.bat` loads `.env` in this folder (copy `.env.example`) through `--dotenv` and prints the names it loaded, never the values; a real environment variable wins over it. A plain `python src/app.py` does not read `.env`. Set variables in `.env` or in the environment before starting:

| Variable | Default | Effect |
|---|---|---|
| `SERVICE_HOST` | `127.0.0.1` | Bind address. Use `0.0.0.0` only if other devices must reach it. |
| `SERVICE_PORT` | `29240` | Port. |
| `SERVICE_ADMIN_PASSWORD` | empty | Unlocks `/admin/` and requires tokens on every call but `/health`. Empty = no auth. |
| `SERVICE_WARM` | `1` | Load the model at start; with `0` the first request pays the load time. |
| `SERVICE_DEVICE` | `cuda` | `cpu` exists for tests only and is far too slow to use. |
| `SERVICE_MODELS_DIR` | the library's default cache | Folder for downloaded model weights. Sets `HF_HOME` (and `OLLAMA_MODELS` to `<folder>\ollama`) at start; a real `HF_HOME` or `OLLAMA_MODELS` wins. Docker keeps weights in the `_models` volume and ignores it. |

PowerShell: `$env:SERVICE_ADMIN_PASSWORD = "secret"; .\run.bat`
Bash: `SERVICE_ADMIN_PASSWORD=secret uv run python src/app.py`

## Check
```bash
curl http://127.0.0.1:29240/health
```
`ready` is `false` until the model has loaded. Then open `http://127.0.0.1:29240/admin/` (see [guide-web-ui.md](guide-web-ui.md)),
make a token, and try a call:
```bash
curl -X POST http://127.0.0.1:29240/v1/generate -H "Content-Type: application/json" -H "X-Internal-Token: tem_..." -d '{"label":"golden retriever","seed":1}' -o dog.png
```

## Stop
Ctrl+C in the terminal. Do not run this and the Docker stack together: both use port 29240.

## Tests
`uv run pytest`.
