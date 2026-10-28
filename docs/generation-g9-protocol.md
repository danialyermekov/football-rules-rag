# G9: Gemini3.8Flash versus Flash-Lite on frozen contexts

Fixed before generation, 2026-10-25. User reports approximately USD9 remaining.
No Argon calls. No third-party proxy calls. Use the existing Gemini credential.

## Configuration

Candidate: `gemini-3.8-flash`, temperature0, thinking_level=LOW,
max_output_tokens2048 (including thinking), unchanged SYSTEM_PROMPT/Answer,
legacy citations and empty guard. Baseline: frozen G7 Gemini2.5FlashLite outputs,
temperature0/output1024 with its original default thinking behaviour. This is
a model/configuration recipe comparison, not an isolated model-size effect.
No G8 checks, reranker changes, query rewriting or new retrieval.

Normal set: all64 G7 conditions,16 dev scenarios ×RU/EN ×E10/sufficient-source.
Compare candidate to the matching64 baseline outputs, not mixed context sets.
Add14 G8 controls (8 irrelevant,6 partial), using matching14 saved baseline
answers.78 new candidate requests maximum, successful smoke reused by exact
request fingerprint. No retries for answer selection. HTTP attempts1.
Generation runs sequentially so budget reservations cannot race.

Frozen source runs: G7 `200753af02644870a17e0cee46c6f7fd` and G8
`723b81f1dd964c358b2ed399b6763231`. Verify FINISHED, questions/dev split,
prompt and source hashes, ordered documents and complete context text. References,
gold, source-selection notes and condition labels never reach the generator.

## Budget

Local ceiling for new requests: **USD1.50**, split into generation USD0.75 and
judge USD0.75. Google billing balance is not accessible/verified; these are local
guards and usage-based estimates, not a cloud billing limit or invoice.

Verified Standard prices 2026-10-25:
- Flash3.8: input0.75/output+thinking3.75 USD/M through2026-12-31.
- Judge Flash-Lite2.5: input0.10/output+thinking0.40 USD/M.
Source: https://ai.google.dev/gemini-api/docs/pricing . No paid search tools,
explicit caching/storage, priority tier or Argon. Ignore automatic cache discounts
in estimates, conservatively charging full input rates.

Before each new generation call, atomically reserve a conservative input-byte
allowance including system/schema overhead plus2048 output tokens. Persist the
reservation before API; successful usage replaces it with the full-rate estimate.
A failed/unaccounted request retains its reservation. Do not retry successful
generation just to collect a new sample. Refuse new calls if the local cap would
be crossed; stop and report incomplete work instead of increasing the cap.

Judge uses the same existing evaluator/model/config and successful cache as
G7/G8. Add a bounded per-metric reservation/usage guard before new calculations;
cache hits consume no new-request budget. Full-state/errors are never hidden
by means computed over incomplete assessments.

## Execution and evaluation

Smoke before full: three fixed candidate questions, FR005 RU E10, FR095 EN E10,
FR069 RU sufficient; corresponding baseline snapshots included. Read one live
CHAIN/RETRIEVER/LLM trace within60s; check valid schema, nonempty answer, usage
and output truncation. No prompt edits after viewing quality. Infrastructure
failures remain recorded; no silent switch to another model.

Score128 normal snapshots with the same five Ragas metrics; keep28 controls out
of normal references. First run a three-snapshot judge smoke. Existing judge
tracing was verified in G7; cached judgments need not emit a fresh LLM trace.
Report E10 and sufficient separately, RU/EN means, all-case statuses/citations,
paired deltas and scenario bootstrap. Context metrics/cache keys must match
within each same-context model pair.64 baseline responses and their cached
judgments are reuse, not independent repeated measurements.

Review all64 normal pairs and28 controls for decision, conditions, actor,
restart/caution completeness, contradictions, refusal contents and unknown facts.
Compare with G7/G8 known failures, but do not retune on them. Sufficient contexts
are privileged diagnostic inputs, not a deployable retriever or independent
expert proof of source completeness. Review is by coding assistant, not referee.

Promote only if substantive improvements survive control review without material
new errors/unjustified refusals, and cost/latency are acceptable. A Ragas increase
alone does not suffice. Test stays unused; default remains unchanged during G9.
