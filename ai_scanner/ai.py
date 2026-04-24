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
    "Review the HTML content and screenshot provided. Check for:\n"
    "- Fake login pages mimicking banks/services\n"
    "- Phishing attempts asking for credentials, OTP, or credit cards\n"
    "- Fake investment or crypto schemes with unrealistic promises\n"
    "- Urgency tactics and countdown timers\n"
    "- Typosquatting or brand impersonation\n"
    "- Suspicious redirects or obfuscated scripts\n"
    "- Prize/lottery scams\n\n"
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
    raise RuntimeError(f"unknown AI_PROVIDER: {provider}")
