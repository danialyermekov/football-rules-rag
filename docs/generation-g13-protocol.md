# G13: bounded E21 three-model pilot

Frozen before calls, 28.10.2026. Direct Gemini only. User requested retaining
API money for further experiments. Local combined ceiling USD0.85, not verified
Google balance: Argon generation0.50, Flash3.8 generation0.10, Lite judge0.25.
Standard prices rechecked https://ai.google.dev/gemini-api/docs/pricing :
Argon2/10 USD/M input/output+thinking, Flash0.75/3.75, Lite0.10/0.40.
No cap increases; stop if allowance exhausted. Preserve failed-call reservations.

## Before generation: evaluation diagnosis

Inspect frozen G12 scores and sources for six preselected cases:
FR005 RU, FR009 RU, FR010 RU, FR050 EN, FR094 EN, FR095 EN.
Record disagreements/alternative source support without rewriting gold, references,
or cached successful judgments. This is a coding-assistant pilot review, not
independent expert calibration or a new validated metric. Keep all five Ragas
metrics unchanged during G13 so the model comparison remains interpretable.

## Frozen comparison

Ten known-error/control dev situations, both languages:
FR001 FR005 FR009 FR010 FR050 FR065 FR069 FR085 FR094 FR095.
Twenty normal inputs use exact E21 contexts and Lite baseline from FINISHED G12
7644cccdb9634aa0a7a13896bb844a8c. Same SYSTEM_PROMPT and Answer schema.
Four controls from FINISHED G8 723b81f1dd964c358b2ed399b6763231:
FR005 RU/EN partial; FR009 RU/EN irrelevant. Reuse four baseline Lite answers.
Generate24 answers per new model,48 total; total72 snapshots with24 reused Lite.
Normal60 snapshots enter Ragas; controls12 assessed separately.

Flash recipe gemini-3.8-flash LOW thinking/temp0/output2048;
Argon gemini-4-argon LOW/no temperature/output32768, as G9/G10.
This compares model/config recipes, not the isolated effect of model size.
HTTP attempts1; full output ceiling reserved before request. No hidden retries.
No question rewriting, prompt changes, retrieval changes, or example-specific
instructions. Gold/reference/control labels never reach the generator.
Test untouched. Diagnostic subset is selected using known dev errors, not a new
representative benchmark. No claim that this pilot proves general superiority.

## Procedure and decision

Prepare-only validates frozen sources, dev questions, hashes and baseline pairs.
Smoke three normal contexts: FR005 RU, FR094 EN, FR069 EN. Nine snapshots,
six new calls. Verify schema/usage and one new CHAIN/RETRIEVER/LLM trace.
Reuse successful smoke answers by exact request fingerprints in full generation.
At most one recovery for missing/failed answers if original caps permit;
never regenerate successful answers to select better output.
Run all processes sequentially, especially when sharing ledgers:
MLFLOW_DISABLE_TELEMETRY=true; MLFLOW_GENAI_EVAL_MAX_WORKERS=1;
MLFLOW_GENAI_EVAL_MAX_SCORER_WORKERS=1 before Python imports.

Native MLflow datasets/evaluate/scorers/traces and existing Ragas snapshot scorer.
Judge smoke3 candidate snapshots; then60 normal x five metrics=300 scores.
Reuse exact-input judgments. Report RU/EN separately, paired deltas against Lite
and Flash, bootstrap2000 seed42 over10 scenarios with shared RU/EN resamples.
Verify complete finite scores, frozen snapshots and native means. CP/CR must
match values/cache keys across model pairs sharing exact sources.
Review all40 new normal answers and8 controls for applicability, sanctions,
contradictions, missing facts, unsupported claims and language.
No new full-system Correct Abstention Rate from four selected controls.
Manual reviewer is coding assistant, not independent referee or blind review.
Keep defaults unchanged; choose only whether a candidate merits broader dev
testing. Cost and latency reported with scope and unknown billing limits.


## Execution deviation: cap respected

Argon completed23/24, Flash24/24. FR069 RU Argon blocked before API:
usage0.14556 + conservative reservation0.36381 =0.50937 > cap0.50.
No cap increase or smaller-output retry. Failed full generation run
5c321249de7045bcb0c37b4487efe74a retains71 successful snapshots.
A separate no-API native snapshot-recovery run4f883b225a9e46d68da5c0898f8244a2
is FINISHED with explicit partial-budget-stopped tag; this does not make the
original generation complete. All59 saved normal responses and12 controls
retained. For comparable numeric groups remove FR069 RU from all three models:
57 normal snapshots,9 RU/10 EN questions,285 scores instead of300. Full Flash
FR069 RU and Lite baseline still preserved and reviewed qualitatively.
Matched subset is post-budget complete-case analysis, not the predeclared full
pilot and not a representative benchmark; missingness depends on input cost.
Bootstrap uses9 or10 indices per language, shared across model pairs within
language; RU/EN index resampling differs because sample sizes differ.
