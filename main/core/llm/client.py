"""LLM client abstraction.

Two implementations ship: a real Anthropic-backed client, and a scripted stub.
The stub is not a toy - it is what makes the pipeline testable without spending
money or requiring a network, and it is what lets someone clone this repo and
run the whole thing end to end before they have an API key.

The interface is deliberately narrow: one method, ``complete``. Anything more
(streaming, tool use, multi-turn) would leak provider specifics into the
pipeline, and none of the extraction calls need it.

One deliberate, narrow exception: ``complete_stream`` (``StreamingLLMClient``
below). Live chat needs the answer to appear as it's generated, not all at
once - that is a UI requirement, not an extraction one, so it is kept as a
second, optional capability rather than changing ``complete`` or anything
extraction calls use. See ``TurnPipeline._generate_answer``, its only caller.
"""

from __future__ import annotations

import json
import logging
import re
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Iterator, Protocol, runtime_checkable

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


@runtime_checkable
class StreamingCompletion(Protocol):
    """One streamed completion: iterate for text deltas, then call ``final()``.

    ``final()`` is only valid once the iterator has been fully consumed - it
    returns exactly what ``complete()`` would have, for the same cost
    accounting. Never yields anything but final-answer text: no provider here
    is asked to think out loud, and the one client (Anthropic) capable of it
    is wired to a helper that structurally cannot surface a thinking block -
    see ``_AnthropicStream``.
    """

    def __iter__(self) -> Iterator[str]: ...
    def final(self) -> LLMResponse: ...


@runtime_checkable
class StreamingLLMClient(Protocol):
    """Optional second capability - see the module docstring for why this
    exists as a separate protocol rather than a change to ``complete``."""

    def complete_stream(
        self,
        system: str,
        user: str,
        *,
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> StreamingCompletion: ...


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

    def complete_stream(
        self, system: str, user: str, *, max_tokens: int = 1024, temperature: float = 0.0
    ) -> StreamingCompletion:
        return _AnthropicStream(self._client, self.model, system, user, max_tokens, temperature)


class _AnthropicStream:
    """Backs ``AnthropicClient.complete_stream``. One-shot: iterate once, then
    call ``final()``.
    """

    def __init__(
        self, client: Any, model: str, system: str, user: str, max_tokens: int, temperature: float
    ) -> None:
        self._client = client
        self._model = model
        self._system = system
        self._user = user
        self._max_tokens = max_tokens
        self._temperature = temperature
        self._final: LLMResponse | None = None

    def __iter__(self) -> Iterator[str]:
        import time  # noqa: PLC0415

        t0 = time.perf_counter()
        try:
            with self._client.messages.stream(
                model=self._model,
                max_tokens=self._max_tokens,
                temperature=self._temperature,
                system=self._system,
                messages=[{"role": "user", "content": self._user}],
            ) as stream:
                # `text_stream` is Anthropic's own helper: it only ever surfaces
                # text_delta content. A thinking/reasoning block (if extended
                # thinking were ever enabled here, which it is not) cannot come
                # through this - the safeguard against exposing chain-of-thought
                # is the SDK's own behaviour, not something bolted on after.
                yield from stream.text_stream
                msg = stream.get_final_message()
        except Exception as exc:  # pragma: no cover - network
            raise LLMError(f"completion failed: {exc}") from exc

        text = "".join(b.text for b in msg.content if getattr(b, "type", None) == "text")
        self._final = LLMResponse(
            text=text,
            input_tokens=msg.usage.input_tokens,
            output_tokens=msg.usage.output_tokens,
            model=self._model,
            latency_s=time.perf_counter() - t0,
        )

    def final(self) -> LLMResponse:
        if self._final is None:
            raise LLMError("final() called before the stream was fully consumed")
        return self._final


class OpenAICompatClient:
    """OpenAI-compatible client for local SLMs (Ollama, vLLM, LM Studio, etc.).

    Any endpoint that speaks the OpenAI chat-completions API can be used here:
    set GM_OPENAI_BASE_URL to the server root (e.g. ``http://localhost:11434/v1``
    for Ollama) and GM_OPENAI_API_KEY if the server requires one.

    This is the primary path for running extraction with a local SLM instead
    of Anthropic, which is required for the Phase 4 multi-provider comparison.
    Section 5.2 of the Phase 1-2 report.
    """

    def __init__(
        self,
        model: str,
        base_url: str,
        api_key: str = "ollama",
        timeout_s: float = 60.0,
    ):
        try:
            from openai import OpenAI  # noqa: PLC0415
        except ImportError as exc:
            raise LLMError(
                "the 'openai' package is required for OpenAICompatClient; "
                "install it with: pip install openai"
            ) from exc
        self.model = model
        self._client = OpenAI(base_url=base_url, api_key=api_key, timeout=timeout_s)

    def complete(
        self, system: str, user: str, *, max_tokens: int = 1024, temperature: float = 0.0
    ) -> LLMResponse:
        import time  # noqa: PLC0415

        t0 = time.perf_counter()
        try:
            resp = self._client.chat.completions.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )
        except Exception as exc:
            raise LLMError(f"completion failed: {exc}") from exc

        text = resp.choices[0].message.content or ""
        usage = resp.usage
        return LLMResponse(
            text=text,
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
            model=self.model,
            latency_s=time.perf_counter() - t0,
        )

    def complete_stream(
        self, system: str, user: str, *, max_tokens: int = 1024, temperature: float = 0.0
    ) -> StreamingCompletion:
        return _OpenAICompatStream(self._client, self.model, system, user, max_tokens, temperature)


class _OpenAICompatStream:
    """Backs ``OpenAICompatClient.complete_stream``. One-shot: iterate once,
    then call ``final()``.

    Does not request usage accounting during streaming: `stream_options` for
    a final usage-only chunk is an OpenAI API extension that not every
    OpenAI-compatible server (Ollama, vLLM, LM Studio, ...) implements the
    same way, and this client exists specifically to talk to that whole
    zoo of servers. Rather than risk breaking streaming for one to get token
    counts, ``final()`` reports 0/0 - the non-streaming ``complete()`` path
    (extraction, batch ingestion) remains fully accurate either way.
    """

    def __init__(
        self, client: Any, model: str, system: str, user: str, max_tokens: int, temperature: float
    ) -> None:
        self._client = client
        self._model = model
        self._system = system
        self._user = user
        self._max_tokens = max_tokens
        self._temperature = temperature
        self._final: LLMResponse | None = None

    def __iter__(self) -> Iterator[str]:
        import time  # noqa: PLC0415

        t0 = time.perf_counter()
        chunks: list[str] = []
        try:
            stream = self._client.chat.completions.create(
                model=self._model,
                max_tokens=self._max_tokens,
                temperature=self._temperature,
                messages=[
                    {"role": "system", "content": self._system},
                    {"role": "user", "content": self._user},
                ],
                stream=True,
            )
            for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta.content
                if delta:
                    chunks.append(delta)
                    yield delta
        except Exception as exc:
            raise LLMError(f"completion failed: {exc}") from exc

        self._final = LLMResponse(
            text="".join(chunks),
            model=self._model,
            latency_s=time.perf_counter() - t0,
        )

    def final(self) -> LLMResponse:
        if self._final is None:
            raise LLMError("final() called before the stream was fully consumed")
        return self._final


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

    def complete_stream(
        self, system: str, user: str, *, max_tokens: int = 1024, temperature: float = 0.0
    ) -> StreamingCompletion:
        """Fakes streaming by word-chunking whatever ``complete`` would have
        returned - offline dev/demo (``npm run dev`` with no API key) should
        still show the live-typing effect, not silently fall back to a single
        blob."""
        response = self.complete(system, user, max_tokens=max_tokens, temperature=temperature)
        return _StubStream(response)


@dataclass
class _StubStream:
    _response: LLMResponse

    def __iter__(self) -> Iterator[str]:
        words = self._response.text.split(" ")
        for i, word in enumerate(words):
            yield word if i == len(words) - 1 else word + " "

    def final(self) -> LLMResponse:
        return self._response


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------

#: Pulls a provider-suggested wait time out of an error message. Both Groq
#: ("Please try again in 10.88s") and Gemini ("Please retry in 9.25s" /
#: "'retryDelay': '48s'") embed this as plain text once the SDK exception has
#: been wrapped into a plain LLMError string - regex is the pragmatic way to
#: recover it without depending on either provider's specific exception shape.
_RETRY_DELAY_RE = re.compile(
    r"(?:retrydelay['\"]?\s*[:=]?\s*['\"]?|try again in|retry in)\s*(\d+(?:\.\d+)?)\s*s",
    re.IGNORECASE,
)


def _parse_retry_delay(message: str) -> float | None:
    m = _RETRY_DELAY_RE.search(message)
    return float(m.group(1)) if m else None


class RateLimitedClient:
    """Wraps any ``LLMClient`` with proactive RPM/TPM throttling plus
    provider-aware backoff on 429s.

    Motivated by hitting real free-tier limits from two different providers
    within the same session: Groq caps by tokens/minute (org-wide, not
    per-model), Gemini's free tier caps by requests/minute (per-model). Both
    got exhausted within the first few turns of ``TurnPipeline``'s three-wave
    concurrent extraction design (5 calls fired per turn), and the pipeline's
    own short fixed retry backoff (``core/pipeline/base.py``) gave up faster
    than these providers actually asked callers to wait - so calls failed
    outright rather than merely being slow.

    One instance is shared across every step in a ``TurnPipeline`` (W1-W5,
    combined - see ``TurnPipeline.__init__``), so the lock here is what
    actually paces the orchestrator's concurrent wave dispatch. Nothing in
    ``core/pipeline/orchestrator.py`` needs to change for this to work
    correctly under concurrency - throttling lives at the client boundary,
    not the call-scheduling boundary.

    Token counts are *estimated* pre-call (chars/4, a rough English
    heuristic) since the exact count isn't known until the response returns.
    This is deliberately conservative pacing, not exact accounting - it will
    not perfectly match a provider's own counters (their window boundaries,
    other traffic on the same key, etc. are invisible here), which is why the
    reactive backoff on an actual 429 still matters even with proactive
    throttling on.
    """

    def __init__(
        self,
        inner: LLMClient,
        requests_per_minute: int | None = None,
        tokens_per_minute: int | None = None,
        max_wait_retries: int = 2,
    ) -> None:
        self._inner = inner
        self._rpm = requests_per_minute
        self._tpm = tokens_per_minute
        self._max_wait_retries = max_wait_retries
        self._lock = threading.Lock()
        self._request_times: deque[float] = deque()
        self._token_events: deque[tuple[float, int]] = deque()

    @staticmethod
    def _estimate_tokens(system: str, user: str) -> int:
        return max(1, (len(system) + len(user)) // 4)

    def _throttle(self, estimated_tokens: int) -> None:
        """Block until a call is safe to make under the configured budgets.

        Sliding 60s window rather than a fixed per-minute bucket, so the
        limit is enforced continuously (a burst right at a minute boundary
        can't slip two windows' worth of calls through back to back).
        """
        while True:
            with self._lock:
                now = time.monotonic()
                cutoff = now - 60.0
                while self._request_times and self._request_times[0] < cutoff:
                    self._request_times.popleft()
                while self._token_events and self._token_events[0][0] < cutoff:
                    self._token_events.popleft()

                wait = 0.0
                if self._rpm is not None and len(self._request_times) >= self._rpm:
                    wait = max(wait, self._request_times[0] + 60.0 - now)
                if self._tpm is not None:
                    used = sum(t for _, t in self._token_events)
                    if used + estimated_tokens > self._tpm and self._token_events:
                        wait = max(wait, self._token_events[0][0] + 60.0 - now)

                if wait <= 0:
                    self._request_times.append(now)
                    self._token_events.append((now, estimated_tokens))
                    return
            time.sleep(min(max(wait, 0.0), 60.0) + 0.05)

    def complete(
        self, system: str, user: str, *, max_tokens: int = 1024, temperature: float = 0.0
    ) -> LLMResponse:
        estimated = self._estimate_tokens(system, user)
        attempts = 0
        while True:
            self._throttle(estimated)
            try:
                return self._inner.complete(
                    system, user, max_tokens=max_tokens, temperature=temperature
                )
            except LLMError as exc:
                delay = _parse_retry_delay(str(exc))
                attempts += 1
                if delay is None or attempts > self._max_wait_retries:
                    raise
                logger.warning(
                    "rate limited, provider asked for %.1fs - waiting (attempt %d/%d)",
                    delay, attempts, self._max_wait_retries,
                )
                time.sleep(delay + 0.5)
