from __future__ import annotations

import argparse
import csv
import datetime as dt
import html
import json
import math
import re
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup
from yt_dlp import YoutubeDL


EXPORT_HEADER = [
    "video_id",
    "platform",
    "url",
    "title",
    "creator_name",
    "publish_date",
    "latest_test_relevance",
    "has_actual_judgment",
    "has_concrete_footage",
    "is_guide_like",
    "selection_status",
    "notes",
    "duration_seconds",
    "view_count",
    "latest_test_confidence",
    "inclusion_reason",
    "ranking_score",
    "search_query",
]

LATEST_TEST_KEYWORDS = [
    "test",
    "beta",
    "cbt",
    "playtest",
    "preview",
    "first look",
    "hands on",
    "impressions",
    "trial",
    "demo",
]

REVIEW_KEYWORDS = ["review", "impressions", "analysis", "thoughts", "verdict", "vs"]
GUIDE_KEYWORDS = ["guide", "tips", "walkthrough", "build", "beginner"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Search and rank Section 4 creator-video candidates.")
    parser.add_argument("--game-name", required=True, help="Game name used as the only required input")
    parser.add_argument("--output-file", help="CSV output path for shortlist export")
    parser.add_argument("--limit", type=int, default=10, help="Number of shortlist rows to export (default: 10)")
    parser.add_argument("--youtube-max", type=int, default=12, help="Raw YouTube results to fetch")
    parser.add_argument("--bilibili-max", type=int, default=12, help="Raw Bilibili results to fetch")
    return parser.parse_args()


def slugify(text: str) -> str:
    lowered = text.casefold().strip()
    return re.sub(r"[^a-z0-9]+", "-", lowered).strip("-") or "section-4"


def normalize_spaces(text: str) -> str:
    return " ".join(text.split()).strip()


def parse_upload_date(text: str) -> str:
    raw = text.strip()
    if not raw:
        return ""
    if re.fullmatch(r"\d{8}", raw):
        return f"{raw[0:4]}-{raw[4:6]}-{raw[6:8]}"
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        return raw
    return ""


def timestamp_to_date(value: Any) -> str:
    if value in {None, ""}:
        return ""
    try:
        stamp = int(float(str(value)))
    except ValueError:
        return ""
    return dt.datetime.utcfromtimestamp(stamp).strftime("%Y-%m-%d")


def parse_duration_to_seconds(value: Any) -> int:
    if value in {None, ""}:
        return 0
    if isinstance(value, (int, float)):
        return max(int(value), 0)
    text = str(value).strip()
    if text.isdigit():
        return int(text)
    parts = text.split(":")
    if not all(part.isdigit() for part in parts):
        return 0
    if len(parts) == 2:
        return int(parts[0]) * 60 + int(parts[1])
    if len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    return 0


def parse_bilibili_view_count(value: Any) -> int:
    if value in {None, ""}:
        return 0
    text = str(value).strip().replace(",", "")
    match = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)([A-Za-z]+)?", text)
    if match:
        base = float(match.group(1))
        suffix = (match.group(2) or "").casefold()
        if suffix in {"k"}:
            return int(base * 1_000)
        if suffix in {"m"}:
            return int(base * 1_000_000)
        return int(base)
    match_cn = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)(.)", text)
    if match_cn:
        base = float(match_cn.group(1))
        unit = match_cn.group(2)
        if unit == "w":
            return int(base * 10_000)
        if unit == "y":
            return int(base * 100_000_000)
    digits = re.sub(r"[^0-9]", "", text)
    return int(digits) if digits else 0


def recent_days_score(publish_date: str) -> tuple[float, bool]:
    if not publish_date:
        return 0.0, False
    try:
        date_value = dt.datetime.strptime(publish_date, "%Y-%m-%d").date()
    except ValueError:
        return 0.0, False
    days = (dt.date.today() - date_value).days
    if days <= 0:
        return 2.0, True
    if days <= 120:
        return 1.5, True
    if days <= 240:
        return 0.8, True
    if days <= 400:
        return 0.3, False
    return 0.0, False


def contains_any(text: str, keywords: list[str]) -> bool:
    lowered = text.casefold()
    return any(keyword in lowered for keyword in keywords)


def keyword_hit_count(text: str, keywords: list[str]) -> int:
    lowered = text.casefold()
    return sum(1 for keyword in keywords if keyword in lowered)


def score_candidate(row: dict[str, str], game_name: str) -> tuple[float, str, float]:
    title = row.get("title", "")
    creator = row.get("creator_name", "")
    combined = f"{title} {creator}".casefold()
    game_hit = game_name.casefold() in combined if game_name else False
    latest_hits = keyword_hit_count(combined, LATEST_TEST_KEYWORDS)
    review_hits = keyword_hit_count(combined, REVIEW_KEYWORDS)
    guide_hits = keyword_hit_count(combined, GUIDE_KEYWORDS)
    duration = int(row.get("duration_seconds", "0") or "0")
    views = int(row.get("view_count", "0") or "0")

    score = 0.0
    reasons: list[str] = []
    if game_hit:
        score += 3.0
        reasons.append("title matches game")
    if latest_hits:
        score += min(2.0, 0.7 * latest_hits)
        reasons.append("latest-test style wording")
    if review_hits:
        score += min(1.5, 0.5 * review_hits)
        reasons.append("review/impression wording")
    if 180 <= duration <= 2400:
        score += 1.0
        reasons.append("usable video length")
    if views > 0:
        score += min(2.0, math.log10(views + 10) / 2.0)
        reasons.append("has audience signal")

    recency_points, likely_latest = recent_days_score(row.get("publish_date", ""))
    score += recency_points
    if likely_latest:
        reasons.append("recent publish date")

    if guide_hits:
        score -= min(1.2, 0.6 * guide_hits)

    confidence = 0.3
    confidence += 0.15 if game_hit else 0.0
    confidence += min(0.35, latest_hits * 0.15)
    confidence += 0.1 if likely_latest else 0.0
    confidence -= 0.1 if guide_hits else 0.0
    confidence = max(0.05, min(confidence, 0.95))

    if not reasons:
        reasons.append("broad search relevance")
    reason_text = "; ".join(reasons[:3])
    return score, reason_text, confidence


def unique_by_key(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    deduped: dict[str, dict[str, str]] = {}
    order: list[str] = []
    for row in rows:
        platform = row.get("platform", "")
        video_id = row.get("video_id", "")
        url = row.get("url", "")
        key = f"{platform}:{video_id or url}"
        if key not in deduped:
            order.append(key)
        deduped[key] = row
    return [deduped[key] for key in order]


def search_youtube(game_name: str, max_results: int) -> list[dict[str, str]]:
    queries = [
        f"{game_name} gameplay review",
        f"{game_name} latest test",
        f"{game_name} cbt gameplay",
    ]
    all_rows: list[dict[str, str]] = []
    # Fetch enough to allow for filtering
    fetch_per_query = max(10, max_results)

    with YoutubeDL({"quiet": True, "no_warnings": True, "extract_flat": True}) as ydl:
        for query in queries:
            try:
                result = ydl.extract_info(f"ytsearch{fetch_per_query}:{query}", download=False)
                for entry in (result.get("entries") or []):
                    if not isinstance(entry, dict):
                        continue
                    video_id = str(entry.get("id") or "").strip()
                    if not video_id:
                        continue

                    title = normalize_spaces(str(entry.get("title") or ""))
                    description = normalize_spaces(str(entry.get("description") or ""))
                    
                    # Tighten filtering: game name must be in title or description
                    game_name_lower = game_name.casefold()
                    if game_name_lower not in title.casefold() and game_name_lower not in description.casefold():
                        continue

                    creator_name = normalize_spaces(str(entry.get("uploader") or entry.get("channel") or ""))
                    publish_date = parse_upload_date(str(entry.get("upload_date") or ""))
                    duration_seconds = parse_duration_to_seconds(entry.get("duration"))
                    view_count = int(entry.get("view_count") or 0)
                    all_rows.append(
                        {
                            "video_id": video_id,
                            "platform": "youtube",
                            "url": f"https://www.youtube.com/watch?v={video_id}",
                            "title": title,
                            "creator_name": creator_name,
                            "publish_date": publish_date,
                            "duration_seconds": str(duration_seconds),
                            "view_count": str(view_count),
                            "search_query": query,
                        }
                    )
            except Exception as e:
                print(f"YouTube search error for query '{query}': {e}")

    return unique_by_key(all_rows)[:max_results]


def parse_initial_state(html_text: str) -> dict[str, Any]:
    match = re.search(r"window\.__INITIAL_STATE__\s*=\s*(\{.*?\})\s*;\s*\(function", html_text, flags=re.DOTALL)
    if not match:
        return {}
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return {}


def iterate_dict_nodes(value: Any):
    if isinstance(value, dict):
        yield value
        for inner in value.values():
            yield from iterate_dict_nodes(inner)
    elif isinstance(value, list):
        for item in value:
            yield from iterate_dict_nodes(item)


def strip_html_tags(text: str) -> str:
    without_tags = re.sub(r"<[^>]+>", "", text)
    return normalize_spaces(html.unescape(without_tags))


def search_bilibili(game_name: str, max_results: int) -> list[dict[str, str]]:
    query = f"{game_name} review gameplay test"
    url = f"https://search.bilibili.com/all?keyword={quote_plus(query)}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "+
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }
    response = requests.get(url, headers=headers, timeout=20)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    rows: list[dict[str, str]] = []

    payload = parse_initial_state(response.text)
    if payload:
        for node in iterate_dict_nodes(payload):
            bvid = str(node.get("bvid") or "").strip()
            arcurl = str(node.get("arcurl") or "").strip()
            title = strip_html_tags(str(node.get("title") or ""))
            author = normalize_spaces(str(node.get("author") or node.get("up_name") or ""))
            if not (bvid or arcurl) or not title:
                continue
            video_id = bvid or arcurl.rstrip("/").split("/")[-1]
            duration_seconds = parse_duration_to_seconds(node.get("duration"))
            view_count = parse_bilibili_view_count(node.get("play") or node.get("view") or "0")
            publish_date = timestamp_to_date(node.get("pubdate"))
            rows.append(
                {
                    "video_id": video_id,
                    "platform": "bilibili",
                    "url": arcurl or f"https://www.bilibili.com/video/{video_id}",
                    "title": title,
                    "creator_name": author,
                    "publish_date": publish_date,
                    "duration_seconds": str(duration_seconds),
                    "view_count": str(view_count),
                    "search_query": query,
                }
            )

    if True:  # Always run DOM parsing to override sparse payload rows
        for card in soup.select(".bili-video-card"):
            anchor = card.select_one("a[href*='/video/BV']")
            if not anchor:
                continue
            href = str(anchor.get("href") or "").strip()
            full_url = href if href.startswith("http") else f"https:{href}"
            match = re.search(r"/video/(BV[0-9A-Za-z]+)", full_url)
            if not match:
                continue
            video_id = match.group(1)

            title_el = card.select_one(".bili-video-card__info--tit")
            title = normalize_spaces(title_el.get_text(strip=True)) if title_el else ""
            
            author_el = card.select_one(".bili-video-card__info--author")
            author = normalize_spaces(author_el.get_text(strip=True)) if author_el else ""
            
            date_el = card.select_one(".bili-video-card__info--date")
            date_text = normalize_spaces(date_el.get_text(strip=True)) if date_el else ""
            # Date often looks like "· 2023-10-23" or "10-23"
            publish_date = ""
            date_match = re.search(r"(\d{4}-\d{2}-\d{2})", date_text)
            if date_match:
                publish_date = date_match.group(1)
            else:
                # Handle "MM-DD" format by prepending current year if it looks like a date
                short_date_match = re.search(r"(\d{2}-\d{2})", date_text)
                if short_date_match:
                    publish_date = f"{dt.date.today().year}-{short_date_match.group(1)}"

            duration_el = card.select_one(".bili-video-card__stats__duration")
            duration_text = normalize_spaces(duration_el.get_text(strip=True)) if duration_el else "0"
            duration_seconds = parse_duration_to_seconds(duration_text)

            view_el = card.select_one(".bili-video-card__stats--left .bili-video-card__stats--item span")
            view_text = normalize_spaces(view_el.get_text(strip=True)) if view_el else "0"
            view_count = parse_bilibili_view_count(view_text)

            if not title:
                continue

            rows.append(
                {
                    "video_id": video_id,
                    "platform": "bilibili",
                    "url": full_url,
                    "title": title,
                    "creator_name": author,
                    "publish_date": publish_date,
                    "duration_seconds": str(duration_seconds),
                    "view_count": str(view_count),
                    "search_query": query,
                }
            )

    if not rows:
        for anchor in soup.select("a[href*='/video/BV']"):
            href = str(anchor.get("href") or "").strip()
            title = normalize_spaces(anchor.get_text(" ", strip=True))
            if not href or not title:
                continue
            full_url = href if href.startswith("http") else f"https:{href}"
            match = re.search(r"/video/(BV[0-9A-Za-z]+)", full_url)
            if not match:
                continue
            rows.append(
                {
                    "video_id": match.group(1),
                    "platform": "bilibili",
                    "url": full_url,
                    "title": title,
                    "creator_name": "",
                    "publish_date": "",
                    "duration_seconds": "0",
                    "view_count": "0",
                    "search_query": query,
                }
            )

    return unique_by_key(rows)[:max_results]


def build_export_rows(candidates: list[dict[str, str]], game_name: str, limit: int) -> list[dict[str, str]]:
    scored: list[dict[str, str]] = []
    for row in candidates:
        score, inclusion_reason, confidence = score_candidate(row, game_name)
        title_lower = row.get("title", "").casefold()
        guide_like = contains_any(title_lower, GUIDE_KEYWORDS)
        latest_test = contains_any(title_lower, LATEST_TEST_KEYWORDS)
        review_like = contains_any(title_lower, REVIEW_KEYWORDS)
        has_footage = "trailer" not in title_lower and "teaser" not in title_lower
        notes = (
            f"shortlist_platform={row.get('platform', '')}; "
            f"search_query={row.get('search_query', '')}; "
            f"ranking_score={score:.3f}; "
            f"latest_test_confidence={confidence:.2f}; "
            f"duration_seconds={row.get('duration_seconds', '0')}; "
            f"view_count={row.get('view_count', '0')}; "
            f"inclusion_reason={inclusion_reason}"
        )
        scored.append(
            {
                "video_id": row.get("video_id", ""),
                "platform": row.get("platform", ""),
                "url": row.get("url", ""),
                "title": row.get("title", ""),
                "creator_name": row.get("creator_name", ""),
                "publish_date": row.get("publish_date", ""),
                "latest_test_relevance": "true" if latest_test else "false",
                "has_actual_judgment": "true" if review_like else "false",
                "has_concrete_footage": "true" if has_footage else "false",
                "is_guide_like": "true" if guide_like else "false",
                "selection_status": "candidate",
                "notes": notes,
                "duration_seconds": row.get("duration_seconds", "0"),
                "view_count": row.get("view_count", "0"),
                "latest_test_confidence": f"{confidence:.2f}",
                "inclusion_reason": inclusion_reason,
                "ranking_score": f"{score:.3f}",
                "search_query": row.get("search_query", ""),
            }
        )

    scored.sort(key=lambda item: float(item.get("ranking_score", "0")), reverse=True)
    return scored[:limit]


def write_shortlist(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=EXPORT_HEADER)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    args = parse_args()
    game_name = normalize_spaces(args.game_name)
    if not game_name:
        raise SystemExit("--game-name must not be empty")

    output_file = Path(args.output_file).resolve() if args.output_file else Path.cwd() / f"{slugify(game_name)}_section_4_shortlist.csv"
    youtube_rows = search_youtube(game_name, max_results=max(args.youtube_max, 1))
    bilibili_rows = search_bilibili(game_name, max_results=max(args.bilibili_max, 1))
    all_candidates = unique_by_key(youtube_rows + bilibili_rows)
    shortlist = build_export_rows(all_candidates, game_name=game_name, limit=max(args.limit, 1))

    if not shortlist:
        raise SystemExit("No shortlist candidates found from YouTube/Bilibili search")

    write_shortlist(output_file, shortlist)
    print(f"Created Section 4 shortlist: {output_file}")
    print(f"- rows: {len(shortlist)}")
    print("- next step: edit selection_status to selected for chosen rows, then run import_section_4_candidates.py")


if __name__ == "__main__":
    main()
