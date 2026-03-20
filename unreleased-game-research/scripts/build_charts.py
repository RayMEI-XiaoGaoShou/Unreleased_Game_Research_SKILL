from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


SENTIMENT_KEYS = [
    ("positive", "Positive", "positive"),
    ("neutral", "Neutral", "neutral"),
    ("negative", "Negative", "negative"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate lightweight SVG charts for Section 2 artifacts.")
    parser.add_argument("--project-dir", required=True, help="Path to an initialized project directory")
    parser.add_argument(
        "--section-dir",
        default="section_2_official_video_comments",
        help="Relative section directory under the project directory",
    )
    parser.add_argument(
        "--theme-path",
        default="unreleased-game-research/assets/chart_theme.json",
        help="Path to chart theme JSON",
    )
    return parser.parse_args()


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise SystemExit(f"Required CSV not found: {path}")
    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return [dict(row) for row in reader]


def load_theme(path: Path) -> dict[str, str]:
    if not path.exists():
        return {
            "positive": "#2f855a",
            "neutral": "#718096",
            "negative": "#c53030",
            "accent": "#2b6cb0",
            "background": "#f7fafc",
        }
    return json.loads(path.read_text(encoding="utf-8"))


def svg_header(width: int, height: int, background: str) -> list[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        f'<rect width="100%" height="100%" fill="{background}"/>',
    ]


def render_sentiment_chart(row: dict[str, str], out_path: Path, theme: dict[str, str]) -> None:
    width = 760
    height = 260
    bar_x = 180
    bar_width = 460
    bar_height = 28
    gap = 18

    parts = svg_header(width, height, theme["background"])
    parts.append('<text x="24" y="36" font-size="22" font-family="sans-serif" fill="#102a43">Sentiment Distribution</text>')
    parts.append(
        f'<text x="24" y="62" font-size="12" font-family="sans-serif" fill="#486581">video={row.get("video_id", "")} milestone={row.get("milestone_id", "")} source=section_2 sentiment_summary.csv</text>'
    )

    y = 92
    for key, label, color_key in SENTIMENT_KEYS:
        ratio = float(row.get(f"{key}_ratio", "0") or 0)
        count = row.get(f"{key}_count", "0")
        width_px = ratio * bar_width
        parts.append(f'<text x="24" y="{y + 18}" font-size="14" font-family="sans-serif" fill="#102a43">{label}</text>')
        parts.append(f'<rect x="{bar_x}" y="{y}" width="{bar_width}" height="{bar_height}" rx="4" fill="#d9e2ec"/>')
        parts.append(f'<rect x="{bar_x}" y="{y}" width="{width_px:.1f}" height="{bar_height}" rx="4" fill="{theme[color_key]}"/>')
        parts.append(
            f'<text x="{bar_x + bar_width + 12}" y="{y + 18}" font-size="13" font-family="sans-serif" fill="#243b53">{count} ({ratio:.1%})</text>'
        )
        y += bar_height + gap

    parts.append('</svg>')
    out_path.write_text("\n".join(parts), encoding="utf-8")


def render_topic_chart(rows: list[dict[str, str]], out_path: Path, theme: dict[str, str]) -> None:
    visible_rows = rows[:8]
    width = 860
    height = 120 + len(visible_rows) * 42
    bar_x = 280
    bar_width = 420
    bar_height = 22

    max_mentions = max((int(row.get("mention_count", "0") or 0) for row in visible_rows), default=1)
    parts = svg_header(width, height, theme["background"])
    parts.append('<text x="24" y="36" font-size="22" font-family="sans-serif" fill="#102a43">Topic Coverage</text>')
    if visible_rows:
        parts.append(
            f'<text x="24" y="62" font-size="12" font-family="sans-serif" fill="#486581">video={visible_rows[0].get("video_id", "")} milestone={visible_rows[0].get("milestone_id", "")} source=section_2 topic_summary.csv</text>'
        )

    y = 92
    for row in visible_rows:
        mentions = int(row.get("mention_count", "0") or 0)
        width_px = 0 if max_mentions == 0 else (mentions / max_mentions) * bar_width
        label = row.get("topic_label", "")
        parts.append(f'<text x="24" y="{y + 16}" font-size="13" font-family="sans-serif" fill="#102a43">{label}</text>')
        parts.append(f'<rect x="{bar_x}" y="{y}" width="{bar_width}" height="{bar_height}" rx="4" fill="#d9e2ec"/>')
        parts.append(f'<rect x="{bar_x}" y="{y}" width="{width_px:.1f}" height="{bar_height}" rx="4" fill="{theme["accent"]}"/>')
        parts.append(
            f'<text x="{bar_x + bar_width + 12}" y="{y + 16}" font-size="12" font-family="sans-serif" fill="#243b53">mentions={mentions} pos={row.get("positive_ratio_within_topic", "0")} neg={row.get("negative_ratio_within_topic", "0")}</text>'
        )
        y += 42

    parts.append('</svg>')
    out_path.write_text("\n".join(parts), encoding="utf-8")


def run() -> None:
    args = parse_args()
    section_dir = Path(args.project_dir) / args.section_dir
    charts_dir = section_dir / "charts"
    charts_dir.mkdir(parents=True, exist_ok=True)

    sentiment_rows = read_csv_rows(section_dir / "sentiment_summary.csv")
    topic_rows = read_csv_rows(section_dir / "topic_summary.csv")
    theme = load_theme(Path(args.theme_path))

    for row in sentiment_rows:
        out_path = charts_dir / f"sentiment_{row.get('video_id', 'unknown')}.svg"
        render_sentiment_chart(row, out_path, theme)

    topic_rows_by_video: dict[str, list[dict[str, str]]] = {}
    for row in topic_rows:
        topic_rows_by_video.setdefault(row.get("video_id", ""), []).append(row)

    for video_id, rows in topic_rows_by_video.items():
        out_path = charts_dir / f"topics_{video_id or 'unknown'}.svg"
        sorted_rows = sorted(rows, key=lambda row: int(row.get("mention_count", "0") or 0), reverse=True)
        render_topic_chart(sorted_rows, out_path, theme)

    print(f"Generated charts in {charts_dir}")


if __name__ == "__main__":
    run()
