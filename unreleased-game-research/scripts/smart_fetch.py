from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

FFMPEG_PATH_CANDIDATES = [
    r"C:\Users\happyelements\AppData\Local\ffmpegio\ffmpeg-downloader\ffmpeg\bin\ffmpeg.exe",
    r"C:\Users\happyelements\AppData\Local\ffmpegio\ffmpeg-downloader\ffmpeg\bin\ffprobe.exe"
]

def ensure_ffmpeg() -> str | None:
    """Checks if ffmpeg is available, and installs it transparently if missing."""
    ffmpeg_cmd = shutil.which("ffmpeg")
    if ffmpeg_cmd:
        return ffmpeg_cmd
    
    # Check common fallback path
    for cand in FFMPEG_PATH_CANDIDATES:
        if Path(cand).exists() and "ffmpeg.exe" in cand:
            return cand
            
    print("\n[System] FFmpeg is missing. Installing it automatically for you... (this only happens once)", flush=True)
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "ffmpeg-downloader"], check=True)
        subprocess.run([sys.executable, "-m", "ffmpeg_downloader", "install", "--add-path", "-y"], check=True)
        
        # Try finding it again
        for cand in FFMPEG_PATH_CANDIDATES:
            if Path(cand).exists() and "ffmpeg.exe" in cand:
                print("[System] FFmpeg installed successfully!\n", flush=True)
                return cand
                
        print("[System] Warning: Installed FFmpeg but couldn't locate it. Falling back to manual.", flush=True)
        return None
    except subprocess.CalledProcessError:
        print("[System] Error: Failed to automatically install FFmpeg. Please install manually.", flush=True)
        return None

def download_subtitles_or_audio(video_url: str, output_dir: Path, audio_format: str = "wav") -> tuple[bool, Path | None]:
    """Attempts to download native subtitles first. If failed/none, downloads audio."""
    import yt_dlp
    
    output_dir.mkdir(parents=True, exist_ok=True)
    video_id_template = "%(id)s"
    
    # 1. First, let's try to see if there are automatic or manual subtitles
    ydl_opts_subs = {
        "skip_download": True,
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitleslangs": ["en", "zh", "zh-Hans", "zh-Hant"],
        "subtitlesformat": "srt/vtt/best",
        "outtmpl": str(output_dir / f"{video_id_template}.%(ext)s"),
        "quiet": True,
        "no_warnings": True
    }
    
    print(f"\n[Downloader] Checking {video_url} for existing subtitles...", flush=True)
    try:
        with yt_dlp.YoutubeDL(ydl_opts_subs) as ydl:
            info = ydl.extract_info(video_url, download=True)
            video_id = info.get("id", "unknown_id")
            
            # Check if any subtitle file was actually written
            possible_subs = list(output_dir.glob(f"{video_id}.*"))
            subs = [p for p in possible_subs if p.suffix in {".srt", ".vtt", ".ass", ".ttml"}]
            if subs:
                print(f"[Downloader] Found and downloaded native subtitles: {subs[0].name}", flush=True)
                return True, subs[0]
            else:
                print("[Downloader] No native subtitles found.", flush=True)
    except Exception as e:
        print(f"[Downloader] Subtitle check failed ({str(e)[:50]}...). Moving to audio extraction.", flush=True)
        
    # 2. If no subtitles, let's download the audio
    ffmpeg_path = ensure_ffmpeg()
    
    ydl_opts_audio = {
        "format": "bestaudio/best",
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": audio_format,
            "preferredquality": "192",
        }],
        "outtmpl": str(output_dir / f"{video_id_template}.%(ext)s"),
        "quiet": True,
        "no_warnings": True
    }
    
    if ffmpeg_path:
        ffmpeg_dir = str(Path(ffmpeg_path).parent)
        ydl_opts_audio["ffmpeg_location"] = ffmpeg_dir
        
    print(f"[Downloader] Extracting audio from {video_url}...", flush=True)
    try:
        with yt_dlp.YoutubeDL(ydl_opts_audio) as ydl:
            info = ydl.extract_info(video_url, download=True)
            video_id = info.get("id", "unknown_id")
            audio_path = output_dir / f"{video_id}.{audio_format}"
            if audio_path.exists():
                print(f"[Downloader] Successfully extracted audio: {audio_path.name}", flush=True)
                return False, audio_path
            
            # Sometimes yt-dlp might leave it as m4a or webm if ffmpeg failed silently
            possible_audio = list(output_dir.glob(f"{video_id}.*"))
            audio_files = [p for p in possible_audio if p.suffix in {".m4a", ".webm", ".mp3", ".wav", ".flac"}]
            if audio_files:
                print(f"[Downloader] Downloaded audio (raw format): {audio_files[0].name}", flush=True)
                return False, audio_files[0]
                
            print("[Downloader] Failed to locate extracted audio file.", flush=True)
            return False, None
    except Exception as e:
        print(f"[Downloader] Audio extraction failed. Anti-scraping block? Error: {str(e)[:100]}", flush=True)
        return False, None

def main() -> None:
    parser = argparse.ArgumentParser(description="Smart Video/Audio/Subtitle Downloader for Section 4")
    parser.add_argument("video_url", help="URL of the video (Bilibili/YouTube/etc)")
    parser.add_argument("--output-dir", help="Destination directory", default=".")
    parser.add_argument("--audio-format", default="mp3", choices=["wav", "mp3", "flac", "m4a"], help="Output audio format")
    args = parser.parse_args()
    
    out_dir = Path(args.output_dir).resolve()
    has_subs, file_path = download_subtitles_or_audio(args.video_url, out_dir, args.audio_format)
    
    if file_path:
        type_str = "SUBTITLE" if has_subs else "AUDIO"
        print(f"\n[SUCCESS] -> {type_str}: {file_path}")
    else:
        print("\n[FAILURE] -> Could not download subtitles or audio. Please use manual fallback.")

if __name__ == "__main__":
    main()