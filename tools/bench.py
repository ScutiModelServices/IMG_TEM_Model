"""Times the TEM service: py tools/bench.py http://127.0.0.1:9190 [--token T] [--runs 3] [--steps 60] [--save DIR]

Asks /v1/generate for a few classes and prints, per picture, the wait and the server's own time. Each run uses a new
seed, so the answer cache never serves it. With --save the PNGs are written to DIR.
Uses only the standard library."""
import argparse
import json
import pathlib
import random
import time
import urllib.request

LABELS = ["golden retriever", "volcano", "bald eagle", "balloon"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("--token", default="")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--steps", type=int, default=60)
    parser.add_argument("--save", default="")
    args = parser.parse_args()
    for label in LABELS:
        for run in range(1, args.runs + 1):
            body = {"label": label, "steps": args.steps, "seed": random.randrange(2**32)}
            request = urllib.request.Request(args.url.rstrip("/") + "/v1/generate", json.dumps(body).encode(),
                                             {"Content-Type": "application/json", "X-Internal-Token": args.token})
            started = time.perf_counter()
            with urllib.request.urlopen(request, timeout=600) as reply:
                png, headers = reply.read(), reply.headers
            wait = time.perf_counter() - started
            print(f"{label:18} run {run}: {wait:5.2f}s wait, server {int(headers['X-Duration-Ms']) / 1000:5.2f}s, "
                  f"{len(png) // 1024} KB, seed {headers['X-Seed']}")
            if args.save:
                folder = pathlib.Path(args.save)
                folder.mkdir(parents=True, exist_ok=True)
                (folder / f"{label.replace(' ', '_')}_{run}.png").write_bytes(png)


if __name__ == "__main__":
    main()
