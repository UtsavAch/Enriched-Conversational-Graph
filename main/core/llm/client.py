"""LLM client abstraction.

Two implementations ship: a real Anthropic-backed client, and a scripted stub.
The stub is not a toy - it is what makes the pipeline testable without spending
money or requiring a network, and it is what lets someone clone this repo and
run the whole thing end to end before they have an API key.

The interface is deliberately narrow: one method, ``complete``. Anything more
(streaming, tool use, multi-turn) would leak provider specifics into the
pipeline, and none of the extraction calls need it.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


class LLMError(RuntimeError):
    """Raised when a completion cannot be obtained or parsed."""


@dataclass
class LLMResponse:
    """A completion plus the accounting the cost analysis needs.

    Token counts are carried through because "bounded per-turn cost" is a
    *constraint of the thesis*, not a vague aspiration. If the pipeline cannot
    report what a turn cost, that constraint cannot be checked. See
    ``core/pipeline/orchestrator.py``, which aggregates these into a per-turn
    cost record.
    """

    text: str
    input_tokens: int = 0
    output_tokens: int = 0
    model: str = ""
    latency_s: float = 0.0


@runtime_checkable
class LLMClient(Protocol):
    def complete(
        self,
        system: str,
        user: str,
        *,
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> LLMResponse: ...


# ---------------------------------------------------------------------------
# JSON extraction
# ---------------------------------------------------------------------------

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def parse_json_response(text: str) -> Any:
    """Parse a model response that is supposed to be JSON.

    Models wrap JSON in markdown fences or add a sentence of preamble even when
    told not to. Rather than making every extraction call handle that, it is
    handled once, here.

    Raises ``LLMError`` on failure so the caller's best-effort handling has a
    single exception type to catch.
    """
    candidate = text.strip()

    fenced = _FENCE_RE.search(candidate)
    if fenced:
        candidate = fenced.group(1).strip()

    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass

    # Last resort: grab the outermost {...} or [...] span.
    for opener, closer in (("{", "}"), ("[", "]")):
        start, end = candidate.find(opener), candidate.rfind(closer)
        if start != -1 and end > start:
            try:
                return json.loads(candidate[start : end + 1])
            except json.JSONDecodeError:
                continue

    raise LLMError(f"could not parse JSON from response: {text[:200]!r}")


# ---------------------------------------------------------------------------
# Implementations
# ---------------------------------------------------------------------------


class AnthropicClient:
    """Anthropic-backed client.

    The ``anthropic`` package is imported lazily so that the rest of the
    codebase - schema, persistence, evaluation metrics, the app's read-only
    endpoints - imports and runs without it installed.
    """

    def __init__(self, model: str, api_key: str | None = None, timeout_s: float = 60.0):
        try:
            import anthropic  # noqa: PLC0415
        except ImportError as exc:  # pragma: no cover
            raise LLMError(
                "the 'anthropic' package is required for AnthropicClient; "
                "install it, or use StubLLMClient for offline runs"
            ) from exc
        self.model = model
        self._client = anthropic.Anthropic(api_key=api_key, timeout=timeout_s)

    def complete(
        self, system: str, user: str, *, max_tokens: int = 1024, temperature: float = 0.0
    ) -> LLMResponse:
        import time  # noqa: PLC0415

        t0 = time.perf_counter()
        try:
            msg = self._client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
        except Exception as exc:  # pragma: no cover - network
            raise LLMError(f"completion failed: {exc}") from exc

        text = "".join(b.text for b in msg.content if getattr(b, "type", None) == "text")
        return LLMResponse(
            text=text,
            input_tokens=msg.usage.input_tokens,
            output_tokens=msg.usage.output_tokens,
            model=self.model,
            latency_s=time.perf_counter() - t0,
        )


@dataclass
class StubLLMClient:
    """Deterministic client for tests, demos, and offline development.

    Two modes, which can be combined:

    * ``scripted`` - a list of responses returned in order. Use in unit tests
      where you want to assert on how the pipeline handles a specific output.
    * ``handlers``  - a mapping from a marker string appearing in the system
      prompt to a callable ``(system, user) -> str``. Use for integration runs
      where you want plausible-shaped output for every call type.

    If neither matches, returns ``default``, which is valid-but-empty JSON. That
    means an end-to-end run with a bare ``StubLLMClient()`` produces a graph with
    nodes and no extracted structure - which is exactly the right null baseline
    to sanity-check the plumbing against.
    """

    scripted: list[str] = field(default_factory=list)
    handlers: dict[str, Any] = field(default_factory=dict)
    default: str = "{}"
    calls: list[tuple[str, str]] = field(default_factory=list)

    def complete(
        self, system: str, user: str, *, max_tokens: int = 1024, temperature: float = 0.0
    ) -> LLMResponse:
        self.calls.append((system, user))
        if self.scripted:
            text = self.scripted.pop(0)
        else:
            text = self.default
            for marker, handler in self.handlers.items():
                if marker in system:
                    text = handler(system, user)
                    break
        return LLMResponse(
            text=text,
            input_tokens=len(system.split()) + len(user.split()),
            output_tokens=len(text.split()),
            model="stub",
        )
