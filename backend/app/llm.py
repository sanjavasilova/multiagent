import asyncio
import re
from dataclasses import dataclass

import httpx

from .config import get_settings


class LLMError(Exception):
    """Raised when the configured provider cannot produce a completion."""


@dataclass
class Completion:
    text: str
    tokens: int


def mock_answer(question: str, reference: str, role: str = "solver") -> str:
    if role == "critic":
        return (
            "Check the proposed answer step by step. Verify the calculation, definitions, "
            f"and final result; expected result: {reference}."
        )
    if role == "revision":
        return (
            f"Revised answer: {reference}. Evidence: apply the relevant rule carefully "
            "and report the result with a concise justification."
        )
    if role == "judge":
        return f"Assessment: the answer agrees with the expected result ({reference})."
    return f"Answer: {reference}. Evidence: apply the relevant rule or facts to the question."


async def complete(prompt: str, question: str = "", reference: str = "",
                   role: str = "solver", model: str | None = None) -> Completion:
    settings = get_settings()
    if settings.llm_provider.lower() in ("mock", "demo") or not settings.openai_api_key:
        text = mock_answer(question, reference, role)
        return Completion(text, max(1, len(text.split())))

    payload = {
        "model": model or settings.openai_model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are one stage in a research experiment. Do not reveal private "
                    "chain-of-thought. Return a concise conclusion, evidence, critique, "
                    "or decision appropriate to your role."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
    }
    try:
        async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
            for attempt in range(3):
                response = await client.post(
                    f"{settings.openai_base_url.rstrip('/')}/chat/completions",
                    headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                    json=payload,
                )
                if response.status_code == 429 and attempt < 2:
                    retry_after = response.headers.get("retry-after")
                    delay = float(retry_after) if retry_after and retry_after.isdigit() else 2 ** attempt
                    await asyncio.sleep(min(delay, 8))
                    continue
                response.raise_for_status()
                body = response.json()
                text = body["choices"][0]["message"]["content"]
                usage = body.get("usage") or {}
                tokens = int(usage.get("total_tokens") or max(1, len(text.split())))
                return Completion(text, tokens)
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
        raise LLMError(str(exc)) from exc
    raise LLMError("Provider returned HTTP 429 after three attempts")


def objective_match(answer: str, reference: str) -> bool:
    a = _canonical_tokens(answer)
    r = _canonical_tokens(reference)
    if not r:
        return False
    if _substring(a, r) or _substring(r, a):
        return True
    return _is_subsequence(a, r) or _is_subsequence(r, a)


def _canonical_tokens(value: str) -> list[str]:
    value = value.lower()
    for pattern, replacement in (
        (r"\b(km/h|kph)\b", " kilometers per hour "),
        (r"\bm/s\b", " meters per second "),
        (r"\bkm\b", " kilometers "),
        (r"\bkg\b", " kilograms "),
        (r"\bmph\b", " miles per hour "),
        (r"°c\b", " degrees celsius "),
        (r"°f\b", " degrees fahrenheit "),
        (r"\bdeg\.?\b", " degrees "),
    ):
        value = re.sub(pattern, replacement, value)
    value = re.sub(r"(\d+\.\d*?)(0+)(?=\D|$)", r"\1", value)
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip().split()


def _substring(a: list[str], r: list[str]) -> bool:
    return " ".join(r) in " ".join(a)


def _is_subsequence(needle: list[str], haystack: list[str]) -> bool:
    it = iter(haystack)
    return all(any(_token_eq(token, cand) for cand in it) for token in needle)


def _token_eq(a: str, b: str) -> bool:
    try:
        return float(a) == float(b)
    except ValueError:
        return a == b
