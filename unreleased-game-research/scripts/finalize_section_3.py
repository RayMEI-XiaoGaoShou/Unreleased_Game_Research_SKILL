from __future__ import annotations

import argparse
from pathlib import Path
import importlib

reporting_utils = importlib.import_module("reporting_utils")
ratio_percent = reporting_utils.ratio_percent
topic_to_zh = reporting_utils.topic_to_zh
section_3_common = importlib.import_module("section_3_common")
EVIDENCE_TABLE_HEADER = section_3_common.EVIDENCE_TABLE_HEADER
REVIEW_REGISTRY_HEADER = section_3_common.REVIEW_REGISTRY_HEADER
SECTION_DIR_NAME = section_3_common.SECTION_DIR_NAME
derive_source_id = section_3_common.derive_source_id
evidence_id_for_review = section_3_common.evidence_id_for_review
is_experience_based = section_3_common.is_experience_based
parse_int = section_3_common.parse_int
read_csv_rows = section_3_common.read_csv_rows
strength_from_review = section_3_common.strength_from_review
write_csv_rows = section_3_common.write_csv_rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="整理 Section 3 主页/预约评价输出。")
    parser.add_argument("--project-dir", required=True, help="项目目录")
    parser.add_argument("--section-dir", default=SECTION_DIR_NAME, help="Section 3 目录")
    return parser.parse_args()


def build_registry_maps(registry_rows: list[dict[str, str]]) -> tuple[dict[str, dict[str, str]], dict[str, str]]:
    registry_by_review = {row.get("review_id", ""): row for row in registry_rows}
    source_by_review = {
        row.get("review_id", ""): derive_source_id(row.get("platform", "unknown"), row.get("url", ""), row.get("game_page_title", ""))
        for row in registry_rows
    }
    return registry_by_review, source_by_review


def build_tag_map(tag_rows: list[dict[str, str]]) -> dict[str, list[str]]:
    tag_map: dict[str, list[str]] = {}
    for row in tag_rows:
        tag_map.setdefault(row.get("review_id", ""), []).append(row.get("reviewer_tag", "unclear"))
    return tag_map


def build_evidence_rows(
    registry_rows: list[dict[str, str]],
    sample_rows: list[dict[str, str]],
    tag_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    registry_by_review, source_by_review = build_registry_maps(registry_rows)
    tag_map = build_tag_map(tag_rows)
    selected = [row for row in sample_rows if row.get("is_high_value") == "true"] or sample_rows
    evidence_rows: list[dict[str, str]] = []
    for row in selected:
        review_id = row.get("review_id", "")
        registry_row = registry_by_review.get(review_id, {header: "" for header in REVIEW_REGISTRY_HEADER})
        likes = parse_int(row.get("likes", "0"))
        replies = parse_int(row.get("replies", "0"))
        evidence_rows.append(
            {
                "evidence_id": evidence_id_for_review(review_id),
                "source_id": source_by_review.get(review_id, ""),
                "claim_or_observation": f"关于“{topic_to_zh(row.get('topic_label', ''))}”的{row.get('sentiment_label', 'neutral')}玩家评论",
                "evidence_type": "player_opinion",
                "quote_original": row.get("text_original", ""),
                "quote_translated": "",
                "topic_label": row.get("topic_label", ""),
                "sentiment_label": row.get("sentiment_label", ""),
                "milestone": "",
                "strength": strength_from_review(likes, replies, row.get("is_high_value") == "true"),
                "risk_note": "; ".join(
                    filter(
                        None,
                        [
                            row.get("experience_basis", ""),
                            registry_row.get("review_length_bucket", ""),
                            "reviewer_tags=" + ",".join(tag_map.get(review_id, ["unclear"])),
                        ],
                    )
                ),
            }
        )
    return evidence_rows


def top_rows(rows: list[dict[str, str]], key: str, limit: int = 5) -> list[dict[str, str]]:
    return sorted(rows, key=lambda row: parse_int(row.get(key, "0")), reverse=True)[:limit]


def top_evidence_by_sentiment(evidence_rows: list[dict[str, str]], sentiment_label: str, limit: int = 3) -> list[dict[str, str]]:
    order = {"strong": 3, "medium": 2, "weak": 1}
    filtered = [row for row in evidence_rows if row.get("sentiment_label") == sentiment_label]
    return sorted(filtered, key=lambda row: order.get(row.get("strength", "weak"), 0), reverse=True)[:limit]


def top_evidence_rows(evidence_rows: list[dict[str, str]], limit: int = 5) -> list[dict[str, str]]:
    order = {"strong": 3, "medium": 2, "weak": 1}
    return sorted(evidence_rows, key=lambda row: order.get(row.get("strength", "weak"), 0), reverse=True)[:limit]


def compare_with_section_2(project_dir: Path) -> list[str]:
    path = project_dir / "section_2_official_video_comments" / "topic_summary.csv"
    if not path.exists():
        return ["- Section 2 尚未生成 topic_summary.csv，因此无法进行跨 section 主题对照。"]
    rows = read_csv_rows(path)
    if not rows:
        return ["- Section 2 的 topic_summary.csv 为空，无法进行跨 section 主题对照。"]
    top_topics = top_rows(rows, "mention_count", limit=4)
    return ["- 与官方视频评论的高频主题对照：" + "、".join(topic_to_zh(row.get("topic_label", "")) for row in top_topics) + "。"]


def build_findings_markdown(
    project_dir: Path,
    registry_rows: list[dict[str, str]],
    sample_rows: list[dict[str, str]],
    tag_rows: list[dict[str, str]],
    sentiment_rows: list[dict[str, str]],
    topic_rows: list[dict[str, str]],
    evidence_rows: list[dict[str, str]],
) -> str:
    platforms = sorted({row.get("platform", "") for row in registry_rows if row.get("platform")})
    longform_count = sum(1 for row in registry_rows if row.get("is_longform") == "true")
    firsthand_count = sum(1 for row in sample_rows if is_experience_based(row.get("experience_basis", "")))
    high_value_count = sum(1 for row in sample_rows if row.get("is_high_value") == "true")
    tag_counts: dict[str, int] = {}
    for row in tag_rows:
        tag_counts[row.get("reviewer_tag", "unclear")] = tag_counts.get(row.get("reviewer_tag", "unclear"), 0) + 1

    lines: list[str] = []
    lines.append("## 分析范围")
    lines.append("")
    lines.append(f"- 样本评论数：{len(sample_rows)}")
    lines.append(f"- 覆盖平台：{', '.join(platforms) or '未知'}")
    lines.append(f"- 长评数：{longform_count}")
    lines.append(f"- 高信息密度评论数：{high_value_count}")
    lines.append("")

    lines.append("## 核心结论")
    lines.append("")
    for row in sentiment_rows:
        lines.append(
            f"- 平台 `{row.get('platform', '')}` 的情绪分布为：正向 `{ratio_percent(row.get('positive_ratio', '0'))}`、中性 `{ratio_percent(row.get('neutral_ratio', '0'))}`、负向 `{ratio_percent(row.get('negative_ratio', '0'))}`。"
        )
        lines.append(
            f"- 平台 `{row.get('platform', '')}` 的长评占比约 `{ratio_percent(row.get('longform_share', '0'))}`，具备实际体验迹象的评论占比约 `{ratio_percent(row.get('experience_based_share', '0'))}`。"
        )
    if topic_rows:
        top_topic = max(topic_rows, key=lambda row: parse_int(row.get("mention_count", "0")))
        lines.append(f"- 当前最集中讨论的主题是“{topic_to_zh(top_topic.get('topic_label', ''))}”，提及占比约 `{ratio_percent(top_topic.get('mention_ratio', '0'))}`。")
    lines.append(f"- 样本中带有直接体验迹象的评论共有 `{firsthand_count}` 条，说明本 section 有一定实玩反馈基础，但仍不能替代全量玩家画像。")
    lines.append("")

    lines.append("## 平台覆盖与样本结构")
    lines.append("")
    lines.append("- 该 section 当前会同时保留长评、高点赞评论和带实玩痕迹的评论，以提升诊断价值。")
    lines.append("- 主页评价比官方视频评论更适合识别具体痛点，但也会放大长评作者和高参与用户的声音。")
    if tag_counts:
        lines.append("- 评论者类型分布：" + "、".join(f"`{tag}`={count}" for tag, count in sorted(tag_counts.items())) + "。")
    lines.append("")

    lines.append("## 高频主题观察")
    lines.append("")
    for row in top_rows(topic_rows, "mention_count", limit=6):
        lines.append(
            f"- “{topic_to_zh(row.get('topic_label', ''))}”：出现 `{row.get('mention_count', '0')}` 次，占比 `{ratio_percent(row.get('mention_ratio', '0'))}`，主题内正向比例 `{ratio_percent(row.get('positive_ratio_within_topic', '0'))}`，主题内负向比例 `{ratio_percent(row.get('negative_ratio_within_topic', '0'))}`。"
        )
    lines.append("")

    lines.append("## 长评与高价值评论摘录")
    lines.append("")
    for row in top_evidence_rows(evidence_rows, limit=5):
        lines.append(f"- “{topic_to_zh(row.get('topic_label', ''))}”：{row.get('quote_original', '')}")
    lines.append("")

    lines.append("## 正向信号")
    lines.append("")
    positive_rows = top_evidence_by_sentiment(evidence_rows, "positive")
    if positive_rows:
        for row in positive_rows:
            lines.append(f"- “{topic_to_zh(row.get('topic_label', ''))}”：{row.get('quote_original', '')}")
    else:
        lines.append("- 本轮没有识别出足够强的正向高价值评论。")
    lines.append("")

    lines.append("## 负向信号与风险点")
    lines.append("")
    negative_rows = top_evidence_by_sentiment(evidence_rows, "negative")
    if negative_rows:
        for row in negative_rows:
            lines.append(f"- “{topic_to_zh(row.get('topic_label', ''))}”：{row.get('quote_original', '')}")
    else:
        lines.append("- 当前负向高价值评论偏少，但这不代表风险不存在，应继续结合长评和后续测试跟踪。")
    lines.append("")

    lines.append("## 与官方视频评论的关系")
    lines.append("")
    for line in compare_with_section_2(project_dir):
        lines.append(line)
    lines.append("- 一般来说，主页评价更容易暴露具体交互、养成、优化问题，适合作为对官方评论的二次验证。")
    lines.append("")

    lines.append("## 置信度与局限")
    lines.append("")
    lines.append("- 本 section 仍采用规则驱动的情绪、主题、玩家标签推断，结果应作为分析辅助。")
    lines.append("- 长评和高赞评论天然会放大更愿意表达的用户，不能直接等同于整体口碑。")
    lines.append("- 后续建议继续扩大 TapTap 长评和 B 站 useful 评论的覆盖率，并将一条长评拆解为多个原子观点。")
    lines.append("")
    return "\n".join(lines)


def run() -> None:
    args = parse_args()
    project_dir = Path(args.project_dir)
    section_dir = project_dir / args.section_dir
    registry_rows = read_csv_rows(section_dir / "review_registry.csv")
    sample_rows = read_csv_rows(section_dir / "review_sample.csv")
    tag_rows = read_csv_rows(section_dir / "reviewer_tags.csv")
    sentiment_rows = read_csv_rows(section_dir / "sentiment_summary.csv")
    topic_rows = read_csv_rows(section_dir / "topic_summary.csv")
    evidence_rows = build_evidence_rows(registry_rows, sample_rows, tag_rows)
    findings_md = build_findings_markdown(project_dir, registry_rows, sample_rows, tag_rows, sentiment_rows, topic_rows, evidence_rows)
    write_csv_rows(section_dir / "evidence_table.csv", EVIDENCE_TABLE_HEADER, evidence_rows)
    (section_dir / "findings.md").write_text(findings_md, encoding="utf-8")
    print(f"已在 {section_dir} 写入 {len(evidence_rows)} 条 Section 3 证据和 findings.md")


if __name__ == "__main__":
    run()
