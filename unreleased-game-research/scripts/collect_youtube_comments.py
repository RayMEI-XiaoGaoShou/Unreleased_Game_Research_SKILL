from __future__ import annotations

import argparse
import csv
import json
import os
import re
from collections import Counter
from pathlib import Path
from typing import Any
from urllib import error, parse, request
import importlib

exclusive_file_lock = importlib.import_module("file_lock").exclusive_file_lock


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

EMPTY_SENTIMENT_SUMMARY_HEADER = [
    "video_id",
    "milestone_id",
    "positive_count",
    "neutral_count",
    "negative_count",
    "positive_ratio",
    "neutral_ratio",
    "negative_ratio",
    "positive_like_weight",
    "negative_like_weight",
    "notes",
]

EMPTY_TOPIC_SUMMARY_HEADER = [
    "video_id",
    "milestone_id",
    "topic_label",
    "mention_count",
    "mention_ratio",
    "positive_ratio_within_topic",
    "negative_ratio_within_topic",
    "avg_likes",
    "representative_evidence_id",
]

EMPTY_MILESTONE_DELTA_HEADER = [
    "from_milestone",
    "to_milestone",
    "topic_label",
    "direction",
    "observed_change",
    "likely_driver",
    "confidence_level",
    "supporting_evidence_ids",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect YouTube video metadata and comments for Section 2 artifacts.")
    parser.add_argument("video_ref", help="YouTube video ID or URL")
    parser.add_argument("--project-dir", required=True, help="Path to an initialized project directory")
    parser.add_argument("--milestone-id", required=True, help="Milestone identifier for this video")
    parser.add_argument("--api-key", help="YouTube Data API v3 key; defaults to YOUTUBE_API_KEY")
    parser.add_argument(
        "--capture-mode",
        default="top_plus_recent",
        choices=["full_capture", "top_plus_recent", "stratified_sample"],
        help="Comment capture strategy",
    )
    parser.add_argument("--max-comments", type=int, default=0, help="Maximum top-level comments to persist; 0 means no explicit cap")
    parser.add_argument("--include-replies", action="store_true", help="Also fetch reply comments via comments.list")
    parser.add_argument(
        "--max-replies-per-thread",
        type=int,
        default=100,
        help="Maximum replies to persist for each top-level comment when --include-replies is set",
    )
    parser.add_argument("--content-type", default="official_video", help="Artifact content type label")
    parser.add_argument("--official-status", default="official", help="Source official_status field")
    parser.add_argument("--notes", default="", help="Extra note stored in registry outputs")
    return parser.parse_args()


def extract_video_id(video_ref: str) -> str:
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", video_ref):
        return video_ref

    parsed = parse.urlparse(video_ref)
    if parsed.netloc in {"youtu.be", "www.youtu.be"}:
        candidate = parsed.path.strip("/")
        if re.fullmatch(r"[A-Za-z0-9_-]{11}", candidate):
            return candidate

    if "youtube.com" in parsed.netloc or "youtube-nocookie.com" in parsed.netloc:
        qs = parse.parse_qs(parsed.query)
        candidate = qs.get("v", [""])[0]
        if re.fullmatch(r"[A-Za-z0-9_-]{11}", candidate):
            return candidate
        path_parts = [part for part in parsed.path.split("/") if part]
        if len(path_parts) >= 2 and path_parts[0] in {"embed", "shorts", "live"}:
            candidate = path_parts[1]
            if re.fullmatch(r"[A-Za-z0-9_-]{11}", candidate):
                return candidate

    raise SystemExit(f"Could not parse a YouTube video ID from: {video_ref}")


def get_api_key(explicit_key: str | None) -> str:
    api_key = explicit_key or os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        raise SystemExit("Missing YouTube API key. Pass --api-key or set YOUTUBE_API_KEY.")
    return api_key


def api_request(endpoint: str, params: dict[str, Any], api_key: str) -> dict[str, Any]:
    query = params.copy()
    query["key"] = api_key
    url = f"https://www.googleapis.com/youtube/v3/{endpoint}?{parse.urlencode(query)}"
    try:
        with request.urlopen(url) as response:
            return json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"YouTube API request failed ({exc.code}): {body}") from exc
    except error.URLError as exc:
        raise SystemExit(f"Network error while calling YouTube API: {exc.reason}") from exc


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


def fetch_video_metadata(video_id: str, api_key: str) -> dict[str, Any]:
    payload = api_request(
        "videos",
        {
            "part": "snippet,statistics",
            "id": video_id,
            "maxResults": 1,
        },
        api_key,
    )
    items = payload.get("items", [])
    if not items:
        raise SystemExit(f"No YouTube video metadata found for video ID: {video_id}")
    return items[0]


def fetch_comment_pages(video_id: str, api_key: str, order: str, limit: int) -> tuple[list[dict[str, Any]], str]:
    rows: list[dict[str, Any]] = []
    page_token = ""
    unlimited = limit <= 0
    stop_reason = "complete"
    while unlimited or len(rows) < limit:
        batch_size = 100 if unlimited else min(100, limit - len(rows))
        params = {
            "part": "snippet",
            "videoId": video_id,
            "maxResults": batch_size,
            "textFormat": "plainText",
            "order": order,
        }
        if page_token:
            params["pageToken"] = page_token
        payload = api_request("commentThreads", params, api_key)
        items = payload.get("items", [])
        if not items:
            stop_reason = "no_more_threads"
            break
        rows.extend(items)
        page_token = payload.get("nextPageToken", "")
        if not page_token:
            stop_reason = "exhausted_api_pages"
            break
    return (rows if unlimited else rows[:limit], stop_reason)


def fetch_reply_pages(parent_id: str, api_key: str, limit: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    page_token = ""
    while len(rows) < limit:
        batch_size = min(100, limit - len(rows))
        params = {
            "part": "snippet",
            "parentId": parent_id,
            "maxResults": batch_size,
            "textFormat": "plainText",
        }
        if page_token:
            params["pageToken"] = page_token
        payload = api_request("comments", params, api_key)
        items = payload.get("items", [])
        if not items:
            break
        rows.extend(items)
        page_token = payload.get("nextPageToken", "")
        if not page_token:
            break
    return rows[:limit]


def fetch_comments(video_id: str, api_key: str, capture_mode: str, max_comments: int) -> tuple[list[dict[str, Any]], str, str]:
    if capture_mode == "full_capture":
        items, stop_reason = fetch_comment_pages(video_id, api_key, "time", max_comments)
        return items, "time", stop_reason

    if max_comments <= 0:
        max_comments = 500

    recent_limit = max(1, max_comments // 2)
    top_limit = max_comments - recent_limit
    if capture_mode == "stratified_sample":
        recent_limit = max(1, max_comments // 3)
        top_limit = max(1, max_comments - recent_limit)

    combined: dict[str, dict[str, Any]] = {}
    orders_used: list[str] = []
    stop_reason = "mixed_sample_cap"
    for order, limit in (("relevance", top_limit), ("time", recent_limit)):
        if limit <= 0:
            continue
        orders_used.append(order)
        items, _ = fetch_comment_pages(video_id, api_key, order, limit)
        for item in items:
            comment_id = item["snippet"]["topLevelComment"]["id"]
            combined.setdefault(comment_id, item)
            combined[comment_id]["_capture_order"] = order
    return list(combined.values())[:max_comments], ",".join(orders_used), stop_reason


def comment_row_from_item(item: dict[str, Any], video_id: str) -> dict[str, Any]:
    snippet = item["snippet"]
    top = snippet["topLevelComment"]["snippet"]
    text_original = top.get("textDisplay") or top.get("textOriginal") or ""
    text_normalized = normalize_text(text_original)
    capture_order = item.get("_capture_order", "time")
    return {
        "comment_id": item["snippet"]["topLevelComment"]["id"],
        "video_id": video_id,
        "platform": "youtube",
        "comment_time": top.get("publishedAt", ""),
        "author_name": top.get("authorDisplayName", ""),
        "text_original": text_original,
        "text_normalized": text_normalized,
        "language": detect_language(text_original),
        "likes": top.get("likeCount", 0),
        "replies": snippet.get("totalReplyCount", 0),
        "is_top_comment": "true" if capture_order == "relevance" else "false",
        "is_spam_or_noise": "true" if is_spam_or_noise(text_original) else "false",
        "sentiment_label": "",
        "topic_label": "",
        "confidence_note": f"captured_via_youtube_api:{capture_order}",
    }


def comment_row_from_reply(item: dict[str, Any], video_id: str, parent_id: str) -> dict[str, Any]:
    snippet = item["snippet"]
    text_original = snippet.get("textDisplay") or snippet.get("textOriginal") or ""
    text_normalized = normalize_text(text_original)
    return {
        "comment_id": item.get("id", ""),
        "video_id": video_id,
        "platform": "youtube",
        "comment_time": snippet.get("publishedAt", ""),
        "author_name": snippet.get("authorDisplayName", ""),
        "text_original": text_original,
        "text_normalized": text_normalized,
        "language": detect_language(text_original),
        "likes": snippet.get("likeCount", 0),
        "replies": 0,
        "is_top_comment": "false",
        "is_spam_or_noise": "true" if is_spam_or_noise(text_original) else "false",
        "sentiment_label": "",
        "topic_label": "",
        "confidence_note": f"captured_via_youtube_api:reply; reply_to:{parent_id}",
    }


def build_language_mix(rows: list[dict[str, Any]]) -> str:
    counter = Counter(row["language"] for row in rows)
    if not counter:
        return "unknown"
    return "; ".join(f"{language}:{count}" for language, count in counter.most_common())


def fetch_replies_for_threads(
    thread_items: list[dict[str, Any]],
    api_key: str,
    max_replies_per_thread: int,
) -> dict[str, list[dict[str, Any]]]:
    replies_by_parent: dict[str, list[dict[str, Any]]] = {}
    if max_replies_per_thread <= 0:
        return replies_by_parent
    for item in thread_items:
        parent_id = item["snippet"]["topLevelComment"]["id"]
        total_reply_count = item["snippet"].get("totalReplyCount", 0)
        if total_reply_count <= 0:
            continue
        replies_by_parent[parent_id] = fetch_reply_pages(parent_id, api_key, max_replies_per_thread)
    return replies_by_parent


def build_comment_rows(
    thread_items: list[dict[str, Any]],
    replies_by_parent: dict[str, list[dict[str, Any]]],
    video_id: str,
) -> list[dict[str, Any]]:
    rows = [comment_row_from_item(item, video_id) for item in thread_items]
    for parent_id, reply_items in replies_by_parent.items():
        for reply_item in reply_items:
            rows.append(comment_row_from_reply(reply_item, video_id, parent_id))
    return rows


def join_notes(*parts: str) -> str:
    return "; ".join(part for part in parts if part)


def video_registry_row(
    video_id: str,
    milestone_id: str,
    video_url: str,
    metadata: dict[str, Any],
    official_status: str,
    content_type: str,
    capture_mode: str,
    comments_captured: int,
    comments_visible_total: int,
    coverage_ratio: str,
    capture_stop_reason: str,
    language_mix: str,
    notes: str,
) -> dict[str, Any]:
    snippet = metadata.get("snippet", {})
    statistics = metadata.get("statistics", {})
    note_parts = [part for part in [notes, f"reported_comment_count={statistics.get('commentCount', '')}"] if part]
    return {
        "video_id": video_id,
        "milestone_id": milestone_id,
        "platform": "youtube",
        "url": video_url,
        "title": snippet.get("title", ""),
        "publish_date": snippet.get("publishedAt", ""),
        "channel_name": snippet.get("channelTitle", ""),
        "official_status": official_status,
        "content_type": content_type,
        "comment_capture_mode": capture_mode,
        "comments_captured": comments_captured,
        "comments_visible_total": comments_visible_total,
        "coverage_ratio": coverage_ratio,
        "capture_stop_reason": capture_stop_reason,
        "language_mix": language_mix,
        "notes": "; ".join(note_parts),
    }


def source_registry_row(
    source_id: str,
    video_url: str,
    metadata: dict[str, Any],
    official_status: str,
    notes: str,
) -> dict[str, Any]:
    snippet = metadata.get("snippet", {})
    statistics = metadata.get("statistics", {})
    default_language = snippet.get("defaultAudioLanguage") or snippet.get("defaultLanguage") or "unknown"
    note_parts = [part for part in [notes, "youtube_api_capture", f"reported_comment_count={statistics.get('commentCount', '')}"] if part]
    return {
        "source_id": source_id,
        "section_id": "section_2",
        "platform": "youtube",
        "source_type": "official_video",
        "url": video_url,
        "title": snippet.get("title", ""),
        "author_or_channel": snippet.get("channelTitle", ""),
        "publish_date": snippet.get("publishedAt", ""),
        "language": default_language,
        "official_status": official_status,
        "reliability_score": 5,
        "bias_risk": "medium",
        "access_method": "api",
        "capture_status": "success",
        "notes": "; ".join(note_parts),
    }


def ensure_section_files(section_dir: Path) -> None:
    ensure_csv(section_dir / "video_registry.csv", VIDEO_REGISTRY_HEADER)
    ensure_csv(section_dir / "comment_sample.csv", COMMENT_SAMPLE_HEADER)
    ensure_csv(section_dir / "sentiment_summary.csv", EMPTY_SENTIMENT_SUMMARY_HEADER)
    ensure_csv(section_dir / "topic_summary.csv", EMPTY_TOPIC_SUMMARY_HEADER)
    ensure_csv(section_dir / "milestone_delta.csv", EMPTY_MILESTONE_DELTA_HEADER)


def write_raw_capture(
    section_dir: Path,
    video_id: str,
    metadata: dict[str, Any],
    comments: list[dict[str, Any]],
    replies_by_parent: dict[str, list[dict[str, Any]]],
) -> Path:
    raw_dir = section_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / f"youtube_{video_id}.json"
    raw_path.write_text(
        json.dumps({"metadata": metadata, "comments": comments, "replies_by_parent": replies_by_parent}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return raw_path


def run() -> None:
    args = parse_args()
    api_key = get_api_key(args.api_key)
    video_id = extract_video_id(args.video_ref)
    project_dir = Path(args.project_dir)
    section_dir = project_dir / "section_2_official_video_comments"
    sources_dir = project_dir / "sources"

    ensure_section_files(section_dir)
    ensure_csv(sources_dir / "source_registry.csv", SOURCE_REGISTRY_HEADER)

    metadata = fetch_video_metadata(video_id, api_key)
    comment_items, actual_capture_mode, capture_stop_reason = fetch_comments(video_id, api_key, args.capture_mode, args.max_comments)
    replies_by_parent: dict[str, list[dict[str, Any]]] = {}
    if args.include_replies:
        replies_by_parent = fetch_replies_for_threads(comment_items, api_key, args.max_replies_per_thread)
    comment_rows = build_comment_rows(comment_items, replies_by_parent, video_id)
    language_mix = build_language_mix(comment_rows)
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    statistics = metadata.get("statistics", {})
    visible_total = int(statistics.get("commentCount", 0) or 0)
    coverage_ratio = f"{(len(comment_items) / visible_total):.4f}" if visible_total > 0 else "1.0000"
    notes = join_notes(
        args.notes,
        "includes_replies" if args.include_replies else "top_level_only",
        f"max_replies_per_thread={args.max_replies_per_thread}" if args.include_replies else "",
    )

    registry_row = video_registry_row(
        video_id=video_id,
        milestone_id=args.milestone_id,
        video_url=video_url,
        metadata=metadata,
        official_status=args.official_status,
        content_type=args.content_type,
        capture_mode=actual_capture_mode or args.capture_mode,
        comments_captured=len(comment_rows),
        comments_visible_total=visible_total,
        coverage_ratio=coverage_ratio,
        capture_stop_reason=capture_stop_reason,
        language_mix=language_mix,
        notes=notes,
    )

    source_id = f"yt_{video_id}"
    source_row = source_registry_row(source_id, video_url, metadata, args.official_status, notes)
    raw_path = write_raw_capture(section_dir, video_id, metadata, comment_items, replies_by_parent)

    append_unique_rows(section_dir / "video_registry.csv", VIDEO_REGISTRY_HEADER, [registry_row], "video_id")
    written_comments = append_unique_rows(section_dir / "comment_sample.csv", COMMENT_SAMPLE_HEADER, comment_rows, "comment_id")
    append_unique_rows(sources_dir / "source_registry.csv", SOURCE_REGISTRY_HEADER, [source_row], "source_id")

    print(
        json.dumps(
            {
                "video_id": video_id,
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
    run()
