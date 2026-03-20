from __future__ import annotations

import argparse
import importlib
from pathlib import Path

from file_lock import exclusive_file_lock

try:
    from . import section_4_common as _s4_common
except ImportError:
    _s4_common = importlib.import_module("section_4_common")

CANDIDATE_VIDEOS_HEADER = _s4_common.CANDIDATE_VIDEOS_HEADER
CREATOR_PROFILES_HEADER = _s4_common.CREATOR_PROFILES_HEADER
SELECTED_VIDEOS_HEADER = _s4_common.SELECTED_VIDEOS_HEADER
SOURCE_REGISTRY_HEADER = _s4_common.SOURCE_REGISTRY_HEADER
derive_source_id = _s4_common.derive_source_id
detect_language = _s4_common.detect_language
ensure_section_files = _s4_common.ensure_section_files
infer_genre_familiarity_note = _s4_common.infer_genre_familiarity_note
infer_sponsorship_risk = _s4_common.infer_sponsorship_risk
infer_support_label = _s4_common.infer_support_label
load_input_rows = _s4_common.load_input_rows
merge_notes = _s4_common.merge_notes
merge_rows_by_key = _s4_common.merge_rows_by_key
normalize_bool = _s4_common.normalize_bool
normalize_level = _s4_common.normalize_level
normalize_selection_status = _s4_common.normalize_selection_status
parse_bool_text = _s4_common.parse_bool_text
read_csv_rows = _s4_common.read_csv_rows
write_csv_rows = _s4_common.write_csv_rows


INPUT_ALIASES = {
    "video_id": ["video_id", "id"],
    "platform": ["platform", "site"],
    "url": ["url", "video_url"],
    "title": ["title", "video_title"],
    "creator_name": ["creator_name", "channel_name", "author_or_channel", "uploader"],
    "publish_date": ["publish_date", "upload_date", "date"],
    "latest_test_relevance": ["latest_test_relevance", "is_latest_test_relevant"],
    "has_actual_judgment": ["has_actual_judgment", "contains_actual_judgment"],
    "has_concrete_footage": ["has_concrete_footage", "contains_concrete_footage"],
    "is_guide_like": ["is_guide_like", "guide_like"],
    "selection_status": ["selection_status", "status"],
    "notes": ["notes", "note"],
    "duration_seconds": ["duration_seconds", "duration", "video_duration_seconds"],
    "view_count": ["view_count", "views", "play_count"],
    "inclusion_reason": ["inclusion_reason", "auto_inclusion_reason", "selection_reason"],
    "latest_test_confidence": ["latest_test_confidence", "latest_test_score", "latest_confidence"],
    "ranking_score": ["ranking_score", "score"],
    "search_query": ["search_query", "query"],
}

SHORTLIST_NOTE_FIELDS = [
    "duration_seconds",
    "view_count",
    "latest_test_confidence",
    "ranking_score",
    "search_query",
    "inclusion_reason",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import candidate creator-review videos into Section 4 artifacts.")
    parser.add_argument("--project-dir", required=True, help="Path to an initialized project directory")
    parser.add_argument("--input-file", required=True, help="CSV, JSON, JSONL, or NDJSON candidate-video export")
    parser.add_argument("--notes", default="", help="Extra notes merged into imported candidate rows")
    parser.add_argument("--access-method", default="manual", choices=["api", "browser", "manual", "transcript", "scrape"], help="access_method written to source_registry.csv")
    parser.add_argument("--capture-status", default="success", choices=["success", "partial", "failed", "manual_fallback"], help="capture_status written to source_registry.csv")
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


def base_candidate_row(raw_row: dict[str, str], index: int, extra_notes: str) -> dict[str, str]:
    video_id = get_first_value(raw_row, "video_id") or f"manual_video_{index:03d}"
    title = get_first_value(raw_row, "title") or video_id
    notes = merge_notes(get_first_value(raw_row, "notes"), shortlist_metadata_notes(raw_row), extra_notes)
    return {
        "video_id": video_id,
        "platform": get_first_value(raw_row, "platform") or "unknown",
        "url": get_first_value(raw_row, "url"),
        "title": title,
        "creator_name": get_first_value(raw_row, "creator_name") or f"creator_{index:03d}",
        "publish_date": get_first_value(raw_row, "publish_date"),
        "latest_test_relevance": normalize_bool(get_first_value(raw_row, "latest_test_relevance"), default=True),
        "has_actual_judgment": normalize_bool(get_first_value(raw_row, "has_actual_judgment"), default=True),
        "has_concrete_footage": normalize_bool(get_first_value(raw_row, "has_concrete_footage"), default=True),
        "is_guide_like": normalize_bool(get_first_value(raw_row, "is_guide_like"), default=False),
        "selection_status": normalize_selection_status(get_first_value(raw_row, "selection_status") or "candidate"),
        "notes": notes,
    }


def shortlist_metadata_notes(raw_row: dict[str, str]) -> str:
    notes: list[str] = []
    for field_name in SHORTLIST_NOTE_FIELDS:
        value = get_first_value(raw_row, field_name)
        if not value:
            continue
        notes.append(f"{field_name}={value.replace(';', ',').strip()}")
    return merge_notes(*notes)


def inclusion_reason_from_notes(notes: str) -> str:
    for item in notes.split(";"):
        cleaned = item.strip()
        if cleaned.casefold().startswith("inclusion_reason="):
            return cleaned.split("=", 1)[1].strip()
    return ""


def default_creator_credibility(candidate_row: dict[str, str]) -> str:
    latest = parse_bool_text(candidate_row.get("latest_test_relevance", "false"), default=False)
    judgment = parse_bool_text(candidate_row.get("has_actual_judgment", "false"), default=False)
    footage = parse_bool_text(candidate_row.get("has_concrete_footage", "false"), default=False)
    guide_like = parse_bool_text(candidate_row.get("is_guide_like", "false"), default=False)
    if latest and judgment and footage and not guide_like:
        return "high"
    if judgment and not guide_like:
        return "medium"
    return "low"


def build_selected_row(candidate_row: dict[str, str], existing_row: dict[str, str] | None) -> dict[str, str]:
    existing = existing_row or {}
    notes = candidate_row.get("notes", "")
    inclusion_reason = inclusion_reason_from_notes(notes)
    return {
        "video_id": candidate_row.get("video_id", ""),
        "selection_reason": existing.get("selection_reason") or inclusion_reason or "manual_first_latest_test_candidate",
        "creator_credibility": existing.get("creator_credibility") or default_creator_credibility(candidate_row),
        "audience_size_bucket": existing.get("audience_size_bucket") or "unknown",
        "sponsorship_risk": existing.get("sponsorship_risk") or infer_sponsorship_risk(candidate_row.get("title", ""), notes),
        "genre_familiarity_note": existing.get("genre_familiarity_note") or infer_genre_familiarity_note(candidate_row.get("title", ""), notes),
        "stance_note": existing.get("stance_note") or infer_support_label(f"{candidate_row.get('title', '')} {notes}"),
    }


def build_creator_profile(candidate_row: dict[str, str], selected_row: dict[str, str], existing_row: dict[str, str] | None) -> dict[str, str]:
    existing = existing_row or {}
    return {
        "creator_name": candidate_row.get("creator_name", ""),
        "platform": candidate_row.get("platform", ""),
        "audience_size_bucket": existing.get("audience_size_bucket") or selected_row.get("audience_size_bucket", "unknown"),
        "genre_relevance": existing.get("genre_relevance") or normalize_level(selected_row.get("genre_familiarity_note", "manual review needed"), default="manual review needed"),
        "ip_relevance": existing.get("ip_relevance") or "unknown",
        "evidence_density": existing.get("evidence_density") or ("medium" if candidate_row.get("has_actual_judgment") == "true" else "low"),
        "balance_of_judgment": existing.get("balance_of_judgment") or "unknown",
        "sponsorship_risk": existing.get("sponsorship_risk") or selected_row.get("sponsorship_risk", "medium"),
        "credibility_rating": existing.get("credibility_rating") or selected_row.get("creator_credibility", "medium"),
        "notes": merge_notes(existing.get("notes", ""), candidate_row.get("notes", "")),
    }


def update_source_registry(project_dir: Path, candidate_rows: list[dict[str, str]], access_method: str, capture_status: str) -> None:
    source_registry_path = project_dir / "sources" / "source_registry.csv"
    with exclusive_file_lock(source_registry_path):
        existing_rows = read_csv_rows(source_registry_path)
        existing_by_id = {row.get("source_id", ""): row for row in existing_rows}
        updated_rows: list[dict[str, str]] = []

        seen_ids: set[str] = set()
        for row in candidate_rows:
            source_id = derive_source_id(row.get("platform", "unknown"), row.get("video_id", ""), row.get("title", ""))
            current = existing_by_id.get(source_id, {})
            updated_rows.append(
                {
                    "source_id": source_id,
                    "section_id": "section_4",
                    "platform": row.get("platform", ""),
                    "source_type": "creator review video",
                    "url": row.get("url", ""),
                    "title": row.get("title", ""),
                    "author_or_channel": row.get("creator_name", ""),
                    "publish_date": row.get("publish_date", ""),
                    "language": current.get("language") or detect_language(f"{row.get('title', '')} {row.get('notes', '')}"),
                    "official_status": "unofficial",
                    "reliability_score": current.get("reliability_score") or ("4" if row.get("selection_status") == "selected" else "3"),
                    "bias_risk": current.get("bias_risk") or infer_sponsorship_risk(row.get("title", ""), row.get("notes", "")),
                    "access_method": current.get("access_method") or access_method,
                    "capture_status": current.get("capture_status") or capture_status,
                    "notes": merge_notes(current.get("notes", ""), row.get("notes", ""), "section_4_candidate_import"),
                }
            )
            seen_ids.add(source_id)

        for row in existing_rows:
            source_id = row.get("source_id", "")
            if source_id and source_id not in seen_ids:
                updated_rows.append({column: row.get(column, "") for column in SOURCE_REGISTRY_HEADER})

        write_csv_rows(source_registry_path, SOURCE_REGISTRY_HEADER, updated_rows)


def main() -> None:
    args = parse_args()
    project_dir = Path(args.project_dir).resolve()
    input_path = Path(args.input_file).resolve()
    if not input_path.exists():
        raise SystemExit(f"Input file not found: {input_path}")

    section_dir = ensure_section_files(project_dir)
    source_rows = load_input_rows(input_path)
    if not source_rows:
        raise SystemExit(f"Input file contains no candidate rows: {input_path}")

    candidate_rows = [base_candidate_row(raw_row, index, args.notes) for index, raw_row in enumerate(source_rows, start=1)]
    existing_candidate_rows = read_csv_rows(section_dir / "candidate_videos.csv")
    merged_candidates = merge_rows_by_key(existing_candidate_rows, candidate_rows, "video_id", CANDIDATE_VIDEOS_HEADER)

    existing_selected_rows = read_csv_rows(section_dir / "selected_videos.csv")
    existing_selected_by_video = {row.get("video_id", ""): row for row in existing_selected_rows}
    selected_rows = [
        build_selected_row(row, existing_selected_by_video.get(row.get("video_id", "")))
        for row in merged_candidates
        if row.get("selection_status") == "selected"
    ]

    existing_profile_rows = read_csv_rows(section_dir / "creator_profiles.csv")
    existing_profile_by_key = {(row.get("creator_name", ""), row.get("platform", "")): row for row in existing_profile_rows}
    creator_profile_rows = []
    for selected_row in selected_rows:
        candidate_row = next(row for row in merged_candidates if row.get("video_id") == selected_row.get("video_id"))
        key = (candidate_row.get("creator_name", ""), candidate_row.get("platform", ""))
        creator_profile_rows.append(build_creator_profile(candidate_row, selected_row, existing_profile_by_key.get(key)))

    write_csv_rows(section_dir / "candidate_videos.csv", CANDIDATE_VIDEOS_HEADER, merged_candidates)
    write_csv_rows(section_dir / "selected_videos.csv", SELECTED_VIDEOS_HEADER, selected_rows)
    write_csv_rows(section_dir / "creator_profiles.csv", CREATOR_PROFILES_HEADER, creator_profile_rows)
    update_source_registry(project_dir, merged_candidates, args.access_method, args.capture_status)

    print(f"Imported {len(candidate_rows)} candidate videos into {section_dir}")
    print(f"- candidates: {section_dir / 'candidate_videos.csv'}")
    print(f"- selected: {section_dir / 'selected_videos.csv'} ({len(selected_rows)} rows)")
    print(f"- creator_profiles: {section_dir / 'creator_profiles.csv'}")


if __name__ == "__main__":
    main()
