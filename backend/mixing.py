import numpy as np
import soundfile as sf

from .daf import generate
from .ingest import RATE, encode_mp3


def render(vocals, rhythm, frames, preset, vocal_gain, daf_gain, directory):
    voice, _ = sf.read(vocals, dtype="float32", always_2d=True)
    voice = voice[:frames]
    if len(voice) < frames:
        voice = np.pad(voice, ((0, frames - len(voice)), (0, 0)))
    percussion = generate(frames, rhythm, preset)
    mix = voice * vocal_gain + percussion * daf_gain
    mix *= min(1, 0.89 / max(float(np.max(np.abs(mix))), 1e-6))
    sf.write(directory / "mix.wav", mix, RATE, subtype="PCM_24")
    encode_mp3(directory / "mix.wav", directory / "mix.mp3")
