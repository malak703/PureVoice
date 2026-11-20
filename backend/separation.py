from functools import lru_cache
from hashlib import sha256
from io import BytesIO
from pathlib import Path

import numpy as np
import soundfile as sf

from .ingest import RATE

CHECKPOINT = "955717e8-8726e21a.th"
CHECKSUM = "8726e21a993978c7ba086d3872e7608d7d5bfca646ca4aca459ffda844faa8b4"
MODEL_URL = "https://dl.fbaipublicfiles.com/demucs/hybrid_transformer/" + CHECKPOINT


@lru_cache(maxsize=1)
def load_model():
    import torch
    from demucs.states import load_model as restore

    torch.set_num_threads(4)
    cache = Path(torch.hub.get_dir()) / "checkpoints"
    cache.mkdir(parents=True, exist_ok=True)
    checkpoint = cache / CHECKPOINT
    if not checkpoint.exists():
        torch.hub.download_url_to_file(MODEL_URL, str(checkpoint), hash_prefix=CHECKSUM)
    payload = checkpoint.read_bytes()
    if sha256(payload).hexdigest() != CHECKSUM:
        raise ValueError("The cached HTDemucs model failed verification. Remove the checkpoint and retry.")
    # The official checkpoint includes its model class. Only deserialize verified bytes.
    return restore(torch.load(BytesIO(payload), map_location="cpu", weights_only=False)).eval()


def separate(source, target):
    import torch
    from demucs.apply import apply_model

    samples, rate = sf.read(source, dtype="float32", always_2d=True)
    if rate != RATE:
        raise ValueError("Unexpected model input sample rate.")
    waveform = torch.from_numpy(samples.T.copy())
    reference = waveform.mean(0)
    center = reference.mean()
    scale = reference.std().clamp_min(1e-6)
    normalized = (waveform - center) / scale
    model = load_model()
    with torch.inference_mode():
        parts = apply_model(model, normalized[None], device="cpu", shifts=0, split=True)
    vocals = (parts[0, model.sources.index("vocals")] * scale).numpy().T
    vocals = np.nan_to_num(vocals, nan=0, posinf=0, neginf=0)
    vocals *= min(1.0, 0.98 / max(float(np.max(np.abs(vocals))), 1e-6))
    sf.write(target, vocals, rate, subtype="PCM_24")
