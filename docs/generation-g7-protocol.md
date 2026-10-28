# G7: sufficient-source diagnostic versus frozen E10

Fixed on 2026-10-25 before generation. This is a targeted development diagnostic,
not a deployable retrieval policy, independent benchmark, or theoretical ceiling.

## Question and selection

Does generation still make substantive errors when a coding assistant supplies
short, source-checked passages sufficient for the requested decision or clarification?

Sixteen existing dev scenarios, both RU and EN (32 paired questions):

```
FR001 FR005 FR009 FR019 FR023 FR037 FR050 FR055
FR094 FR095 FR068 FR100 FR010 FR065 FR069 FR085
```

Ten answerable, two conditional_answer, four insufficient_information. The set
deliberately includes known G5/G6 errors plus simple controls. No out-of-scope or
test scenarios; proportions are not representative of the full dataset.

## Conditions and fixed settings

- `e10`: exact rendered context, document order and texts from FINISHED retrieval
  run `b50e71e2d39d4145ae2f7e08fd49416e`, with its original 2048 BGE-token budget.
- `sufficient`: exact substrings of the existing source-page text, manually
  reviewed against each question. Coordinates and input hashes are frozen in
  `generation-g7-context-selection.json`. Preserve governing headings, relevant
  exceptions and required consequences; omit unrelated list items where possible.
  This deliberately changes content, length and presentation together. It cannot
  isolate ranking, packing, distraction and source-completeness effects.

Both conditions use fresh Gemini 2.5 Flash-Lite answers, temperature 0,
max_output_tokens 1024, existing SYSTEM_PROMPT, legacy citations, JSON schema and
empty-context guard. No model/prompt/citation-policy tuning. Successful smoke
responses may be reused by an exact request fingerprint, explicitly recorded.
Interleave conditions and alternate their order across questions; do not select
the better of multiple answers. Temperature 0 does not guarantee determinism.

The generator receives only question, language, unchanged system prompt and
source context. References, must_include/must_not_claim, gold, review notes and
condition labels are evaluation data and never sent to the answering model.
No new search, embedding/index changes, reference edits or source edits.

## Verification and evaluation

Before full generation, validate source hashes, dev-only selection, both languages,
exact substring provenance, question equality and E10 source consistency. Run
three paired smoke questions (six answers) and read back one CHAIN/RETRIEVER/LLM
trace within a 60-second verification deadline. Reuse existing MLflow native
datasets/scorers/evaluate and Gemini tracing; disable service telemetry as in G6.

Use all five existing Ragas metrics on frozen responses with the same evaluator
as G5/G6, plus strict citation validity. Run a three-snapshot judge smoke with
trace readback before full scoring. Ragas scores are supporting diagnostics, not
a percentage of fully correct rulings. Missing/failed scores block acceptance
of summary means and are never replaced with zero.

Manually inspect all 32 pairs against source text, references and constraints.
Record substantive correctness/completeness, contradiction, unsupported extra
claims, uncertainty and citation-format failures separately. Clarification is
correct when facts are missing even though the rule is available. A bare status
is insufficient. Review is by a coding assistant, not an independent referee.
Report language-specific results, individual fixes/regressions, and small-sample
uncertainty; RU/EN of one scenario are not independent samples.

## Interpretation

If errors largely disappear, prioritize source selection/packing and distraction.
If errors remain despite checked support, investigate generation/application and
uncertainty. Do not change defaults from this privileged-context diagnostic.
Keep artifacts, raw responses, model versions, usage, code and negative results.
No test evaluation or publication is authorized by this experiment.
