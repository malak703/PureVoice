"use client";

import { useEffect, useRef, useState } from "react";
import { Activity, AudioLines, CircleHelp, Disc3, Download, FileAudio, Globe2, Link2, LoaderCircle, Music2, SlidersHorizontal, UploadCloud, Youtube } from "lucide-react";

const copy = {
  en: {
    local: "Local processing", language: "العربية", intro: "Arabic vocal & daf converter",
    subtitle: "Isolate vocals and add Daf percussion that follows the original song’s rhythm.",
    source: "Audio source", file: "Upload file", link: "YouTube link", drop: "Drop your audio here",
    browse: "or browse files", limits: "MP3 or WAV · Up to 80 MB and 10 minutes",
    youtube: "Paste a link to a YouTube video", convert: "Convert audio", rhythm: "Rhythm analysis",
    bpm: "Detected tempo", beats: "Beat events", pauses: "Pauses", changes: "Tempo sections",
    empty: "Add a song to see its beat map and tempo.", correction: "BPM override", auto: "Auto",
    studio: "Daf & mix", intensity: "Daf intensity", soft: "Soft", balanced: "Balanced", bold: "Bold",
    vocals: "Vocals", daf: "Daf", apply: "Update mix", preview: "Preview & export", final: "Final mix",
    isolated: "Isolated vocals", listen: "Your audio will appear here once processing finishes.",
    footer: "PureVoice Studio", help: "Changes apply when you update the mix.",
    noBeats: "No reliable beat events detected. The mix contains isolated vocals.",
    failed: "The local audio server could not complete the request.", retry: "Retry status check",
    revisions: "Download the current mix", invalid: "Select an MP3/WAV file or enter a valid YouTube link.",
    stages: { queued: "Queued", importing: "Importing YouTube audio", decoding: "Decoding audio", separating: "Separating vocals with HTDemucs", analyzing: "Analyzing the original rhythm", mixing: "Synthesizing Daf and exporting", ready: "Mix ready", error: "Processing failed" },
  },
  ar: {
    local: "معالجة محلية", language: "English", intro: "استوديو لعزل الغناء وإضافة الدف",
    subtitle: "اعزل الغناء وأضف صوت الدف بما يتبع إيقاع الأغنية الأصلية.",
    source: "مصدر الصوت", file: "رفع ملف", link: "رابط يوتيوب", drop: "أفلت ملف الصوت هنا",
    browse: "أو تصفح الملفات", limits: "MP3 أو WAV · حتى ٨٠ ميغابايت و١٠ دقائق",
    youtube: "ألصق رابط فيديو من يوتيوب", convert: "تحويل الصوت", rhythm: "تحليل الإيقاع",
    bpm: "السرعة المكتشفة", beats: "النبضات", pauses: "التوقفات", changes: "مقاطع السرعة",
    empty: "أضف أغنية لعرض النبضات وسرعة الإيقاع.", correction: "تعديل سرعة الإيقاع", auto: "تلقائي",
    studio: "الدف والمزج", intensity: "شدة الدف", soft: "هادئ", balanced: "متوازن", bold: "قوي",
    vocals: "الغناء", daf: "الدف", apply: "تحديث المزيج", preview: "المعاينة والتصدير", final: "المزيج النهائي",
    isolated: "الغناء المعزول", listen: "سيظهر الصوت هنا بعد انتهاء المعالجة.",
    footer: "استوديو بيور فويس", help: "تُطبّق التغييرات عند تحديث المزيج.",
    noBeats: "تعذّر العثور على نبضات موثوقة. يحتوي المزيج على الغناء المعزول.",
    failed: "تعذّر إكمال الطلب على خادم الصوت المحلي.", retry: "إعادة التحقق من الحالة",
    revisions: "تنزيل المزيج الحالي", invalid: "اختر ملف MP3 أو WAV أو أدخل رابط يوتيوب صالحاً.",
    stages: { queued: "في قائمة الانتظار", importing: "استيراد صوت يوتيوب", decoding: "قراءة الصوت", separating: "عزل الغناء باستخدام HTDemucs", analyzing: "تحليل الإيقاع الأصلي", mixing: "توليد صوت الدف وتصديره", ready: "المزيج جاهز", error: "تعذّرت المعالجة" },
  },
};

type Preset = "soft" | "balanced" | "bold";
type Job = {
  id: string; stage: keyof typeof copy.en.stages; progress: number; name?: string; error?: string;
  revision?: number; duration?: number;
  rhythm?: { bpm: number | null; beats: { time: number; strong: boolean; strength: number }[];
    pauses: { start: number; end: number }[]; tempo_changes: { time: number; bpm: number }[] };
};

async function request(path: string, options?: RequestInit) {
  const response = await fetch(path, { ...options, cache: "no-store" });
  const payload = await response.json();
  if (!response.ok) throw new Error(typeof payload.detail === "string" ? payload.detail : "");
  return payload;
}

export default function Studio() {
  const [lang, setLang] = useState<"en" | "ar">("en");
  const t = copy[lang];
  const [mode, setMode] = useState<"file" | "link">("file");
  const [file, setFile] = useState<File>();
  const [url, setUrl] = useState("");
  const [dragging, setDragging] = useState(false);
  const [job, setJob] = useState<Job>();
  const [error, setError] = useState("");
  const [pollError, setPollError] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [preset, setPreset] = useState<Preset>("balanced");
  const [vocal, setVocal] = useState(100);
  const [daf, setDaf] = useState(70);
  const [bpm, setBpm] = useState("");
  const input = useRef<HTMLInputElement>(null);
  const mixPlayer = useRef<HTMLAudioElement>(null);
  const vocalPlayer = useRef<HTMLAudioElement>(null);
  const busy = !!job && job.stage !== "ready" && job.stage !== "error";
  const id = job?.id;
  const rhythm = job?.rhythm;
  const revision = job?.revision;

  useEffect(() => { document.documentElement.lang = lang; document.documentElement.dir = lang === "ar" ? "rtl" : "ltr"; }, [lang]);

  useEffect(() => {
    if (!id || !busy || pollError) return;
    let stopped = false;
    let next: ReturnType<typeof setTimeout>;
    async function poll() {
      try {
        const result: Job = await request("/api/jobs/" + id);
        if (stopped) return;
        setJob(result);
        if (result.stage !== "ready" && result.stage !== "error") next = setTimeout(poll, 1000);
      } catch {
        if (!stopped) setPollError(true);
      }
    }
    void poll();
    return () => { stopped = true; clearTimeout(next); };
  }, [id, busy, pollError]);

  function pick(selected?: File) {
    if (selected) { setFile(selected); setError(""); }
  }

  async function submit(remix: boolean) {
    setError("");
    setSubmitting(true);
    try {
      if (remix && job) {
        const result = await request("/api/jobs/" + job.id + "/mix", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ preset, vocal_gain: vocal / 100, daf_gain: daf / 100, bpm: bpm ? Number(bpm) : null }),
        });
        setJob({ ...job, id: result.id, stage: "queued", progress: 0, error: undefined });
      } else {
        const body = new FormData();
        if (mode === "file" && file) body.set("file", file);
        else if (mode === "link" && url.trim()) body.set("url", url.trim());
        else throw new Error(t.invalid);
        const result = await request("/api/jobs", { method: "POST", body });
        setPreset("balanced"); setVocal(100); setDaf(70); setBpm("");
        setJob({ id: result.id, stage: "queued", progress: 0 });
      }
      setPollError(false);
    } catch (failure) {
      setError(failure instanceof Error && failure.message ? failure.message : t.failed);
    } finally {
      setSubmitting(false);
    }
  }

  const audio = (kind: string, download = false) => "/api/jobs/" + id + "/audio/" + kind +
    "?revision=" + revision + (download ? "&download=true" : "");

  return (
    <>
      <header className="top"><div className="shell flex items-center justify-between">
        <div className="brand"><span className="logo"><AudioLines size={22} /></span>Pure<span>Voice</span></div>
        <div className="flex items-center gap-3"><span className="local"><i />{t.local}</span>
          <button className="language" onClick={() => setLang(lang === "en" ? "ar" : "en")}><Globe2 size={16} />{t.language}</button></div>
      </div></header>
      <main className="shell">
        <section className="hero"><h1>{t.intro}</h1><p>{t.subtitle}</p></section>
        <div className="studio-grid">
          <section className="card"><h2><Music2 />{t.source}</h2>
            <div className="tabs">
              <button className={mode === "file" ? "selected" : ""} onClick={() => { setMode("file"); setError(""); }}><FileAudio />{t.file}</button>
              <button className={mode === "link" ? "selected" : ""} onClick={() => { setMode("link"); setError(""); }}><Youtube />{t.link}</button>
            </div>
            <form onSubmit={event => { event.preventDefault(); void submit(false); }}>
              {mode === "file" ? <div className={"drop " + (dragging ? "dragging" : "")}
                onDragOver={event => { event.preventDefault(); setDragging(true); }}
                onDragLeave={() => setDragging(false)}
                onDrop={event => { event.preventDefault(); setDragging(false); pick(event.dataTransfer.files[0]); }}>
                <input ref={input} className="sr-only" type="file" tabIndex={-1} accept=".mp3,.wav,audio/mpeg,audio/wav" onChange={event => { pick(event.target.files?.[0]); event.target.value = ""; }} />
                <button type="button" onClick={() => input.current?.click()}><span className="upload-icon"><UploadCloud size={26} /></span>
                  <strong>{file?.name || t.drop}</strong><span>{t.browse}</span></button>
                <small>{t.limits}</small>
              </div> : <div className="link-box"><Link2 size={20} /><label>{t.youtube}
                <input type="url" dir="ltr" required placeholder="https://www.youtube.com/watch?v=…" value={url} onChange={event => setUrl(event.target.value)} />
              </label><small>{t.limits}</small></div>}
              <button className="primary" disabled={busy || submitting || (mode === "file" ? !file : !url.trim())}><AudioLines size={18} />{t.convert}</button>
            </form>
            {job && <div className="status" aria-live="polite"><div>{busy && <LoaderCircle className="animate-spin" size={16} />}{t.stages[job.stage]}<span>{job.progress}%</span></div>
              <progress aria-label={t.stages[job.stage]} max={100} value={job.progress} /></div>}
            {(error || job?.error) && <p role="alert" className="error">{error || job?.error}</p>}
            {pollError && <button className="secondary" onClick={() => setPollError(false)}>{t.retry}</button>}
          </section>

          <section className="card"><h2><SlidersHorizontal />{t.studio}</h2>
            <form onSubmit={event => { event.preventDefault(); void submit(true); }}>
              <fieldset disabled={!revision || busy || submitting}>
                <legend>{t.intensity}</legend>
                <div className="presets">{(["soft", "balanced", "bold"] as const).map(value =>
                  <button type="button" key={value} aria-pressed={preset === value} className={preset === value ? "selected" : ""} onClick={() => setPreset(value)}>{t[value]}</button>)}</div>
                <label className="slider"><span>{t.vocals}<output>{vocal}%</output></span><input type="range" min="0" max="150" value={vocal} onChange={event => setVocal(Number(event.target.value))} /></label>
                <label className="slider"><span>{t.daf}<output>{daf}%</output></span><input type="range" min="0" max="150" value={daf} onChange={event => setDaf(Number(event.target.value))} /></label>
                <label className="bpm-input">{t.correction}<input type="number" min="35" max="260" step="0.1" placeholder={t.auto} value={bpm} onChange={event => setBpm(event.target.value)} /></label>
                <button className="secondary full">{t.apply}</button>
              </fieldset>
              <small className="hint"><CircleHelp size={14} />{t.help}</small>
            </form>
          </section>

          <section className="card"><h2><Activity />{t.rhythm}</h2>
            <div className="metrics">
              <div><small>{t.bpm}</small><strong>{rhythm?.bpm ?? "—"} <em>BPM</em></strong></div>
              <div><small>{t.beats}</small><strong>{rhythm?.beats.length ?? "—"}</strong></div>
              <div><small>{t.pauses}</small><strong>{rhythm?.pauses.length ?? "—"}</strong></div>
            </div>
            {rhythm && job?.duration ? <>
              <div className="beat-map" dir="ltr" aria-label={t.beats} role="img">
                {rhythm.pauses.map(pause => <i className="pause" key={pause.start} style={{ left: (100 * pause.start / job.duration!) + "%", width: (100 * (pause.end - pause.start) / job.duration!) + "%" }} />)}
                {rhythm.beats.map(beat => <i className={beat.strong ? "strong" : ""} key={beat.time}
                  title={beat.time.toFixed(2) + " s"} style={{ left: (100 * beat.time / job.duration!) + "%", height: (20 + 75 * beat.strength) + "%" }} />)}
              </div>
              <small className="hint">{rhythm.beats.length ? t.changes + " · " + rhythm.tempo_changes.map(change => change.time.toFixed(1) + "s / " + change.bpm + " BPM").join(" · ") : t.noBeats}</small>
            </> : <p className="empty">{t.empty}</p>}
          </section>

          <section className="card"><h2><Disc3 />{t.preview}</h2>
            {revision ? <>
              <div className="player"><label htmlFor="mix">{t.final}</label><audio key={audio("wav")} id="mix" ref={mixPlayer} controls preload="metadata" src={audio("wav")} onPlay={() => vocalPlayer.current?.pause()} /></div>
              <div className="player"><label htmlFor="vocals">{t.isolated}</label><audio id="vocals" ref={vocalPlayer} controls preload="metadata" src={audio("vocals")} onPlay={() => mixPlayer.current?.pause()} /></div>
              <div className="downloads" aria-label={t.revisions}>
                <a className="secondary" href={audio("wav", true)}><Download size={16} />WAV</a>
                <a className="secondary" href={audio("mp3", true)}><Download size={16} />MP3</a>
              </div>
            </> : <div className="preview-empty"><AudioLines size={28} /><p>{t.listen}</p></div>}
          </section>
        </div>
        <footer><AudioLines size={16} />{t.footer}</footer>
      </main>
    </>
  );
}
