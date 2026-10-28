# G12: E21 context versus frozen E10/E15, Flash-Lite

Frozen before new calls, 28.10.2026. Retrieval E21 passed the predeclared gate:
CER RU55/71, EN60/71 versus E15 RU50/71, EN55/71. No prompt tuning follows.

Use the same20 dev scenarios and40 RU/EN questions as G5:
FR001 FR005 FR009 FR019 FR023 FR037 FR050 FR055 FR077 FR090 FR094 FR095
FR063 FR068 FR088 FR100 FR010 FR065 FR069 FR085.
G5 baseline generation E10=02521c443704494c95ce8128c599d8d3 and
E15=1cb1eb64b281419bb7e6954adee03bcd must be FINISHED.
Candidate retrieval174a45eee3c243e2a7bf21be9ddd7bae, same model/prompt/schema
as G5: gemini-2.5-flash-lite, SYSTEM_PROMPT, legacy citations, temp0, output1024.
Only context content/order changes. Source hashes/questions/gold unchanged.
Test untouched; this known-error dev subset is diagnostic, not representative.

Smoke3 E21 questions with trace readback, then40 fresh candidate answers.
Smoke requests are additional (maximum43 new calls), explicitly not independent
repeats to select better answers. Full answers, including the three repeated
questions, are used without choosing by quality. No successful answer resampling.
Previous G9/G10 irrelevant/partial tests are not evidence for a new Lite policy;
generator/prompt unchanged here, so controls are not regenerated. Source reliance
is checked by manual claim/source inspection; no new abstention-rate claim.

Use native MLflow evaluate and same five Ragas metrics/Gemini Lite judge. Smoke
three candidate snapshots then120 frozen normal answers × five =600 scores,
reusing exact-input cache. New local cap0.50USD: generation0.10 + judge0.40.
ApiBudget uses Lite Standard0.10 input/0.40 output+thinking USD/M, verified
28.10.2026 https://ai.google.dev/gemini-api/docs/pricing . No cap increases.
Failed calls retain allowance. No proxy, no new dependency or model download.
MLFLOW_DISABLE_TELEMETRY=true and both MLFLOW_GENAI_EVAL_MAX_WORKERS=1 and
MLFLOW_GENAI_EVAL_MAX_SCORER_WORKERS=1 set before imports. Cache successes persist.

Report all five metrics RU/EN, all statuses, strict citation validity, cost,
generation latency excluding retrieval; compare E21 against both E10 and E15.
Paired bootstrap2000 seed42 over20 situations, common resamples RU/EN.
Read back every output/expectation/source, finite scores and native means.
Review all40 new answers against reference and supplied context; pay attention
to E21 regression FR050 EN and E15→E21 gains FR009/010/068/094 RU, FR005/069/095 EN.
Do not repair sources/gold/scores or filter inconvenient outcomes after execution.
Keep E21 as candidate until answers support promotion; no default change here.
