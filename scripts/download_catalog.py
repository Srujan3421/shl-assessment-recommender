import argparse
import json
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


CATALOG_URL = "https://tcp-us-prod-rnd.shl.com/voiceRater/shl-ai-hiring/shl_product_catalog.json"
OUTPUT_PATH = Path(__file__).resolve().parents[1] / "app" / "data" / "catalog.json"
KEEP_FIELDS = {
    "name",
    "link",
    "description",
    "job_levels",
    "languages",
    "duration",
    "keys",
    "remote",
    "adaptive",
}


def download(url: str, timeout: int = 30) -> list[dict[str, Any]]:
    request = Request(url, headers={"User-Agent": "SHL-Assessment-Recommender/1.0"})
    with urlopen(request, timeout=timeout) as response:
        text = response.read().decode("utf-8")
        payload = json.loads(text, strict=False)
    if not isinstance(payload, list):
        raise ValueError("Catalog payload must be a JSON list.")
    return payload


def normalize(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cleaned: list[dict[str, Any]] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        name = clean(record.get("name"))
        link = clean(record.get("link"))
        if not name or not link:
            continue
        item = {field: record.get(field, [] if field in {"job_levels", "languages", "keys"} else "") for field in KEEP_FIELDS}
        item["name"] = name
        item["link"] = link
        item["description"] = clean(item.get("description"))
        item["duration"] = clean(item.get("duration"))
        item["job_levels"] = clean_list(item.get("job_levels"))
        item["languages"] = clean_list(item.get("languages"))
        item["keys"] = clean_list(item.get("keys"))
        item["remote"] = clean(item.get("remote"))
        item["adaptive"] = clean(item.get("adaptive"))
        cleaned.append(item)
    return cleaned


def clean(value: Any) -> str:
    return " ".join(str(value or "").split())


def clean_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [clean(item) for item in value if clean(item)]


def main() -> int:
    parser = argparse.ArgumentParser(description="Download the official SHL assignment catalog JSON.")
    parser.add_argument("--url", default=CATALOG_URL)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    args = parser.parse_args()

    try:
        records = normalize(download(args.url))
    except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
        print(f"Failed to download SHL catalog: {exc}", file=sys.stderr)
        return 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Downloaded {len(records)} valid SHL catalog records to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
