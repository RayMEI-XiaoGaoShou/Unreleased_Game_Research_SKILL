from __future__ import annotations

import argparse
from pathlib import Path

from section_4_common import (
    CLAIM_EVIDENCE_MAP_HEADER,
    CREATOR_PROFILES_HEADER,
    SELECTED_VIDEOS_HEADER,
    TOPIC_CONSENSUS_HEADER,
    TRANSCRIPT_SEGMENTS_HEADER,
    derive_claim_id,
    detect_language,
    ensure_section_files,
    infer_claim_type,
    infer_support_label,
    infer_topic,
    infer_visible_footage_support,
    merge_notes,
    normalize_text_value,
    read_csv_rows,
    write_csv_rows,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Annotate Section 4 transcript segments into claims and topic consensus.")
    _ = parser.add_argument("--project-dir", required=True, help="Path to an initialized project directory")
    _ = parser.add_argument("--section-dir", default="section_4_creator_reviews", help="Relative section directory under the project directory")
    return parser.parse_args()


def read_optional_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    return read_csv_rows(path)


def load_cross_section_topics(project_dir: Path) -> tuple[set[str], set[str]]:
    section_2_topics = read_optional_rows(project_dir / "section_2_official_video_comments" / "topic_summary.csv")
    section_3_topics = read_optional_rows(project_dir / "section_3_homepage_reviews" / "topic_summary.csv")
    return (
        {normalize_text_value(row.get("topic_label", "")) for row in section_2_topics if row.get("topic_label", "")},
        {normalize_text_value(row.get("topic_label", "")) for row in section_3_topics if row.get("topic_label", "")},
    )


def infer_cross_source_support(topic_label: str, section_2_topics: set[str], section_3_topics: set[str]) -> str:
    normalized = normalize_text_value(topic_label)
    support_2 = normalized in section_2_topics
    support_3 = normalized in section_3_topics
    if support_2 and support_3:
        return "section_2+section_3"
    if support_2:
        return "section_2"
    if support_3:
        return "section_3"
    return "none"


def infer_confidence_level(text: str, visible_support: str, cross_support: str) -> str:
    if len(text.strip()) >= 120 and visible_support == "yes" and cross_support != "none":
        return "high"
    if len(text.strip()) >= 40 or cross_support != "none":
        return "medium"
    return "low"


def update_transcript_rows(
    transcript_rows: list[dict[str, str]],
    section_2_topics: set[str],
    section_3_topics: set[str],
) -> list[dict[str, str]]:
    updated_rows: list[dict[str, str]] = []
    for row in transcript_rows:
        quote_original = row.get("quote_original", "").strip()
        if not quote_original:
            continue
        topic_label = row.get("topic_label", "") or infer_topic(quote_original)
        visible_support = row.get("visible_footage_support", "") or infer_visible_footage_support(quote_original)
        cross_support = row.get("cross_source_support", "") or infer_cross_source_support(topic_label, section_2_topics, section_3_topics)
        updated_rows.append(
            {
                "segment_id": row.get("segment_id", ""),
                "video_id": row.get("video_id", ""),
                "timestamp_start": row.get("timestamp_start", ""),
                "timestamp_end": row.get("timestamp_end", ""),
                "quote_original": quote_original,
                "quote_normalized": row.get("quote_normalized", "") or normalize_text_value(quote_original),
                "topic_label": topic_label,
                "claim_type": row.get("claim_type", "") or infer_claim_type(quote_original),
                "supports_positive_or_negative": row.get("supports_positive_or_negative", "") or infer_support_label(quote_original),
                "visible_footage_support": visible_support,
                "cross_source_support": cross_support,
                "confidence_level": row.get("confidence_level", "") or infer_confidence_level(quote_original, visible_support, cross_support),
            }
        )
    return updated_rows


def build_claim_summary(text: str) -> str:
    stripped = text.strip().replace("\n", " ")
    if len(stripped) <= 160:
        return stripped
    return stripped[:157].rstrip() + "..."


def build_topic_consensus_rows(claim_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in claim_rows:
        grouped.setdefault(row.get("topic_label", "gameplay loop"), []).append(row)

    consensus_rows: list[dict[str, str]] = []
    for topic_label, rows in sorted(grouped.items()):
        positive_videos = {row.get("video_id", "") for row in rows if row.get("supports_positive_or_negative") == "positive"}
        negative_videos = {row.get("video_id", "") for row in rows if row.get("supports_positive_or_negative") == "negative"}
        mixed_videos = {row.get("video_id", "") for row in rows if row.get("supports_positive_or_negative") in {"mixed", "neutral"}}
        participating_videos = positive_videos | negative_videos | mixed_videos
        if len(participating_videos) < 2:
            consensus_type = "weak_signal"
        elif len(positive_videos) >= 2 and not negative_videos and not mixed_videos:
            consensus_type = "consensus_positive"
        elif len(negative_videos) >= 2 and not positive_videos and not mixed_videos:
            consensus_type = "consensus_negative"
        elif positive_videos and negative_videos:
            consensus_type = "mixed"
        else:
            consensus_type = "weak_signal"

        supporting_video_count = len(participating_videos)
        contradicting_video_count = min(len(positive_videos), len(negative_videos)) if positive_videos and negative_videos else 0
        confidence_level = "high" if supporting_video_count >= 3 and contradicting_video_count == 0 else "medium" if supporting_video_count >= 2 else "low"
        representative_claim_ids = "; ".join(row.get("claim_id", "") for row in rows[:3])
        consensus_rows.append(
            {
                "topic_label": topic_label,
                "consensus_type": consensus_type,
                "supporting_video_count": str(supporting_video_count),
                "contradicting_video_count": str(contradicting_video_count),
                "representative_claim_ids": representative_claim_ids,
                "confidence_level": confidence_level,
            }
        )
    return consensus_rows


def final_assessment_for_claim(visible_support: str, cross_support: str, confidence_level: str, contradicted: bool) -> str:
    if contradicted:
        return "mixed_or_contested"
    if visible_support == "yes" and cross_support != "none" and confidence_level == "high":
        return "strong_support"
    if visible_support == "yes" or cross_support != "none" or confidence_level in {"high", "medium"}:
        return "partial_support"
    return "limited_support"


def update_creator_profiles(
    selected_rows: list[dict[str, str]],
    candidate_by_video: dict[str, dict[str, str]],
    updated_segments: list[dict[str, str]],
    existing_profiles: list[dict[str, str]],
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    segments_by_video: dict[str, list[dict[str, str]]] = {}
    for row in updated_segments:
        segments_by_video.setdefault(row.get("video_id", ""), []).append(row)

    existing_profile_by_key = {(row.get("creator_name", ""), row.get("platform", "")): row for row in existing_profiles}
    updated_profiles: list[dict[str, str]] = []
    updated_selected_rows: list[dict[str, str]] = []
    for selected_row in selected_rows:
        video_id = selected_row.get("video_id", "")
        candidate_row = candidate_by_video.get(video_id, {})
        key = (candidate_row.get("creator_name", ""), candidate_row.get("platform", ""))
        existing = existing_profile_by_key.get(key, {})
        video_segments = segments_by_video.get(video_id, [])
        positive_count = sum(1 for row in video_segments if row.get("supports_positive_or_negative") == "positive")
        negative_count = sum(1 for row in video_segments if row.get("supports_positive_or_negative") == "negative")
        segment_count = len(video_segments)
        evidence_density = "high" if segment_count >= 8 else "medium" if segment_count >= 4 else "low"
        balance = "balanced" if positive_count > 0 and negative_count > 0 else "one_sided_positive" if positive_count > 0 else "one_sided_negative" if negative_count > 0 else "unclear"
        credibility = selected_row.get("creator_credibility", "")
        if not credibility:
            credibility = "high" if evidence_density == "high" and balance == "balanced" else "medium" if evidence_density in {"high", "medium"} else "low"

        updated_profiles.append(
            {
                "creator_name": candidate_row.get("creator_name", ""),
                "platform": candidate_row.get("platform", ""),
                "audience_size_bucket": existing.get("audience_size_bucket") or selected_row.get("audience_size_bucket", "unknown"),
                "genre_relevance": existing.get("genre_relevance") or selected_row.get("genre_familiarity_note", "manual review needed"),
                "ip_relevance": existing.get("ip_relevance") or "unknown",
                "evidence_density": evidence_density,
                "balance_of_judgment": balance,
                "sponsorship_risk": existing.get("sponsorship_risk") or selected_row.get("sponsorship_risk", "medium"),
                "credibility_rating": existing.get("credibility_rating") or credibility,
                "notes": merge_notes(existing.get("notes", ""), f"segments={segment_count}", f"lang={detect_language(candidate_row.get('title', ''))}"),
            }
        )

        updated_selected_rows.append(
            {
                "video_id": selected_row.get("video_id", ""),
                "selection_reason": selected_row.get("selection_reason", ""),
                "creator_credibility": credibility,
                "audience_size_bucket": selected_row.get("audience_size_bucket", "unknown"),
                "sponsorship_risk": selected_row.get("sponsorship_risk", "medium"),
                "genre_familiarity_note": selected_row.get("genre_familiarity_note", "manual review needed"),
                "stance_note": selected_row.get("stance_note", "unclear"),
            }
        )

    return updated_profiles, updated_selected_rows


def main() -> None:
    args = parse_args()
    project_dir = Path(args.project_dir).resolve()
    section_dir = ensure_section_files(project_dir)
    if args.section_dir != section_dir.name:
        section_dir = project_dir / args.section_dir

    candidate_rows = read_csv_rows(section_dir / "candidate_videos.csv")
    selected_rows = read_csv_rows(section_dir / "selected_videos.csv")
    transcript_rows = read_csv_rows(section_dir / "transcript_segments.csv")
    existing_profiles = read_csv_rows(section_dir / "creator_profiles.csv")
    if not selected_rows:
        raise SystemExit("selected_videos.csv has no data rows. Import candidates and choose final videos first.")
    if not transcript_rows:
        raise SystemExit("transcript_segments.csv has no data rows. Import transcript segments before annotation.")

    section_2_topics, section_3_topics = load_cross_section_topics(project_dir)
    updated_segments = update_transcript_rows(transcript_rows, section_2_topics, section_3_topics)
    candidate_by_video = {row.get("video_id", ""): row for row in candidate_rows}
    consensus_seed_rows: list[dict[str, str]] = []
    for row in updated_segments:
        candidate_row = candidate_by_video.get(row.get("video_id", ""), {})
        claim_id = derive_claim_id(row.get("segment_id", ""))
        consensus_seed_rows.append(
            {
                "claim_id": claim_id,
                "video_id": row.get("video_id", ""),
                "creator_name": candidate_row.get("creator_name", ""),
                "claim_summary": build_claim_summary(row.get("quote_original", "")),
                "topic_label": row.get("topic_label", ""),
                "claim_type": row.get("claim_type", ""),
                "supported_by_footage": "true" if row.get("visible_footage_support") == "yes" else "false",
                "supported_by_section_2": "true" if "section_2" in row.get("cross_source_support", "") else "false",
                "supported_by_section_3": "true" if "section_3" in row.get("cross_source_support", "") else "false",
                "contradicted_elsewhere": "false",
                "final_assessment": "",
                "notes": merge_notes(row.get("confidence_level", ""), row.get("cross_source_support", ""), f"segment_id={row.get('segment_id', '')}"),
                "supports_positive_or_negative": row.get("supports_positive_or_negative", "neutral"),
                "confidence_level": row.get("confidence_level", "low"),
                "visible_footage_support": row.get("visible_footage_support", "unclear"),
            }
        )

    consensus_rows = build_topic_consensus_rows(consensus_seed_rows)
    consensus_by_topic = {row.get("topic_label", ""): row for row in consensus_rows}
    claim_rows: list[dict[str, str]] = []
    for row in consensus_seed_rows:
        consensus = consensus_by_topic.get(row.get("topic_label", ""), {})
        contradicted = consensus.get("consensus_type") == "mixed"
        claim_rows.append(
            {
                "claim_id": row.get("claim_id", ""),
                "video_id": row.get("video_id", ""),
                "creator_name": row.get("creator_name", ""),
                "claim_summary": row.get("claim_summary", ""),
                "topic_label": row.get("topic_label", ""),
                "claim_type": row.get("claim_type", ""),
                "supported_by_footage": row.get("supported_by_footage", "false"),
                "supported_by_section_2": row.get("supported_by_section_2", "false"),
                "supported_by_section_3": row.get("supported_by_section_3", "false"),
                "contradicted_elsewhere": "true" if contradicted else "false",
                "final_assessment": final_assessment_for_claim(
                    row.get("visible_footage_support", "unclear"),
                    row.get("notes", ""),
                    row.get("confidence_level", "low"),
                    contradicted,
                ),
                "notes": row.get("notes", ""),
            }
        )

    updated_profiles, updated_selected_rows = update_creator_profiles(selected_rows, candidate_by_video, updated_segments, existing_profiles)

    write_csv_rows(section_dir / "transcript_segments.csv", TRANSCRIPT_SEGMENTS_HEADER, updated_segments)
    write_csv_rows(section_dir / "selected_videos.csv", SELECTED_VIDEOS_HEADER, updated_selected_rows)
    write_csv_rows(section_dir / "creator_profiles.csv", CREATOR_PROFILES_HEADER, updated_profiles)
    write_csv_rows(section_dir / "claim_evidence_map.csv", CLAIM_EVIDENCE_MAP_HEADER, claim_rows)
    write_csv_rows(section_dir / "topic_consensus.csv", TOPIC_CONSENSUS_HEADER, consensus_rows)

    print(f"Annotated {len(updated_segments)} Section 4 transcript segments")
    print(f"- claims: {section_dir / 'claim_evidence_map.csv'}")
    print(f"- consensus: {section_dir / 'topic_consensus.csv'}")


if __name__ == "__main__":
    main()
