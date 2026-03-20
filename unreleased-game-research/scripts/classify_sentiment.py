from __future__ import annotations

import argparse
import csv
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
    "language_mix",
    "notes",
]

SENTIMENT_SUMMARY_HEADER = [
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

POSITIVE_KEYWORDS = {
    "en": ["good", "great", "love", "amazing", "nice", "cool", "beautiful", "hype", "interesting", "promising"],
    "zh": ["好", "喜欢", "期待", "不错", "牛", "神", "香", "优秀", "惊艳", "有趣"],
}

NEGATIVE_KEYWORDS = {
    "en": ["bad", "boring", "worse", "awful", "hate", "lag", "clunky", "copy", "generic", "worried"],
    "zh": ["差", "无聊", "卡", "烂", "担心", "像换皮", "氪", "失望", "一般", "不行"],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply a minimal rule-based sentiment pass to Section 2 comments.")
    parser.add_argument("--project-dir", required=True, help="Path to an initialized project directory")
    parser.add_argument(
        "--section-dir",
        default="section_2_official_video_comments",
        help="Relative section directory under the project directory",
    )
    return parser.parse_args()


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise SystemExit(f"Required CSV not found: {path}")
    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return [dict(row) for row in reader]


def write_csv_rows(path: Path, header: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=header)
        writer.writeheader()
        writer.writerows(rows)


def classify_text(text: str, language: str) -> str:
    lowered = text.casefold()
    positive_hits = sum(1 for keyword in POSITIVE_KEYWORDS.get(language, []) if keyword in lowered)
    negative_hits = sum(1 for keyword in NEGATIVE_KEYWORDS.get(language, []) if keyword in lowered)

    if positive_hits > negative_hits:
        return "positive"
    if negative_hits > positive_hits:
        return "negative"
    return "neutral"


def parse_int(value: str) -> int:
    try:
        return int(value)
    except ValueError:
        return 0


def update_comment_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    updated_rows: list[dict[str, str]] = []
    for row in rows:
        updated = {header: row.get(header, "") for header in COMMENT_SAMPLE_HEADER}
        if updated["is_spam_or_noise"] == "true":
            updated["sentiment_label"] = "neutral"
        else:
            updated["sentiment_label"] = classify_text(updated["text_normalized"], updated["language"])
        updated_rows.append(updated)
    return updated_rows


def build_milestone_map(video_rows: list[dict[str, str]]) -> dict[str, str]:
    return {row.get("video_id", ""): row.get("milestone_id", "") for row in video_rows}


def format_ratio(count: int, total: int) -> str:
    if total <= 0:
        return "0.0000"
    return f"{count / total:.4f}"


def build_summary_rows(comment_rows: list[dict[str, str]], milestone_map: dict[str, str]) -> list[dict[str, str]]:
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in comment_rows:
        grouped.setdefault(row.get("video_id", ""), []).append(row)

    summary_rows: list[dict[str, str]] = []
    for video_id, rows in grouped.items():
        positive_count = sum(1 for row in rows if row["sentiment_label"] == "positive")
        neutral_count = sum(1 for row in rows if row["sentiment_label"] == "neutral")
        negative_count = sum(1 for row in rows if row["sentiment_label"] == "negative")
        positive_like_weight = sum(parse_int(row["likes"]) for row in rows if row["sentiment_label"] == "positive")
        negative_like_weight = sum(parse_int(row["likes"]) for row in rows if row["sentiment_label"] == "negative")
        total = len(rows)
        summary_rows.append(
            {
                "video_id": video_id,
                "milestone_id": milestone_map.get(video_id, ""),
                "positive_count": str(positive_count),
                "neutral_count": str(neutral_count),
                "negative_count": str(negative_count),
                "positive_ratio": format_ratio(positive_count, total),
                "neutral_ratio": format_ratio(neutral_count, total),
                "negative_ratio": format_ratio(negative_count, total),
                "positive_like_weight": str(positive_like_weight),
                "negative_like_weight": str(negative_like_weight),
                "notes": "rule_based_sentiment_v1",
            }
        )
    return summary_rows


def run() -> None:
    args = parse_args()
    section_dir = Path(args.project_dir) / args.section_dir
    comment_sample_path = section_dir / "comment_sample.csv"
    video_registry_path = section_dir / "video_registry.csv"
    sentiment_summary_path = section_dir / "sentiment_summary.csv"

    comment_rows = read_csv_rows(comment_sample_path)
    video_rows = read_csv_rows(video_registry_path)
    updated_comment_rows = update_comment_rows(comment_rows)
    milestone_map = build_milestone_map(video_rows)
    summary_rows = build_summary_rows(updated_comment_rows, milestone_map)

    write_csv_rows(comment_sample_path, COMMENT_SAMPLE_HEADER, updated_comment_rows)
    write_csv_rows(sentiment_summary_path, SENTIMENT_SUMMARY_HEADER, summary_rows)

    print(
        f"Classified {len(updated_comment_rows)} rows and wrote {len(summary_rows)} sentiment summary rows to {sentiment_summary_path}"
    )


if __name__ == "__main__":
    run()
