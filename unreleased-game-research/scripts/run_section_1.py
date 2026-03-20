from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


TIMELINE_HEADER = [
    "milestone_id",
    "label",
    "date",
    "source_id",
    "content_type",
    "summary",
    "change_vs_previous",
    "confidence_level",
]

TEAM_HEADER = [
    "entity_name",
    "entity_type",
    "role",
    "related_prior_titles",
    "genre_relevance",
    "evidence_source_id",
    "confidence_level",
    "notes",
]

FACT_HEADER = [
    "fact_key",
    "fact_value",
    "source_id",
    "source_type",
    "verification_status",
    "confidence_level",
    "notes",
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

REQUIRED_FACT_KEYS = {"official_name", "developer", "publisher"}
VERIFIED_STATUSES = {"official_confirmed", "cross_checked", "verified"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="导入并校验 Section 1 的公开情报结构化数据。")
    parser.add_argument("--project-dir", required=True, help="目标项目目录")
    parser.add_argument("--data-file", required=True, help="Section 1 结构化 JSON 文件")
    return parser.parse_args()


def ensure_csv(path: Path, header: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=header)
        writer.writeheader()


def write_csv_rows(path: Path, header: list[str], rows: list[dict[str, object]]) -> None:
    ensure_csv(path, header)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=header)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: str(row.get(column, "")) for column in header})


def load_json(path: Path) -> dict[str, object]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"Section 1 JSON 顶层必须是对象：{path}")
    return data


def normalize_fact_rows(data: dict[str, object]) -> list[dict[str, object]]:
    raw_rows = data.get("facts")
    if not isinstance(raw_rows, list):
        raise SystemExit(
            "Section 1 JSON 缺少 `facts` 数组。为了降低幻觉风险，Section 1 现在要求提供事实账本。"
        )
    rows: list[dict[str, object]] = []
    for raw in raw_rows:
        if not isinstance(raw, dict):
            continue
        rows.append({column: raw.get(column, "") for column in FACT_HEADER})
    if not rows:
        raise SystemExit("Section 1 `facts` 数组为空，无法进行事实校验。")
    return rows


def validate_fact_rows(fact_rows: list[dict[str, object]]) -> None:
    fact_keys_present = {str(row.get("fact_key", "")).strip() for row in fact_rows if str(row.get("fact_key", "")).strip()}
    missing_keys = sorted(REQUIRED_FACT_KEYS - fact_keys_present)
    if missing_keys:
        raise SystemExit(f"Section 1 缺少必填事实字段：{', '.join(missing_keys)}")

    for row in fact_rows:
        fact_key = str(row.get("fact_key", "")).strip()
        fact_value = str(row.get("fact_value", "")).strip()
        source_id = str(row.get("source_id", "")).strip()
        verification_status = str(row.get("verification_status", "")).strip()
        if not fact_key or not fact_value:
            raise SystemExit("Section 1 fact_registry 中存在空的 fact_key 或 fact_value。")
        if fact_key in REQUIRED_FACT_KEYS:
            if not source_id:
                raise SystemExit(f"Section 1 硬事实 `{fact_key}` 缺少 source_id。")
            if verification_status not in VERIFIED_STATUSES:
                raise SystemExit(
                    f"Section 1 硬事实 `{fact_key}` 的 verification_status 必须是 {', '.join(sorted(VERIFIED_STATUSES))} 之一。"
                )


def normalize_rows(data: dict[str, object], key: str, header: list[str]) -> list[dict[str, object]]:
    raw_rows = data.get(key, [])
    if not isinstance(raw_rows, list):
        return []
    rows: list[dict[str, object]] = []
    for raw in raw_rows:
        if not isinstance(raw, dict):
            continue
        rows.append({column: raw.get(column, "") for column in header})
    return rows


def build_evidence_rows(fact_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    evidence_rows: list[dict[str, object]] = []
    for index, row in enumerate(fact_rows, start=1):
        fact_key = str(row.get("fact_key", "")).strip()
        fact_value = str(row.get("fact_value", "")).strip()
        evidence_rows.append(
            {
                "evidence_id": f"s1_fact_{index:03d}",
                "source_id": str(row.get("source_id", "")).strip(),
                "claim_or_observation": f"{fact_key}: {fact_value}",
                "evidence_type": "fact",
                "quote_original": fact_value,
                "quote_translated": "",
                "topic_label": fact_key,
                "sentiment_label": "neutral",
                "milestone": "",
                "strength": "strong" if str(row.get("verification_status", "")).strip() in VERIFIED_STATUSES else "medium",
                "risk_note": str(row.get("notes", "")).strip(),
            }
        )
    return evidence_rows


def findings_with_fact_guard(findings_content: str, fact_rows: list[dict[str, object]]) -> str:
    facts_lines = [
        "## 已确认事实",
        "",
    ]
    for row in fact_rows:
        facts_lines.append(
            f"- `{row.get('fact_key', '')}`：{row.get('fact_value', '')}（核验状态：{row.get('verification_status', '')}；来源：{row.get('source_id', '')}）"
        )
    facts_lines.append("")
    if "## 已确认事实" in findings_content:
        return findings_content
    return "\n".join(facts_lines) + findings_content.strip() + "\n"


def main() -> None:
    args = parse_args()
    project_dir = Path(args.project_dir).resolve()
    data_file = Path(args.data_file).resolve()
    if not data_file.exists():
        raise SystemExit(f"Section 1 数据文件不存在：{data_file}")

    data = load_json(data_file)
    fact_rows = normalize_fact_rows(data)
    validate_fact_rows(fact_rows)
    timeline_rows = normalize_rows(data, "timeline", TIMELINE_HEADER)
    team_rows = normalize_rows(data, "team", TEAM_HEADER)
    DEFAULT_FINDINGS = """## 范围与核心结论

## 1. 基础信息与开发脉络
根据目前公开信息，暂无相关报道

## 2. 多维度评估产品
根据目前公开信息，暂无相关报道

## 3. 核心乐趣提炼与品类定位
根据目前公开信息，暂无相关报道

## 4. 品类基准比较
根据目前公开信息，暂无相关报道

## 5. 品类趋势与生态位判断
根据目前公开信息，暂无相关报道

## 置信度与信息局限
"""
    findings_content = str(data.get("findings", DEFAULT_FINDINGS))

    section_dir = project_dir / "section_1_public_intel"
    section_dir.mkdir(parents=True, exist_ok=True)

    write_csv_rows(section_dir / "timeline.csv", TIMELINE_HEADER, timeline_rows)
    write_csv_rows(section_dir / "team_profile.csv", TEAM_HEADER, team_rows)
    write_csv_rows(section_dir / "fact_registry.csv", FACT_HEADER, fact_rows)
    write_csv_rows(section_dir / "evidence_table.csv", EVIDENCE_TABLE_HEADER, build_evidence_rows(fact_rows))
    (section_dir / "findings.md").write_text(findings_with_fact_guard(findings_content, fact_rows), encoding="utf-8")

    print(f"[Section 1] 已完成事实校验并写入：{section_dir}")


if __name__ == "__main__":
    main()
