from __future__ import annotations

import argparse
import csv
from pathlib import Path
import importlib

reporting_utils = importlib.import_module("reporting_utils")
ratio_percent = reporting_utils.ratio_percent
topic_to_zh = reporting_utils.topic_to_zh


EVIDENCE_TABLE_HEADER = [
    "evidence_id",
    "source_id",
    "claim_or_observation",
    "evidence_type",
    "quote_original",
    "quote_translated",
    "topic_label",
    "sentiment_label",
    "milestone",
    "strength",
    "risk_note",
]

MILESTONE_DELTA_HEADER = [
    "from_milestone",
    "to_milestone",
    "topic_label",
    "direction",
    "observed_change",
    "likely_driver",
    "confidence_level",
    "supporting_evidence_ids",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="整理 Section 2 官方视频评论分析输出。")
    parser.add_argument("--project-dir", required=True, help="项目目录")
    parser.add_argument("--section-dir", default="section_2_official_video_comments", help="Section 2 目录")
    return parser.parse_args()


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise SystemExit(f"缺少必需文件：{path}")
    with path.open("r", newline="", encoding="utf-8") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def write_csv_rows(path: Path, header: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=header)
        writer.writeheader()
        writer.writerows(rows)


def parse_int(value: str) -> int:
    try:
        return int(value)
    except ValueError:
        return 0


def parse_float(value: str) -> float:
    try:
        return float(value)
    except ValueError:
        return 0.0


def strength_from_likes(likes: int) -> str:
    if likes >= 50:
        return "strong"
    if likes >= 10:
        return "medium"
    return "weak"


def build_video_maps(video_rows: list[dict[str, str]]) -> tuple[dict[str, dict[str, str]], dict[str, str]]:
    return {row.get("video_id", ""): row for row in video_rows}, {row.get("video_id", ""): row.get("milestone_id", "") for row in video_rows}


def build_evidence_rows(comment_rows: list[dict[str, str]], milestone_map: dict[str, str], video_map: dict[str, dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[tuple[str, str, str], list[dict[str, str]]] = {}
    for row in comment_rows:
        if row.get("is_spam_or_noise") == "true":
            continue
        key = (row.get("video_id", ""), row.get("topic_label", "uncategorized"), row.get("sentiment_label", "neutral"))
        grouped.setdefault(key, []).append(row)

    evidence_rows: list[dict[str, str]] = []
    for (video_id, topic_label, sentiment_label), rows in sorted(grouped.items()):
        representative = max(rows, key=lambda row: parse_int(row.get("likes", "0")))
        likes = parse_int(representative.get("likes", "0"))
        title = video_map.get(video_id, {}).get("title", video_id)
        evidence_rows.append(
            {
                "evidence_id": f"s2_{video_id}_{representative.get('comment_id', '')}",
                "source_id": f"s2_{video_id}",
                "claim_or_observation": f"《{title}》中关于“{topic_to_zh(topic_label)}”的代表性{sentiment_label}评论",
                "evidence_type": "player_opinion",
                "quote_original": representative.get("text_original", ""),
                "quote_translated": "",
                "topic_label": topic_label,
                "sentiment_label": sentiment_label,
                "milestone": milestone_map.get(video_id, ""),
                "strength": strength_from_likes(likes),
                "risk_note": f"likes={likes}; is_top_comment={representative.get('is_top_comment', 'false')}",
            }
        )
    return evidence_rows


def representative_evidence_map(evidence_rows: list[dict[str, str]]) -> dict[tuple[str, str], str]:
    return {(row.get("source_id", "").removeprefix("s2_"), row.get("topic_label", "")): row.get("evidence_id", "") for row in evidence_rows}


def sorted_milestones(video_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return sorted(video_rows, key=lambda row: row.get("publish_date", ""))


def build_milestone_deltas(video_rows: list[dict[str, str]], topic_rows: list[dict[str, str]], evidence_lookup: dict[tuple[str, str], str]) -> list[dict[str, str]]:
    if len(video_rows) < 2:
        return []
    topic_by_video: dict[str, dict[str, dict[str, str]]] = {}
    for row in topic_rows:
        topic_by_video.setdefault(row.get("video_id", ""), {})[row.get("topic_label", "")] = row
    deltas: list[dict[str, str]] = []
    ordered = sorted_milestones(video_rows)
    for index in range(len(ordered) - 1):
        current = ordered[index]
        nxt = ordered[index + 1]
        current_video = current.get("video_id", "")
        next_video = nxt.get("video_id", "")
        for topic in sorted(set(topic_by_video.get(current_video, {})) | set(topic_by_video.get(next_video, {}))):
            current_ratio = parse_float(topic_by_video.get(current_video, {}).get(topic, {}).get("mention_ratio", "0"))
            next_ratio = parse_float(topic_by_video.get(next_video, {}).get(topic, {}).get("mention_ratio", "0"))
            if abs(next_ratio - current_ratio) < 0.0001:
                continue
            deltas.append(
                {
                    "from_milestone": current.get("milestone_id", ""),
                    "to_milestone": nxt.get("milestone_id", ""),
                    "topic_label": topic,
                    "direction": "上升" if next_ratio > current_ratio else "下降",
                    "observed_change": f"讨论占比 {ratio_percent(str(current_ratio))} -> {ratio_percent(str(next_ratio))}",
                    "likely_driver": "需结合版本变化人工复核",
                    "confidence_level": "中",
                    "supporting_evidence_ids": "; ".join(filter(None, [evidence_lookup.get((current_video, topic), ""), evidence_lookup.get((next_video, topic), "")])),
                }
            )
    return deltas


def topic_label_cn(topic_label: str) -> str:
    mapping = {
        "technical_quality": "技术/性能/优化",
        "monetization_anxiety": "商业化/抽卡焦虑",
        "art_visual_identity": "美术/画面/场景",
        "gameplay_loop": "玩法/战斗/操作",
        "world_setting": "题材/世界观/剧情",
        "innovation_sameness": "竞品比较/同质化",
        "trust_in_progress": "开发进度/打磨信任",
        "noise_or_meme": "玩梗/噪声信息",
        "uncategorized": "其他",
    }
    if topic_label in mapping:
        return mapping[topic_label]
    translated = topic_to_zh(topic_label)
    return translated if translated else topic_label


def ratio_text(numerator: int, denominator: int) -> str:
    if denominator <= 0:
        return "0.0%"
    return ratio_percent(f"{numerator / denominator:.4f}")


def build_platform_findings_section(
    platform_key: str,
    platform_title: str,
    platform_video_ids: set[str],
    comment_rows: list[dict[str, str]],
    topic_rows: list[dict[str, str]],
) -> tuple[list[str], dict[str, str]]:
    rows = [row for row in comment_rows if row.get("video_id", "") in platform_video_ids and row.get("is_spam_or_noise") != "true"]
    platform_topic_rows = [row for row in topic_rows if row.get("video_id", "") in platform_video_ids]

    sentiment_order = [("positive", "正面"), ("neutral", "中性"), ("negative", "负面")]
    sentiment_counts = {label: 0 for label, _ in sentiment_order}
    sentiment_likes = {label: 0 for label, _ in sentiment_order}
    total_comments = len(rows)
    total_likes = 0
    for row in rows:
        sentiment = row.get("sentiment_label", "neutral")
        likes = parse_int(row.get("likes", "0"))
        total_likes += likes
        if sentiment in sentiment_counts:
            sentiment_counts[sentiment] += 1
            sentiment_likes[sentiment] += likes

    topic_stats: dict[str, dict[str, float]] = {}
    for row in platform_topic_rows:
        topic_label = row.get("topic_label", "uncategorized")
        mention_count = parse_int(row.get("mention_count", "0"))
        positive_ratio = parse_float(row.get("positive_ratio_within_topic", "0"))
        negative_ratio = parse_float(row.get("negative_ratio_within_topic", "0"))
        stats = topic_stats.setdefault(
            topic_label,
            {
                "mention_count": 0,
                "positive_est": 0.0,
                "negative_est": 0.0,
                "likes_total": 0,
                "positive_count": 0,
                "negative_count": 0,
            },
        )
        stats["mention_count"] += mention_count
        stats["positive_est"] += mention_count * positive_ratio
        stats["negative_est"] += mention_count * negative_ratio

    for row in rows:
        topic_label = row.get("topic_label", "uncategorized")
        stats = topic_stats.setdefault(
            topic_label,
            {
                "mention_count": 0,
                "positive_est": 0.0,
                "negative_est": 0.0,
                "likes_total": 0,
                "positive_count": 0,
                "negative_count": 0,
            },
        )
        likes = parse_int(row.get("likes", "0"))
        stats["likes_total"] += likes
        if row.get("sentiment_label") == "positive":
            stats["positive_count"] += 1
        if row.get("sentiment_label") == "negative":
            stats["negative_count"] += 1

    positive_topic_ranking = sorted(
        [
            (topic, stats)
            for topic, stats in topic_stats.items()
            if topic != "noise_or_meme" and int(stats["positive_count"]) > 0
        ],
        key=lambda item: (item[1]["likes_total"], item[1]["positive_count"]),
        reverse=True,
    )
    negative_topic_ranking = sorted(
        [
            (topic, stats)
            for topic, stats in topic_stats.items()
            if topic != "noise_or_meme" and int(stats["negative_count"]) > 0
        ],
        key=lambda item: (item[1]["likes_total"], item[1]["negative_count"]),
        reverse=True,
    )

    buy_in_topics = [topic_label_cn(topic) for topic, _ in positive_topic_ranking[:3]]
    challenge_topics = [topic_label_cn(topic) for topic, _ in negative_topic_ranking[:3]]

    positive_exemplars: dict[str, dict[str, str]] = {}
    negative_exemplars: dict[str, dict[str, str]] = {}
    for row in rows:
        topic_label = row.get("topic_label", "uncategorized")
        if topic_label == "noise_or_meme":
            continue
        sentiment = row.get("sentiment_label", "neutral")
        likes = parse_int(row.get("likes", "0"))
        if sentiment == "positive":
            current = positive_exemplars.get(topic_label)
            if current is None or likes > parse_int(current.get("likes", "0")):
                positive_exemplars[topic_label] = row
        elif sentiment == "negative":
            current = negative_exemplars.get(topic_label)
            if current is None or likes > parse_int(current.get("likes", "0")):
                negative_exemplars[topic_label] = row

    lines: list[str] = []
    lines.append(f"## {platform_title}视频评论区情绪分析【评论样本量：{total_comments}】")
    lines.append("")
    lines.append("### 1. 总体情绪分布")
    lines.append("")
    lines.append("| 情绪 | 评论数 | 评论占比 | 点赞总数 | 点赞占比 | 平均点赞/条 |")
    lines.append("|------|--------|----------|----------|----------|------------|")
    for sentiment_key, sentiment_cn in sentiment_order:
        count = sentiment_counts[sentiment_key]
        likes = sentiment_likes[sentiment_key]
        comment_ratio = ratio_text(count, total_comments)
        like_ratio = ratio_text(likes, total_likes)
        avg_likes = f"{(likes / count):.2f}" if count > 0 else "0.00"
        lines.append(f"| {sentiment_cn} | {count} | {comment_ratio} | {likes} | {like_ratio} | {avg_likes} |")

    if total_comments == 0:
        sentiment_takeaway = "当前平台暂无可用评论样本，无法形成稳定情绪判断。"
    else:
        dominant_by_count = max(sentiment_order, key=lambda item: sentiment_counts[item[0]])
        dominant_by_likes = max(sentiment_order, key=lambda item: sentiment_likes[item[0]])
        sentiment_takeaway = (
            f"评论区按数量看以{dominant_by_count[1]}为主，"
            f"但点赞权重更集中在{dominant_by_likes[1]}观点，说明高共鸣内容与整体发言分布并不完全一致。"
        )
    lines.append("")
    lines.append(f"- {sentiment_takeaway}")
    lines.append("")

    lines.append("### 2. 游戏设计相关讨论焦点")
    lines.append("")
    lines.append("| 讨论维度 | 提及次数 | 评论覆盖率 | 正面占比 | 负面占比 | 点赞总数 |")
    lines.append("|----------|----------|------------|----------|----------|----------|")

    ranked_topics = sorted(
        [item for item in topic_stats.items() if item[0] != "noise_or_meme" and int(item[1]["mention_count"]) > 0],
        key=lambda item: (item[1]["mention_count"], item[1]["likes_total"]),
        reverse=True,
    )
    for topic_label, stats in ranked_topics[:8]:
        mention_count = int(stats["mention_count"])
        positive_est = float(stats["positive_est"])
        negative_est = float(stats["negative_est"])
        positive_ratio = ratio_percent(f"{(positive_est / mention_count):.4f}") if mention_count > 0 else "0.0%"
        negative_ratio = ratio_percent(f"{(negative_est / mention_count):.4f}") if mention_count > 0 else "0.0%"
        lines.append(
            f"| {topic_label_cn(topic_label)} | {mention_count} | {ratio_text(mention_count, total_comments)} | {positive_ratio} | {negative_ratio} | {int(stats['likes_total'])} |"
        )

    best_text = " + ".join(buy_in_topics) if buy_in_topics else "暂无明显高共鸣正向维度"
    risk_text = " + ".join(challenge_topics) if challenge_topics else "暂无明显高共鸣负向维度"
    lines.append("")
    lines.append(f"- 评论区最买账的是 \"{best_text}\"；最容易引发挑刺的是 \"{risk_text}\"。")
    lines.append("")

    lines.append("### 3. 典型正面观点")
    lines.append("")
    if positive_topic_ranking:
        for topic_label, _ in positive_topic_ranking[:3]:
            exemplar = positive_exemplars.get(topic_label)
            if exemplar is None:
                continue
            quote = exemplar.get("text_original", "").strip().replace("\n", " ")
            likes = parse_int(exemplar.get("likes", "0"))
            lines.append(f"- **{topic_label_cn(topic_label)}**：该维度存在稳定正向反馈，讨论重心集中在玩法预期与观感认可。")
            lines.append(f"  \"{quote}\"（{likes}赞）")
    else:
        lines.append("- 暂无可提炼的典型正面观点。")
    lines.append("")

    lines.append("### 4. 典型负面观点/担忧点")
    lines.append("")
    lines.append("| 议题 | 评论数 | 占负面比例 | 点赞总数 |")
    lines.append("|------|--------|-----------|----------|")
    total_negative = sentiment_counts["negative"]
    for topic_label, stats in negative_topic_ranking[:5]:
        negative_count = int(stats["negative_count"])
        lines.append(
            f"| {topic_label_cn(topic_label)} | {negative_count} | {ratio_text(negative_count, total_negative)} | {int(stats['likes_total'])} |"
        )

    if negative_topic_ranking:
        lines.append("")
        for topic_label, _ in negative_topic_ranking[:3]:
            exemplar = negative_exemplars.get(topic_label)
            if exemplar is None:
                continue
            quote = exemplar.get("text_original", "").strip().replace("\n", " ")
            likes = parse_int(exemplar.get("likes", "0"))
            lines.append(f"- **{topic_label_cn(topic_label)}**：该维度的担忧主要围绕体验风险与兑现不确定性。")
            lines.append(f"  \"{quote}\"（{likes}赞）")
    else:
        lines.append("")
        lines.append("- 暂无可提炼的典型负面观点。")
    lines.append("")

    core = {
        "sample_size": str(total_comments),
        "dominant_count": max(sentiment_order, key=lambda item: sentiment_counts[item[0]])[1] if total_comments else "无",
        "dominant_likes": max(sentiment_order, key=lambda item: sentiment_likes[item[0]])[1] if total_comments else "无",
        "buy_in": best_text,
        "challenge": risk_text,
    }
    _ = platform_key
    return lines, core


def build_findings_markdown(
    video_rows: list[dict[str, str]],
    comment_rows: list[dict[str, str]],
    sentiment_rows: list[dict[str, str]],
    topic_rows: list[dict[str, str]],
    evidence_rows: list[dict[str, str]],
    delta_rows: list[dict[str, str]],
) -> str:
    _ = sentiment_rows
    _ = evidence_rows
    video_platform_map = {row.get("video_id", ""): row.get("platform", "").strip().casefold() for row in video_rows}
    bilibili_video_ids = {video_id for video_id, platform in video_platform_map.items() if platform == "bilibili"}
    youtube_video_ids = {video_id for video_id, platform in video_platform_map.items() if platform == "youtube"}

    bilibili_lines, bilibili_core = build_platform_findings_section(
        "bilibili", "B站", bilibili_video_ids, comment_rows, topic_rows
    )
    youtube_lines, youtube_core = build_platform_findings_section(
        "youtube", "YouTube", youtube_video_ids, comment_rows, topic_rows
    )

    lines: list[str] = []
    lines.append("## 核心结论")
    lines.append("")
    lines.append(
        f"- B站整体反馈：按评论数量看以{bilibili_core['dominant_count']}为主，但点赞权重更偏向{bilibili_core['dominant_likes']}，高共鸣观点与总体分布存在结构性差异。"
    )
    lines.append(
        f"- B站评论区最买账的是 \"{bilibili_core['buy_in']}\"；最容易引发挑刺的是 \"{bilibili_core['challenge']}\"。"
    )
    lines.append(
        f"- YouTube整体反馈：按评论数量看以{youtube_core['dominant_count']}为主，但点赞权重更偏向{youtube_core['dominant_likes']}，讨论更集中在高共鸣少数观点。"
    )
    lines.append(
        f"- YouTube正面观点集中在{youtube_core['buy_in']}，负面观点集中在{youtube_core['challenge']}。"
    )
    lines.append("")

    lines.extend(bilibili_lines)
    lines.extend(youtube_lines)

    milestones = sorted({row.get("milestone_id", "") for row in video_rows if row.get("milestone_id", "")})
    if len(milestones) > 1:
        lines.append("## 里程碑变化")
        lines.append("")
        if delta_rows:
            for row in delta_rows[:10]:
                lines.append(
                    f"- 从 `{row.get('from_milestone', '')}` 到 `{row.get('to_milestone', '')}`，\"{topic_label_cn(row.get('topic_label', ''))}\"{row.get('direction', '')}，{row.get('observed_change', '')}。"
                )
        else:
            lines.append("- 当前样本不足以形成稳定的跨里程碑变化判断。")
        lines.append("")

    lines.append("## 分析限制与后续建议")
    lines.append("")
    lines.append("- 本报告的情绪与主题标签来自规则与关键词映射，应作为定性线索而非因果结论。")
    lines.append("- 高赞评论天然放大少数强观点，建议与中低赞样本、社区长帖和媒体评测交叉验证。")
    lines.append("- 建议下一轮按\"角色、美术、玩法、性能、商业化、同质化\"六类维度做定向深挖并补充人工复核。")
    lines.append("")
    return "\n".join(lines)


def run() -> None:
    args = parse_args()
    section_dir = Path(args.project_dir) / args.section_dir
    video_rows = read_csv_rows(section_dir / "video_registry.csv")
    comment_rows = read_csv_rows(section_dir / "comment_sample.csv")
    sentiment_rows = read_csv_rows(section_dir / "sentiment_summary.csv")
    topic_rows = read_csv_rows(section_dir / "topic_summary.csv")
    video_map, milestone_map = build_video_maps(video_rows)
    evidence_rows = build_evidence_rows(comment_rows, milestone_map, video_map)
    evidence_lookup = representative_evidence_map(evidence_rows)
    delta_rows = build_milestone_deltas(video_rows, topic_rows, evidence_lookup)
    findings_md = build_findings_markdown(video_rows, comment_rows, sentiment_rows, topic_rows, evidence_rows, delta_rows)
    write_csv_rows(section_dir / "evidence_table.csv", EVIDENCE_TABLE_HEADER, evidence_rows)
    write_csv_rows(section_dir / "milestone_delta.csv", MILESTONE_DELTA_HEADER, delta_rows)
    (section_dir / "findings.md").write_text(findings_md, encoding="utf-8")
    print(f"已在 {section_dir} 写入 {len(evidence_rows)} 条 Section 2 证据、{len(delta_rows)} 条里程碑变化和 findings.md")


if __name__ == "__main__":
    run()
