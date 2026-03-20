from __future__ import annotations

import argparse
import concurrent.futures
import csv
import importlib
import re
import subprocess
import sys
from pathlib import Path

section_4_common = importlib.import_module("section_4_common")
# Only imports still needed after the Section 4 refactor (transcript .txt flow).
# parse_srt_like / load_rows_from_generated_file kept for subtitle-first fallback path.
derive_segment_id = section_4_common.derive_segment_id
normalize_text_value = section_4_common.normalize_text_value
read_csv_rows = section_4_common.read_csv_rows
ensure_section_files = section_4_common.ensure_section_files


MEDIA_MANIFEST_HEADER = [
    "video_id",
    "url",
    "media_kind",
    "download_status",
    "file_path",
    "notes",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate transcript_segments.csv from downloaded Section 4 media.")
    parser.add_argument("--project-dir", required=True, help="Path to an initialized project directory")
    parser.add_argument("--provider", default="auto", choices=["auto", "local-whisper", "volcengine", "manual-template"], help="Automatic transcript generation backend")
    parser.add_argument("--model", default="base", help="Whisper model name when local-whisper is used")
    parser.add_argument("--language", default="zh-CN", help="Language code for ASR (default: zh-CN for Chinese)")
    parser.add_argument("--volcengine-api-key", help="Volcano Engine API Key (or set VOLCENGINE_ASR_TOKEN env var)")
    parser.add_argument("--manual-fallback", action="store_true", help="Allow local whisper to fall back to a manual CSV template")
    return parser.parse_args()


def parse_srt_like(path: Path, video_id: str) -> list[dict[str, str]]:
    content = path.read_text(encoding="utf-8")
    chunks = re.split(r"\r?\n\r?\n", content.strip())
    rows: list[dict[str, str]] = []
    for index, chunk in enumerate(chunks, start=1):
        lines = [line.strip() for line in chunk.splitlines() if line.strip()]
        if not lines:
            continue
        if lines[0].casefold() == "webvtt":
            continue
        time_line = ""
        text_lines: list[str] = []
        for position, line in enumerate(lines):
            if "-->" in line:
                time_line = line.replace(",", ".")
                text_lines = lines[position + 1 :]
                break
        if not time_line:
            continue
        start, end = [part.strip() for part in time_line.split("-->", maxsplit=1)]
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


def load_rows_from_generated_file(path: Path, video_id: str) -> list[dict[str, str]]:
    suffix = path.suffix.casefold()
    if suffix in {".srt", ".vtt"}:
        return parse_srt_like(path, video_id)
    if suffix == ".csv":
        rows = read_csv_rows(path)
        normalized: list[dict[str, str]] = []
        for index, row in enumerate(rows, start=1):
            quote_original = row.get("quote_original", "").strip()
            if not quote_original:
                continue
            normalized.append(
                {
                    "segment_id": row.get("segment_id", "") or derive_segment_id(video_id, index),
                    "video_id": row.get("video_id", "") or video_id,
                    "timestamp_start": row.get("timestamp_start", ""),
                    "timestamp_end": row.get("timestamp_end", ""),
                    "quote_original": quote_original,
                    "quote_normalized": row.get("quote_normalized", "") or normalize_text_value(quote_original),
                    "topic_label": row.get("topic_label", ""),
                    "claim_type": row.get("claim_type", ""),
                    "supports_positive_or_negative": row.get("supports_positive_or_negative", ""),
                    "visible_footage_support": row.get("visible_footage_support", ""),
                    "cross_source_support": row.get("cross_source_support", ""),
                    "confidence_level": row.get("confidence_level", ""),
                }
            )
        return normalized
    raise SystemExit(f"Unsupported generated transcript file: {path}")


def run_local_transcribe(script_path: Path, media_path: Path, output_dir: Path, video_id: str, provider: str, model: str, language: str | None, manual_fallback: bool) -> Path:
    command = [
        sys.executable,
        str(script_path),
        str(media_path),
        "--output-dir",
        str(output_dir),
        "--video-id",
        video_id,
        "--engine",
        "whisper" if provider in {"auto", "local-whisper"} else "manual-template",
        "--model",
        model,
    ]
    if language:
        command.extend(["--language", language])
    if manual_fallback or provider == "auto":
        command.append("--manual-fallback")
    completed = subprocess.run(command, check=False)
    if completed.returncode != 0:
        raise SystemExit(f"Transcription failed for {media_path} with provider {provider}")

    srt_path = output_dir / f"{media_path.stem}.srt"
    if srt_path.exists():
        return srt_path
    template_path = output_dir / f"{media_path.stem}_manual_segments.csv"
    if template_path.exists():
        return template_path
    raise SystemExit(f"Transcription succeeded but no output file found for {media_path}")


def run_volcengine_transcribe(
    script_path: Path,
    media_path: Path,
    output_dir: Path,
    video_id: str,
    language: str,
    api_key: str | None,
) -> Path:
    """Transcribe audio using Volcano Engine ASR."""
    command = [
        sys.executable,
        str(script_path),
        str(media_path),
        "--output-dir",
        str(output_dir),
        "--video-id",
        video_id,
        "--language",
        language,
    ]
    if api_key:
        command.extend(["--api-key", api_key])
    
    completed = subprocess.run(command, check=False)
    if completed.returncode != 0:
        raise SystemExit(f"Volcano Engine transcription failed for {media_path}")
    
    output_path = output_dir / f"{media_path.stem}_volcengine.txt"
    if output_path.exists():
        return output_path
    raise SystemExit(f"Volcano Engine transcription succeeded but no output file found for {media_path}")


def process_row(
    row: dict[str, str],
    args: argparse.Namespace,
    generated_dir: Path,
    volcengine_script: Path,
    transcribe_script: Path,
) -> Path | None:
    if row.get("download_status") != "success":
        return None
    video_id = row.get("video_id", "")
    file_path_str = row.get("file_path", "").strip()
    if not file_path_str:
        print(f"  Skipping video {video_id}: empty file_path in manifest")
        return None
    media_path = Path(file_path_str)
    if not media_path.is_file():
        print(f"  Skipping video {video_id}: file not found: {media_path}")
        return None
    media_kind = row.get("media_kind", "")
    if media_kind == "subtitle":
        # Convert subtitle (.srt/.vtt) to plain text for Agent consumption
        txt_path = generated_dir / f"{media_path.stem}_subtitle.txt"
        try:
            content = media_path.read_text(encoding="utf-8")
            import re as _re
            # Strip timestamp lines and index numbers, keep text only
            lines = [l.strip() for l in content.splitlines()]
            text_lines = [l for l in lines if l and not _re.match(r"^\d+$", l) and "-->" not in l and l.upper() != "WEBVTT"]
            txt_path.write_text("\n".join(text_lines), encoding="utf-8")
        except Exception as exc:
            raise RuntimeError(f"Failed to convert subtitle {media_path} to txt: {exc}") from exc
        return txt_path
    elif args.provider == "volcengine":
        return run_volcengine_transcribe(
            volcengine_script,
            media_path,
            generated_dir,
            video_id,
            args.language,
            args.volcengine_api_key,
        )
    else:
        return run_local_transcribe(
            transcribe_script,
            media_path,
            generated_dir,
            video_id,
            args.provider,
            args.model,
            args.language,
            args.manual_fallback,
        )


def main() -> None:
    args = parse_args()
    project_dir = Path(args.project_dir).resolve()
    section_dir = ensure_section_files(project_dir)
    manifest_path = section_dir / "media_manifest.csv"
    if not manifest_path.exists():
        raise SystemExit(f"Missing media manifest: {manifest_path}")
    manifest_rows = read_csv_rows(manifest_path)
    if not manifest_rows:
        raise SystemExit("media_manifest.csv has no data rows")

    generated_dir = section_dir / "generated_transcripts"
    generated_dir.mkdir(parents=True, exist_ok=True)
    transcribe_script = Path(__file__).resolve().parent / "transcribe_audio.py"
    volcengine_script = Path(__file__).resolve().parent / "transcribe_with_volcengine.py"

    generated_txt_files = []
    
    # Use ThreadPoolExecutor for parallel transcription
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            executor.submit(
                process_row, row, args, generated_dir, volcengine_script, transcribe_script
            ): row
            for row in manifest_rows
        }
        
        for future in concurrent.futures.as_completed(futures):
            row = futures[future]
            try:
                generated_path = future.result()
                if generated_path:
                    generated_txt_files.append(generated_path)
            except SystemExit as e:
                # Workers raise SystemExit for expected failures; convert to logged error
                print(f"Error processing video {row.get('video_id')}: {e}")
            except Exception as e:
                print(f"Error processing video {row.get('video_id')}: {e}")

    if not generated_txt_files:
        raise SystemExit("No transcript files were generated from media_manifest.csv")

    print(f"Generated {len(generated_txt_files)} transcript text files in {generated_dir}")


if __name__ == "__main__":
    main()
