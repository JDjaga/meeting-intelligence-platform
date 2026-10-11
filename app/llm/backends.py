"""Multi-LLM backend for chat and extraction.

One interface, two providers, zero hard dependencies beyond what we ship:
- Gemini  : stdlib urllib REST + GEMINI_API_KEY (no SDK install needed)
- HF      : huggingface_hub InferenceClient + HF_TOKEN (ships with faster-whisper)

Selection: MIP_CHAT_BACKEND=auto (default) tries Gemini → HF, first key found wins.
Set it to gemini|hf to force one (or pass only=...). Anything without a key is
skipped, so offline mode keeps working untouched.

Contract: generate_json(system, user, only=None) -> (backend_name, dict) | (None, {})
"""
from __future__ import annotations
import json
import urllib.request
from app import config


def _strip_fences(s: str) -> str:
    s = (s or "").strip()
    if s.startswith("```"):
        s = s.strip("`").strip()
        if s.lower().startswith("json"):
            s = s[4:].strip()
    return s


def _gemini(system: str, user: str) -> dict | None:
    if not config.GEMINI_API_KEY:
        return None
    # Fallback chain: primary model, then backup model (wrong name / quota / 404).
    models = [config.GEMINI_MODEL, config.GEMINI_FALLBACK_MODEL]
    last: Exception | None = None
    for model in dict.fromkeys(m for m in models if m):
        body = json.dumps({
            "system_instruction": {"parts": [{"text": system}]},
            "contents": [{"parts": [{"text": user}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0.1},
        }).encode()
        url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
               f"{model}:generateContent?key={config.GEMINI_API_KEY}")
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                data = json.loads(r.read().decode())
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(_strip_fences(text))
        except Exception as e:  # try next model
            last = e
    raise RuntimeError(f"Gemini failed on all models: {last}")


def _hf(system: str, user: str) -> dict | None:
    if not config.HF_TOKEN:
        return None
    from huggingface_hub import InferenceClient
    client = InferenceClient(model=config.HF_MODEL, token=config.HF_TOKEN)
    resp = client.chat_completion(
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": user}],
        max_tokens=800, temperature=0.1)
    return json.loads(_strip_fences(resp.choices[0].message.content or "{}"))


_BACKENDS = (("gemini", _gemini), ("hf", _hf))


def generate_json(system: str, user: str, only: str | None = None) -> tuple[str | None, dict]:
    """Try backends in configured order. Returns (name, parsed_json) or (None, {})."""
    want = (only or config.CHAT_BACKEND or "auto").lower()
    ordered = [b for b in _BACKENDS if want == "auto" or b[0] == want]
    for name, fn in ordered:
        try:
            data = fn(system, user)
        except Exception:
            continue  # provider failed → next backend, never crash the chat
        if isinstance(data, dict) and data:
            return name, data
    return None, {}
