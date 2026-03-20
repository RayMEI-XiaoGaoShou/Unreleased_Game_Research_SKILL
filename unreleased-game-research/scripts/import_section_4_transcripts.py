from __future__ import annotations

import argparse
import re
from pathlib import Path

from section_4_common import (
    TRANSCRIPT_SEGMENTS_HEADER,
    derive_segment_id,
    ensure_section_files,
    load_input_rows,
    merge_rows_by_key,
    normalize_text_value,
    read_csv_rows,
    write_csv_rows,
)


INPUT_ALIASES = {
    "segment_id": ["segment_id", "id"],
    "video_id": ["video_id"],
    "timestamp_start": ["timestamp_start", "start", "start_time"],
    "timestamp_end": ["timestamp_end", "end", "end_time"],
    "quote_original": ["quote_original", "text", "transcript", "content"],
    "quote_normalized": ["quote_normalized", "normalized_text"],
    "topic_label": ["topic_label"],
    "claim_type": ["claim_type"],
    "supports_positive_or_negative": ["supports_positive_or_negative", "sentiment_label"],
    "visible_footage_support": ["visible_footage_support"],
    "cross_source_support": ["cross_source_support"],
    "confidence_level": ["confidence_level"],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import transcript segments into Section 4 artifacts.")
    parser.add_argument("--project-dir", required=True, help="Path to an initialized project directory")
    parser.add_argument("--input-file", required=True, help="CSV, JSON, JSONL, NDJSON, or SRT transcript input")
    parser.add_argument("--video-id", help="Required when importing a single SRT file without embedded video_id")
    return parser.parse_args()


def get_first_value(row: dict[str, str], field_name: str) -> str:
    for key in INPUT_ALIASES[field_name]:
        value = row.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def parse_srt_blocks(path: Path, video_id: str) -> list[dict[str, str]]:
    content = path.read_text(encoding="utf-8")
    chunks = re.split(r"\r?\n\r?\n", content.strip())
    rows: list[dict[str, str]] = []
    for index, chunk in enumerate(chunks, start=1):
        lines = [line.strip() for line in chunk.splitlines() if line.strip()]
        if len(lines) < 2:
            continue
        time_line = lines[1] if len(lines) >= 2 and "-->" in lines[1] else lines[0]
        if "-->" not in time_line:
            continue
        start, end = [part.strip().replace(",", ".") for part in time_line.split("-->", maxsplit=1)]
        text_lines = lines[2:] if time_line == lines[1] else lines[1:]
        quote_original = " ".join(text_lines).strip()
        if not quote_original:
            continue
        rows.append(
            {
                "segment_id": derive_segment_id(video_id, index),
                "video_id": video_id,
                "timestamp_start": start,
                "timestamp_end": end,
                "quote_original": quote_original,
                "quote_normalized": normalize_text_value(quote_original),
                "topic_label": "",
                "claim_type": "",
                "supports_positive_or_negative": "",
                "visible_footage_support": "",
                "cross_source_support": "",
                "confidence_level": "",
            }
        )
    return rows


def load_transcript_rows(path: Path, fallback_video_id: str | None) -> list[dict[str, str]]:
    if path.suffix.casefold() == ".srt":
        if not fallback_video_id:
            raise SystemExit("--video-id is required when importing an SRT transcript.")
        return parse_srt_blocks(path, fallback_video_id)
    source_rows = load_input_rows(path)
    normalized_rows: list[dict[str, str]] = []
    for index, raw_row in enumerate(source_rows, start=1):
        video_id = get_first_value(raw_row, "video_id") or (fallback_video_id or "")
        if not video_id:
            raise SystemExit(f"Transcript row {index} is missing video_id")
        quote_original = get_first_value(raw_row, "quote_original")
        if not quote_original:
            continue
        normalized_rows.append(
            {
                "segment_id": get_first_value(raw_row, "segment_id") or derive_segment_id(video_id, index),
                "video_id": video_id,
                "timestamp_start": get_first_value(raw_row, "timestamp_start"),
                "timestamp_end": get_first_value(raw_row, "timestamp_end"),
                "quote_original": quote_original,
                "quote_normalized": get_first_value(raw_row, "quote_normalized") or normalize_text_value(quote_original),
                "topic_label": get_first_value(raw_row, "topic_label"),
                "claim_type": get_first_value(raw_row, "claim_type"),
                "supports_positive_or_negative": get_first_value(raw_row, "supports_positive_or_negative"),
                "visible_footage_support": get_first_value(raw_row, "visible_footage_support"),
                "cross_source_support": get_first_value(raw_row, "cross_source_support"),
                "confidence_level": get_first_value(raw_row, "confidence_level"),
            }
        )
    return normalized_rows


def main() -> None:
    args = parse_args()
    project_dir = Path(args.project_dir).resolve()
    input_path = Path(args.input_file).resolve()
    if not input_path.exists():
        raise SystemExit(f"Input file not found: {input_path}")

    section_dir = ensure_section_files(project_dir)
    selected_rows = read_csv_rows(section_dir / "selected_videos.csv")
    selected_ids = {row.get("video_id", "") for row in selected_rows if row.get("video_id", "")}
    if not selected_ids:
        raise SystemExit("selected_videos.csv has no selected data rows. Import candidates and mark final videos first.")

    transcript_rows = load_transcript_rows(input_path, args.video_id)
    if not transcript_rows:
        raise SystemExit(f"Input file contains no usable transcript rows: {input_path}")

    invalid_video_ids = sorted({row.get("video_id", "") for row in transcript_rows if row.get("video_id", "") not in selected_ids})
    if invalid_video_ids:
        raise SystemExit(f"Transcript rows reference unselected or unknown video_id values: {', '.join(invalid_video_ids)}")

    existing_rows = read_csv_rows(section_dir / "transcript_segments.csv")
    merged_rows = merge_rows_by_key(existing_rows, transcript_rows, "segment_id", TRANSCRIPT_SEGMENTS_HEADER)
    write_csv_rows(section_dir / "transcript_segments.csv", TRANSCRIPT_SEGMENTS_HEADER, merged_rows)

    print(f"Imported {len(transcript_rows)} transcript segments into {section_dir / 'transcript_segments.csv'}")


if __name__ == "__main__":
    main()
