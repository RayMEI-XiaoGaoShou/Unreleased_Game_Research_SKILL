from __future__ import annotations

import re
from pathlib import Path


TOPIC_LABEL_ZH = {
    "uncategorized": "其他高频讨论",
    "technical_quality": "技术表现与优化",
    "technical quality / optimization": "技术表现与优化",
    "art_visual_identity": "美术与视觉识别",
    "art and atmosphere": "美术与氛围",
    "gameplay_loop": "核心玩法循环",
    "gameplay loop": "核心玩法循环",
    "combat and feel": "交互体验与战斗手感",
    "combat depth and feel": "交互体验与战斗手感",
    "progression and retention": "养成与长期留存",
    "exploration and world density": "探索与世界密度",
    "content depth / endgame concern": "内容深度与后期空间",
    "differentiation vs competitors": "差异化与竞品对比",
    "onboarding / UX": "新手引导与界面体验",
    "monetization concern": "商业化与付费焦虑",
    "monetization_anxiety": "商业化与付费焦虑",
    "monetization anxiety": "商业化与付费焦虑",
    "innovation_sameness": "创新度与同质化",
    "innovation vs sameness": "创新度与同质化",
    "theme_plot": "题材与叙事表达",
    "theme / plot": "题材与叙事表达",
    "ip adaptation": "IP还原与改编",
    "content ceiling / longevity": "内容天花板与长线运营",
    "exploration and world interaction": "探索与世界密度",
}

DIMENSION_LABELS = {
    "题材与定位": {"theme_plot", "theme / plot", "differentiation vs competitors", "ip adaptation"},
    "美术与视听": {"art_visual_identity", "art and atmosphere"},
    "交互体验与战斗": {"combat and feel", "combat depth and feel", "onboarding / UX"},
    "核心玩法与内容循环": {"gameplay_loop", "gameplay loop", "exploration and world density", "content depth / endgame concern", "content ceiling / longevity"},
    "商业化与成长压力": {"progression and retention", "monetization concern", "monetization_anxiety"},
    "技术表现与优化": {"technical_quality", "technical quality / optimization"},
    "市场讨论与竞品比较": {"innovation_sameness", "differentiation vs competitors", "uncategorized"},
}

SENTIMENT_LABEL_ZH = {
    "positive": "正向",
    "negative": "负向",
    "neutral": "中性",
    "mixed": "分歧",
}

CONFIDENCE_LABEL_ZH = {
    "high": "高",
    "medium": "中",
    "low": "低",
    "unknown": "未知",
}


def topic_to_zh(topic_label: str) -> str:
    return TOPIC_LABEL_ZH.get(topic_label.strip(), topic_label.strip() or "未分类")


def sentiment_to_zh(sentiment_label: str) -> str:
    return SENTIMENT_LABEL_ZH.get(sentiment_label.strip(), sentiment_label.strip() or "未知")


def confidence_to_zh(confidence_label: str) -> str:
    return CONFIDENCE_LABEL_ZH.get(confidence_label.strip(), confidence_label.strip() or "未知")


def strip_bullet_prefix(text: str) -> str:
    stripped = text.strip()
    stripped = re.sub(r"^[-*]\s+", "", stripped)
    stripped = re.sub(r"^\d+\.\s+", "", stripped)
    return stripped.strip()


def markdown_section_text(file_path: Path, section_header: str) -> list[str]:
    if not file_path.exists():
        return []
    content = file_path.read_text(encoding="utf-8")
    lines = content.splitlines()
    result: list[str] = []
    inside = False
    current_depth = 0
    target = section_header.strip().lower()
    for line in lines:
        match = re.match(r"^(#{2,3})\s+(.+)$", line)
        if match:
            depth = len(match.group(1))
            title = match.group(2).strip().lower()
            if not inside and target in title:
                inside = True
                current_depth = depth
                continue
            if inside and depth <= current_depth:
                break
        elif inside and line.strip():
            result.append(strip_bullet_prefix(line))
    return [line for line in result if line]


def infer_dimension(topic_label: str, fallback_text: str = "") -> str:
    normalized = topic_label.strip()
    for dimension, labels in DIMENSION_LABELS.items():
        if normalized in labels:
            return dimension
    text = fallback_text.lower()
    if any(word in text for word in ["美术", "画风", "氛围", "音乐", "视觉"]):
        return "美术与视听"
    if any(word in text for word in ["战斗", "手感", "交互", "锁敌", "打击感"]):
        return "交互体验与战斗"
    if any(word in text for word in ["商业化", "抽卡", "付费", "氪", "养成"]):
        return "商业化与成长压力"
    if any(word in text for word in ["优化", "卡顿", "掉帧", "性能", "bug"]):
        return "技术表现与优化"
    if any(word in text for word in ["剧情", "题材", "世界观", "叙事", "设定"]):
        return "题材与定位"
    if any(word in text for word in ["探索", "开放世界", "内容", "循环", "玩法"]):
        return "核心玩法与内容循环"
    return "市场讨论与竞品比较"


def ratio_percent(value: str) -> str:
    try:
        return f"{float(value) * 100:.1f}%"
    except ValueError:
        return "0.0%"
