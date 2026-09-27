"""Every prompt template must render with str.format.

combined_extraction.txt shipped with single-brace JSON examples, which made
str.format raise KeyError on every render, so the combined_call strategy could
never run. This test renders each current prompt with dummy values for exactly
the placeholders it declares.
"""

import re
import string

import pytest

from core.llm.prompts import PromptLibrary

CURRENT = PromptLibrary()


def _placeholders(raw: str) -> set[str]:
    return {field for _, field, _, _ in string.Formatter().parse(raw) if field}


@pytest.mark.parametrize("name", CURRENT.available())
def test_prompt_renders(name):
    raw = CURRENT._raw(name)
    fields = _placeholders(raw)
    assert all(re.fullmatch(r"\w+", f) for f in fields), f"{name}: non-identifier placeholder in {fields}"
    system, user = CURRENT.render(name, **{f: f"<{f}>" for f in fields})
    assert system
    for f in fields:
        assert f"<{f}>" in system + user
