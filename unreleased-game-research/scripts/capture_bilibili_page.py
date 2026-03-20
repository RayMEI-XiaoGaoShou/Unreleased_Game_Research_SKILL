from __future__ import annotations

import argparse
import json
import shlex
from pathlib import Path
from urllib import error, request

import importlib

from file_lock import exclusive_file_lock

section_3_common = importlib.import_module("section_3_common")
DEFAULT_HEADERS = section_3_common.DEFAULT_HEADERS
REVIEW_REGISTRY_HEADER = section_3_common.REVIEW_REGISTRY_HEADER
REVIEW_SAMPLE_HEADER = section_3_common.REVIEW_SAMPLE_HEADER
SOURCE_REGISTRY_HEADER = section_3_common.SOURCE_REGISTRY_HEADER
SECTION_DIR_NAME = section_3_common.SECTION_DIR_NAME
append_unique_rows = section_3_common.append_unique_rows
detect_language = section_3_common.detect_language
derive_source_id = section_3_common.derive_source_id
ensure_csv = section_3_common.ensure_csv
extract_meta_content = section_3_common.extract_meta_content
extract_title_text = section_3_common.extract_title_text
fetch_url_text = section_3_common.fetch_url_text
merge_notes = section_3_common.merge_notes
normalize_text_value = section_3_common.normalize_text_value
parse_int = section_3_common.parse_int
read_csv_rows = section_3_common.read_csv_rows
review_length_bucket = section_3_common.review_length_bucket
write_csv_rows = section_3_common.write_csv_rows

GUIDE_FILE_NAME = "section_3_bilibili_semi_auto_guide.md"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Semi-automatic capture for Bilibili game homepage or reservation pages.")
    parser.add_argument("--project-dir", required=True, help="Path to an initialized project directory")
    parser.add_argument("--page-url", help="Biligame or app.biligame detail URL")
    parser.add_argument("--game-page-title", default="", help="Override detected game page title")
    parser.add_argument("--platform", default="biligame", help="Platform label stored in Section 3 outputs")
    parser.add_argument("--capture-method", default="semi_auto_signed_request", help="capture_method value written to review_registry.csv")
    parser.add_argument("--access-method", default="api", choices=["api", "browser", "manual", "transcript", "scrape"], help="access_method written to source_registry.csv")
    parser.add_argument("--source-type", default="player review", help="source_type written to source_registry.csv")
    parser.add_argument("--official-status", default="unofficial", help="official_status written to source_registry.csv")
    parser.add_argument("--reliability-score", type=int, default=2, help="reliability_score written to source_registry.csv")
    parser.add_argument("--bias-risk", default="high", choices=["low", "medium", "high"], help="bias_risk written to source_registry.csv")
    parser.add_argument("--request-bundle-file", help="Path to a plain-text or JSON file containing copied Bilibili request info")
    parser.add_argument("--notes", default="", help="Extra notes written to the imported rows and source registry")
    return parser.parse_args()


def guide_path() -> Path:
    return Path(__file__).resolve().parent.parent / "references" / GUIDE_FILE_NAME


def render_guide_message() -> str:
    path = guide_path()
    body = path.read_text(encoding="utf-8") if path.exists() else "Guide file is missing."
    return (
        "Bilibili Section 3 semi-automatic capture needs a request bundle copied from browser DevTools.\n"
        f"Read and follow: {path}\n\n"
        f"{body}"
    )


def update_source_registry(source_registry_path: Path, source_row: dict[str, str]) -> None:
    with exclusive_file_lock(source_registry_path):
        ensure_csv(source_registry_path, SOURCE_REGISTRY_HEADER)
        existing_rows: list[dict[str, str]] = []
        if source_registry_path.exists():
            existing_rows = read_csv_rows(source_registry_path)
        deduped = [row for row in existing_rows if row.get("source_id") != source_row.get("source_id")]
        deduped.append(source_row)
        write_csv_rows(source_registry_path, SOURCE_REGISTRY_HEADER, deduped)


def normalize_bundle_key(key: str) -> str:
    normalized = []
    for char in key.casefold():
        normalized.append(char if char.isalnum() else "_")
    text = "".join(normalized)
    while "__" in text:
        text = text.replace("__", "_")
    return text.strip("_")


def parse_curl_command(command_text: str) -> dict[str, str]:
    tokens = shlex.split(command_text, posix=True)
    if not tokens or tokens[0] != "curl":
        raise SystemExit("Copied cURL text is invalid. Please use Copy as cURL (bash).\n\n" + render_guide_message())
    parsed: dict[str, str] = {}
    index = 1
    while index < len(tokens):
        token = tokens[index]
        # Skip known flags without values
        if token in {"--compressed", "--insecure", "--location", "-L", "-s", "-S"}:
            index += 1
            continue
        # Handle headers (-H or --header)
        if token in {"-H", "--header"} and index + 1 < len(tokens):
            header_text = tokens[index + 1]
            if ":" in header_text:
                header_key, header_value = header_text.split(":", 1)
                parsed[normalize_bundle_key(header_key)] = header_value.strip()
            index += 2
            continue
        # Handle explicit URL flag
        if token in {"--url"} and index + 1 < len(tokens):
            parsed["request_url"] = tokens[index + 1].strip()
            index += 2
            continue
        # Skip other flags that take values
        if token in {"-X", "--request", "--data-raw", "--data", "--data-binary", "-d"} and index + 1 < len(tokens):
            index += 2
            continue
        # Handle bare URL argument (http, https, or file for testing)
        if token.startswith(("http://", "https://", "file://")):
            parsed["request_url"] = token.strip()
            index += 1
            continue
        index += 1
    return parsed


def merge_curl_bundle(parsed: dict[str, object], curl_lines: list[str]) -> dict[str, object]:
    request_urls: list[str] = []
    for line in curl_lines:
        curl_info = parse_curl_command(line)
        request_url = curl_info.get("request_url", "")
        if request_url:
            request_urls.append(request_url)
            if ("/recommend" in request_url) and not parsed.get("recommend_request_url"):
                parsed["recommend_request_url"] = request_url
            if "/page" in request_url:
                page_request_urls = parsed.get("page_request_urls", [])
                if isinstance(page_request_urls, list):
                    page_request_urls.append(request_url)
                    parsed["page_request_urls"] = page_request_urls
        for header_key in ["cookie", "referer", "user_agent"]:
            if curl_info.get(header_key) and not parsed.get(header_key):
                parsed[header_key] = curl_info[header_key]
    if request_urls and not parsed.get("page_url"):
        referer = str(parsed.get("referer", "")).strip()
        if referer:
            parsed["page_url"] = referer
    return parsed


def parse_request_bundle(bundle_path: Path) -> dict[str, object]:
    if not bundle_path.exists():
        raise SystemExit(f"Bilibili request bundle file not found: {bundle_path}\n\n{render_guide_message()}")
    text_content = bundle_path.read_text(encoding="utf-8")
    if bundle_path.suffix.casefold() == ".json":
        payload = json.loads(text_content)
        if not isinstance(payload, dict):
            raise SystemExit(f"Bilibili request bundle JSON must be an object: {bundle_path}")
        parsed: dict[str, object] = {normalize_bundle_key(str(key)): value for key, value in payload.items()}
    else:
        parsed = {}
        page_request_urls: list[str] = []
        curl_lines: list[str] = []
        
        import re
        curl_matches = re.finditer(r'(?:^|\n)(curl\s+.*?)(?=\ncurl\s+|\Z)', text_content, re.DOTALL)
        for m in curl_matches:
            curl_lines.append(m.group(1))
            
        for raw_line in text_content.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("curl ") or line.startswith("-H ") or line == "\\":
                continue
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            normalized_key = normalize_bundle_key(key)
            cleaned_value = value.strip()
            if not cleaned_value:
                continue
            if normalized_key.startswith("page_request_url"):
                page_request_urls.append(cleaned_value)
            else:
                parsed[normalized_key] = cleaned_value
        if page_request_urls:
            parsed["page_request_urls"] = page_request_urls
        if curl_lines:
            parsed = merge_curl_bundle(parsed, curl_lines)
    if "page_request_url" in parsed and "page_request_urls" not in parsed:
        parsed["page_request_urls"] = [str(parsed["page_request_url"])]
    recommend_url = str(parsed.get("recommend_request_url", "")).strip()
    raw_page_urls = parsed.get("page_request_urls", [])
    page_url_items = raw_page_urls if isinstance(raw_page_urls, list) else []
    page_urls = [str(item).strip() for item in page_url_items if str(item).strip()]
    cookie = str(parsed.get("cookie", "")).strip()
    referer = str(parsed.get("referer", parsed.get("referrer", ""))).strip()
    user_agent = str(parsed.get("user_agent", DEFAULT_HEADERS["User-Agent"])).strip() or DEFAULT_HEADERS["User-Agent"]
    page_url = str(parsed.get("biligame_page_url", parsed.get("page_url", ""))).strip() or referer
    game_page_title = str(parsed.get("game_page_title", "")).strip()
    missing_fields: list[str] = []
    if not recommend_url and not page_urls:
        missing_fields.append("Recommend Request URL or Page Request URL")
    if not cookie:
        missing_fields.append("Cookie or copied cURL with Cookie header")
    if not referer:
        missing_fields.append("Referer or copied cURL with Referer header")
    if missing_fields:
        raise SystemExit("Bilibili request bundle is missing required fields: " + ", ".join(missing_fields) + "\n\n" + render_guide_message())
    return {
        "page_url": page_url,
        "game_page_title": game_page_title,
        "recommend_request_url": recommend_url,
        "page_request_urls": page_urls,
        "cookie": cookie,
        "referer": referer,
        "user_agent": user_agent,
    }


def request_headers(bundle: dict[str, object]) -> dict[str, str]:
    referer = str(bundle["referer"])
    return {
        "User-Agent": str(bundle["user_agent"]),
        "Accept": "*/*",
        "Accept-Language": DEFAULT_HEADERS["Accept-Language"],
        "Cookie": str(bundle["cookie"]),
        "Referer": referer,
        "Origin": "https://www.biligame.com",
    }


def fetch_url_text_with_headers(url: str, headers: dict[str, str], timeout: int = 20) -> str:
    req = request.Request(url, headers=headers)
    try:
        with request.urlopen(req, timeout=timeout) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(charset, errors="replace")
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"Request failed for {url} ({exc.code}): {body[:500]}") from exc
    except error.URLError as exc:
        raise SystemExit(f"Network error while requesting {url}: {exc.reason}") from exc


def load_comment_items(url: str, headers: dict[str, str], response_kind: str) -> list[dict[str, object]]:
    payload = json.loads(fetch_url_text_with_headers(url, headers))
    if not isinstance(payload, dict):
        raise SystemExit(f"Unexpected Bilibili payload for {response_kind}: {url}")
    data = payload.get("data")
    if response_kind == "recommend":
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        raise SystemExit(f"Recommend request did not return a comment list: {url}")
    if isinstance(data, dict) and isinstance(data.get("list"), list):
        return [item for item in data["list"] if isinstance(item, dict)]
    raise SystemExit(f"Page request did not return a paged comment list: {url}")


def resolve_title(page_url: str, explicit_title: str) -> str:
    if explicit_title:
        return explicit_title
    if not page_url:
        return "Bilibili game page"
    html_text = fetch_url_text(page_url)
    return extract_meta_content(html_text, "og:title") or extract_title_text(html_text) or "Bilibili game page"


def normalize_comment_rows(
    items: list[dict[str, object]],
    page_url: str,
    game_page_title: str,
    platform: str,
    capture_method: str,
    extra_notes: str,
    source_label: str,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    registry_rows: list[dict[str, str]] = []
    sample_rows: list[dict[str, str]] = []
    for item in items:
        comment_no = str(item.get("comment_no", "")).strip()
        content = str(item.get("content", "")).strip()
        if not comment_no or not content:
            continue
        review_id = f"blgm_comment_{comment_no}"
        likes = str(parse_int(str(item.get("up_count", 0))))
        replies = str(parse_int(str(item.get("reply_count", 0))))
        language = detect_language(content)
        notes = merge_notes("semi_auto_request_bundle", source_label, extra_notes)
        length_bucket = review_length_bucket(content)
        registry_rows.append(
            {
                "review_id": review_id,
                "platform": platform,
                "url": page_url,
                "game_page_title": game_page_title,
                "review_publish_time": str(item.get("publish_time", "")),
                "review_length_bucket": length_bucket,
                "likes": likes,
                "replies": replies,
                "capture_method": capture_method,
                "language": language,
                "is_longform": "true" if length_bucket == "long" else "false",
                "notes": notes,
            }
        )
        sample_rows.append(
            {
                "review_id": review_id,
                "platform": platform,
                "author_name": str(item.get("user_name", "unknown")),
                "text_original": content,
                "text_normalized": normalize_text_value(content),
                "language": language,
                "likes": likes,
                "replies": replies,
                "sentiment_label": "",
                "topic_label": "",
                "experience_basis": "",
                "is_high_value": "",
                "confidence_note": f"biligame_{source_label}_semi_auto_capture",
            }
        )
    return registry_rows, sample_rows


def dedupe_rows(rows: list[dict[str, str]], key_name: str) -> list[dict[str, str]]:
    deduped: dict[str, dict[str, str]] = {}
    for row in rows:
        key = row.get(key_name, "")
        if key:
            deduped[key] = row
    return list(deduped.values())


def main() -> None:
    args = parse_args()
    if not args.request_bundle_file:
        raise SystemExit(render_guide_message())

    project_dir = Path(args.project_dir).resolve()
    bundle = parse_request_bundle(Path(args.request_bundle_file).resolve())
    page_url = args.page_url or str(bundle.get("page_url", ""))
    if not page_url:
        raise SystemExit("Bilibili semi-automatic capture still needs the game detail page URL.\n\n" + render_guide_message())

    title = resolve_title(page_url, args.game_page_title or str(bundle.get("game_page_title", "")))
    headers = request_headers(bundle)
    request_plan: list[tuple[str, str, str]] = []
    recommend_url = str(bundle.get("recommend_request_url", ""))
    if recommend_url:
        request_plan.append(("recommend", "recommend", recommend_url))
    raw_page_request_urls = bundle.get("page_request_urls", [])
    page_request_url_items = raw_page_request_urls if isinstance(raw_page_request_urls, list) else []
    for index, page_request_url in enumerate(page_request_url_items, start=1):
        request_plan.append((f"page_{index}", "page", str(page_request_url)))

    all_registry_rows: list[dict[str, str]] = []
    all_sample_rows: list[dict[str, str]] = []
    for source_label, response_kind, request_url in request_plan:
        items = load_comment_items(request_url, headers, response_kind)
        registry_rows, sample_rows = normalize_comment_rows(
            items,
            page_url,
            title,
            args.platform,
            args.capture_method,
            args.notes,
            source_label,
        )
        all_registry_rows.extend(registry_rows)
        all_sample_rows.extend(sample_rows)

    all_registry_rows = dedupe_rows(all_registry_rows, "review_id")
    all_sample_rows = dedupe_rows(all_sample_rows, "review_id")
    if not all_registry_rows:
        raise SystemExit("Bilibili semi-automatic capture ran, but no comment rows were normalized from the supplied request bundle.")

    section_dir = project_dir / SECTION_DIR_NAME
    review_registry_path = section_dir / "review_registry.csv"
    review_sample_path = section_dir / "review_sample.csv"
    ensure_csv(review_registry_path, REVIEW_REGISTRY_HEADER)
    ensure_csv(review_sample_path, REVIEW_SAMPLE_HEADER)

    registry_written = append_unique_rows(review_registry_path, REVIEW_REGISTRY_HEADER, all_registry_rows, "review_id")
    sample_written = append_unique_rows(review_sample_path, REVIEW_SAMPLE_HEADER, all_sample_rows, "review_id")

    source_id = derive_source_id(args.platform, page_url, title)
    update_source_registry(
        project_dir / "sources" / "source_registry.csv",
        {
            "source_id": source_id,
            "section_id": "section_3",
            "platform": args.platform,
            "source_type": args.source_type,
            "url": page_url,
            "title": title,
            "author_or_channel": "",
            "publish_date": "",
            "language": detect_language(" ".join(row["text_original"] for row in all_sample_rows)),
            "official_status": args.official_status,
            "reliability_score": str(args.reliability_score),
            "bias_risk": args.bias_risk,
            "access_method": args.access_method,
            "capture_status": "success",
            "notes": merge_notes("section_3_biligame_semi_auto", args.notes),
        },
    )
    print(
        f"Semi-automatic captured Bilibili comments into {section_dir}; new_registry_rows={registry_written}; new_sample_rows={sample_written}"
    )


if __name__ == "__main__":
    main()
