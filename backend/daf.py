import numpy as np
from scipy.signal import butter, sosfilt

from .ingest import RATE

PRESETS = {"soft": (0.56, 0.23), "balanced": (0.82, 0.48), "bold": (1.0, 0.75)}


def hit(kind, rng):
    duration = {"dum": 0.29, "tak": 0.14, "jingle": 0.19}[kind]
    t = np.arange(round(RATE * duration)) / RATE
    pitch = rng.uniform(0.94, 1.06)
    noise = rng.normal(size=len(t))
    if kind == "dum":
        phase = 2 * np.pi * pitch * (74 * t + 0.9 * (1 - np.exp(-t * 43)))
        sound = 0.78 * np.sin(phase) * np.exp(-t * 19)
        sound += 0.24 * np.sin(phase * 1.77) * np.exp(-t * 32)
        sound += 0.11 * sosfilt(butter(2, 1100, fs=RATE, output="sos"), noise) * np.exp(-t * 90)
    elif kind == "tak":
        attack = sosfilt(butter(2, [1050, 6200], btype="bandpass", fs=RATE, output="sos"), noise)
        sound = 0.62 * attack * np.exp(-t * 58)
        sound += 0.26 * np.sin(2 * np.pi * 410 * pitch * t) * np.exp(-t * 48)
    else:
        frequencies = [2399, 3127, 4891, 6197, 8423]
        sound = sum(np.sin(2 * np.pi * pitch * f * t + rng.uniform(0, 6.28)) for f in frequencies)
        sound = 0.18 * sound * np.exp(-t * 33)
    return sound * np.minimum(t / 0.002, 1) * np.minimum((duration - t) / 0.012, 1)


def generate(frames, rhythm, preset):
    gain, jingle_chance = PRESETS[preset]
    rng = np.random.default_rng(74)
    output = np.zeros((frames, 2), dtype=np.float32)
    for beat in rhythm["beats"]:
        if preset == "soft" and not beat["strong"] and beat["strength"] < 0.25:
            continue
        kind = "dum" if beat["strong"] else "tak"
        start = round(beat["time"] * RATE)
        end = min(frames, next((round(pause["start"] * RATE) for pause in rhythm["pauses"] if pause["start"] > beat["time"]), frames))
        for layer, level, offset in [(kind, 1, 0), ("jingle", 0.24 if rng.random() < jingle_chance else 0, 0.012)]:
            position = start + round(RATE * offset)
            if not level or position >= end:
                continue
            sound = hit(layer, rng)[:end - position]
            pan = rng.uniform(-0.11, 0.11)
            velocity = gain * level * (0.32 + 0.52 * beat["strength"]) * rng.uniform(0.92, 1.08)
            output[position:position + len(sound)] += sound[:, None] * velocity * np.array([1 - pan, 1 + pan])
    return output
