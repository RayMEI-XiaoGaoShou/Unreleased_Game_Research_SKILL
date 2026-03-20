from __future__ import annotations

import argparse
from pathlib import Path

from section_3_common import (
    REVIEW_REGISTRY_HEADER,
    REVIEW_SAMPLE_HEADER,
    REVIEWER_TAGS_HEADER,
    SECTION_DIR_NAME,
    SENTIMENT_SUMMARY_HEADER,
    TOPIC_SUMMARY_HEADER,
    evidence_id_for_review,
    classify_sentiment,
    detect_language,
    format_ratio,
    high_value_reasons,
    infer_experience_basis,
    infer_reviewer_tags,
    infer_topic,
    is_experience_based,
    parse_int,
    read_csv_rows,
    review_length_bucket,
    write_csv_rows,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Annotate Section 3 homepage reviews with heuristic sentiment, topic, and reviewer tags.")
    parser.add_argument("--project-dir", required=True, help="Path to an initialized project directory")
    parser.add_argument("--section-dir", default=SECTION_DIR_NAME, help="Relative section directory under the project directory")
    return parser.parse_args()


def annotate_reviews(
    registry_rows: list[dict[str, str]],
    sample_rows: list[dict[str, str]],
) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    registry_by_id = {row.get("review_id", ""): dict(row) for row in registry_rows}
    updated_registry: list[dict[str, str]] = []
    updated_samples: list[dict[str, str]] = []
    reviewer_tag_rows: list[dict[str, str]] = []

    for row in sample_rows:
        review_id = row.get("review_id", "")
        registry_row = {header: registry_by_id.get(review_id, {}).get(header, "") for header in REVIEW_REGISTRY_HEADER}
        text_original = row.get("text_original", "")
        text_normalized = " ".join(text_original.casefold().split()).strip()
        language = row.get("language", "") or registry_row.get("language", "") or detect_language(text_original)
        sentiment_label, sentiment_note = classify_sentiment(text_normalized, language)
        topic_label, topic_note = infer_topic(text_normalized)
        experience_basis, experience_note = infer_experience_basis(text_normalized)
        tags = infer_reviewer_tags(text_normalized)
        likes = parse_int(row.get("likes", "0"))
        replies = parse_int(row.get("replies", "0"))
        reasons = high_value_reasons(text_original, likes, replies, experience_basis, tags)
        is_high_value = "true" if reasons else "false"

        updated_sample = {header: row.get(header, "") for header in REVIEW_SAMPLE_HEADER}
        updated_sample["text_normalized"] = text_normalized
        updated_sample["language"] = language
        updated_sample["sentiment_label"] = sentiment_label
        updated_sample["topic_label"] = topic_label
        updated_sample["experience_basis"] = experience_basis
        updated_sample["is_high_value"] = is_high_value
        updated_sample["confidence_note"] = "; ".join(
            part
            for part in [sentiment_note, topic_note, experience_note, f"high_value_reasons={','.join(reasons) or 'none'}"]
            if part
        )
        updated_samples.append(updated_sample)

        updated_registry_row = {header: registry_row.get(header, row.get(header, "")) for header in REVIEW_REGISTRY_HEADER}
        updated_registry_row["language"] = language
        updated_registry_row["review_length_bucket"] = review_length_bucket(text_original)
        updated_registry_row["is_longform"] = "true" if review_length_bucket(text_original) == "long" else "false"
        updated_registry.append(updated_registry_row)

        for tag, tag_basis, confidence_level, notes in tags:
            reviewer_tag_rows.append(
                {
                    "review_id": review_id,
                    "reviewer_tag": tag,
                    "tag_basis": tag_basis,
                    "confidence_level": confidence_level,
                    "notes": notes,
                }
            )

    return updated_registry, updated_samples, reviewer_tag_rows


def build_sentiment_summary(sample_rows: list[dict[str, str]], registry_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    platform_by_review = {row.get("review_id", ""): row.get("platform", "") for row in registry_rows}
    longform_by_review = {row.get("review_id", ""): row.get("is_longform", "false") for row in registry_rows}
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in sample_rows:
        grouped.setdefault(platform_by_review.get(row.get("review_id", ""), row.get("platform", "") or "unknown"), []).append(row)

    summary_rows: list[dict[str, str]] = []
    for platform, rows in sorted(grouped.items()):
        positive_count = sum(1 for row in rows if row.get("sentiment_label") == "positive")
        neutral_count = sum(1 for row in rows if row.get("sentiment_label") == "neutral")
        negative_count = sum(1 for row in rows if row.get("sentiment_label") == "negative")
        longform_count = sum(1 for row in rows if longform_by_review.get(row.get("review_id", ""), "false") == "true")
        experience_count = sum(1 for row in rows if is_experience_based(row.get("experience_basis", "")))
        total = len(rows)
        summary_rows.append(
            {
                "platform": platform,
                "positive_count": str(positive_count),
                "neutral_count": str(neutral_count),
                "negative_count": str(negative_count),
                "positive_ratio": format_ratio(positive_count, total),
                "neutral_ratio": format_ratio(neutral_count, total),
                "negative_ratio": format_ratio(negative_count, total),
                "longform_share": format_ratio(longform_count, total),
                "experience_based_share": format_ratio(experience_count, total),
                "notes": "rule_based_section_3_v1",
            }
        )
    return summary_rows


def build_topic_summary(sample_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in sample_rows:
        grouped.setdefault(row.get("topic_label", "content depth / endgame concern"), []).append(row)

    total = len(sample_rows)
    summary_rows: list[dict[str, str]] = []
    for topic_label, rows in sorted(grouped.items()):
        mention_count = len(rows)
        positive_count = sum(1 for row in rows if row.get("sentiment_label") == "positive")
        negative_count = sum(1 for row in rows if row.get("sentiment_label") == "negative")
        experience_count = sum(1 for row in rows if is_experience_based(row.get("experience_basis", "")))
        representative = max(rows, key=lambda row: (parse_int(row.get("likes", "0")), row.get("is_high_value") == "true"))
        summary_rows.append(
            {
                "topic_label": topic_label,
                "mention_count": str(mention_count),
                "mention_ratio": format_ratio(mention_count, total),
                "positive_ratio_within_topic": format_ratio(positive_count, mention_count),
                "negative_ratio_within_topic": format_ratio(negative_count, mention_count),
                "experience_based_ratio": format_ratio(experience_count, mention_count),
                "representative_evidence_id": evidence_id_for_review(representative.get("review_id", "")),
            }
        )
    return summary_rows


def run() -> None:
    args = parse_args()
    section_dir = Path(args.project_dir) / args.section_dir
    registry_rows = read_csv_rows(section_dir / "review_registry.csv")
    sample_rows = read_csv_rows(section_dir / "review_sample.csv")

    updated_registry, updated_samples, reviewer_tag_rows = annotate_reviews(registry_rows, sample_rows)
    sentiment_summary_rows = build_sentiment_summary(updated_samples, updated_registry)
    topic_summary_rows = build_topic_summary(updated_samples)

    write_csv_rows(section_dir / "review_registry.csv", REVIEW_REGISTRY_HEADER, updated_registry)
    write_csv_rows(section_dir / "review_sample.csv", REVIEW_SAMPLE_HEADER, updated_samples)
    write_csv_rows(section_dir / "reviewer_tags.csv", REVIEWER_TAGS_HEADER, reviewer_tag_rows)
    write_csv_rows(section_dir / "sentiment_summary.csv", SENTIMENT_SUMMARY_HEADER, sentiment_summary_rows)
    write_csv_rows(section_dir / "topic_summary.csv", TOPIC_SUMMARY_HEADER, topic_summary_rows)

    print(
        f"Annotated {len(updated_samples)} Section 3 reviews and wrote reviewer_tags, sentiment_summary, and topic_summary in {section_dir}"
    )


if __name__ == "__main__":
    run()
