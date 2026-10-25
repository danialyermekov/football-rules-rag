# G6: focused generation on frozen E10 contexts

Fixed before new API calls, 2026-10-25. Development prompt experiment using known
G5 errors; no independent generalization claim or test-split access.

Only generator system prompt changes: SYSTEM_PROMPT versus FOCUSED_PROMPT.
The latter requests a direct decision, brief relevant justification, preserved
conditions, no unrelated sanctions, and separate handling of missing incident
facts versus missing rule evidence. One candidate only, no metric-driven edits.
Gemini 2.5 Flash-Lite, temperature0, max_output_tokens1024, JSON schema, legacy
citations and empty-context guard remain fixed. No retries/answer selection.

Normal questions: exactly G5's 20 scenarios in both languages, 40 answers:

```
FR001 FR005 FR009 FR019 FR023 FR037 FR050 FR055 FR077 FR090 FR094 FR095
FR063 FR068 FR088 FR100 FR010 FR065 FR069 FR085
```

Frozen retrieval source: E10 `b50e71e2d39d4145ae2f7e08fd49416e`.
Saved baseline generation: G5 `02521c443704494c95ce8128c599d8d3`.
Source questions, references, ordered context documents, and rendered context
must match G5. Baseline answers are reused, not new independent model samples.

Score 80 frozen baseline/candidate snapshots using unchanged G5 JSON Schema
Gemini judge, Ragas0.4.3 and five metrics: Context Precision with reference,
Context Recall, Faithfulness, Answer Relevancy (strictness3 + pinned BGE-M3),
Factual Correctness default F1. CP/CR must remain identical, including cache keys.
Report all-case RU/EN means, paired deltas and bootstrap intervals, valid counts,
answered-only diagnostics, statuses, strict citation validity, latency and usage.
Inspect all paired answers for contradictions, missing material conditions and
unnecessary assertions; shorter answers alone are not success.

Negative context control: FR001, FR005, FR009, FR055 in RU/EN (8 cases), both
prompts generated fresh (16 answers). Contexts copied exactly from audited G1
`13bca0d6da334de58f200846cac3fbbf` preparation.json. EN PDF49 is technical-area
conduct; RU PDF48 is flagposts/technical area. Full texts manually reread before
generation: neither supplies the target decisions. Documents retain language,
edition, labels and text. Different RU/EN distractor lengths preclude attributing
language differences solely to generator ability. Stored BGE token count is null
for interventions because no budget packing is rerun. Both prompts see identical
intervention texts. These short obvious distractors are a narrow stress test,
not evidence of robustness to all irrelevant or partially relevant contexts.

Controls use native MLflow refusal-status and citation-integrity scorers plus
manual inspection for any normative ruling inside a refusal. Status alone is
not Correct Abstention. Do not average control answers against normal football
references or merge their metrics into the 40-question normal comparison.
No removal intervention, empty-guard test, or gold changes in this experiment.

Run three generation smoke questions with trace readback before full calls;
also smoke the negative intervention. Score three snapshots with trace readback
before the full rescore. Successful judge caches are reusable and explicitly
recorded. All runs use MLFLOW_DISABLE_TELEMETRY=true to avoid the observed MLflow
3.17.2 import-hook deadlock; tracking and tracing remain enabled.

Promote only if evidence supports fewer unsupported claims/contradictions without
loss of correctness or more unjustified refusals. Save negative results as well.
Any N/A remains undefined, never zero; any scorer errors block accepting means.
