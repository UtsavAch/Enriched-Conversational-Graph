"""Shared plumbing for extraction steps.

Every step (W1-W5) follows the same shape: render a prompt, call the model,
parse JSON, validate against the schema, return a typed result. Putting that
shape here means each step file contains only what is specific to it - its
prompt inputs and its output type - which is what makes the steps comparable and
individually swappable.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from core.config import PipelineConfig
from core.llm.client import LLMClient, LLMError, parse_json_response
from core.llm.prompts import PromptLibrary, prompts as default_prompts

logger = logging.getLogger(__name__)


@dataclass
class CallCost:
    """What one model call cost. Aggregated per turn by the orchestrator.

    Exists because "bounded per-turn extraction cost" is a stated constraint of
    this project, and a constraint that is never measured is not a constraint.
    """

    step: str
    input_tokens: int = 0
    output_tokens: int = 0
    latency_s: float = 0.0
    failed: bool = False


@dataclass
class StepResult:
    """A step's typed output plus its cost and any failure."""

    data: Any = None
    cost: CallCost | None = None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None


class ExtractionStep(ABC):
    """Base class for one extraction call.

    Subclasses implement ``prompt_name``, ``build_inputs`` and ``parse``.
    Retries, JSON extraction, cost accounting and best-effort failure handling
    are handled here, once.
    """

    #: Name of the prompt template in the prompt library.
    prompt_name: str = ""
    #: Identifier used in logs and cost records, e.g. "W1".
    step_id: str = ""
    max_tokens: int = 1024

    def __init__(
        self,
        client: LLMClient,
        config: PipelineConfig | None = None,
        library: PromptLibrary | None = None,
    ) -> None:
        self.client = client
        self.config = config or PipelineConfig()
        self.library = library or default_prompts

    @abstractmethod
    def build_inputs(self, **kwargs: Any) -> dict[str, Any]:
        """Map call arguments onto the prompt template's placeholders."""

    @abstractmethod
    def parse(self, payload: Any, **kwargs: Any) -> Any:
        """Turn parsed JSON into typed schema objects. Raise on invalid content."""

    def run(self, **kwargs: Any) -> StepResult:
        """Execute the step, retrying transient failures.

        Returns a ``StepResult`` with ``error`` set rather than raising, when
        ``config.best_effort`` is on. Rationale, inherited from the baseline
        architecture: a failed extraction call should cost you one attribute,
        not the whole turn. The turn's question and answer are still valuable
        even if entity extraction failed.
        """
        try:
            system, user = self.library.render(self.prompt_name, **self.build_inputs(**kwargs))
        except (KeyError, Exception) as exc:  # noqa: BLE001
            return self._fail(f"prompt rendering failed: {exc}")

        last_error = ""
        for attempt in range(self.config.max_retries + 1):
            try:
                response = self.client.complete(
                    system=system,
                    user=user,
                    max_tokens=self.max_tokens,
                    temperature=self.config.extraction_temperature,
                )
                payload = parse_json_response(response.text)
                data = self.parse(payload, **kwargs)
                return StepResult(
                    data=data,
                    cost=CallCost(
                        step=self.step_id,
                        input_tokens=response.input_tokens,
                        output_tokens=response.output_tokens,
                        latency_s=response.latency_s,
                    ),
                )
            except (LLMError, ValueError, KeyError, TypeError) as exc:
                last_error = str(exc)
                logger.warning(
                    "%s attempt %d/%d failed: %s",
                    self.step_id, attempt + 1, self.config.max_retries + 1, exc,
                )
        return self._fail(last_error)

    def _fail(self, message: str) -> StepResult:
        if not self.config.best_effort:
            raise LLMError(f"{self.step_id}: {message}")
        logger.error("%s failed after retries: %s", self.step_id, message)
        return StepResult(
            data=None,
            cost=CallCost(step=self.step_id, failed=True),
            error=message,
        )


@dataclass
class TurnCost:
    """Aggregated cost of processing one turn. The bounded-cost audit record."""

    turn_id: str
    calls: list[CallCost] = field(default_factory=list)

    @property
    def n_calls(self) -> int:
        return len(self.calls)

    @property
    def n_failed(self) -> int:
        return sum(1 for c in self.calls if c.failed)

    @property
    def input_tokens(self) -> int:
        return sum(c.input_tokens for c in self.calls)

    @property
    def output_tokens(self) -> int:
        return sum(c.output_tokens for c in self.calls)

    @property
    def wall_clock_s(self) -> float:
        """Longest single call.

        The extraction calls are intended to run concurrently, so wall-clock
        time is the slowest call, not the sum. NOTE: the current orchestrator
        runs them sequentially (see its docstring) - so this property currently
        describes the *design*, not the *implementation*. That gap is a known
        open item and is flagged wherever it matters.
        """
        return max((c.latency_s for c in self.calls), default=0.0)

    @property
    def serial_s(self) -> float:
        """Sum of call latencies - what you actually pay when running serially."""
        return sum(c.latency_s for c in self.calls)

    def summary(self) -> dict[str, Any]:
        return {
            "turn_id": self.turn_id,
            "n_calls": self.n_calls,
            "n_failed": self.n_failed,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "wall_clock_s": round(self.wall_clock_s, 3),
            "serial_s": round(self.serial_s, 3),
        }
