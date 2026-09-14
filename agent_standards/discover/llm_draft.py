"""Optional LLM drafting layer — advisory only.

Pass 2 of discovery. May rewrite a candidate's title/body prose using a LOCAL
Ollama endpoint (default http://localhost:11434). It can never:
  - change evidence numbers,
  - create or delete candidates,
  - mark anything approved.
If Ollama is unreachable, candidates pass through untouched. No API keys.
"""

from __future__ import annotations

import json
import urllib.request

DEFAULT_URL = "http://localhost:11434"
DEFAULT_MODEL = "llama3.2"

PROMPT = (
    "Rewrite the following coding standard's title and body so they are clear and "
    "actionable for an AI coding agent. Keep meaning identical. Reply with strict "
    "JSON: {{\"title\": \"...\", \"body\": \"...\"}}. "
    "Standard: title={title!r} body={body!r} category={category!r}"
)


def _ollama_chat(base_url: str, model: str, prompt: str, timeout: int = 60) -> str:
    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
    }).encode()
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/api/chat", data=payload,
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.load(resp)
    return data.get("message", {}).get("content", "")


def _extract_json(text: str) -> dict | None:
    try:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            return None
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None


def draft(std, base_url: str = DEFAULT_URL, model: str = DEFAULT_MODEL):
    """Return a copy of `std` with LLM-polished title/body, or the original.

    Evidence, status, criticality and id are NEVER modified. Purely advisory.
    """
    try:
        raw = _ollama_chat(
            base_url, model,
            PROMPT.format(title=std.title, body=std.body, category=std.category))
        parsed = _extract_json(raw)
        if not parsed or "title" not in parsed or "body" not in parsed:
            return std
        out = type(std)(**vars(std) | {})
        out.title, out.body = str(parsed["title"]), str(parsed["body"])
        return out
    except (urllib.error.URLError, OSError, TimeoutError, ValueError):
        return std  # local model unavailable -> pass through unchanged
