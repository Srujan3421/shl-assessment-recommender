from pathlib import Path
import sys

import uvicorn


ROOT = Path(__file__).resolve().parents[1]
LOG = ROOT / "run_api.log"
sys.path.insert(0, str(ROOT))


def main() -> None:
    with LOG.open("a", encoding="utf-8", buffering=1) as log:
        sys.stdout = log
        sys.stderr = log
        print("Starting SHL API on http://0.0.0.0:8000", flush=True)
        uvicorn.run("app.main:app", host="0.0.0.0", port=8000, log_level="info")


if __name__ == "__main__":
    main()
