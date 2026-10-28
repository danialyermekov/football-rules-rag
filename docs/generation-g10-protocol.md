# G10: Argon against both frozen G9 baselines

Frozen before task-specific Argon calls, 2026-10-26. A prior connectivity probe
returned OK (36 input/5 output tokens, estimated USD0.000122); it is not a sample
in this experiment. Use existing direct Gemini credential; no proxy or new keys.

## Fixed comparison

All78 G9 contexts:16 dev scenarios × RU/EN × E10/sufficient =64 normal,
plus8 irrelevant and6 partial controls. Sources: FINISHED G9 generation
1717c12dcac84a11a76a6de9039a27ee, with frozen G7/G8 origins. Reuse all156 G9
baseline snapshots (Flash3.8 and Lite). Add78 Argon outputs, total234 snapshots:
192 normal and42 controls. Verify questions, expectations, source hashes,
documents and context text. Gold/references/condition labels never reach the LLM.
Test stays untouched. No prompt, retriever, source-ID or evidence-check changes.

Argon recipe: gemini-4-argon, LOW thinking, max_output_tokens32768 including
thinking. Omit temperature (Google says sampling parameters are ignored).
Baseline Flash3.8 is LOW/output2048/temp0; Lite output1024/temp0/default thinking.
This compares deployable model/configuration recipes, not an isolated model effect
or the maximum reasoning capability of Argon. Do not silently raise thinking.

The large ceiling follows Google's migration guidance to avoid truncating
reasoning; it is a ceiling, not a target answer length. SYSTEM_PROMPT still asks
for concise answers. HTTP timeout900s, attempts1; no retries for answer selection.
Persist successful responses/cache immediately. At most one recovery for failed
calls with unchanged settings, only if the original spending caps permit it.
Record failed/malformed outputs; never include incomplete-run averages as final.

## Budget

Total local ceiling for new G10 requests USD1.50: generation1.25 + judge0.25.
Argon Standard input2/output+thinking10 USD/M through2026-11-30; judge Lite
input0.10/output+thinking0.40 USD/M. Verified official prices 2026-10-26:
https://ai.google.dev/gemini-api/docs/pricing
Configuration guidance: https://ai.google.dev/gemini-api/docs/latest-model?hl=en

Use ApiBudget and separate persistent G10 ledgers. Reserve UTF-8 input allowance
plus system/schema margin and full32768 output ceiling before each generation
request; settle using reported usage. Failed requests retain reservation. Ignore
cache discounts conservatively. Never increase the cap to complete the run.
If no allowance remains, stop new API calls and report the incomplete scope.
This is a local single-process guard/estimate, not cloud billing enforcement or
verification of the user's approximate USD9 balance.

Run generation and judge sequentially (MLFLOW_GENAI_EVAL_MAX_WORKERS=1 set before
Python import) to avoid concurrent aggregate reservations. Do not run both full
stages concurrently. Existing evaluator metric configuration and successful cache
remain unchanged; no stronger paid judge in this experiment.

## Smoke, evaluation and review

Same three smoke contexts as G9: FR005 RU E10, FR095 EN E10, FR069 RU sufficient.
Nine snapshots including both frozen baselines. Verify valid schema, usage,
completion and one new CHAIN/RETRIEVER/LLM trace readback within60s. Confirm an
actual completion before starting full generation. Successful smoke reused by
exact request fingerprint. No edits to instructions after seeing answers.

Three-snapshot Ragas smoke on Argon outputs, then all192 normal snapshots × five
metrics =960 assessments. Controls evaluated separately from normal references.
Reuse baseline judgments, not independent repeated measurements. Inspect error,
undefined and missing states explicitly. CP/CR values/cache keys must match for
all three same-context model pairs. Report both languages and contexts separately,
all-case status/citation counts, paired deltas and scenario bootstrap2000/seed42.

Review all64 Argon normal answers against both frozen answers and14 control
answers for rule applicability, restart, sanction actor/completeness, uncertainty,
unsupported claims and contradictions. The coding assistant is not an independent
referee or blinded expert. Keep raw judge results even when manual review differs;
do not rescore successful judgments to improve averages. Model names can be hidden
in a review artifact, but no claim of genuine blinding after prior G9 exposure.

Default stays unchanged during this experiment. Promotion needs substantive
improvement, controls without material new failures, and acceptable cost/latency;
an aggregate Ragas increase alone is insufficient. Log all reports, code, sources,
usage, failed runs and limits in MLflow; do not publish or commit automatically.

## Commands

Set PYTHONIOENCODING=utf-8, MLFLOW_DISABLE_TELEMETRY=true and
MLFLOW_GENAI_EVAL_MAX_WORKERS=1 in PowerShell, then use the existing environment:

    uv run --no-sync python scripts/evaluate_flash38.py --argon --prepare-only
    uv run --no-sync python scripts/evaluate_flash38.py --argon --smoke --verify-trace
    uv run --no-sync python scripts/evaluate_flash38.py --argon

Evaluate the resulting FINISHED generation run with evaluate_ragas_snapshots.py,
--factual-correctness --max-new-judge-usd 0.25
--budget-ledger tmp/g10/judge-ledger.jsonl. The judge smoke must select candidate
rows (not the first baseline rows) while preserving the scorer implementation.

## Operational note after execution

MLflow 3.17 has a separate scorer pool: future budgeted evaluations must also
set MLFLOW_GENAI_EVAL_MAX_SCORER_WORKERS=1. The original setting above only
serialized rows. G10 recovery reused 956 successful judgments and computed four
previously blocked by aggregate reservations, without raising the spending cap.
This note was added after execution; it was not part of the frozen protocol.
