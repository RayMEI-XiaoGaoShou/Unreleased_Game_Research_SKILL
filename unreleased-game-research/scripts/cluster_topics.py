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

TOPIC_SUMMARY_HEADER = [
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

TOPIC_RULES = {
    "technical_quality": ["优化", "卡", "lag", "fps", "frame", "stutter", "bug", "performance"],
    "monetization_anxiety": ["氪", "pay to win", "p2w", "gacha", "monetization", "抽卡"],
    "art_visual_identity": ["美术", "画风", "visual", "art", "beautiful", "ugly", "character design"],
    "gameplay_loop": ["玩法", "loop", "gameplay", "combat", "battle", "战斗", "操作"],
    "world_setting": ["世界观", "atmosphere", "world", "setting", "剧情", "story", "lore"],
    "innovation_sameness": ["copy", "generic", "换皮", "same", "clone", "创新", "不像"],
    "trust_in_progress": ["进度", "delay", "更新", "improve", "polish", "开发", "测试"],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Assign rule-based topic labels and build Section 2 topic summaries.")
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


def infer_topic(text: str) -> str:
    best_topic = "uncategorized"
    best_hits = 0
    lowered = text.casefold()
    for topic, keywords in TOPIC_RULES.items():
        hits = sum(1 for keyword in keywords if keyword in lowered)
        if hits > best_hits:
            best_topic = topic
            best_hits = hits
    return best_topic


def parse_int(value: str) -> int:
    try:
        return int(value)
    except ValueError:
        return 0


def format_ratio(count: int, total: int) -> str:
    if total <= 0:
        return "0.0000"
    return f"{count / total:.4f}"


def update_comment_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    updated_rows: list[dict[str, str]] = []
    for row in rows:
        updated = {header: row.get(header, "") for header in COMMENT_SAMPLE_HEADER}
        if updated["is_spam_or_noise"] == "true":
            updated["topic_label"] = "noise_or_meme"
        elif not updated["topic_label"]:
            updated["topic_label"] = infer_topic(updated["text_normalized"])
        updated_rows.append(updated)
    return updated_rows


def build_milestone_map(rows: list[dict[str, str]]) -> dict[str, str]:
    return {row.get("video_id", ""): row.get("milestone_id", "") for row in rows}


def build_topic_summary(comment_rows: list[dict[str, str]], milestone_map: dict[str, str]) -> list[dict[str, str]]:
    non_noise_rows = [row for row in comment_rows if row["topic_label"] != "noise_or_meme"]
    grouped: dict[tuple[str, str], list[dict[str, str]]] = {}
    totals_by_video: dict[str, int] = {}

    for row in non_noise_rows:
        key = (row.get("video_id", ""), row.get("topic_label", "uncategorized"))
        grouped.setdefault(key, []).append(row)
        totals_by_video[row.get("video_id", "")] = totals_by_video.get(row.get("video_id", ""), 0) + 1

    summary_rows: list[dict[str, str]] = []
    for (video_id, topic_label), rows in sorted(grouped.items()):
        total = len(rows)
        positive_count = sum(1 for row in rows if row["sentiment_label"] == "positive")
        negative_count = sum(1 for row in rows if row["sentiment_label"] == "negative")
        avg_likes = sum(parse_int(row["likes"]) for row in rows) / total if total else 0.0
        representative = max(rows, key=lambda row: parse_int(row["likes"])) if rows else None
        summary_rows.append(
            {
                "video_id": video_id,
                "milestone_id": milestone_map.get(video_id, ""),
                "topic_label": topic_label,
                "mention_count": str(total),
                "mention_ratio": format_ratio(total, totals_by_video.get(video_id, total)),
                "positive_ratio_within_topic": format_ratio(positive_count, total),
                "negative_ratio_within_topic": format_ratio(negative_count, total),
                "avg_likes": f"{avg_likes:.2f}",
                "representative_evidence_id": representative.get("comment_id", "") if representative else "",
            }
        )
    return summary_rows


def run() -> None:
    args = parse_args()
    section_dir = Path(args.project_dir) / args.section_dir
    comment_sample_path = section_dir / "comment_sample.csv"
    video_registry_path = section_dir / "video_registry.csv"
    topic_summary_path = section_dir / "topic_summary.csv"

    comment_rows = read_csv_rows(comment_sample_path)
    video_rows = read_csv_rows(video_registry_path)

    updated_comment_rows = update_comment_rows(comment_rows)
    topic_summary_rows = build_topic_summary(updated_comment_rows, build_milestone_map(video_rows))

    write_csv_rows(comment_sample_path, COMMENT_SAMPLE_HEADER, updated_comment_rows)
    write_csv_rows(topic_summary_path, TOPIC_SUMMARY_HEADER, topic_summary_rows)

    print(
        f"Updated topic labels for {len(updated_comment_rows)} comments and wrote {len(topic_summary_rows)} topic summary rows to {topic_summary_path}"
    )


if __name__ == "__main__":
    run()
