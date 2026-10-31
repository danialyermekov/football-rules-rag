# Football Rules RAG: состояние проекта и дальнейшая работа

Срез на **31 октября 2026 года**, после G13, аудита Q1 и опытов Q2/Q3/E22/E23/E24/E25. Это навигация по реализованному
проекту, принятым решениям, ограничениям и плану. Подробные результаты каждого
опыта находятся в отдельных журналах. Исторические формулировки «пока не
реализовано» в ранних разделах журналов относятся к моменту соответствующего опыта.

Последние опыты: [E21](retrieval-e21-results.md) улучшил CER; [G13](generation-g13-results.md) проверил E21 с Flash/Argon. Argon остановлен перед последним запросом по budget cap; общая часть9 RU/10 EN,285 оценок, смешанные scores. Argon не продвинут; Flash кандидат. Расходы≈$0.2484. Приоритет — проверка judge/reference/decomposition на сохранённых ответах; default сохранён.

[Q1 — аудит оценки](evaluation-q1-results.md), 31.10: 48 frozen snapshots (24 random/24 targeted), 60 слепых reviews и 48 разборов judgments. Подтверждены ошибки decomposition/verifier и ограничения reference/rule-only NLI; это assistant audit, не независимая экспертная калибровка. [Q2](evaluation-q2-results.md) сравнил два старых score с этой разметкой: ни один исследованный порог нельзя считать самостоятельной гарантией правильности. [E22](retrieval-e22-results.md) завершён после устранения QueuePool starvation ограничением конкурентности MLflow: oracle нашёл допустимый комплект для61/71 RU и67/71 EN против E21 55/71 и60/71. Все13 потерь упаковки при полном top50 исправимы в B2048; это gold-aware bound, не новый retriever и не улучшение генерации. Исторические scores/gold/default не менялись, новых provider API calls нет.

[E23 — gold-blind anchor-first](retrieval-e23-results.md): один фиксированный selector без gold-аргументов, RU55/71 без изменения, EN60/71→61/71, регрессий CER нет. Прирост только FR050 EN; альтернативная норма уже была в E21, поэтому улучшение ответов не установлено. 710 native assessments проверены; default сохранён, test и generation не запускались.

[E24 — compaction перекрытий](retrieval-e24-results.md): повторы source characters устранены без потери provenance, но CER остался RU55/71/EN60/71; gate не пройден, кандидат не продвигается. Единственный прирост partial coverage — FR091 RU0→0.6591, недостающий хвост отсутствует в top50. Все710 assessments и lossless source unions проверены; default сохранён.

[E25 — rerank полного union до top50](retrieval-e25-results.md): 7100 старых scores переиспользованы,3960 новых пар оценены локальным Qwen с точным smoke-контролем150 scores. Полнота selected50 RU61→63/71, EN67/71 без изменения, но готовый контекст ухудшился RU55→54/71, EN60→58/71. Gate fail, кандидат не продвигается;710 native assessments проверены, test/Gemini не запускались.

[Q3 — чувствительность к альтернативному evidence](evaluation-q3-results.md): 568 frozen contexts /2272 native assessments. Два сценарно-достаточных официальных фрагмента приняты двумя слепыми AI-reviewers (не экспертом). E21/E24: RU55→56, EN60→61; E23: RU55→56, EN61 без изменения; E25: RU54→55, EN58→59. При одном альтернативном evaluator единственный CER gain E23 над E21 исчезает; регрессии E25 сохраняются. Это изменение измерения, **не улучшение системы**. Старый gold/default/test не изменены; экспертная калибровка pending.

## 1. Цель и текущее состояние

Учебный проект для GitHub: разобраться в RAG Engineering через воспроизводимые
эксперименты и построить ассистента по официальным футбольным правилам RU/EN.
Изменение архитектуры принимается за улучшение только после измерения качества
и разбора ошибок. Отрицательные результаты тоже сохраняются.

**Сейчас работает локальная исследовательская текстовая цепочка:** PDF →
извлечение → очистка → чанки → embeddings/Qdrant → retrieval → контекст →
Gemini → оценка ответов в MLflow. Генерация запускается исследовательскими
скриптами, в том числе на сохранённых контекстах; пользовательский API и веб-чат
ещё не созданы. Анализ изображений, React и production deployment впереди.

| Компонент | Состояние | Где смотреть |
|---|---|---|
| Источники IFAB/RFS 2026/27 RU/EN | Выбраны, скачаны локально, проверены хеши | [Источники](ifab-sources.md), [manifest](source-manifest.json) |
| Датасет | 100 ситуаций / 200 вопросов, 83 evidence | [Описание](../data/evaluation/README.md), [версия для чтения](dataset-review.md) |
| Ingestion и cleaning | Реализованы с привязкой к исходнику | [Ingestion](ingestion.md), [cleaning](cleaning.md) |
| Chunking | Реализован; размер/overlap исследованы | [Описание](chunking.md) |
| Dense/BM25/Hybrid/reranking | Реализованы и измерены | [Retrieval](retrieval.md), [журнал E](retrieval-results.md) |
| Gemini generation | Реализована, исследована на dev | [Модуль](../src/football_rules/generation.py), [журнал G](generation-results.md) |
| CLI для своего вопроса | `football-rules chat` / `ask`, просмотр источников и сохранение ответов | [Команды](../README.md#задать-свой-вопрос-через-cli), [модуль](../src/football_rules/asking.py) |
| Ragas + Gemini judge | Пять метрик, сохранение суждений | [Адаптер](../src/football_rules/ragas_evaluation.py), [скрипт](../scripts/evaluate_ragas_snapshots.py) |
| MLflow | Tracking, datasets, native evaluation, tracing | [Настройки](../src/football_rules/tracking.py) |
| Multimodal/API/UI/Docker | Не реализованы | План в разделе 8 |

## 2. Документы и подготовка корпуса

Используем одну редакцию **2026/27**, два документа:

- EN: официальный IFAB, 260 PDF-страниц.
- RU: официальный перевод РФС, 254 PDF-страницы.

Происхождение, URL, локальные пути и SHA-256 указаны в
[source-manifest.json](source-manifest.json). Работа с редакциями предусмотрена
метаданными; поиск и маршрутизация по нескольким сезонам ещё не реализованы.

Вместо первоначально предложенного PyMuPDF используется **pypdf + fonttools**:
этот extractor закреплён вместе с текстом, по которому размечены evidence.
Его замена требует проверки координат, а не простого пересоздания файлов.

Что сделали:

1. Извлекли страницы, сохранили номера PDF, язык, редакцию и происхождение.
2. Проверяли извлечённый текст относительно страниц PDF.
3. Убрали распознанные колонтитулы/номера, соединили переносы строк; сохранили
   исходный текст и диапазоны удалённых/сохранённых символов.
4. Добавили воспроизводимый chunking через RecursiveCharacterTextSplitter
   из langchain-text-splitters. LangGraph для текущих цепочек не требуется.
5. Сохранили provenance каждого чанка для проверки evidence и цитат.

Текущий канонический корпус: **773 чанка**, 384 EN и 389 RU;
размер 1000 символов, overlap 150, без перехода между страницами.
Символы chunking и токены бюджета контекста — разные единицы.

Код: [ingestion.py](../src/football_rules/ingestion.py),
[cleaning.py](../src/football_rules/cleaning.py),
[chunking.py](../src/football_rules/chunking.py).

## 3. Датасет и методология оценки

Набор написан coding assistant по источникам и проверен относительно документов;
независимой экспертной разметки арбитром нет. Новые вопросы добавлялись до
экспериментов. Охвачены все 17 правил, но не все их подразделы и варианты применения.

- [scenarios.jsonl](../data/evaluation/scenarios.jsonl): вопросы RU/EN,
  reference answers, must_include/must_not_claim, тип и split.
- [evidence.jsonl](../data/evaluation/evidence.jsonl): 83 смысловые единицы с
  координатами в исходных документах.
- [manifest.json](../data/evaluation/manifest.json): версии, хеши, происхождение.
- [dataset-review.md](dataset-review.md): человекочитаемые 100 ситуаций.
- [Пилот оценки](evaluation-pilot.md): исходные решения по постановке оценки.
- [Валидатор](../scripts/validate_dataset.py): структура, связи и источники.

Split по ситуациям: **75 dev / 25 test**; RU/EN одной ситуации не расходятся
между split. Retrieval-оценка использует 71 dev-ситуацию с обязательными evidence,
то есть 142 вопроса; четыре out-of-scope в неё не входят. Test не использовался
для запуска оценок и выбора конфигураций. Dev уже многократно использован,
поэтому его приросты нельзя выдавать за независимую итоговую точность.

### Почему изменили оценку retrieval

При изменении chunking нельзя честно сравнивать только попадание в прежние
chunk IDs. Поэтому перешли к покрытию фиксированных координат источника.

- **Complete Evidence Rate (CER):** все необходимые locators всех evidence
  покрыты контекстом не менее чем на 80% каждый.
- **Evidence Recall / Coverage:** дополнительные оценки полноты.
- **Strict CER:** порог 100%.
- Recall/Precision@K, MRR/NDCG по прежней chunk-разметке оставлены как
  диагностика; они не заменяют независимую от chunking основную оценку.

Протокол: [retrieval-evaluation-v2.md](retrieval-evaluation-v2.md).
Причины пересмотра: [evidence-audit-e0.md](evidence-audit-e0.md).
Реализация: [evidence_evaluation.py](../src/football_rules/evidence_evaluation.py),
[retrieval_metrics.py](../src/football_rules/retrieval_metrics.py).

Разметка содержит проверенные основания, но не все возможные релевантные места.
В G5 нашли случай: CER=0, но во введении было альтернативное подтверждение.
CER не равен ни точности ответа, ни доказательству отсутствия любого основания.

## 4. Что исследовали в retrieval

Полная таблица, параметры, RU/EN, latency, run IDs и ограничения:
[retrieval-results.md](retrieval-results.md). Исследование подходов и ранний план:
[retrieval-experiments.md](retrieval-experiments.md),
[embedding-model-research.md](embedding-model-research.md).
Это исторические планы: фактическое выполнение определяется журналом результатов.

| Опыты | Что проверяли | Итоговое решение |
|---|---|---|
| E0 | BGE-M3 Dense baseline, новый evidence-протокол | Контроль первого цикла |
| E1–E2 | BM25 отдельно и Dense+BM25/RRF | Hybrid полезен; не везде одинаковый эффект |
| E3/E4/E4b | BGE cross-encoder, Dense/Hybrid, кандидаты 20/50 | Есть приросты, дополнительная latency |
| E5–E7 | Размер 600/1600, overlap 0 вместо 150 | Универсального улучшения нет; 1000/150 сохранён |
| E9–E12 | Qwen embeddings, Hybrid, BGE reranker, multilingual-e5-large | E10 выбран быстрым рабочим контролем |
| E13–E14 | Приоритет соседнего продолжения/списка | Смешанные языковые эффекты; не default |
| E15 | Qwen3-Reranker-0.6B поверх Qwen Hybrid | Кандидат качества, не автоматическая замена E10 |
| E16 | BGE-M3 learned sparse вместо BM25 | Хуже E10 на обоих языках |
| E17 | Snowball stemming в BM25 | RU хуже, EN небольшой плюс; не default |
| E18 | Fusion Hybrid ranking и reranker ranking | Не улучшил E15 по CER |
| E19 | Исходный вопрос + свободный Gemini rewrite | Рост CER, но drift фактов; не default |
| E20 | Дословные поисковые фразы с проверкой | Не улучшил контроль; не default |

Номера опыта исторические: строки соответствуют реально записанным запускам,
а не обещанию эксперимента для каждого целого номера.

### Рабочая точка E10 и кандидат E15

| Конфигурация | CER RU | CER EN | Роль |
|---|---:|---:|---|
| E0: BGE Dense | 56,34% | 69,01% | Исторический baseline v2 |
| E10: Qwen Hybrid | 66,20% | 76,06% | Быстрый контроль дальнейших опытов |
| E15: Qwen Hybrid + Qwen reranker | 70,42% | 77,46% | Кандидат качества |

Это 71 ситуация на язык, не выборка generation 20. E15 добавляет p50 rerank+pack
около 5,11s RU/3,65s EN без поиска; E10 search+pack p50≈0,395/0,367s в своём
опыте. Разные границы измерения нельзя складывать как измеренную end-to-end latency.

E10: Qwen3-Embedding-0.6B, 1024 normalized dimensions, Qdrant Local;
Dense50+BM2550 → equal RRF60 → top50 → упаковка целых чанков в 2048 BGE tokens.
RRF60 — константа формулы слияния, а 50 — глубина кандидатов. Это разные параметры.
Бюджет 2048 включает подписи источников; это не предел контекстного окна Gemini.

E10 run `b50e71e2d39d4145ae2f7e08fd49416e`;
E15 run `b8b229800f4246d090eea03a4d5c9900`.
Текущий выбор эксперимента не означает, что все CLI defaults заменены на Qwen:
например, `index/search --embedding` по умолчанию всё ещё bge-m3.

Код: [embeddings.py](../src/football_rules/embeddings.py),
[retrieval.py](../src/football_rules/retrieval.py),
[bm25.py](../src/football_rules/bm25.py), [hybrid.py](../src/football_rules/hybrid.py),
[reranking.py](../src/football_rules/reranking.py),
[sparse_retrieval.py](../src/football_rules/sparse_retrieval.py),
[query_rewriting.py](../src/football_rules/query_rewriting.py).

## 5. Что исследовали в генерации

Источник подробностей: [generation-results.md](generation-results.md).
Генератор получает вопрос, язык, контекст и system prompt. Reference,
must_include/must_not_claim и gold передаются оценке, а не ответчику.
Выход: `status`, `answer`, `citations`; статусы answered, insufficient_context,
needs_clarification. Пустой контекст обрабатывается локальным guard без API.

| Опыт | Что сделали | Что выяснили |
|---|---|---|
| G0 | 12 RU/EN ответов Gemini на E10 | Ошибки применения правил, цитат и лишние утверждения |
| G1 | Пустой, сокращённый и нерелевантный контекст | Модель может отвечать из памяти; статус отказа недостаточен |
| G2 | Строгий grounding prompt и empty guard | Guard полезен; строгий prompt дал другие регрессии и не принят |
| G3 | Четыре метрики Ragas на frozen snapshots | Метрики работают, но не гарантируют правильность решения |
| G4 | Ограниченные source IDs для цитат | Формат улучшился, семантика ответов могла ухудшиться |
| G5 | E10 против E15, 80 ответов, 400 оценок | Более полный контекст не дал убедительной общей победы E15 |
| G6 | Один focused prompt на E10 + 16 контрольных ответов | Выше Factual Correctness, но хуже grounding/цитаты; отклонён |
| G7 | E10 против достаточных исходных фрагментов, 64 ответа | Часть ошибок исправлена, но пропуски и ошибки применения сохраняются |
| G8 | Явные проверки нормы/фактов/последствий, 64 normal + 28 controls | Ключевые ошибки остались, новые регрессии; отклонён |
| G9 | Gemini 3.8 Flash против Lite, 128 normal + 28 controls | Есть исправления и лучшее grounding в controls; метрики смешанные, default сохранён |
| G10 | Argon против обеих Flash, 192 normal + 42 controls | 960/960 scores; смешанные метрики и регрессии неизвестных фактов, default сохранён |

Протоколы: [G5](generation-e10-e15-protocol.md), [G6](generation-g6-protocol.md).
Baseline генерации остаётся **SYSTEM_PROMPT + empty-context guard**,
Gemini 2.5 Flash Lite, temperature 0. Строгий, focused и source-ID варианты
сохранены как измеренные альтернативы, а не принятые улучшения.

### Предыдущий результат G6

Те же 20 ситуаций × RU/EN, только prompt изменён; все 400 оценок получены.

| Метрика | Baseline RU → G6 RU | Baseline EN → G6 EN |
|---|---:|---:|
| Faithfulness | 0,7171 → 0,7258 | 0,7978 → 0,7588 |
| Answer Relevancy | 0,6048 → 0,6260 | 0,6872 → 0,6872 |
| Factual Correctness | 0,6385 → 0,7580 | 0,6135 → 0,7765 |

CP/CR неизменны, потому что контекст прежний. Ответы короче, но в контроле
новый prompt дал 6/8 решений без нужных источников; baseline объявил недостаток
в 8/8, хотя некоторые отказы тоже содержали ошибки. Strict Citation Validity
упала с 16/20 RU и 20/20 EN до 0/40: неверный формат raw ссылок.
Повышение одной метрики не оправдывает эти регрессии.

Итоговый G6 evaluation run: `0b19c33a99ad463cbe917cf278de48ca`.

### Предыдущий результат G7

16 dev-ситуаций RU/EN, 64 свежих ответа с прежним baseline prompt. Достаточные
фрагменты повышают Factual Correctness RU 0,6800→0,7475, EN 0,6513→0,7356,
но парные интервалы включают 0. Устойчивые пропуски предупреждения инициатору
трюка и анатомической границы руки остаются при нужных источниках; есть новая
ошибка объяснения RU. Проблема не сводится к retrieval, defaults не менялись.
[Результат и ограничения](generation-g7-results.md),
[ручной разбор](generation-g7-review.md).

### Предыдущий результат G8

Один evidence-check prompt/schema-кандидат на прежних E10 contexts. Все 320 scores
получены. Factual Correctness RU 0,6800→0,5731, EN 0,6513→0,6663; интервалы включают 0.
Устойчивого улучшения нет: сохранены ошибки адресата санкции и условий, а контроль
с нерелевантным контекстом дал старое правило из памяти. Дословная цитата не
доказывает правильное применение. Candidate отклонён, исходный default сохранён.
[Результат](generation-g8-results.md), [ручной разбор](generation-g8-review.md).

### Последний результат G9

Flash 3.8 с прежним prompt на точных E10 и sufficient contexts. Все 640 scores
получены. Factual Correctness E10 RU 0,6800→0,5938, EN 0,6513→0,7331;
sufficient RU 0,7475→0,8519, EN 0,7356→0,7225. Faithfulness E10 снизилась,
sufficient выросла; парные интервалы включают 0. Ручной разбор подтверждает
исправления санкции инициатору трюка, границы руки и ряда противоречий.
Неподтверждённые нормы irrelevant 2/8→0/8, restarts partial 4/6→0/6.
RU E10 чаще обоснованно отказывается без нужного основания; остаётся проблема
неизвестного характера касания FR069. Перспективный кандидат, default сохранён.
Оценка новых расходов с резервом ошибок ≈$0,22; не фактический billing.
[Результат, runs и бюджет](generation-g9-results.md),
[полный ручной разбор](generation-g9-review.md).

### Последний результат G10

Argon LOW на тех же источниках: 78 новых ответов, 156 baseline snapshots переиспользованы. Все 960 оценок получены после восстановления четырёх пропусков бюджета. Faithfulness выше Flash в трёх группах из четырёх; Factual Correctness выше в двух. Сохраняется grounding контролей, но FR069 RU и FR085 EN дают необоснованные выводы при неизвестных фактах. Стоимость генерации примерно в 3,1 раза выше Flash, latency также выше. Argon не продвигается; default сохранён. Новые расходы ≈$0,425.
[Результат, runs и ограничения](generation-g10-results.md), [ручной разбор](generation-g10-review.md).

## 6. Как оцениваем качество и храним результаты

| Проверка | Смысл | Важное ограничение |
|---|---|---|
| Context Precision with reference | Полезность/порядок контекстных фрагментов | Суждение LLM, не замена координатному gold |
| Context Recall | Поддержка эталонных утверждений контекстом | Может пропускать существенные условия |
| Faithfulness | Поддержка утверждений ответа контекстом | Не гарантирует правильное применение к фактам |
| Answer Relevancy | Соответствие вопросу | Релевантный ответ может быть неверным |
| Factual Correctness | Совпадение с reference, F1 | Не доля полностью правильных решений; зависит от эталона |
| Citation Validity / Integrity | Допустимость ссылок и страниц | Не claim-level semantic Citation Accuracy |
| Контроль и ручной разбор | Неподтверждённые решения, противоречия, неопределённость | Пока без независимого эксперта |

Judge тоже Gemini 2.5 Flash Lite. Relevancy использует локальный BGE-M3 и strictness 3.
Для judge принят JSON Schema режим Instructor; ошибки не заменяются нулями.
Cache помечен явно: reuse не является независимым повторным измерением.

MLflow experiment **football-rules-retrieval**, локальный id 1, объединяет этапы
через теги stage и ссылки на source run. Используются native datasets, scorers,
`mlflow.genai.evaluate`, сохранение prompts/code/hashes, per-question outputs,
judgments, summary, usage и traces. Run ID в журналах устойчивее локального URL.
UI обычно открывается на localhost:5000 после запуска, наличие записи run не
означает, что UI-сервер сейчас работает. База: `data/mlflow/mlflow.db` локально.

Оценка расходов по usage — не фактический счёт Google. Для interrupted/failed
запросов учёт может быть неполным. Итоги G5/G6 не надо складывать без учёта reuse.

## 7. Навигация по коду и воспроизведение

| Задача | Точка входа |
|---|---|
| ingest/clean/chunk/index/search/ask/chat | [CLI](../src/football_rules/__init__.py) |
| Интерактивная сессия и одиночные вопросы | [asking.py](../src/football_rules/asking.py) |
| Retrieval evaluation | [evaluate_retrieval.py](../scripts/evaluate_retrieval.py) |
| Reranker evaluation/replay | [evaluate_reranker.py](../scripts/evaluate_reranker.py) |
| Generation evaluation и G6 controls | [evaluate_generation.py](../scripts/evaluate_generation.py) |
| Исторические G1/G2 interventions | [evaluate_context_controls.py](../scripts/evaluate_context_controls.py) |
| Пять метрик на frozen answers | [evaluate_ragas_snapshots.py](../scripts/evaluate_ragas_snapshots.py) |
| Правила generation/схема ответа | [generation.py](../src/football_rules/generation.py) |
| Ragas judge/embeddings | [ragas_evaluation.py](../src/football_rules/ragas_evaluation.py) |
| Зависимости | [pyproject.toml](../pyproject.toml), [uv.lock](../uv.lock) |
| Тесты | [tests](../tests) |
| Команды и история запусков | [README](../README.md), журналы E/G и протоколы |

Среда проекта: Windows/PowerShell, Python 3.13+, uv, существующая .venv,
CUDA PyTorch на локальном GPU. Для этого окружения используем `--extra cuda`;
`--extra cpu` — отдельный выбор среды, эти extras конфликтуют. Ревизии моделей
и параметры индексов закреплены; нельзя незаметно смешивать разные manifests.

Без запуска платных экспериментов можно проверить датасет:

```powershell
uv run --extra cuda python scripts/validate_dataset.py
```

Запуск оценки Gemini требует локальный GEMINI_API_KEY либо GOOGLE_API_KEY.
Для текущей версии MLflow используем `$env:MLFLOW_DISABLE_TELEMETRY='true'`
как обход проверенного import-hook deadlock; tracking/tracing остаются включены.
Команды конкретного опыта следует брать из его протокола, а не запускать все
исторические варианты README подряд.

PDF, извлечённые тексты, модели, Qdrant, MLflow и tmp исключены из Git:
[.gitignore](../.gitignore). Чистый clone не содержит локальных артефактов
экспериментов; ingestion проверяет уже скачанные PDF и не загружает их сам.
Run IDs доступны в этой локальной MLflow базе; публичного хранилища runs нет.
Изменения сохранялись в тематических ветках и коммитах; локальный коммит сам
по себе не означает push/публикацию на GitHub.

## 8. Дальнейший план

Это очередность работ, а не уже реализованные возможности. Каждый этап
заканчивается проверкой, разбором архитектуры/альтернатив и фиксацией ограничений.

### Ближайший этап: покрытие источников и калибровка оценки

1. Разобрать потерянные основания E10 RU: оборванное продолжение правила,
   отсутствующее определение и неверно выбранный тематический фрагмент.
   Отдельно выбрать один кандидат улучшения контекста, без переписывания gold.
2. Разобрать готовые спорные judgments G9 с экспертом/независимой проверкой.
   Зафиксировать ограничения judge/reference F1 до следующего платного прогона.
3. Flash 3.8 сохранить кандидатом. Следующий протокол — более широкий dev,
   один фиксированный рецепт, ограниченный бюджет и исходный baseline.
4. Разделять отсутствие нормы и отсутствие фактов. Сохранить irrelevant/partial
   controls; отдельно проверять запрос неизвестных фактов и unsupported claims.
5. Формат цитат исследовать отдельно. Не менять одновременно prompt, retrieval,
   модель и citation representation; Argon не обязателен для ближайшего шага.

### После устойчивой генерации

- **Калибровка оценки:** экспертное ревью части references и спорных ответов;
  откалиброванные проверки существенных утверждений, Citation Accuracy и
  Correct Abstention Rate. При необходимости независимый/более сильный judge.
- **Возврат к retrieval по ошибкам:** разбирать потерянное правило, альтернативное
  evidence, ranking и packing отдельно; проверять только обоснованный кандидат.
  Повторный перебор моделей/chunking не является обязательным следующим шагом.
- **Контрольная точка test:** после заморозки конфигурации/метрик один итоговый
  прогон на 25 test-ситуациях. После подбора по test он уже не независимый holdout.
- **API:** FastAPI/Pydantic, интерфейсы сменных retriever/reranker/LLM, реальный
  онлайн-путь query→retrieval→answer, проверки ошибок и измерение полной latency.
- **Multimodal:** отдельные изображение/вопрос → наблюдаемые факты и неизвестное
  → правила → обоснованный ответ. Понадобится отдельная разметка и оценка;
  один кадр часто не устанавливает момент паса, движение и влияние на соперника.
- **UI:** React-чат с языком/редакцией, изображениями, понятными источниками и
  уточнениями. Только после рабочего и проверенного API.
- **Production:** Docker, логирование, health/readiness, timeouts, ограничение
  нагрузки, secrets, стоимость/latency, воспроизводимое развёртывание и
  документированный startup. Внешний deployment пока не выполнен.
- **GitHub/портфолио:** понятный quickstart с источниками и получением моделей,
  выбранные обезличенные результаты, схема архитектуры, честные ограничения и
  сохранённые отрицательные опыты. Публикация — отдельное действие.

## 9. Что нельзя утверждать на текущем этапе

- Что система production-ready или доступна как пользовательское приложение.
- Что метрика judge 0,8 означает 80% правильных решений.
- Что любой CER 0 доказывает отсутствие подходящего текста.
- Что допустимая страница доказывает поддержку каждого утверждения.
- Что status insufficient_context автоматически означает корректный отказ.
- Что RU/EN различия вызваны только LLM: документы, перевод и retrieval тоже различаются.
- Что результаты dev доказывают независимое качество на новых вопросах.
- Что синтетические references проверены профессиональным арбитром.

Актуальные решения: **E10 как быстрый retrieval-контроль, E15 как кандидат;
baseline SYSTEM_PROMPT + empty guard для генерации; focused G6 и checked G8 отклонены;
Flash 3.8 G9 остаётся кандидатом, Argon G10 не продвигается; test сохранён для будущей контрольной точки.**
