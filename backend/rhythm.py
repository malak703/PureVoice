import librosa
import numpy as np
from scipy.ndimage import maximum_filter1d


def analyze(path, bpm_hint=None):
    # Analysis runs on the original mix and uses a frame-varying tempo estimate.
    rate, hop = 22050, 220
    samples, _ = librosa.load(path, sr=rate, mono=False)
    magnitude = np.abs(librosa.stft(samples, n_fft=1024, hop_length=hop))
    if samples.ndim == 2:
        magnitude = magnitude.mean(axis=0)
    energy = np.sqrt(np.mean(magnitude ** 2, axis=0))
    if energy.max() < 1e-5:
        return {"bpm": None, "beats": [], "pauses": [], "tempo_changes": []}
    bands = librosa.power_to_db(librosa.feature.melspectrogram(S=magnitude ** 2, sr=rate, n_fft=1024))
    onset = librosa.onset.onset_strength(S=bands, sr=rate, hop_length=hop, n_fft=1024)
    bass = librosa.onset.onset_strength(S=bands[:20], sr=rate, hop_length=hop, n_fft=1024)
    local = librosa.feature.tempo(onset_envelope=onset, sr=rate, hop_length=hop,
                                  aggregate=None, start_bpm=bpm_hint or 110, ac_size=4)
    anchor = bpm_hint or float(np.median(local))
    # Correct octave errors while leaving the local tempo curve intact.
    local = local * 2 ** np.round(np.log2(anchor / local))
    if bpm_hint:
        local *= bpm_hint / np.median(local)
    _, grid = librosa.beat.beat_track(onset_envelope=onset, sr=rate, hop_length=hop, bpm=local)
    onsets = librosa.onset.onset_detect(onset_envelope=onset, sr=rate, hop_length=hop, delta=0.065)
    peak_scale = max(float(np.percentile(onset[onsets], 80)) if len(onsets) else float(onset.max()), 1e-6)
    bass_scale = max(float(np.percentile(bass[onsets], 80)) if len(onsets) else float(bass.max()), 1e-6)
    if bpm_hint is None and len(grid) >= 4 and anchor < 100:
        # Alternating accents may make the tracker lock onto every other beat.
        # Raise the metrical level only when measured onsets support the intervening beats.
        intervals = [(a, b) for a, b in zip(grid[:-1], grid[1:]) if (b - a) * hop / rate < 1.3]
        supported = sum(np.any((abs(onsets - (a + b) / 2) <= (b - a) * 0.15) &
                               (onset[onsets] >= peak_scale * 0.18)) for a, b in intervals)
        if intervals and supported / len(intervals) >= 0.55:
            local *= 2
            anchor *= 2
            _, grid = librosa.beat.beat_track(onset_envelope=onset, sr=rate, hop_length=hop, bpm=local)
    if len(grid) < 3:
        grid = onsets
    active = maximum_filter1d(energy, size=17) > max(float(np.percentile(energy, 90)) * 0.025, 1e-5)
    edges = np.flatnonzero(np.diff(np.r_[False, ~active, False]))
    pauses = [{"start": round(a * hop / rate, 3), "end": round(min(b * hop / rate, samples.shape[-1] / rate), 3)}
              for a, b in edges.reshape(-1, 2) if (b - a) * hop / rate >= 0.24]
    events = []
    for index, frame in enumerate(grid):
        interval = (grid[index + 1] - frame) if index + 1 < len(grid) else (60 * rate / (hop * anchor))
        nearby = onsets[np.abs(onsets - frame) <= min(9, max(3, interval * 0.23))]
        if len(nearby):
            frame = int(nearby[np.argmin(np.abs(nearby - frame))])
        if not active[frame] or (events and frame - events[-1]["frame"] < 12):
            continue
        strength = min(1.0, float(np.max(onset[max(0, frame - 2):frame + 3]) / peak_scale))
        low = min(1.0, float(np.max(bass[max(0, frame - 2):frame + 3]) / bass_scale))
        if strength < 0.10 and low < 0.14:
            continue
        events.append({"frame": int(frame), "time": round(frame * hop / rate, 5),
                       "strength": round(0.65 * strength + 0.35 * low, 3),
                       "strong": bool(0.55 * strength + 0.45 * low >= 0.62),
                       "local_bpm": round(float(local[frame]), 1)})
    changes = []
    for event in events:
        if not changes or (event["time"] - changes[-1]["time"] >= 2 and abs(event["local_bpm"] - changes[-1]["bpm"]) >= 6):
            changes.append({"time": event["time"], "bpm": event["local_bpm"]})
    return {"bpm": round(float(np.median([e["local_bpm"] for e in events])), 1) if events else None,
            "beats": events, "pauses": pauses, "tempo_changes": changes}
