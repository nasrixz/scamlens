"""AI scam-detection clients. Anthropic primary, Gemini optional.

Both return the same normalized `ScanVerdict` — the worker doesn't care which
model actually ran. The prompt lives here (single source of truth).
"""
from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass, field
from typing import Any, Optional

import structlog
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

log = structlog.get_logger()


SYSTEM_PROMPT = (
    "You are a cybersecurity expert analyzing a webpage for scam indicators. "
    "Review the domain name, HTML content, and screenshot provided.\n\n"
    "STEP 1 — analyze the DOMAIN STRING itself (not just the page content):\n"
    "- Does it look like a brand name with character substitutions? "
    "  (paypa1.com / paypa11.com / paypaII.com → paypal.com; "
    "  g00gle.com / google-secure.xyz → google.com; "
    "  app1e-support.com → apple.com; rnaybank.com → maybank.com.my). "
    "  These are typosquats EVEN IF the page later redirects to the real brand "
    "  or shows legitimate-looking content. Flag them.\n"
    "- Is the brand the leading label, or buried inside (e.g. login-paypal-secure.xyz)? "
    "  Brand inside an unrelated domain is impersonation.\n\n"
    "STEP 2 — analyze the page CONTENT for:\n"
    "- Fake login pages mimicking banks/services\n"
    "- Phishing attempts asking for credentials, OTP, or credit cards\n"
    "- Fake investment or crypto schemes with unrealistic promises\n"
    "- Urgency tactics and countdown timers\n"
    "- Suspicious redirects or obfuscated scripts\n"
    "- Prize/lottery scams\n\n"
    "Decision rules:\n"
    "- A domain that looks like a typosquat of a major brand is at least "
    "'suspicious' (risk ≥ 60), even if the page itself looks legitimate or "
    "redirects to the real brand. Set mimics_brand to the brand it imitates.\n"
    "- Phishing-style content + brand-mimic domain → 'scam' (risk ≥ 90).\n\n"
    "Respond ONLY with a JSON object, no markdown, no commentary:\n"
    "{\n"
    '  "risk_score": <0-100>,\n'
    '  "verdict": "safe" | "suspicious" | "scam",\n'
    '  "reasons": ["reason1", "reason2"],\n'
    '  "mimics_brand": "<brand name or null>",\n'
    '  "confidence": <0-100>\n'
    "}"
)


@dataclass
class ScanVerdict:
    verdict: str  # safe | suspicious | scam
    risk_score: int
    confidence: int
    reasons: list[str] = field(default_factory=list)
    mimics_brand: Optional[str] = None
    model: str = ""

    @property
    def primary_reason(self) -> str:
        return self.reasons[0] if self.reasons else self.verdict


class AIClient:
    async def scan(self, domain: str, html: str, screenshot_png: bytes) -> ScanVerdict:
        raise NotImplementedError


class AnthropicClient(AIClient):
    def __init__(self, api_key: str, model: str):
        # Imported lazily so the scanner image doesn't require the SDK just to
        # boot with a different provider.
        import anthropic  # noqa: WPS433
        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._model = model

    async def scan(self, domain: str, html: str, screenshot_png: bytes) -> ScanVerdict:
        user_blocks: list[dict[str, Any]] = [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": base64.b64encode(screenshot_png).decode(),
                },
            },
            {
                "type": "text",
                "text": (
                    f"Domain being analyzed: {domain}\n\n"
                    f"HTML content (truncated):\n```html\n{html}\n```"
                ),
            },
        ]

        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=1, max=8),
            retry=retry_if_exception_type(Exception),
            reraise=True,
        ):
            with attempt:
                response = await self._client.messages.create(
                    model=self._model,
                    max_tokens=600,
                    system=SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": user_blocks}],
                )
                text = "".join(
                    block.text for block in response.content if block.type == "text"
                )
                return _parse_verdict(text, model=self._model)

        raise RuntimeError("unreachable")


class QwenClient(AIClient):
    """Alibaba Qwen via DashScope OpenAI-compatible endpoint.

    Vision-capable models (e.g. qwen-vl-max, qwen-vl-plus) accept image +
    text in a single multimodal message — same shape as OpenAI's vision API
    so we use the official `openai` SDK with a custom base_url.
    """

    def __init__(self, api_key: str, model: str, base_url: str):
        from openai import AsyncOpenAI  # lazy import
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self._model = model

    async def scan(self, domain: str, html: str, screenshot_png: bytes) -> ScanVerdict:
        # Qwen-VL via DashScope OpenAI-compat:
        #   - rejects a separate `system` role alongside multimodal content
        #     (returns "model input format error")
        #   - HTML beyond ~30k chars triggers the same generic 400.
        # Inline the system prompt and trim HTML.
        # Also detect actual image mime — fetcher falls back to JPEG when the
        # PNG is too large, so hard-coding "image/png" can desync.
        mime = _sniff_image_mime(screenshot_png)
        image_data_url = (
            f"data:{mime};base64," + base64.b64encode(screenshot_png).decode()
        )
        trimmed_html = html[:30000]
        prompt_text = (
            f"{SYSTEM_PROMPT}\n\n"
            f"Domain being analyzed: {domain}\n\n"
            f"HTML content (truncated):\n```html\n{trimmed_html}\n```"
        )
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": image_data_url}},
                    {"type": "text", "text": prompt_text},
                ],
            },
        ]

        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=1, max=8),
            retry=retry_if_exception_type(Exception),
            reraise=True,
        ):
            with attempt:
                resp = await self._client.chat.completions.create(
                    model=self._model,
                    messages=messages,
                    max_tokens=600,
                )
                text = resp.choices[0].message.content or ""
                return _parse_verdict(text, model=self._model)
        raise RuntimeError("unreachable")


class GeminiClient(AIClient):
    def __init__(self, api_key: str, model: str):
        from google import genai  # noqa: WPS433
        self._client = genai.Client(api_key=api_key)
        self._model = model

    async def scan(self, domain: str, html: str, screenshot_png: bytes) -> ScanVerdict:
        from google.genai import types  # noqa: WPS433

        contents = [
            types.Part.from_bytes(data=screenshot_png, mime_type="image/png"),
            types.Part.from_text(
                text=(
                    f"Domain being analyzed: {domain}\n\n"
                    f"HTML content (truncated):\n{html}"
                )
            ),
        ]
        response = await self._client.aio.models.generate_content(
            model=self._model,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_mime_type="application/json",
                max_output_tokens=600,
            ),
        )
        return _parse_verdict(response.text or "", model=self._model)


def _parse_verdict(text: str, model: str) -> ScanVerdict:
    """Accept raw JSON or JSON fenced in ```json ... ```."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        # Strip ```json / ``` fences
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        # Salvage first {...} block if the model wrapped commentary around it.
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not match:
            log.warning("verdict_parse_failed", body=text[:300])
            return ScanVerdict(
                verdict="suspicious", risk_score=50, confidence=10,
                reasons=["model returned unparseable response"], model=model,
            )
        data = json.loads(match.group(0))

    verdict = str(data.get("verdict", "suspicious")).lower()
    if verdict not in ("safe", "suspicious", "scam"):
        verdict = "suspicious"

    return ScanVerdict(
        verdict=verdict,
        risk_score=_clamp(data.get("risk_score", 0)),
        confidence=_clamp(data.get("confidence", 0)),
        reasons=[str(r) for r in (data.get("reasons") or [])][:8],
        mimics_brand=data.get("mimics_brand") or None,
        model=model,
    )


def _sniff_image_mime(data: bytes) -> str:
    """Detect image format from magic bytes. Defaults to PNG."""
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n"):
        return "image/png"
    if data.startswith(b"GIF8"):
        return "image/gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return "image/png"


def _clamp(value) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, min(100, n))


def build_client(provider: str, cfg) -> AIClient:
    if provider == "anthropic":
        if not cfg.anthropic_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not set")
        return AnthropicClient(cfg.anthropic_api_key, cfg.anthropic_model)
    if provider == "gemini":
        if not cfg.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY not set")
        return GeminiClient(cfg.gemini_api_key, cfg.gemini_model)
    if provider == "qwen":
        if not cfg.qwen_api_key:
            raise RuntimeError("QWEN_API_KEY (or DASHSCOPE_API_KEY) not set")
        return QwenClient(cfg.qwen_api_key, cfg.qwen_model, cfg.qwen_base_url)
    raise RuntimeError(f"unknown AI_PROVIDER: {provider}")
