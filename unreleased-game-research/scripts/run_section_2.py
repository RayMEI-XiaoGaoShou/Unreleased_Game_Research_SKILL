from __future__ import annotations

import argparse
import csv
import re
import subprocess
import sys
from urllib import parse
from pathlib import Path


STEP_ORDER = ["collect", "normalize", "sentiment", "topics", "charts", "finalize"]

STEP_ALIASES = {
    "collect": "collect",
    "normalize": "normalize",
    "sentiment": "sentiment",
    "classify": "sentiment",
    "classify_sentiment": "sentiment",
    "topics": "topics",
    "topic": "topics",
    "cluster": "topics",
    "cluster_topics": "topics",
    "charts": "charts",
    "build_charts": "charts",
    "finalize": "finalize",
    "finalize_section_2": "finalize",
}

STEP_FILE_REQUIREMENTS = {
    "normalize": {
        "comment_sample.csv": {"comment_id", "video_id", "text_original", "text_normalized", "is_spam_or_noise"},
    },
    "sentiment": {
        "comment_sample.csv": {"comment_id", "video_id", "text_normalized", "language", "sentiment_label"},
        "video_registry.csv": {"video_id", "milestone_id", "publish_date", "platform"},
    },
    "topics": {
        "comment_sample.csv": {"comment_id", "video_id", "text_normalized", "sentiment_label", "topic_label"},
        "video_registry.csv": {"video_id", "milestone_id", "publish_date", "platform"},
    },
    "charts": {
        "sentiment_summary.csv": {"video_id", "milestone_id", "positive_count", "neutral_count", "negative_count"},
        "topic_summary.csv": {"video_id", "milestone_id", "topic_label", "mention_count"},
    },
    "finalize": {
        "comment_sample.csv": {"comment_id", "video_id", "sentiment_label", "topic_label"},
        "video_registry.csv": {"video_id", "milestone_id", "publish_date", "platform"},
        "sentiment_summary.csv": {"video_id", "milestone_id", "positive_count", "neutral_count", "negative_count"},
        "topic_summary.csv": {"video_id", "milestone_id", "topic_label", "mention_count"},
    },
}

FILE_PRODUCER_STEP = {
    "comment_sample.csv": "collect",
    "video_registry.csv": "collect",
    "sentiment_summary.csv": "sentiment",
    "topic_summary.csv": "topics",
}

MANIFEST_REQUIRED_HEADERS = {"video_ref", "milestone_id"}
MANIFEST_OPTIONAL_HEADERS = {"notes", "platform"}

def extract_video_id_for_platform(video_ref: str, platform: str) -> str:
    if platform == "bilibili":
        # minimal inline extraction for runner validation
        if re.fullmatch(r"BV[1-9A-HJ-NP-Za-km-z]{10}", video_ref, re.IGNORECASE):
            return video_ref
        parsed = parse.urlparse(video_ref)
        for part in parsed.path.split("/"):
            if re.fullmatch(r"BV[1-9A-HJ-NP-Za-km-z]{10}", part, re.IGNORECASE):
                return part
        raise SystemExit(f"Could not parse Bilibili BV ID from: {video_ref}")
    else:
        return extract_youtube_video_id(video_ref)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the full Section 2 pipeline in one command.")
    parser.add_argument("video_ref", nargs="?", help="YouTube/Bilibili video ID or URL; required when starting from collect")
    parser.add_argument("--project-dir", required=True, help="Path to the target project directory")
    parser.add_argument("--milestone-id", help="Milestone identifier for this video; required when starting from collect")
    parser.add_argument("--platform", default="youtube", choices=["youtube", "bilibili"], help="Target platform for single-video collect")
    parser.add_argument("--api-key", help="YouTube Data API v3 key; otherwise use YOUTUBE_API_KEY")
    parser.add_argument("--cookie-file", help="Path to Bilibili cookie JSON file (used when platform is bilibili)")
    _ = parser.add_argument(
        "--capture-mode",
        default="full_capture",
        choices=["full_capture", "top_plus_recent", "stratified_sample"],
        help="Comment capture strategy passed to collect_youtube_comments.py",
    )
    _ = parser.add_argument("--max-comments", type=int, default=0, help="Maximum top-level comments to persist; 0 means no explicit cap")
    _ = parser.add_argument("--max-pages", type=int, default=300, help="Maximum comment pages to fetch (used when platform is bilibili); 0 means no explicit cap")
    _ = parser.add_argument("--include-replies", action="store_true", help="Also fetch reply comments")
    _ = parser.add_argument(
        "--max-replies-per-thread",
        type=int,
        default=100,
        help="Maximum replies to persist per top-level comment when replies are enabled",
    )
    _ = parser.add_argument("--content-type", default="official_video", help="Artifact content type label")
    _ = parser.add_argument("--official-status", default="official", help="Source official_status field")
    _ = parser.add_argument("--notes", default="", help="Extra note stored in registry outputs")
    _ = parser.add_argument("--dedupe", action="store_true", help="Drop duplicate normalized comment rows")
    _ = parser.add_argument("--theme-path", help="Optional path to chart theme JSON")
    _ = parser.add_argument("--manifest", help="Path to a CSV manifest for multi-video Section 2 collection.")
    resume_group = parser.add_mutually_exclusive_group()
    _ = resume_group.add_argument(
        "--skip-collect",
        action="store_true",
        help="Start from normalize and skip the collect step; requires existing Section 2 artifacts.",
    )
    _ = resume_group.add_argument(
        "--from-step",
        help="Resume from a specific step: collect, normalize, sentiment, topics, charts, finalize.",
    )
    _ = parser.add_argument("--list-steps", action="store_true", help="Print available Section 2 steps and prerequisites, then exit.")
    _ = parser.add_argument(
        "--check-readiness",
        action="store_true",
        help="Check which resume entry points are currently valid for this project directory, then exit.",
    )
    return parser.parse_args()


def build_script_path(script_name: str) -> Path:
    return Path(__file__).resolve().parent / script_name


def normalize_step_name(raw_step: str | None, skip_collect: bool) -> str:
    if skip_collect:
        return "normalize"
    if raw_step is None:
        return "collect"
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


def read_csv_rows(path: Path) -> tuple[list[dict[str, str]], set[str]]:
    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = set(reader.fieldnames or [])
        rows = [dict(row) for row in reader]
    return rows, fieldnames


def extract_youtube_video_id(video_ref: str) -> str:
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", video_ref):
        return video_ref

    parsed = parse.urlparse(video_ref)
    if parsed.netloc in {"youtu.be", "www.youtu.be"}:
        candidate = parsed.path.strip("/")
        if re.fullmatch(r"[A-Za-z0-9_-]{11}", candidate):
            return candidate

    if "youtube.com" in parsed.netloc or "youtube-nocookie.com" in parsed.netloc:
        qs = parse.parse_qs(parsed.query)
        candidate = qs.get("v", [""])[0]
        if re.fullmatch(r"[A-Za-z0-9_-]{11}", candidate):
            return candidate
        path_parts = [part for part in parsed.path.split("/") if part]
        if len(path_parts) >= 2 and path_parts[0] in {"embed", "shorts", "live"}:
            candidate = path_parts[1]
            if re.fullmatch(r"[A-Za-z0-9_-]{11}", candidate):
                return candidate

    raise SystemExit(f"Could not parse a YouTube video ID from manifest or input: {video_ref}")


def existing_registry_entries(section_dir: Path) -> tuple[set[str], set[str]]:
    video_registry_path = section_dir / "video_registry.csv"
    if not video_registry_path.exists():
        return set(), set()
    rows, _ = read_csv_rows(video_registry_path)
    existing_video_ids = {row.get("video_id", "").strip() for row in rows if row.get("video_id", "").strip()}
    existing_milestones = {row.get("milestone_id", "").strip() for row in rows if row.get("milestone_id", "").strip()}
    return existing_video_ids, existing_milestones


def parse_bool_text(value: str) -> bool:
    normalized = value.strip().casefold()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off", ""}:
        return False
    raise SystemExit(f"Invalid boolean value in manifest: {value}")


def parse_int_text(value: str, field_name: str) -> int:
    try:
        return int(value)
    except ValueError as exc:
        raise SystemExit(f"Invalid integer value for {field_name} in manifest: {value}") from exc


def load_manifest(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise SystemExit(f"Manifest file not found: {path}")
    rows, fieldnames = read_csv_rows(path)
    missing_headers = sorted(MANIFEST_REQUIRED_HEADERS - fieldnames)
    if missing_headers:
        raise SystemExit(f"Manifest missing required headers: {', '.join(missing_headers)}")
    unsupported_headers = sorted(fieldnames - MANIFEST_REQUIRED_HEADERS - MANIFEST_OPTIONAL_HEADERS)
    if unsupported_headers:
        raise SystemExit(f"Manifest has unsupported headers: {', '.join(unsupported_headers)}")
    if not rows:
        raise SystemExit(f"Manifest has no data rows: {path}")
    seen_video_refs: set[str] = set()
    seen_milestones: set[str] = set()
    for index, row in enumerate(rows, start=2):
        video_ref = (row.get("video_ref") or "").strip()
        milestone_id = (row.get("milestone_id") or "").strip()
        if not video_ref:
            raise SystemExit(f"Manifest row {index} is missing video_ref")
        if not milestone_id:
            raise SystemExit(f"Manifest row {index} is missing milestone_id")
        if video_ref in seen_video_refs:
            raise SystemExit(f"Manifest row {index} duplicates video_ref: {video_ref}")
        if milestone_id in seen_milestones:
            raise SystemExit(f"Manifest row {index} duplicates milestone_id: {milestone_id}")
        seen_video_refs.add(video_ref)
        seen_milestones.add(milestone_id)
    return rows


def validate_manifest_against_project(rows: list[dict[str, str]], section_dir: Path, default_platform: str) -> None:
    existing_video_ids, existing_milestones = existing_registry_entries(section_dir)
    seen_video_ids: set[str] = set()
    seen_milestones: set[str] = set()

    for index, row in enumerate(rows, start=2):
        video_ref = (row.get("video_ref") or "").strip()
        milestone_id = (row.get("milestone_id") or "").strip()
        platform = (row.get("platform") or default_platform).strip().casefold()
        video_id = extract_video_id_for_platform(video_ref, platform)

        if video_id in seen_video_ids:
            raise SystemExit(f"Manifest row {index} resolves to duplicate video_id: {video_id}")
        if milestone_id in seen_milestones:
            raise SystemExit(f"Manifest row {index} resolves to duplicate milestone_id: {milestone_id}")
        if video_id in existing_video_ids:
            raise SystemExit(f"Manifest row {index} conflicts with existing video_registry.csv video_id: {video_id}")
        if milestone_id in existing_milestones:
            raise SystemExit(f"Manifest row {index} conflicts with existing video_registry.csv milestone_id: {milestone_id}")

        seen_video_ids.add(video_id)
        seen_milestones.add(milestone_id)


def earliest_safe_step_for_files(file_names: list[str]) -> str:
    producer_indices = [STEP_ORDER.index(FILE_PRODUCER_STEP[name]) for name in file_names if name in FILE_PRODUCER_STEP]
    if not producer_indices:
        return "collect"
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
        try:
            header = read_csv_header(file_path)
        except SystemExit as exc:
            ok = False
            messages.append(str(exc))
            continue
        missing_headers = sorted(required_headers - header)
        if missing_headers:
            ok = False
            messages.append(f"invalid header in {file_path}: missing {', '.join(missing_headers)}")
        else:
            messages.append(f"ok: {file_path}")
    return ok, messages


def print_step_catalog() -> None:
    descriptions = {
        "collect": "Fetch YouTube metadata/comments and seed Section 2 artifacts.",
        "normalize": "Normalize comment text, language, and spam flags.",
        "sentiment": "Apply rule-based sentiment labels and build sentiment_summary.csv.",
        "topics": "Assign rule-based topic labels and build topic_summary.csv.",
        "charts": "Render lightweight SVG charts from Section 2 summaries.",
        "finalize": "Generate evidence_table.csv, milestone_delta.csv, and findings.md.",
    }
    print("Section 2 steps:")
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
    print(f"Section 2 readiness for: {section_dir}")
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

    if not missing_files and not invalid_headers:
        return

    advice_basis = missing_files or [entry.split(" ", 1)[0] for entry in invalid_headers]
    earliest_step = earliest_safe_step_for_files(advice_basis)
    lines = [f"Cannot start Section 2 runner from step '{start_step}'."]
    if missing_files:
        lines.append("Missing prerequisite files:")
        lines.extend(f"- {section_dir / file_name}" for file_name in missing_files)
    if invalid_headers:
        lines.append("Invalid prerequisite files:")
        lines.extend(f"- {entry}" for entry in invalid_headers)
    lines.append(f"Earliest safe step to retry from: {earliest_step}")
    ready_steps = [step for step in STEP_ORDER if step == "collect" or step_requirement_messages(step, section_dir)[0]]
    lines.append(f"Currently valid entry points: {', '.join(ready_steps)}")
    raise SystemExit("\n".join(lines))


def run_step(step_name: str, command: list[str]) -> None:
    print(f"[Section 2 Runner] Running {step_name}...", flush=True)
    completed = subprocess.run(command, check=False)
    if completed.returncode != 0:
        command_text = " ".join(command)
        raise SystemExit(f"Step failed: {step_name}\nCommand: {command_text}\nExit code: {completed.returncode}")


def build_collect_command(
    python_executable: str,
    project_dir: Path,
    args: argparse.Namespace,
    manifest_row: dict[str, str] | None = None,
) -> tuple[str, list[str]]:
    row = manifest_row or {}
    video_ref = (row.get("video_ref") or args.video_ref or "").strip()
    milestone_id = (row.get("milestone_id") or args.milestone_id or "").strip()
    
    # Platform resolution (v1: bilibili or youtube)
    platform = (row.get("platform") or getattr(args, "platform", "youtube")).strip().casefold()
    if platform not in {"youtube", "bilibili"}:
        raise SystemExit(f"Unsupported platform: {platform}")
        
    capture_mode = args.capture_mode.strip()
    max_comments = args.max_comments
    max_replies = args.max_replies_per_thread
    include_replies = args.include_replies
    content_type = args.content_type.strip()
    official_status = args.official_status.strip()
    notes = row.get("notes") if row.get("notes") is not None else args.notes

    if platform == "bilibili":
        script_name = "collect_bilibili_comments.py"
    else:
        script_name = "collect_youtube_comments.py"

    command = [
        python_executable,
        str(build_script_path(script_name)),
        video_ref,
        "--project-dir",
        str(project_dir),
        "--milestone-id",
        milestone_id,
    ]

    if platform == "youtube":
        command.extend(["--capture-mode", capture_mode, "--max-comments", str(max_comments)])
    elif platform == "bilibili":
        # bilibili collector uses sort-mode instead of capture-mode, and max-pages instead of max-comments
        sort_mode = "hot" if capture_mode == "top_plus_recent" else "time"
        command.extend(["--sort-mode", sort_mode, "--max-pages", str(getattr(args, "max_pages", 300))])

    command.extend([
        "--max-replies-per-thread",
        str(max_replies),
        "--content-type",
        content_type,
        "--official-status",
        official_status,
    ])
    
    if platform == "youtube" and args.api_key:
        command.extend(["--api-key", args.api_key])
    elif platform == "bilibili":
        cookie_file = getattr(args, "cookie_file", None)
        if cookie_file:
            command.extend(["--cookie-file", cookie_file])
            
    if platform == "youtube" and include_replies:
        command.append("--include-replies")
        
    if notes:
        command.extend(["--notes", notes])

    return milestone_id, command


def main() -> None:
    args = parse_args()
    python_executable = sys.executable
    project_dir = Path(args.project_dir).resolve()
    theme_path = Path(args.theme_path).resolve() if args.theme_path else (Path(__file__).resolve().parent.parent / "assets" / "chart_theme.json")
    manifest_path = Path(args.manifest).resolve() if args.manifest else None
    section_dir = project_dir / "section_2_official_video_comments"

    if args.list_steps:
        print_step_catalog()
        return

    if args.check_readiness:
        print_readiness_report(section_dir)
        return

    start_step = normalize_step_name(args.from_step, args.skip_collect)

    if start_step == "collect":
        if args.manifest and args.video_ref:
            raise SystemExit("Use either a single video_ref or --manifest when starting from collect, not both.")
        if not args.manifest and not args.video_ref:
            raise SystemExit("video_ref or --manifest is required when starting from collect.")
        if args.video_ref and not args.milestone_id:
            raise SystemExit("--milestone-id is required when using single-video collect mode.")
    else:
        validate_resume_prerequisites(start_step, section_dir)

    manifest_rows = load_manifest(manifest_path) if manifest_path and start_step == "collect" else []
    if manifest_rows:
        validate_manifest_against_project(manifest_rows, section_dir, args.platform)
    if manifest_path and start_step != "collect":
        print(f"[Section 2 Runner] Ignoring manifest because execution starts from '{start_step}'.", flush=True)

    normalize_cmd = [
        python_executable,
        str(build_script_path("normalize_text.py")),
        "--project-dir",
        str(project_dir),
    ]
    if args.dedupe:
        normalize_cmd.append("--dedupe")

    classify_cmd = [
        python_executable,
        str(build_script_path("classify_sentiment.py")),
        "--project-dir",
        str(project_dir),
    ]
    cluster_cmd = [
        python_executable,
        str(build_script_path("cluster_topics.py")),
        "--project-dir",
        str(project_dir),
    ]
    chart_cmd = [
        python_executable,
        str(build_script_path("build_charts.py")),
        "--project-dir",
        str(project_dir),
        "--theme-path",
        str(theme_path),
    ]
    finalize_cmd = [
        python_executable,
        str(build_script_path("finalize_section_2.py")),
        "--project-dir",
        str(project_dir),
    ]

    collect_steps: list[tuple[str, str, list[str]]] = []
    if start_step == "collect":
        if manifest_rows:
            platform_counts: dict[str, int] = {}
            for row in manifest_rows:
                resolved_platform = (row.get("platform") or args.platform).strip().casefold()
                platform_counts[resolved_platform] = platform_counts.get(resolved_platform, 0) + 1

            bilibili_count = platform_counts.get("bilibili", 0)
            youtube_count = platform_counts.get("youtube", 0)

            # Guard: floor division can produce 0 when count > budget, which would
            # disable the cap entirely (0 == no limit in the collector scripts).
            per_video_bilibili_pages = max(1, args.max_pages // bilibili_count) if bilibili_count > 0 else args.max_pages
            per_video_youtube_comments = (
                max(1, args.max_comments // youtube_count) if youtube_count > 0 and args.max_comments > 0 else args.max_comments
            )

            for row in manifest_rows:
                row_platform = (row.get("platform") or args.platform).strip().casefold()
                per_video_args = argparse.Namespace(**vars(args))
                if row_platform == "bilibili":
                    per_video_args.max_pages = per_video_bilibili_pages
                elif row_platform == "youtube":
                    per_video_args.max_comments = per_video_youtube_comments

                milestone_id, command = build_collect_command(python_executable, project_dir, per_video_args, row)
                collect_steps.append(("collect", f"collect_youtube_comments[{milestone_id}]", command))
        else:
            milestone_id, command = build_collect_command(python_executable, project_dir, args)
            collect_steps.append(("collect", f"collect_youtube_comments[{milestone_id}]", command))

    downstream_steps = [
        ("normalize", "normalize_text", normalize_cmd),
        ("sentiment", "classify_sentiment", classify_cmd),
        ("topics", "cluster_topics", cluster_cmd),
        ("charts", "build_charts", chart_cmd),
        ("finalize", "finalize_section_2", finalize_cmd),
    ]
    steps = collect_steps + downstream_steps

    if start_step == "collect":
        selected_steps = steps
        start_index = 0
    else:
        start_index = STEP_ORDER.index(start_step)
        downstream_order = STEP_ORDER[1:]
        selected_steps = downstream_steps[downstream_order.index(start_step):]

    if start_index > 0:
        skipped_steps = ", ".join(STEP_ORDER[:start_index])
        print(f"[Section 2 Runner] Starting from step '{start_step}'. Skipping earlier steps: {skipped_steps}", flush=True)
    elif manifest_rows:
        print(f"[Section 2 Runner] Starting manifest collection for {len(manifest_rows)} videos before downstream processing.", flush=True)

    total_steps = len(selected_steps)
    for index, (_, display_name, command) in enumerate(selected_steps, start=1):
        run_step(f"{index}/{total_steps} {display_name}", command)

    print("[Section 2 Runner] Pipeline completed successfully.")
    print(f"- section_dir: {section_dir}")
    print(f"- comment_sample: {section_dir / 'comment_sample.csv'}")
    print(f"- sentiment_summary: {section_dir / 'sentiment_summary.csv'}")
    print(f"- topic_summary: {section_dir / 'topic_summary.csv'}")
    print(f"- findings: {section_dir / 'findings.md'}")
    print(f"- charts: {section_dir / 'charts'}")


if __name__ == "__main__":
    main()
