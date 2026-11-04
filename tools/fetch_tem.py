"""Downloads tem.py, the model code of github.com/int-lee/TEM, at the pinned commit into tem_code/ (git-ignored).

The code has no license file, so it is fetched here and never copied into this repository.
    python tools/fetch_tem.py [target_dir]
Fails when the file does not match the pinned SHA-256."""
import hashlib
import sys
import urllib.request
from pathlib import Path

COMMIT = "7e28035f522882e7acf0aed6d04f65604945e41f"
SHA256 = "6de9611ef395fd8e8995a41477215271934d61938835dacd0966132417b6124f"
URL = f"https://raw.githubusercontent.com/int-lee/TEM/{COMMIT}/tem.py"


def main() -> int:
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "tem_code"
    with urllib.request.urlopen(URL, timeout=60) as reply:
        data = reply.read()
    if hashlib.sha256(data).hexdigest() != SHA256:
        print("tem.py does not match the pinned SHA-256; not saved", file=sys.stderr)
        return 1
    target.mkdir(parents=True, exist_ok=True)
    (target / "tem.py").write_bytes(data)
    print(f"Saved {target / 'tem.py'} (commit {COMMIT[:8]})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
