@echo off
REM Starts the tem service on port 9190 (syncs .venv with uv on each run). Needs an NVIDIA GPU with about 4 GB free.
REM The first start fetches tem.py and downloads the 2.4 GB checkpoint and the VAE.
REM LABEL: TEM Image Service
REM DESCRIPTION: Shared HTTP service that runs the TEM image generation model (ImageNet classes) on the GPU for every project.

cd /d "%~dp0"

python -m uv sync
if errorlevel 1 (
    echo uv sync failed. Install uv: winget install astral-sh.uv
    pause
    exit /b 1
)
call .venv\Scripts\activate

if not exist tem_code\tem.py python tools\fetch_tem.py
if errorlevel 1 (
    pause
    exit /b 1
)

python src/app.py
pause
