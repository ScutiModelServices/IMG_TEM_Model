import asyncio
import time

import pytest

from conftest import make_engine, tiny_png
from engine import EngineError


def run(coro):
    return asyncio.run(coro)


def test_generate_loads_once_and_passes_the_arguments():
    engine = make_engine()
    assert not engine.ready
    assert run(engine.generate(207, 60, 500.0, 7)) == tiny_png(207)
    run(engine.generate(1, 10, 400.0, 8))
    assert len(engine.loads) == 1 and engine.ready
    assert engine.made[0].calls[0] == {"class_id": 207, "steps": 60, "step_size": 500.0, "seed": 7, "threads": None}


def test_threads_reach_the_sampler_without_reloading():
    engine = make_engine()
    run(engine.generate(0, 1, 1.0, 0))
    engine.num_thread = 3
    run(engine.generate(0, 1, 1.0, 0))
    assert [call["threads"] for call in engine.made[0].calls] == [None, 3]
    assert len(engine.loads) == 1


def test_resolve_class_by_id_and_by_name():
    engine = make_engine()
    assert engine.resolve_class(5, None) == 5
    assert engine.resolve_class(None, "golden retriever") == 207
    assert engine.resolve_class(None, "Volcano") == 980
    with pytest.raises(EngineError) as error:
        engine.resolve_class(None, "no such thing at all")
    assert error.value.status == 404
    with pytest.raises(EngineError) as error:
        engine.resolve_class(None, "dog")  # many classes contain it
    assert error.value.status == 422
    with pytest.raises(EngineError):
        engine.resolve_class(1000, None)


def test_a_missing_file_is_downloaded_before_loading():
    state = {"there": False}
    engine = make_engine(cached_sha=lambda path: "sha" if state["there"] else None,
                         download=lambda path: state.update(there=True))
    run(engine.generate(0, 1, 1.0, 0))
    assert state["there"] and len(engine.loads) == 1


def test_unload_drops_the_model_here_and_in_other_replicas(tmp_path):
    marker = tmp_path / "marker"
    first, second = make_engine(marker=marker), make_engine(marker=marker)
    for engine in (first, second):
        run(engine.generate(0, 1, 1.0, 0))
    generation = second.generation
    run(first.unload())
    assert not first.ready
    second.sync()
    assert not second.ready and second.generation == generation + 1
    run(second.generate(0, 1, 1.0, 0))
    assert len(second.loads) == 2


def test_one_generation_runs_at_a_time():
    engine = make_engine()
    running, peak = 0, 0

    def slow(class_id, steps, step_size, seed, threads):
        nonlocal running, peak
        running += 1
        peak = max(peak, running)
        time.sleep(0.05)
        running -= 1
        return tiny_png()

    async def both():
        await engine.warm()
        engine._loaded.generate = slow
        await asyncio.gather(engine.generate(0, 1, 1.0, 0), engine.generate(1, 1, 1.0, 0))

    run(both())
    assert peak == 1
