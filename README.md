# Football Rules RAG

Учебный проект ассистента по футбольным правилам IFAB. Реализованы обработка PDF, chunking, Dense/BM25/Hybrid retrieval через Qdrant Local, reranking, генерация Gemini и оценка через Ragas/MLflow. Проект пока находится на стадии локальных текстовых экспериментов; API, UI и мультимодальный анализ ещё не реализованы.

[Обзор проекта: что сделано, результаты, карта файлов и дальнейший план](docs/project-overview.md) — состояние после G10 на 26.10.2026.

[G9: сравнение Gemini 3.8 Flash с Flash-Lite](docs/generation-g9-results.md):
есть исправления и лучшее соблюдение границ источников; общие метрики смешанные,
default пока сохранён. Локальная оценка новых расходов с резервом ошибок — $0,22.

[G10: Argon против обеих Flash](docs/generation-g10-results.md): устойчивого преимущества нет; есть регрессии при неизвестных фактах. 960/960 оценок, новые расходы ≈$0,425. Default сохранён.

## Задать свой вопрос через CLI

Из корня проекта, с существующим окружением и подготовленным локальным индексом:

```powershell
# Интерактивный режим (загружает индекс и модель эмбеддингов один раз):
uv run --no-sync football-rules chat
uv run --no-sync football-rules chat --model gemini-4-argon
uv run --no-sync football-rules chat --language en --model gemini-3.8-flash

# Одиночный вопрос:
uv run --no-sync football-rules ask "Можно ли забить гол непосредственно с вбрасывания?"
uv run --no-sync football-rules ask "Вратарь держал мяч девять секунд. Что назначить?" --model gemini-3.8-flash
uv run --no-sync football-rules ask "Когда назначается повтор пенальти?" --model gemini-4-argon --sources
uv run --no-sync football-rules ask "Can a player be offside directly from a throw-in?" --language en --model gemini-3.8-flash --save tmp/saved-questions.jsonl
```

В интерактивном режиме `chat` поисковая модель и индекс загружаются один раз при старте, а вопросы принимаются в цикле. Доступны команды внутри сессии:

- `/sources` (или `/источники`) — показать использованные фрагменты контекста последнего ответа с отметкой `[cited]`.
- `/save [заметка]` (или `/сохранить [заметка]`) — сохранить последний вопрос, точные источники, упакованный контекст, ответ, модель и настройки в JSONL (по умолчанию `tmp/saved-questions.jsonl`, либо `--save-path`).
- `/model [имя]` — посмотреть или переключить модель (`gemini-2.5-flash-lite`, `gemini-3.8-flash`, `gemini-4-argon`) без перезагрузки индекса.
- `/lang [ru|en]` — посмотреть или переключить язык вопросов.
- `/help` — справка по командам; `/exit` (или `выход`) — завершить сессию.

По умолчанию язык `ru`, модель `gemini-2.5-flash-lite`. Команды `ask` и `chat` используют
E10: Qwen3-Embedding-0.6B + BM25/RRF, глубина ветвей 50 и контекст 2048 токенов
по локальному BGE-токенизатору. Нужны подготовленные chunks, модели и Qdrant;
коллекция по умолчанию — `football_44d75390ffa00dde1b74f0e6`.
Другой путь/совместимый Qwen-индекс задаются через `--database` и `--collection`.

Вывод содержит ответ, статус и ссылки `document_id:PDF_page`. `needs_clarification`
означает нехватку фактов эпизода, `insufficient_context` — нехватку источников.
В `ask` можно добавить `--sources` для вывода фрагментов контекста, `--save <путь>` для записи в JSONL или `--json` для полного JSON с источниками, usage и результатом формальной проверки ссылок. Справка: `uv run --no-sync football-rules ask --help` и `uv run --no-sync football-rules chat --help`.

Ключ читается из `GEMINI_API_KEY`/`GOOGLE_API_KEY` в окружении или локальном `.env`.
Это один реальный платный запрос генерации при непустом контексте, без LLM-оценщика.
Flash 3.8 и Argon используют настройки G9/G10 (LOW thinking, лимиты 2048/32768);
Argon дороже. Первый запуск загружает локальную embedding-модель и может занять
заметно больше времени, чем сама генерация. Каждый вопрос обрабатывается независимо, без
истории диалога.

## Запуск ingestion

Требования: Python 3.13+ и uv. Из корня репозитория:

```powershell
uv sync --locked
uv run football-rules ingest
```

Команда читает `docs/source-manifest.json`, проверяет локальные PDF по размеру и SHA-256 и сохраняет все страницы в `data/processed/pages.jsonl`. Файлы PDF должны находиться по путям из manifest; [официальные источники и результаты проверки](docs/ifab-sources.md). Автоматической загрузки в этой команде нет. Исходники и извлечённый текст исключены из Git.

Можно явно указать manifest и файл результата:

```powershell
uv run football-rules ingest --manifest docs/source-manifest.json --output data/processed/pages.jsonl
```

Пути PDF в manifest задаются относительно текущего корня проекта. [Описание реализации, полей, QA и ограничений](docs/ingestion.md).

## Очистка текста

```powershell
uv run football-rules clean
```

Команда читает `data/processed/pages.jsonl` и создаёт отдельный файл `data/processed/cleaned-pages.jsonl`. Убирает распознанные колонтитулы и номера страниц, соединяет перенесённые строки и выделяет предварительные блоки текста. Исходные поля сохраняются; блоки содержат диапазоны символов в исходном `text` для будущего сопоставления с evidence датасета. [Алгоритм, поля, результаты и ограничения](docs/cleaning.md).

## Чанкинг

```powershell
uv run football-rules chunk
```

Результат — `data/processed/chunks.jsonl`. Используется `RecursiveCharacterTextSplitter` из `langchain-text-splitters`: до 1000 символов, целевой overlap 150, без перехода между страницами. Каждый чанк содержит текст, воспроизводимый ID, метаданные, параметры разбиения и точные диапазоны в исходном `text`.

Другую конфигурацию сохраняйте отдельно:

```powershell
uv run football-rules chunk --chunk-size 600 --chunk-overlap 100 --output data/processed/chunks-600-100.jsonl
```

[Как работает разбиение, примеры RU/EN, результаты и ограничения](docs/chunking.md). Изменение параметров само по себе не считается улучшением: сравниваем метрики retrieval на dev-наборе.

E5 проверяет размер 600 при прежнем overlap 150. Новый файл и коллекция сохраняются отдельно от baseline; модель, CPU FP32, пул 50 и бюджет контекста 2048 фиксированы:

```powershell
uv run --extra cpu football-rules chunk --chunk-size 600 --chunk-overlap 150 --output data/processed/chunks-600-150.jsonl
uv run --extra cpu football-rules index --input data/processed/chunks-600-150.jsonl
uv run --extra cpu python scripts/evaluate_retrieval.py --collection football_bc5fcb15e54aaeef28b171c6 --chunks data/processed/chunks-600-150.jsonl --run-name E5-dense-chunks-600-150-v2 --limit 3 --verify-trace
uv run --extra cpu python scripts/evaluate_retrieval.py --collection football_bc5fcb15e54aaeef28b171c6 --chunks data/processed/chunks-600-150.jsonl --run-name E5-dense-chunks-600-150-v2
```

Имя коллекции относится к текущим закреплённым версиям и артефактам; при другой конфигурации используйте значение из вывода `index`. Основные метрики оценивают покрытие фиксированных исходных evidence, поэтому gold не меняется при другом количестве чанков; исторические `chunk_v1_*` не используются для выбора размера.

E6 проверяет размер 1600 при том же overlap 150 и Dense-конфигурации E0. Чанки и векторная коллекция также сохраняются отдельно:

```powershell
uv run --extra cpu football-rules chunk --chunk-size 1600 --chunk-overlap 150 --output data/processed/chunks-1600-150.jsonl
uv run --extra cpu football-rules index --input data/processed/chunks-1600-150.jsonl
```

После `index` передайте выведенное имя коллекции в оценку:

```powershell
uv run --extra cpu python scripts/evaluate_retrieval.py --collection football_4380140929ffc0653c675e9c --chunks data/processed/chunks-1600-150.jsonl --run-name E6-dense-chunks-1600-150-v2 --limit 3 --verify-trace
uv run --extra cpu python scripts/evaluate_retrieval.py --collection football_4380140929ffc0653c675e9c --chunks data/processed/chunks-1600-150.jsonl --run-name E6-dense-chunks-1600-150-v2
```

E7 изолирует влияние overlap: размер остаётся 1000 символов, перекрытие уменьшается со 150 до 0. Остальные настройки совпадают с E0:

```powershell
uv run --extra cpu football-rules chunk --chunk-size 1000 --chunk-overlap 0 --output data/processed/chunks-1000-0.jsonl
uv run --extra cpu football-rules index --input data/processed/chunks-1000-0.jsonl
uv run --extra cpu python scripts/evaluate_retrieval.py --collection football_2d278e0ae22ca05466186f42 --chunks data/processed/chunks-1000-0.jsonl --run-name E7-dense-chunks-1000-0-v2 --limit 3 --verify-trace
uv run --extra cpu python scripts/evaluate_retrieval.py --collection football_2d278e0ae22ca05466186f42 --chunks data/processed/chunks-1000-0.jsonl --run-name E7-dense-chunks-1000-0-v2
```

Коллекция указана для текущих закреплённых артефактов; при пересоздании проверьте имя из `index`. Все прежние файлы чанков и индексы сохраняются.

## Embeddings, поиск и оценка

После загрузки закреплённой версии BGE-M3:

```powershell
uv run football-rules index
uv run football-rules search "Можно ли оказаться вне игры после вбрасывания?" --language ru --collection football_a71631f65a6ba8bd0978b14e --k 5
uv run python scripts/evaluate_retrieval.py --collection football_a71631f65a6ba8bd0978b14e --limit 3 --verify-trace
uv run python scripts/evaluate_retrieval.py --collection football_a71631f65a6ba8bd0978b14e
```

Имя коллекции в примере относится к текущему корпусу и модели; при другой конфигурации используйте имя, выведенное `index`. Qdrant работает локально на диске, без отдельного Docker-сервера. MLflow использует локальный SQLite, если не задано другое tracking destination. Retrieval оценивается отдельно для RU/EN, без Gemini и платных LLM judges.

[Загрузка модели, устройство индекса, правило релевантности, MLflow и ограничения](docs/retrieval.md).

[Исследование методов улучшения retrieval и план контролируемых экспериментов](docs/retrieval-experiments.md): evidence-based оценка, candidate depth, BM25/hybrid, reranking и chunking. Измерены E0 Dense, E1 BM25, E2 hybrid, E3 Dense20 → cross-encoder, E4 RRF20 → cross-encoder и E4b с расширением до RRF50.

BM25 использует те же чанки, но не требует embedding-модели и Qdrant. Для одинакового бюджета контекста нужен локальный токенизатор закреплённой версии BGE-M3:

```powershell
uv run python scripts/evaluate_retrieval.py --strategy bm25 --limit 3 --verify-trace
uv run python scripts/evaluate_retrieval.py --strategy bm25
```

Статистика BM25 считается отдельно по языкам, параметры `k1=1.2`, `b=0.75`. Нормализация NFKC/casefold и `ё→е`, разбиение на Unicode-буквы/цифры, без стемминга и стоп-слов. Повторения слов вопроса не усиливают их вес. Чанки без совпадений исключаются, одинаковые оценки разрешаются сортировкой по ID. [Формула IDF и параметры BM25 в документации Lucene](https://lucene.apache.org/core/10_3_1/core/org/apache/lucene/search/similarities/BM25Similarity.html); наша реализация использует точные длины текстов и не воспроизводит Lucene analyzer/norm quantization.

Hybrid выполняет Dense50 и BM2550 последовательно и объединяет их на стороне приложения через RRF: `sum(1/(60+rank))`, ранги от 1, равные веса. Сохраняется весь уникальный пул с позициями и исходными scores каждой ветви; для основного контекста используются первые 50 результатов RRF и прежний бюджет 2048. Константа 60 — настройка проекта, не default Qdrant. [Официальное описание RRF](https://qdrant.tech/documentation/search/hybrid-queries/).

```powershell
uv run python scripts/evaluate_retrieval.py --strategy hybrid --collection football_a71631f65a6ba8bd0978b14e --limit 3 --verify-trace
uv run python scripts/evaluate_retrieval.py --strategy hybrid --collection football_a71631f65a6ba8bd0978b14e
```

[Текущий протокол оценки v2](docs/retrieval-evaluation-v2.md) использует объединённые evidence и фиксированный бюджет контекста. [Журнал всех результатов и изменений метрик](docs/retrieval-results.md) пополняется после каждого эксперимента.

## Реранкер и CUDA

Для E9 сравнивается Dense-поиск с `Qwen/Qwen3-Embedding-0.6B`. Чанки 1000/150 и бюджет 2048 по токенизатору BGE-M3 остаются прежними. Qwen кодирует вопросы с опубликованной английской инструкцией, документы — без неё. FP32, CUDA, batch 2; требуется доступный GPU:

```powershell
uv run --extra cuda hf download Qwen/Qwen3-Embedding-0.6B config.json model.safetensors tokenizer.json tokenizer_config.json config_sentence_transformers.json modules.json 1_Pooling/config.json --revision 97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3 --local-dir data/models/qwen3-embedding-0.6b
uv run --extra cuda football-rules index --embedding qwen3-0.6b
uv run --extra cuda python scripts/evaluate_retrieval.py --embedding qwen3-0.6b --collection football_44d75390ffa00dde1b74f0e6 --run-name E9-dense-qwen3-0.6b-v2 --limit 3 --verify-trace
uv run --extra cuda python scripts/evaluate_retrieval.py --embedding qwen3-0.6b --collection football_44d75390ffa00dde1b74f0e6 --run-name E9-dense-qwen3-0.6b-v2
uv run --extra cuda football-rules search "Можно ли оказаться вне игры после вбрасывания?" --embedding qwen3-0.6b --language ru --collection football_44d75390ffa00dde1b74f0e6 --k 5
```

Имя коллекции зависит от закреплённых версий; проверьте вывод `index`. Параметр `--embedding` доступен для `index`, `search` и оценки; по умолчанию используется прежняя BGE-M3. Векторы моделей не смешиваются. Новые evaluation runs помечаются `run_kind=smoke/full`; проверочный запуск на 3 вопросах не сравнивают с полными 142. Задержка Qwen на GPU не является сравнением скорости моделей с историческим CPU-run E0.

E3 использует multilingual cross-encoder `BAAI/bge-reranker-v2-m3`, закреплённая ревизия `953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e`. [Карточка модели BAAI](https://huggingface.co/BAAI/bge-reranker-v2-m3/tree/953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e). Ввод — полный вопрос и текст чанка, выход — raw logit релевантности. Это не вероятность корректности ответа.

На Windows опция `cuda` устанавливает PyTorch `2.14.1+cu130` из официального индекса. Обычный `uv run` выбирает исходную сборку `2.14.1` из PyPI; `cpu` и `cuda` взаимоисключающие. CUDA проверена на RTX 3060 Laptop 6 ГиБ. Настройка следует [руководству uv по PyTorch](https://docs.astral.sh/uv/guides/integration/pytorch/).

```powershell
uv run --extra cuda hf download BAAI/bge-reranker-v2-m3 config.json model.safetensors tokenizer.json tokenizer_config.json special_tokens_map.json sentencepiece.bpe.model --revision 953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e --local-dir data/models/bge-reranker-v2-m3
uv run --extra cuda python scripts/evaluate_reranker.py --limit 6 --verify-trace
uv run --extra cuda python scripts/evaluate_reranker.py
```

E3 повторно использует первые 20 сохранённых кандидатов E0; новый поиск не выполняется. В каждом вопросе сравнивается упаковка этого пула до и после reranking, бюджет 2048 неизменен. Требуется локальный завершённый E0 run; при повторении baseline в другом MLflow хранилище передайте его ID через `--source-run`. Проверяются хеши корпуса/разметки и соответствие текстов кандидатов текущим чанкам.

Для E4 тот же скрипт получает сохранённый E2 run и использует первые 20 кандидатов RRF. Режим определяется по параметрам источника; настройки RRF должны совпадать с E2. Контроль без реранкера собирается из тех же RRF20, а не из полного RRF50:

```powershell
uv run --extra cuda python scripts/evaluate_reranker.py --source-run 723f6e95d56a4397ab9166fd2291076e --limit 6 --verify-trace
uv run --extra cuda python scripts/evaluate_reranker.py --source-run 723f6e95d56a4397ab9166fd2291076e
```

E4b проверяет расширение этого пула до 50, сохраняя ту же модель и бюджет контекста. Контроль пересчитывается из RRF50 без реранкинга; это 7100 оценочных пар вместо 2840. E3/E4 по умолчанию сохраняют пул 20:

```powershell
uv run --extra cuda python scripts/evaluate_reranker.py --source-run 723f6e95d56a4397ab9166fd2291076e --candidate-pool 50 --limit 6 --verify-trace
uv run --extra cuda python scripts/evaluate_reranker.py --source-run 723f6e95d56a4397ab9166fd2291076e --candidate-pool 50
```

FP32, batch size 2, лимит пары 1024 токена; превышение вызывает ошибку вместо обрезания. Для CPU: `uv run --extra cpu python scripts/evaluate_reranker.py --device cpu`. Измеряется только reranking + упаковка, без query embedding/search; это не end-to-end latency. Сам реранкер доступен отдельно в `src/football_rules/reranking.py`, онлайн-цепочка поиска с ним пока не подключена.

E10 проверяет тот же Qwen-индекс вместе с BM25. Поиск и RRF сохраняют настройки E2, меняется embedding-модель Dense-ветви:

```powershell
uv run --extra cuda python scripts/evaluate_retrieval.py --strategy hybrid --embedding qwen3-0.6b --collection football_44d75390ffa00dde1b74f0e6 --run-name E10-qwen-hybrid-rrf-v2 --limit 3 --verify-trace
uv run --extra cuda python scripts/evaluate_retrieval.py --strategy hybrid --embedding qwen3-0.6b --collection football_44d75390ffa00dde1b74f0e6 --run-name E10-qwen-hybrid-rrf-v2
```

E11 применяет прежний BGE-reranker к сохранённым top50 E10. Поиск повторно не выполняется, контрольный контекст собирается из той же выдачи без reranking:

```powershell
uv run --extra cuda python scripts/evaluate_reranker.py --source-run b50e71e2d39d4145ae2f7e08fd49416e --candidate-pool 50 --run-name E11-qwen-rrf50-reranker-v2 --limit 6 --verify-trace
uv run --extra cuda python scripts/evaluate_reranker.py --source-run b50e71e2d39d4145ae2f7e08fd49416e --candidate-pool 50 --run-name E11-qwen-rrf50-reranker-v2
```

В другом MLflow-хранилище используйте ID своего полного E10 run. `--run-name` меняет подпись, а проверки source/gold/corpus/fusion сохраняются. Run также записывает `source_embedding_*` для однозначного определения модели первого этапа. Измеряется reranking + упаковка, без поиска; одновременная загрузка Qwen и reranker этим replay не проверяется.

E15 заменяет только reranker на `Qwen/Qwen3-Reranker-0.6B`, revision `e61197ed45024b0ed8a2d74b80b4d909f1255473`, на тех же сохранённых top50 E10:

```powershell
uv run --extra cuda hf download Qwen/Qwen3-Reranker-0.6B --revision e61197ed45024b0ed8a2d74b80b4d909f1255473 --local-dir data/models/qwen3-reranker-0.6b --exclude '*.md' --exclude '.gitattributes'
uv run --extra cuda python scripts/evaluate_reranker.py --source-run b50e71e2d39d4145ae2f7e08fd49416e --candidate-pool 50 --reranker qwen3-0.6b --run-name E15-qwen-rrf50-qwen-reranker-v2 --limit 3 --verify-trace
uv run --extra cuda python scripts/evaluate_reranker.py --source-run b50e71e2d39d4145ae2f7e08fd49416e --candidate-pool 50 --reranker qwen3-0.6b --run-name E15-qwen-rrf50-qwen-reranker-v2
```

Используется встроенная поддержка causal reranker в установленной Sentence Transformers: полный chat template, опубликованная английская инструкция, score = logit(yes) − logit(no). Это оценка релевантности, не вероятность правильного ответа. FP32/batch2, лимит 1024 включает шаблон; превышение вызывает ошибку, обрезания нет. Бюджет контекста остаётся 2048 по прежнему BGE-токенизатору. Для альтернативного reranker обязателен `--run-name`, чтобы не смешивать его с историческими E3/E4. По умолчанию остаётся BGE.

E20 проверяет extractive query вместо свободного переписывания:

```powershell
uv run --extra cuda python scripts/evaluate_retrieval.py --strategy hybrid --embedding qwen3-0.6b --collection football_44d75390ffa00dde1b74f0e6 --extractive-query --run-name E20-qwen-hybrid-extractive-query-rrf-v2 --limit 3 --verify-trace
uv run --extra cuda python scripts/evaluate_retrieval.py --strategy hybrid --embedding qwen3-0.6b --collection football_44d75390ffa00dde1b74f0e6 --extractive-query --run-name E20-qwen-hybrid-extractive-query-rrf-v2
```

Gemini выбирает 1–6 дословных фраз вопроса. Проверка casefold + границы слов/чисел отбрасывает неподходящие или повторные фразы; оставшиеся соединяются через `;`. Если ни одна не подходит, используется исходный вопрос. Принятые/отклонённые фразы и fallback сохраняются в snapshots, счётчики — в MLflow. Проверка не допускает новые слова или вырезание `6` из `2026`, но не гарантирует смысловую полноту выбранных keywords. Исходный вопрос остаётся отдельной веткой; корпус/модель/бюджет и query RRF те же, что E19. Опции `--query-rewrite` и `--extractive-query` взаимоисключающие; без них прежняя цепочка сохраняется. Время API и поиска учитывается отдельно, как в E19.

E19 проверяет один same-language rewrite Gemini 2.5 Flash-Lite вместе с исходным вопросом:

```powershell
uv run --extra cuda python scripts/evaluate_retrieval.py --strategy hybrid --embedding qwen3-0.6b --collection football_44d75390ffa00dde1b74f0e6 --query-rewrite --run-name E19-qwen-hybrid-query-rewrite-rrf-v2 --limit 3 --verify-trace
uv run --extra cuda python scripts/evaluate_retrieval.py --strategy hybrid --embedding qwen3-0.6b --collection football_44d75390ffa00dde1b74f0e6 --query-rewrite --run-name E19-qwen-hybrid-query-rewrite-rrf-v2
```

Нужен существующий `GEMINI_API_KEY` в `.env`. Модель получает только вопрос/язык, без gold, reference или документов. Переформулировки фиксируются до native retrieval evaluation и кэшируются по вопросу/языку/модели/промпту/параметрам в `tmp/query-rewrites/`; snapshots/raw responses/usage записываются в run. Исходный и новый вопрос отдельно проходят прежний Hybrid, их top50 объединяются вторым RRF60, итоговый top50 упаковывается при B=2048. Исходные выдачи обеих веток сохранены. Время `latency_seconds` исключает rewrite API: это поиск по frozen queries + fusion + packing. API latency и новые token usage/стоимость записываются отдельно; cache hit не объявляется ускорением модели. Свободный rewrite экспериментален: ручной аудит выявил изменение условий даже при строгом промпте, поэтому опция не включена по умолчанию.

E18 объединяет два сохранённых порядка одних top50 — E10 Hybrid и E15 Qwen reranker — через RRF60 с равными весами:

```powershell
uv run --extra cuda python scripts/evaluate_reranker.py --source-run b50e71e2d39d4145ae2f7e08fd49416e --candidate-pool 50 --reranker qwen3-0.6b --cached-reranker-run b8b229800f4246d090eea03a4d5c9900 --run-name E18-qwen-retrieval-reranker-rrf60-v2 --limit 3 --verify-trace
uv run --extra cuda python scripts/evaluate_reranker.py --source-run b50e71e2d39d4145ae2f7e08fd49416e --candidate-pool 50 --reranker qwen3-0.6b --cached-reranker-run b8b229800f4246d090eea03a4d5c9900 --run-name E18-qwen-retrieval-reranker-rrf60-v2
```

Ранжирования должны относиться к одному source run, кандидатам и gold. Scores проверяются на конечность и соответствие сохранённому порядку; одинаковые значения разрешаются через chunk ID. E18 использует прежний BM25 без stemming; новых embeddings/LLM/reranker inference нет. Final score = 1/(60 + retrieval_rank) + 1/(60 + reranker_rank); оба исходных ранга и scores сохранены. `fusion_and_pack_seconds` измеряет только пересчёт и упаковку по cached scores: это не end-to-end latency и не ускорение Qwen-реранкера. Без `--cached-reranker-run` прежний режим inference сохраняется.

E17 проверяет Snowball stemming в BM25 при прежнем Qwen Hybrid без reranker:

```powershell
uv run --extra cuda python scripts/evaluate_retrieval.py --strategy hybrid --embedding qwen3-0.6b --collection football_44d75390ffa00dde1b74f0e6 --bm25-stemming --run-name E17-qwen-hybrid-bm25-snowball-v2 --limit 3 --verify-trace
uv run --extra cuda python scripts/evaluate_retrieval.py --strategy hybrid --embedding qwen3-0.6b --collection football_44d75390ffa00dde1b74f0e6 --bm25-stemming --run-name E17-qwen-hybrid-bm25-snowball-v2
```

Зависимость `snowballstemmer==3.1.1` закреплена в lock. Russian/English stemming применяется после прежней Unicode-нормализации одинаково к вопросам и корпусу. Числа/отрицания сохраняются, стоп-слова не удаляются. Без `--bm25-stemming` остаётся прежний BM25. Это экспериментальная опция; стеммеры используются последовательно, один экземпляр не предназначен для конкурентного вызова из нескольких потоков.

E16 заменяет BM25 на BGE-M3 learned sparse при том же Qwen dense, без reranker. Нужны уже загруженный BGE-M3 и его sparse head той же ревизии:

```powershell
uv run --extra cuda hf download BAAI/bge-m3 sparse_linear.pt --revision 5617a9f61b028005a4858fdac845db406aefb181 --local-dir data/models/bge-m3
uv run --extra cuda python scripts/evaluate_retrieval.py --strategy hybrid --lexical bge-m3-sparse --embedding qwen3-0.6b --collection football_44d75390ffa00dde1b74f0e6 --run-name E16-qwen-bge-sparse-rrf-v2 --limit 3 --verify-trace
uv run --extra cuda python scripts/evaluate_retrieval.py --strategy hybrid --lexical bge-m3-sparse --embedding qwen3-0.6b --collection football_44d75390ffa00dde1b74f0e6 --run-name E16-qwen-bge-sparse-rrf-v2
```

Sparse-веса вычисляются через `relu(sparse_linear(last_hidden_state))`, с максимумом для повторных token IDs и исключением CLS/EOS/PAD/UNK. Поиск — скалярное произведение весов совпадающих токенов, без нормализации или инструкции. Используются существующие Transformers/PyTorch, отдельная библиотека FlagEmbedding не устанавливается. Точный поиск по небольшому sparse-индексу выполняется в памяти, dense — через прежний Qdrant. Индекс корпуса кэшируется в `data/sparse/` с fingerprint модели/корпуса/параметров; файл и его checksum фиксируются в артефактах E16. GPU FP32/batch2, лимит 1024 с отклонением переполнения. Обе модели загружаются одновременно; время запроса включает dense + sparse + RRF + упаковку, без построения индекса. Прежние RRF60, depth50, язык и B=2048 сохраняются. В provenance ветка называется `bge_m3_sparse`; BM25 в этом запуске отсутствует. Обычный `--lexical bm25` остаётся default.

E12 сравнивает `intfloat/multilingual-e5-large` в Dense-поиске с E0/E9. Чанки 1000/150, фильтр языка и бюджет 2048 по токенизатору BGE неизменны. Перед вопросом добавляется `query: `, перед документом — `passage: `, включая RU; лимит 512 проверяется с префиксами и специальными токенами, обрезание запрещено. CUDA FP32 / batch 2:

```powershell
uv run --extra cuda hf download intfloat/multilingual-e5-large model.safetensors config.json tokenizer.json tokenizer_config.json special_tokens_map.json sentencepiece.bpe.model sentence_bert_config.json modules.json 1_Pooling/config.json --revision 3d7cfbdacd47fdda877c5cd8a79fbcc4f2a574f3 --local-dir data/models/multilingual-e5-large
uv run --extra cuda football-rules index --embedding multilingual-e5-large
uv run --extra cuda python scripts/evaluate_retrieval.py --embedding multilingual-e5-large --collection football_a6a20a4e7fd525b1c4c7cb69 --run-name E12-dense-multilingual-e5-large-v2 --limit 3 --verify-trace
uv run --extra cuda python scripts/evaluate_retrieval.py --embedding multilingual-e5-large --collection football_a6a20a4e7fd525b1c4c7cb69 --run-name E12-dense-multilingual-e5-large-v2
uv run --extra cuda football-rules search "Можно ли оказаться вне игры после вбрасывания?" --embedding multilingual-e5-large --language ru --collection football_a6a20a4e7fd525b1c4c7cb69 --k 3
```

Имя коллекции относится к закреплённым артефактам — проверяйте вывод `index`. Значение `multilingual-e5-large` доступно во всех трёх командах выбора embeddings; BGE остаётся default. Время E12 можно сопоставлять с Qwen E9 как замеры конфигураций на одном GPU, но не как доказательство ускорения относительно CPU E0.

E13 проверяет приоритет непосредственного продолжения чанка перед упаковкой контекста Qwen Hybrid. Переставляются только уже найденные top50: пул не расширяется, тексты/источники/scores не меняются. Соседи определяются порядком чанков в документе; между страницами требуется следующая страница и начало продолжения с `•`. На один исходный anchor поднимается не более одного successor, без рекурсивного обхода. Бюджет BGE 2048 сохраняется:

```powershell
uv run --extra cuda python scripts/evaluate_retrieval.py --strategy hybrid --embedding qwen3-0.6b --collection football_44d75390ffa00dde1b74f0e6 --context-policy successor_first --run-name E13-qwen-hybrid-successor-v2 --limit 3 --verify-trace
uv run --extra cuda python scripts/evaluate_retrieval.py --strategy hybrid --embedding qwen3-0.6b --collection football_44d75390ffa00dde1b74f0e6 --context-policy successor_first --run-name E13-qwen-hybrid-successor-v2
```

Default `--context-policy rank_order` сохраняет прежнюю упаковку. В E13 `documents` остаётся исходной выдачей, `context_candidates` хранит порядок для сборки контекста; основной и диагностические бюджеты используют эту политику. `context-ordering.json` фиксирует карту соседей. Это эвристика продолжения, не полноценный разбор Law/section; тематически чужой сосед может вытеснить полезный чанк.

E14 ограничивает тот же приоритет только продолжением списка через границу страниц; соседи внутри страницы не переставляются. Пул, модель и бюджет остаются прежними:

```powershell
uv run --extra cuda python scripts/evaluate_retrieval.py --strategy hybrid --embedding qwen3-0.6b --collection football_44d75390ffa00dde1b74f0e6 --context-policy page_continuation --run-name E14-qwen-hybrid-page-continuation-v2 --limit 3 --verify-trace
uv run --extra cuda python scripts/evaluate_retrieval.py --strategy hybrid --embedding qwen3-0.6b --collection football_44d75390ffa00dde1b74f0e6 --context-policy page_continuation --run-name E14-qwen-hybrid-page-continuation-v2
```

## Первая оценка генерации

G0 использует **точные сохранённые контексты E10**, без повторного retrieval. Вопрос и контекст передаются Gemini 2.5 Flash-Lite; эталон доступен только оценщику Ragas. Ключ `GEMINI_API_KEY` задаётся в окружении или локальном `.env` (файл исключён из Git). Команды выполняют реальные API-запросы:

```powershell
uv run --extra cuda python scripts/evaluate_generation.py --limit 3 --verify-trace
uv run --extra cuda python scripts/evaluate_generation.py
```

Вторая команда запускает диагностический пилот из 6 ситуаций RU/EN (12 ответов), а не весь dev. Сохраняются structured answer/status/citations, usage, исходный retrieval run, ответы оценщика и native MLflow metrics. Отдельные API-вызовы Ragas многократно превосходят число ответов: пилот стоил расчётно около $0.02 без smoke-run.

[Журнал генерации](docs/generation-results.md) содержит конфигурацию, метрики и разбор ошибок. Оценщик пока не откалиброван: найдено ошибочное разбиение условий и штрафы за факты из вопроса. Эти метрики не используются для выбора retrieval. `--retrieval-run` позволяет указать совместимый завершённый run с той же разметкой; `--scenario-ids` ограничивает dev-ситуации. По умолчанию используется E10, модель и оценщик — `gemini-2.5-flash-lite`.

G1 проверяет тот же промпт с пустым контекстом, без ключевого evidence и с нерелевантным текстом. Ответы original G0 переиспользуются. Подготовка не вызывает Google API; smoke/full выполняют соответственно 3/36 новых запросов:

```powershell
uv run --extra cuda python scripts/evaluate_context_controls.py --prepare-only
uv run --extra cuda python scripts/evaluate_context_controls.py --limit 3 --verify-trace
uv run --extra cuda python scripts/evaluate_context_controls.py
```

48 записей G1 хранятся в том же MLflow experiment. В текущем пилоте при пустом контексте отказов `insufficient_context` не было, а 11/12 ответов содержали недопустимые ссылки. Подробности подготовки, ручного разбора и ограничения — в [журнале G1](docs/generation-results.md#g1--контроль-поведения-при-отсутствии-доказательств). Промпт и генератор G0 не изменены.

G2 сравнивает строгий prompt на тех же замороженных 48 случаях и проверяет защиту пустого контекста. В обычном `generate_answer` empty-context guard включён по умолчанию: отказ без API и без токенов. Старый режим G1 `--policy original` намеренно обходит guard, чтобы воспроизводить исторический опыт.

```powershell
uv run --extra cuda python scripts/evaluate_context_controls.py --policy strict --prepare-only
uv run --extra cuda python scripts/evaluate_context_controls.py --policy strict --limit 3 --verify-trace
uv run --extra cuda python scripts/evaluate_context_controls.py --policy strict
```

G2: 12 случаев обработаны guard, 36 получили новые ответы, включая original contexts. Guard устранил ответы без источников. Строгий prompt не выбран default: на непустом контексте общего выигрыша нет, обнаружены ошибки формата ссылок и регрессия FR001 EN. Подробности и неизменённые raw metrics — в [журнале G2](docs/generation-results.md#g2--отказ-без-llm-при-пустом-контексте-и-строгий-prompt).

G3 оценивает сохранённые G0/G2 через **Context Precision с reference, Context Recall, Faithfulness и Answer Relevancy**. Новых ответов ассистента нет; API вызывается только судьями. Для Answer Relevancy используется закреплённый локальный BGE-M3, strictness3:

```powershell
uv run --extra cuda python scripts/evaluate_ragas_snapshots.py --limit 3 --verify-trace
uv run --extra cuda python scripts/evaluate_ragas_snapshots.py
```

Полный набор — 60 записей / 240 invocations. Пустые контексты имеют N/A для трёх context-dependent метрик; отказы и answered показаны раздельно. Идентичные judge inputs кешируются с provenance; сырые ответы судьи и usage сохраняются. Кеш может использовать результат предыдущего запуска, поэтому повторный прогон не является новым независимым измерением. Полная оценка со smoke стоила расчётно $0.06449. [Результаты и ограничения G3](docs/generation-results.md#g3--четыре-ragas-метрики-на-сохранённых-ответах).

G4 проверяет выбор ссылок из ограниченного набора ID. Модель выбирает S1/S2/... в enum JSON schema, код отображает их в document_id/pdf_page, неизвестные и повторные ID отклоняются. Режим экспериментальный: исправил формат ссылок, но не выбран baseline из-за регрессии решения FR005 RU.

```powershell
uv run --extra cuda python scripts/evaluate_generation.py --citation-mode source_ids --generate-only --limit 3 --verify-trace
uv run --extra cuda python scripts/evaluate_generation.py --citation-mode source_ids --generate-only
uv run --extra cuda python scripts/evaluate_ragas_snapshots.py --sources G0=aaf7ea28d5bf459db7271fbbf8cdd970 G4=7b50ab660dc84e12af720a62b1d8e3fd --condition original --run-name G4-ragas-source-ids
```

В последней команде закреплён G4-run этого опыта; для своего нового запуска укажите его ID. `--generate-only` пропускает LLM-оценки G0, сохраняя ответы и кодовую проверку ссылок. Snapshot evaluator принимает `--sources LABEL=RUN_ID`, `--condition` и `--run-name`; без них действует прежний G3-набор. [Сравнение G0/G4 и ограничения](docs/generation-results.md#g4--выбор-ссылок-из-ограниченного-набора-source-ids).

## Проверка

```powershell
uv run python -m unittest discover -s tests -v
uv run python scripts/validate_dataset.py --check-sources
```

Проверка датасета с `--check-sources` требует PDF и локального снимка `data/processed/reference-pages.json`. [Инструкция восстановления снимка](data/evaluation/README.md). При отсутствии локальных артефактов соответствующие интеграционные тесты пропускаются; тесты на небольших синтетических PDF работают самостоятельно.

## Датасет

100 ситуаций / 200 вопросов RU/EN, dev/test = 75/25 ситуаций. Эталоны сверены агентом с источниками, без независимой судейской проверки. [Описание и ограничения](data/evaluation/README.md), [все примеры для чтения](docs/dataset-review.md).
