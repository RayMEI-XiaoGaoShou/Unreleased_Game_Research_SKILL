from __future__ import annotations

import argparse
import csv
import importlib
from pathlib import Path

smart_fetch = importlib.import_module("smart_fetch")
download_subtitles_or_audio = smart_fetch.download_subtitles_or_audio

section_4_common = importlib.import_module("section_4_common")
ensure_section_files = section_4_common.ensure_section_files
read_csv_rows = section_4_common.read_csv_rows


MEDIA_MANIFEST_HEADER = [
    "video_id",
    "url",
    "media_kind",
    "download_status",
    "file_path",
    "notes",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare Section 4 raw media for transcription.")
    parser.add_argument("--project-dir", required=True, help="Path to an initialized project directory")
    parser.add_argument("--audio-format", default="mp3", choices=["wav", "mp3", "flac", "m4a"], help="Fallback extracted audio format")
    return parser.parse_args()


def write_manifest(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=MEDIA_MANIFEST_HEADER)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    args = parse_args()
    project_dir = Path(args.project_dir).resolve()
    section_dir = ensure_section_files(project_dir)
    raw_media_dir = section_dir / "raw_media"
    raw_media_dir.mkdir(parents=True, exist_ok=True)

    candidate_rows = read_csv_rows(section_dir / "candidate_videos.csv")
    selected_rows = read_csv_rows(section_dir / "selected_videos.csv")
    candidate_by_video = {row.get("video_id", ""): row for row in candidate_rows}
    manifest_rows: list[dict[str, str]] = []

    for selected_row in selected_rows:
        video_id = selected_row.get("video_id", "")
        candidate_row = candidate_by_video.get(video_id, {})
        url = candidate_row.get("url", "")
        if not url:
            manifest_rows.append(
                {
                    "video_id": video_id,
                    "url": "",
                    "media_kind": "none",
                    "download_status": "failed",
                    "file_path": "",
                    "notes": "missing video url",
                }
            )
            continue

        has_subs, file_path = download_subtitles_or_audio(url, raw_media_dir, args.audio_format)
        if file_path is None:
            manifest_rows.append(
                {
                    "video_id": video_id,
                    "url": url,
                    "media_kind": "none",
                    "download_status": "failed",
                    "file_path": "",
                    "notes": "download failed",
                }
            )
            continue

        manifest_rows.append(
            {
                "video_id": video_id,
                "url": url,
                "media_kind": "subtitle" if has_subs else "audio",
                "download_status": "success",
                "file_path": str(file_path.resolve()),
                "notes": "native subtitles" if has_subs else "audio extracted",
            }
        )

    manifest_path = section_dir / "media_manifest.csv"
    write_manifest(manifest_path, manifest_rows)
    success_count = sum(1 for row in manifest_rows if row["download_status"] == "success")
    print(f"Prepared media for {success_count}/{len(manifest_rows)} selected videos: {manifest_path}")


if __name__ == "__main__":
    main()
