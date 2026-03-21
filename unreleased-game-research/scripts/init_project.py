from __future__ import annotations

import argparse
from pathlib import Path


SECTION_DIRS = [
    "section_1_public_intel",
    "section_2_official_video_comments",
    "section_3_homepage_reviews",
    "section_4_creator_reviews",
]


SECTION_2_HEADERS = {
    # Must stay in sync with VIDEO_REGISTRY_HEADER in collect_bilibili_comments.py
    # and collect_youtube_comments.py (16 columns).
    "video_registry.csv": "video_id,milestone_id,platform,url,title,publish_date,channel_name,official_status,content_type,comment_capture_mode,comments_captured,comments_visible_total,coverage_ratio,capture_stop_reason,language_mix,notes\n",
    "comment_sample.csv": "comment_id,video_id,platform,comment_time,author_name,text_original,text_normalized,language,likes,replies,is_top_comment,is_spam_or_noise,sentiment_label,topic_label,confidence_note\n",
    "sentiment_summary.csv": "video_id,milestone_id,positive_count,neutral_count,negative_count,positive_ratio,neutral_ratio,negative_ratio,positive_like_weight,negative_like_weight,notes\n",
    "topic_summary.csv": "video_id,milestone_id,topic_label,mention_count,mention_ratio,positive_ratio_within_topic,negative_ratio_within_topic,avg_likes,representative_evidence_id\n",
    "milestone_delta.csv": "from_milestone,to_milestone,topic_label,direction,observed_change,likely_driver,confidence_level,supporting_evidence_ids\n",
}


PROJECT_YAML = """game_name: \"{game_name}\"
aliases: []
company: \"\"
studio: \"\"
target_markets: []
platforms_to_cover: []
milestones: []
output_mode: {output_mode}
"""


SOURCE_REGISTRY_HEADER = (
    "source_id,section_id,platform,source_type,url,title,author_or_channel,publish_date,"
    "language,official_status,reliability_score,bias_risk,access_method,capture_status,notes\n"
)


FINDINGS_TEMPLATE = """## Scope

## Core Conclusions

## What We Know

## What We Infer

## Key Evidence

## Positive Signals

## Negative Signals / Concerns

## Disagreements / Mixed Signals

## Confidence and Limitations

## Open Questions
"""


def slugify(value: str) -> str:
    cleaned = []
    last_dash = False
    for ch in value.lower():
        if ch.isalnum():
            cleaned.append(ch)
            last_dash = False
        elif not last_dash:
            cleaned.append("-")
            last_dash = True
    slug = "".join(cleaned).strip("-")
    return slug or "game-project"


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(content, encoding="utf-8")


def build_project(root: Path, game_name: str, output_mode: str) -> Path:
    project_dir = root / slugify(game_name)
    project_dir.mkdir(parents=True, exist_ok=True)

    write_text(project_dir / "project.yaml", PROJECT_YAML.format(game_name=game_name, output_mode=output_mode))
    write_text(project_dir / "sources" / "source_registry.csv", SOURCE_REGISTRY_HEADER)
    write_text(project_dir / "sources" / "source_notes.md", "# Source Notes\n")
    write_text(project_dir / "synthesis" / "executive_summary.md", "# Executive Summary\n")
    write_text(project_dir / "synthesis" / "final_report.md", "# Final Report\n")
    (project_dir / "exports").mkdir(exist_ok=True)

    for section in SECTION_DIRS:
        section_dir = project_dir / section
        section_dir.mkdir(exist_ok=True)
        write_text(section_dir / "findings.md", FINDINGS_TEMPLATE)
        write_text(section_dir / "evidence_table.csv", "evidence_id,source_id,claim_or_observation,evidence_type,quote_original,quote_translated,topic_label,sentiment_label,milestone,strength,risk_note\n")

    for filename, header in SECTION_2_HEADERS.items():
        write_text(project_dir / "section_2_official_video_comments" / filename, header)

    (project_dir / "section_2_official_video_comments" / "raw").mkdir(exist_ok=True)

    return project_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize an unreleased-game research project.")
    parser.add_argument("game_name", help="Display name of the game to analyze")
    parser.add_argument("--root", default="projects", help="Root directory for project folders")
    parser.add_argument("--output-mode", default="safe_mode", choices=["safe_mode", "deep_mode"])
    args = parser.parse_args()

    project_dir = build_project(Path(args.root), args.game_name, args.output_mode)
    print(project_dir)


if __name__ == "__main__":
    main()
