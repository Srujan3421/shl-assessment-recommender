import argparse
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen


BASE_URL = "https://www.shl.com"
CATALOG_URL = BASE_URL + "/solutions/products/product-catalog?start={start}&type=1"
OUTPUT_PATH = Path(__file__).resolve().parents[1] / "app" / "data" / "catalog.json"
USER_AGENT = "Mozilla/5.0 SHL-Assessment-Recommender/1.0"


class CatalogListParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.section = ""
        self.in_heading = False
        self.current_heading: list[str] = []
        self.in_row = False
        self.current_row: dict[str, Any] | None = None
        self.current_cell = -1
        self.in_cell = False
        self.cell_text: list[str] = []
        self.in_key = False
        self.records: list[dict[str, Any]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        classes = attrs_dict.get("class", "")
        if tag == "th" and "custom__table-heading__title" in classes:
            self.in_heading = True
            self.current_heading = []
        if tag == "tr" and ("data-course-id" in attrs_dict or "data-entity-id" in attrs_dict):
            self.in_row = True
            self.current_row = {
                "section": self.section,
                "name": "",
                "url": "",
                "remote_testing": False,
                "adaptive_irt": False,
                "test_types": [],
            }
            self.current_cell = -1
        if self.in_row and tag == "td":
            self.current_cell += 1
            self.in_cell = True
            self.cell_text = []
        if self.in_row and tag == "a" and self.current_cell == 0 and self.current_row is not None:
            href = attrs_dict.get("href") or ""
            self.current_row["url"] = urljoin(BASE_URL, href)
        if self.in_row and tag == "span" and "catalogue__circle" in classes and self.current_row is not None:
            if self.current_cell == 1:
                self.current_row["remote_testing"] = True
            if self.current_cell == 2:
                self.current_row["adaptive_irt"] = True
        if self.in_row and tag == "span" and "product-catalogue__key" in classes:
            self.in_key = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "th" and self.in_heading:
            heading = " ".join("".join(self.current_heading).split())
            if heading:
                self.section = heading
            self.in_heading = False
        if self.in_row and tag == "td":
            text = " ".join("".join(self.cell_text).split())
            if self.current_cell == 0 and self.current_row is not None:
                self.current_row["name"] = text
            self.in_cell = False
        if self.in_row and tag == "span" and self.in_key:
            self.in_key = False
        if tag == "tr" and self.in_row:
            if (
                self.current_row
                and self.current_row["section"] == "Individual Test Solutions"
                and self.current_row["name"]
                and self.current_row["url"]
            ):
                self.records.append(self.current_row)
            self.in_row = False
            self.current_row = None

    def handle_data(self, data: str) -> None:
        if self.in_heading:
            self.current_heading.append(data)
        if self.in_cell:
            self.cell_text.append(data)
        if self.in_key and self.current_row is not None:
            value = data.strip().upper()
            if value and value not in self.current_row["test_types"]:
                self.current_row["test_types"].append(value)


class DescriptionParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.description = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "meta":
            return
        attrs_dict = {key.lower(): value for key, value in attrs if value}
        name = attrs_dict.get("name", "").lower()
        prop = attrs_dict.get("property", "").lower()
        if name == "description" or prop == "og:description":
            content = attrs_dict.get("content", "").strip()
            if content and not self.description:
                self.description = " ".join(content.split())


def fetch(url: str, retries: int = 3, timeout: int = 20) -> str:
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            request = Request(url, headers={"User-Agent": USER_AGENT})
            with urlopen(request, timeout=timeout) as response:
                return response.read().decode("utf-8", errors="ignore")
        except Exception as exc:
            last_error = exc
            time.sleep(0.75 * (attempt + 1))
    raise RuntimeError(f"Failed to fetch {url}: {last_error}")


def parse_catalog_page(html: str) -> list[dict[str, Any]]:
    parser = CatalogListParser()
    parser.feed(html)
    return parser.records


def parse_max_start(html: str) -> int:
    starts = [int(value) for value in re.findall(r"start=(\d+)", html)]
    return max(starts) if starts else 0


def parse_description(html: str) -> str:
    parser = DescriptionParser()
    parser.feed(html)
    return parser.description


def keywords_for(record: dict[str, Any]) -> list[str]:
    text = f"{record['name']} {record.get('description', '')}".lower()
    tokens = sorted(set(re.findall(r"[a-z0-9+#.]{2,}", text)))
    stopwords = {
        "and",
        "the",
        "for",
        "with",
        "new",
        "test",
        "that",
        "measures",
        "knowledge",
        "candidate",
        "assessment",
        "shl",
    }
    return [token for token in tokens if token not in stopwords][:40]


def scrape_catalog(include_details: bool = False, workers: int = 8) -> dict[str, Any]:
    first_html = fetch(CATALOG_URL.format(start=0))
    max_start = parse_max_start(first_html)
    starts = list(range(0, max_start + 1, 12))

    records_by_url: dict[str, dict[str, Any]] = {}
    for start in starts:
        html = first_html if start == 0 else fetch(CATALOG_URL.format(start=start))
        for record in parse_catalog_page(html):
            records_by_url[record["url"]] = record

    records = list(records_by_url.values())
    records.sort(key=lambda item: item["name"].lower())

    if include_details:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            future_to_record = {executor.submit(fetch, record["url"], 1, 8): record for record in records}
            for future in as_completed(future_to_record):
                record = future_to_record[future]
                try:
                    record["description"] = parse_description(future.result())
                except Exception:
                    record["description"] = ""

    for record in records:
        record["keywords"] = keywords_for(record)

    return {
        "source": "https://www.shl.com/solutions/products/product-catalog/",
        "scope": "Individual Test Solutions",
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "count": len(records),
        "records": records,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape SHL Individual Test Solutions catalog.")
    parser.add_argument("--with-details", action="store_true", help="Also fetch product detail page descriptions.")
    parser.add_argument("--workers", type=int, default=8, help="Concurrent detail page fetches.")
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    args = parser.parse_args()

    payload = scrape_catalog(include_details=args.with_details, workers=args.workers)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
    print(f"Wrote {payload['count']} records to {args.output}")


if __name__ == "__main__":
    main()
