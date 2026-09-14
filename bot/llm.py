"""One LLM interface, three providers.

Set LLM_PROVIDER to `openrouter`, `gemini` or `anthropic`. Everything else in
the bot calls `ask()` / `ask_json()` and never learns which one is in use.

OpenRouter is the default because it takes one key and reaches every model,
including Claude - so the provider can change without touching this file.
"""
from __future__ import annotations

import json
import os
import re
import time

import requests

TIMEOUT = 300
RETRY_STATUS = (408, 409, 429, 500, 502, 503, 504, 529)

DEFAULT_MODELS = {
    "openrouter": "anthropic/claude-sonnet-4.5",
    "gemini": "gemini-2.5-flash",
    "anthropic": "claude-sonnet-4-5",
}


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, "").strip() or default


def provider() -> str:
    p = _env("LLM_PROVIDER", "openrouter").lower()
    if p not in DEFAULT_MODELS:
        raise RuntimeError(
            f"LLM_PROVIDER '{p}' is not one of: {', '.join(DEFAULT_MODELS)}")
    return p


def model() -> str:
    return _env("LLM_MODEL", DEFAULT_MODELS[provider()])


def _key() -> str:
    p = provider()
    var = {"openrouter": "OPENROUTER_API_KEY",
           "gemini": "GEMINI_API_KEY",
           "anthropic": "ANTHROPIC_API_KEY"}[p]
    value = _env(var)
    if not value:
        raise RuntimeError(
            f"LLM_PROVIDER is '{p}' so {var} must be set. Add it under "
            f"Settings -> Secrets and variables -> Actions.")
    return value


# --------------------------------------------------------------- providers

def _openrouter(system: str, user: str, max_tokens: int, temperature: float):
    r = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {_key()}",
                 "Content-Type": "application/json",
                 # Optional but polite; shows up in OpenRouter's dashboard.
                 "X-Title": "diy-video-bot"},
        json={"model": model(),
              "messages": [{"role": "system", "content": system},
                           {"role": "user", "content": user}],
              "max_tokens": max_tokens,
              "temperature": temperature},
        timeout=TIMEOUT)
    if r.status_code != 200:
        return None, f"{r.status_code} {r.text[:400]}", r.status_code
    body = r.json()
    if "error" in body and not body.get("choices"):
        return None, f"provider error: {str(body['error'])[:300]}", 500
    try:
        return body["choices"][0]["message"]["content"], None, 200
    except (KeyError, IndexError):
        return None, f"unexpected shape: {str(body)[:300]}", 500


def _gemini(system: str, user: str, max_tokens: int, temperature: float):
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{model()}:generateContent")
    r = requests.post(
        url,
        headers={"Content-Type": "application/json",
                 "x-goog-api-key": _key()},
        json={"systemInstruction": {"parts": [{"text": system}]},
              "contents": [{"role": "user", "parts": [{"text": user}]}],
              "generationConfig": {"maxOutputTokens": max_tokens,
                                   "temperature": temperature}},
        timeout=TIMEOUT)
    if r.status_code != 200:
        return None, f"{r.status_code} {r.text[:400]}", r.status_code
    body = r.json()
    try:
        parts = body["candidates"][0]["content"]["parts"]
        return "".join(p.get("text", "") for p in parts), None, 200
    except (KeyError, IndexError):
        # A safety block or an empty finish comes back without parts.
        reason = (body.get("candidates") or [{}])[0].get("finishReason", "?")
        return None, f"no text returned (finishReason={reason})", 500


def _anthropic(system: str, user: str, max_tokens: int, temperature: float):
    r = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={"x-api-key": _key(),
                 "anthropic-version": "2023-06-01",
                 "content-type": "application/json"},
        json={"model": model(), "max_tokens": max_tokens,
              "temperature": temperature, "system": system,
              "messages": [{"role": "user", "content": user}]},
        timeout=TIMEOUT)
    if r.status_code != 200:
        return None, f"{r.status_code} {r.text[:400]}", r.status_code
    blocks = r.json().get("content", [])
    return "".join(b.get("text", "") for b in blocks
                   if b.get("type") == "text"), None, 200


_DISPATCH = {"openrouter": _openrouter, "gemini": _gemini,
             "anthropic": _anthropic}


# ------------------------------------------------------------------- api

def ask(system: str, user: str, max_tokens: int = 4000,
        temperature: float = 1.0, retries: int = 3) -> str:
    fn = _DISPATCH[provider()]
    last = "no attempt made"
    for attempt in range(retries):
        text, error, status = fn(system, user, max_tokens, temperature)
        if text:
            return text
        last = error or "empty response"
        if status in RETRY_STATUS and attempt < retries - 1:
            time.sleep(5 * (attempt + 1))
            continue
        break
    raise RuntimeError(f"{provider()} ({model()}) call failed: {last}")


def ask_json(system: str, user: str, max_tokens: int = 6000,
             temperature: float = 1.0):
    raw = ask(system + "\n\nReply with JSON only. No prose, no code fence.",
              user, max_tokens=max_tokens, temperature=temperature)
    return parse_json(raw)


def parse_json(raw: str):
    raw = raw.strip()
    fence = re.search(r"```(?:json)?\s*(.+?)```", raw, re.S)
    if fence:
        raw = fence.group(1).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        for opener, closer in (("{", "}"), ("[", "]")):
            start, end = raw.find(opener), raw.rfind(closer)
            if start != -1 and end > start:
                try:
                    return json.loads(raw[start:end + 1])
                except json.JSONDecodeError:
                    continue
        raise
