# Football Rules RAG

Учебный проект ассистента по футбольным правилам IFAB. Реализованы извлечение и очистка текста PDF, baseline-чанкинг, локальные embeddings BGE-M3 и dense retrieval через Qdrant Local. Подготовлен датасет оценки и скрипт retrieval evaluation в MLflow. Генерация ответов пока не подключена.

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

## Проверка

```powershell
uv run python -m unittest discover -s tests -v
uv run python scripts/validate_dataset.py --check-sources
```

Проверка датасета с `--check-sources` требует PDF и локального снимка `data/processed/reference-pages.json`. [Инструкция восстановления снимка](data/evaluation/README.md). При отсутствии локальных артефактов соответствующие интеграционные тесты пропускаются; тесты на небольших синтетических PDF работают самостоятельно.

## Датасет

100 ситуаций / 200 вопросов RU/EN, dev/test = 75/25 ситуаций. Эталоны сверены агентом с источниками, без независимой судейской проверки. [Описание и ограничения](data/evaluation/README.md), [все примеры для чтения](docs/dataset-review.md).
