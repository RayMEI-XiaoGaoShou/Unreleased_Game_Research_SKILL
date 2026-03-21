from __future__ import annotations

import argparse
import csv
import json
import random
import re
import time
from collections import Counter
from pathlib import Path
from typing import Any
import importlib

exclusive_file_lock = importlib.import_module("file_lock").exclusive_file_lock

from playwright.sync_api import sync_playwright

VIDEO_REGISTRY_HEADER = [
    "video_id", "milestone_id", "platform", "url", "title", "publish_date", 
    "channel_name", "official_status", "content_type", "comment_capture_mode", 
    "comments_captured", "comments_visible_total", "coverage_ratio", 
    "capture_stop_reason", "language_mix", "notes"
]

COMMENT_SAMPLE_HEADER = [
    "comment_id", "video_id", "platform", "comment_time", "author_name", 
    "text_original", "text_normalized", "language", "likes", "replies", 
    "is_top_comment", "is_spam_or_noise", "sentiment_label", "topic_label", "confidence_note"
]

SOURCE_REGISTRY_HEADER = [
    "source_id", "section_id", "platform", "source_type", "url", "title", 
    "author_or_channel", "publish_date", "language", "official_status", 
    "reliability_score", "bias_risk", "access_method", "capture_status", "notes"
]

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect Bilibili official video comments using Playwright.")
    parser.add_argument("video_ref", help="Bilibili video BV ID or URL")
    parser.add_argument("--project-dir", required=True, help="Path to an initialized project directory")
    parser.add_argument("--milestone-id", required=True, help="Milestone identifier for this video")
    parser.add_argument("--cookie-file", help="Path to JSON file containing Bilibili cookies")
    parser.add_argument("--cookie-string", help="Raw cookie string for Bilibili requests")
    parser.add_argument("--max-pages", type=int, default=0, help="Maximum comment pages to fetch")
    parser.add_argument("--max-replies-per-thread", type=int, default=20, help="Maximum replies to fetch per top-level comment (limited by embedded)")
    parser.add_argument("--sort-mode", default="hot", choices=["hot", "time"], help="Sort mode for main comments")
    parser.add_argument("--content-type", default="official_video", help="Artifact content type label")
    parser.add_argument("--official-status", default="official", help="Source official_status field")
    parser.add_argument("--notes", default="", help="Extra note stored in registry")
    return parser.parse_args()

def extract_bvid(video_ref: str) -> str:
    if re.fullmatch(r"BV[1-9A-HJ-NP-Za-km-z]{10}", video_ref, re.IGNORECASE):
        return video_ref
    for part in video_ref.split("/"):
        if re.fullmatch(r"BV[1-9A-HJ-NP-Za-km-z]{10}", part, re.IGNORECASE):
            return part
    raise SystemExit(f"Could not parse a Bilibili BV ID from: {video_ref}")

def parse_cookies_for_playwright(cookie_string: str) -> list[dict[str, str]]:
    if not cookie_string:
        return []
    pw_cookies = []
    # If the cookie string is actually JSON
    if "{" in cookie_string and "}" in cookie_string:
        try:
            data = json.loads(cookie_string)
            for k, v in data.items():
                pw_cookies.append({"name": k, "value": str(v), "domain": ".bilibili.com", "path": "/"})
            return pw_cookies
        except json.JSONDecodeError:
            pass
    # If it's standard foo=bar;
    for pair in cookie_string.split(";"):
        if "=" in pair:
            k, v = pair.split("=", 1)
            pw_cookies.append({"name": k.strip(), "value": v.strip(), "domain": ".bilibili.com", "path": "/"})
    return pw_cookies

def load_cookie_string(cookie_file: str | None, cookie_string: str | None) -> str:
    if cookie_string:
        return cookie_string
    if cookie_file:
        path = Path(cookie_file)
        if not path.exists():
            raise SystemExit(f"Cookie file not found: {path}")
        return path.read_text(encoding="utf-8")
    return ""

def normalize_text(text: str) -> str:
    return " ".join(text.split())

def detect_language(text: str) -> str:
    if re.search(r"[\u4e00-\u9fff]", text): return "zh"
    if re.search(r"[\u3040-\u30ff]", text): return "ja"
    if re.search(r"[\uac00-\ud7af]", text): return "ko"
    if re.search(r"[A-Za-z]", text): return "en"
    return "unknown"

def is_spam_or_noise(text: str) -> bool:
    normalized = normalize_text(text)
    if not normalized or len(normalized) <= 1: return True
    if "http://" in normalized or "https://" in normalized: return True
    return False

def format_timestamp(ts: int) -> str:
    import datetime
    return datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc).isoformat()

def build_comment_row(item: dict[str, Any], bvid: str, is_top: bool, capture_mode: str, parent_id: str | None = None) -> dict[str, Any]:
    content = item.get("content", {})
    text_original = content.get("message", "")
    member = item.get("member", {})
    note = f"playwright_intercept:{capture_mode}"
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
    if not path.exists(): return set()
    with path.open("r", newline="", encoding="utf-8") as handle:
        return {row[key_field] for row in csv.DictReader(handle) if row.get(key_field)}

def append_unique_rows(path: Path, header: list[str], rows: list[dict[str, Any]], key_field: str) -> int:
    with exclusive_file_lock(path):
        ensure_csv(path, header)
        existing = load_existing_keys(path, key_field)
        written = 0
        with path.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=header)
            for row in rows:
                key = str(row[key_field])
                if key not in existing:
                    writer.writerow(row)
                    existing.add(key)
                    written += 1
    return written

def write_raw_capture(section_dir: Path, bvid: str, metadata: dict[str, Any], main_comments: list[dict[str, Any]], sub_replies: dict[str, list[dict[str, Any]]]) -> Path:
    raw_dir = section_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / f"bilibili_{bvid}.json"
    raw_path.write_text(json.dumps({"metadata": metadata, "main_comments": main_comments, "sub_replies": sub_replies}, ensure_ascii=False, indent=2), encoding="utf-8")
    return raw_path

def build_language_mix(rows: list[dict[str, Any]]) -> str:
    counter = Counter(row["language"] for row in rows)
    return "; ".join(f"{language}:{count}" for language, count in counter.most_common()) if counter else "unknown"

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

    target_url = f"https://www.bilibili.com/video/{bvid}/"
    captured_responses = []
    metadata = {}
    
    print(f"Starting Playwright scraper for {bvid}...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        context.add_cookies(parse_cookies_for_playwright(cookie_string))
        page = context.new_page()

        def handle_response(response):
            nonlocal metadata
            try:
                # Capture video metadata
                if "/x/web-interface/view" in response.url and "interaction" not in response.url:
                    data = response.json()
                    if data.get("code") == 0 and "data" in data:
                        # Only assign once
                        if not metadata:
                            metadata = data["data"]

                # Capture comment pages
                if "/x/v2/reply" in response.url and "main" in response.url and response.request.resource_type in ["fetch", "xhr"]:
                    data = response.json()
                    if data.get("code") == 0:
                        captured_responses.append(data)
            except Exception:
                pass

        page.on("response", handle_response)
        page.goto(target_url, wait_until="domcontentloaded")
        page.wait_for_timeout(3000)

        # Switch sorting to 'time' if needed
        if args.sort_mode == "time":
            try:
                # Try to click the "最新" (latest) sort button in the Bilibili comment UI
                sort_btn = page.locator("text='最新'").first
                if sort_btn:
                    sort_btn.click(timeout=3000)
                    page.wait_for_timeout(3000)
                    captured_responses.clear() # Clear the initial "hot" load
            except Exception as e:
                print("Failed to switch sort mode to time, defaulting to original sort.", e)

        print("Scrolling down to collect comments...")
        target_pages = args.max_pages if args.max_pages > 0 else 100
        last_length = 0
        retries = 0
        while len(captured_responses) < target_pages and retries < 5:
            page.mouse.wheel(0, 3000)
            page.wait_for_timeout(2000)
            if len(captured_responses) > last_length:
                last_length = len(captured_responses)
                retries = 0
                print(f"Collected {last_length} comment payloads...")
            else:
                retries += 1

        browser.close()

    if not metadata:
        metadata = {"title": bvid, "pubdate": int(time.time()), "owner": {"name": "Bilibili Omitted"}}
        print("Warning: Metadata could not be intercepted. Using placeholder.")
        
    aid = metadata.get("aid", 0)

    main_items = []
    sub_replies_by_parent = {}
    total_count = 0
    
    # Process intercepted JSONs
    seen_rpid = set()
    for resp in captured_responses:
        rep_data = resp.get("data", {})
        if "page" in rep_data and "count" in rep_data["page"]:
            total_count = max(total_count, int(rep_data["page"]["count"]))
            
        replies = rep_data.get("replies") or []
        for r in replies:
            rpid = r.get("rpid")
            if rpid and rpid not in seen_rpid:
                main_items.append(r)
                seen_rpid.add(rpid)
                # Pull embedded sub-replies first
                embedded = r.get("replies") or []
                if embedded:
                    sub_replies_by_parent[str(rpid)] = embedded

    print(f"Captured {len(main_items)} main comments. Now fetching deep sub-replies for hot threads...")
    
    # Fetch deep sub-replies using Playwright context
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        context.add_cookies(parse_cookies_for_playwright(cookie_string))
        
        deep_fetch_count = 0
        for item in main_items:
            # If the comment has more than 3 replies and we have a valid aid
            if aid and item.get("rcount", 0) > 3:
                rpid = item["rpid"]
                rcount = item["rcount"]
                max_sub_pages = min(3, (rcount + 19) // 20) # Fetch up to 3 pages (60 subreplies) per top comment
                
                fetched_for_thread = []
                for pn in range(1, max_sub_pages + 1):
                    deep_url = f"https://api.bilibili.com/x/v2/reply/reply?oid={aid}&type=1&root={rpid}&pn={pn}&ps=20"
                    try:
                        resp = context.request.get(deep_url)
                        if resp.ok:
                            js = resp.json()
                            if js.get("code") == 0:
                                page_replies = js.get("data", {}).get("replies") or []
                                fetched_for_thread.extend(page_replies)
                                deep_fetch_count += len(page_replies)
                    except Exception as e:
                        print(f"Failed to fetch deep replies for {rpid}: {e}")
                    time.sleep(1.0) # rate limit
                
                if fetched_for_thread:
                    # Deduplicate with embedded
                    existing_ids = {str(r["rpid"]) for r in sub_replies_by_parent.get(str(rpid), [])}
                    for r in fetched_for_thread:
                        if str(r.get("rpid")) not in existing_ids:
                            sub_replies_by_parent.setdefault(str(rpid), []).append(r)
                            existing_ids.add(str(r.get("rpid")))
                            
        print(f"Deep fetch complete. Acquired {deep_fetch_count} active sub-replies.")
        browser.close()

    comment_rows = []
    capture_mode = f"playwright_{args.sort_mode}"
    for item in main_items:
        comment_rows.append(build_comment_row(item, bvid, True, capture_mode))
    for parent_id, replies in sub_replies_by_parent.items():
        for reply in replies[:args.max_replies_per_thread]:
            comment_rows.append(build_comment_row(reply, bvid, False, capture_mode, parent_id))

    owner = metadata.get("owner", {})
    notes = "; ".join([args.notes, f"playwright_capture:{capture_mode}", "embedded_replies_only"])
    
    registry_row = {
        "video_id": bvid, "milestone_id": args.milestone_id, "platform": "bilibili",
        "url": target_url, "title": metadata.get("title", ""),
        "publish_date": format_timestamp(metadata.get("pubdate", 0)),
        "channel_name": owner.get("name", ""), "official_status": args.official_status,
        "content_type": args.content_type, "comment_capture_mode": capture_mode,
        "comments_captured": len(comment_rows), "comments_visible_total": total_count,
        "coverage_ratio": f"{(len(main_items) / total_count):.4f}" if total_count > 0 else "1.0000",
        "capture_stop_reason": "playwright_pages_reached" if len(captured_responses) >= args.max_pages and args.max_pages > 0 else "end_of_scroll",
        "language_mix": build_language_mix(comment_rows), "notes": notes,
    }
    
    source_row = {
        "source_id": f"bili_{bvid}", "section_id": "section_2", "platform": "bilibili",
        "source_type": "official_video", "url": target_url, "title": metadata.get("title", ""),
        "author_or_channel": owner.get("name", ""), "publish_date": format_timestamp(metadata.get("pubdate", 0)),
        "language": "zh", "official_status": args.official_status,
        "reliability_score": 5, "bias_risk": "medium", 
        "access_method": "playwright_intercept", "capture_status": "success", "notes": notes,
    }

    raw_path = write_raw_capture(section_dir, bvid, metadata, main_items, sub_replies_by_parent)
    append_unique_rows(section_dir / "video_registry.csv", VIDEO_REGISTRY_HEADER, [registry_row], "video_id")
    written_comments = append_unique_rows(section_dir / "comment_sample.csv", COMMENT_SAMPLE_HEADER, comment_rows, "comment_id")
    append_unique_rows(sources_dir / "source_registry.csv", SOURCE_REGISTRY_HEADER, [source_row], "source_id")
    
    print(json.dumps({
        "video_id": bvid, "milestone_id": args.milestone_id,
        "comments_written": written_comments, "raw_capture": str(raw_path),
    }, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
