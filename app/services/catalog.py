import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.schemas import Recommendation


CATALOG_PATH = Path(__file__).resolve().parents[1] / "data" / "catalog.json"
SHL_PREFIX = "https://www.shl.com/"

KEY_TO_CODE = {
    "ability & aptitude": "A",
    "biodata & situational judgment": "B",
    "biodata & situational judgement": "B",
    "competencies": "C",
    "development & 360": "D",
    "assessment exercises": "E",
    "knowledge & skills": "K",
    "personality & behavior": "P",
    "personality & behaviour": "P",
    "simulations": "S",
}


class CatalogError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def load_catalog() -> list[dict[str, Any]]:
    if not CATALOG_PATH.exists():
        raise CatalogError(
            f"Catalog data not found at {CATALOG_PATH}. Run scripts/download_catalog.py first."
        )

    payload = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    records = payload.get("records", []) if isinstance(payload, dict) else payload
    if not records:
        raise CatalogError("Catalog has no records.")

    seen_urls: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        item = normalize_record(record)
        if not item:
            continue
        url = item["url"]
        if url in seen_urls:
            continue
        seen_urls.add(url)
        normalized.append(item)

    if not normalized:
        raise CatalogError("Catalog validation removed all records.")
    return normalized


def normalize_record(record: dict[str, Any]) -> dict[str, Any] | None:
    name = clean(record.get("name"))
    url = clean(record.get("link") or record.get("url"))
    if not name or not url.startswith(SHL_PREFIX):
        return None

    keys = clean_list(record.get("keys"))
    old_types = [clean(value).upper() for value in record.get("test_types", []) if clean(value)]
    test_types = sorted({KEY_TO_CODE.get(key.lower(), key.upper()) for key in keys})
    test_types = [code for code in test_types if code in KEY_TO_CODE.values()]
    if not test_types:
        test_types = [code for code in old_types if code in KEY_TO_CODE.values()]
    if not test_types:
        return None

    description = clean(record.get("description"))
    job_levels = clean_list(record.get("job_levels"))
    languages = clean_list(record.get("languages"))
    duration = clean(record.get("duration"))
    keywords = sorted(
        {
            token
            for value in [name, description, duration, *keys, *job_levels, *languages]
            for token in token_candidates(value)
        }
    )

    return {
        "name": name,
        "url": url,
        "test_types": test_types,
        "test_type": " ".join(test_types),
        "description": description,
        "job_levels": job_levels,
        "languages": languages,
        "duration": duration,
        "keys": keys,
        "remote": yes_no(record.get("remote") if "remote" in record else record.get("remote_testing")),
        "adaptive": yes_no(record.get("adaptive") if "adaptive" in record else record.get("adaptive_irt")),
        "keywords": keywords,
    }


def clean(value: Any) -> str:
    return " ".join(str(value or "").split())


def clean_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [clean(item) for item in value if clean(item)]


def yes_no(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"yes", "true", "1"}


def token_candidates(value: str) -> set[str]:
    import re

    stopwords = {
        "and",
        "the",
        "for",
        "with",
        "new",
        "test",
        "that",
        "this",
        "candidate",
        "assessment",
        "shl",
    }
    return {
        token
        for token in re.findall(r"[a-z0-9+#.]+", value.lower())
        if len(token) > 1 and token not in stopwords
    }


def to_recommendation(record: dict[str, Any]) -> Recommendation:
    return Recommendation(
        name=record["name"],
        url=record["url"],
        test_type=record["test_type"],
    )
