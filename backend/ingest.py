import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import imageio_ffmpeg
import soundfile as sf

RATE = 44100
MAX_SECONDS = 600
MAX_BYTES = 80 * 1024 * 1024
FFMPEG = os.environ.get("PUREVOICE_FFMPEG") or imageio_ffmpeg.get_ffmpeg_exe()


def youtube_url(value):
    url = urlsplit(value.strip())
    if url.scheme != "https" or url.username or url.password or url.port:
        raise ValueError("Enter an HTTPS YouTube video link.")
    if url.hostname == "youtu.be":
        video = url.path.strip("/")
    elif url.hostname in {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"}:
        video = parse_qs(url.query).get("v", [""])[0] if url.path == "/watch" else (
            url.path.split("/")[2] if re.fullmatch(r"/(?:shorts|live|embed)/[^/]+/?", url.path) else ""
        )
    else:
        video = ""
    if not re.fullmatch(r"[\w-]{11}", video, flags=re.ASCII):
        raise ValueError("Enter a YouTube link to a single video.")
    return f"https://www.youtube.com/watch?v={video}"


def download(url, directory):
    result = subprocess.run(
        [sys.executable, "-m", "yt_dlp", "--ignore-config", "--no-playlist",
         "--js-runtimes", "node", "--socket-timeout", "20", "--retries", "1",
         "--match-filter", "!is_live & duration <= 600", "--max-filesize", "80M",
         "-f", "bestaudio/best", "-o", str(directory / "youtube.%(ext)s"), url],
        capture_output=True, text=True, errors="replace", timeout=180,
    )
    files = [path for path in directory.glob("youtube.*") if not path.name.endswith((".part", ".ytdl"))]
    if result.returncode or len(files) != 1:
        raise ValueError("YouTube audio could not be imported. Try a public video under 10 minutes or upload its audio file.")
    if files[0].stat().st_size > MAX_BYTES:
        raise ValueError("The audio exceeds the 80 MB limit.")
    return files[0]


def decode(source, target):
    result = subprocess.run(
        [FFMPEG, "-nostdin", "-v", "error", "-y", "-protocol_whitelist", "file",
         "-i", str(source), "-map", "0:a:0", "-ac", "2", "-ar", str(RATE),
         "-t", str(MAX_SECONDS + 1), "-c:a", "pcm_f32le", str(target)],
        capture_output=True, timeout=90,
    )
    if result.returncode:
        raise ValueError("The source could not be decoded as audio.")
    frames = sf.info(target).frames
    if not RATE <= frames <= MAX_SECONDS * RATE:
        raise ValueError("Audio must be between 1 second and 10 minutes long.")
    return frames


def encode_mp3(source: Path, target: Path):
    subprocess.run(
        [FFMPEG, "-nostdin", "-v", "error", "-y", "-i", str(source),
         "-c:a", "libmp3lame", "-b:a", "256k", str(target)],
        check=True, capture_output=True, timeout=90,
    )
