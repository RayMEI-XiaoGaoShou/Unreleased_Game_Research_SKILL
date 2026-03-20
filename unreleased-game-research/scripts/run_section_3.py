from __future__ import annotations

import argparse
import csv
import re
import subprocess
import sys
from pathlib import Path

import importlib

section_3_common = importlib.import_module("section_3_common")
EVIDENCE_TABLE_HEADER = section_3_common.EVIDENCE_TABLE_HEADER
REVIEW_REGISTRY_HEADER = section_3_common.REVIEW_REGISTRY_HEADER
REVIEW_SAMPLE_HEADER = section_3_common.REVIEW_SAMPLE_HEADER
REVIEWER_TAGS_HEADER = section_3_common.REVIEWER_TAGS_HEADER
SECTION_DIR_NAME = section_3_common.SECTION_DIR_NAME
SENTIMENT_SUMMARY_HEADER = section_3_common.SENTIMENT_SUMMARY_HEADER
TOPIC_SUMMARY_HEADER = section_3_common.TOPIC_SUMMARY_HEADER
platform_from_url = section_3_common.platform_from_url


STEP_ORDER = ["capture", "annotate", "finalize"]

STEP_ALIASES = {
    "capture": "capture",
    "collect": "capture",
    "annotate": "annotate",
    "analyze": "annotate",
    "finalize": "finalize",
    "finalize_section_3": "finalize",
}

STEP_FILE_REQUIREMENTS = {
    "annotate": {
        "review_registry.csv": {"review_id", "platform", "url", "game_page_title", "review_publish_time", "review_length_bucket", "likes", "replies", "capture_method", "language", "is_longform", "notes"},
        "review_sample.csv": {"review_id", "platform", "author_name", "text_original", "text_normalized", "language", "likes", "replies", "sentiment_label", "topic_label", "experience_basis", "is_high_value", "confidence_note"},
    },
    "finalize": {
        "review_registry.csv": {"review_id", "platform", "url", "game_page_title", "review_publish_time", "review_length_bucket", "likes", "replies", "capture_method", "language", "is_longform", "notes"},
        "review_sample.csv": {"review_id", "platform", "sentiment_label", "topic_label", "experience_basis", "is_high_value"},
        "reviewer_tags.csv": {"review_id", "reviewer_tag", "tag_basis", "confidence_level", "notes"},
        "sentiment_summary.csv": {"platform", "positive_count", "neutral_count", "negative_count"},
        "topic_summary.csv": {"topic_label", "mention_count", "mention_ratio", "representative_evidence_id"},
    },
}

FILE_PRODUCER_STEP = {
    "review_registry.csv": "capture",
    "review_sample.csv": "capture",
    "reviewer_tags.csv": "annotate",
    "sentiment_summary.csv": "annotate",
    "topic_summary.csv": "annotate",
    "evidence_table.csv": "finalize",
    "findings.md": "finalize",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the full Section 3 homepage review pipeline in one command.")
    parser.add_argument("--project-dir", required=True, help="Path to the target project directory")
    parser.add_argument("--input-file", help="CSV, JSON, JSONL, or NDJSON review export used for capture fallback")
    parser.add_argument("--page-url", help="Source page URL for the imported review set")
    parser.add_argument("--game-page-title", help="Source page title for the imported review set")
    parser.add_argument("--platform", default="taptap", help="Review platform label, for example taptap or reservation_page")
    parser.add_argument("--secondary-page-url", help="Optional second source page URL, typically for Bilibili game comments")
    parser.add_argument("--secondary-platform", default="biligame", help="Platform label for the secondary source")
    parser.add_argument("--secondary-game-page-title", default="", help="Optional title override for the secondary source")
    parser.add_argument("--secondary-biligame-request-bundle-file", help="Request bundle file for the optional Bilibili secondary source")
    parser.add_argument("--capture-method", default="manual_import", help="Section 3 capture method stored in review_registry.csv")
    parser.add_argument("--access-method", default="manual", choices=["api", "browser", "manual", "transcript", "scrape"], help="Source registry access_method")
    parser.add_argument("--source-type", default="player review", help="Source registry source_type value")
    parser.add_argument("--official-status", default="unofficial", help="Source registry official_status value")
    parser.add_argument("--reliability-score", type=int, default=3, help="Source registry reliability score")
    parser.add_argument("--bias-risk", default="medium", choices=["low", "medium", "high"], help="Source registry bias_risk value")
    parser.add_argument("--max-reviews", type=int, default=100, help="Maximum reviews to capture for direct homepage-review crawling")
    parser.add_argument("--biligame-request-bundle-file", help="Path to a text or JSON bundle copied from a successful Bilibili comment request")
    parser.add_argument("--notes", default="", help="Extra note stored in capture and source outputs")
    resume_group = parser.add_mutually_exclusive_group()
    resume_group.add_argument("--skip-capture", action="store_true", help="Start from annotate and skip the capture step")
    resume_group.add_argument("--from-step", help="Resume from a specific step: capture, annotate, finalize")
    parser.add_argument("--list-steps", action="store_true", help="Print available Section 3 steps and prerequisites, then exit")
    parser.add_argument("--check-readiness", action="store_true", help="Check which resume entry points are currently valid for this project directory, then exit")
    return parser.parse_args()


def build_script_path(script_name: str) -> Path:
    return Path(__file__).resolve().parent / script_name


def biligame_guide_path() -> Path:
    return Path(__file__).resolve().parent.parent / "references" / "section_3_bilibili_semi_auto_guide.md"


def render_biligame_request_guidance() -> str:
    path = biligame_guide_path()
    body = path.read_text(encoding="utf-8") if path.exists() else "Guide file is missing."
    return (
        "Bilibili Section 3 semi-automatic capture needs a request bundle copied from browser DevTools.\n"
        f"Read and follow: {path}\n\n"
        f"{body}"
    )


def normalize_step_name(raw_step: str | None, skip_capture: bool) -> str:
    if skip_capture:
        return "annotate"
    if raw_step is None:
        return "capture"
    normalized = STEP_ALIASES.get(raw_step.casefold())
    if normalized is None:
        valid_steps = ", ".join(STEP_ORDER)
        raise SystemExit(f"Invalid --from-step value: {raw_step}. Valid values: {valid_steps}")
    return normalized


def ensure_section_files(section_dir: Path) -> None:
    section_dir.mkdir(parents=True, exist_ok=True)
    ensure_csv_header(section_dir / "review_registry.csv", REVIEW_REGISTRY_HEADER)
    ensure_csv_header(section_dir / "review_sample.csv", REVIEW_SAMPLE_HEADER)
    ensure_csv_header(section_dir / "reviewer_tags.csv", REVIEWER_TAGS_HEADER)
    ensure_csv_header(section_dir / "sentiment_summary.csv", SENTIMENT_SUMMARY_HEADER)
    ensure_csv_header(section_dir / "topic_summary.csv", TOPIC_SUMMARY_HEADER)
    ensure_csv_header(section_dir / "evidence_table.csv", EVIDENCE_TABLE_HEADER)
    findings_path = section_dir / "findings.md"
    if not findings_path.exists():
        findings_path.write_text("## Scope\n\n## Core Conclusions\n\n## What We Know\n\n## What We Infer\n\n## Key Evidence\n\n## Positive Signals\n\n## Negative Signals / Concerns\n\n## Disagreements / Mixed Signals\n\n## Confidence and Limitations\n\n## Open Questions\n", encoding="utf-8")


def ensure_csv_header(path: Path, header: list[str]) -> None:
    if path.exists():
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=header)
        writer.writeheader()


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
            next(reader)
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
        else:
            if not csv_has_data_rows(file_path):
                ok = False
                messages.append(f"missing data rows: {file_path}")
            else:
                messages.append(f"ok: {file_path}")
    return ok, messages


def print_step_catalog() -> None:
    descriptions = {
        "capture": "Import homepage or reservation reviews into Section 3 registry and sample files.",
        "annotate": "Apply heuristic sentiment, topic, experience, and reviewer-tag annotations.",
        "finalize": "Generate evidence_table.csv and findings.md from annotated Section 3 artifacts.",
    }
    print("Section 3 steps:")
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
    print(f"Section 3 readiness for: {section_dir}")
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
    lines = [f"Cannot start Section 3 runner from step '{start_step}'."]
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
    print(f"[Section 3 Runner] Running {step_name}...", flush=True)
    completed = subprocess.run(command, check=False)
    if completed.returncode != 0:
        raise SystemExit(f"Step failed: {step_name}\nCommand: {' '.join(command)}\nExit code: {completed.returncode}")


def select_capture_script(page_url: str | None, platform: str) -> str:
    if page_url:
        detected = platform_from_url(page_url)
        if detected in {"biligame", "bilibili"} or platform.casefold() in {"biligame", "bilibili"}:
            return "capture_bilibili_page.py"
    return "capture_taptap_reviews.py"


def resolve_capture_defaults(
    capture_script: str,
    capture_method: str,
    access_method: str,
    page_url: str | None,
    has_direct_url: bool,
) -> tuple[str, str]:
    if not has_direct_url:
        return capture_method, access_method
    resolved_capture_method = capture_method
    resolved_access_method = access_method
    if capture_script == "capture_taptap_reviews.py":
        if re.search(r"/review/\d+", page_url or ""):
            if capture_method == "manual_import":
                resolved_capture_method = "direct_html_fetch"
            if access_method == "manual":
                resolved_access_method = "scrape"
        else:
            if capture_method == "manual_import":
                resolved_capture_method = "direct_review_api_fetch"
            if access_method == "manual":
                resolved_access_method = "api"
    elif capture_script == "capture_bilibili_page.py":
        if capture_method == "manual_import":
            resolved_capture_method = "semi_auto_signed_request"
        if access_method == "manual":
            resolved_access_method = "api"
    return resolved_capture_method, resolved_access_method


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
    if start_step == "capture":
        if not args.input_file and not args.page_url:
            raise SystemExit("Capture requires either --page-url for direct crawl or --input-file for manual import fallback.")
        capture_script_preview = select_capture_script(args.page_url, args.platform)
        # Only require request bundle for direct-crawl mode; manual --input-file bypasses scraping entirely
        if capture_script_preview == "capture_bilibili_page.py" and not args.biligame_request_bundle_file and not args.input_file:
            raise SystemExit(render_biligame_request_guidance())
        if args.secondary_page_url:
            secondary_capture_script = select_capture_script(args.secondary_page_url, args.secondary_platform)
            if secondary_capture_script == "capture_bilibili_page.py" and not args.secondary_biligame_request_bundle_file:
                raise SystemExit(render_biligame_request_guidance())
    else:
        validate_resume_prerequisites(start_step, section_dir)

    python_executable = sys.executable
    capture_script = select_capture_script(args.page_url, args.platform)
    capture_method_value, access_method_value = resolve_capture_defaults(
        capture_script,
        args.capture_method,
        args.access_method,
        args.page_url,
        bool(args.page_url and not args.input_file),
    )
    capture_cmd = [
        python_executable,
        str(build_script_path(capture_script)),
        "--project-dir",
        str(project_dir),
        "--platform",
        args.platform,
        "--capture-method",
        capture_method_value,
        "--access-method",
        access_method_value,
        "--source-type",
        args.source_type,
        "--official-status",
        args.official_status,
        "--reliability-score",
        str(args.reliability_score),
        "--bias-risk",
        args.bias_risk,
    ]
    if args.input_file:
        capture_cmd.extend(["--input-file", args.input_file])
    if args.page_url:
        capture_cmd.extend(["--page-url", args.page_url])
    if args.game_page_title:
        capture_cmd.extend(["--game-page-title", args.game_page_title])
    if args.notes:
        capture_cmd.extend(["--notes", args.notes])
    if capture_script == "capture_taptap_reviews.py":
        capture_cmd.extend(["--max-reviews", str(args.max_reviews)])
    if capture_script == "capture_bilibili_page.py" and args.biligame_request_bundle_file:
        capture_cmd.extend(["--request-bundle-file", args.biligame_request_bundle_file])

    secondary_capture_cmd: list[str] | None = None
    if args.secondary_page_url:
        secondary_capture_script = select_capture_script(args.secondary_page_url, args.secondary_platform)
        secondary_capture_method, secondary_access_method = resolve_capture_defaults(
            secondary_capture_script,
            args.capture_method,
            args.access_method,
            args.secondary_page_url,
            True,
        )
        secondary_capture_cmd = [
            python_executable,
            str(build_script_path(secondary_capture_script)),
            "--project-dir",
            str(project_dir),
            "--platform",
            args.secondary_platform,
            "--capture-method",
            secondary_capture_method,
            "--access-method",
            secondary_access_method,
            "--source-type",
            args.source_type,
            "--official-status",
            args.official_status,
            "--reliability-score",
            str(args.reliability_score),
            "--bias-risk",
            args.bias_risk,
            "--page-url",
            args.secondary_page_url,
        ]
        if args.secondary_game_page_title:
            secondary_capture_cmd.extend(["--game-page-title", args.secondary_game_page_title])
        if args.notes:
            secondary_capture_cmd.extend(["--notes", args.notes])
        if secondary_capture_script == "capture_taptap_reviews.py":
            secondary_capture_cmd.extend(["--max-reviews", str(args.max_reviews)])
        if secondary_capture_script == "capture_bilibili_page.py" and args.secondary_biligame_request_bundle_file:
            secondary_capture_cmd.extend(["--request-bundle-file", args.secondary_biligame_request_bundle_file])

    annotate_cmd = [python_executable, str(build_script_path("annotate_section_3_reviews.py")), "--project-dir", str(project_dir)]
    finalize_cmd = [python_executable, str(build_script_path("finalize_section_3.py")), "--project-dir", str(project_dir)]

    steps = [
        ("capture", capture_script.replace(".py", ""), capture_cmd),
        ("annotate", "annotate_section_3_reviews", annotate_cmd),
        ("finalize", "finalize_section_3", finalize_cmd),
    ]
    start_index = STEP_ORDER.index(start_step)
    selected_steps = steps[start_index:]
    if start_index > 0:
        skipped_steps = ", ".join(name for name, _, _ in steps[:start_index])
        print(f"[Section 3 Runner] Starting from step '{start_step}'. Skipping earlier steps: {skipped_steps}", flush=True)

    total_steps = len(selected_steps)
    for index, (_, display_name, command) in enumerate(selected_steps, start=1):
        run_step(f"{index}/{total_steps} {display_name}", command)
        if display_name == capture_script.replace(".py", "") and secondary_capture_cmd is not None:
            run_step(f"{index}/{total_steps} {Path(secondary_capture_cmd[1]).stem}", secondary_capture_cmd)

    print("[Section 3 Runner] Pipeline completed successfully.")
    print(f"- section_dir: {section_dir}")
    print(f"- review_registry: {section_dir / 'review_registry.csv'}")
    print(f"- review_sample: {section_dir / 'review_sample.csv'}")
    print(f"- reviewer_tags: {section_dir / 'reviewer_tags.csv'}")
    print(f"- sentiment_summary: {section_dir / 'sentiment_summary.csv'}")
    print(f"- topic_summary: {section_dir / 'topic_summary.csv'}")
    print(f"- evidence_table: {section_dir / 'evidence_table.csv'}")
    print(f"- findings: {section_dir / 'findings.md'}")


if __name__ == "__main__":
    main()
