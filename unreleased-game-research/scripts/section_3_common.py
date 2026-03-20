from __future__ import annotations

import csv
import html
import re
from pathlib import Path
from urllib import error, request


SECTION_DIR_NAME = "section_3_homepage_reviews"

REVIEW_REGISTRY_HEADER = [
    "review_id",
    "platform",
    "url",
    "game_page_title",
    "review_publish_time",
    "review_length_bucket",
    "likes",
    "replies",
    "capture_method",
    "language",
    "is_longform",
    "notes",
]

REVIEW_SAMPLE_HEADER = [
    "review_id",
    "platform",
    "author_name",
    "text_original",
    "text_normalized",
    "language",
    "likes",
    "replies",
    "sentiment_label",
    "topic_label",
    "experience_basis",
    "is_high_value",
    "confidence_note",
]

REVIEWER_TAGS_HEADER = [
    "review_id",
    "reviewer_tag",
    "tag_basis",
    "confidence_level",
    "notes",
]

SENTIMENT_SUMMARY_HEADER = [
    "platform",
    "positive_count",
    "neutral_count",
    "negative_count",
    "positive_ratio",
    "neutral_ratio",
    "negative_ratio",
    "longform_share",
    "experience_based_share",
    "notes",
]

TOPIC_SUMMARY_HEADER = [
    "topic_label",
    "mention_count",
    "mention_ratio",
    "positive_ratio_within_topic",
    "negative_ratio_within_topic",
    "experience_based_ratio",
    "representative_evidence_id",
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

POSITIVE_KEYWORDS = {
    "en": [
        "good",
        "great",
        "love",
        "amazing",
        "nice",
        "smooth",
        "promising",
        "impressive",
        "fun",
        "solid",
        "beautiful",
        "interesting",
    ],
    "zh": [
        "好",
        "喜欢",
        "期待",
        "不错",
        "优秀",
        "惊艳",
        "流畅",
        "扎实",
        "有趣",
        "舒服",
        "香",
    ],
}

NEGATIVE_KEYWORDS = {
    "en": [
        "bad",
        "boring",
        "worse",
        "awful",
        "hate",
        "lag",
        "clunky",
        "generic",
        "worried",
        "disappointed",
        "pay to win",
        "grindy",
        "empty",
        "weak",
    ],
    "zh": [
        "差",
        "无聊",
        "卡",
        "烂",
        "担心",
        "失望",
        "一般",
        "不行",
        "换皮",
        "氪",
        "空",
        "重复",
        "弱",
    ],
}

FIRSTHAND_KEYWORDS = [
    "试玩",
    "测过",
    "参加测试",
    "参加过测试",
    "参加了测试",
    "参加了两次测试",
    "测试服",
    "内测",
    "封测",
    "公测",
    "一测",
    "二测",
    "三测",
    "四测",
    "首测",
    "玩了",
    "玩过",
    "我玩",
    "我打到",
    "上手",
    "体验过",
    "体验了一下",
    "测试玩家",
    "体验服",
    "played",
    "i played",
    "hours in",
    "after playing",
    "in the beta",
    "beta participant",
    "test player",
    "during the test",
]

EXPECTATION_KEYWORDS = [
    "希望",
    "看起来",
    "感觉会",
    "担心会",
    "应该",
    "估计",
    "猜测",
    "似乎",
    "looks like",
    "seems",
    "i think it will",
    "probably",
    "might be",
]

NOSTALGIA_KEYWORDS = [
    "童年",
    "当年",
    "以前",
    "老玩家",
    "原作",
    "情怀",
    "经典",
    "回忆",
    "nostalgia",
    "old school",
    "grew up with",
    "classic",
]

GENRE_ASSUMPTION_KEYWORDS = [
    "二游",
    "开放世界",
    "mmo",
    "mmorpg",
    "roguelike",
    "gacha",
    "soulslike",
    "品类",
    "同类",
    "genre",
    "benchmark",
    "like other",
    "compared to",
]

LONGFORM_SYSTEM_KEYWORDS = [
    "系统",
    "循环",
    "数值",
    "成长",
    "养成",
    "任务",
    "关卡",
    "新手",
    "引导",
    "优化",
    "氪金",
    "抽卡",
    "endgame",
    "onboarding",
    "retention",
    "monetization",
    "progression",
    "loop",
    "system",
    "ux",
]

TOPIC_RULES = {
    "combat and feel": ["战斗", "combat", "hit feel", "手感", "操作", "技能", "boss"],
    "exploration and world interaction": ["探索", "world", "地图", "交互", "开放世界", "exploration"],
    "collection and progression": ["养成", "成长", "build", "抽卡", "收集", "progression", "upgrade"],
    "onboarding and UX": ["新手", "引导", "教程", "ui", "ux", "上手", "menu", "操作逻辑"],
    "technical quality / optimization": ["优化", "卡", "bug", "崩", "lag", "fps", "frame", "stutter", "performance"],
    "art / atmosphere / identity": ["美术", "画风", "atmosphere", "visual", "art", "角色设计", "风格", "音乐"],
    "IP adaptation / franchise faithfulness": ["原作", "ip", "设定", "还原", "粉丝", "franchise", "faithful"],
    "content depth / endgame concern": ["内容", "后期", "endgame", "深度", "耐玩", "重复", "空", "长线"],
    "monetization anxiety": ["氪", "pay to win", "p2w", "gacha", "monetization", "付费", "抽卡"],
    "pacing and retention": ["节奏", "retention", "日常", "上线", "留存", "拖沓", "肝", "挂机"],
    "multiplayer / social potential": ["联机", "公会", "组队", "社交", "multiplayer", "coop", "guild"],
    "genre competitiveness": ["同类", "benchmark", "竞品", "像", "copy", "换皮", "genre", "compared to"],
}

REVIEWER_TAG_RULES = {
    "test_player": [
        "试玩",
        "参加测试",
        "参加过测试",
        "参加了测试",
        "测试服",
        "内测",
        "封测",
        "公测",
        "一测",
        "二测",
        "三测",
        "四测",
        "首测",
        "beta",
        "test",
        "played",
    ],
    "ip_core_fan": ["ip", "原作", "粉丝", "设定党", "franchise", "canon"],
    "genre_core_player": ["二游", "mmo", "roguelike", "soulslike", "品类", "genre", "benchmark"],
    "returning_franchise_player": ["老玩家", "回坑", "以前玩过", "当年", "returning", "came back"],
    "curious_noncore": ["路人", "没玩过", "第一次接触", "随便看看", "new to", "first time"],
    "content_creator": ["up主", "主播", "测评", "review channel", "content creator", "stream"],
}


def ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def ensure_csv(path: Path, header: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=header)
        writer.writeheader()


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise SystemExit(f"Required CSV not found: {path}")
    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return [dict(row) for row in reader]


def write_csv_rows(path: Path, header: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=header)
        writer.writeheader()
        writer.writerows(rows)


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


def parse_int(value: str) -> int:
    try:
        return int(float(value))
    except ValueError:
        return 0


def format_ratio(count: int, total: int) -> str:
    if total <= 0:
        return "0.0000"
    return f"{count / total:.4f}"


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


def review_length_bucket(text: str) -> str:
    length = len(text.strip())
    if length >= 180:
        return "long"
    if length >= 60:
        return "medium"
    return "short"


def is_longform_text(text: str) -> bool:
    return review_length_bucket(text) == "long"


def keyword_hits(text: str, keywords: list[str]) -> int:
    lowered = text.casefold()
    return sum(1 for keyword in keywords if keyword in lowered)


def derive_source_id(platform: str, url: str, game_page_title: str) -> str:
    source_key = game_page_title or url or platform
    return f"s3_{slugify(f'{platform}-{source_key}')[:48]}"


def evidence_id_for_review(review_id: str) -> str:
    return f"s3_{review_id}"


def merge_notes(*parts: str) -> str:
    ordered: list[str] = []
    for part in parts:
        for item in part.split(";"):
            cleaned = item.strip()
            if cleaned and cleaned not in ordered:
                ordered.append(cleaned)
    return "; ".join(ordered)


def infer_experience_basis(text: str) -> tuple[str, str]:
    firsthand_hits = keyword_hits(text, FIRSTHAND_KEYWORDS)
    expectation_hits = keyword_hits(text, EXPECTATION_KEYWORDS)
    nostalgia_hits = keyword_hits(text, NOSTALGIA_KEYWORDS)
    genre_hits = keyword_hits(text, GENRE_ASSUMPTION_KEYWORDS)

    active = sum(1 for value in [firsthand_hits, expectation_hits, nostalgia_hits, genre_hits] if value > 0)
    if active >= 2:
        return "mixed", "multiple_experience_frames_detected"
    if firsthand_hits > 0:
        return "firsthand_experience", "self_reported_play_experience"
    if nostalgia_hits > 0:
        return "nostalgia_projection", "nostalgia_or_franchise_memory"
    if expectation_hits > 0:
        return "secondhand_expectation", "future_or_surface_expectation_language"
    if genre_hits > 0:
        return "genre_assumption", "genre_benchmark_language"
    return "mixed", "insufficient_signal_to_separate_experience_basis"


def classify_sentiment(text: str, language: str) -> tuple[str, str]:
    positive_hits = keyword_hits(text, POSITIVE_KEYWORDS.get(language, []))
    negative_hits = keyword_hits(text, NEGATIVE_KEYWORDS.get(language, []))
    if positive_hits > negative_hits:
        return "positive", "positive_keyword_majority"
    if negative_hits > positive_hits:
        return "negative", "negative_keyword_majority"
    return "neutral", "no_clear_sentiment_keyword_majority"


def infer_topic(text: str) -> tuple[str, str]:
    best_topic = "genre competitiveness"
    best_hits = 0
    lowered = text.casefold()
    for topic_label, keywords in TOPIC_RULES.items():
        hits = sum(1 for keyword in keywords if keyword in lowered)
        if hits > best_hits:
            best_topic = topic_label
            best_hits = hits
    if best_hits == 0:
        return "content depth / endgame concern", "fallback_topic_due_to_low_specificity"
    return best_topic, "topic_keyword_match"


def infer_reviewer_tags(text: str) -> list[tuple[str, str, str, str]]:
    lowered = text.casefold()
    tags: list[tuple[str, str, str, str]] = []
    for tag, keywords in REVIEWER_TAG_RULES.items():
        hits = sum(1 for keyword in keywords if keyword in lowered)
        if hits <= 0:
            continue
        confidence = "high" if hits >= 2 else "medium"
        tags.append((tag, "keyword_match", confidence, f"matched {hits} tag hints"))
    if tags:
        return tags
    return [("unclear", "no_identity_signal", "low", "identity inferred as unclear")]


def high_value_reasons(
    text: str,
    likes: int,
    replies: int,
    experience_basis: str,
    reviewer_tags: list[tuple[str, str, str, str]],
) -> list[str]:
    reasons: list[str] = []
    if is_longform_text(text):
        reasons.append("longform")
    if keyword_hits(text, LONGFORM_SYSTEM_KEYWORDS) > 0:
        reasons.append("system_detail")
    if experience_basis == "firsthand_experience":
        reasons.append("firsthand")
    if likes >= 10:
        reasons.append("high_resonance")
    if replies >= 3:
        reasons.append("thread_discussion")
    if any(tag != "unclear" for tag, _, _, _ in reviewer_tags):
        reasons.append("reviewer_context")
    return reasons


def strength_from_review(likes: int, replies: int, is_high_value: bool) -> str:
    if is_high_value and (likes >= 10 or replies >= 3):
        return "strong"
    if is_high_value or likes >= 3 or replies >= 1:
        return "medium"
    return "weak"


def is_experience_based(experience_basis: str) -> bool:
    return experience_basis in {"firsthand_experience", "mixed"}


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


def fetch_url_text(url: str, timeout: int = 20) -> str:
    req = request.Request(url, headers=DEFAULT_HEADERS)
    try:
        with request.urlopen(req, timeout=timeout) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(charset, errors="replace")
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"Request failed for {url} ({exc.code}): {body[:400]}") from exc
    except error.URLError as exc:
        raise SystemExit(f"Network error while requesting {url}: {exc.reason}") from exc


def extract_meta_content(html_text: str, key: str) -> str:
    patterns = [
        rf'<meta[^>]+property=["\']{re.escape(key)}["\'][^>]+content=["\']([^"\']+)["\']',
        rf'<meta[^>]+name=["\']{re.escape(key)}["\'][^>]+content=["\']([^"\']+)["\']',
        rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']{re.escape(key)}["\']',
        rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']{re.escape(key)}["\']',
    ]
    for pattern in patterns:
        match = re.search(pattern, html_text, re.IGNORECASE)
        if match:
            return html.unescape(match.group(1)).strip()
    return ""


def extract_title_text(html_text: str) -> str:
    match = re.search(r"<title>(.*?)</title>", html_text, re.IGNORECASE | re.DOTALL)
    if not match:
        return ""
    return clean_html_text(match.group(1))


def clean_html_text(value: str) -> str:
    without_tags = re.sub(r"<[^>]+>", " ", value)
    unescaped = html.unescape(without_tags)
    return " ".join(unescaped.split()).strip()


def platform_from_url(url: str) -> str:
    lowered = url.casefold()
    if "taptap" in lowered:
        return "taptap"
    if "biligame.com" in lowered:
        return "biligame"
    if "bilibili.com" in lowered:
        return "bilibili"
    return "unknown"


def append_unique_rows(path: Path, header: list[str], rows: list[dict[str, str]], key_field: str) -> int:
    ensure_csv(path, header)
    existing_rows = read_csv_rows(path)
    existing_keys = {row.get(key_field, "") for row in existing_rows if row.get(key_field, "")}
    new_rows = [{column: row.get(column, "") for column in header} for row in rows if row.get(key_field, "") not in existing_keys]
    if not new_rows:
        return 0
    write_csv_rows(path, header, existing_rows + new_rows)
    return len(new_rows)
