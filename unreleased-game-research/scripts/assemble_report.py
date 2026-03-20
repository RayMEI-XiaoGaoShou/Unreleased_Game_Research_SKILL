from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import importlib

reporting_utils = importlib.import_module("reporting_utils")
confidence_to_zh = reporting_utils.confidence_to_zh
infer_dimension = reporting_utils.infer_dimension
markdown_section_text = reporting_utils.markdown_section_text
strip_bullet_prefix = reporting_utils.strip_bullet_prefix
topic_to_zh = reporting_utils.topic_to_zh


@dataclass
class SectionSummary:
    section_id: int
    section_name: str
    findings_path: Path
    evidence_path: Path
    status: str = "缺失"
    confidence: str = "unknown"
    key_conclusions: list[str] = field(default_factory=list)
    positive_signals: list[str] = field(default_factory=list)
    negative_signals: list[str] = field(default_factory=list)


@dataclass
class DimensionBucket:
    name: str
    items: list[str] = field(default_factory=list)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="生成中文最终研究报告。")
    parser.add_argument("project_dir", help="项目目录")
    parser.add_argument("--output-dir", help="输出目录，默认为 project/synthesis")
    parser.add_argument("--skip-validation", action="store_true", help="跳过最终产物检查")
    return parser.parse_args()


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def summarize_section(project_dir: Path, section_id: int) -> SectionSummary:
    section_names = {
        1: ("section_1_public_intel", "Section 1 公开情报"),
        2: ("section_2_official_video_comments", "Section 2 官方视频评论"),
        3: ("section_3_homepage_reviews", "Section 3 主页与长评反馈"),
        4: ("section_4_creator_reviews", "Section 4 创作者评测"),
    }
    dir_name, section_name = section_names[section_id]
    findings_path = project_dir / dir_name / "findings.md"
    evidence_path = project_dir / dir_name / "evidence_table.csv"
    summary = SectionSummary(section_id, section_name, findings_path, evidence_path)
    if findings_path.exists():
        summary.status = "完成"
        summary.key_conclusions = markdown_section_text(findings_path, "核心结论") or markdown_section_text(findings_path, "Core Conclusions")
        summary.positive_signals = markdown_section_text(findings_path, "正向") or markdown_section_text(findings_path, "Positive Signals")
        summary.negative_signals = markdown_section_text(findings_path, "负向") or markdown_section_text(findings_path, "Negative")
        confidence_lines = markdown_section_text(findings_path, "置信") or markdown_section_text(findings_path, "Confidence")
        if confidence_lines:
            joined = " ".join(confidence_lines).lower()
            if "high" in joined or "高" in joined:
                summary.confidence = "high"
            elif "low" in joined or "低" in joined:
                summary.confidence = "low"
            else:
                summary.confidence = "medium"
        else:
            summary.confidence = "medium"
    return summary


def build_dimension_buckets(summaries: list[SectionSummary], project_dir: Path) -> list[DimensionBucket]:
    bucket_map = {
        name: DimensionBucket(name)
        for name in [
            "题材与定位",
            "美术与视听",
            "交互体验与战斗",
            "核心玩法与内容循环",
            "商业化与成长压力",
            "技术表现与优化",
            "市场讨论与竞品比较",
        ]
    }

    for summary in summaries:
        for text in summary.key_conclusions + summary.positive_signals + summary.negative_signals:
            clean = strip_bullet_prefix(text)
            bucket_map[infer_dimension("", clean)].items.append(f"[{summary.section_name}] {clean}")

    section_2_topics = read_csv_rows(project_dir / "section_2_official_video_comments" / "topic_summary.csv")
    section_3_topics = read_csv_rows(project_dir / "section_3_homepage_reviews" / "topic_summary.csv")

    for row in section_2_topics + section_3_topics:
        topic_label = row.get("topic_label", "")
        dimension = infer_dimension(topic_label, topic_to_zh(topic_label))
        item = f"[{topic_to_zh(topic_label)}] 提及占比 {row.get('mention_ratio', '') or row.get('positive_ratio_within_topic', '')}"
        bucket_map[dimension].items.append(item)

    # Section 4 now produces per-video .txt transcripts + Agent-written findings.md.
    # claim_evidence_map.csv is no longer generated; bucket items come from findings.md summaries above.

    return list(bucket_map.values())


def overall_confidence(summaries: list[SectionSummary]) -> str:
    score_map = {"high": 3, "medium": 2, "low": 1, "unknown": 1}
    valid = [summary for summary in summaries if summary.status == "完成"]
    if not valid:
        return "low"
    average = sum(score_map.get(summary.confidence, 1) for summary in valid) / len(valid)
    if average >= 2.5:
        return "high"
    if average >= 1.5:
        return "medium"
    return "low"


def write_executive_summary(output_path: Path, project_name: str, summaries: list[SectionSummary], buckets: list[DimensionBucket]) -> None:
    confidence = confidence_to_zh(overall_confidence(summaries))
    completed = [summary for summary in summaries if summary.status == "完成"]
    lines: list[str] = []
    lines.append(f"# {project_name}：执行摘要")
    lines.append("")
    lines.append(f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"整体置信度：{confidence}")
    lines.append(f"完成 section 数：{len(completed)}/{len(summaries)}")
    lines.append("")
    lines.append("## 总体判断")
    lines.append("")
    if completed:
        lines.append("- 当前报告已覆盖公开情报、官方视频评论、主页评价与创作者评测四类证据，可用于形成一版中高颗粒度的未上线游戏研判。")
    else:
        lines.append("- 当前项目尚未形成足够证据，无法输出有效判断。")
    lines.append("- 建议优先关注‘题材与定位、美术与视听、交互体验与战斗、核心玩法与内容循环、商业化与成长压力、技术表现与优化’六个维度的共识和分歧。")
    lines.append("")
    lines.append("## 维度级总结")
    lines.append("")
    for bucket in buckets:
        lines.append(f"### {bucket.name}")
        if bucket.items:
            for item in bucket.items[:5]:
                lines.append(f"- {item}")
        else:
            lines.append("- 当前证据不足。")
        lines.append("")
    lines.append("")
    lines.append("---")
    lines.append("## ⚠️ 【Agent 必须完成以下步骤，否则本报告视为未完成】")
    lines.append("")
    lines.append("上方「总体判断」与「维度级总结」是脚本自动生成的数据拼接，**不是最终分析内容**。")
    lines.append("")
    lines.append("作为 Agent，你现在必须：")
    lines.append("1. 读取本文件底部「Section 1~4 详析」中各 section 的完整 findings 内容。")
    lines.append("2. **删除**上方「总体判断」与「维度级总结」两节的所有脚本生成内容。")
    lines.append("3. **重新撰写**这两节，要求：")
    lines.append("   - 用专业分析师口吻，全部使用中文。")
    lines.append("   - 每个维度下，明确列出正面共识、负面共识、以及各 Section 间的矛盾或分歧点。")
    lines.append("   - 点名具体证据来源（如「Section 3 多位玩家提到…」「Section 4 创作者指出…」）。")
    lines.append("   - 字数不设上限，深度优先于简洁。")
    lines.append("4. 完成重写后，**删除本「⚠️ Agent 必须完成」提示块**，输出干净的最终版本。")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"[Synthesis] Written: {output_path}")


def section_block(summary: SectionSummary) -> str:
    if summary.status != "完成" or not summary.findings_path.exists():
        return "本节暂无可用内容。"
    return summary.findings_path.read_text(encoding="utf-8").strip()


def write_final_report(output_path: Path, project_name: str, summaries: list[SectionSummary], buckets: list[DimensionBucket]) -> None:
    confidence = confidence_to_zh(overall_confidence(summaries))
    lines: list[str] = []
    lines.append(f"# {project_name}：未上线游戏综合研究报告")
    lines.append("")
    lines.append(f"研究日期：{datetime.now().strftime('%Y-%m-%d')}")
    lines.append(f"整体置信度：{confidence}")
    lines.append("")
    lines.append("---")
    lines.append("## ⚠️ 【Agent 必须完成以下步骤，否则本报告视为未完成】")
    lines.append("")
    lines.append("上方「一、总结性判断」是脚本自动生成的数据拼接，**不是最终分析内容**。")
    lines.append("")
    lines.append("作为 Agent，你现在必须：")
    lines.append("1. 读取本文件「二~五」各 Section 详析中的完整 findings 内容。")
    lines.append("2. **删除**上方「一、总结性判断」中所有脚本生成的 bullet point 内容。")
    lines.append("3. **重新撰写**「一、总结性判断」，要求：")
    lines.append("   - 全部使用中文，用专业分析师口吻。")
    lines.append("   - 按「题材与定位 / 美术与视听 / 交互体验与战斗 / 核心玩法与内容循环 / 商业化与成长压力 / 技术表现与优化」六大维度逐一输出。")
    lines.append("   - 每个维度下列：正面共识、负面共识、Section 间的矛盾分歧（如「Section 2 评论区总体乐观，但 Section 3 内测玩家反馈截然不同」）。")
    lines.append("   - 具体引用证据来源（如「Section 4 创作者普遍指出……」）。")
    lines.append("4. 完成重写后，**删除本「⚠️ Agent 必须完成」提示块**，输出干净的最终版本。")
    lines.append("---")
    lines.append("")
    lines.append("## 一、总结性判断")
    lines.append("")
    lines.append("本报告先给出跨 section 的系统性整理，再附上 Section 1~4 的详细分析内容，以保证管理层摘要和分析师深读都可直接使用。")
    lines.append("")
    for bucket in buckets:
        lines.append(f"### {bucket.name}")
        if bucket.items:
            for item in bucket.items[:8]:
                lines.append(f"- {item}")
        else:
            lines.append("- 当前暂无足够证据。")
        lines.append("")
        
    lines.append("")
    lines.append("---")
    lines.append("> **[AGENT_ACTION_REQUIRED]**")
    lines.append("> 上述“一、总结性判断”为脚本生成的粗略拼接。作为 Agent，你必须阅读本报告后半部分的各 Section 详析，用专业分析师的口吻重写本章节，确保跨源数据的交叉验证与矛盾披露。")
    lines.append("---")
    lines.append("")
    lines.append("## 二、Section 1 公开情报详析")
    lines.append("")
    lines.append(section_block(next(summary for summary in summaries if summary.section_id == 1)))
    lines.append("")
    lines.append("## 三、Section 2 官方视频评论详析")
    lines.append("")
    lines.append(section_block(next(summary for summary in summaries if summary.section_id == 2)))
    lines.append("")
    lines.append("## 四、Section 3 主页与长评反馈详析")
    lines.append("")
    lines.append(section_block(next(summary for summary in summaries if summary.section_id == 3)))
    lines.append("")
    lines.append("## 五、Section 4 创作者评测详析")
    lines.append("")
    lines.append(section_block(next(summary for summary in summaries if summary.section_id == 4)))
    lines.append("")
    lines.append("## 六、附录：证据文件索引")
    lines.append("")
    for summary in summaries:
        if summary.evidence_path.exists():
            try:
                rel = summary.evidence_path.relative_to(output_path.parent.parent)
            except ValueError:
                rel = summary.evidence_path  # fallback to absolute path when --output-dir is outside project tree
            lines.append(f"- {summary.section_name}：`{rel}`")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"[Synthesis] Written: {output_path}")


def default_output_dir(project_dir: Path) -> Path:
    """Return <skill_root>/reports/<project_name>/ so the final reports sit
    parallel to 'projects/' and 'credentials/' for easy access."""
    skill_root = Path(__file__).resolve().parent.parent
    return skill_root / "reports" / project_dir.name


def main() -> None:
    args = parse_args()
    project_dir = Path(args.project_dir).resolve()
    if not project_dir.exists():
        raise SystemExit(f"项目目录不存在：{project_dir}")
    project_name = project_dir.name.replace("-", " ").replace("_", " ").title()
    print("=" * 60)
    print(f"ASSEMBLING FINAL REPORT: {project_name}")
    print("=" * 60)
    summaries = [summarize_section(project_dir, section_id) for section_id in [1, 2, 3, 4]]
    for summary in summaries:
        print(f"  {'OK' if summary.status == '完成' else 'MISS'} Section {summary.section_id}: {summary.status}")
    buckets = build_dimension_buckets(summaries, project_dir)
    output_dir = Path(args.output_dir).resolve() if args.output_dir else default_output_dir(project_dir)
    write_executive_summary(output_dir / "executive_summary.md", project_name, summaries, buckets)
    write_final_report(output_dir / "final_report.md", project_name, summaries, buckets)
    if not args.skip_validation:
        missing = [name for name in ["executive_summary.md", "final_report.md"] if not (output_dir / name).exists()]
        if missing:
            raise SystemExit("未生成完整的 synthesis 文件：" + ", ".join(missing))
        print("  OK Contract validation passed")
    print("=" * 60)
    print("SYNTHESIS COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
