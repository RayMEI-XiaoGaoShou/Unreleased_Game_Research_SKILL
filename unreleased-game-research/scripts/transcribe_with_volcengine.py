"""
Volcano Engine (火山引擎) Speech-to-Text transcription for Section 4.

Uses the 大模型录音文件识别 API for long audio transcription.
API Documentation: https://www.volcengine.com/docs/6561/1354868

Cost: ~2.3 CNY/hour for 大模型录音文件识别（标准版）
"""

from __future__ import annotations

import argparse
import base64
import csv
import os
import time
import uuid
from pathlib import Path
from typing import Any

try:
    import requests
except ImportError:
    print("Error: 'requests' package is required. Install with: pip install requests")
    raise

# Volcano Engine ASR API endpoints (大模型录音文件识别)
VOLCENGINE_ASR_SUBMIT_URL = "https://openspeech.bytedance.com/api/v3/auc/bigmodel/submit"
VOLCENGINE_ASR_QUERY_URL = "https://openspeech.bytedance.com/api/v3/auc/bigmodel/query"

# Polling configuration
POLL_INTERVAL_SECONDS = 10  # Increased for large files
MAX_POLL_ATTEMPTS = 180  # 30 minutes max for large files


def load_api_token() -> str:
    """
    Load Volcano Engine API token from environment or config file.
    
    Priority:
    1. VOLCENGINE_ASR_TOKEN environment variable
    2. .volcengine_token file in project root or script directory
    3. --token command line argument (handled by argparse)
    """
    # Check environment variable
    token = os.environ.get("VOLCENGINE_ASR_TOKEN", "")
    if token:
        return token
    
    # Check for .volcengine_token file
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent.parent
    
    for search_dir in [project_root, script_dir]:
        token_file = search_dir / ".volcengine_token"
        if token_file.exists():
            return token_file.read_text(encoding="utf-8").strip()
    
    return ""


def submit_transcription_task(
    audio_path: Path,
    api_key: str,
    language: str = "zh-CN",
) -> str:
    """
    Submit audio file for transcription to Volcano Engine ASR.
    
    Uses the 大模型录音文件识别 API.
    Returns task_id for polling.
    
    Note: For large files (>10MB), consider uploading to a URL first.
    """
    # Read audio file and encode as base64
    audio_bytes = audio_path.read_bytes()
    file_size_mb = len(audio_bytes) / (1024 * 1024)
    
    print(f"  Audio file size: {file_size_mb:.2f} MB")
    
    if file_size_mb > 20:
        print("  WARNING: Large file may take a long time to process.")
        print("  Consider uploading to a URL for faster processing.")
    
    audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")
    
    # Determine audio format
    audio_format = "mp3"
    if audio_path.suffix.lower() == ".wav":
        audio_format = "wav"
    elif audio_path.suffix.lower() == ".flac":
        audio_format = "flac"
    elif audio_path.suffix.lower() == ".ogg":
        audio_format = "ogg"
    
    # Generate unique request ID
    request_id = str(uuid.uuid4())
    
    print(f"  Request ID: {request_id}")
    print(f"  Audio format: {audio_format}")
    
    # Build request payload for 大模型录音文件识别 API
    # Reference: https://www.volcengine.com/docs/6561/1354868
    payload = {
        "user": {
            "uid": "section4_transcriber"
        },
        "audio": {
            "format": audio_format,
            "data": audio_base64,
        },
        "request": {
            "model_name": "bigmodel",
            "enable_itn": True,  # Inverse text normalization
            "enable_punc": True,  # Enable punctuation
            "show_utterances": True,  # Return utterances with timestamps
        }
    }
    
    # Add language if specified
    if language:
        payload["audio"]["language"] = language
    
    # Headers based on user's curl example
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "X-Api-Resource-Id": "volc.seedasr.auc",  # 豆包录音文件识别模型2.0
        "X-Api-Request-Id": request_id,
        "X-Api-Sequence": "-1",
    }
    
    print("  Submitting to Volcano Engine...")
    
    response = requests.post(
        VOLCENGINE_ASR_SUBMIT_URL,
        headers=headers,
        json=payload,
        timeout=180,  # 3 minutes for upload
    )
    
    if response.status_code != 200:
        raise RuntimeError(
            f"Volcano Engine ASR submit failed: HTTP {response.status_code}\n"
            f"Response: {response.text}"
        )
    
    # Check response headers for status
    status_code = response.headers.get("X-Api-Status-Code", "")
    message = response.headers.get("X-Api-Message", "")
    
    if status_code and status_code != "20000000":
        raise RuntimeError(
            f"Volcano Engine ASR submit error: {message}\n"
            f"Status Code: {status_code}"
        )
    
    print(f"  Submit successful: {message}")
    
    # The request_id is used as task_id
    return request_id


def query_transcription_result(
    task_id: str,
    api_key: str,
) -> dict[str, Any]:
    """
    Query transcription result by task_id.
    
    Returns the full result dict with status and transcription.
    """
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "X-Api-Resource-Id": "volc.seedasr.auc",
        "X-Api-Request-Id": task_id,
    }
    
    payload = {}
    
    response = requests.post(
        VOLCENGINE_ASR_QUERY_URL,
        headers=headers,
        json=payload,
        timeout=30,
    )
    
    if response.status_code != 200:
        raise RuntimeError(
            f"Volcano Engine ASR query failed: HTTP {response.status_code}\n"
            f"Response: {response.text}"
        )
    
    return response.json()


def poll_transcription_result(
    task_id: str,
    api_key: str,
    poll_interval: int = POLL_INTERVAL_SECONDS,
    max_attempts: int = MAX_POLL_ATTEMPTS,
) -> dict[str, Any]:
    """
    Poll for transcription result until complete or timeout.
    
    Returns the final result dict.
    """
    for attempt in range(max_attempts):
        result = query_transcription_result(task_id, api_key)
        
        # Check if result contains transcription data (indicates completion)
        result_data = result.get("result", {})
        has_text = bool(result_data.get("text", ""))
        has_utterances = bool(result_data.get("utterances", []))
        
        if has_text or has_utterances:
            print(f"  Transcription complete (attempt {attempt + 1})")
            return result
        
        # Check status in result (for APIs that return status)
        # Status values: "pending", "processing", "completed", "failed", "success"
        status = result.get("status", "")
        
        if status in ("completed", "success", "Finished"):
            return result
        
        if status == "failed":
            error_msg = result.get("message", "Unknown error")
            raise RuntimeError(f"Transcription task failed: {error_msg}")
        
        # Still processing
        if attempt < max_attempts - 1:
            print(f"  Status: {status or 'processing'}... (attempt {attempt + 1}/{max_attempts})")
            time.sleep(poll_interval)
    
    raise RuntimeError(f"Transcription timeout after {max_attempts * poll_interval} seconds")


def parse_volcengine_result(result: dict[str, Any], video_id: str) -> list[dict[str, str]]:
    """
    Parse Volcano Engine ASR result into transcript segments.
    
    Returns list of segment dicts compatible with transcript_segments.csv schema.
    
    Response format:
    {
      "audio_info": {"duration": 6312},
      "result": {
        "text": "完整文本",
        "utterances": [{
          "start_time": 480,
          "end_time": 5880,
          "text": "分句文本",
          "words": [...]
        }]
      }
    }
    """
    # Get result object
    result_data = result.get("result", {})
    
    # Structure 1: result.utterances (with timestamps)
    utterances = result_data.get("utterances", [])
    
    # Structure 2: result.text (plain text, no timestamps)
    if not utterances:
        plain_text = result_data.get("text", "")
        if plain_text:
            # Create single segment without timestamps
            return [{
                "segment_id": f"{video_id}_seg_001",
                "video_id": video_id,
                "timestamp_start": "00:00:00.000",
                "timestamp_end": "",  # Unknown duration
                "quote_original": plain_text.strip(),
                "quote_normalized": plain_text.strip(),
                "topic_label": "",
                "claim_type": "",
                "supports_positive_or_negative": "",
                "visible_footage_support": "",
                "cross_source_support": "",
                "confidence_level": "",
            }]
    
    segments = []
    for idx, utt in enumerate(utterances, start=1):
        text = utt.get("text", "").strip()
        if not text:
            continue
        
        # Parse timestamps (in milliseconds)
        start_ms = utt.get("start_time", 0)
        end_ms = utt.get("end_time", 0)
        
        # Convert to HH:MM:SS.mmm format
        start_ts = format_timestamp_ms(start_ms)
        end_ts = format_timestamp_ms(end_ms)
        
        segments.append({
            "segment_id": f"{video_id}_seg_{idx:04d}",
            "video_id": video_id,
            "timestamp_start": start_ts,
            "timestamp_end": end_ts,
            "quote_original": text,
            "quote_normalized": text,  # Already normalized by ASR
            "topic_label": "",
            "claim_type": "",
            "supports_positive_or_negative": "",
            "visible_footage_support": "",
            "cross_source_support": "",
            "confidence_level": "",
        })
    
    return segments


def format_timestamp_ms(ms: int) -> str:
    """Convert milliseconds to HH:MM:SS.mmm format."""
    total_seconds = ms / 1000
    hours = int(total_seconds // 3600)
    minutes = int((total_seconds % 3600) // 60)
    seconds = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:06.3f}"


def write_transcript_txt(
    text: str,
    output_path: Path,
) -> None:
    """Write full transcript to a TXT file."""
    with output_path.open("w", encoding="utf-8") as f:
        f.write(text)


def transcribe_audio(
    audio_path: Path,
    output_dir: Path,
    video_id: str,
    api_key: str,
    language: str = "zh-CN",
) -> Path:
    """
    Transcribe audio file using Volcano Engine ASR.
    
    Returns path to generated transcript TXT file.
    """
    print(f"Submitting {audio_path.name} to Volcano Engine ASR...")
    
    # Submit transcription task
    task_id = submit_transcription_task(audio_path, api_key, language)
    print(f"Task submitted: {task_id}")
    
    # Poll for result
    print("Waiting for transcription to complete...")
    result = poll_transcription_result(task_id, api_key)
    
    # Parse result
    result_data = result.get("result", {})
    text = result_data.get("text", "").strip()
    
    if not text:
        # Fallback to concatenating utterances if text is empty
        utterances = result_data.get("utterances", [])
        if utterances:
            text = " ".join(utt.get("text", "").strip() for utt in utterances if utt.get("text", "").strip())
            
    if not text:
        raise RuntimeError(f"No transcription text returned for {audio_path}")
    
    # Write output
    output_path = output_dir / f"{audio_path.stem}_volcengine.txt"
    write_transcript_txt(text, output_path)
    
    print(f"Transcription complete: Output written to {output_path}")
    
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Transcribe audio using Volcano Engine (火山引擎) ASR API"
    )
    parser.add_argument("audio_path", help="Path to audio file (MP3, WAV, etc.)")
    parser.add_argument("--output-dir", required=True, help="Directory for output transcript CSV")
    parser.add_argument("--video-id", required=True, help="Video ID for segment naming")
    parser.add_argument("--api-key", help="Volcano Engine API Key (or set VOLCENGINE_ASR_TOKEN env var)")
    parser.add_argument("--language", default="zh-CN", help="Language code (default: zh-CN)")
    args = parser.parse_args()
    
    audio_path = Path(args.audio_path).resolve()
    if not audio_path.exists():
        raise SystemExit(f"Audio file not found: {audio_path}")
    
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Get API key
    api_key = args.api_key or load_api_token()
    if not api_key:
        raise SystemExit(
            "No API key provided. Use --api-key, set VOLCENGINE_ASR_TOKEN environment variable, "
            "or create a .volcengine_token file."
        )
    
    try:
        output_path = transcribe_audio(audio_path, output_dir, args.video_id, api_key, args.language)
        print(f"SUCCESS: {output_path}")
    except Exception as e:
        raise SystemExit(f"Transcription failed: {e}")


if __name__ == "__main__":
    main()
