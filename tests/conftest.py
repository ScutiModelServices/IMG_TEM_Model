import io

import pytest
from PIL import Image

from engine import TEMEngine


@pytest.fixture(autouse=True)
def _tmp_tokens_file(tmp_path, monkeypatch):
    """Keeps tokens.json and settings.json out of the repo, and a saved setting from leaking into the next test."""
    monkeypatch.setenv("SERVICE_TOKENS_FILE", str(tmp_path / "tokens.json"))


def tiny_png(shade: int = 0) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (4, 4), (shade, shade, shade)).save(buf, "PNG")
    return buf.getvalue()


class FakeSampler:
    """Stands in for the loaded model: answers a 4x4 PNG whose shade is the class, and records every call."""

    def __init__(self, device):
        self.device, self.calls = device, []

    def generate(self, class_id, steps, step_size, seed, threads):
        self.calls.append({"class_id": class_id, "steps": steps, "step_size": step_size, "seed": seed, "threads": threads})
        return tiny_png(class_id % 256)


def make_engine(**options):
    """An engine whose loader builds a FakeSampler; `engine.loads` lists the paths it was asked for, `engine.made` the samplers.
    A test may pass `remote_sha` taking one argument (as the template tests do); the engine calls it with none."""
    loads, made = [], []

    def loader(path, device):
        loads.append(path)
        made.append(FakeSampler(device))
        return made[-1]

    if "remote_sha" in options:
        old_remote = options["remote_sha"]
        options["remote_sha"] = lambda: old_remote("m")
    options.setdefault("cached_sha", lambda path: "sha")
    options.setdefault("loader", loader)
    engine = TEMEngine("model.pth", "cuda", **options)
    engine.loads, engine.made = loads, made
    return engine
