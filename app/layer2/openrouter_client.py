import base64
import time
from io import BytesIO

import httpx
from PIL import Image

from app.config import (
    API_PROVIDER,
    GEMINI_API_KEY,
    GEMINI_MODEL,
    GEMINI_URL,
    OLLAMA_MODEL,
    OLLAMA_URL,
    OPENROUTER_API_KEY,
    OPENROUTER_MODEL,
    OPENROUTER_URL,
)
from app.layer2.prompts import MODERATION_PROMPT


def _encode_image(image: Image.Image) -> str:
    buf = BytesIO()
    image.convert("RGB").save(buf, format="JPEG", quality=85)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def _get_provider_config():
    """Return (url, headers, model, timeout)."""
    if API_PROVIDER == "gemini":
        if not GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY is not set in .env")
        return (
            GEMINI_URL,
            {
                "Authorization": f"Bearer {GEMINI_API_KEY}",
                "Content-Type": "application/json",
            },
            GEMINI_MODEL,
            60.0,
        )

    if API_PROVIDER == "ollama":
        return (
            OLLAMA_URL,
            {"Content-Type": "application/json"},
            OLLAMA_MODEL,
            180.0,
        )

    if not OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY is not set in .env")
    return (
        OPENROUTER_URL,
        {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        },
        OPENROUTER_MODEL,
        60.0,
    )


def analyze_image(
    image: Image.Image, timeout: float | None = None, max_retries: int = 2
) -> dict:
    url, headers, model, default_timeout = _get_provider_config()
    if timeout is None:
        timeout = default_timeout

    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": MODERATION_PROMPT},
                    {"type": "image_url", "image_url": {"url": _encode_image(image)}},
                ],
            }
        ],
        "temperature": 0.0,
        "max_tokens": 2048,
    }

    if API_PROVIDER == "gemini":
        payload["response_format"] = {"type": "json_object"}
        payload["reasoning_effort"] = "none"

    last_error = None
    for attempt in range(max_retries):
        try:
            with httpx.Client(timeout=timeout) as client:
                resp = client.post(url, headers=headers, json=payload)

            if resp.status_code == 429:
                wait = min(int(resp.headers.get("Retry-After", 10)), 60)
                print(
                    f"[layer2] 429 (attempt {attempt+1}/{max_retries}), waiting {wait}s"
                )
                time.sleep(wait)
                last_error = "429 after retries"
                continue

            if resp.status_code != 200:
                raise RuntimeError(
                    f"{API_PROVIDER.upper()} {resp.status_code}: "
                    f"{resp.text[:300]} (model={model})"
                )

            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            finish = data["choices"][0].get("finish_reason", "?")
            print(
                f"[layer2] provider={API_PROVIDER} model={model} "
                f"finish={finish} len={len(content)}"
            )
            return {"raw": content, "usage": data.get("usage", {})}

        except httpx.TimeoutException:
            last_error = f"timeout after {timeout}s"
            print(f"[layer2] timeout (attempt {attempt+1}/{max_retries})")
        except httpx.HTTPError as e:
            last_error = f"http error: {e}"
            print(f"[layer2] http error (attempt {attempt+1}/{max_retries}): {e}")

    raise RuntimeError(f"Layer 2 failed after {max_retries} attempts: {last_error}")
