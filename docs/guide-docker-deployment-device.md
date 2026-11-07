# TEMImageModel: Docker on a deployment machine

Run TEM-XL/2 ImageNet image generation on an NVIDIA GPU (about 4 GB of GPU memory free) on a separate always-on machine (default `lex@scutiserver1.local`, folder
`/media/ZimaOS-HD/Apps/TEMImageModel`). Callers reach it over the published port.

## Requirements on the machine

- Docker + Compose v2, and ssh access (root over ssh is refused; use the normal user).
- Linux with an NVIDIA GPU, the NVIDIA driver and the NVIDIA Container Toolkit. Check it: `docker run --rm --gpus all nvidia/cuda:12.6.0-base-ubuntu24.04 nvidia-smi`.
- This service does not belong on a box without a GPU. The default Deploy target (`lex@scutiserver1.local`, ZimaOS) has none, so point `DEPLOY_HOST` and `DEPLOY_DIR` at the GPU machine (see step 1).

## 1. Publish the code (from your PC)

Run `TEMImageModel\run.bat` and choose **Deploy** (or `run.bat deploy`). Menu:

| Option | Does |
|---|---|
| 1 | Publish code to the `live` branch |
| 2 | Copy your `.env` to the server (one ssh/tar session, one password prompt) |
| 3 | Both |
| 4, 5 | Dry runs of 1 and 2 |
| 6 | chown helper, if option 2 says `Permission denied` |
| R | Release: publish, then tag `VERSION` |

Keep your own target in the git-ignored `tools\deploy.local.ini` (copy `tools\deploy.local.example.ini`), or set
`DEPLOY_HOST`, `DEPLOY_DIR` and `DEPLOY_WEB_PORT` before running. Commit `main` first: publish reads committed `main`.

## 2. First-time setup on the machine

```bash
mkdir -p /media/ZimaOS-HD/Apps
git clone -b live <your-repo-url> /media/ZimaOS-HD/Apps/TEMImageModel
cd /media/ZimaOS-HD/Apps/TEMImageModel
```
Create `.env` (deploy option 2 copies yours, or `cp .env.example .env` and edit):
- `TEM_ADMIN_PASSWORD`: a real password.
- `TEM_REPLICAS=1` unless you have the memory for more.
- `TEM_PORT=9190` (published on all interfaces; firewall it if the LAN should not reach it, or bind it to
  `127.0.0.1` in the `ports:` line of `tem_lb` when only callers on the machine need it).

## 3. Start

```bash
docker compose up -d --build
docker compose ps
curl http://127.0.0.1:9190/health
```
The first start downloads the 2.4 GB checkpoint and the VAE, and `tools/fetch_tem.py` fetches `tem.py` into the `models` volume; `tem_lb` waits for a healthy service
(up to 300 s grace).

## 4. Connect callers

1. Open `http://<machine-ip>:9190/admin/`, sign in with the admin password and create one token per caller
   (see [guide-web-ui.md](guide-web-ui.md)).
2. The caller holds the URL and token:
   - Caller on another machine: `http://<machine-ip>:9190`.
   - Caller in a Docker stack on the same machine: `http://host.docker.internal:9190`.
3. Try a call from the machine:
   ```bash
   curl -X POST http://127.0.0.1:9190/v1/generate -H "Content-Type: application/json" -H "X-Internal-Token: tem_..." -d '{"label":"golden retriever","seed":1}' -o dog.png
   ```

## Scaling

```bash
TEM_REPLICAS=2 docker compose up -d --build
docker compose restart tem_lb
```

The restart is needed because nginx resolves replica addresses once at start. Check that the GPU has about 4 GB per
replica (`nvidia-smi`).

## Updating

```bash
cd /media/ZimaOS-HD/Apps/TEMImageModel
git pull
docker compose up -d --build
docker compose restart tem_lb
```

## Releasing

A plain publish (`run.bat`, Deploy, option 1) only updates the `live` branch. For a release set `VERSION` (and
`pyproject.toml` to the same number), commit, then run `run.bat`, Deploy, option R or
`py tools\publish_live.py --release`. `run.bat`, Build the release ZIP, then builds `_zip_versions\TEMImageModel-<VERSION>.zip`.

## Problems

| Symptom | Fix |
|---|---|
| Caller cannot reach the service | Check the caller's URL and token, and that `curl http://<machine-ip>:9190/health` works. |
| nginx 502 after an update | `docker compose restart tem_lb`. |
| Permission denied on push | run.bat Deploy option 6. |
| Port 9190 in use | Another stack on the machine already publishes it. |
| 503 `no GPU is visible here` | Install the NVIDIA Container Toolkit and restart Docker, then re-run the `nvidia-smi` check. |
