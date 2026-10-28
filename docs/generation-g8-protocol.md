# G8: observable evidence checks on frozen E10 contexts

Fixed before API calls, 2026-10-25. One candidate only. Same 16 dev scenarios
and 32 RU/EN questions as G7; targeted known failures, not a new holdout.

Baseline normal answers are the 32 exact E10-condition outputs of G7 generation
run `200753af02644870a17e0cee46c6f7fd`. Verify question, prompt hash, source hashes,
ordered documents and context before reuse. These are not new model samples.
Candidate uses the exact same E10 contexts, Gemini2.5FlashLite, temperature0,
max_output_tokens1024, empty guard and legacy page citation representation.

The intervention is a single-call prompt plus structured-output schema recipe.
Before status/answer/citations, the model emits at most three concise checks:
verbatim rule quote, cited page, established incident fact and consequence for
the actual actor; then missing_facts and missing_rules. No reference/gold/notes
are sent to the model. New prompt is SYSTEM_PROMPT plus EVIDENCE_CHECK_PROMPT's
additional source/application requirements. This does not isolate schema from
instruction effects. There is no additional verifier call or answer selection.
Checks are factual support records, not extended reasoning. Answer alone is
scored by the unchanged Ragas suite; checks are saved and reviewed separately.

## Stress controls

Both baseline and candidate are generated fresh on identical control contexts:

- Eight irrelevant cases: FR001/005/009/055 × RU/EN, exact audited G1 irrelevant
  contexts from `13bca0d6da334de58f200846cac3fbbf` preparation.json.
- Six partial-source cases: FR005/009/055 × RU/EN. FR005 keeps only the referee's
  countdown sentence, omitting the required restart. FR009 keeps the handling
  condition/list without the governing indirect-free-kick heading. FR055 keeps
  only the sentence restricting direct goal-kick goals to the opponents' goal,
  omitting the own-goal restart. Full remaining texts are source-checked before
  calls; none states the requested restart, even though some related rule is
  present. They are deliberate interventions using source knowledge, not a
  proposed retrieval strategy.

Expected behaviour: identify absent support, do not invent the missing restart
or give it from memory; no unsupported ruling embedded inside a refusal.
Supported partial observations with an explicit limitation are distinguished
from invented completion in manual review. Status alone is not a correct
abstention metric. Control answers are not compared to ordinary football
reference answers or averaged with the normal set's Ragas scores.

## Verification, evaluation and decision

Prepare-only validates source hashes, dev split, both languages and exact control
source ranges. Run three paired normal smoke questions and read one candidate
CHAIN/RETRIEVER/LLM trace before full generation (readback deadline60s). Preserve
successful smoke outputs by exact request fingerprint; no repeat for selection.
Run all92 snapshots through native MLflow evaluation for code diagnostics.
Save64 normal and28 control snapshots separately. Existing native datasets are
discovered before creation; custom scorer code is imported directly, as the
local store disables custom scorer registration. Do not weaken that setting.

Code diagnostics: strict citation validity; whether each supplied check quote
occurs verbatim (whitespace-normalized) in its cited supplied fragment; declared
insufficient_context for controls. Empty checks establish no support, even if
there is no invalid quote. Do not normalize/correct invalid citations or quotes,
override status, discard bad outputs, or silently retry them. No semantic
correctness claim follows from successful quote provenance.

Use five unchanged Ragas metrics and judge configuration on64 normal snapshots,
with three-snapshot smoke. Reuse successful identical cached judgments explicitly;
cache hits need not create new traces. Generation tracing and G7's verified judge
tracing remain available; if a fresh judge smoke is needed, check it once rather
than expecting a new LLM trace from a cached judgment. Undefined/errors are not
zeros. Read back finite scores, native/grouped means and paired deltas.

Manually review32 normal pairs and28 control answers. Check required decision,
conditions, restart and sanction recipient, contradictions, unsupported extras,
missing-fact handling, and refusal content. Keep statuses and citation format
separate from semantic findings. Report RU/EN separately, bootstrap by scenario,
cost/usage and latency boundaries. Review is by coding assistant, not referee.

Promote only with fewer substantive mistakes/unsupported decisions and without
more unjustified refusals, missing consequences, or format regression. A Ragas
mean increase alone is insufficient. Do not retune after seeing G8 results.
Keep default, gold and test unchanged unless a later explicit decision is made.
