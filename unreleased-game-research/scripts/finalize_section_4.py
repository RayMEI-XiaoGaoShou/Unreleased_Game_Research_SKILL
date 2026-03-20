from __future__ import annotations

import argparse
from pathlib import Path
import importlib

reporting_utils = importlib.import_module("reporting_utils")
topic_to_zh = reporting_utils.topic_to_zh
section_4_common = importlib.import_module("section_4_common")
EVIDENCE_TABLE_HEADER = section_4_common.EVIDENCE_TABLE_HEADER
derive_evidence_id = section_4_common.derive_evidence_id
derive_source_id = section_4_common.derive_source_id
ensure_section_files = section_4_common.ensure_section_files
merge_notes = section_4_common.merge_notes
parse_int = section_4_common.parse_int
read_csv_rows = section_4_common.read_csv_rows
write_csv_rows = section_4_common.write_csv_rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="整理 Section 4 创作者评测分析输出。")
    parser.add_argument("--project-dir", required=True, help="项目目录")
    parser.add_argument("--section-dir", default="section_4_creator_reviews", help="Section 4 目录")
    return parser.parse_args()


def strength_for_claim(final_assessment: str, confidence_level: str) -> str:
    if final_assessment == "strong_support" or confidence_level == "high":
        return "strong"
    if final_assessment in {"partial_support", "mixed_or_contested"} or confidence_level == "medium":
        return "medium"
    return "weak"


def build_evidence_rows(
    candidate_rows: list[dict[str, str]],
    selected_rows: list[dict[str, str]],
    transcript_rows: list[dict[str, str]],
    claim_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    candidate_by_video = {row.get("video_id", ""): row for row in candidate_rows}
    selected_by_video = {row.get("video_id", ""): row for row in selected_rows}
    transcript_by_video: dict[str, list[dict[str, str]]] = {}
    for row in transcript_rows:
        transcript_by_video.setdefault(row.get("video_id", ""), []).append(row)

    evidence_rows: list[dict[str, str]] = []
    for claim_row in claim_rows:
        video_id = claim_row.get("video_id", "")
        candidate_row = candidate_by_video.get(video_id, {})
        selected_row = selected_by_video.get(video_id, {})
        segment_id = ""
        for note_part in claim_row.get("notes", "").split(";"):
            note_part = note_part.strip()
            if note_part.startswith("segment_id="):
                segment_id = note_part.split("=", 1)[1].strip()
                break
        transcript_row = next((row for row in transcript_by_video.get(video_id, []) if row.get("segment_id", "") == segment_id), {})
        sentiment_label = transcript_row.get("supports_positive_or_negative", "neutral")
        if sentiment_label not in {"positive", "negative", "neutral"}:
            sentiment_label = "neutral"
        evidence_rows.append(
            {
                "evidence_id": derive_evidence_id(claim_row.get("claim_id", "")),
                "source_id": derive_source_id(candidate_row.get("platform", "unknown"), video_id, candidate_row.get("title", "")),
                "claim_or_observation": claim_row.get("claim_summary", ""),
                "evidence_type": "creator_opinion",
                "quote_original": transcript_row.get("quote_original", ""),
                "quote_translated": "",
                "topic_label": claim_row.get("topic_label", ""),
                "sentiment_label": sentiment_label,
                "milestone": "latest_test_phase",
                "strength": strength_for_claim(claim_row.get("final_assessment", ""), transcript_row.get("confidence_level", "low")),
                "risk_note": merge_notes(
                    selected_row.get("sponsorship_risk", "medium"),
                    selected_row.get("creator_credibility", "medium"),
                    transcript_row.get("visible_footage_support", "unclear"),
                    transcript_row.get("cross_source_support", "none"),
                ),
            }
        )
    return evidence_rows


def top_consensus(consensus_rows: list[dict[str, str]], consensus_type: str, limit: int = 4) -> list[dict[str, str]]:
    filtered = [row for row in consensus_rows if row.get("consensus_type") == consensus_type]
    return sorted(filtered, key=lambda row: parse_int(row.get("supporting_video_count", "0")), reverse=True)[:limit]


def rows_by_video(rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        grouped.setdefault(row.get("video_id", ""), []).append(row)
    return grouped


def findings_markdown(
    candidate_rows: list[dict[str, str]],
    selected_rows: list[dict[str, str]],
    profile_rows: list[dict[str, str]],
    transcript_rows: list[dict[str, str]],
    claim_rows: list[dict[str, str]],
    consensus_rows: list[dict[str, str]],
    evidence_rows: list[dict[str, str]],
) -> str:
    candidate_by_video = {row.get("video_id", ""): row for row in candidate_rows}
    profile_by_video: dict[str, dict[str, str]] = {}
    for row in selected_rows:
        creator_name = candidate_by_video.get(row.get("video_id", ""), {}).get("creator_name", "")
        platform = candidate_by_video.get(row.get("video_id", ""), {}).get("platform", "")
        profile = next((item for item in profile_rows if item.get("creator_name") == creator_name and item.get("platform") == platform), {})
        profile_by_video[row.get("video_id", "")] = profile

    claims_by_video = rows_by_video(claim_rows)
    segments_by_video = rows_by_video(transcript_rows)

    lines: list[str] = []
    lines.append("## 分析范围")
    lines.append("")
    lines.append(f"- 候选视频数：{len(candidate_rows)}")
    lines.append(f"- 最终入选视频数：{len(selected_rows)}")
    lines.append(f"- 转录片段数：{len(transcript_rows)}")
    lines.append(f"- 创作者画像数：{len(profile_rows)}")
    lines.append("")

    lines.append("## 核心结论")
    lines.append("")
    for row in top_consensus(consensus_rows, "consensus_positive"):
        lines.append(f"- 多位创作者对“{topic_to_zh(row.get('topic_label', ''))}”给出一致性正向判断，覆盖视频数 `{row.get('supporting_video_count', '0')}`。")
    for row in top_consensus(consensus_rows, "consensus_negative"):
        lines.append(f"- 多位创作者对“{topic_to_zh(row.get('topic_label', ''))}”反复提出风险，覆盖视频数 `{row.get('supporting_video_count', '0')}`。")
    if not top_consensus(consensus_rows, "consensus_positive") and not top_consensus(consensus_rows, "consensus_negative"):
        lines.append("- 当前创作者样本更像‘多角度体验报告’，共识存在但仍偏弱，需要更多视频样本增强稳定性。")
    lines.append("")

    lines.append("## 创作者样本画像")
    lines.append("")
    for row in selected_rows:
        video_id = row.get("video_id", "")
        candidate = candidate_by_video.get(video_id, {})
        profile = profile_by_video.get(video_id, {})
        lines.append(
            f"- 《{candidate.get('title', video_id)}》 / {candidate.get('creator_name', '未知创作者')}：可信度 `{row.get('creator_credibility', 'unknown')}`，"
            f"受众体量 `{row.get('audience_size_bucket', 'unknown')}`，商务风险 `{row.get('sponsorship_risk', 'unknown')}`，证据密度 `{profile.get('evidence_density', 'unknown')}`。"
        )
    lines.append("")

    lines.append("## 逐视频诊断")
    lines.append("")
    for row in selected_rows:
        video_id = row.get("video_id", "")
        candidate = candidate_by_video.get(video_id, {})
        video_claims = claims_by_video.get(video_id, [])
        video_segments = segments_by_video.get(video_id, [])
        lines.append(f"### 《{candidate.get('title', video_id)}》")
        lines.append(f"- 创作者：{candidate.get('creator_name', '未知')} | 平台：{candidate.get('platform', '未知')} | 发布时间：{candidate.get('publish_date', '未知')}")
        lines.append(f"- 入选理由：{row.get('selection_reason', '人工筛选')}。")
        lines.append(f"- 有效片段数：{len(video_segments)}；结构化观点数：{len(video_claims)}。")
        top_claims = video_claims[:4]
        if top_claims:
            lines.append("- 核心观点：")
            for claim in top_claims:
                lines.append(f"  - [{topic_to_zh(claim.get('topic_label', ''))}] {claim.get('claim_summary', '')}")
        quoted = [segment.get("quote_original", "") for segment in video_segments[:3] if segment.get("quote_original", "")]
        if quoted:
            lines.append("- 代表引文：")
            for quote in quoted:
                lines.append(f"  - {quote}")
        lines.append("")

    lines.append("## 跨视频共识")
    lines.append("")
    consensus_positive = top_consensus(consensus_rows, "consensus_positive")
    consensus_negative = top_consensus(consensus_rows, "consensus_negative")
    if consensus_positive:
        lines.append("- 一致性正向主题：")
        for row in consensus_positive:
            lines.append(f"  - {topic_to_zh(row.get('topic_label', ''))}（{row.get('supporting_video_count', '0')} 个视频支持）")
    if consensus_negative:
        lines.append("- 一致性风险主题：")
        for row in consensus_negative:
            lines.append(f"  - {topic_to_zh(row.get('topic_label', ''))}（{row.get('supporting_video_count', '0')} 个视频反复提及）")
    if not consensus_positive and not consensus_negative:
        lines.append("- 当前未出现强共识主题，说明创作者样本仍偏分散或观点仍在形成中。")
    lines.append("")

    lines.append("## 与 Section 2/3 的交叉验证")
    lines.append("")
    cross_supported = [row for row in transcript_rows if row.get("cross_source_support") != "none"]
    if cross_supported:
        for row in cross_supported[:6]:
            lines.append(
                f"- 主题“{topic_to_zh(row.get('topic_label', ''))}”在创作者评测中被提及，且与 `{row.get('cross_source_support', '')}` 存在交叉支持。"
            )
    else:
        lines.append("- 当前跨源自动对齐仍然偏弱，后续需要把 Section 2/3/4 的主题本体进一步统一。")
    lines.append("")

    lines.append("## 高价值证据摘录")
    lines.append("")
    for row in evidence_rows[:8]:
        lines.append(f"- “{topic_to_zh(row.get('topic_label', ''))}”：{row.get('quote_original', '')}")
    lines.append("")

    lines.append("## 置信度与局限")
    lines.append("")
    lines.append("- 创作者视频能提供系统级诊断，但无法直接代表广泛玩家分布。")
    lines.append("- 自动转录会损失口语细节，且不同视频对同一问题的展开深浅差异较大。")
    lines.append("- 若后续要进一步提高质量，建议为每个视频补‘视频 thesis / 风险点 / 关键证据 / 竞品对比’的单独结构化卡片。")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    project_dir = Path(args.project_dir).resolve()
    section_dir = ensure_section_files(project_dir)
    if args.section_dir != section_dir.name:
        section_dir = project_dir / args.section_dir

    candidate_rows = read_csv_rows(section_dir / "candidate_videos.csv")
    selected_rows = read_csv_rows(section_dir / "selected_videos.csv")
    profile_rows = read_csv_rows(section_dir / "creator_profiles.csv")
    transcript_rows = read_csv_rows(section_dir / "transcript_segments.csv")
    claim_rows = read_csv_rows(section_dir / "claim_evidence_map.csv")
    consensus_rows = read_csv_rows(section_dir / "topic_consensus.csv")
    if not selected_rows or not transcript_rows or not claim_rows:
        raise SystemExit("Section 4 finalize 需要 selected_videos.csv、transcript_segments.csv 和 claim_evidence_map.csv。")

    evidence_rows = build_evidence_rows(candidate_rows, selected_rows, transcript_rows, claim_rows)
    findings_md = findings_markdown(candidate_rows, selected_rows, profile_rows, transcript_rows, claim_rows, consensus_rows, evidence_rows)
    write_csv_rows(section_dir / "evidence_table.csv", EVIDENCE_TABLE_HEADER, evidence_rows)
    (section_dir / "findings.md").write_text(findings_md, encoding="utf-8")
    print(f"已在 {section_dir} 写入 {len(evidence_rows)} 条 Section 4 证据和 findings.md")


if __name__ == "__main__":
    main()
