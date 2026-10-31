# E22 — достижимость полного evidence при бюджете 2048

**Полный recovery завершён: 142/142 dev-вопросов, 142/142 native assessments.** Для всех 13 случаев, где top50 содержит полный размеченный комплект, но E21 потерял его при упаковке, найдено свидетельство в пределах прежнего бюджета. Это gold-aware диагностический oracle, **не новое качество retriever или генератора**. Default не изменён.

[Протокол и последовательные recovery-дополнения](retrieval-e22-protocol.md), [машиночитаемая сводка с IDs](retrieval-e22-summary.json), [скрипт](../scripts/evaluate_e22_budget_oracle.py).

## Полный результат

| Показатель | RU /71 | EN /71 |
|---|---:|---:|
| E21: полный комплект в готовом контексте | 55 (77,46%) | 60 (84,51%) |
| Oracle FOUND при тех же top50/B2048 | **61 (85,92%)** | **67 (94,37%)** |
| IMPOSSIBLE_POOL: top50 не покрывает gold | 10 | 4 |
| UNKNOWN | 0 | 0 |
| E21 CER=0, но найден допустимый комплект | **6** | **7** |

Итого: E21 **115/142=80,99%**, oracle **128/142=90,14%**. Диагностический запас упаковки: RU +8,45 п.п., EN +9,86 п.п., суммарно +13/142=9,15 п.п. Это не измеренный прирост работающей цепочки: oracle использует gold, недоступный реальному retriever. В этом run нижняя и верхняя границы feasibility совпали: UNKNOWN=0, остальные неуспехи доказаны отсутствием полного gold в top50. Для FOUND не доказана минимальность набора/стоимости — найдено первое допустимое свидетельство.

В 14 IMPOSSIBLE_POOL одной перестановкой/отбором имеющихся top50 полный **координатный** gold не восстановить. Это не доказательство отсутствия смысловой альтернативы в контексте или во всём корпусе: canonical gold не исчерпывает альтернативные основания.

## Какие потери упаковки действительно исправимы

Новые witnesses содержат 1–3 целых чанка и занимают 236–733 BGE-токена с прежними подписями/разделителями; увеличение бюджета не потребовалось.

| Сценарий | Язык | Чанков | Токенов |
|---|---|---:|---:|
| FR002 | RU | 3 | 681 |
| FR004 | RU | 3 | 681 |
| FR004 | EN | 3 | 633 |
| FR005 | RU | 2 | 471 |
| FR010 | EN | 2 | 368 |
| FR035 | RU | 1 | 259 |
| FR035 | EN | 1 | 258 |
| FR041 | RU | 2 | 461 |
| FR041 | EN | 2 | 486 |
| FR046 | EN | 1 | 239 |
| FR050 | EN | 1 | 236 |
| FR068 | EN | 3 | 633 |
| FR089 | RU | 3 | 733 |

IMPOSSIBLE_POOL RU: FR006/045/063/067/069/087/090/091/095/100. EN: FR006/063/087/089. Сценарии и языки зависимы; dev многократно использован, обобщение и CI по этим данным не заявляются.

## Почему предыдущие полные запуски зависали

Первоначальный full `ecb2be0318324fe68cfca07af3854f87` прерван после20 минут; остался KILLED. Smoke `d2f0eb9c18ec47b9a040dbec14980e11` дал3/3 FOUND. Начальная документация честно фиксировала отсутствие полного результата.

Для диагностики:

1. На12 frozen outputs тот же native scorer завершился за≈4s: `f44add939a1941bb992f3dc0494b1bb3`.
2. E22 prefix12 `39d9127ef6e44456b081bca398d63584` и prefix32 `cef8dd7f037a4387b6992b3dd23b3efc` завершились; native phase≈2/4s. Это диагностические runs, не новые полные оценки.
3. Документированный `MLFLOW_DISABLE_TELEMETRY=true` был явно задан; у первой команды он не задавался, унаследованное окружение неизвестно. **Одного этого недостаточно:** новый full `8520e4d46f0e441ebc4a6842e9fbabc0` также прерван за180s, KILLED.
4. В этом воспроизведении получен stack dump: потоки ждут SQLAlchemy QueuePool при `start_trace`/`log_spans`. Логи явно сообщают `QueuePool limit of size 5 overflow 10 reached, connection timed out, timeout 30.00`. Поэтому таймаут scorer был симптомом конкуренции записи traces/assessments за ограниченный пул локального tracking store, а не доказательством медленного evidence scorer. Это объяснение подтверждено для нового воспроизведения; у старого20-минутного run аналогичного стека нет.
5. До native evaluate заданы безопасные defaults **MAX_WORKERS=1, MAX_SCORER_WORKERS=1**, без отключения tracing/scorer и без изменения самого oracle или бюджета. Обе настройки логируются; явные overrides пользователя сохраняются и могут вернуть проблему, поэтому для воспроизводимой команды их следует оставить1.
6. Свежий smoke `3eadb6afe4f048d79d53c26ab6d5cc72` прошёл3/3, trace `tr-e86226255d3ec6163400a2ff69f662e2` прочитана. Полный run **`d54f4c7f1fc046e58b12caa275033d17` FINISHED**, native phase≈14s, без QueuePool/scorer warnings. Перед ней выполнялся полный replay142;14s не является end-to-end временем команды или production latency.

Не увеличивались SQLAlchemy pool/timeout и не менялась общая tracking-конфигурация приложения. Добавлены диагностический `--limit`, fail-fast проверки документированного telemetry workaround и ограничение конкурентности только для E22. Native datasets, `mlflow.genai.evaluate`, scorer и tracing сохранены. Предупреждения/незавершённые runs не скрыты и не заменены нулями.

## Проверки

Перед каждым запуском: **142/142** совпадений inputs/expectations, top50 E21/E15 с scores и source chunks; четыре исходных SHA-256 против обоих runs; pinned tokenizer; точный replay E21 packing/metrics.

Независимый readback полного run дополнительно проверил:

- 142 уникальных пар question/language,71+71 по языкам;
- каждый witness — уникальные **целые** чанки строго из исходного top50, с неизменными текстами/метаданными;
- точный `render_context`, токенизация целой строки≤2048 и повторный `evidence_metrics`;
- каждый IMPOSSIBLE_POOL действительно имеет pool CER=0;
- все **142 native assessments конечны и без errors**, их mean совпадает с per-question пересчётом, summary и native run metrics: **0.9014084507042254**;
- все 10 записанных source/tokenizer hashes неизменны. Найдены142 traces, исходные scores не пересчитывались и не перезаписывались.

Verification JSON и анализатор находятся в `verification/` полного run; per-question witnesses, input hashes и reproduction code — в его артефактах. Диагностические stderr/stdout также приложены к нему, не в публичный Git. Unit test подтверждает fail-fast/worker defaults, **не имитирует конкурентный deadlock**; его реальная регрессионная проверка — первоначально неуспешный и затем успешный native full142 при изменении конкурентности. Поведенческие тесты oracle проверяют budget boundary, source-page coordinates и UNKNOWN. Полный `unittest discover` — **150 tests, OK**; `py_compile` и `git diff --check` прошли. SQLAlchemy `noload` deprecation и SQLite ResourceWarning в старых тестах остаются предупреждениями, не failures. Ruff/Black не запускались: эти инструменты отсутствуют в установленной среде; зависимости не добавлялись.

Новых embeddings, reranker inference, Gemini/API или test-evaluation не было; provider experiment cost **$0**. Проверка целостности датасета может читать test-структуру, но test не использовался для настройки/оценки модели.

## Вывод для следующего опыта

Увеличение бюджета не является необходимым условием устранения этих13 координатных потерь. Обоснован следующий **gold-blind** packing-кандидат на тех же top50/B2048, отдельно от model/prompt: например, защита anchor от вытеснения соседями. Oracle не даёт реальному selector способа узнать нужные чанки. Продвижение потребует измерения CER/регрессий по обоим языкам и последующей проверки генерации с надёжной оценкой. Такой следующий опыт в рамках recovery не запускался.

## Воспроизведение

Из Git Bash, окружение проекта без sync/установки пакетов:

```sh
MLFLOW_DISABLE_TELEMETRY=true MLFLOW_GENAI_EVAL_MAX_WORKERS=1 MLFLOW_GENAI_EVAL_MAX_SCORER_WORKERS=1 uv run --no-sync python scripts/evaluate_e22_budget_oracle.py --smoke
MLFLOW_DISABLE_TELEMETRY=true MLFLOW_GENAI_EVAL_MAX_WORKERS=1 MLFLOW_GENAI_EVAL_MAX_SCORER_WORKERS=1 uv run --no-sync python scripts/evaluate_e22_budget_oracle.py
```

Нужны локальные исходные runs и tokenizer. `--limit N` создаёт отдельный diagnostic-prefix run и не называется full. Команды ограничивать внешним deadline; в данном recovery использовалось180s.
