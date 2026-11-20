from pathlib import Path
import sys
import tempfile

import numpy as np
import soundfile as sf

from backend.daf import generate
from backend.ingest import RATE, decode
from backend.mixing import render
from backend.rhythm import analyze
from backend.separation import separate


def timing_fixture(path):
    first = 0.31 + np.array([0, .49, 1.02, 1.48, 2.01, 2.47, 3, 3.52])
    second = 5.55 + np.array([0, .39, .84, 1.23, 1.67, 2.08, 2.52, 2.91])
    expected = np.r_[first, second]
    samples = np.zeros((9 * RATE, 2))
    t = np.arange(RATE // 7) / RATE
    for i, beat in enumerate(expected):
        start = round(beat * RATE)
        signal = (0.65 if i % 2 == 0 else 0.30) * np.sin(2 * np.pi * (100 if i % 2 == 0 else 970) * t) * np.exp(-38 * t)
        samples[start:start + len(t)] += signal[:, None]
    sf.write(path, samples, RATE)
    rhythm = analyze(path)
    positions = np.array([event["time"] for event in rhythm["beats"]])
    assert len(positions), rhythm
    distances = abs(positions[:, None] - expected)
    assert np.all(distances.min(axis=1) < 0.085), positions
    assert np.count_nonzero(distances.min(axis=0) < 0.085) >= 13, positions
    assert any(pause["start"] < 4.4 < pause["end"] for pause in rhythm["pauses"])
    assert np.count_nonzero(generate(len(samples), rhythm, "balanced")[int(4.4 * RATE):5 * RATE]) == 0
    print(f"Timing verified: {len(positions)} beats, {rhythm['tempo_changes']}, silent break preserved.", flush=True)
    analyze(path, 125)


def main():
    with tempfile.TemporaryDirectory(dir="data") as temporary:
        folder = Path(temporary)
        fixture = folder / "fixture.wav"
        timing_fixture(fixture)
        original = folder / "original.wav"
        frames = decode(Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else fixture, original)
        vocals = folder / "vocals.wav"
        separate(original, vocals)
        rhythm = analyze(original)
        render(vocals, rhythm, frames, "balanced", 1, 0.7, folder)
        samples, _ = sf.read(folder / "mix.wav")
        assert len(samples) == sf.info(vocals).frames == frames
        assert np.isfinite(samples).all() and np.max(np.abs(samples)) <= 0.891
        assert (folder / "mix.mp3").stat().st_size > 1024
        print(f"HTDemucs, WAV and MP3 verified for {frames / RATE:.2f} seconds. {len(rhythm['beats'])} beat events.")


if __name__ == "__main__":
    main()
