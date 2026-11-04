# Changelog

## Unreleased

- First version: TEM-XL/2 class-conditional ImageNet image generation (256x256) on the GPU, with the admin page, tokens
  (scope, rate limit, expiry), metrics, Settings card and update checks shared with the other model services.
- `POST /v1/generate` takes `class_id` or `label`, `steps`, `step_size` and `seed` and returns a PNG. `GET /v1/classes` lists the classes.
- Answer cache for images made with a seed (`TEM_CACHE_SIZE`, default 32, 0 = off; `X-Cache` header). No streaming.
- The weights are one pinned file downloaded from the authors' Google Drive and checked by SHA-256; `tem.py` is fetched at a pinned commit by `tools/fetch_tem.py` and is not part of this repository (no license stated upstream).
- `tools/bench.py` times a service and saves the pictures.
