import json
import logging
import os
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Lock
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .ingest import MAX_BYTES, RATE, decode, download, youtube_url
from .mixing import render
from .rhythm import analyze
from .separation import separate

app = FastAPI(title="PureVoice")
data = Path(os.environ.get("PUREVOICE_DATA", "data")).resolve()
data.mkdir(parents=True, exist_ok=True)
pool = ThreadPoolExecutor(max_workers=1)
lock = Lock()
jobs = {}
log = logging.getLogger("uvicorn.error")


class Mix(BaseModel):
    preset: Literal["soft", "balanced", "bold"] = "balanced"
    vocal_gain: float = Field(1, ge=0, le=1.5)
    daf_gain: float = Field(0.7, ge=0, le=1.5)
    bpm: float | None = Field(None, ge=35, le=260)


def update(key, **values):
    with lock:
        jobs[key].update(values)


def process(key, settings, source=None, url=None):
    folder = data / key
    try:
        if url:
            update(key, stage="importing", progress=8)
            source = download(url, folder)
        if source:
            update(key, stage="decoding", progress=18)
            frames = decode(source, folder / "original.wav")
            source.unlink()
            update(key, stage="separating", progress=30)
            separate(folder / "original.wav", folder / "vocals.wav")
        else:
            frames = jobs[key]["frames"]
        analysis_path = folder / "rhythm.json"
        if not analysis_path.exists() or settings.bpm != jobs[key].get("analyzed_bpm"):
            update(key, stage="analyzing", progress=65)
            rhythm = analyze(folder / "original.wav", settings.bpm)
            analysis_path.write_text(json.dumps(rhythm), encoding="utf-8")
            update(key, analyzed_bpm=settings.bpm)
        else:
            rhythm = json.loads(analysis_path.read_text(encoding="utf-8"))
        update(key, stage="mixing", progress=85)
        revision = jobs[key].get("revision", 0) + 1
        output = folder / str(revision)
        output.mkdir(exist_ok=True)
        render(folder / "vocals.wav", rhythm, frames, settings.preset, settings.vocal_gain, settings.daf_gain, output)
        update(key, stage="ready", progress=100, frames=frames, duration=frames / RATE,
               rhythm=rhythm, revision=revision, error=None)
    except Exception as exc:
        log.exception("Audio job %s failed", key)
        update(key, stage="error", error=str(exc) if isinstance(exc, ValueError) else
               "Processing failed. Check the local server log and try again.")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/jobs", status_code=202)
def create(file: Annotated[UploadFile | None, File()] = None, url: Annotated[str | None, Form()] = None):
    if (file is None) == (not url):
        raise HTTPException(400, "Choose one MP3/WAV file or one YouTube link.")
    key = str(uuid4())
    folder = data / key
    source = None
    try:
        if url:
            url = youtube_url(url)
        if file:
            suffix = Path(file.filename or "").suffix.lower()
            if suffix not in {".mp3", ".wav"}:
                raise ValueError("Choose an MP3 or WAV file.")
            folder.mkdir()
            source = folder / ("upload" + suffix)
            total = 0
            with source.open("wb") as output:
                while chunk := file.file.read(1024 * 1024):
                    total += len(chunk)
                    if total > MAX_BYTES:
                        raise ValueError("Maximum upload size is 80 MB.")
                    output.write(chunk)
        else:
            folder.mkdir()
    except ValueError as exc:
        if source and folder.exists():
            shutil.rmtree(folder)
        raise HTTPException(400, str(exc)) from exc
    with lock:
        jobs[key] = {"id": key, "stage": "queued", "progress": 0,
                     "name": Path(file.filename or "Audio").name if file else "YouTube"}
    pool.submit(process, key, Mix(), source, url)
    return {"id": key}


@app.get("/jobs/{job_id}")
def status(job_id: UUID):
    with lock:
        job = jobs.get(str(job_id))
        if job is None:
            raise HTTPException(404, "Job not found.")
        return dict(job)


@app.post("/jobs/{job_id}/mix", status_code=202)
def remix(job_id: UUID, settings: Mix):
    key = str(job_id)
    with lock:
        job = jobs.get(key)
        if not job:
            raise HTTPException(404, "Job not found.")
        if job["stage"] not in {"ready", "error"} or not job.get("revision"):
            raise HTTPException(409, "Wait until the first mix has finished.")
        job.update(stage="queued", progress=0, error=None)
    pool.submit(process, key, settings)
    return {"id": key}


@app.get("/jobs/{job_id}/audio/{kind}")
def audio(job_id: UUID, kind: Literal["vocals", "wav", "mp3"], revision: int | None = None, download: bool = False):
    job = status(job_id)
    folder = data / str(job_id)
    revision = revision if revision is not None else job.get("revision", 0)
    path = folder / "vocals.wav" if kind == "vocals" else folder / str(revision) / ("mix." + kind)
    if not job.get("revision") or revision < 1 or revision > job["revision"] or not path.is_file():
        raise HTTPException(404, "Audio is still processing.")
    return FileResponse(path, media_type="audio/mpeg" if kind == "mp3" else "audio/wav",
                        filename=("PureVoice-" + path.name) if download else None)
