"""Every prompt template must render with exactly the placeholders the pipeline supplies.

Two bugs this guards against:
- combined_extraction.txt shipped with single-brace JSON examples, so str.format
  raised KeyError on every render and the combined_call strategy could never run.
- a revised w1_extraction.txt wrote API routes as "/invoices/{id}", which
  str.format reads as an {id} placeholder the pipeline never supplies, so every
  W1 call failed.

The placeholder set each prompt may use is the one the pipeline code supplies
(PIPELINE_PLACEHOLDERS, taken from core/pipeline). A prompt that asks for anything
else fails at runtime, so it fails here.
"""

import pytest

from core.llm.prompts import PromptLibrary, placeholders

CURRENT = PromptLibrary()
BASELINE = PromptLibrary("baseline_2026_09")

#: What core/pipeline passes to render() for each prompt.
PIPELINE_PLACEHOLDERS = {
    "w1_extraction": {"allowed_entity_types", "question", "answer"},
    "w2_hierarchical": {"question", "answer", "candidates"},
    "w3_pragmatic": {"question", "answer", "candidates"},
    "w4_state_nodes": {"question", "answer", "open_state_nodes"},
    "combined_extraction": {"allowed_entity_types", "question", "answer", "candidates", "open_state_nodes"},
}


@pytest.mark.parametrize("lib", [CURRENT, BASELINE], ids=["current", "baseline"])
@pytest.mark.parametrize("name", sorted(PIPELINE_PLACEHOLDERS))
def test_prompt_uses_exactly_the_supplied_placeholders(lib, name):
    if lib is BASELINE and name == "combined_extraction":
        pytest.xfail("known bug kept in the baseline snapshot: single-brace JSON examples")
    assert placeholders(lib._raw(name)) == PIPELINE_PLACEHOLDERS[name], name


def test_escaped_braces_are_not_placeholders():
    assert placeholders('Route "/items/{{id}}", value {question}') == {"question"}


@pytest.mark.parametrize("name", sorted(PIPELINE_PLACEHOLDERS))
def test_current_prompt_renders(name):
    system, user = CURRENT.render(name, **{f: f"<{f}>" for f in PIPELINE_PLACEHOLDERS[name]})
    assert system
    for f in PIPELINE_PLACEHOLDERS[name]:
        assert f"<{f}>" in system + user
