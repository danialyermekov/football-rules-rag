# Архитектура Football Rules RAG

Этот документ объясняет, как устроен RAG-пайплайн в проекте — от исходного PDF до ответа с указанием страниц.

## Общая схема

```text
IFAB / RFS PDF (2026/27, EN + RU)
   │
   ▼  [ingestion/pdf.py]        постраничное извлечение текста (pypdf) + SHA-256 проверка
pages.jsonl
   │
   ▼  [ingestion/cleaning.py]   удаление колонтитулов/номеров страниц, склейка переносов
cleaned-pages.jsonl
   │
   ▼  [ingestion/chunking.py]   разбиение на чанки (1000 символов, overlap 150) с provenance
chunks.jsonl (773 чанка: 384 EN + 389 RU)
   │
   ├─────────────────────────────────────────┐
   ▼                                         ▼
[retrieval/embeddings.py + store.py]    [retrieval/bm25.py]
Dense: Qwen3-Embedding-0.6B -> Qdrant   Lexical: BM25 Okapi (k1=1.2, b=0.75)
   │                                         │
   └─────────────────┬───────────────────────┘
                     ▼
            [retrieval/hybrid.py]
            Reciprocal Rank Fusion (RRF60, ветви по 50 кандидатов)
                     │
                     ▼  (опционально --rerank)
            [retrieval/reranking.py]
            CrossEncoderReranker (Qwen3-Reranker-0.6B)
                     │
                     ▼
            [retrieval/context.py]
            pack_context: сборка целых чанков в бюджет 2048 токенов
                     │
                     ▼
            [generation/gemini.py]
            Gemini + SYSTEM_PROMPT -> JSON {status, answer, citations}
                     │
                     ▼
            [app/chat.py + cli.py]
            CLI команды `ask` и `chat` + проверка допустимости ссылок
```

## Слои и модули (`src/football_rules/`)

| Слой | Файлы | За что отвечает |
|---|---|---|
| Конфигурация и I/O | `config.py`, `io.py`, `cli.py` | Пути, параметры по умолчанию, атомарная запись JSONL, CLI-команды |
| Ingestion | `ingestion/pdf.py`, `cleaning.py`, `chunking.py` | Чтение PDF по манифесту, очистка страниц с сохранением координат исходного текста, чанкинг |
| Retrieval | `retrieval/embeddings.py`, `store.py`, `bm25.py`, `hybrid.py`, `reranking.py`, `context.py` | Локальные эмбеддинги, Qdrant Local, BM25, RRF-слияние, опциональный reranker, упаковка контекста |
| Generation | `generation/gemini.py` | Запрос к Gemini с JSON-схемой (`answered`, `insufficient_context`, `needs_clarification`), защита от пустого контекста и валидация `citations` |
| App | `app/chat.py` | `AskSession` (единоразовая загрузка моделей/индекса), команды `ask` и интерактивный цикл `chat` (`/sources`, `/save`, `/model`, `/lang`) |
| Evaluation | `evaluation/evidence.py`, `ranking.py`, `ragas_adapter.py`, `budget.py`, `tracking.py` | Подсчёт Complete Evidence Rate (CER) по координатам текста, Recall@K/MRR/NDCG, Ragas-судьи, лимит расходов API и MLflow |

## Ключевые инженерные решения

1. **Провенанс на уровне символов (provenance).** Каждый чанк хранит `document_id`, `pdf_page`, `printed_page` и `source_spans` в исходной странице. Это позволяет считать покрытие правил независимо от выбранного размера чанка и проверять, что LLM сослалась на реально переданные страницы.
2. **Оценка поиска через Complete Evidence Rate (CER).** Вместо жёсткой привязки к ID старых чанков оценка проверяет, покрывает ли собранный контекст ≥80% непробельных символов каждого необходимого фрагмента правила.
3. **Защита от галлюцинаций на уровне кода.**
   - При пустом контексте `generate_answer` возвращает `insufficient_context` локально, без вызова API.
   - `valid_citations` проверяет, что все ссылки (`document_id:pdf_page`) уникальны и действительно присутствовали в переданном контексте.
4. **Разделение рабочего кода и оценочного контура.** `ask` и `chat` используют единый путь `HybridRetriever` → (опционально `CrossEncoderReranker`) → `pack_context` → `generate_answer`, не смешиваясь со скриптами оценки.
