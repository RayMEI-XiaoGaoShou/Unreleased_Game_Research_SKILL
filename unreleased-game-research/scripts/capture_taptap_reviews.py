from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from urllib import parse
from pathlib import Path

from file_lock import exclusive_file_lock
from section_3_common import (
    REVIEW_REGISTRY_HEADER,
    REVIEW_SAMPLE_HEADER,
    SOURCE_REGISTRY_HEADER,
    SECTION_DIR_NAME,
    clean_html_text,
    derive_source_id,
    detect_language,
    ensure_csv,
    extract_meta_content,
    extract_title_text,
    fetch_url_text,
    merge_notes,
    normalize_text_value,
    parse_int,
    platform_from_url,
    read_csv_rows,
    review_length_bucket,
    write_csv_rows,
)


INPUT_ALIASES = {
    "review_id": ["review_id", "id", "comment_id"],
    "author_name": ["author_name", "author", "user_name", "nickname", "user"],
    "text_original": ["text_original", "text", "content", "review", "comment"],
    "likes": ["likes", "like_count", "thumbs_up"],
    "replies": ["replies", "reply_count", "comments_count"],
    "review_publish_time": ["review_publish_time", "publish_time", "comment_time", "time", "date"],
    "url": ["url", "review_url", "page_url"],
    "language": ["language", "lang"],
    "game_page_title": ["game_page_title", "page_title", "title"],
    "notes": ["notes", "note"],
    "platform": ["platform"],
}


def normalize_input_row(row: dict[str, object]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for key, value in row.items():
        normalized[str(key)] = "" if value is None else str(value)
    return normalized


def get_first_value(row: dict[str, str], field_name: str) -> str:
    for key in INPUT_ALIASES[field_name]:
        value = row.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def load_input_rows(path: Path) -> list[dict[str, str]]:
    suffix = path.suffix.casefold()
    if suffix == ".csv":
        return read_csv_rows(path)
    if suffix in {".jsonl", ".ndjson"}:
        rows: list[dict[str, str]] = []
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                stripped = line.strip()
                if not stripped:
                    continue
                payload = json.loads(stripped)
                if not isinstance(payload, dict):
                    raise SystemExit(f"Expected object rows in {path}")
                rows.append(normalize_input_row(payload))
        return rows
    if suffix == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, list) or any(not isinstance(item, dict) for item in payload):
            raise SystemExit(f"Expected a list of objects in {path}")
        return [normalize_input_row(item) for item in payload]
    raise SystemExit(f"Unsupported input format: {path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Capture TapTap homepage reviews either from direct page URLs or from exported files.")
    parser.add_argument("--project-dir", required=True, help="Path to an initialized project directory")
    parser.add_argument("--input-file", help="CSV, JSON, JSONL, or NDJSON review export")
    parser.add_argument("--page-url", default="", help="Source page URL for the imported review set")
    parser.add_argument("--game-page-title", default="", help="Source page title for the imported review set")
    parser.add_argument("--platform", default="taptap", help="Platform label stored in Section 3 outputs")
    parser.add_argument("--capture-method", default="manual_import", help="capture_method value written to review_registry.csv")
    parser.add_argument("--access-method", default="manual", choices=["api", "browser", "manual", "transcript", "scrape"], help="access_method written to source_registry.csv")
    parser.add_argument("--source-type", default="player review", help="source_type written to source_registry.csv")
    parser.add_argument("--official-status", default="unofficial", help="official_status written to source_registry.csv")
    parser.add_argument("--reliability-score", type=int, default=3, help="reliability_score written to source_registry.csv")
    parser.add_argument("--bias-risk", default="medium", choices=["low", "medium", "high"], help="bias_risk written to source_registry.csv")
    parser.add_argument("--max-reviews", type=int, default=100, help="Maximum direct-fetched review rows to import from a TapTap app review listing")
    parser.add_argument("--notes", default="", help="Extra notes written to the imported rows and source registry")
    return parser.parse_args()


def build_taptap_xua() -> str:
    return "V=1&PN=WebApp&LANG=zh_CN&VN_CODE=102&LOC=CN&PLT=PC&DS=Android&UID=opencode-section3&OS=Windows&OSV=10&DT=PC"


def build_taptap_api_url(endpoint: str, params: dict[str, str]) -> str:
    query = {"X-UA": build_taptap_xua(), **params}
    return f"https://www.taptap.cn/webapiv2/{endpoint}?{parse.urlencode(query)}"


def fetch_taptap_json(endpoint: str, params: dict[str, str]) -> dict[str, object]:
    payload = fetch_url_text(build_taptap_api_url(endpoint, params))
    data = json.loads(payload)
    if not isinstance(data, dict):
        raise SystemExit(f"TapTap API returned unexpected payload for {endpoint}")
    return data


def extract_taptap_app_id(url: str) -> str:
    match = re.search(r"/app/(\d+)", url)
    return match.group(1) if match else ""


def timestamp_to_iso(value: object) -> str:
    if not isinstance(value, int):
        return ""
    return dt.datetime.fromtimestamp(value, tz=dt.timezone.utc).isoformat()


def extract_taptap_listing_reviews(
    page_url: str,
    html_text: str,
    max_reviews: int,
    notes: str,
    game_page_title_override: str,
) -> list[dict[str, str]]:
    app_id = extract_taptap_app_id(page_url)
    if not app_id:
        raise SystemExit(f"Could not determine TapTap app id from URL: {page_url}")

    parsed_url = parse.urlparse(page_url)
    query = parse.parse_qs(parsed_url.query)
    mapping_value = query.get("mapping", [""])[0]
    label_value = query.get("label", [""])[0]
    sort_value = query.get("sort", [""])[0] or ("hot" if not mapping_value else "new")

    all_items: list[object] = []
    next_page_endpoint: str | None = "review/v2/list-by-app"
    current_params: dict[str, str] | None = {
        "app_id": app_id,
        "filter_platform": "",
        "limit": "10",
        "label": label_value,
        "mapping": mapping_value,
        "source_type": "",
        "sort": sort_value,
        "stage_type": "1",
    }
    
    seen_ids: set[int] = set()

    while next_page_endpoint and current_params and len(all_items) < max_reviews:
        payload = fetch_taptap_json(next_page_endpoint, current_params)
        data = payload.get("data")
        if not isinstance(data, dict):
            break
            
        items = data.get("list")
        if not isinstance(items, list):
            items = data.get("reviews")
        if not isinstance(items, list) or not items:
            break
            
        for item in items:
            if not isinstance(item, dict):
                continue
            moment = item.get("moment")
            if not isinstance(moment, dict):
                continue
            review = moment.get("review")
            if not isinstance(review, dict):
                continue
            review_id = review.get("id")
            if isinstance(review_id, int) and review_id not in seen_ids:
                seen_ids.add(review_id)
                all_items.append(item)
                
        next_page = data.get("next_page")
        if isinstance(next_page, str) and next_page:
            parsed_next = parse.urlparse(next_page)
            next_page_endpoint = parsed_next.path.lstrip("/webapiv2/")
            current_params = {k: v[0] for k, v in parse.parse_qs(parsed_next.query).items()}
        else:
            break

    if not all_items:
        raise SystemExit(f"TapTap review list API returned no reviews for app_id={app_id}")

    title = game_page_title_override or extract_title_text(html_text)
    if title.endswith(" - 游戏评价 - TapTap"):
        title = title[: -len(" - 游戏评价 - TapTap")].strip()
    page_title = title or game_page_title_override or f"TapTap app {app_id}"

    rows: list[dict[str, str]] = []
    for item in all_items[:max_reviews]:
        if not isinstance(item, dict):
            continue
        moment = item.get("moment")
        if not isinstance(moment, dict):
            continue
        review = moment.get("review")
        if not isinstance(review, dict):
            continue
        contents = review.get("contents")
        if not isinstance(contents, dict):
            continue
        raw_text = contents.get("raw_text")
        text_original = raw_text if isinstance(raw_text, str) and raw_text.strip() else clean_html_text(str(contents.get("text", "")))
        if not text_original:
            continue
        moment_stat = moment.get("stat")
        stat: dict[str, object] = moment_stat if isinstance(moment_stat, dict) else {}
        moment_author = moment.get("author")
        author: dict[str, object] = moment_author if isinstance(moment_author, dict) else {}
        author_user = author.get("user")
        user: dict[str, object] = author_user if isinstance(author_user, dict) else {}
        raw_stage_label = review.get("stage_label")
        stage_label = raw_stage_label if isinstance(raw_stage_label, str) else ""
        review_id = review.get("id")
        if not isinstance(review_id, int):
            continue
        notes_value = merge_notes("direct_app_review_api", notes, stage_label)
        rows.append(
            {
                "review_id": f"tt_review_{review_id}",
                "platform": "taptap",
                "author_name": str(user.get("name", "unknown")),
                "text_original": text_original,
                "likes": str(parse_int(str(stat.get("ups", 0)))),
                "replies": str(parse_int(str(stat.get("comments", 0)))),
                "review_publish_time": timestamp_to_iso(moment.get("publish_time")),
                "url": f"https://www.taptap.cn/review/{review_id}",
                "game_page_title": page_title,
                "language": detect_language(text_original),
                "notes": notes_value,
            }
        )
    if rows:
        return rows
    raise SystemExit(f"TapTap review list API returned items, but none could be normalized for app_id={app_id}")


def update_source_registry(
    source_registry_path: Path,
    source_row: dict[str, str],
) -> None:
    with exclusive_file_lock(source_registry_path):
        ensure_csv(source_registry_path, SOURCE_REGISTRY_HEADER)
        existing_rows = read_csv_rows(source_registry_path)
        deduped = [row for row in existing_rows if row.get("source_id") != source_row.get("source_id")]
        deduped.append(source_row)
        write_csv_rows(source_registry_path, SOURCE_REGISTRY_HEADER, deduped)


def merge_rows_by_key(
    existing_rows: list[dict[str, str]],
    new_rows: list[dict[str, str]],
    key_name: str,
    header: list[str],
) -> list[dict[str, str]]:
    merged: dict[str, dict[str, str]] = {}
    ordered_keys: list[str] = []

    for row in existing_rows + new_rows:
        key_value = row.get(key_name, "")
        if not key_value:
            continue
        normalized_row = {column: row.get(column, "") for column in header}
        if key_value not in merged:
            ordered_keys.append(key_value)
        merged[key_value] = normalized_row

    return [merged[key] for key in ordered_keys]


def extract_taptap_single_review(url: str, html_text: str, notes: str) -> dict[str, str]:
    description = extract_meta_content(html_text, "description")
    title = extract_title_text(html_text)
    keywords = extract_meta_content(html_text, "keywords")
    review_id_match = re.search(r"/review/(\d+)", url)
    review_id = review_id_match.group(1) if review_id_match else derive_source_id("taptap", url, title)
    author_name = ""
    game_page_title = ""
    marker = " 的评价 - TapTap"
    if " 对 " in title and marker in title:
        author_name, remainder = title.split(" 对 ", 1)
        game_page_title = remainder.split(marker, 1)[0].strip()
        author_name = author_name.strip()
    elif keywords and "," in keywords:
        keyword_parts = [part.strip() for part in keywords.split(",") if part.strip()]
        if len(keyword_parts) >= 2:
            author_name = keyword_parts[0]
            game_page_title = keyword_parts[1]
    publish_time = extract_meta_content(html_text, "bytedance:published_time") or extract_meta_content(html_text, "article:published_time")
    text_original = description or extract_meta_content(html_text, "og:description")
    if not text_original:
        raise SystemExit(f"Could not extract review text from TapTap review page: {url}")
    return {
        "review_id": f"tt_review_{review_id}",
        "platform": "taptap",
        "author_name": author_name or "unknown",
        "text_original": text_original,
        "likes": "0",
        "replies": "0",
        "review_publish_time": publish_time,
        "url": url,
        "game_page_title": game_page_title or title or "TapTap review",
        "language": detect_language(text_original),
        "notes": merge_notes("direct_review_page", notes),
    }


def extract_review_links_from_listing(page_url: str, html_text: str, max_reviews: int) -> list[str]:
    review_links: list[str] = []
    seen: set[str] = set()
    for match in re.finditer(r'https://www\.taptap\.cn/review/(\d+)|/review/(\d+)', html_text):
        review_id = match.group(1) or match.group(2)
        if not review_id:
            continue
        full_url = f"https://www.taptap.cn/review/{review_id}"
        if full_url in seen:
            continue
        seen.add(full_url)
        review_links.append(full_url)
        if len(review_links) >= max_reviews:
            break
    if review_links:
        return review_links
    if page_url.rstrip("/").endswith("/review") and re.search(r"/app/\d+/review", page_url):
        raise SystemExit(
            "TapTap review listing fetched successfully, but no review links were found in static HTML. "
            "Use a direct `.../review/<id>` URL or manual export fallback."
        )
    raise SystemExit(
        "TapTap app page HTML did not expose review links in a stable static form. "
        "Try the app `/review` page or direct review URLs instead."
    )


def crawl_taptap_rows(page_url: str, max_reviews: int, notes: str) -> list[dict[str, str]]:
    html_text = fetch_url_text(page_url)
    if re.search(r"/review/\d+", page_url):
        return [extract_taptap_single_review(page_url, html_text, notes)]
    app_id = extract_taptap_app_id(page_url)
    if app_id:
        try:
            return extract_taptap_listing_reviews(page_url, html_text, max_reviews, notes, "")
        except SystemExit:
            if page_url.rstrip("/").endswith("/review"):
                review_links = extract_review_links_from_listing(page_url, html_text, max_reviews)
                crawled_rows: list[dict[str, str]] = []
                for review_url in review_links:
                    review_html = fetch_url_text(review_url)
                    crawled_rows.append(extract_taptap_single_review(review_url, review_html, notes))
                return crawled_rows
            raise
    review_links = extract_review_links_from_listing(page_url, html_text, max_reviews)
    crawled_rows: list[dict[str, str]] = []
    for review_url in review_links:
        review_html = fetch_url_text(review_url)
        crawled_rows.append(extract_taptap_single_review(review_url, review_html, notes))
    return crawled_rows


def main() -> None:
    args = parse_args()
    project_dir = Path(args.project_dir).resolve()
    if not args.input_file and not args.page_url:
        raise SystemExit("Section 3 capture requires either --page-url or --input-file.")

    source_rows: list[dict[str, str]]
    if args.input_file:
        input_path = Path(args.input_file).resolve()
        if not input_path.exists():
            raise SystemExit(f"Input file not found: {input_path}")
        source_rows = load_input_rows(input_path)
        if not source_rows:
            raise SystemExit(f"Input file contains no review rows: {input_path}")
    else:
        if platform_from_url(args.page_url) != "taptap":
            raise SystemExit(f"TapTap capture received a non-TapTap URL: {args.page_url}")
        source_rows = crawl_taptap_rows(args.page_url, args.max_reviews, args.notes)

    section_dir = project_dir / SECTION_DIR_NAME
    section_dir.mkdir(parents=True, exist_ok=True)
    review_registry_path = section_dir / "review_registry.csv"
    review_sample_path = section_dir / "review_sample.csv"
    ensure_csv(review_registry_path, REVIEW_REGISTRY_HEADER)
    ensure_csv(review_sample_path, REVIEW_SAMPLE_HEADER)

    platform = "taptap" if args.page_url and not args.input_file else args.platform
    capture_method_value = args.capture_method
    access_method_value = args.access_method
    if args.page_url and not args.input_file:
        if re.search(r"/review/\d+", args.page_url):
            if capture_method_value == "manual_import":
                capture_method_value = "direct_html_fetch"
            if access_method_value == "manual":
                access_method_value = "scrape"
        elif extract_taptap_app_id(args.page_url):
            if capture_method_value == "manual_import":
                capture_method_value = "direct_review_api_fetch"
            if access_method_value == "manual":
                access_method_value = "api"
        else:
            if capture_method_value == "manual_import":
                capture_method_value = "direct_html_fetch"
            if access_method_value == "manual":
                access_method_value = "scrape"
    page_url = args.page_url or get_first_value(source_rows[0], "url")
    game_page_title = args.game_page_title or get_first_value(source_rows[0], "game_page_title") or platform
    source_id = derive_source_id(platform, page_url, game_page_title)
    review_registry_rows: list[dict[str, str]] = []
    review_sample_rows: list[dict[str, str]] = []

    for index, raw_row in enumerate(source_rows, start=1):
        text_original = get_first_value(raw_row, "text_original")
        if not text_original:
            continue
        review_id = get_first_value(raw_row, "review_id") or f"{source_id}_r{index:04d}"
        review_platform = get_first_value(raw_row, "platform") or platform
        review_url = get_first_value(raw_row, "url") or page_url
        review_title = get_first_value(raw_row, "game_page_title") or game_page_title
        review_language = get_first_value(raw_row, "language") or detect_language(text_original)
        likes = str(parse_int(get_first_value(raw_row, "likes")))
        replies = str(parse_int(get_first_value(raw_row, "replies")))
        publish_time = get_first_value(raw_row, "review_publish_time")
        notes = merge_notes(get_first_value(raw_row, "notes"), args.notes)
        author_name = get_first_value(raw_row, "author_name") or f"reviewer_{index:03d}"

        review_registry_rows.append(
            {
                "review_id": review_id,
                "platform": review_platform,
                "url": review_url,
                "game_page_title": review_title,
                "review_publish_time": publish_time,
                "review_length_bucket": review_length_bucket(text_original),
                "likes": likes,
                "replies": replies,
                "capture_method": capture_method_value,
                "language": review_language,
                "is_longform": "true" if review_length_bucket(text_original) == "long" else "false",
                "notes": notes,
            }
        )
        review_sample_rows.append(
            {
                "review_id": review_id,
                "platform": review_platform,
                "author_name": author_name,
                "text_original": text_original,
                "text_normalized": normalize_text_value(text_original),
                "language": review_language,
                "likes": likes,
                "replies": replies,
                "sentiment_label": "",
                "topic_label": "",
                "experience_basis": "",
                "is_high_value": "",
                "confidence_note": "capture_import_v1",
            }
        )

    if not review_registry_rows:
        source_label = args.input_file or args.page_url or "capture source"
        raise SystemExit(f"No usable review rows found in {source_label}")

    existing_registry_rows = read_csv_rows(review_registry_path)
    existing_sample_rows = read_csv_rows(review_sample_path)
    merged_registry_rows = merge_rows_by_key(existing_registry_rows, review_registry_rows, "review_id", REVIEW_REGISTRY_HEADER)
    merged_sample_rows = merge_rows_by_key(existing_sample_rows, review_sample_rows, "review_id", REVIEW_SAMPLE_HEADER)
    write_csv_rows(review_registry_path, REVIEW_REGISTRY_HEADER, merged_registry_rows)
    write_csv_rows(review_sample_path, REVIEW_SAMPLE_HEADER, merged_sample_rows)

    source_registry_path = project_dir / "sources" / "source_registry.csv"
    update_source_registry(
        source_registry_path,
        {
            "source_id": source_id,
            "section_id": "section_3",
            "platform": platform,
            "source_type": args.source_type,
            "url": page_url,
            "title": game_page_title,
            "author_or_channel": "",
            "publish_date": "",
            "language": review_registry_rows[0].get("language", "unknown"),
            "official_status": args.official_status,
            "reliability_score": str(args.reliability_score),
            "bias_risk": args.bias_risk,
            "access_method": access_method_value,
            "capture_status": "manual_fallback" if args.input_file else "success",
            "notes": merge_notes("section_3_import" if args.input_file else "section_3_direct_fetch", args.notes),
        },
    )
    print(
        f"Imported {len(review_registry_rows)} reviews into {section_dir}; total_review_rows={len(merged_registry_rows)}"
    )


if __name__ == "__main__":
    main()
