"""TEM (Transformer Energy Model) image generation, run in this process on the GPU.

TEM-XL/2 is a class-conditional ImageNet model (256x256) from "Scaling Transformer Energy-based Models For High Quality
Image Synthesis". An image is made by Langevin sampling: start from noise in the Stable Diffusion VAE latent space, take
`steps` gradient steps down the model's energy, then decode with the VAE. One generation runs at a time per replica
(about 4 GB of GPU memory at batch size 1); scale with replicas or more GPUs.

The model code (tem.py) is not part of this repository: `tools/fetch_tem.py` downloads it at a pinned commit.
Every call starts from fresh noise (no shared replay buffer), so the images can differ from the paper's FID setup.

shortcut: the weights are one pinned file, so the update check only reports a missing or damaged file, never a newer one."""

from __future__ import annotations

import asyncio
import hashlib
import io
import logging
import os
import re
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Callable

_log = logging.getLogger(__name__)

MODEL_NAME = "tem-xl-256"  # what a token's "projects" list limits
CHECKPOINT_FILE = "TEM-XL-2_imagenet256_ema.pth"
CHECKPOINT_SHA256 = "02eee5f8d90a633055ae0441559ee5ae89928bc1cb4dfa931ae3bae2ba55e4f8"
CHECKPOINT_DRIVE_ID = "1xBJOjGM-Wrdr-hEUNAdLt9Kj__TKzLHs"  # published by the authors, github.com/int-lee/TEM
VAE_REPO = "stabilityai/sd-vae-ft-mse"
VAE_SCALE = 0.18215
LATENT_SIZE, LATENT_CHANNELS, NUM_CLASSES = 32, 4, 1000
NOISE_STD, CLIP_NORM = 0.05, 100.0  # the paper's values for 256 px


class EngineError(RuntimeError):
    """The image could not be made. `status` is the HTTP status the service maps it to."""

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


def imagenet_classes() -> list[str]:
    """The 1000 ImageNet class names, in label order."""
    try:
        from torchvision.models._meta import _IMAGENET_CATEGORIES

        return list(_IMAGENET_CATEGORIES)
    except Exception:  # names are a convenience; ids always work
        return [f"class {i}" for i in range(NUM_CLASSES)]


class Sampler:
    """A loaded model that turns a class into a PNG."""

    def __init__(self, model: Any, vae: Any, device: str) -> None:
        self._model, self._vae, self._device = model, vae, device

    def generate(self, class_id: int, steps: int, step_size: float, seed: int, threads: int | None) -> bytes:
        import numpy as np
        import torch
        from PIL import Image

        if threads:
            torch.set_num_threads(threads)
        dev = torch.device(self._device)
        gen = torch.Generator(device=dev).manual_seed(seed)
        x = torch.randn(1, LATENT_CHANNELS, LATENT_SIZE, LATENT_SIZE, device=dev, generator=gen)
        label = torch.tensor([class_id], device=dev)
        for step in range(steps):
            x.requires_grad_(True)
            if step < steps - 1:  # the last step is noise-free
                x = x + torch.randn(x.shape, device=dev, generator=gen) * NOISE_STD
            with torch.autocast(dev.type, dtype=torch.bfloat16, enabled=dev.type == "cuda"):
                energy = self._model(x, label)
            grad = torch.autograd.grad(energy.sum(), x)[0]
            x = x - step_size * grad
            norm = x.flatten(1).norm(dim=1).view(-1, 1, 1, 1)
            x = (x * torch.clamp(CLIP_NORM / norm, max=1.0)).detach()
        with torch.no_grad():
            pixels = (self._vae.decode(x / VAE_SCALE).sample * 127.5 + 128.0).clamp(0, 255)
        array = pixels[0].permute(1, 2, 0).to(torch.uint8).cpu().numpy()
        buf = io.BytesIO()
        Image.fromarray(np.ascontiguousarray(array)).save(buf, "PNG")
        return buf.getvalue()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(1 << 20):
            digest.update(block)
    return digest.hexdigest()


def code_dir() -> Path:
    return Path(os.environ.get("SERVICE_CODE_DIR", Path(__file__).resolve().parents[1] / "_tem_code"))


def models_dir() -> Path:
    return Path(os.environ.get("SERVICE_MODELS_DIR") or os.environ.get("HF_HOME") or "~/.cache/tem").expanduser()


def load(checkpoint: Path, device: str) -> Sampler:
    """Reads the checkpoint (tensors only, never pickled code) and the VAE. Blocking: run it in a thread."""
    import torch

    if device.startswith("cuda") and not torch.cuda.is_available():
        raise EngineError("The device is cuda but no GPU is visible here. Install a CUDA build of torch or set the device to cpu.", 503)
    if not (code_dir() / "tem.py").is_file():
        raise EngineError(f"tem.py is missing in {code_dir()}; run tools/fetch_tem.py", 503)
    if str(code_dir()) not in sys.path:
        sys.path.insert(0, str(code_dir()))
    from diffusers import AutoencoderKL
    from tem import build_tem

    data = torch.load(checkpoint, map_location="cpu", mmap=True, weights_only=True)
    state = {key.removeprefix("module."): value for key, value in data["ema_model_state_dict"].items()}
    heads = tuple(data["head_layers"]) if data.get("head_layers") is not None else None
    model = build_tem("XL", input_size=LATENT_SIZE, in_channels=LATENT_CHANNELS,
                      num_classes=state["y_embedder.embedding_table.weight"].shape[0], patch_size=2,
                      num_energy_heads=3, head_layers=heads)
    model.load_state_dict(state)
    model = model.to(device).eval().requires_grad_(False)
    vae = AutoencoderKL.from_pretrained(VAE_REPO, cache_dir=str(models_dir() / "hub"), local_files_only=True).to(device).eval().requires_grad_(False)
    return Sampler(model, vae, device)


def _download(checkpoint: Path) -> None:
    """Fetches the published file from Google Drive and keeps it only if its SHA-256 is the pinned one."""
    import gdown
    from huggingface_hub import snapshot_download
    from progress import tracking

    checkpoint.parent.mkdir(parents=True, exist_ok=True)
    temp = checkpoint.with_name(f"{checkpoint.name}.{uuid.uuid4().hex}.part")
    try:
        with tracking("TEM checkpoint", None, checkpoint.parent):  # the .part file grows in this folder
            ok = gdown.download(id=CHECKPOINT_DRIVE_ID, output=str(temp), quiet=True)
        if not ok:
            raise EngineError("The download from Google Drive failed", 502)
        if _sha256(temp) != CHECKPOINT_SHA256:
            raise EngineError("The downloaded file does not match the published SHA-256", 502)
        snapshot_download(VAE_REPO, cache_dir=str(models_dir() / "hub"))
        os.replace(temp, checkpoint)
    finally:
        temp.unlink(missing_ok=True)


def _cached_sha(checkpoint: Path) -> str | None:
    """The pinned hash when the file is there. Hashing 2.4 GB on every check is too slow, so only the size is compared;
    a damaged file of the right size is caught when the weights are downloaded again."""
    if not checkpoint.is_file() or checkpoint.stat().st_size <= 2_000_000_000:
        return None
    from huggingface_hub import snapshot_download
    try:
        vae = Path(snapshot_download(VAE_REPO, cache_dir=str(models_dir() / "hub"), local_files_only=True))
        complete = (vae / "config.json").is_file() and any((vae / name).is_file() for name in ("diffusion_pytorch_model.bin", "diffusion_pytorch_model.safetensors"))
        return CHECKPOINT_SHA256 if complete else None
    except (OSError, ValueError):
        return None


def default_marker() -> Path:
    """File in the shared models volume whose content changes when one replica downloads new weights."""
    configured = os.environ.get("SERVICE_WEIGHTS_MARKER")
    return Path(configured) if configured else models_dir() / ".tem-weights-version"


class TEMEngine:
    """The `loader`, `remote_sha`, `cached_sha` and `download` callables are injectable for tests."""

    def __init__(self, checkpoint: str | os.PathLike[str] | None = None, device: str = "cuda", *, marker: Path | None = None,
                 loader: Callable[[Path, str], Sampler] = load, remote_sha: Callable[[], str] = lambda: CHECKPOINT_SHA256,
                 cached_sha: Callable[[Path], str | None] = _cached_sha, download: Callable[[Path], None] = _download) -> None:
        self.model = MODEL_NAME
        self.checkpoint = Path(checkpoint) if checkpoint else models_dir() / CHECKPOINT_FILE
        self.device = device
        self.classes = imagenet_classes()
        self._threads: int | None = None
        self._marker = marker
        self._seen = self._read_marker()
        self._loader = loader
        self._remote_sha_of, self._cached_sha_of, self._download_of = remote_sha, cached_sha, download
        self._loaded: Sampler | None = None
        self._load_lock = threading.Lock()
        self._gate = asyncio.Semaphore(1)
        self.generation = 0  # part of the answer cache key; changes whenever the loaded model is dropped

    @property
    def num_thread(self) -> int | None:
        return self._threads

    @num_thread.setter
    def num_thread(self, count: int) -> None:
        self._threads = count  # read on every call; the model stays loaded

    @property
    def ready(self) -> bool:
        return self._loaded is not None

    async def close(self) -> None:
        self._loaded = None

    async def warm(self) -> None:
        """Load the model now so the first request does not pay for it."""
        await asyncio.to_thread(self._sampler)

    def _sampler(self) -> Sampler:
        with self._load_lock:
            if self._loaded is None:
                if self._cached_sha_of(self.checkpoint) is None:
                    raise EngineError("Model weights are not downloaded. Ask an admin to press Download on the Updates card.", 503)
                self._loaded = self._loader(self.checkpoint, self.device)
            return self._loaded

    def resolve_class(self, class_id: int | None, label: str | None) -> int:
        """The class number for an id or a name (exact, else the one class that contains the text)."""
        if class_id is not None:
            if not 0 <= class_id < len(self.classes):
                raise EngineError(f"class_id must be 0 to {len(self.classes) - 1}", 422)
            return class_id
        needle = (label or "").strip().lower()
        exact = [i for i, name in enumerate(self.classes) if needle in {part.strip().lower() for part in name.split(",")}]
        found = exact or [i for i, name in enumerate(self.classes) if needle and needle in name.lower()]
        if len(found) == 1:
            return found[0]
        if not found:
            raise EngineError(f"No class is named {label!r}; GET /v1/classes?q= lists them", 404)
        raise EngineError(f"{label!r} fits {len(found)} classes ({', '.join(self.classes[i] for i in found[:5])}, ...); use class_id", 422)

    async def generate(self, class_id: int, steps: int, step_size: float, seed: int) -> bytes:
        async with self._gate:
            return await asyncio.to_thread(self._generate, class_id, steps, step_size, seed)

    def _generate(self, class_id: int, steps: int, step_size: float, seed: int) -> bytes:
        return self._sampler().generate(class_id, steps, step_size, seed, self._threads)

    # Updates: one pinned checkpoint file, shared by all replicas through one models volume.

    async def cached_sha(self) -> str | None:
        return await asyncio.to_thread(self._cached_sha_of, self.checkpoint)

    async def remote_sha(self) -> str:
        return await asyncio.to_thread(self._remote_sha_of)

    async def pull(self) -> None:
        await asyncio.to_thread(self._download_of, self.checkpoint)

    async def unload(self) -> None:
        """Forget the loaded model here and tell the other replicas to do the same; the next call loads the new file."""
        if self._marker is not None:
            self._marker.parent.mkdir(parents=True, exist_ok=True)
            self._seen = uuid.uuid4().hex
            self._marker.write_text(self._seen, "utf-8")
        self._forget()

    def sync(self) -> None:
        """Called every second: drop the loaded model when another replica downloaded a new file."""
        current = self._read_marker()
        if current != self._seen:
            self._seen = current
            self._forget()

    def _forget(self) -> None:
        with self._load_lock:
            self._loaded = None
            self.generation += 1  # kept answers are from the old file

    def _read_marker(self) -> str | None:
        try:
            return self._marker.read_text("utf-8") if self._marker else None
        except OSError:
            return None
