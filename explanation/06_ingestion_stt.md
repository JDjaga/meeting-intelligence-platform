# 6. Ingestion & Speech-to-Text (`app/stt/transcriber.py`)

`ingest(path)` routes by extension and returns plain transcript text — every later stage
only ever sees text, so **any new file type is a 5-line addition here**.

- **`.txt/.md`** — read directly. **`.srt/.vtt`** — subtitle timestamps stripped
  (`strip_subtitle_format`), dialogue kept.
- **`.pdf`** — `pypdf` extracts page text. Scanned/image PDFs have no text layer and
  return empty (rejected as "too short" at upload with a clear message).
- **`.docx`** — `python-docx` concatenates non-empty paragraphs.
- **Audio (`.mp3/.wav/.m4a/.ogg/.flac/.webm/.mp4`)** — `faster-whisper` (`tiny`, int8 CPU).
  Two Windows-specific robustness fixes live here: `.wav` is decoded with the **stdlib
  `wave` module** (bypasses the fragile PyAV/ffmpeg stack that breaks on version drift),
  and all other formats are converted with the **bundled static ffmpeg binary**
  (`imageio-ffmpeg`) to 16 kHz mono, then fed to whisper as a numpy array. Whisper's own
  file-decoding path is never used.

Why tiny+int8: ~75 MB one-time download, ~real-time CPU transcription, good enough for
clear meeting audio (expect minor mishears like "sales sink" — realistic STT noise, and
harmless because evidence quotes come from the transcript itself).
