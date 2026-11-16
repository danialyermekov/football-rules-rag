# Football Rules RAG

Двуязычный (RU/EN) RAG-ассистент по официальным футбольным правилам **IFAB Laws of the Game 2026/27**.

Проект построен как учебно-инженерная система: с полным локальным пайплайном обработки PDF, гибридным поиском (Dense + BM25 + RRF), опциональным cross-encoder reranker, строгим JSON-ответом Gemini со ссылками на страницы и воспроизводимой оценкой качества.

## Архитектура

```text
PDF (IFAB EN + РФС RU)
  └─► ingest ─► clean ─► chunk (1000 симв., overlap 150, 773 чанка)
                            │
              ┌─────────────┴─────────────┐
              ▼                           ▼
     Qwen3-Embedding-0.6B          BM25 Okapi
       (Qdrant Local)             (in-memory)
              └─────────────┬─────────────┘
                            ▼
              Reciprocal Rank Fusion (RRF60, k=50)
                            │
                            ▼ (опционально --rerank)
                  Qwen3-Reranker-0.6B
                            │
                            ▼
             Context Packing (бюджет 2048 токенов)
                            │
                            ▼
           Gemini (JSON: status, answer, citations)
```

- Подробное описание модулей и решений: [docs/architecture.md](docs/architecture.md)
- Сводка проведённых экспериментов (`E0–E25`, `G0–G13`, `Q1–Q4`): [docs/experiments-summary.md](docs/experiments-summary.md)

## Быстрый старт

Требования: **Python 3.13+**, [uv](https://docs.astral.sh/uv/) и ключ Google Gemini API.

### 1. Установка зависимостей и окружения

```powershell
# Для CPU:
uv sync --locked --extra cpu

# Или для NVIDIA GPU (CUDA):
uv sync --locked --extra cuda

# Настройка API-ключа:
Copy-Item .env.example .env
# Укажите GEMINI_API_KEY=... в файле .env
```

### 2. Подготовка исходных PDF и локальных моделей

Исходные PDF и веса моделей не хранятся в Git (см. [docs/ifab-sources.md](docs/ifab-sources.md)).

1. Скачайте два PDF (2026/27 EN и RU) по ссылкам и путям из [docs/source-manifest.json](docs/source-manifest.json):
   - `data/raw/ifab-laws-2026-27-en.pdf`
   - `data/raw/rfs-laws-2026-27-ru.pdf`
2. Скачайте pinned-ревизию основной embedding-модели для `ask`/`chat` (`Qwen/Qwen3-Embedding-0.6B`):

```powershell
uv run --no-sync hf download Qwen/Qwen3-Embedding-0.6B `
  config.json model.safetensors tokenizer.json tokenizer_config.json `
  config_sentence_transformers.json modules.json 1_Pooling/config.json `
  --revision 97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3 `
  --local-dir data/models/qwen3-embedding-0.6b
```

*(Опционально для режима `--rerank` скачайте `Qwen/Qwen3-Reranker-0.6B` ревизии `e61197ed45024b0ed8a2d74b80b4d909f1255473` в `data/models/qwen3-reranker-0.6b`.)*

### 3. Сборка корпуса и индекса

```powershell
uv run --no-sync football-rules ingest
uv run --no-sync football-rules clean
uv run --no-sync football-rules chunk
uv run --no-sync football-rules index --embedding qwen3-0.6b
```

## Использование CLI

### Интерактивный чат (`chat`)

Загружает индекс и модель эмбеддингов один раз при старте:

```powershell
uv run --no-sync football-rules chat
uv run --no-sync football-rules chat --language en --model gemini-3.8-flash
uv run --no-sync football-rules chat --rerank
```

Команды внутри чата:
- `/sources` (`/источники`) — показать фрагменты контекста последнего ответа с пометкой `[cited]`;
- `/save [заметка]` (`/сохранить`) — сохранить вопрос, источники и ответ в `tmp/saved-questions.jsonl`;
- `/model [имя]` — переключить модель (`gemini-2.5-flash-lite`, `gemini-3.8-flash`, `gemini-4-argon`);
- `/lang [ru|en]` — переключить язык вопросов;
- `/help` / `/exit`.

### Одиночный вопрос (`ask`)

```powershell
uv run --no-sync football-rules ask "Можно ли забить гол непосредственно с вбрасывания?"
uv run --no-sync football-rules ask "Вратарь держал мяч девять секунд. Что назначить?" --sources
uv run --no-sync football-rules ask "Can a player be offside directly from a throw-in?" --language en --json
```

Ответ всегда имеет структуру `{status, answer, citations}`:
- `answered` — ответ подтверждён фрагментами контекста со ссылками `document_id:pdf_page`;
- `needs_clarification` — правило найдено, но в описании эпизода не хватает фактов;
- `insufficient_context` — в контексте нет достаточных оснований (пустой контекст отсекается локально до вызова API).

## Ключевые результаты экспериментов

На dev-выборке (71 ситуация, 142 вопроса RU/EN, бюджет 2048 токенов, метрика **Complete Evidence Rate**):

| Конфигурация | CER RU | CER EN | Роль |
|---|---:|---:|---|
| Dense (`BAAI/bge-m3`, E0) | 56.34% | 69.01% | Исторический baseline |
| BM25 Okapi (E1) | 59.15% | 70.42% | Lexical baseline |
| **Hybrid (`Qwen3-0.6B` + BM25 + RRF60, E10)** | **66.20%** | **76.06%** | **Рабочий default в CLI** |
| Hybrid + `Qwen3-Reranker-0.6B` (E15) | 70.42% | 77.46% | Опциональный режим `--rerank` |

Подробнее обо всех циклах (включая неудачные гипотезы вроде query rewriting, stemming, learned sparse и сравнения промптов/моделей Gemini) — в [docs/experiments-summary.md](docs/experiments-summary.md). Полная исследовательская история сохранена в git-теге `archive/research-experiments`.

## Структура проекта

```text
src/football_rules/
├── config.py               # Конфигурация по умолчанию
├── io.py                   # Атомарное чтение/запись JSONL
├── cli.py                  # CLI: ingest, clean, chunk, index, search, ask, chat
├── ingestion/              # PDF extraction (pypdf), очистка, чанкинг с provenance
├── retrieval/              # Embeddings, Qdrant store, BM25, RRF hybrid, reranker, context packing
├── generation/             # Grounded Gemini + JSON schema + валидация ссылок
├── app/                    # AskSession и интерактивный chat loop
└── evaluation/             # CER-метрики, Recall@K/MRR/NDCG, Ragas, API budget, MLflow
scripts/
├── validate_dataset.py     # Проверка консистентности 100 сценариев и 83 evidence
├── evaluate_retrieval.py   # Оценка стратегий поиска в MLflow
└── evaluate_generation.py  # Оценка генерации и Ragas-метрик в MLflow
data/evaluation/            # 100 RU/EN сценариев (75 dev / 25 test) и evidence-координаты
docs/                       # Архитектура, сводка экспериментов и описание источников IFAB
tests/                      # Unit-тесты (работают без PDF, весов моделей и API-ключей)
```

## Тесты и проверка датасета

```powershell
$env:MLFLOW_DISABLE_TELEMETRY='true'
uv run --no-sync python -m unittest discover -s tests -v
uv run --no-sync python scripts/validate_dataset.py
```

Для оценки retrieval/generation в MLflow используются скрипты в `scripts/`:

```powershell
uv run --no-sync python scripts/evaluate_retrieval.py --strategy hybrid --embedding qwen3-0.6b --collection <имя_коллекции> --limit 3
uv run --no-sync python scripts/evaluate_generation.py --retrieval-run <run_id> --limit 3
```

## Ограничения и авторские права

- Текущий индекс работает только с текстом редакции **IFAB 2026/27** (мультимодальный анализ изображений и веб-интерфейс ещё не реализованы).
- Оценочный датасет составлен и сверен с PDF с помощью coding assistant; независимая экспертиза профессиональным футбольным арбитром не проводилась.
- Исходные PDF правил IFAB/РФС защищены авторским правом издателей и не включены в репозиторий. Код проекта распространяется по лицензии [MIT](LICENSE).
