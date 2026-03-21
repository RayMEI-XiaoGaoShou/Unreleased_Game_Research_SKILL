from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import re
import time
from collections import Counter
from pathlib import Path
from typing import Any
from urllib import error, parse, request
import importlib

exclusive_file_lock = importlib.import_module("file_lock").exclusive_file_lock

# ---------------------------------------------------------------------------
# Bilibili WBI Signature
# Required since 2023 for all /x/* API endpoints.
# Without this, the server returns HTTP 412.
# Pure stdlib implementation – no external dependencies.
# Reference: https://github.com/SocialSisterYi/bilibili-API-collect
# ---------------------------------------------------------------------------

_MIXIN_KEY_ENC_TAB = [
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35,
    27, 43, 5, 49, 33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13,
    37, 48, 7, 16, 24, 55, 40, 61, 26, 17, 0, 1, 60, 51, 30, 4,
    22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11, 36, 20, 34, 44, 52,
]

_wbi_cache: dict[str, Any] = {}  # {"mixin_key": str, "expires_at": float}


def _fetch_wbi_keys(cookie_string: str) -> tuple[str, str]:
    """Fetch img_key and sub_key from Bilibili /x/web-interface/nav."""
    url = "https://api.bilibili.com/x/web-interface/nav"
    req = request.Request(url)
    req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    req.add_header("Referer", "https://www.bilibili.com/")
    if cookie_string:
        req.add_header("Cookie", cookie_string)
    try:
        with request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        raise SystemExit(f"Failed to fetch WBI keys: {exc}") from exc
    wbi_img = data.get("data", {}).get("wbi_img", {})
    img_url: str = wbi_img.get("img_url", "")
    sub_url: str = wbi_img.get("sub_url", "")
    img_key = img_url.rsplit("/", 1)[-1].split(".")[0]
    sub_key = sub_url.rsplit("/", 1)[-1].split(".")[0]
    return img_key, sub_key


def _derive_mixin_key(img_key: str, sub_key: str) -> str:
    raw = img_key + sub_key
    return "".join(raw[i] for i in _MIXIN_KEY_ENC_TAB if i < len(raw))[:32]


def _get_mixin_key(cookie_string: str) -> str:
    now = time.time()
    if _wbi_cache.get("mixin_key") and now < _wbi_cache.get("expires_at", 0):
        return _wbi_cache["mixin_key"]
    img_key, sub_key = _fetch_wbi_keys(cookie_string)
    mixin_key = _derive_mixin_key(img_key, sub_key)
    _wbi_cache["mixin_key"] = mixin_key
    _wbi_cache["expires_at"] = now + 3600  # cache for 1 hour
    return mixin_key


def _wbi_sign_params(params: dict[str, Any], cookie_string: str) -> dict[str, Any]:
    """Return a copy of params with wts and w_rid added (WBI signature)."""
    mixin_key = _get_mixin_key(cookie_string)
    signed = dict(params)
    signed["wts"] = int(time.time())
    # Remove chars that may interfere with signing
    def _clean(v: str) -> str:
        return re.sub(r"[!'()*]", "", str(v))
    query = "&".join(f"{k}={_clean(v)}" for k, v in sorted(signed.items()))
    signed["w_rid"] = hashlib.md5((query + mixin_key).encode("utf-8")).hexdigest()
    return signed


VIDEO_REGISTRY_HEADER = [
    "video_id",
    "milestone_id",
    "platform",
    "url",
    "title",
    "publish_date",
    "channel_name",
    "official_status",
    "content_type",
    "comment_capture_mode",
    "comments_captured",
    "comments_visible_total",
    "coverage_ratio",
    "capture_stop_reason",
    "language_mix",
    "notes",
]

COMMENT_SAMPLE_HEADER = [
    "comment_id",
    "video_id",
    "platform",
    "comment_time",
    "author_name",
    "text_original",
    "text_normalized",
    "language",
    "likes",
    "replies",
    "is_top_comment",
    "is_spam_or_noise",
    "sentiment_label",
    "topic_label",
    "confidence_note",
]

SOURCE_REGISTRY_HEADER = [
    "source_id",
    "section_id",
    "platform",
    "source_type",
    "url",
    "title",
    "author_or_channel",
    "publish_date",
    "language",
    "official_status",
    "reliability_score",
    "bias_risk",
    "access_method",
    "capture_status",
    "notes",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect Bilibili official video comments into Section 2 artifacts.")
    parser.add_argument("video_ref", help="Bilibili video BV ID or URL")
    parser.add_argument("--project-dir", required=True, help="Path to an initialized project directory")
    parser.add_argument("--milestone-id", required=True, help="Milestone identifier for this video")
    parser.add_argument("--cookie-file", help="Path to JSON file containing Bilibili cookies (SESSDATA, etc)")
    parser.add_argument("--cookie-string", help="Raw cookie string for Bilibili requests")
    parser.add_argument("--max-pages", type=int, default=0, help="Maximum comment pages to fetch; 0 means no explicit cap")
    parser.add_argument("--max-replies-per-thread", type=int, default=20, help="Maximum replies to fetch per top-level comment")
    parser.add_argument(
        "--sort-mode",
        default="hot",
        choices=["hot", "time"],
        help="Sort mode for main comments",
    )
    parser.add_argument("--content-type", default="official_video", help="Artifact content type label")
    parser.add_argument("--official-status", default="official", help="Source official_status field")
    parser.add_argument("--notes", default="", help="Extra note stored in registry outputs")
    return parser.parse_args()


def extract_bvid(video_ref: str) -> str:
    if re.fullmatch(r"BV[1-9A-HJ-NP-Za-km-z]{10}", video_ref, re.IGNORECASE):
        return video_ref

    parsed = parse.urlparse(video_ref)
    path_parts = [part for part in parsed.path.split("/") if part]
    for part in path_parts:
        if re.fullmatch(r"BV[1-9A-HJ-NP-Za-km-z]{10}", part, re.IGNORECASE):
            return part

    raise SystemExit(f"Could not parse a Bilibili BV ID from: {video_ref}")


def load_cookie_string(cookie_file: str | None, cookie_string: str | None) -> str:
    if cookie_string:
        return cookie_string
    if cookie_file:
        path = Path(cookie_file)
        if not path.exists():
            raise SystemExit(f"Cookie file not found: {path}")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return "; ".join(f"{k}={v}" for k, v in data.items())
            raise SystemExit(f"Cookie file must be a JSON dictionary: {path}")
        except json.JSONDecodeError as exc:
            raise SystemExit(f"Invalid JSON in cookie file: {exc}")
    return ""


def bilibili_request(url: str, cookie_string: str) -> dict[str, Any]:
    req = request.Request(url)
    req.add_header(
        "User-Agent",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    )
    req.add_header("Referer", "https://www.bilibili.com/")
    if cookie_string:
        req.add_header("Cookie", cookie_string)
    
    try:
        with request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode("utf-8"))
            if data.get("code") != 0:
                print(f"[Warning] Bilibili API returned non-zero code {data.get('code')}: {data.get('message')}")
            return data
    except error.HTTPError as exc:
        raise SystemExit(f"Bilibili API request failed ({exc.code}): {exc.reason}") from exc
    except error.URLError as exc:
        raise SystemExit(f"Network error while calling Bilibili API: {exc.reason}") from exc


def fetch_video_metadata(bvid: str, cookie_string: str) -> dict[str, Any]:
    url = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
    data = bilibili_request(url, cookie_string)
    if data.get("code") != 0:
        raise SystemExit(f"Failed to fetch metadata for {bvid}: {data.get('message')}")
    return data.get("data", {})


def fetch_main_comments(oid: int, sort_mode: str, max_pages: int, cookie_string: str) -> tuple[list[dict[str, Any]], int, str]:
    # sort_mode: 1=time, 2=hot (fallback to 0=time default usually)
    sort_param = 2 if sort_mode == "hot" else 1
    all_replies: list[dict[str, Any]] = []
    total_count = 0
    stop_reason = "complete"
    page = 1
    
    while True:
        if max_pages > 0 and page > max_pages:
            stop_reason = "page_limit"
            break
        base_params = {"type": "1", "oid": str(oid), "sort": str(sort_param), "pn": str(page), "ps": "20"}
        signed = _wbi_sign_params(base_params, cookie_string)
        url = "https://api.bilibili.com/x/v2/reply?" + parse.urlencode(signed)
        time.sleep(random.uniform(0.8, 1.5))  # slightly longer delay after WBI
        data = bilibili_request(url, cookie_string)
        
        if data.get("code") != 0:
            stop_reason = f"api_code_{data.get('code')}"
            break
            
        replies = data.get("data", {}).get("replies")
        if not replies:
            stop_reason = "no_more_threads"
            break
            
        all_replies.extend(replies)
        
        page_info = data.get("data", {}).get("page", {})
        total_count = int(page_info.get("count", 0) or 0)
        if total_count and len(all_replies) >= total_count:
            stop_reason = "complete"
            break
        page += 1
    return all_replies, total_count, stop_reason


def fetch_sub_replies(oid: int, root_id: int, max_replies: int, cookie_string: str) -> list[dict[str, Any]]:
    if max_replies <= 0:
        return []
        
    all_replies: list[dict[str, Any]] = []
    page = 1
    
    while len(all_replies) < max_replies:
        base_params = {"type": "1", "oid": str(oid), "root": str(root_id), "pn": str(page), "ps": "20"}
        signed = _wbi_sign_params(base_params, cookie_string)
        url = "https://api.bilibili.com/x/v2/reply/reply?" + parse.urlencode(signed)
        time.sleep(random.uniform(1.5, 3.0))  # longer delay for sub-replies
        data = bilibili_request(url, cookie_string)
        
        if data.get("code") != 0:
            break
            
        replies = data.get("data", {}).get("replies")
        if not replies:
            break
            
        all_replies.extend(replies)
        
        page_info = data.get("data", {}).get("page", {})
        count = page_info.get("count", 0)
        if len(all_replies) >= count or len(replies) == 0:
            break
            
        page += 1
        
    return all_replies[:max_replies]


def normalize_text(text: str) -> str:
    return " ".join(text.split())


def detect_language(text: str) -> str:
    if re.search(r"[\u4e00-\u9fff]", text):
        return "zh"
    if re.search(r"[\u3040-\u30ff]", text):
        return "ja"
    if re.search(r"[\uac00-\ud7af]", text):
        return "ko"
    if re.search(r"[A-Za-z]", text):
        return "en"
    return "unknown"


def is_spam_or_noise(text: str) -> bool:
    normalized = normalize_text(text)
    if not normalized:
        return True
    if "http://" in normalized or "https://" in normalized:
        return True
    if len(normalized) <= 1:
        return True
    return False


def format_timestamp(ts: int) -> str:
    import datetime
    return datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc).isoformat()


def build_comment_row(item: dict[str, Any], bvid: str, is_top: bool, capture_mode: str, parent_id: str | None = None) -> dict[str, Any]:
    content = item.get("content", {})
    text_original = content.get("message", "")
    member = item.get("member", {})
    
    note = f"bilibili_api:{capture_mode}"
    if parent_id:
        note += f"; reply_to:{parent_id}"
        
    return {
        "comment_id": str(item.get("rpid", "")),
        "video_id": bvid,
        "platform": "bilibili",
        "comment_time": format_timestamp(item.get("ctime", 0)),
        "author_name": member.get("uname", ""),
        "text_original": text_original,
        "text_normalized": normalize_text(text_original),
        "language": detect_language(text_original),
        "likes": item.get("like", 0),
        "replies": item.get("rcount", 0),
        "is_top_comment": "true" if is_top else "false",
        "is_spam_or_noise": "true" if is_spam_or_noise(text_original) else "false",
        "sentiment_label": "",
        "topic_label": "",
        "confidence_note": note,
    }


def ensure_csv(path: Path, header: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=header)
            writer.writeheader()


def load_existing_keys(path: Path, key_field: str) -> set[str]:
    if not path.exists():
        return set()
    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return {row[key_field] for row in reader if row.get(key_field)}


def append_unique_rows(path: Path, header: list[str], rows: list[dict[str, Any]], key_field: str) -> int:
    with exclusive_file_lock(path):
        ensure_csv(path, header)
        existing = load_existing_keys(path, key_field)
        written = 0
        with path.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=header)
            for row in rows:
                key = str(row[key_field])
                if key in existing:
                    continue
                writer.writerow(row)
                existing.add(key)
                written += 1
    return written


def write_raw_capture(
    section_dir: Path,
    bvid: str,
    metadata: dict[str, Any],
    main_comments: list[dict[str, Any]],
    sub_replies: dict[str, list[dict[str, Any]]],
) -> Path:
    raw_dir = section_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / f"bilibili_{bvid}.json"
    raw_path.write_text(
        json.dumps({"metadata": metadata, "main_comments": main_comments, "sub_replies": sub_replies}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return raw_path


def build_language_mix(rows: list[dict[str, Any]]) -> str:
    counter = Counter(row["language"] for row in rows)
    if not counter:
        return "unknown"
    return "; ".join(f"{language}:{count}" for language, count in counter.most_common())


def main() -> None:
    args = parse_args()
    bvid = extract_bvid(args.video_ref)
    cookie_string = load_cookie_string(args.cookie_file, args.cookie_string)
    
    project_dir = Path(args.project_dir)
    section_dir = project_dir / "section_2_official_video_comments"
    sources_dir = project_dir / "sources"
    
    ensure_csv(section_dir / "video_registry.csv", VIDEO_REGISTRY_HEADER)
    ensure_csv(section_dir / "comment_sample.csv", COMMENT_SAMPLE_HEADER)
    ensure_csv(sources_dir / "source_registry.csv", SOURCE_REGISTRY_HEADER)

    print(f"Fetching metadata for {bvid}...")
    metadata = fetch_video_metadata(bvid, cookie_string)
    oid = metadata.get("aid")
    if not oid:
        raise SystemExit("Failed to extract 'aid' (oid) from video metadata.")

    print(f"Fetching main comments for {bvid} (page_limit={args.max_pages or 'unlimited'}, mode={args.sort_mode})...")
    main_items, visible_total, capture_stop_reason = fetch_main_comments(oid, args.sort_mode, args.max_pages, cookie_string)
    
    sub_replies_by_parent: dict[str, list[dict[str, Any]]] = {}
    if args.max_replies_per_thread > 0:
        print(f"Fetching sub-replies for {len(main_items)} threads (up to {args.max_replies_per_thread} per thread)...")
        for idx, item in enumerate(main_items, start=1):
            root_id = item.get("rpid")
            rcount = item.get("rcount", 0)
            if not root_id or rcount == 0:
                continue
            if idx % 5 == 0:
                print(f"  progress: {idx}/{len(main_items)} threads")
            replies = fetch_sub_replies(oid, root_id, args.max_replies_per_thread, cookie_string)
            if replies:
                sub_replies_by_parent[str(root_id)] = replies

    comment_rows: list[dict[str, Any]] = []
    capture_mode = f"paged_{args.sort_mode}"
    
    for item in main_items:
        comment_rows.append(build_comment_row(item, bvid, True, capture_mode))
        
    for parent_id, replies in sub_replies_by_parent.items():
        for reply in replies:
            comment_rows.append(build_comment_row(reply, bvid, False, capture_mode, parent_id))

    video_url = f"https://www.bilibili.com/video/{bvid}"
    owner = metadata.get("owner", {})
    stat = metadata.get("stat", {})
    
    note_parts = [part for part in [args.notes, f"bilibili_api_capture:{capture_mode}", f"reported_comment_count={stat.get('reply', '')}"] if part]
    notes = "; ".join(note_parts)
    
    registry_row = {
        "video_id": bvid,
        "milestone_id": args.milestone_id,
        "platform": "bilibili",
        "url": video_url,
        "title": metadata.get("title", ""),
        "publish_date": format_timestamp(metadata.get("pubdate", 0)),
        "channel_name": owner.get("name", ""),
        "official_status": args.official_status,
        "content_type": args.content_type,
        "comment_capture_mode": capture_mode,
        "comments_captured": len(comment_rows),
        "comments_visible_total": visible_total,
        "coverage_ratio": f"{(len(main_items) / visible_total):.4f}" if visible_total > 0 else "1.0000",
        "capture_stop_reason": capture_stop_reason,
        "language_mix": build_language_mix(comment_rows),
        "notes": notes,
    }
    
    source_id = f"bili_{bvid}"
    source_row = {
        "source_id": source_id,
        "section_id": "section_2",
        "platform": "bilibili",
        "source_type": "official_video",
        "url": video_url,
        "title": metadata.get("title", ""),
        "author_or_channel": owner.get("name", ""),
        "publish_date": format_timestamp(metadata.get("pubdate", 0)),
        "language": "zh",  # Bilibili default
        "official_status": args.official_status,
        "reliability_score": 5,
        "bias_risk": "medium",
        "access_method": "cookie_scrape" if cookie_string else "anonymous_scrape",
        "capture_status": "success",
        "notes": notes,
    }

    raw_path = write_raw_capture(section_dir, bvid, metadata, main_items, sub_replies_by_parent)
    
    append_unique_rows(section_dir / "video_registry.csv", VIDEO_REGISTRY_HEADER, [registry_row], "video_id")
    written_comments = append_unique_rows(section_dir / "comment_sample.csv", COMMENT_SAMPLE_HEADER, comment_rows, "comment_id")
    append_unique_rows(sources_dir / "source_registry.csv", SOURCE_REGISTRY_HEADER, [source_row], "source_id")
    
    print(
        json.dumps(
            {
                "video_id": bvid,
                "milestone_id": args.milestone_id,
                "comments_written": written_comments,
                "raw_capture": str(raw_path),
                "video_registry": str(section_dir / "video_registry.csv"),
                "comment_sample": str(section_dir / "comment_sample.csv"),
                "source_registry": str(sources_dir / "source_registry.csv"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
