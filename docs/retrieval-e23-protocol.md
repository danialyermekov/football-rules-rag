# E23 — anchor-first packing (gold-blind)

Протокол зафиксирован до evaluation. Разрешён ровно один кандидат после E22; policy grid, подбор по scores и изменение default запрещены. Runner: `scripts/evaluate_anchor_first.py`; core: `pack_anchor_first_context`, tests: `tests/test_anchor_first.py`. До smoke должны пройти core tests. На момент фиксации протокола прошли156 unittest tests; evaluation ещё не запускалась.

## Frozen design

142 dev-вопроса с required evidence, 71 RU + 71 EN. Сохранённый E15 `b8b229800f4246d090eea03a4d5c9900` задаёт top50 и rank; E21 `174a45eee3c243e2a7bf21be9ddd7bae` — контроль. Оба должны быть FINISHED. Никаких новых embeddings, reranker inference, generation, provider API, пакетов или test-evaluation. Общие JSONL могут содержать test-структуру, но в dataset входят только dev. Модели, локальный `data/models/bge-m3`, MODEL_REVISION, source coordinates, evidence v2 и бюджет 2048 неизменны.

Единственная policy: `pack_anchor_first_context(documents, successors, budget, count_tokens)` из `football_rules.evidence_evaluation`. Никаких evidence/query/scenario аргументов. Anchors идут в E15 rank, ранее рассмотренные IDs пропускаются. В каждой группе попытки: anchor, один predecessor, один successor; каждый найденный в top50 ID рассматривается ровно один раз и становится seen даже при отказе. При принятии predecessor отображается перед anchor текущей группы, successor после. Уже принятые группы не пересортировываются и не вытесняются; рекурсии нет. При rejected anchor соседи всё равно рассматриваются. Каждую попытку проверять точными токенами всей предлагаемой строки `render_context`, `add_special_tokens=False`, а не суммой длин. Duplicate IDs, неоднозначные predecessors и budget<=0 — ошибки. Возврат: прежний context dict `documents/text/token_count/skipped`.

## Preflight и воспроизводимость

До evaluation проверить SHA256 chunks/scenarios/evidence/cleaned-pages против параметров **обоих** frozen runs. Все десять входных хешей (4 JSONL, 2 per-question artifacts, tokenizer metadata и 3 tokenizer JSON) дополнительно pinned по manifest FINISHED E22 `d54f4c7f1fc046e58b12caa275033d17`; значения включены в runner, изменение вызывает отказ. Проверить metadata revision до local-only загрузки tokenizer. Сверить 142 уникальные пары inputs/expectations, 71+71, top50 E21/E15 с неизменными scores и полными source chunk metadata. Полностью воспроизвести E21 ordering, context и все пять evidence metrics до любого E23 evaluate. Также replay E15 context. Сохранить hashes входов и reproduction code; перепроверить их после оценки, чтобы обнаружить изменение файлов во время запуска.

Native MLflow datasets: сначала discovery по детерминированному имени, reuse при полном совпадении records, иначе create/merge. Пять существующих deterministic native scorers: `complete_evidence`, `strict_complete_evidence`, `evidence_recall`, `evidence_coverage`, `source_redundancy`. Использовать `mlflow.genai.evaluate`, tracing и registration; не заменять native evaluation самописным циклом. Postprocessing per-question нужен для сравнения и проверки native means, не для замены missing scores. Все пять native means и все per-row assessments должны быть finite, без scorer errors.

## Безопасный порядок запуска

`MLFLOW_DISABLE_TELEMETRY=true`, `MLFLOW_GENAI_EVAL_MAX_WORKERS=1`, `MLFLOW_GENAI_EVAL_MAX_SCORER_WORKERS=1`. Runner задаёт defaults до импорта MLflow, сохраняет и логирует явные overrides, как E22; overrides могут вернуть QueuePool starvation. Для воспроизводимого запуска задавать явно все три значения. Не отключать tracing/scorers, не менять SQLAlchemy pool или tracking-конфигурацию.

1. После успешных tests: `uv run --no-sync python scripts/evaluate_anchor_first.py --smoke`, внешний process deadline **180 секунд**. Первые 3 dev records, native 5 scorers. Перед evaluate один traced predict, ID немедленно вывести и сохранить; flush + readback в отдельном процессе с общим deadline **не более 60 секунд**. При ошибке/таймауте остановиться, без polling/fallback/repeated eval.
2. После проверки smoke receipt разрешён full. `uv run --no-sync python scripts/evaluate_anchor_first.py`, внешний process deadline **300 секунд**. Runner требует успешный smoke receipt с теми же input/code hashes; это защищает от full на другой версии кода после smoke. Full — только 142 records, не prefix/другой dataset.
3. Прерывание, missing/nonfinite assessment и неполный run не являются результатом. Не заменять их нулями и не запускать новый метод вслед за неудачей.

## Reporting и предварительный gate

В MLflow: полные per-question inputs/expectations/outputs/metrics, E21 baseline metrics, summary с пятью native finite means, mean и counts по языкам, CER improved/regressed scenario IDs, input/code hashes, source run IDs, neighbor links, replay/evaluate/packing/end-to-end timings, trace receipt и reproduction files. В `tmp/e23` — run-specific и smoke/full receipts; run ID выводить сразу после start_run, затем итоговый receipt в stdout. Измеряется только cached packing плюс отдельно offline replay/evaluation overhead, не online latency.

Gate **только для будущего обсуждения generation**: mean CER строго выше E21, при этом ни один язык не теряет больше 1/71 (net complete count не ниже E21 минус один). Gate считается только на полном 142 dev; smoke не принимает решения. Default не менять даже при gate pass. Нет утверждений обобщения/независимого holdout: dev многократно использован, historical coordinate gold не исчерпывает альтернативные нормы. E22 — gold-aware feasibility diagnosis, не selector и не контроль E23 качества.
