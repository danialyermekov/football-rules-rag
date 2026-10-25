# G5: frozen E10 versus E15 generation comparison

Protocol fixed on 2026-10-25 before new generation. Development diagnostics only;
these scenarios have previously participated in retrieval selection. This is not
an independent test estimate and the test split remains untouched.

- E10: `b50e71e2d39d4145ae2f7e08fd49416e`, Qwen dense + BM25, RRF60.
- E15: `b8b229800f4246d090eea03a4d5c9900`, same candidates + Qwen reranker.
- Same frozen context budget of 2048 BGE tokens, baseline SYSTEM_PROMPT,
  Gemini 2.5 Flash-Lite, temperature 0, legacy citations, empty-context guard.
- No query rewriting, new retrieval, prompt search, or answer regeneration.
- Both languages for each scenario: 40 responses per source, 80 total.

Fixed scenario list:

```
FR001 FR005 FR009 FR019 FR023 FR037 FR050 FR055 FR077 FR090 FR094 FR095
FR063 FR068 FR088 FR100
FR010 FR065 FR069 FR085
```

The first 12 are answerable, the next four conditional_answer, and the last four
insufficient_information. Six scenarios overlap the earlier generation pilot.
Selection covers ordinary rules, exceptions, discipline, restarts, and situations
requiring missing facts. It is purposive, not a representative random sample.
Out-of-scope questions are excluded because these frozen retrieval runs do not
contain them. Missing facts in a scenario differ from missing retrieved evidence.

Run three generation smoke questions with trace readback, then the two full
generation runs. Smoke outputs are separate diagnostics. Run the existing frozen
snapshot evaluator with Gemini judges and these five metrics:

1. Context Precision with reference: usefulness of the ordered supplied passages.
2. Context Recall: coverage of reference claims by supplied passages.
3. Faithfulness: support for answer claims in supplied passages.
4. Answer Relevancy: generated reverse questions and pinned BGE embeddings.
5. Factual Correctness: response versus reference, independently of context.

Score three frozen snapshots first with judge trace readback. Judge caches are
identified explicitly; reused scores are not independent repeated measurements.
Report means and valid counts for RU/EN separately, paired E15-minus-E10 deltas,
and answered-only diagnostics. Undefined values remain N/A. Do not collapse
metrics into a single quality score. Inspect answers against reference constraints,
especially differing decisions, refusals, and strong scores on incorrect answers.
Citation page membership is a format/source check, not proof of claim support.

Save source hashes, prompts, answers, judgments, usage, and comparison artifacts
in MLflow; append results and limitations to generation-results.md. Generation
latency excludes retrieval replay; retrieval/reranking timings come from the
source experiments and must not be added as separate medians to claim end-to-end
latency. The comparison cannot establish production readiness or expert accuracy.
