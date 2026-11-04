import threading

import pytest
from fastapi.testclient import TestClient

from app import create_app
from conftest import make_engine, tiny_png
from engine import EngineError
from tokens import TokenStore


def client(**options):
    engine = options.pop("engine", None) or make_engine()
    return TestClient(create_app(engine, **options)), engine


def test_generate_returns_a_png_with_headers():
    api, _ = client()
    reply = api.post("/v1/generate", json={"class_id": 207, "seed": 5})
    assert reply.status_code == 200 and reply.headers["content-type"] == "image/png"
    assert reply.content == tiny_png(207)
    assert reply.headers["x-class-id"] == "207" and reply.headers["x-seed"] == "5" and reply.headers["x-steps"] == "60"
    assert "golden retriever" in reply.headers["x-class-label"]


def test_label_resolves_to_a_class_and_a_missing_seed_is_made_up():
    api, engine = client()
    reply = api.post("/v1/generate", json={"label": "volcano"})
    assert reply.headers["x-class-id"] == "980"
    assert 0 <= int(reply.headers["x-seed"]) < 2**32
    assert engine.made[0].calls[0]["seed"] == int(reply.headers["x-seed"])


@pytest.mark.parametrize("body", [{}, {"class_id": 1, "label": "volcano"}, {"class_id": 1000}, {"class_id": 1, "steps": 0},
                                  {"class_id": 1, "extra": 1}, {"label": "no such thing at all"}, {"label": "dog"}])
def test_bad_requests_are_refused(body):
    api, engine = client()
    assert api.post("/v1/generate", json=body).status_code in (404, 422)
    assert not engine.made


def test_steps_above_the_limit_are_refused():
    api, engine = client(max_steps=50)
    assert api.post("/v1/generate", json={"class_id": 1, "steps": 51}).status_code == 422
    assert api.post("/v1/generate", json={"class_id": 1, "steps": 50}).status_code == 200
    assert len(engine.made[0].calls) == 1


def test_seeded_answers_are_cached_and_unseeded_are_not():
    api, engine = client(cache_size=4)
    first = api.post("/v1/generate", json={"class_id": 3, "seed": 1})
    second = api.post("/v1/generate", json={"class_id": 3, "seed": 1})
    assert (first.headers["x-cache"], second.headers["x-cache"]) == ("miss", "hit")
    assert len(engine.made[0].calls) == 1
    api.post("/v1/generate", json={"class_id": 3})
    api.post("/v1/generate", json={"class_id": 3})
    assert len(engine.made[0].calls) == 3


def test_cache_is_off_without_a_size():
    api, engine = client()
    api.post("/v1/generate", json={"class_id": 3, "seed": 1})
    api.post("/v1/generate", json={"class_id": 3, "seed": 1})
    assert len(engine.made[0].calls) == 2


def test_classes_can_be_filtered():
    api, _ = client()
    assert api.get("/v1/classes", params={"q": "volcano"}).json()["classes"] == [{"id": 980, "name": "volcano"}]
    assert len(api.get("/v1/classes").json()["classes"]) == 1000


def test_health_needs_no_token_and_reports_the_device():
    api, _ = client(admin_password="pw")
    body = api.get("/health").json()
    assert body["status"] == "ok" and body["device"] == "cuda" and body["ready"] is False


def test_tokens_gate_the_api_and_limit_the_model(tmp_path):
    api, _ = client(admin_password="pw", tokens=TokenStore(tmp_path / "tokens.json"))
    admin = {"X-Internal-Token": "pw"}
    assert api.post("/v1/generate", json={"class_id": 1}).status_code == 401
    other = api.post("/admin/tokens", json={"name": "a", "projects": ["something-else"]}, headers=admin).json()
    allowed = api.post("/admin/tokens", json={"name": "b", "projects": ["tem-xl-256"]}, headers=admin).json()
    assert other["token"].startswith("tem_")
    assert api.post("/v1/generate", json={"class_id": 1}, headers={"X-Internal-Token": other["token"]}).status_code == 403
    assert api.post("/v1/generate", json={"class_id": 1}, headers={"X-Internal-Token": allowed["token"]}).status_code == 200


def test_in_flight_cap_gives_429_with_retry_after():
    engine = make_engine()
    entered, release = threading.Event(), threading.Event()
    original = engine._generate

    def blocked(*args):
        entered.set()
        release.wait(10)
        return original(*args)

    engine._generate = blocked
    api = TestClient(create_app(engine, max_inflight=1))
    results = []
    worker = threading.Thread(target=lambda: results.append(api.post("/v1/generate", json={"class_id": 1})))
    worker.start()
    assert entered.wait(10)  # the first call now holds the only slot
    second = api.post("/v1/generate", json={"class_id": 2})
    release.set()
    worker.join(10)
    assert second.status_code == 429 and second.headers["retry-after"] == "5"
    assert results[0].status_code == 200


def test_engine_errors_keep_their_status_and_other_errors_are_500():
    def refuse(path, device):
        raise EngineError("no GPU", 503)

    def explode(path, device):
        raise RuntimeError("boom")

    api, _ = client(engine=make_engine(loader=refuse))
    reply = api.post("/v1/generate", json={"class_id": 1})
    assert reply.status_code == 503 and "no GPU" in reply.json()["detail"]
    api, _ = client(engine=make_engine(loader=explode))
    assert api.post("/v1/generate", json={"class_id": 1}).status_code == 500


def test_admin_threads_and_workers():
    api, engine = client(admin_password="pw")
    headers = {"X-Internal-Token": "pw"}
    assert api.put("/admin/threads", json={"num_thread": 4}, headers=headers).json() == {"num_thread": 4}
    assert engine.num_thread == 4
    assert api.get("/admin/workers", headers=headers).json()["parallel"] == 1
    assert api.get("/admin/workers").status_code == 401


def test_metrics_use_the_tem_prefix():
    api, _ = client(admin_password="pw")
    api.post("/v1/generate", json={"class_id": 1}, headers={"X-Internal-Token": "pw"})
    assert "tem_request_seconds" in api.get("/metrics", headers={"X-Internal-Token": "pw"}).text
