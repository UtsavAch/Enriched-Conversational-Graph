"""Prompt library: templates loaded from ``.txt`` files next to this module.

Prompts live in plain text files rather than Python string literals for three
reasons that matter for this project specifically:

1. **They are research artifacts.** Phase 3 is "iterate on prompts based on
   validation findings", and the deliverable is a changelog of what was changed
   and why. A git diff of ``w3_pragmatic.txt`` is that changelog. A diff of a
   triple-quoted string buried in a classifier is not.
2. **They are versionable.** ``PromptLibrary(version="v2")`` loads from a
   ``v2/`` subdirectory, so an ablation comparing prompt versions is a config
   change rather than a branch.
3. **Non-programmers can read them.** A supervisor reviewing the extraction
   design should not have to read Python to see what the model was asked.

Template format is ``str.format``-style ``{placeholder}``. Rendering validates
that every placeholder was supplied, because a silently-missing candidate list
produces a plausible-looking but meaningless classification.
"""

from __future__ import annotations

import os
import string
from functools import lru_cache
from pathlib import Path

_PROMPT_DIR = Path(__file__).resolve().parent
#: Every recorded prompt version, one subdirectory each (see versions/README.md).
#: The working prompts in _PROMPT_DIR must equal the latest version there.
_VERSIONS_DIR = _PROMPT_DIR / "versions"
def placeholders(template: str) -> set[str]:
    """The fields str.format will ask for.

    Uses str.format's own parser. A regex like ``\\{(\\w+)\\}`` also matches the
    inside of an escaped ``{{id}}`` and reports a placeholder that format() will
    never request, which made any literal "{id}" in a prompt unrenderable.
    """
    return {field for _, field, _, _ in string.Formatter().parse(template) if field}

#: The system/user split marker inside a prompt file. Everything before it is
#: the system prompt; everything after is the user-message template.
_SPLIT_MARKER = "=== USER ==="


class PromptNotFound(KeyError):
    pass


class PromptLibrary:
    """Loads and renders prompt templates.

    Parameters
    ----------
    version:
        Subdirectory to load from. ``None`` (default) loads the files sitting
        directly in ``core/llm/prompts/``, which are the current working
        versions.
    """

    def __init__(self, version: str | None = None) -> None:
        self.version = version
        if not version:
            self.root = _PROMPT_DIR
        elif (_VERSIONS_DIR / version).is_dir():
            self.root = _VERSIONS_DIR / version  # recorded versions: "v1", "v2", ...
        else:
            self.root = _PROMPT_DIR / version

    def available(self) -> list[str]:
        return sorted(p.stem for p in self.root.glob("*.txt"))

    @lru_cache(maxsize=64)  # noqa: B019 - library instances are long-lived
    def _raw(self, name: str) -> str:
        path = self.root / f"{name}.txt"
        if not path.exists():
            raise PromptNotFound(
                f"no prompt '{name}' in {self.root}. Available: {self.available()}"
            )
        return path.read_text(encoding="utf-8")

    def render(self, name: str, **kwargs: object) -> tuple[str, str]:
        """Return ``(system_prompt, user_prompt)`` with placeholders filled.

        Raises ``KeyError`` if the template needs a placeholder that was not
        supplied - a loud failure is much better than a prompt containing the
        literal text ``{candidate_nodes}``.
        """
        raw = self._raw(name)
        if _SPLIT_MARKER in raw:
            system_tpl, user_tpl = raw.split(_SPLIT_MARKER, 1)
        else:
            system_tpl, user_tpl = raw, ""

        required = placeholders(raw)
        missing = required - set(kwargs)
        if missing:
            raise KeyError(
                f"prompt '{name}' requires placeholders {sorted(missing)} "
                f"which were not supplied"
            )
        return system_tpl.strip().format(**kwargs), user_tpl.strip().format(**kwargs)


#: Default library instance for convenience. Construct your own for ablations.
#: GM_PROMPT_VERSION selects a recorded version (e.g. "v3", the prompts before
#: the 2026-09-27 revision) without code changes, so prompt versions can be
#: compared on the same corpus. See versions/README.md.
prompts = PromptLibrary(os.environ.get("GM_PROMPT_VERSION") or None)
