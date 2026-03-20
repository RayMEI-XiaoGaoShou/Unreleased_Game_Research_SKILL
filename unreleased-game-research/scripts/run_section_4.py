from __future__ import annotations

import argparse
import csv
import importlib
import subprocess
import sys
from pathlib import Path

section_4_common = importlib.import_module("section_4_common")
CANDIDATE_VIDEOS_HEADER = section_4_common.CANDIDATE_VIDEOS_HEADER
CLAIM_EVIDENCE_MAP_HEADER = section_4_common.CLAIM_EVIDENCE_MAP_HEADER
CREATOR_PROFILES_HEADER = section_4_common.CREATOR_PROFILES_HEADER
EVIDENCE_TABLE_HEADER = section_4_common.EVIDENCE_TABLE_HEADER
FINDINGS_TEMPLATE = section_4_common.FINDINGS_TEMPLATE
SECTION_DIR_NAME = section_4_common.SECTION_DIR_NAME
SELECTED_VIDEOS_HEADER = section_4_common.SELECTED_VIDEOS_HEADER
TOPIC_CONSENSUS_HEADER = section_4_common.TOPIC_CONSENSUS_HEADER
TRANSCRIPT_SEGMENTS_HEADER = section_4_common.TRANSCRIPT_SEGMENTS_HEADER
ensure_csv = section_4_common.ensure_csv


STEP_ORDER = ["capture", "fetch_media", "transcripts"]

STEP_ALIASES = {
    "capture": "capture",
    "collect": "capture",
    "import": "capture",
    "fetch_media": "fetch_media",
    "fetch": "fetch_media",
    "media": "fetch_media",
    "transcripts": "transcripts",
    "transcript": "transcripts",
}

STEP_FILE_REQUIREMENTS = {
    "fetch_media": {
        "candidate_videos.csv": set(CANDIDATE_VIDEOS_HEADER),
        "selected_videos.csv": set(SELECTED_VIDEOS_HEADER),
    },
    "transcripts": {
        "candidate_videos.csv": set(CANDIDATE_VIDEOS_HEADER),
        "selected_videos.csv": set(SELECTED_VIDEOS_HEADER),
    },
}

FILE_PRODUCER_STEP = {
    "candidate_videos.csv": "capture",
    "selected_videos.csv": "capture",
    "creator_profiles.csv": "capture",
    "media_manifest.csv": "fetch_media",
    "generated_transcripts": "transcripts",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the full Section 4 creator-review pipeline in one command.")
    _ = parser.add_argument("--project-dir", required=True, help="Path to the target project directory")
    _ = parser.add_argument("--candidates-file", help="Manual candidate-video CSV/JSON export used for the capture step")
    _ = parser.add_argument("--transcripts-file", help="Transcript CSV/JSON/SRT used for the transcripts step")
    _ = parser.add_argument("--transcript-video-id", help="Required when transcripts-file is a single SRT file without embedded video_id")
    _ = parser.add_argument("--notes", default="", help="Extra note stored in imported candidate rows")
    _ = parser.add_argument("--auto-transcribe", action="store_true", help="Automatically fetch media and generate transcripts when no transcripts-file is supplied")
    _ = parser.add_argument("--stt-provider", default="volcengine", choices=["auto", "local-whisper", "volcengine", "manual-template"], help="Automatic transcript provider (default: volcengine)")
    _ = parser.add_argument("--stt-model", default="base", help="Model name for local whisper transcription")
    _ = parser.add_argument("--stt-language", default="zh-CN", help="Language code for ASR (default: zh-CN for Chinese)")
    _ = parser.add_argument("--volcengine-api-key", help="Volcano Engine API Key (or set VOLCENGINE_ASR_TOKEN env var)")
    _ = parser.add_argument("--audio-format", default="mp3", choices=["wav", "mp3", "flac", "m4a"], help="Fallback extracted audio format")
    _ = parser.add_argument("--manual-fallback", action="store_true", help="Allow automatic STT to fall back to a manual transcript template")
    resume_group = parser.add_mutually_exclusive_group()
    _ = resume_group.add_argument("--skip-capture", action="store_true", help="Start from fetch_media and skip the capture step")
    _ = resume_group.add_argument("--from-step", help="Resume from a specific step: capture, fetch_media, transcripts")
    _ = parser.add_argument("--list-steps", action="store_true", help="Print available Section 4 steps and prerequisites, then exit")
    _ = parser.add_argument("--check-readiness", action="store_true", help="Check which resume entry points are valid for this project directory, then exit")
    return parser.parse_args()


def build_script_path(script_name: str) -> Path:
    return Path(__file__).resolve().parent / script_name


def ensure_section_files(section_dir: Path) -> None:
    section_dir.mkdir(parents=True, exist_ok=True)
    ensure_csv(section_dir / "candidate_videos.csv", CANDIDATE_VIDEOS_HEADER)
    ensure_csv(section_dir / "selected_videos.csv", SELECTED_VIDEOS_HEADER)
    ensure_csv(section_dir / "creator_profiles.csv", CREATOR_PROFILES_HEADER)
    # transcript_segments.csv and claim_evidence_map.csv are legacy artifacts.
    # Section 4 now produces per-video .txt files in generated_transcripts/
    # and Agent writes findings.md directly. These CSVs are no longer auto-created.
    ensure_csv(section_dir / "evidence_table.csv", EVIDENCE_TABLE_HEADER)
    findings_path = section_dir / "findings.md"
    if not findings_path.exists():
        _ = findings_path.write_text(FINDINGS_TEMPLATE, encoding="utf-8")


def normalize_step_name(raw_step: str | None, skip_capture: bool) -> str:
    if skip_capture:
        return "fetch_media"
    if raw_step is None:
        return "capture"
    normalized = STEP_ALIASES.get(raw_step.casefold())
    if normalized is None:
        valid_steps = ", ".join(STEP_ORDER)
        raise SystemExit(f"Invalid --from-step value: {raw_step}. Valid values: {valid_steps}")
    return normalized


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


def earliest_safe_step_for_files(file_names: list[str]) -> str:
    producer_indices = [STEP_ORDER.index(FILE_PRODUCER_STEP[name]) for name in file_names if name in FILE_PRODUCER_STEP]
    if not producer_indices:
        return "capture"
    return STEP_ORDER[min(producer_indices)]


def step_requirement_messages(step_name: str, section_dir: Path) -> tuple[bool, list[str]]:
    requirements = STEP_FILE_REQUIREMENTS.get(step_name, {})
    if not requirements:
        return True, ["No prerequisite files required."]
    messages: list[str] = []
    ok = True
    for file_name, required_headers in requirements.items():
        file_path = section_dir / file_name
        if not file_path.exists():
            ok = False
            messages.append(f"missing file: {file_path}")
            continue
        header = read_csv_header(file_path)
        missing_headers = sorted(required_headers - header)
        if missing_headers:
            ok = False
            messages.append(f"invalid header in {file_path}: missing {', '.join(missing_headers)}")
            continue
        if not csv_has_data_rows(file_path):
            ok = False
            messages.append(f"missing data rows: {file_path}")
            continue
        messages.append(f"ok: {file_path}")
    return ok, messages


def print_step_catalog() -> None:
    descriptions = {
        "capture": "Import manual candidate creator videos into candidate/selected/profile artifacts.",
        "fetch_media": "Download native subtitles or extract audio for the selected creator videos.",
        "transcripts": "Transcribe audio via Volcano Engine ASR (or local Whisper) → write per-video .txt files in generated_transcripts/. Agent then reads txts and writes findings.md.",
    }
    print("Section 4 steps:")
    for step in STEP_ORDER:
        print(f"- {step}: {descriptions[step]}")
        requirements = STEP_FILE_REQUIREMENTS.get(step)
        if not requirements:
            print("  prerequisites: none")
            continue
        print("  prerequisites:")
        for file_name, headers in requirements.items():
            print(f"  - {file_name} [{', '.join(sorted(headers))}]")


def print_readiness_report(section_dir: Path) -> None:
    print(f"Section 4 readiness for: {section_dir}")
    for step in STEP_ORDER:
        ok, messages = step_requirement_messages(step, section_dir)
        status = "READY" if ok else "BLOCKED"
        print(f"- {step}: {status}")
        for message in messages:
            print(f"  {message}")


def validate_resume_prerequisites(start_step: str, section_dir: Path) -> None:
    requirements = STEP_FILE_REQUIREMENTS.get(start_step, {})
    missing_files: list[str] = []
    invalid_headers: list[str] = []
    for file_name, required_headers in requirements.items():
        file_path = section_dir / file_name
        if not file_path.exists():
            missing_files.append(file_name)
            continue
        header = read_csv_header(file_path)
        missing_headers = sorted(required_headers - header)
        if missing_headers:
            invalid_headers.append(f"{file_name} missing headers: {', '.join(missing_headers)}")
            continue
        if not csv_has_data_rows(file_path):
            invalid_headers.append(f"{file_name} has header only and no data rows")
    if not missing_files and not invalid_headers:
        return
    advice_basis = missing_files or [entry.split(" ", 1)[0] for entry in invalid_headers]
    earliest_step = earliest_safe_step_for_files(advice_basis)
    lines = [f"Cannot start Section 4 runner from step '{start_step}'."]
    if missing_files:
        lines.append("Missing prerequisite files:")
        lines.extend(f"- {section_dir / file_name}" for file_name in missing_files)
    if invalid_headers:
        lines.append("Invalid prerequisite files:")
        lines.extend(f"- {entry}" for entry in invalid_headers)
    lines.append(f"Earliest safe step to retry from: {earliest_step}")
    ready_steps = [step for step in STEP_ORDER if step == "capture" or step_requirement_messages(step, section_dir)[0]]
    lines.append(f"Currently valid entry points: {', '.join(ready_steps)}")
    raise SystemExit("\n".join(lines))


def run_step(step_name: str, command: list[str]) -> None:
    print(f"[Section 4 Runner] Running {step_name}...", flush=True)
    completed = subprocess.run(command, check=False)
    if completed.returncode != 0:
        raise SystemExit(f"Step failed: {step_name}\nCommand: {' '.join(command)}\nExit code: {completed.returncode}")


def main() -> None:
    args = parse_args()
    project_dir = Path(args.project_dir).resolve()
    section_dir = project_dir / SECTION_DIR_NAME
    ensure_section_files(section_dir)

    if args.list_steps:
        print_step_catalog()
        return
    if args.check_readiness:
        print_readiness_report(section_dir)
        return

    start_step = normalize_step_name(args.from_step, args.skip_capture)
    if start_step == "capture" and not args.candidates_file:
        raise SystemExit("--candidates-file is required when starting from capture.")
    if start_step == "transcripts" and not args.auto_transcribe and not args.transcripts_file:
        raise SystemExit("--transcripts-file is required when starting from the transcripts step without --auto-transcribe.")
    if start_step != "capture":
        validate_resume_prerequisites(start_step, section_dir)

    python_executable = sys.executable
    capture_cmd = [
        python_executable,
        str(build_script_path("import_section_4_candidates.py")),
        "--project-dir",
        str(project_dir),
        "--input-file",
        args.candidates_file or "",
    ]
    if args.notes:
        capture_cmd.extend(["--notes", args.notes])

    fetch_media_cmd = [
        python_executable,
        str(build_script_path("prepare_section_4_media.py")),
        "--project-dir",
        str(project_dir),
        "--audio-format",
        args.audio_format,
    ]

    manual_transcripts_cmd = [
        python_executable,
        str(build_script_path("import_section_4_transcripts.py")),
        "--project-dir",
        str(project_dir),
        "--input-file",
        args.transcripts_file or "",
    ]
    if args.transcript_video_id:
        manual_transcripts_cmd.extend(["--video-id", args.transcript_video_id])

    auto_transcripts_cmd = [
        python_executable,
        str(build_script_path("generate_section_4_transcripts.py")),
        "--project-dir",
        str(project_dir),
        "--provider",
        args.stt_provider,
        "--model",
        args.stt_model,
        "--language",
        args.stt_language,
    ]
    if args.volcengine_api_key:
        auto_transcripts_cmd.extend(["--volcengine-api-key", args.volcengine_api_key])
    if args.manual_fallback or args.stt_provider == "auto":
        auto_transcripts_cmd.append("--manual-fallback")

    steps = [
        ("capture", "import_section_4_candidates", capture_cmd),
        ("fetch_media", "prepare_section_4_media", fetch_media_cmd),
        ("transcripts", "generate_section_4_transcripts" if args.auto_transcribe else "import_section_4_transcripts", auto_transcripts_cmd if args.auto_transcribe else manual_transcripts_cmd),
    ]
    start_index = STEP_ORDER.index(start_step)
    selected_steps = steps[start_index:]
    if start_index > 0:
        skipped_steps = ", ".join(name for name, _, _ in steps[:start_index])
        _ = print(f"[Section 4 Runner] Starting from step '{start_step}'. Skipping earlier steps: {skipped_steps}", flush=True)

    total_steps = len(selected_steps)
    for index, (_, display_name, command) in enumerate(selected_steps, start=1):
        if display_name == "import_section_4_transcripts" and not args.transcripts_file:
            raise SystemExit("--transcripts-file is required to run the transcripts step without --auto-transcribe.")
        run_step(f"{index}/{total_steps} {display_name}", command)

    print("[Section 4 Runner] Pipeline completed successfully.")
    print(f"- section_dir: {section_dir}")
    print(f"- candidate_videos: {section_dir / 'candidate_videos.csv'}")
    print(f"- selected_videos: {section_dir / 'selected_videos.csv'}")
    print(f"- media_manifest: {section_dir / 'media_manifest.csv'}")
    print(f"- generated_transcripts: {section_dir / 'generated_transcripts'}")


if __name__ == "__main__":
    main()
