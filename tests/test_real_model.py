"""Runs the real model: needs _tem_code/tem.py (tools/fetch_tem.py), the checkpoint in SERVICE_MODELS_DIR and a GPU.
Skipped when any of them is missing."""
import io
import os
from pathlib import Path

import pytest

import engine as engine_module
from engine import CHECKPOINT_FILE, TEMEngine

CHECKPOINT = engine_module.models_dir() / CHECKPOINT_FILE


def _gpu() -> bool:
    try:
        import torch

        return torch.cuda.is_available()
    except ImportError:
        return False


pytestmark = [pytest.mark.real_model,
              pytest.mark.skipif(not (engine_module.code_dir() / "tem.py").is_file() or not CHECKPOINT.is_file() or not _gpu(),
                                 reason="needs _tem_code/tem.py, the checkpoint and a GPU")]


def test_same_seed_gives_the_same_picture_and_a_class_changes_it():
    import asyncio

    from PIL import Image

    engine = TEMEngine(CHECKPOINT, "cuda")
    first = asyncio.run(engine.generate(980, 20, 500.0, 1))
    again = asyncio.run(engine.generate(980, 20, 500.0, 1))
    other = asyncio.run(engine.generate(207, 20, 500.0, 1))
    image = Image.open(io.BytesIO(first))
    assert image.size == (256, 256) and image.format == "PNG"
    assert first != other
    # bf16 on the GPU is not bit-exact between runs, so compare the pictures loosely
    a, b = (list(Image.open(io.BytesIO(x)).convert("L").resize((16, 16)).getdata()) for x in (first, again))
    assert sum(abs(p - q) for p, q in zip(a, b)) / len(a) < 8
