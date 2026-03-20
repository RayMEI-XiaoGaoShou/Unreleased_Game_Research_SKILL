from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path


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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Normalize Section 2 comment_sample.csv data.")
    parser.add_argument("--project-dir", required=True, help="Path to an initialized project directory")
    parser.add_argument(
        "--section-dir",
        default="section_2_official_video_comments",
        help="Relative section directory under the project directory",
    )
    parser.add_argument(
        "--dedupe",
        action="store_true",
        help="Drop duplicate rows that share video_id, author_name, and normalized text",
    )
    return parser.parse_args()


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


def normalize_text_value(text: str) -> str:
    lowered = text.casefold()
    collapsed = " ".join(lowered.split())
    return collapsed.strip()


def is_spam_or_noise(text: str) -> bool:
    if not text:
        return True
    if "http://" in text or "https://" in text:
        return True
    if len(text) <= 1:
        return True
    if re.fullmatch(r"[!?.~\-_=+*/\\|]+", text):
        return True
    return False


def read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise SystemExit(f"comment_sample.csv not found: {path}")
    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return [dict(row) for row in reader]


def normalize_rows(rows: list[dict[str, str]], dedupe: bool) -> tuple[list[dict[str, str]], int]:
    normalized_rows: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    dropped = 0

    for row in rows:
        text_original = row.get("text_original", "")
        text_normalized = normalize_text_value(text_original)
        language = detect_language(text_original)
        spam_flag = "true" if is_spam_or_noise(text_normalized) else row.get("is_spam_or_noise", "false") or "false"
        key = (
            row.get("video_id", ""),
            row.get("author_name", ""),
            text_normalized,
        )
        if dedupe and key in seen:
            dropped += 1
            continue
        seen.add(key)

        updated = {header: row.get(header, "") for header in COMMENT_SAMPLE_HEADER}
        updated["text_normalized"] = text_normalized
        updated["language"] = language
        updated["is_spam_or_noise"] = spam_flag
        normalized_rows.append(updated)

    return normalized_rows, dropped


def write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COMMENT_SAMPLE_HEADER)
        writer.writeheader()
        writer.writerows(rows)


def run() -> None:
    args = parse_args()
    section_dir = Path(args.project_dir) / args.section_dir
    comment_sample_path = section_dir / "comment_sample.csv"
    rows = read_rows(comment_sample_path)
    normalized_rows, dropped = normalize_rows(rows, args.dedupe)
    write_rows(comment_sample_path, normalized_rows)
    print(
        f"Normalized {len(normalized_rows)} rows in {comment_sample_path}"
        + (f"; dropped_duplicates={dropped}" if args.dedupe else "")
    )


if __name__ == "__main__":
    run()
