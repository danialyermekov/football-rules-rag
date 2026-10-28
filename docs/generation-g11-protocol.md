# G11: unknown incident facts, one prompt change

Frozen before new model calls, 2026-10-28. Direct Gemini only. No proxy.

## Hypothesis and fixed inputs

Append one general clarification instruction to SYSTEM_PROMPT: distinguish
stated facts from unknown conditions; ask a direct question before any ruling
when the missing fact changes the decision. Missing source information remains
insufficient_context. Do not introduce example-specific rules or gold labels.

Use gemini-3.8-flash, LOW thinking, temperature 0, output ceiling 2048, as in G9.
Keep Answer schema, source labels, question language and frozen context unchanged.
Reuse all 78 Flash outputs from FINISHED G9 run
1717c12dcac84a11a76a6de9039a27ee, not its Lite outputs.
Generate 78 candidate outputs: 16 dev situations x RU/EN x E10/sufficient =64
normal, plus eight irrelevant and six partial controls. Total 156 snapshots.
Sufficient contexts are hand-selected diagnostics, not an improved retriever.
Test is untouched. This repeatedly inspected dev subset is not a fresh benchmark.

## Execution and spending

Reuse scripts/evaluate_flash38.py --clarify and the existing native MLflow
datasets, evaluate, tracing and exact-input caches. Prepare-only validates dev
questions, source hashes, baseline outputs and matching documents. Smoke on
FR005 RU E10, FR095 EN E10, FR069 RU sufficient, read back one new trace, then
complete the run without changing the prompt. Reuse successful smoke answers.
At most one recovery for failed calls with unchanged inputs; retain failed runs
and reservations. No resampling successful answers or judgments.

Local ceiling USD0.75: generation0.35 + judge0.40, persistent separate ledgers.
Standard rates rechecked 2026-10-28 at
https://ai.google.dev/gemini-api/docs/pricing : Flash3.8 input0.75/output+thinking
3.75 USD/M through2026-12-31. Judge uses existing Lite0.10/0.40 USD/M.
Estimates and guards are not a cloud billing balance. No cap increases.
Set MLFLOW_DISABLE_TELEMETRY=true, MLFLOW_GENAI_EVAL_MAX_WORKERS=1 and
MLFLOW_GENAI_EVAL_MAX_SCORER_WORKERS=1 before importing MLflow.

## Evaluation and decision

Use unchanged Ragas Context Precision, Context Recall, Faithfulness, Answer
Relevancy and Factual Correctness with Gemini2.5FlashLite judge. Three candidate
snapshots smoke, then all128 normal snapshots x five =640 finite assessments.
Reuse prior exact-input judgments; CP/CR cache keys and values must match pairs.
Read back complete outputs, expectations and native means before reporting.
Report each language and each context separately, paired deltas and bootstrap
2000/seed42 over the16 scenario IDs, with the same resamples across languages.

Review all64 candidate normal answers and14 controls against frozen baseline.
Focus on FR010/063/065/068/069/085: whether decisive unknowns are asked about,
whether the explanation assumes an outcome, and whether supported branches are
correct. Also check unnecessary clarification in the ten answerable cases,
unsupported claims, sanctions, contradictions and citation validity. Status alone
is not success; a clarification containing an incorrect rule remains defective.
Manual review is by coding assistant, not independent referee or blind review.

Promote only if substantive ambiguity handling improves without new material
control or ordinary-answer regressions; metric growth alone is insufficient.
Keep raw scores even when manual review disagrees. Default remains unchanged
during this experiment. Save results, review, usage and comparison artifacts.
