# Q1 — аудит сохранённой оценки, протокол 31.10.2026

Статус до отбора: исследовательский аудит coding assistants, **не независимая экспертная калибровка**. Пользователь разрешил только первый эксперимент; после Q1 остановиться. Новые вызовы Gemini/embeddings/retrieval запрещены. Работа рецензентов в редакторе не является бесплатным внешним экспертным трудом; $0 ниже относится только к новым provider API experiments.

## Вопрос

Какие расхождения обусловлены ошибкой ответа, ошибкой decomposition/verifier, краткостью reference или несовпадением измеряемого конструкта (поддержка утверждений против полноты решения)? Не пересчитывать исторические scores и не выбирать новую модель/default.

## Источники

Frozen per-question-results.json и judgment-cache из четырёх native MLflow evaluation runs:

- G10: `88d58a2bd1c442a4a5f4172b4ffabdf5` (включает прежние Lite/Flash).
- G11: `39b9184f90be4c30a75e87ebfc33bd7d`.
- G12: `f434ef6d599f485192878bf58551eb75`.
- G13: `3f506b8e79514157bdea51749c57b261` (только сохранённая общая часть).

Только dev normal, не test/controls. Дедупликация по SHA-256 canonical JSON: question, language, status, answer, citations, ordered context document_id/page/text, expectations. При повторе — первый run в указанном порядке; остальные occurrences сохранить. Идентичный output на другом контексте — другой объект. Проверить exact cache payload inputs перед использованием raw judgments. Проверен существующий judge trace `tr-9e35822fe25189368abb1af03ed053db`, 5 spans; это readback исторической trace, не новая runtime-проверка.

## Отбор до ревью

48 уникальных объектов, фиксированный seed 20261031, sorted fingerprint population.

1. Random: random.sample по 12 RU/EN без использования scores, модели или статуса.
2. Targeted: среди оставшихся по 12 RU/EN из FR001/005/009/010/037/050/065/068/069/085/094/095. Приоритет объектов с Faithfulness=1 или Factual Correctness<=0.6; затем SHA-256(seed + fingerprint). Это явно score-enriched диагностическая часть, не случайная выборка.
3. Смешать выбранные объекты seeded shuffle и присвоить Q001–Q048. Рецензентам не сообщать stratum, scenario ID, run, model, condition, scores или selection priority. Не включать token usage/latency/retrieval scores.

Random относится к популяции сохранённых unique snapshots, не пользователей, футбольных правил или независимых ситуаций. RU/EN и варианты одного сценария зависимы. Интервалы точности judge и ранжирование моделей по этим данным не строить.

## Двухэтапное ревью

Phase A: три свежих subagents получают непересекающиеся 16 объектов и дополнительно общие 6 объектов (первые 2 каждого блока). Итого по 20 объектов, 60 reviews. Это частичное ослепление: модель можно угадать по стилю, prompts/источники общие, обучение и семейство reviewer-моделей не независимы. Каждый сохраняет JSON до раскрытия scores.

По каждому объекту true/false/null:
- `decision_correct`: корректность ответа по фактам и источникам; обоснованный отказ допустим. Null при неразрешимой интерпретации.
- `required_consequences_complete`: все существенные применимые последствия; отказ оценивается по честности отсутствующей поддержки, не требованию выдумать restart.
- `claims_grounded`: существенные утверждения поддержаны контекстом плюс факты QUESTION. Отсутствие повторения факта в CONTEXT не само по себе ошибка.
- `clarification_policy_met`: достаточная обработка неизвестности; условно верный ответ без прямого вопроса отличать от неверного категорического решения.
- `citations_support`: поддерживают ли приведённые фрагменты существенные выводы; null при уместном отказе без citations.
- `critical_error`: неверное существенное решение/actor/санкция/противоречие, а не косметический формат.
- `notes`: конкретные цитаты/страницы и основания; спорные детали помечать, reference не считать безошибочным.

Phase B: после сохранения Phase A раскрыть только соответствующие saved scores и полные parsed/raw judgments. Каждый reviewer аудирует свои основные 16 объектов. Отдельно по Faithfulness и Factual Correctness записать:
- `decomposition_error`, `verification_error`, `reference_limitation`, `construct_mismatch` (bool);
- `evidence`: точные проблемные claims/verdict/reason и объяснение, либо явно «не обнаружено»;
- не называть корректный низкий F1 ошибкой verifier только за несовпадение с нужной нам метрикой.

Основной review принадлежит reviewer своего блока. Расхождения common-six не разрешать молча: сохранить исходные reviews, отдельно описать; при споре использовать conservative/uncertain вывод. Не менять labels задним числом под scores.

## Анализ и gate

Раздельно random/targeted: количество выявленных механизмов по обеим метрикам; описательные cross-tabs. Пороговые probes (FC>=0.8, Faithfulness=1) — только диагностика, **не исходная семантика метрик**. Отдельно показать, как Faithfulness=1 сосуществует с пропуском обязательного последствия: это construct mismatch, не обязательно сбой judge.

Один конкретный подтверждённый дефект достаточен для рекомендации regression fixture; не достаточен для оценки распространённости или смены judge. Не исправлять scorer/reference в рамках Q1: результат — артефакты, отчёт и точная рекомендация будущей версии. Если эксперта нет, статус «expert calibration pending» обязателен.

## Сохранение и проверки

Создать новый MLflow audit run, приложить protocol, source checksums, selection manifest, blinded packets, исходные Phase A/B reviews, сводку и report. Это ручной аудит существующих native evaluations, не новый LLM scorer и не повторный mlflow.genai.evaluate. Новые scorer APIs/платные вызовы не нужны. Сохранить компактный review/manifest и отчёт в docs. Проверить 48 unique/dev объектов, 24+24, 24+24 языков, 60 Phase A reviews, 48 Phase B reviews, exact cache inputs, все исходные хеши неизменны. После Q1 остановиться.
