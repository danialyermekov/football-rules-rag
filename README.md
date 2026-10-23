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

[Исследование методов улучшения retrieval и план контролируемых экспериментов](docs/retrieval-experiments.md): evidence-based оценка, candidate depth, BM25/hybrid, reranking и chunking. Контроль E0, BM25 E1 и hybrid E2 по протоколу v2 измерены; reranker ещё не запускался.

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

## Проверка

```powershell
uv run python -m unittest discover -s tests -v
uv run python scripts/validate_dataset.py --check-sources
```

Проверка датасета с `--check-sources` требует PDF и локального снимка `data/processed/reference-pages.json`. [Инструкция восстановления снимка](data/evaluation/README.md). При отсутствии локальных артефактов соответствующие интеграционные тесты пропускаются; тесты на небольших синтетических PDF работают самостоятельно.

## Датасет

100 ситуаций / 200 вопросов RU/EN, dev/test = 75/25 ситуаций. Эталоны сверены агентом с источниками, без независимой судейской проверки. [Описание и ограничения](data/evaluation/README.md), [все примеры для чтения](docs/dataset-review.md).
