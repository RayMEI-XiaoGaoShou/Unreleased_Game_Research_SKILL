"""
Bilibili 评论采集器 V2 — 纯 HTTP + WBI 签名
=============================================
无需 Playwright / 无需浏览器，直接调用 B 站 REST API。
需要有效的 Cookie（SESSDATA + bili_jct + buvid3 + buvid4）。

用法:
  python collect_bilibili_comments_v2.py BV1bb6gByEjg \
      --project-dir "path/to/project" \
      --milestone-id reveal_cn \
      --cookie-file "path/to/bilibili_cookies.json" \
      --max-pages 20

WBI 签名算法来源: 公开技术社区（掘金、CSDN 等），非逆向工程产物。
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
import datetime
import importlib
from collections import Counter
from functools import reduce
from hashlib import md5
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import requests

HTTP_TIMEOUT = 15  # seconds per request

exclusive_file_lock = importlib.import_module("file_lock").exclusive_file_lock

# ─────────────────────────────────────────────
# CSV headers (same as v1 for compatibility)
# ─────────────────────────────────────────────

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

# ─────────────────────────────────────────────
# WBI 签名
# ─────────────────────────────────────────────

MIXIN_KEY_ENC_TAB = [
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35, 27, 43, 5, 49,
    33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13, 37, 48, 7, 16, 24, 55, 40,
    61, 26, 17, 0, 1, 60, 51, 30, 4, 22, 25, 54, 21, 56, 59, 6, 63, 57, 62,
    11, 36, 20, 34, 44, 52
]


def get_mixin_key(img_key: str, sub_key: str) -> str:
    """将 img_key + sub_key 按映射表重排后截取前 32 位"""
    orig = img_key + sub_key
    return reduce(lambda s, i: s + orig[i], MIXIN_KEY_ENC_TAB, "")[:32]


def wbi_sign(params: dict, img_key: str, sub_key: str) -> dict:
    """对请求参数进行 WBI 签名，返回附带 wts + w_rid 的参数字典"""
    mixin_key = get_mixin_key(img_key, sub_key)
    params["wts"] = round(time.time())
    # 按 key 字母排序
    params = dict(sorted(params.items()))
    # 过滤特殊字符
    params = {
        k: "".join(filter(lambda c: c not in "!'()*", str(v)))
        for k, v in params.items()
    }
    query = urlencode(params)
    w_rid = md5((query + mixin_key).encode()).hexdigest()
    params["w_rid"] = w_rid
    return params


# ─────────────────────────────────────────────
# HTTP 会话
# ─────────────────────────────────────────────

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Referer": "https://www.bilibili.com/",
    "Origin": "https://www.bilibili.com",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


def build_session(cookie_dict: dict) -> requests.Session:
    """构建带 Cookie 的 requests 会话"""
    sess = requests.Session()
    sess.headers.update(DEFAULT_HEADERS)
    for k, v in cookie_dict.items():
        sess.cookies.set(k, str(v), domain=".bilibili.com")
    return sess


def fetch_wbi_keys(sess: requests.Session) -> tuple[str, str]:
    """从 /x/web-interface/nav 获取 img_key 和 sub_key"""
    resp = sess.get("https://api.bilibili.com/x/web-interface/nav", timeout=HTTP_TIMEOUT)
    data = resp.json()
    if data.get("code") != 0:
        print(f"Warning: nav API returned code {data.get('code')}, attempting without login keys")
        # Fallback: try without cookies
        resp2 = requests.get("https://api.bilibili.com/x/web-interface/nav", headers=DEFAULT_HEADERS, timeout=HTTP_TIMEOUT)
        data = resp2.json()

    wbi_img = data.get("data", {}).get("wbi_img", {})
    img_url = wbi_img.get("img_url", "")
    sub_url = wbi_img.get("sub_url", "")

    img_key = img_url.rsplit("/", 1)[-1].split(".")[0] if img_url else ""
    sub_key = sub_url.rsplit("/", 1)[-1].split(".")[0] if sub_url else ""

    if not img_key or not sub_key:
        raise SystemExit("Failed to obtain WBI keys from Bilibili. Check cookie validity.")

    print(f"WBI keys obtained: img_key={img_key[:8]}..., sub_key={sub_key[:8]}...")
    return img_key, sub_key


# ─────────────────────────────────────────────
# 视频信息
# ─────────────────────────────────────────────

def fetch_video_info(sess: requests.Session, bvid: str, img_key: str, sub_key: str) -> dict:
    """获取视频元数据（标题、aid、发布时间等）"""
    params = wbi_sign({"bvid": bvid}, img_key, sub_key)
    resp = sess.get("https://api.bilibili.com/x/web-interface/view", params=params, timeout=HTTP_TIMEOUT)
    data = resp.json()
    if data.get("code") != 0:
        print(f"Warning: video info API returned code {data.get('code')}: {data.get('message')}")
        return {"aid": 0, "title": bvid, "pubdate": int(time.time()), "owner": {"name": "unknown"}}
    return data["data"]


# ─────────────────────────────────────────────
# 评论采集
# ─────────────────────────────────────────────

def fetch_comments_page(
    sess: requests.Session,
    oid: int,
    next_offset: int,
    mode: int,
    img_key: str,
    sub_key: str,
) -> dict:
    """
    调用 /x/v2/reply/main 获取一页评论
    mode: 2=按时间, 3=按热度
    """
    params = {
        "oid": oid,
        "type": 1,       # 1 = 视频
        "mode": mode,
        "next": next_offset,
    }
    signed = wbi_sign(params, img_key, sub_key)
    resp = sess.get("https://api.bilibili.com/x/v2/reply/main", params=signed, timeout=HTTP_TIMEOUT)
    return resp.json()


def fetch_sub_replies(
    sess: requests.Session,
    oid: int,
    root_rpid: int,
    page_num: int,
    img_key: str,
    sub_key: str,
) -> dict:
    """获取某条主评论下的子评论（分页）"""
    params = {
        "oid": oid,
        "type": 1,
        "root": root_rpid,
        "pn": page_num,
        "ps": 20,
    }
    signed = wbi_sign(params, img_key, sub_key)
    resp = sess.get("https://api.bilibili.com/x/v2/reply/reply", params=signed, timeout=HTTP_TIMEOUT)
    return resp.json()


def collect_all_comments(
    sess: requests.Session,
    oid: int,
    img_key: str,
    sub_key: str,
    max_pages: int = 50,
    sort_mode: str = "hot",
    max_sub_pages: int = 3,
    delay: float = 1.5,
) -> tuple[list[dict], dict[str, list[dict]], int]:
    """
    采集全部评论，返回 (main_comments, sub_replies_by_parent, total_count)
    """
    mode = 3 if sort_mode == "hot" else 2
    main_comments: list[dict] = []
    sub_replies_by_parent: dict[str, list[dict]] = {}
    seen_rpid: set[int] = set()
    total_count = 0
    next_offset = 0

    for page_idx in range(max_pages):
        print(f"  Fetching main comments page {page_idx + 1} (next={next_offset})...", flush=True)
        data = fetch_comments_page(sess, oid, next_offset, mode, img_key, sub_key)

        if data.get("code") != 0:
            print(f"  API error on page {page_idx + 1}: code={data.get('code')}, msg={data.get('message')}")
            if data.get("code") == -412:
                print("  Rate limited! Waiting 30 seconds...")
                time.sleep(30)
                continue
            break

        cursor = data.get("data", {}).get("cursor", {})
        replies = data.get("data", {}).get("replies") or []
        total_count = max(total_count, cursor.get("all_count", 0))

        if not replies:
            print(f"  No more replies on page {page_idx + 1}. Stopping.")
            break

        for item in replies:
            rpid = item.get("rpid")
            if rpid and rpid not in seen_rpid:
                main_comments.append(item)
                seen_rpid.add(rpid)
                # 保存内嵌的子评论
                embedded = item.get("replies") or []
                if embedded:
                    sub_replies_by_parent[str(rpid)] = list(embedded)

        next_offset = cursor.get("next", 0)
        is_end = cursor.get("is_end", False)
        print(f"    Got {len(replies)} comments (total main so far: {len(main_comments)}, is_end={is_end})")

        if is_end:
            print("  Cursor reports is_end=True. Done with main comments.")
            break

        time.sleep(delay + (page_idx % 3) * 0.5)  # 变速延迟

    # 采集深度子评论
    hot_threads = [c for c in main_comments if c.get("rcount", 0) > 3]
    if hot_threads:
        print(f"\nFetching deep sub-replies for {len(hot_threads)} hot threads...")
        for idx, item in enumerate(hot_threads):
            rpid = item["rpid"]
            rcount = item.get("rcount", 0)
            pages_needed = min(max_sub_pages, (rcount + 19) // 20)
            fetched = []
            for pn in range(1, pages_needed + 1):
                try:
                    sub_data = fetch_sub_replies(sess, oid, rpid, pn, img_key, sub_key)
                    if sub_data.get("code") == 0:
                        page_replies = sub_data.get("data", {}).get("replies") or []
                        fetched.extend(page_replies)
                    elif sub_data.get("code") == -412:
                        print(f"    Rate limited on sub-reply fetch. Waiting 30s...")
                        time.sleep(30)
                except Exception as e:
                    print(f"    Error fetching sub-replies for {rpid}: {e}")
                time.sleep(delay)

            if fetched:
                existing_ids = {str(r["rpid"]) for r in sub_replies_by_parent.get(str(rpid), [])}
                for r in fetched:
                    if str(r.get("rpid")) not in existing_ids:
                        sub_replies_by_parent.setdefault(str(rpid), []).append(r)
                        existing_ids.add(str(r.get("rpid")))

            if (idx + 1) % 10 == 0:
                print(f"    Progress: {idx + 1}/{len(hot_threads)} threads processed")

    return main_comments, sub_replies_by_parent, total_count


# ─────────────────────────────────────────────
# 数据处理（复用 v1 逻辑）
# ─────────────────────────────────────────────

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
    return datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc).isoformat()

def build_comment_row(item: dict, bvid: str, is_top: bool, capture_mode: str, parent_id: str | None = None) -> dict:
    content = item.get("content", {})
    text_original = content.get("message", "")
    member = item.get("member", {})
    note = f"api_v2:{capture_mode}"
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

def build_language_mix(rows: list[dict]) -> str:
    counter = Counter(row["language"] for row in rows)
    return "; ".join(f"{lang}:{cnt}" for lang, cnt in counter.most_common()) if counter else "unknown"

# ─────────────────────────────────────────────
# CSV 工具
# ─────────────────────────────────────────────

def ensure_csv(path: Path, header: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        with path.open("w", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=header).writeheader()

def load_existing_keys(path: Path, key_field: str) -> set[str]:
    if not path.exists(): return set()
    with path.open("r", newline="", encoding="utf-8") as f:
        return {row[key_field] for row in csv.DictReader(f) if row.get(key_field)}

def append_unique_rows(path: Path, header: list[str], rows: list[dict], key_field: str) -> int:
    with exclusive_file_lock(path):
        ensure_csv(path, header)
        existing = load_existing_keys(path, key_field)
        written = 0
        with path.open("a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=header)
            for row in rows:
                key = str(row[key_field])
                if key not in existing:
                    writer.writerow(row)
                    existing.add(key)
                    written += 1
    return written

# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect Bilibili comments via REST API + WBI sign (no browser).")
    parser.add_argument("video_ref", help="Bilibili BV ID or URL")
    parser.add_argument("--project-dir", required=True, help="Project directory path")
    parser.add_argument("--milestone-id", required=True, help="Milestone ID for this video")
    parser.add_argument("--cookie-file", help="Path to JSON cookie file")
    parser.add_argument("--cookie-string", help="Raw cookie string")
    parser.add_argument("--max-pages", type=int, default=50, help="Max comment pages to fetch (default 50)")
    parser.add_argument("--max-sub-pages", type=int, default=3, help="Max sub-reply pages per hot thread")
    parser.add_argument("--max-replies-per-thread", type=int, default=100, help="Max replies to persist per top-level comment (compat with run_section_2)")
    parser.add_argument("--sort-mode", default="hot", choices=["hot", "time"], help="Comment sort mode")
    parser.add_argument("--delay", type=float, default=1.5, help="Base delay between requests (seconds)")
    parser.add_argument("--content-type", default="official_video")
    parser.add_argument("--official-status", default="official")
    parser.add_argument("--notes", default="")
    return parser.parse_args()

def extract_bvid(video_ref: str) -> str:
    if re.fullmatch(r"BV[1-9A-HJ-NP-Za-km-z]{10}", video_ref, re.IGNORECASE):
        return video_ref
    for part in video_ref.split("/"):
        if re.fullmatch(r"BV[1-9A-HJ-NP-Za-km-z]{10}", part, re.IGNORECASE):
            return part
    raise SystemExit(f"Could not parse a Bilibili BV ID from: {video_ref}")

def load_cookies(cookie_file: str | None, cookie_string: str | None) -> dict:
    """加载 Cookie 为 dict"""
    raw = ""
    if cookie_string:
        raw = cookie_string
    elif cookie_file:
        p = Path(cookie_file)
        if not p.exists():
            raise SystemExit(f"Cookie file not found: {p}")
        raw = p.read_text(encoding="utf-8").strip()

    if not raw:
        return {}

    # Try JSON first
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return {k: str(v) for k, v in data.items()}
    except json.JSONDecodeError:
        pass

    # Fallback: key=value; format
    result = {}
    for pair in raw.split(";"):
        if "=" in pair:
            k, v = pair.split("=", 1)
            result[k.strip()] = v.strip()
    return result


def main() -> None:
    args = parse_args()
    bvid = extract_bvid(args.video_ref)
    cookies = load_cookies(args.cookie_file, args.cookie_string)

    if not cookies:
        print("Warning: No cookies provided. Some API calls may fail.")

    project_dir = Path(args.project_dir)
    section_dir = project_dir / "section_2_official_video_comments"
    sources_dir = project_dir / "sources"

    ensure_csv(section_dir / "video_registry.csv", VIDEO_REGISTRY_HEADER)
    ensure_csv(section_dir / "comment_sample.csv", COMMENT_SAMPLE_HEADER)
    ensure_csv(sources_dir / "source_registry.csv", SOURCE_REGISTRY_HEADER)

    # 1. 建立会话 + 获取 WBI keys
    print(f"=== Bilibili Comment Collector V2 (API + WBI) ===")
    print(f"Target: {bvid}")
    sess = build_session(cookies)
    img_key, sub_key = fetch_wbi_keys(sess)

    # 2. 获取视频信息
    print(f"\nFetching video info...")
    video_info = fetch_video_info(sess, bvid, img_key, sub_key)
    aid = video_info.get("aid", 0)
    title = video_info.get("title", bvid)
    pubdate = video_info.get("pubdate", int(time.time()))
    owner = video_info.get("owner", {})
    print(f"  Title: {title}")
    print(f"  AID: {aid}")

    if not aid:
        raise SystemExit("Failed to obtain video AID. Cannot fetch comments without it.")

    # 3. 采集评论
    print(f"\nStarting comment collection (sort={args.sort_mode}, max_pages={args.max_pages})...")
    main_comments, sub_replies, total_count = collect_all_comments(
        sess, aid, img_key, sub_key,
        max_pages=args.max_pages,
        sort_mode=args.sort_mode,
        max_sub_pages=args.max_sub_pages,
        delay=args.delay,
    )

    # 4. 构建行
    capture_mode = f"api_{args.sort_mode}"
    comment_rows = []
    for item in main_comments:
        comment_rows.append(build_comment_row(item, bvid, True, capture_mode))
    for parent_id, replies in sub_replies.items():
        for reply in replies[:args.max_replies_per_thread]:
            comment_rows.append(build_comment_row(reply, bvid, False, capture_mode, parent_id))

    # 5. 保存 raw JSON
    raw_dir = section_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / f"bilibili_{bvid}.json"
    raw_path.write_text(json.dumps({
        "metadata": video_info,
        "main_comments": main_comments,
        "sub_replies": sub_replies,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    # 6. 写入 CSV
    target_url = f"https://www.bilibili.com/video/{bvid}/"
    notes = "; ".join(filter(None, [args.notes, f"api_v2:{capture_mode}", "wbi_signed"]))
    stop_reason = "end_of_cursor" if len(main_comments) < args.max_pages * 20 else "max_pages_reached"

    registry_row = {
        "video_id": bvid, "milestone_id": args.milestone_id, "platform": "bilibili",
        "url": target_url, "title": title,
        "publish_date": format_timestamp(pubdate),
        "channel_name": owner.get("name", ""), "official_status": args.official_status,
        "content_type": args.content_type, "comment_capture_mode": capture_mode,
        "comments_captured": len(comment_rows), "comments_visible_total": total_count,
        "coverage_ratio": f"{(len(main_comments) / total_count):.4f}" if total_count > 0 else "1.0000",
        "capture_stop_reason": stop_reason,
        "language_mix": build_language_mix(comment_rows), "notes": notes,
    }

    source_row = {
        "source_id": f"bili_{bvid}", "section_id": "section_2", "platform": "bilibili",
        "source_type": "official_video", "url": target_url, "title": title,
        "author_or_channel": owner.get("name", ""), "publish_date": format_timestamp(pubdate),
        "language": "zh", "official_status": args.official_status,
        "reliability_score": 5, "bias_risk": "medium",
        "access_method": "api_v2_wbi", "capture_status": "success", "notes": notes,
    }

    append_unique_rows(section_dir / "video_registry.csv", VIDEO_REGISTRY_HEADER, [registry_row], "video_id")
    written = append_unique_rows(section_dir / "comment_sample.csv", COMMENT_SAMPLE_HEADER, comment_rows, "comment_id")
    append_unique_rows(sources_dir / "source_registry.csv", SOURCE_REGISTRY_HEADER, [source_row], "source_id")

    # 7. 输出结果
    result = {
        "video_id": bvid,
        "milestone_id": args.milestone_id,
        "main_comments": len(main_comments),
        "sub_replies": sum(len(v) for v in sub_replies.values()),
        "total_rows": len(comment_rows),
        "comments_written": written,
        "total_visible": total_count,
        "raw_capture": str(raw_path),
    }
    print(f"\n=== Collection Complete ===")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
