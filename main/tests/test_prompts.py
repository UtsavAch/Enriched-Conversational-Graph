"""Prompt templates: render correctly, and every version is recorded.

Bugs this guards against:
- combined_extraction.txt (v2, v3) used single-brace JSON examples, so str.format
  raised KeyError on every render and the combined_call strategy could never run.
- a draft of v4's w1_extraction.txt wrote API routes as "/invoices/{id}", which
  str.format reads as an {id} placeholder the pipeline never supplies, so every
  W1 call failed.
- prompt edits made without recording a new version (the git history of this
  folder has iterations that were never committed on their own).
"""

import re
from pathlib import Path

import pytest

from core.llm.prompts import PromptLibrary, placeholders

PROMPT_DIR = Path(PromptLibrary().root)
VERSIONS = sorted((p.name for p in (PROMPT_DIR / "versions").iterdir() if p.is_dir()),
                  key=lambda v: int(re.sub(r"\D", "", v)))
LATEST = VERSIONS[-1]
CURRENT = PromptLibrary()

#: What core/pipeline passes to render() for each prompt (core/pipeline/steps.py).
PIPELINE_PLACEHOLDERS = {
    "w1_extraction": {"allowed_entity_types", "question", "answer"},
    "w2_hierarchical": {"question", "answer", "candidates"},
    "w3_pragmatic": {"question", "answer", "candidates"},
    "w4_state_nodes": {"question", "answer", "open_state_nodes"},
    "combined_extraction": {"allowed_entity_types", "question", "answer", "candidates", "open_state_nodes"},
}

#: Recorded bugs in historical versions, kept as they were.
KNOWN_BROKEN = {("v2", "combined_extraction"), ("v3", "combined_extraction")}


def test_versions_are_recorded():
    assert VERSIONS[:4] == ["v1", "v2", "v3", "v4"]


def test_working_prompts_equal_latest_version():
    """Editing a prompt without recording it as a new version fails here."""
    latest = PROMPT_DIR / "versions" / LATEST
    working = {p.name: p.read_bytes() for p in PROMPT_DIR.glob("*.txt")}
    recorded = {p.name: p.read_bytes() for p in latest.glob("*.txt")}
    changed = sorted(n for n in working.keys() | recorded.keys() if working.get(n) != recorded.get(n))
    assert not changed, (
        f"working prompts differ from versions/{LATEST}: {changed}. Copy them into a new "
        f"versions/v{int(LATEST[1:]) + 1}/ folder and add a CHANGELOG entry."
    )


@pytest.mark.parametrize("version", VERSIONS)
@pytest.mark.parametrize("name", sorted(PIPELINE_PLACEHOLDERS))
def test_version_only_asks_for_supplied_placeholders(version, name):
    lib = PromptLibrary(version)
    if not (lib.root / f"{name}.txt").exists():
        pytest.skip(f"{version} has no {name}")
    if (version, name) in KNOWN_BROKEN:
        pytest.xfail("known bug kept in this recorded version: single-brace JSON examples")
    # Older versions may ask for fewer inputs (extra kwargs are ignored by format).
    assert placeholders(lib._raw(name)) <= PIPELINE_PLACEHOLDERS[name]


@pytest.mark.parametrize("name", sorted(PIPELINE_PLACEHOLDERS))
def test_current_prompt_uses_every_supplied_placeholder_and_renders(name):
    assert placeholders(CURRENT._raw(name)) == PIPELINE_PLACEHOLDERS[name]
    system, user = CURRENT.render(name, **{f: f"<{f}>" for f in PIPELINE_PLACEHOLDERS[name]})
    for f in PIPELINE_PLACEHOLDERS[name]:
        assert f"<{f}>" in system + user


def test_escaped_braces_are_not_placeholders():
    assert placeholders('Route "/items/{{id}}", value {question}') == {"question"}
