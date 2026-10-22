# Football Rules RAG

Учебный проект ассистента по футбольным правилам IFAB. Сейчас реализованы постраничное извлечение, консервативная очистка текста PDF и baseline-чанкинг, подготовлен датасет оценки. Embeddings, векторная база, поиск и генерация ответов ещё не подключены.

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

[Как работает разбиение, примеры RU/EN, результаты и ограничения](docs/chunking.md). Изменение параметров пока не считается измеренным улучшением: оценка retrieval и запись экспериментов в MLflow появятся после подключения поиска.

## Проверка

```powershell
uv run python -m unittest discover -s tests -v
uv run python scripts/validate_dataset.py --check-sources
```

Проверка датасета с `--check-sources` требует PDF и локального снимка `data/processed/reference-pages.json`. [Инструкция восстановления снимка](data/evaluation/README.md). При отсутствии локальных артефактов соответствующие интеграционные тесты пропускаются; тесты на небольших синтетических PDF работают самостоятельно.

## Датасет

100 ситуаций / 200 вопросов RU/EN, dev/test = 75/25 ситуаций. Эталоны сверены агентом с источниками, без независимой судейской проверки. [Описание и ограничения](data/evaluation/README.md), [все примеры для чтения](docs/dataset-review.md).
