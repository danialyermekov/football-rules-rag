# E24 — strict-overlap context compaction (gold-blind)

**Preregistration: один кандидат, одна frozen policy до любых E24 scores.** На момент фиксации кода и протокола прошли163 unittest tests, smoke/full ещё не запускались. Перед full требуется успешный smoke с совпадающими хешами кода и данных. Нельзя менять policy после scores, выбирать победителя из нескольких версий или менять default, даже если gate пройден.

Runner: `scripts/evaluate_overlap_packing.py`. Core: `football_rules.context_compaction.pack_overlap_context`. Основной контроль — **E21** `174a45eee3c243e2a7bf21be9ddd7bae`; source ranking — E15 `b8b229800f4246d090eea03a4d5c9900`. [E23 results](retrieval-e23-results.md) и summary разрешены лишь как историческая диагностика, **не selector, не контроль для gate и не источник настройки**. Runner не читает E23 scores/summary; импортирует из E23 runner только frozen constants и общие validation/hash helpers, не его packing policy.

## Frozen inputs и границы опыта

- Только прежние **142 dev inputs**, 71 RU + 71 EN, прежние expectations/evidence v2. Это зависимые языковые версии 71 сценария, не 142 независимых пользовательских эпизода. Test-evaluation и изменение gold/references запрещены.
- Те же E15 top50, scores и source chunks. `documents` на входе core — **E21 ordering**: `prioritize_rule_neighbors(E15_top50, links)`, а не anchor-first E23.
- `pages` — общие cleaned pages `dict[(document_id, pdf_page), page]`, без gold. Вызов ровно `pack_overlap_context(documents, pages, budget, count_tokens)`. Нет query, scenario ID, reference, required evidence или иных evidence arguments. Query/language в predict используются только для выбора frozen retrieval input, не для настройки packing.
- **B=2048**, прежний local-only BGE-M3 tokenizer и `MODEL_REVISION`; `add_special_tokens=False`. Никаких новых моделей/загрузок весов, embeddings, reranker inference, generation, provider API, установки зависимостей или платных вызовов.

Все **10 frozen SHA256** берутся без изменений из `FROZEN_HASHES` в `scripts/evaluate_anchor_first.py` (manifest FINISHED E22 `d54f4c7f1fc046e58b12caa275033d17`): четыре JSONL (`chunks/scenarios/evidence/cleaned-pages`), два E21/E15 `per-question-results.json`, tokenizer metadata и три tokenizer JSON. Это pinned значения, а не просто сравнение текущих файлов между собой. Оба source runs обязаны быть FINISHED; SHA256 четырёх JSONL также сверяется с параметрами обоих runs. Tokenizer revision сверяется с metadata до local-only loading.

## Единственная policy v1

Идентификатор: `e21_order_strict_page_overlap_union_greedy_no_eviction_v1`.

1. Последовательно рассмотреть каждый candidate ровно один раз в E21 order. Уже принятые оригинальные chunks не выбрасывать, не обрезать и не заменять другой выборкой. Отказ по бюджету окончательный, без повторной попытки после будущих admissions.
2. Для trial `selected_originals + candidate` построить connected components **строго перекрывающихся** cleaned intervals одной пары `(document_id, pdf_page)`. При сортировке по start объединение допустимо только когда `current_end > next_start`. Транзитивное перекрытие допустимо; touching (`end == next_start`), disjoint, разные документы и страницы **не объединять**. Нельзя включать текст gap, новый source или расширять границы до блока/страницы.
3. Merged block занимает место constituent с самым ранним **admission rank**, не место минимального source offset. Порядок блоков — по этим ранним ranks. Внутри merged block — в точности `page.cleaned_text[min_start:max_end]`, без нормализации/переписывания текста. Каждая уникальная cleaned character position выбранных originals, включая whitespace, сохраняется; добавление позиций запрещено.
4. Metadata page/edition/language и source identity должны совпадать с исходной страницей. `source_spans` вычисляются через `source_positions(page)` и `source_ranges(positions[start:end], page.text)`, не через подстановку gold или расширение spans. Synthetic merged `chunk_id` не может совпадать с **каким-либо** original ID корпуса. Для merged block обязателен `constituent_chunk_ids` с полным уникальным составом; singleton остаётся original record целиком, включая retrieval metadata.
5. Admission решается по **точной токенизации целой строки `render_context(trial_merged_blocks)`**, включая labels и separators, не суммой chunk token counts. Принять, только если целая строка ≤2048; иначе добавить один `{"chunk_id": original_id, "reason": "token_budget"}` в `skipped` и продолжить.
6. Вернуть context dict: `documents` (фактические merged blocks/singletons), `selected_documents` (raw originals в admission order), `text`, `token_count`, `skipped`.

Core обязан валидировать source text/spans/metadata consistency, duplicate IDs и положительный budget. Поведение алгоритма, сохранение admissions, strict/transitive overlap, touching/disjoint/cross-page cases и exact trial budget проверяет main в core tests **до smoke**. Никакие результаты core tests не заявляются этим протоколом заранее.

## Runner validation — без предположения merged == pool record

До любого E24 scoring, в том числе smoke:

- Проверить 142 уникальные input pairs и полное равенство inputs/expectations с E21/E15, распределение 71+71, уникальный top50, неизменные scores и source metadata.
- Выполнить **полный baseline replay142**: E21 ordering, context и все пять evidence metrics; E15 context. Smoke сокращает только новые E24 records до первых трёх, а не preflight replay.
- Построить исходные cleaned-to-source maps для всех candidate pages. Проверить text slice, `source_ranges` и page metadata **каждого** candidate, не только будущих selected.
- Вычислить reproduction SHA256 до scoring, включая новый `src/football_rules/context_compaction.py`, runner, protocol, `chunking.py`, `cleaning.py`, evidence/scorer/tracking/embedding code, импортируемый E23 runner, `pyproject.toml` и `uv.lock`. Сохранить manifest и сами reproduction files. Перепроверить code/input hashes после evaluation; изменение файлов — ошибка, не новый результат.

Gold-blind predict создан отдельной factory, получающей только retrieval candidates, pages, source maps, tokenizer callback и original IDs; он не замыкает baseline records, expectations или source gold. Core получает только четыре согласованных аргумента. Runner проверяет отсутствие мутации candidates, exact rendering и budget до возвращения output, поэтому native scorers получают **настоящие merged blocks** в `outputs.context.documents`.

Для каждого context runner независимо строит strict overlap components и проверяет:

- `selected_documents` — неизменённое подмножество frozen top50 в E21/admission order, без duplicate IDs; `skipped` — ordered once-only complement.
- Количество/порядок blocks и constituent membership точно соответствуют этим components; constituents уникальны и в совокупности равны всем selected originals. Singleton равен original record; merged ID уникален и не masquerades original.
- Exact cleaned boundaries/text, metadata и `source_spans` каждого блока сверены с исходной страницей/картой. Нормализованные **coordinate unions** raw и merged равны; mapped source character unions также равны. Touching intervals могут схлопываться только при проверке равенства множеств координат, но **не при формировании blocks**.
- Whole rendered text повторно токенизируется и совпадает с `token_count ≤2048`.

**Только после выбора контекста** evaluator сравнивает `evidence_metrics(selected_raw, required, pages)` и `evidence_metrics(merged, required, pages)`: четыре coverage/completeness метрики должны быть в точности равны. `source_redundancy` может отличаться. Native per-question assessments сверяются с recomputed merged metrics по query/language, а native trace response — с фактическим context. В установленном MLflow 3.17.2 `result_df` предоставляет root `request/response`, а не предполагаемые flattened `inputs.query` columns. Все assessments и пять native means должны быть finite, без scorer errors; пропуски не заменять нулями.

## Native MLflow и безопасное исполнение

Использовать native dataset discovery → deterministic-name reuse/create/merge, проверять records через **`dataset.to_df()`** как после reuse, так и после creation. Новые записи содержат лишь прежние dev inputs/expectations. Evaluation — **`mlflow.genai.evaluate(data=dataset, predict_fn=..., scorers=...)`**, не самописный scoring loop.

Пять существующих deterministic scorers из repository `make_evidence_scorer`: `complete_evidence`, `strict_complete_evidence`, `evidence_recall`, `evidence_coverage`, `source_redundancy`. **Не вызывать `.register()`**: local persistent custom scorer registration security-blocked. Не включать unsafe deserialization opt-in/`MLFLOW_SERVER_ENABLE_CUSTOM_SCORERS`. Native evaluate, все пять scorers и tracing обязательны.

Environment до импорта MLflow:

```text
MLFLOW_DISABLE_TELEMETRY=true
MLFLOW_GENAI_EVAL_MAX_WORKERS=1
MLFLOW_GENAI_EVAL_MAX_SCORER_WORKERS=1
```

Runner задаёт defaults и **отклоняет** overrides, нарушающие эти значения; QueuePool starvation не обходить увеличением pool/изменением общего tracking. Внешние process deadlines обеспечивает main/вызывающий terminal, не флаг runner. При timeout процесс должен быть остановлен; не оставлять работающий background evaluation.

1. **Main проверяет core tests и frozen policy до запуска.** Затем smoke: `uv run --no-sync python scripts/evaluate_overlap_packing.py --smoke`, внешний deadline **180 секунд**. Ровно первые 3 dev records, native 5 scorers/15 finite assessments. Дополнительный traced predict первого record — только техническая trace verification, не четвёртый evaluation record.
2. Перед smoke evaluate: synchronous trace logging, predict, немедленно вывести/сохранить trace ID. Один subprocess выполняет flush + readback + проверку E24 span с I/O; общий timeout **не более 60 секунд**, включая импорт/SDK retries. При отказе/timeout остановиться: без polling, fallback или повторного evaluation ради trace ID.
3. Main читает smoke receipt и проверяет run/trace/assessments. Full разрешён только после этого: `uv run --no-sync python scripts/evaluate_overlap_packing.py`, внешний deadline **300 секунд**, ровно142 records.
4. Runner требует `tmp/e24/smoke.json`: FINISHED smoke3, matching **все10 input hashes и все reproduction code hashes**, policy ID, trace spans>0/readback≤60s, backend FINISHED run того же experiment, smoke age **не более24 часов**. Local receipt создаётся только после успешного закрытия run; stale/failed/mismatched smoke не авторизует full. Этот технический guard не заменяет проверку main.
5. Любой preflight mismatch, неполный run, nonfinite/missing score, scorer error или timeout — остановка, не отрицательная метрика и не повод менять policy. После содержательных scores нельзя исправить policy и запустить ещё одного кандидата в рамках этого разрешения. Чисто технический блокер до scoring документировать отдельно; не скрывать failed runs.

## Reporting, gate и ограничения вывода

Сохранить в MLflow полные per-question inputs/expectations/outputs, merged и selected-raw metrics, E21 baseline metrics; source run IDs, neighbor links, input/code manifests, reproduction files, trace receipt и native means. В summary — means и complete counts по языкам, improved/regressed scenario IDs, mean CER, gate. В `tmp/e24` — run-specific и smoke/full receipts с run ID и end-to-end timing; run ID выводится сразу после start_run.

Отдельно измерять baseline replay, native evaluation, сумму времени **core packing** и end-to-end. Predict/source validation overhead входит в evaluation wall time, но не core packing; сумма не является online SLA/latency. Нельзя складывать вложенные интервалы как независимые затраты.

Preregistered gate только для **будущего обсуждения generation** и только на full142:

- mean CER **строго выше E21**;
- каждый язык: E24 complete count **≥ E21 complete count −1**.

Smoke не принимает качественного решения (`gate=null`). **Default/CLI не менять даже при pass.** E23 не участвует в gate/selection. Снижение source redundancy ожидается **по конструкции**: удаляется повторное представление тех же source characters. Оно само по себе не доказывает качество, смысловую достаточность, улучшение ответов или обобщение. Сравниваем canonical coordinate coverage, а не правильность будущей generation. Dev многократно просмотрен, gold не исчерпывает альтернативные прямые основания нормы; E23 FR050 EN уже показал это ограничение. Никакого winner-tuning, policy grid, новых правил по scenario/language или просмотра test для настройки.

## Проверки до запуска

Core и семь behavior tests реализованы; первоначальный red зафиксирован до создания модуля, затем163 tests прошли. Проверяются lossless union, strict/transitive overlap, touching/disjoint/cross-page, порядок admission, exact trial tokenization, не-восстановление удалённого текста и ошибки provenance. `py_compile` и `git diff --check` прошли. Это не заменяет runtime smoke и не является результатом E24.

## Уточнение SDK preflight до любых E24 scores

Первый smoke остановился до создания MLflow run: строгая проверка native dataset после `merge_records` обнаружила добавленные SDK provenance/tags в переданные Python dicts. Установленный MLflow мутирует этот аргумент (`_infer_source_types`, resolved user tags); исходные inputs/expectations в сохранённом native dataset совпадают с fresh records. Исправление — передавать deep JSON copy в `merge_records`, не ослаблять сравнение. Oracle/policy/gold не менялись, E24 scores на момент исправления отсутствуют. Повторный smoke и full используют один и тот же исправленный runner.
