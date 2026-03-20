from __future__ import annotations

import argparse
import csv
import shutil
import subprocess
import os
os.environ["PATH"] = r"C:/Users/happyelements/AppData/Local/ffmpegio/ffmpeg-downloader/ffmpeg/bin;" + os.environ.get("PATH", "")

from pathlib import Path


TRANSCRIPT_TEMPLATE_HEADER = [
    "segment_id",
    "video_id",
    "timestamp_start",
    "timestamp_end",
    "quote_original",
    "quote_normalized",
    "topic_label",
    "claim_type",
    "supports_positive_or_negative",
    "visible_footage_support",
    "cross_source_support",
    "confidence_level",
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Transcribe local audio with Whisper CLI when available, or emit a manual template.")
    parser.add_argument("audio_path", help="Path to the source audio file")
    parser.add_argument("--output-dir", help="Directory for generated transcript artifacts")
    parser.add_argument("--video-id", default="", help="video_id written into the manual transcript template")
    parser.add_argument("--engine", default="auto", choices=["auto", "whisper", "manual-template"], help="Transcription backend")
    parser.add_argument("--model", default="base", help="Whisper model name when using the whisper CLI")
    parser.add_argument("--language", help="Optional language hint passed to Whisper")
    parser.add_argument("--manual-fallback", action="store_true", help="If Whisper is unavailable or fails, write a manual CSV template instead of exiting immediately")
    args = parser.parse_args()

    audio_path = Path(args.audio_path).resolve()
    if not audio_path.exists():
        raise SystemExit(f"Audio file not found: {audio_path}")

    output_dir = Path(args.output_dir).resolve() if args.output_dir else audio_path.parent / f"{audio_path.stem}_transcript"
    output_dir.mkdir(parents=True, exist_ok=True)
    whisper_path = shutil.which("whisper")
    should_try_whisper = args.engine in {"auto", "whisper"} and whisper_path is not None

    if should_try_whisper:
        command = [whisper_path, str(audio_path), "--output_dir", str(output_dir), "--output_format", "srt", "--model", args.model]
        if args.language:
            command.extend(["--language", args.language])
        completed = subprocess.run(command, check=False)
        if completed.returncode == 0:
            transcript_path = output_dir / f"{audio_path.stem}.srt"
            print(f"Wrote transcript to {transcript_path}")
            return
        if not args.manual_fallback:
            raise SystemExit(f"Whisper transcription failed for {audio_path}")

    if args.engine == "whisper" and whisper_path is None and not args.manual_fallback:
        raise SystemExit("Whisper CLI is not available on PATH. Re-run with --manual-fallback or install whisper.")

    template_path = output_dir / f"{audio_path.stem}_manual_segments.csv"
    with template_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=TRANSCRIPT_TEMPLATE_HEADER)
        writer.writeheader()
        writer.writerow(
            {
                "segment_id": f"manual_{audio_path.stem}_0001",
                "video_id": args.video_id,
                "timestamp_start": "",
                "timestamp_end": "",
                "quote_original": "",
                "quote_normalized": "",
                "topic_label": "",
                "claim_type": "",
                "supports_positive_or_negative": "",
                "visible_footage_support": "",
                "cross_source_support": "",
                "confidence_level": "",
            }
        )
    print(f"Whisper unavailable or skipped. Wrote manual transcript template to {template_path}")


if __name__ == "__main__":
    main()
