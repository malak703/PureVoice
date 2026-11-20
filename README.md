# PureVoice

PureVoice separates vocals with Meta's pretrained HTDemucs and accompanies them with procedural Daf. It accepts MP3 and WAV uploads and single YouTube video links. The Next.js studio supports English and Arabic, including right-to-left layout.

## Start on Windows

Install Python 3.13 and Node.js 24. From the repository root in PowerShell:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt --extra-index-url https://download.pytorch.org/whl/cpu
npm.cmd ci --prefix frontend
```

In one terminal:

```powershell
$env:TORCH_HOME = Join-Path $PWD 'data/torch'
.\.venv\Scripts\python.exe -m uvicorn backend.api:app --host 127.0.0.1 --port 8000
```

In a second terminal:

```powershell
npm.cmd run dev --prefix frontend
```

Open [the local studio](http://127.0.0.1:3000) and upload an MP3 or WAV, or choose **YouTube link**. The first conversion downloads the official ~84 MB HTDemucs checkpoint. FFmpeg comes from the Python dependency and can be overridden with `PUREVOICE_FFMPEG`. YouTube import uses yt-dlp with Node.js and needs internet access. YouTube can restrict downloads of particular videos or networks. Use audio you are authorized to process.

## Use the studio

- Choose an audio source between 1 second and 10 minutes, up to 80 MB.
- Watch the processing stages. CPU separation and first-time audio analysis can take a while.
- Inspect the detected tempo and beat timeline. Taller lavender bars mark stronger detected accents and shaded areas mark quiet gaps.
- Adjust the Daf preset, vocal level or Daf level, then choose **Update mix**. A BPM override guides beat tracking while keeping placements tied to detected transients.
- Preview the mix or isolated vocal stem, and download the final mix as 24-bit WAV or 256 kbps MP3.

## Pipeline and limits

FFmpeg decodes stereo PCM at 44.1 kHz. HTDemucs extracts the vocal stem on CPU. Librosa analyzes the original mix using spectral onsets, low-frequency accents, frame-varying tempo estimates and an energy gate for quiet gaps. The Daf engine uses the selected event timestamps to place synthesized DUM, TAK and jingle hits. Pitch and dynamics vary while timing stays anchored to the events. The WAV matches the decoded source's sample count. The mixer reduces the overall gain when necessary to leave headroom before MP3 encoding.

Sparse, rubato, densely arranged or weakly percussive recordings can produce missed or misclassified beats. Vocal separation can leave audible bleed. Browser playback and MP3 duration displays can vary by decoder. Files stay under `data/` by default. The server keeps active jobs in memory and processes one at a time. Restarting the API clears those job references. To reclaim storage, close the API before removing old job folders.

## Verification

```powershell
$env:TORCH_HOME = Join-Path $PWD 'data/torch'
New-Item -ItemType Directory -Force data | Out-Null
.\.venv\Scripts\python.exe -m backend.smoke_test
.\.venv\Scripts\python.exe -m backend.smoke_test 'C:\path\to\your-short-song.wav'
npm.cmd run build --prefix frontend
```

The test checks uneven beat placement across two tempo sections, a silent break, HTDemucs inference, mix duration and peak headroom, and MP3 creation.
