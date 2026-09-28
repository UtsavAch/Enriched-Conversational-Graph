# Prompt versions

Every recorded version of the extraction prompts, one folder each. The working
prompts in `core/llm/prompts/*.txt` are always identical to the **latest** version
here (`tests/test_prompts.py` fails otherwise).

Select a version without code changes:

```
GM_PROMPT_VERSION=v3 python -m scripts.ingest_conversation ...
```

or in code: `PromptLibrary("v3")`.

| Version | Date | Source | Summary | Evaluation runs that used it |
|---|---|---|---|---|
| [v1](v1/) | 2026-09-06 | commit `47bed79` | Initial W1-W5 and combined prompts. W1 has no entity-type vocabulary yet. | — |
| [v2](v2/) | 2026-09-08 | commit `78bf461` | Consistency pass over W1-W4 and combined. **Introduces the combined-prompt brace bug** (`combined_call` cannot render from here until v4). | — |
| [v3](v3/) | 2026-09-17 | commit `8540c81` | Phase 3 version: configurable entity-type vocabulary (`{allowed_entity_types}`), `propose:` types, W2 subcase/supercase/same_level examples. | `rest_api_gemma4`, `rest_api_qwen3`, `hpc_support_gemma4`, `rest_api_gemini_promptv2/v3` (see note); held-out baseline `<corpus>_gemma4_v3` |
| [v4](v4/) | 2026-09-27 | commits `8ce261e`, `f3f4990` | Revision from gemma4 error analysis: canonical entity names, immediate-parent subcase, citation rule for pragmatic edges, contradicts/revises examples, stricter state-node creation, examples no longer copied from `rest_api`; combined-prompt brace bug fixed. Details: [../CHANGELOG.md](../CHANGELOG.md). | `hpc_support_gemma4_p2`, `rest_api_gemma4_p2`, `rest_api_gemma4_p3` |
| [v5](v5/) | 2026-09-27 | this branch | W4 (and combined): looser constraint definition - limits, project rules and must/must-not requirements all count; decision vs constraint distinction with two new examples. W1-W3 unchanged from v4. | W4-only replay on `rest_api`, `hpc_support` (see CHANGELOG); held-out comparison with v3 on six testbeds, `<corpus>_gemma4_v5` (`evaluation/reports/prompt_v5_heldout_evaluation_2026-09-28.md`) |

Note on the Gemini `promptv2` / `promptv3` reports (2026-09-16/17): they came from
W2 iterations made between v2 and v3 that were not committed separately, so git
cannot reproduce them exactly; v3 is the state they converged to.

## Adding a version

1. Edit the working prompts in `core/llm/prompts/`.
2. Copy all `*.txt` into a new folder here (`v5/`, ...).
3. Add a row above and an entry in `../CHANGELOG.md` with the evidence behind the change.
