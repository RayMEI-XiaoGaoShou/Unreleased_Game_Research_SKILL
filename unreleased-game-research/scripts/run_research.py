from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


SECTION_LABELS = {
    1: "Section 1 - Public Intel",
    2: "Section 2 - Official Video Comments",
    3: "Section 3 - Homepage Reviews",
    4: "Section 4 - Creator Reviews",
}

CONTRACT_CHECKLIST = {
    "project.yaml": "Project metadata and configuration",
    "sources/source_registry.csv": "Source provenance tracking",
    "sources/source_notes.md": "Analyst notes on sources",
    "section_1_public_intel/findings.md": "Public intel findings",
    "section_2_official_video_comments/findings.md": "Video comment findings",
    "section_2_official_video_comments/evidence_table.csv": "Video comment evidence",
    "section_3_homepage_reviews/findings.md": "Homepage review findings",
    "section_3_homepage_reviews/evidence_table.csv": "Homepage review evidence",
    "section_4_creator_reviews/findings.md": "Creator review findings",
    "section_4_creator_reviews/evidence_table.csv": "Creator review evidence",
    "synthesis/executive_summary.md": "Cross-section synthesis",
    "synthesis/final_report.md": "Final assembled report",
}


@dataclass
class SectionJob:
    section_id: int
    label: str
    command: list[str]
    runnable: bool
    reason: str = ""
    manual: bool = False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Headless master runner for unreleased game research.")
    _ = parser.add_argument("--project-dir", help="Path to project directory")
    _ = parser.add_argument("--game-name", help="Game name for initialization")
    _ = parser.add_argument("--game-slug", help="Optional slug for the project folder")
    _ = parser.add_argument("--init", action="store_true", help="Initialize a new project")
    _ = parser.add_argument("--section", type=int, choices=[1, 2, 3, 4], help="Run only one section")
    _ = parser.add_argument("--from-section", type=int, choices=[1, 2, 3, 4], help="Run from this section onward")
    _ = parser.add_argument("--list-sections", action="store_true", help="List section purposes")
    _ = parser.add_argument("--check-readiness", action="store_true", help="Show readiness and missing inputs")
    _ = parser.add_argument("--validate-contract", action="store_true", help="Validate expected artifacts")
    _ = parser.add_argument("--synthesize", action="store_true", help="Run synthesis only")
    _ = parser.add_argument("--strict", action="store_true", help="Stop if any requested section is blocked or fails")
    _ = parser.add_argument("--dry-run", action="store_true", help="Print commands without executing them")
    _ = parser.add_argument("--yes", "-y", action="store_true", help="Skip any remaining confirmations")
    _ = parser.add_argument("--parallel", dest="parallel", action="store_true", help="Run executable sections in parallel")
    _ = parser.add_argument("--no-parallel", dest="parallel", action="store_false", help="Run sections sequentially")
    parser.set_defaults(parallel=True)
    _ = parser.add_argument("--auto-synthesize", dest="auto_synthesize", action="store_true", help="Automatically synthesize after multi-section runs")
    _ = parser.add_argument("--no-auto-synthesize", dest="auto_synthesize", action="store_false", help="Do not auto-run synthesis after multi-section runs")
    parser.set_defaults(auto_synthesize=True)

    _ = parser.add_argument("--section1-data", help="Section 1 input JSON file containing team, timeline, and findings")

    _ = parser.add_argument("--youtube-api-key", help="YouTube Data API key for Section 2")
    _ = parser.add_argument("--bilibili-cookie-file", help="Path to Bilibili cookie JSON for Section 2")
    _ = parser.add_argument("--video-manifest", help="Section 2 manifest CSV for multi-video collection")
    _ = parser.add_argument("--video-ref", help="Section 2 single video ID or URL")
    _ = parser.add_argument("--milestone-id", help="Section 2 single-video milestone id")
    _ = parser.add_argument("--section2-platform", choices=["youtube", "bilibili"], default="youtube", help="Section 2 platform for single-video mode")

    _ = parser.add_argument("--page-url", help="Section 3 direct page URL")
    _ = parser.add_argument("--input-file", help="Section 3 manual review import file")
    _ = parser.add_argument("--section3-platform", default="taptap", help="Section 3 platform label")
    _ = parser.add_argument("--game-page-title", default="", help="Section 3 optional page title override")
    _ = parser.add_argument("--biligame-request-bundle-file", help="Section 3 Bilibili request bundle file")
    
    _ = parser.add_argument("--secondary-page-url", help="Optional second source page URL, typically for Bilibili game comments")
    _ = parser.add_argument("--secondary-platform", default="biligame", help="Platform label for the secondary source")
    _ = parser.add_argument("--secondary-game-page-title", default="", help="Optional title override for the secondary source")
    _ = parser.add_argument("--secondary-biligame-request-bundle-file", help="Request bundle file for the optional Bilibili secondary source")

    _ = parser.add_argument("--candidates-file", help="Section 4 candidate videos file")
    _ = parser.add_argument("--transcripts-file", help="Section 4 transcript import file")
    _ = parser.add_argument("--transcript-video-id", help="Section 4 SRT fallback video id")
    _ = parser.add_argument("--section4-notes", default="", help="Extra notes merged into Section 4 candidate import")
    _ = parser.add_argument("--volcengine-api-key", help="Volcano Engine API Key for Section 4 ASR")
    return parser.parse_args()


def script_dir() -> Path:
    return Path(__file__).resolve().parent


def skill_root() -> Path:
    return script_dir().parent


def build_script_path(script_name: str) -> Path:
    return script_dir() / script_name


def normalize_text(value: str) -> str:
    return value.strip()


def slugify(name: str) -> str:
    cleaned: list[str] = []
    last_dash = False
    for char in name.casefold():
        if char.isalnum():
            cleaned.append(char)
            last_dash = False
            continue
        if not last_dash:
            cleaned.append("-")
            last_dash = True
    return "".join(cleaned).strip("-") or "unnamed-game"


def print_section_catalog() -> None:
    print("=" * 72)
    print("UNRELEASED GAME RESEARCH")
    print("=" * 72)
    print("1. Section 1 - Public Intel: game profile, studio background, milestone map")
    print("2. Section 2 - Official Video Comments: YouTube/Bilibili official video comments")
    print("3. Section 3 - Homepage Reviews: TapTap/Bilibili reservation or detail page reviews")
    print("4. Section 4 - Creator Reviews: creator-video interpretation and credibility analysis")
    print("=" * 72)


def project_game_name(project_dir: Path) -> str:
    project_file = project_dir / "project.yaml"
    if project_file.exists():
        for line in project_file.read_text(encoding="utf-8").splitlines():
            if line.startswith("game_name:"):
                return line.split(":", 1)[1].strip().strip('"') or project_dir.name
    return project_dir.name.replace("-", " ").replace("_", " ").title()


def init_project(game_name: str, game_slug: str | None) -> Path:
    root_dir = skill_root() / "projects"
    root_dir.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        str(build_script_path("init_project.py")),
        game_name,
        "--root",
        str(root_dir),
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise SystemExit(f"Project initialization failed:\n{result.stderr or result.stdout}")
    if game_slug:
        desired_dir = root_dir / game_slug
        created_dir = Path(result.stdout.strip()).resolve()
        if created_dir.exists() and created_dir != desired_dir and not desired_dir.exists():
            created_dir.rename(desired_dir)
            return desired_dir
        return desired_dir if desired_dir.exists() else created_dir
    created_text = result.stdout.strip()
    return Path(created_text).resolve() if created_text else root_dir / slugify(game_name)


def ensure_project_dir(args: argparse.Namespace) -> Path:
    if args.project_dir:
        return Path(args.project_dir).resolve()
    if not args.game_name:
        raise SystemExit("--project-dir or --game-name is required.")
    args.init = True
    project_dir = init_project(args.game_name, args.game_slug)
    print(f"\n[Init] Project created at: {project_dir}")
    return project_dir


def credentials_from_env() -> dict[str, str]:
    return {
        "youtube_api_key": os.environ.get("YOUTUBE_API_KEY", "").strip(),
        "sessdata": os.environ.get("BILIBILI_SESSDATA", "").strip(),
        "bili_jct": os.environ.get("BILIBILI_BILI_JCT", "").strip(),
        "dedeuserid": os.environ.get("BILIBILI_DEDEUSERID", "").strip(),
        "buvid3": os.environ.get("BILIBILI_BUVID3", "").strip(),
        "buvid4": os.environ.get("BILIBILI_BUVID4", "").strip(),
    }


def print_credential_status(args: argparse.Namespace) -> None:
    env_values = credentials_from_env()
    youtube_ready = bool(args.youtube_api_key or env_values["youtube_api_key"])
    bilibili_ready = bool(args.bilibili_cookie_file)
    print("\n" + "=" * 72)
    print("INPUT STATUS")
    print("=" * 72)
    print(f"Section 1 input data: {'READY' if args.section1_data else 'MISSING (will skip)'}")
    print(f"Section 2 YouTube API Key: {'READY' if youtube_ready else 'MISSING'}")
    print(f"Section 2 Bilibili Cookie: {'READY' if bilibili_ready else 'MISSING'}")
    print(f"Section 2 source input: {'READY' if args.video_manifest or args.video_ref else 'MISSING (will skip)'}")
    print(f"Section 3 source input: {'READY' if args.page_url or args.input_file else 'MISSING (will skip)'}")
    print(f"Section 4 source input: {'READY' if args.candidates_file and args.transcripts_file else 'MISSING (will skip)'}")
    print("=" * 72)


def build_section_1_job(project_dir: Path, args: argparse.Namespace) -> SectionJob:
    if not args.section1_data:
        return SectionJob(1, SECTION_LABELS[1], [], False, "Missing --section1-data input JSON file.")
    command = [
        sys.executable,
        str(build_script_path("run_section_1.py")),
        "--project-dir",
        str(project_dir),
        "--data-file",
        args.section1_data,
    ]
    return SectionJob(1, SECTION_LABELS[1], command, True)


def build_section_2_job(project_dir: Path, args: argparse.Namespace) -> SectionJob:
    if not (args.youtube_api_key or args.bilibili_cookie_file or credentials_from_env()["youtube_api_key"]):
        return SectionJob(2, SECTION_LABELS[2], [], False, "Missing Section 2 credentials. Provide YouTube API Key and/or Bilibili Cookie.")
    if not args.video_manifest and not args.video_ref:
        return SectionJob(2, SECTION_LABELS[2], [], False, "Missing Section 2 video input. Provide --video-manifest or --video-ref.")
    command = [sys.executable, str(build_script_path("run_section_2.py")), "--project-dir", str(project_dir)]
    if args.video_manifest:
        command.extend(["--manifest", args.video_manifest])
    else:
        command.extend([args.video_ref, "--milestone-id", args.milestone_id or "latest_test", "--platform", args.section2_platform])
    if args.youtube_api_key:
        command.extend(["--api-key", args.youtube_api_key])
    elif credentials_from_env()["youtube_api_key"]:
        command.extend(["--api-key", credentials_from_env()["youtube_api_key"]])
    if args.bilibili_cookie_file:
        command.extend(["--cookie-file", args.bilibili_cookie_file])
    return SectionJob(2, SECTION_LABELS[2], command, True)


def build_section_3_job(project_dir: Path, args: argparse.Namespace) -> SectionJob:
    if not args.page_url and not args.input_file:
        return SectionJob(3, SECTION_LABELS[3], [], False, "Missing Section 3 --page-url or --input-file.")
    lowered = (args.page_url or "").casefold()
    if ("biligame" in lowered or "bilibili" in lowered) and not args.biligame_request_bundle_file and not args.input_file:
        return SectionJob(3, SECTION_LABELS[3], [], False, "Bilibili Section 3 capture needs --biligame-request-bundle-file.")
    command = [
        sys.executable,
        str(build_script_path("run_section_3.py")),
        "--project-dir",
        str(project_dir),
        "--platform",
        args.section3_platform,
    ]
    if args.page_url:
        command.extend(["--page-url", args.page_url])
    if args.input_file:
        command.extend(["--input-file", args.input_file])
    if args.game_page_title:
        command.extend(["--game-page-title", args.game_page_title])
    if args.biligame_request_bundle_file:
        command.extend(["--biligame-request-bundle-file", args.biligame_request_bundle_file])
    
    if args.secondary_page_url:
        command.extend(["--secondary-page-url", args.secondary_page_url])
        if args.secondary_platform:
            command.extend(["--secondary-platform", args.secondary_platform])
        if args.secondary_game_page_title:
            command.extend(["--secondary-game-page-title", args.secondary_game_page_title])
        if args.secondary_biligame_request_bundle_file:
            command.extend(["--secondary-biligame-request-bundle-file", args.secondary_biligame_request_bundle_file])

    return SectionJob(3, SECTION_LABELS[3], command, True)


def build_section_4_job(project_dir: Path, args: argparse.Namespace) -> SectionJob:
    if not args.candidates_file:
        return SectionJob(4, SECTION_LABELS[4], [], False, "Missing Section 4 --candidates-file.")
    
    command = [
        sys.executable,
        str(build_script_path("run_section_4.py")),
        "--project-dir",
        str(project_dir),
        "--candidates-file",
        args.candidates_file,
    ]
    
    if hasattr(args, "transcripts_file") and args.transcripts_file:
        command.extend(["--transcripts-file", args.transcripts_file])
    else:
        command.append("--auto-transcribe")
        command.extend(["--stt-provider", "volcengine"])
        if hasattr(args, "volcengine_api_key") and args.volcengine_api_key:
            command.extend(["--volcengine-api-key", args.volcengine_api_key])
            
    if hasattr(args, "transcript_video_id") and args.transcript_video_id:
        command.extend(["--transcript-video-id", args.transcript_video_id])
    if hasattr(args, "section4_notes") and args.section4_notes:
        command.extend(["--notes", args.section4_notes])
    return SectionJob(4, SECTION_LABELS[4], command, True)


def requested_sections(args: argparse.Namespace) -> list[int]:
    if args.section:
        return [args.section]
    if args.from_section:
        return list(range(args.from_section, 5))
    if args.synthesize:
        return []
    return [1, 2, 3, 4]


def build_jobs(project_dir: Path, args: argparse.Namespace, sections: list[int]) -> list[SectionJob]:
    builders = {
        1: lambda: build_section_1_job(project_dir, args),
        2: lambda: build_section_2_job(project_dir, args),
        3: lambda: build_section_3_job(project_dir, args),
        4: lambda: build_section_4_job(project_dir, args),
    }
    return [builders[section_id]() for section_id in sections]


def print_jobs(jobs: list[SectionJob]) -> None:
    print("\n" + "=" * 72)
    print("EXECUTION PLAN")
    print("=" * 72)
    for job in jobs:
        if job.manual:
            print(f"- {job.label}: MANUAL")
            print(f"  {job.reason}")
            continue
        if job.runnable:
            print(f"- {job.label}: READY")
            print(f"  {' '.join(job.command)}")
            continue
        print(f"- {job.label}: BLOCKED / SKIPPED")
        print(f"  {job.reason}")
    print("=" * 72)


def execute_jobs(jobs: list[SectionJob], parallel: bool, dry_run: bool) -> dict[int, bool]:
    results: dict[int, bool] = {}
    runnable_jobs = [job for job in jobs if job.runnable]
    manual_jobs = [job for job in jobs if job.manual]
    for job in manual_jobs:
        print(f"\n[Manual] {job.label}")
        print(job.reason)
        results[job.section_id] = True
    if dry_run:
        for job in runnable_jobs:
            print(f"[DRY RUN] {' '.join(job.command)}")
            results[job.section_id] = True
        return results
    if parallel and len(runnable_jobs) > 1:
        processes: list[tuple[SectionJob, subprocess.Popen[bytes]]] = []
        for job in runnable_jobs:
            print(f"\n[Launch] {job.label}")
            process = subprocess.Popen(job.command)
            processes.append((job, process))
        for job, process in processes:
            return_code = process.wait()
            results[job.section_id] = return_code == 0
            print(f"[Done] {job.label}: {'OK' if return_code == 0 else f'FAILED ({return_code})'}")
        return results
    for job in runnable_jobs:
        print(f"\n[Run] {job.label}")
        return_code = subprocess.run(job.command, check=False).returncode
        results[job.section_id] = return_code == 0
        print(f"[Done] {job.label}: {'OK' if return_code == 0 else f'FAILED ({return_code})'}")
    return results


def section_1_ready_for_synthesis(project_dir: Path) -> bool:
    findings_path = project_dir / "section_1_public_intel" / "findings.md"
    timeline_path = project_dir / "section_1_public_intel" / "timeline.csv"
    team_path = project_dir / "section_1_public_intel" / "team_profile.csv"
    if timeline_path.exists() or team_path.exists():
        return True
    if not findings_path.exists():
        return False
    content = findings_path.read_text(encoding="utf-8")
    stripped = [line.strip() for line in content.splitlines() if line.strip() and not line.startswith("## ")]
    return bool(stripped)


def should_auto_synthesize(args: argparse.Namespace, sections: list[int], results: dict[int, bool], project_dir: Path) -> bool:
    if args.synthesize:
        return True
    if not args.auto_synthesize:
        return False
    if len(sections) <= 1:
        return False
    failed_requested = [section_id for section_id in sections if not results.get(section_id, False)]
    if failed_requested:
        return False
    if 1 in sections and not section_1_ready_for_synthesis(project_dir):
        print("\n[Skip Synthesis] Section 1 still looks incomplete, so synthesis is deferred.")
        return False
    return True


def reports_dir(project_dir: Path) -> Path:
    """Mirror of assemble_report.default_output_dir — <skill_root>/reports/<project_name>/"""
    return project_dir.parent.parent / "reports" / project_dir.name


def run_synthesis(project_dir: Path, dry_run: bool) -> bool:
    output_dir = reports_dir(project_dir)
    command = [
        sys.executable,
        str(build_script_path("assemble_report.py")),
        str(project_dir),
        "--output-dir",
        str(output_dir),
    ]
    if dry_run:
        print(f"[DRY RUN] {' '.join(command)}")
        return True
    print(f"\n[Run] Synthesis → {output_dir}")
    return subprocess.run(command, check=False).returncode == 0


def validate_contract(project_dir: Path) -> tuple[bool, list[str]]:
    messages: list[str] = []
    all_ok = True
    for relative_path, description in CONTRACT_CHECKLIST.items():
        full_path = project_dir / relative_path
        if full_path.exists():
            messages.append(f"[OK] {relative_path} - {description}")
        else:
            messages.append(f"[MISSING] {relative_path} - {description}")
            all_ok = False
    return all_ok, messages


def print_readiness(args: argparse.Namespace, project_dir: Path) -> None:
    print_credential_status(args)
    jobs = build_jobs(project_dir, args, [1, 2, 3, 4])
    print_jobs(jobs)


def print_contract_validation(project_dir: Path) -> None:
    all_ok, messages = validate_contract(project_dir)
    print("\n" + "=" * 72)
    print(f"CONTRACT VALIDATION - {project_dir.name}")
    print("=" * 72)
    for message in messages:
        print(message)
    print("=" * 72)
    print("STATUS: ALL REQUIRED ARTIFACTS PRESENT" if all_ok else "STATUS: SOME ARTIFACTS ARE MISSING")
    print("=" * 72)


def main() -> None:
    args = parse_args()
    if args.list_sections:
        print_section_catalog()
        return

    project_dir = ensure_project_dir(args)
    _ = args.game_name or project_game_name(project_dir)

    if args.init and args.project_dir:
        print(f"[Init] Using existing project directory: {project_dir}")

    sections = requested_sections(args)

    if args.check_readiness:
        print_readiness(args, project_dir)
        return

    if args.validate_contract:
        print_contract_validation(project_dir)
        return

    print_credential_status(args)
    jobs = build_jobs(project_dir, args, sections)
    blocked_jobs = [job for job in jobs if not job.runnable and not job.manual]
    print_jobs(jobs)

    if blocked_jobs and args.strict:
        reasons = "\n".join(f"- {job.label}: {job.reason}" for job in blocked_jobs)
        raise SystemExit(f"Strict mode blocked execution:\n{reasons}")

    results = execute_jobs(jobs, args.parallel, args.dry_run)

    run_synthesis_now = should_auto_synthesize(args, sections, results, project_dir)
    synthesis_ok = True
    if run_synthesis_now:
        synthesis_ok = run_synthesis(project_dir, args.dry_run)

    completed = sum(1 for section_id in sections if results.get(section_id, False))
    total = len(sections)
    print("\n" + "=" * 72)
    print("EXECUTION SUMMARY")
    print("=" * 72)
    print(f"Project: {project_dir}")
    print(f"Completed sections: {completed}/{total}")
    if sections:
        for section_id in sections:
            status = "OK" if results.get(section_id, False) else "SKIPPED_OR_FAILED"
            print(f"- {SECTION_LABELS[section_id]}: {status}")
    if run_synthesis_now:
        print(f"- Synthesis: {'OK' if synthesis_ok else 'FAILED'}")
    print("=" * 72)


if __name__ == "__main__":
    main()
