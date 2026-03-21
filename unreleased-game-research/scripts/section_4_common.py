from __future__ import annotations

import csv
import json
import re
from pathlib import Path


SECTION_DIR_NAME = "section_4_creator_reviews"

CANDIDATE_VIDEOS_HEADER = [
    "video_id",
    "platform",
    "url",
    "title",
    "creator_name",
    "publish_date",
    "latest_test_relevance",
    "has_actual_judgment",
    "has_concrete_footage",
    "is_guide_like",
    "selection_status",
    "notes",
]

SELECTED_VIDEOS_HEADER = [
    "video_id",
    "selection_reason",
    "creator_credibility",
    "audience_size_bucket",
    "sponsorship_risk",
    "genre_familiarity_note",
    "stance_note",
]

CREATOR_PROFILES_HEADER = [
    "creator_name",
    "platform",
    "audience_size_bucket",
    "genre_relevance",
    "ip_relevance",
    "evidence_density",
    "balance_of_judgment",
    "sponsorship_risk",
    "credibility_rating",
    "notes",
]

TRANSCRIPT_SEGMENTS_HEADER = [
    "segment_id",
    "video_id",
    "timestamp_start",
    "timestamp_end",
    "quote_original",
    "quote_normalized",
    "topic_label",
    "claim_type",
    "supports_positive_or_negative",
    "visible_footage_support",
    "cross_source_support",
    "confidence_level",
]

CLAIM_EVIDENCE_MAP_HEADER = [
    "claim_id",
    "video_id",
    "creator_name",
    "claim_summary",
    "topic_label",
    "claim_type",
    "supported_by_footage",
    "supported_by_section_2",
    "supported_by_section_3",
    "contradicted_elsewhere",
    "final_assessment",
    "notes",
]

TOPIC_CONSENSUS_HEADER = [
    "topic_label",
    "consensus_type",
    "supporting_video_count",
    "contradicting_video_count",
    "representative_claim_ids",
    "confidence_level",
]

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

SOURCE_REGISTRY_HEADER = [
    "source_id",
    "section_id",
    "platform",
    "source_type",
    "url",
    "title",
    "author_or_channel",
    "publish_date",
    "language",
    "official_status",
    "reliability_score",
    "bias_risk",
    "access_method",
    "capture_status",
    "notes",
]

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

POSITIVE_KEYWORDS = [
    "good",
    "great",
    "love",
    "promising",
    "solid",
    "strong",
    "fun",
    "smooth",
    "impressive",
    "interesting",
    "喜欢",
    "不错",
    "期待",
    "优秀",
    "惊艳",
    "流畅",
    "扎实",
    "有趣",
    "舒服",
    "香",
]

NEGATIVE_KEYWORDS = [
    "bad",
    "weak",
    "worried",
    "concern",
    "disappointed",
    "lag",
    "clunky",
    "generic",
    "grindy",
    "empty",
    "boring",
    "差",
    "担心",
    "失望",
    "一般",
    "不行",
    "换皮",
    "氪",
    "空",
    "重复",
    "卡",
    "弱",
]

TOPIC_RULES = {
    "gameplay loop": ["loop", "循环", "核心玩法", "daily", "core gameplay", "looping"],
    "combat depth and feel": ["combat", "fight", "battle", "手感", "战斗", "技能", "boss"],
    "exploration and world density": ["exploration", "world", "地图", "探索", "开放世界", "密度"],
    "progression and retention": ["progression", "retention", "成长", "养成", "留存", "daily"],
    "technical quality / optimization": ["optimization", "performance", "fps", "stutter", "lag", "优化", "卡", "bug"],
    "art and atmosphere": ["art", "visual", "atmosphere", "音乐", "美术", "画风", "氛围"],
    "IP adaptation": ["ip", "franchise", "faithful", "还原", "原作", "设定"],
    "onboarding / UX": ["onboarding", "ux", "ui", "tutorial", "新手", "引导", "菜单"],
    "monetization concern": ["monetization", "gacha", "pay to win", "氪", "抽卡", "付费"],
    "content ceiling / longevity": ["endgame", "content", "long-term", "longevity", "后期", "耐玩", "内容"],
    "differentiation vs competitors": ["compare", "competitor", "同类", "竞品", "benchmark", "vs"],
}

CLAIM_TYPE_RULES = {
    "recommendation": ["recommend", "should play", "值得", "建议", "入坑", "skip", "不推荐"],
    "prediction": ["likely", "probably", "会不会", "估计", "未来", "上线后", "预测"],
    "market_comparison": ["compared to", "versus", "vs", "像", "对比", "同类", "竞品"],
    "hands_on_impression": ["i played", "after playing", "试玩", "我玩了", "上手", "体验下来", "内测"],
    "design_judgment": ["system", "loop", "design", "机制", "循环", "数值", "设计"],
}

SPONSORSHIP_KEYWORDS = [
    "sponsored",
    "sponsor",
    "paid promotion",
    "advertisement",
    "ad",
    "推广",
    "恰饭",
    "赞助",
    "商务合作",
]

GENRE_FAMILIARITY_KEYWORDS = [
    "genre",
    "同类",
    "竞品",
    "benchmark",
    "mmo",
    "open world",
    "二游",
    "开放世界",
    "gacha",
    "roguelike",
    "pokemon",
]


def ensure_csv(path: Path, header: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=header)
        writer.writeheader()


def ensure_section_files(project_dir: Path) -> Path:
    section_dir = project_dir / SECTION_DIR_NAME
    section_dir.mkdir(parents=True, exist_ok=True)
    ensure_csv(section_dir / "candidate_videos.csv", CANDIDATE_VIDEOS_HEADER)
    ensure_csv(section_dir / "selected_videos.csv", SELECTED_VIDEOS_HEADER)
    ensure_csv(section_dir / "creator_profiles.csv", CREATOR_PROFILES_HEADER)
    ensure_csv(section_dir / "evidence_table.csv", EVIDENCE_TABLE_HEADER)
    # transcript_segments.csv, claim_evidence_map.csv, topic_consensus.csv are
    # legacy artifacts from the pre-refactor CSV-first pipeline.
    # Current Section 4 produces per-video .txt files under generated_transcripts/.
    findings_path = section_dir / "findings.md"
    if not findings_path.exists():
        _ = findings_path.write_text(FINDINGS_TEMPLATE, encoding="utf-8")
    ensure_csv(project_dir / "sources" / "source_registry.csv", SOURCE_REGISTRY_HEADER)
    return section_dir


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise SystemExit(f"Required CSV not found: {path}")
    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return [dict(row) for row in reader]


def write_csv_rows(path: Path, header: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=header, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def read_csv_header(path: Path) -> set[str]:
    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        try:
            first_row = next(reader)
        except StopIteration as exc:
            raise SystemExit(f"CSV file is empty: {path}") from exc
    return {column.strip() for column in first_row}


def csv_has_data_rows(path: Path) -> bool:
    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        try:
            _ = next(reader)
        except StopIteration:
            raise SystemExit(f"CSV file is empty: {path}")
        for row in reader:
            if any(cell.strip() for cell in row):
                return True
    return False


def normalize_input_row(row: dict[str, object]) -> dict[str, str]:
    return {str(key): "" if value is None else str(value) for key, value in row.items()}


def load_input_rows(path: Path) -> list[dict[str, str]]:
    suffix = path.suffix.casefold()
    if suffix == ".csv":
        return read_csv_rows(path)
    if suffix in {".jsonl", ".ndjson"}:
        rows: list[dict[str, str]] = []
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                stripped = line.strip()
                if not stripped:
                    continue
                payload_object = json.loads(stripped)
                if not isinstance(payload_object, dict):
                    raise SystemExit(f"Expected object rows in {path}")
                rows.append(normalize_input_row({str(key): value for key, value in payload_object.items()}))
        return rows
    if suffix == ".json":
        payload_object = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload_object, list) or any(not isinstance(item, dict) for item in payload_object):
            raise SystemExit(f"Expected a list of objects in {path}")
        return [normalize_input_row({str(key): value for key, value in item.items()}) for item in payload_object]
    raise SystemExit(f"Unsupported input format: {path}")


def merge_rows_by_key(
    existing_rows: list[dict[str, str]],
    new_rows: list[dict[str, str]],
    key_name: str,
    header: list[str],
) -> list[dict[str, str]]:
    merged: dict[str, dict[str, str]] = {}
    ordered_keys: list[str] = []
    for row in existing_rows + new_rows:
        key_value = row.get(key_name, "")
        if not key_value:
            continue
        normalized_row = {column: row.get(column, "") for column in header}
        if key_value not in merged:
            ordered_keys.append(key_value)
        merged[key_value] = normalized_row
    return [merged[key] for key in ordered_keys]


def parse_int(value: str) -> int:
    try:
        return int(float(value))
    except ValueError:
        return 0


def format_ratio(count: int, total: int) -> str:
    if total <= 0:
        return "0.0000"
    return f"{count / total:.4f}"


def parse_bool_text(value: str, default: bool = False) -> bool:
    normalized = value.strip().casefold()
    if not normalized:
        return default
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    raise SystemExit(f"Invalid boolean value: {value}")


def normalize_bool(value: str, default: bool = False) -> str:
    return "true" if parse_bool_text(value, default=default) else "false"


def normalize_text_value(text: str) -> str:
    return " ".join(text.casefold().split()).strip()


def detect_language(text: str) -> str:
    if re.search(r"[\u4e00-\u9fff]", text):
        return "zh"
    if re.search(r"[\u3040-\u30ff]", text):
        return "ja"
    if re.search(r"[\uac00-\ud7af]", text):
        return "ko"
    if re.search(r"[A-Za-z]", text):
        return "en"
    return "unknown"


def slugify(value: str) -> str:
    cleaned: list[str] = []
    last_dash = False
    for char in value.casefold():
        if char.isalnum():
            cleaned.append(char)
            last_dash = False
            continue
        if not last_dash:
            cleaned.append("-")
            last_dash = True
    return "".join(cleaned).strip("-") or "unknown"


def merge_notes(*parts: str) -> str:
    ordered: list[str] = []
    for part in parts:
        for item in part.split(";"):
            cleaned = item.strip()
            if cleaned and cleaned not in ordered:
                ordered.append(cleaned)
    return "; ".join(ordered)


def keyword_hits(text: str, keywords: list[str]) -> int:
    lowered = text.casefold()
    return sum(1 for keyword in keywords if keyword in lowered)


def derive_source_id(platform: str, video_id: str, title: str) -> str:
    source_key = video_id or title or platform
    return f"s4_{slugify(f'{platform}-{source_key}')[:48]}"


def derive_segment_id(video_id: str, index: int) -> str:
    return f"s4seg_{slugify(video_id)[:24]}_{index:04d}"


def derive_claim_id(segment_id: str) -> str:
    return f"s4claim_{slugify(segment_id)[:48]}"


def derive_evidence_id(segment_id: str) -> str:
    return f"s4_{slugify(segment_id)[:52]}"


def normalize_selection_status(value: str) -> str:
    normalized = value.strip().casefold()
    if normalized in {"selected", "select", "keep", "chosen"}:
        return "selected"
    if normalized in {"excluded", "exclude", "drop", "reject"}:
        return "excluded"
    return "candidate"


def normalize_level(value: str, default: str = "unknown") -> str:
    cleaned = value.strip().casefold()
    return cleaned or default


def infer_support_label(text: str) -> str:
    positive_hits = keyword_hits(text, POSITIVE_KEYWORDS)
    negative_hits = keyword_hits(text, NEGATIVE_KEYWORDS)
    if positive_hits > negative_hits:
        return "positive"
    if negative_hits > positive_hits:
        return "negative"
    if positive_hits > 0 and negative_hits > 0:
        return "mixed"
    return "neutral"


def infer_topic(text: str) -> str:
    lowered = text.casefold()
    best_topic = "gameplay loop"
    best_hits = 0
    for topic_label, keywords in TOPIC_RULES.items():
        hits = sum(1 for keyword in keywords if keyword in lowered)
        if hits > best_hits:
            best_topic = topic_label
            best_hits = hits
    return best_topic


def infer_claim_type(text: str) -> str:
    lowered = text.casefold()
    for claim_type, keywords in CLAIM_TYPE_RULES.items():
        if any(keyword in lowered for keyword in keywords):
            return claim_type
    if any(token in lowered for token in ["i think", "我觉得", "感觉", "seems", "看起来"]):
        return "design_judgment"
    return "factual_observation"


def infer_sponsorship_risk(*texts: str) -> str:
    combined = " ".join(texts).casefold()
    if any(keyword in combined for keyword in SPONSORSHIP_KEYWORDS):
        return "high"
    return "medium"


def infer_genre_familiarity_note(*texts: str) -> str:
    combined = " ".join(texts).casefold()
    if any(keyword in combined for keyword in GENRE_FAMILIARITY_KEYWORDS):
        return "genre-aware wording detected"
    return "manual review needed"


def infer_visible_footage_support(text: str) -> str:
    lowered = text.casefold()
    if any(token in lowered for token in ["as shown", "you can see", "从画面", "视频里", "能看到", "footage"]):
        return "yes"
    if any(token in lowered for token in ["i think", "猜测", "可能", "感觉", "估计"]):
        return "unclear"
    return "unclear"


def top_rows(rows: list[dict[str, str]], key: str, limit: int = 3) -> list[dict[str, str]]:
    return sorted(rows, key=lambda row: parse_int(row.get(key, "0")), reverse=True)[:limit]
