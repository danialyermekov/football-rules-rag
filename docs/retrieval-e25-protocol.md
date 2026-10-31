# E25 — full-union Qwen reranking → top50 → E21 packing

Протокол одной policy, зафиксированный **до E25 evaluation/inference**. Runner: `scripts/evaluate_full_union_reranker.py`, helper: `src/football_rules/candidate_expansion.py`, tests: `tests/test_candidate_expansion.py`. До smoke прошли171 unittest tests и проверки всех7100 cached prefix scores/3960 tail memberships на frozen source artifacts. Исходное отсутствие модуля и SDK metadata serialization regression зафиксированы red→green; SDK source/tags не сериализуются как frozen inputs. Приложение/defaults, зависимости и gold не менялись.

**Порядок исполнения:** после green tests и фиксации протокола разрешён smoke. Полный run — только после проверки успешного matching smoke receipt. На момент этой фиксации E25 inference/evaluation ещё не выполнялись.

## Frozen design

- Только 142 dev-вопроса с required evidence: 71 RU + 71 EN. Test off; Gemini/provider calls = 0. Новых embeddings/search нет.
- E10 `b50e71e2d39d4145ae2f7e08fd49416e`: сохранённые `outputs.fusion_candidates`, полный RRF union 64–92 документов. Первые **ровно 50** — исходный RRF prefix.
- E15 `b8b229800f4246d090eea03a4d5c9900`: 7100 сохранённых Qwen scores исходных top50. Это единственный источник prefix scores в E25; их не заменять повторным inference.
- E21 `174a45eee3c243e2a7bf21be9ddd7bae`: primary quality control. Все три source runs должны быть FINISHED.
- `tail_candidates(fused, cached_prefix)` проверяет уникальные raw IDs, exact membership первых N, rank/score/provenance и возвращает tail в исходном E10 порядке. Runner фиксирует N=50 и суммарно **3960 tail pairs**.
- Для tail — только локальный `CrossEncoderReranker(model_name='qwen3-0.6b', device='cuda')`. `merge_reranked_candidates(fused, cached_prefix, fresh_tail)` проверяет exact membership, scores/provenance и создаёт **общий ranking всего union** через существующий `rank_documents` (score descending, chunk ID ascending).
- Из общего ranking выбрать **top50**, затем только `prioritize_rule_neighbors(top50, links)` и `pack_context(..., 2048, exact_budget_tokens)`, как E21. Упаковка всего union напрямую запрещена. E23 anchor-first и E24 compaction не комбинировать. Импорт E23 ограничен frozen constants и общими validators/hash helpers, не его policy.
- Helper не получает query/evidence. Inference получает только вопрос и raw passage text. Gold/expectations доступны только source replay, native scorers и post-hoc diagnostics; не передавать их selector’у, cache key или модели. Никаких question/scenario-specific правил и gold filters.

## Inputs, code и local model pinning

До первого forward проверить:

1. SHA256 исходных chunks/scenarios/evidence/cleaned-pages против параметров **E10, E15 и E21**. Все 10 frozen hashes E23 (4 JSONL, E15/E21 per-question artifacts, budget-tokenizer metadata и 3 tokenizer JSON) импортируются без изменений. Одиннадцатый — E10 `per-question-results.json`: `762ccd9194ed44b5826ac434a3176c7688e361a03ab196cf9b81586b034c7c8d`.
2. Артефакты читать из существующего **локального** `file:` artifact URI, без download/network fallback. Сверить unique142 inputs/expectations, 71+71, корпусный raw metadata/text/source coordinates у каждого union candidate, E10 prefix, E15 `source_candidates`, E21 тот же pool/scores. Воспроизвести для всех 142 E10/E15/E21 contexts, E21 ordering и пять context metrics. Проверить 7100 finite prefix scores, 3960 tail pairs, корректный score/tie ranking.
3. Budget tokenizer `data/models/bge-m3`: metadata revision `MODEL_REVISION`, pinned JSON hashes, загрузка `local_files_only=True`, `add_special_tokens=False` при подсчёте всей строки `render_context`.
4. Qwen `data/models/qwen3-reranker-0.6b`, revision **`e61197ed45024b0ed8a2d74b80b4d909f1255473`**. Все файлы из существующего класса и дополнительные локальные config/tokenizer files, включая `1_LogitScore/config.json`, должны существовать с revision metadata; SHA256 pinned в `MODEL_HASHES`. Critical weights `model.safetensors`: **`27cd75a405b9c1b46b59abfd88aaa209e6fed2a1972cde9b70e7659537c5e65b`**. Веса хешировать потоково **один раз на worker**, не для каждого cache key; к концу проверить size/mtime всех model/config/metadata files. Metadata SHA включить в binding. HF/Transformers offline, модель строго local-only; никаких downloads.
5. `reranker.parameters()` должен целиком совпасть с `reranker_*` E15, включая runtime versions/GPU. Frozen recipe: CUDA, FP32, batch=2, max_pair_tokens=1024, reject overflow, тот же instruction `Given a web search query, retrieve relevant passages that answer the query`, `yes_minus_no_logits`. CPU fallback, изменение max tokens/batch/prompt и relaxation запрещены.
6. До любого inference preflight **всех 11060 пар** полного E10 union через `reranker.model.preprocess` с actual Qwen template/instruction/answer suffix и `truncation=False`. Это tokenization, не forward. Любой overflow >1024 — stop, не truncation и не смена max.
7. `REPRODUCTION` SHA включает runner, этот протокол, `candidate_expansion.py`, reranking/evidence/evaluation/hash/tracking imports, `pyproject.toml`, `uv.lock`. Input/code hashes перепроверить перед успешным receipt. Изменение helper после smoke инвалидирует разрешение full.

## Cache и accounting

Сохранять только model responses, **не cached metric scores**. Ключ — SHA256 canonical JSON из query, ordered raw documents (включая IDs/text и provenance), всех model parameters и model-file hashes. Gold и evidence не входят. Более строгий полный raw input предотвращает reuse при незаметной смене RRF provenance.

`tmp/e25/responses/tail/<key>.json` хранит ответ Qwen только на tail. `head-control` — отдельный namespace для технических smoke controls. Проверять exact input/key, finite score на каждый unique ID, exact membership, score order/tie-break, retrieval score/provenance через `rank_documents`; tail дополнительно проходит helper merge. Cache corruption — stop, не незаметный rescore.

Перед локальным вызовом записать durable `.pending.json` intent; сразу по получении ответа записать atomic JSON, flush+fsync, **до metric logging**. Только после проверки сохранённого ответа удалить intent. Прерывание сохраняет все готовые caches. Intent без response — неоднозначный interrupted call: автоматический retry запрещён, требуется разбор main. Ответ уже на диске переиспользовать даже при оставшемся intent. После каждого доступа — run-specific calls ledger с purpose/cache status/local calls/local pairs/local inference seconds/cache access seconds. Cache-hit не означает новый GPU вызов. Повторный predict для trace/native evaluation не должен повторять inference.

Full использует ровно 3960 tail pair responses суммарно вместе с reuse smoke/предыдущих законченных responses; это **не 3960 вызовов метода**, поскольку `rerank` вызывается по query, внутри batch=2. Отдельно учитывать 150 head-control pairs smoke. Full не делает новых prefix/head-control calls и явно проверяет все три smoke tail caches перед evaluate. Offline timings не являются online SLA; cache-hit и actual local inference latency логировать раздельно.

## Smoke3 → receipt → full142

Обязательные env до MLflow import: `MLFLOW_DISABLE_TELEMETRY=true`, `MLFLOW_GENAI_EVAL_MAX_WORKERS=1`, `MLFLOW_GENAI_EVAL_MAX_SCORER_WORKERS=1`; runner выставляет defaults и отвергает несовпадающие overrides. Также `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`, `MLFLOW_ENABLE_ASYNC_TRACE_LOGGING=false`. Tracking только локальный. Не включать arbitrary custom-scorer deserialization, не менять pool/backend.

### Smoke — только после разрешения main

Команда для **будущего** разрешённого запуска: `uv run --no-sync python -B scripts/evaluate_full_union_reranker.py --smoke`. Общий deadline **240 секунд**; runner supervisor ограничивает worker, trace child входит в этот бюджет.

1. Зарегистрировать MLflow run и вывести `STARTED <run_id>` до долгого preflight/model loading; сохранить started receipt. Выполнить все source/hash/replay/template checks для 142.
2. Первые 3 dev records, без выбора по scores/gold. Отдельно rerank исходные E10 **50** для каждого из трёх вопросов. Сравнить **все 150** scores по ID с E15: `max_abs_error <= 1e-4` и **exact sorted IDs** для каждого вопроса. Проверить finite/rank/membership/provenance. Несовпадение — stop; не ослаблять tolerance/order и не пересчитывать E15 cache. Готовые exact-input head-control responses можно явно reuse после прерывания.
3. Только после успешных всех head controls score tails. Первый traced predict — root **`E25_full_union_reranker` CHAIN**, вложенный **`E25_union_reranking` RERANKER**, сохраняющий input/output полного ranking/cache operation; реальный вызов класса дополнительно имеет существующий `cross_encoder_reranking` RERANKER. Root/name не E23. ID вывести и durable сохранить сразу. Один flush+readback в отдельном убиваемом child с deadline **не более 60 секунд**; проверить CHAIN/RERANKER и непустые I/O. Без polling, fallback или повторного inference для readback.
4. Native `mlflow.genai.evaluate` на 3 с существующими пятью repository scorers: `complete_evidence`, `strict_complete_evidence`, `evidence_recall`, `evidence_coverage`, `source_redundancy`, всегда **после context packing**. Прямой `make_evidence_scorer`, **без `.register()`**: backend security blocking не обходить.
5. Native datasets: discovery по deterministic digest имени; reuse только exact inputs/expectations. Использовать `to_df()`, не `.df`; до `merge_records` передавать deep JSON copy, т.к. SDK мутирует вложенные records. Все **15 assessments** и 5 means finite; проверить каждый native request/response/context/score, не только averages.
6. Receipt только после FINISHED backend run: binding input/code/model hashes и parameters, все 3 head checks/150 scores, tail keys, trace readback, 3 complete rows/15 finite assessments, latency/calls ledger. `tmp/e25/smoke.json` и run-specific `<id>.json`. Smoke не принимает quality gate.

### Full — только с успешным matching smoke

Будущая команда: `uv run --no-sync python -B scripts/evaluate_full_union_reranker.py`. Общий deadline **720 секунд (12 минут)**. Никакого limit/grid/другой policy.

Проверить успешный receipt, FINISHED smoke run в том же experiment, те же input/code/model hashes/recipe и trace/head/native checks. Повторять head inference не нужно: перечитать exact-input head responses и assert 150 сравнений против receipt; любые cache misses — stop. Все три smoke tail responses должны существовать и совпадать с receipt. Затем только недостающие tail inference; оригинальные 7100 prefix scores остаются E15. Native evaluation 142; **142 complete rows, 710 finite per-row assessments, 5 finite means** обязательны. Полный gold-blind pipeline не получает expectations даже через closure.

При ошибке/таймауте результат не принимать; успешный receipt не писать. Supervisor убивает worker, но аварийно оборванный MLflow run может остаться RUNNING: main проверяет started run ID и при необходимости вручную закрывает его FAILED. Сохранённые caches/ledger не удалять. Никакого автоматического full после smoke, retry или нового метода после failure. Дополнительный внешний process deadline допустим; `--worker` — внутренний supervisor аргумент, не публичный способ обходить budget.

## Reporting и preregistered gate

Сохранить native metrics и полноценные per-question outputs (ranked union, selected50, context candidates, exact context), input/code/model binding, head controls, neighbor links, reproduction code, calls ledger и времена replay/template/native evaluation. Pool diagnostics только post-hoc: original50, full union до/после общего rerank, selected50. Full union coverage до/после ranking должна быть одинаковой. Frozen diagnostic CER: original full pool **61/71 RU, 67/71 EN**, full union **64/71 RU, 68/71 EN** — не outcome/selector и не обещание прироста packed-context CER. Сохранить evidence recall/coverage и остальные pool metrics до/после selection/context, CER gains/losses scenario IDs по языкам.

Единственный gate для будущего обсуждения generation: **mean packed-context CER строго выше E21**, и у каждого языка net complete count не ниже E21 минус один (loss ≤1/71). Оценивать только на full142; никаких дополнительных policies, gold filters или test evaluation. **Default никогда не менять**, даже при gate pass. Reused dev не является independent holdout; historical coordinate gold не исчерпывает все допустимые нормы. Качественный разбор main делает отдельно, без настройки policy по результатам этого run.
