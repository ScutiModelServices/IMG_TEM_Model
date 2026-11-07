# syntax=docker/dockerfile:1
# Needs an NVIDIA GPU, the host driver and the NVIDIA Container Toolkit; the CUDA libraries come with the torch wheel.
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.13.6 /uv /usr/local/bin/uv
ENV SERVICE_WEB_DIR=/app/web SERVICE_TOKENS_FILE=/data/tokens.json SERVICE_CODE_DIR=/app/_tem_code SERVICE_MODELS_DIR=/models PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/opt/venv PATH="/opt/venv/bin:$PATH" HF_HOME=/models SERVICE_HOST=0.0.0.0
WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY tools/fetch_tem.py ./tools/fetch_tem.py
RUN python tools/fetch_tem.py /app/_tem_code
COPY src ./src
COPY web ./web

ENV SERVICE_PORT=29240
EXPOSE 29240
CMD ["python", "src/app.py"]
