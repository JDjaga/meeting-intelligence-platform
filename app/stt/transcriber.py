"""Speech-to-text + transcript ingestion.

Supports: .txt / .md / .vtt / .srt uploads directly.
Audio (.mp3/.wav/.m4a/.ogg): uses faster-whisper if installed, else raises a
clear error telling the user to upload a transcript instead. No silent failures.
"""
from __future__ import annotations
import re
from pathlib import Path

AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".webm", ".mp4"}
TEXT_EXTS = {".txt", ".md", ".vtt", ".srt"}
DOC_EXTS = {".pdf", ".docx"}


def strip_subtitle_format(text: str) -> str:
    text = re.sub(r"\d+\n\d{2}:\d{2}:\d{2}[,\.]\d{3} -->.*\n", "", text)
    text = re.sub(r"WEBVTT.*\n", "", text)
    lines = [ln.strip() for ln in text.splitlines()
             if ln.strip() and not re.match(r"^\d+$", ln.strip())]
    return "\n".join(lines)


def read_transcript_file(path: str | Path) -> str:
    p = Path(path)
    return strip_subtitle_format(p.read_text(encoding="utf-8", errors="ignore")).strip()


def _wav_to_16k_mono(path: str | Path):
    """Decode a .wav with stdlib only → float32 mono 16kHz numpy array.

    Avoids the ffmpeg/PyAV stack entirely (version-fragile on Windows).
    """
    import wave
    import numpy as np
    with wave.open(str(path), "rb") as w:
        n_ch, width, rate, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        raw = w.readframes(n)
    dtype = {1: np.int8, 2: np.int16, 4: np.int32}[width]
    audio = np.frombuffer(raw, dtype=dtype).astype(np.float32)
    audio /= float(2 ** (8 * width - 1))
    if n_ch > 1:
        audio = audio.reshape(-1, n_ch).mean(axis=1)
    if rate != 16000:
        idx = (np.arange(int(len(audio) * 16000 / rate)) * rate / 16000)
        audio = np.interp(idx, np.arange(len(audio)), audio).astype(np.float32)
    return audio


def _any_audio_to_16k(path: str | Path):
    """Any supported audio → float32 mono 16kHz array, without PyAV.

    .wav is decoded with stdlib; everything else is converted with the
    bundled static ffmpeg binary (imageio-ffmpeg). faster-whisper then
    receives a numpy array, so its ffmpeg/PyAV stack is never touched.
    """
    import subprocess
    import tempfile
    p = Path(path)
    if p.suffix.lower() == ".wav":
        return _wav_to_16k_mono(p)
    try:
        import imageio_ffmpeg
    except ImportError as e:
        raise RuntimeError(
            "Non-wav audio needs imageio-ffmpeg (pip install imageio-ffmpeg)."
        ) from e
    exe = imageio_ffmpeg.get_ffmpeg_exe()
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        out = tmp.name
    subprocess.run([exe, "-y", "-v", "error", "-i", str(p),
                    "-ac", "1", "-ar", "16000", "-sample_fmt", "s16", out],
                   check=True)
    try:
        return _wav_to_16k_mono(out)
    finally:
        Path(out).unlink(missing_ok=True)


def read_document_file(path: str | Path) -> str:
    """Extract plain text from .pdf / .docx uploads."""
    ext = Path(path).suffix.lower()
    if ext == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError as e:
            raise RuntimeError("PDF upload needs pypdf (pip install pypdf).") from e
        reader = PdfReader(str(path))
        return "\n".join((pg.extract_text() or "") for pg in reader.pages).strip()
    if ext == ".docx":
        try:
            import docx
        except ImportError as e:
            raise RuntimeError("Word upload needs python-docx (pip install python-docx).") from e
        doc = docx.Document(str(path))
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip()).strip()
    raise ValueError(f"Unsupported document type {ext}")


def transcribe_audio(path: str | Path, model: str = "tiny") -> str:
    try:
        from faster_whisper import WhisperModel
    except ImportError as e:
        raise RuntimeError(
            "Audio transcription needs faster-whisper (pip install faster-whisper). "
            "Alternatively upload a .txt transcript."
        ) from e
    wm = WhisperModel(model, compute_type="int8")
    segments, _ = wm.transcribe(_any_audio_to_16k(path))
    return "\n".join(s.text.strip() for s in segments if s.text.strip())


def ingest(path: str | Path) -> str:
    p = Path(path)
    ext = p.suffix.lower()
    if ext in TEXT_EXTS:
        return read_transcript_file(p)
    if ext in DOC_EXTS:
        return read_document_file(p)
    if ext in AUDIO_EXTS:
        return transcribe_audio(p)
    raise ValueError(f"Unsupported file type {ext}. Upload {sorted(TEXT_EXTS | DOC_EXTS | AUDIO_EXTS)}")
