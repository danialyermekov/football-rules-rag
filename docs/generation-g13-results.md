# G13 — E21 + Flash/Argon: ограниченный пилот, 28.10.2026

**Решение: не продвигать Argon; Flash оставить кандидатом.** Исправления применения правил видны у обеих моделей, но средние автоматические оценки смешанные. Argon дороже/медленнее, устойчивого общего выигрыша нет. Результат неполный из-за заранее заданного cap, default сохранён.

[Протокол и отклонение](generation-g13-protocol.md), [разбор ответов](generation-g13-review.md), [диагностика judge](evaluation-diagnosis-g13.md).

## Scope и бюджет

Планировались10 dev-ситуаций × RU/EN на прежних E21 контекстах, новый Flash3.8 и Argon против сохранённого Lite G12, плюс4 frozen G8 controls на модель. SYSTEM_PROMPT/Answer/context неизменны. Flash LOW/temp0/output2048; Argon LOW/no temperature/output32768; Lite G12 temp0/output1024. Сравниваются готовые model/config recipes.

Flash получил24/24 новых ответа; Argon23/24. Не отправлен FR069 RU normal: учтённые$0.14556 + максимальный резерв$0.36381 = $0.50937 > cap$0.50. Cap не повышен, новый ответ не запрашивался с меньшим ceiling. Все47 успешных новых ответов сохранены, включая6 переиспользованных smoke outputs. Нет ошибок API или скрытых retries; блокировка до API.

Исходный full run FAILED с71/72 snapshots. Отдельный no-API recovery сохраняет59 normal+12 controls с тегом partial_budget_stopped. Это не завершённый исходный план. Для парных метрик исключён FR069 RU у всех трёх моделей: **9 RU/10 EN вопросов**,57 snapshots,285 scores. Пропуск зависит от стоимости/длины входа; complete-case таблица exploratory. Её нельзя сравнивать напрямую с G12 на20 вопросах языка.

## Пять метрик на общей части

Все285 значений конечны/status=ok,180 assessments reused. CP/CR совпадают между тремя моделями по значениям и cache keys каждого вопроса. Native MLflow means совпадают с assert-readback. Factual Correctness — reference F1, не процент правильных судейских решений.

| Метрика | Lite RU | Flash RU | Argon RU | Lite EN | Flash EN | Argon EN |
|---|---:|---:|---:|---:|---:|---:|
| context_precision | 0.8497 | 0.8497 | 0.8497 | 0.7016 | 0.7016 | 0.7016 |
| context_recall | 1.0000 | 1.0000 | 1.0000 | 0.9667 | 0.9667 | 0.9667 |
| faithfulness | 0.7460 | 0.6579 | 0.6843 | 0.7417 | 0.8607 | 0.8018 |
| answer_relevancy | 0.6426 | 0.6548 | 0.6014 | 0.5170 | 0.6651 | 0.7232 |
| factual_correctness | 0.7100 | 0.6433 | 0.5933 | 0.6630 | 0.7930 | 0.6100 |

Парные differences Factual Correctness и95% bootstrap CI (2000,seed42,9/10 ситуаций, одни resamples для моделей внутри языка):
- flash_minus_lite_ru: Δ-0.0667, CI[-0.3077777777777778, 0.19].
- flash_minus_lite_en: Δ+0.1300, CI[-0.025000000000000012, 0.308].
- argon_minus_lite_ru: Δ-0.1167, CI[-0.2988888888888889, 0.10333333333333333].
- argon_minus_lite_en: Δ-0.0530, CI[-0.275, 0.16999999999999998].
- argon_minus_flash_ru: Δ-0.0500, CI[-0.2666666666666667, 0.17555555555555555].
- argon_minus_flash_en: Δ-0.1830, CI[-0.303, -0.06800000000000003].

Argon−Flash EN имеет отрицательный интервал в этом selected subset. Это не доказательство общего ранжирования моделей: dev многократно изучен, размер мал, пропуск post-budget, шум judge/референсов и множественные сравнения не учтены.

## Смысловые результаты и оценщик

Обе модели исправили FR005 RU (угловой по вводному разделу), FR009 RU (исключение санкций не перенесено на обычный пас), FR065 EN (анатомическая граница), FR094 EN (нет противоречивого свободного) и FR095 RU/EN (предупреждение инициатору). Не все уточнения фактов сделаны: FR010/069/085 часто answered с корректными условными ветками, без прямого уточняющего вопроса. Argon FR069 RU отсутствует, именно на этом важном случае утверждать улучшение нельзя. Argon чаще добавляет лишние ветки; Flash обычно короче.

Низкие автоматические scores не всегда равны неверному решению. Проверены raw judgments трёх низких Argon FC: FR005 EN штрафует верные подробности, отсутствующие в коротком reference; FR050 RU дублирует claims и частично неверно читает reference; FR094 RU меняет actor/action при decomposition. Эти examples не объясняют всё снижение средних. Scores не пересчитаны и references не расширены посреди опыта. Детали и cache keys в отдельной диагностике.

На4 controls каждой сильной модели4/4 insufficient_context, неподтверждённых целевых решений в ручном разборе нет. Исторический Lite3/4 отказа: FR005 RU partial давал ошибочный свободный и девятисекундный порог. Это четыре selected checks, не общая Correct Abstention Rate. Отдельные номера Law из памяти встречаются и в отказах.

| Вариант | RU answered/clarification/insufficient | EN answered/clarification/insufficient | RU/EN valid citations | RU/EN generation p50,s |
|---|---|---|---|---|
| lite | 5/3/1 | 8/2/0 | 8/9;10/10 | 1.163/0.981 |
| flash | 7/2/0 | 9/1/0 | 9/9;10/10 | 3.394/2.945 |
| argon | 8/1/0 | 9/1/0 | 9/9;10/10 | 6.293/5.592 |

Citation validity проверяет доступность страниц, не смысловую поддержку. Latency только generation, не online retrieval; Lite исторический, новые модели выполнялись в разных запросах без повторного нагрузочного измерения.

## Расходы и воспроизводимость

| Категория | Успешные вызовы/резервы | Usage estimate USD |
|---|---:|---:|
| flash | 24 ledger entries; pending0 | 0.04992075 |
| argon | 23 ledger entries; pending0 | 0.14556000 |
| judge | 114 ledger entries; pending0 | 0.05291510 |

**Всего новых расходов≈$0.24839585**, при ceiling$0.85. Judge ledger entries — metric assessments/reservations, а не число HTTP calls. Непогашенных резервов нет. Другие балансы/скидки не учтены; это расчёт по reported usage и Standard prices, не проверенный счёт Google. [Тарифы](https://ai.google.dev/gemini-api/docs/pricing) проверены28.10.2026. Все дальнейшие новые платные вызовы этого цикла остановлены.

- Generation smoke cdfb79f0b5474012bcb6d8fb0e1c1b81 FINISHED;6 новых API responses reused в full, trace CHAIN/RETRIEVER/LLM прочитана.
- Full5c321249de7045bcb0c37b4487efe74a FAILED по budget cap,71 outputs сохранены.
- No-API recovery4f883b225a9e46d68da5c0898f8244a2 FINISHED с явной пометкой partial.
- Judge smoke9fb03a068fc54a05bdf688d896419131 FINISHED,15/15; trace tr-9e35822fe25189368abb1af03ed053db CHAIN/LLM прочитана.
- Evaluation3f506b8e79514157bdea51749c57b261 FINISHED,285/285.

Native MLflow datasets/scorers/evaluate/tracing и exact-input cache. Readback/assert проверил71 сохранённый snapshot,57 парных normal inputs/expectations/contexts, baseline reuse, CP/CR cache equality,285 finite scores и native means. Budget-stop proof, сборщик partial outputs, comparison/analyzer, raw answers и ledgers сохранены в артефактах. Никаких изменений test/gold/references. Прошли142 unittest tests, Ruff/Black, py_compile, prepare-only assertions и реальные smoke/full. Strict mypy нового исследовательского скрипта не запускался.

## Что делать дальше

Не расширять Argon сейчас. Flash дешевле и исправляет основные замеченные ошибки, но не считать RU/EN качество доказанно выше без надёжной оценки. Ближайшая работа без новой генерации — аудит claim decomposition и критериев reference coverage на более широкой сохранённой выборке; затем отдельная версия judge/методики. Для независимой калибровки требуется экспертная проверка. Test остаётся отложенным.
