from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup

DEFAULT_PAGE_URL = (
    "https://en.wikipedia.org/wiki/"
    "Opinion_polling_for_the_next_United_Kingdom_general_election"
)

USER_AGENT = (
    "UKPollingSiteBot/0.1 (educational project; contact via repo issues) "
    "requests-python"
)


@dataclass
class ScrapeResult:
    source_url: str
    fetched_at: str
    graph_remote_url: str | None
    graph_local_path: str | None
    graph_caption: str | None
    table_title: str | None
    table_columns: list[str]
    table_rows: list[dict[str, Any]]
    notes: list[str]


def get_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    return session


def fetch_html(session: requests.Session, url: str) -> str:
    resp = session.get(url, timeout=30)
    resp.raise_for_status()
    return resp.text


def normalize_img_url(src: str) -> str:
    if src.startswith("//"):
        return "https:" + src
    return src


def score_graph_candidate(text: str) -> int:
    t = text.lower()
    score = 0
    if "opinion" in t:
        score += 2
    if "poll" in t:
        score += 3
    if "graph" in t or "chart" in t:
        score += 1
    if "next united kingdom" in t or "general election" in t:
        score += 2
    return score


def extract_graph(soup: BeautifulSoup, page_url: str) -> tuple[str | None, str | None]:
    candidates: list[tuple[int, str, str | None]] = []

    for container in soup.select("figure, div.thumb, .thumbinner"):
        img = container.select_one("img")
        if not img or not img.get("src"):
            continue
        caption_el = container.select_one("figcaption, .thumbcaption")
        alt_text = img.get("alt", "")
        caption = caption_el.get_text(" ", strip=True) if caption_el else ""
        context = f"{alt_text} {caption}".strip()
        score = score_graph_candidate(context)
        if score <= 0:
            continue
        src = normalize_img_url(img["src"])
        candidates.append((score, urljoin(page_url, src), caption or None))

    if not candidates:
        # Fallback: choose the first image in article content that mentions polling in alt text.
        for img in soup.select("#mw-content-text img"):
            alt_text = (img.get("alt") or "").lower()
            if "poll" in alt_text and img.get("src"):
                src = normalize_img_url(img["src"])
                return urljoin(page_url, src), img.get("alt")
        return None, None

    candidates.sort(key=lambda item: item[0], reverse=True)
    _, img_url, caption = candidates[0]
    return img_url, caption


def flatten_columns(columns: Any) -> list[str]:
    if isinstance(columns, pd.MultiIndex):
        flat = []
        for tup in columns:
            parts = [str(x).strip() for x in tup if str(x).strip() and str(x) != "nan"]
            flat.append(" | ".join(parts) if parts else "column")
        return flat
    return [str(col).strip() for col in columns]


def score_table(df: pd.DataFrame) -> int:
    columns = " ".join(flatten_columns(df.columns)).lower()
    score = 0
    for token in ["poll", "pollster", "date", "fieldwork"]:
        if token in columns:
            score += 2
    for token in ["con", "conservative", "lab", "labour", "ld", "lib dem", "reform"]:
        if token in columns:
            score += 1
    if len(df) >= 5:
        score += 1
    return score


def extract_table(html: str) -> tuple[str | None, pd.DataFrame]:
    tables = pd.read_html(html)
    if not tables:
        raise ValueError("No tables found on page")

    best_df = max(tables, key=score_table)
    best_score = score_table(best_df)
    if best_score < 4:
        raise ValueError("Could not confidently identify polling table")

    return "Wikipedia polling table (auto-detected)", best_df


def sanitize_filename_from_url(url: str) -> str:
    parsed = urlparse(url)
    name = Path(parsed.path).name or "graph"
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name)
    if "." not in name:
        name += ".img"
    return name


def download_graph(session: requests.Session, graph_url: str, assets_dir: Path) -> str:
    assets_dir.mkdir(parents=True, exist_ok=True)
    filename = sanitize_filename_from_url(graph_url)
    local_path = assets_dir / filename

    resp = session.get(graph_url, timeout=30)
    resp.raise_for_status()
    local_path.write_bytes(resp.content)

    latest_ext = local_path.suffix or ".img"
    latest_path = assets_dir / f"graph-latest{latest_ext}"
    latest_path.write_bytes(resp.content)
    return f"assets/{latest_path.name}"


def dataframe_to_rows(df: pd.DataFrame) -> tuple[list[str], list[dict[str, Any]]]:
    df = df.copy()
    df.columns = flatten_columns(df.columns)
    df = df.fillna("")
    rows = [
        {str(k): ("" if pd.isna(v) else str(v)) for k, v in row.items()}
        for row in df.to_dict(orient="records")
    ]
    return list(df.columns), rows


def ensure_dirs(base: Path) -> dict[str, Path]:
    site_dir = base / "site"
    data_dir = site_dir / "data"
    history_dir = data_dir / "history"
    assets_dir = site_dir / "assets"
    for p in [site_dir, data_dir, history_dir, assets_dir]:
        p.mkdir(parents=True, exist_ok=True)
    return {"site": site_dir, "data": data_dir, "history": history_dir, "assets": assets_dir}


def save_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> None:
    base = Path(__file__).resolve().parent
    paths = ensure_dirs(base)

    page_url = os.getenv("WIKI_PAGE_URL", DEFAULT_PAGE_URL)
    fetched_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    notes: list[str] = []

    session = get_session()
    html = fetch_html(session, page_url)
    soup = BeautifulSoup(html, "lxml")

    graph_remote_url, graph_caption = extract_graph(soup, page_url)
    graph_local_path = None
    if graph_remote_url:
        try:
            graph_local_path = download_graph(session, graph_remote_url, paths["assets"])
        except Exception as exc:  # noqa: BLE001
            notes.append(f"Graph download failed: {exc}")
    else:
        notes.append("Graph image not found on page")

    table_title, df = extract_table(html)
    columns, rows = dataframe_to_rows(df)

    result = ScrapeResult(
        source_url=page_url,
        fetched_at=fetched_at,
        graph_remote_url=graph_remote_url,
        graph_local_path=graph_local_path,
        graph_caption=graph_caption,
        table_title=table_title,
        table_columns=columns,
        table_rows=rows,
        notes=notes,
    )

    payload = {
        "source_url": result.source_url,
        "fetched_at": result.fetched_at,
        "graph": {
            "remote_url": result.graph_remote_url,
            "local_path": result.graph_local_path,
            "caption": result.graph_caption,
        },
        "table": {
            "title": result.table_title,
            "columns": result.table_columns,
            "rows": result.table_rows,
            "row_count": len(result.table_rows),
        },
        "notes": result.notes,
    }

    latest_path = paths["data"] / "latest.json"
    date_key = fetched_at.split("T")[0]
    history_path = paths["history"] / f"{date_key}.json"
    save_json(latest_path, payload)
    save_json(history_path, payload)

    print(f"Saved {latest_path}")
    print(f"Saved {history_path}")
    print(f"Rows: {len(rows)}")
    if graph_local_path:
        print(f"Graph: {graph_local_path}")


if __name__ == "__main__":
    main()
