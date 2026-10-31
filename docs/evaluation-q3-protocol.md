# Q3 — sensitivity к альтернативным официальным evidence

Протокол до нового scoring. Это проверка измерения на уже изученном dev, **не улучшение retrieval, не независимая калибровка и не замена gold**. Ветка: `experiment/q3-alternative-evidence`. Старые scenarios/evidence/references и исторические runs остаются неизменными.

## Вопрос и заранее ограниченный scope

В `evaluation-diagnosis-g13.md` до E23–E25 зафиксированы два возможных альтернативных основания: FR005 RU (введение PDF12), FR050 EN (изменения Law14 PDF182). Проверить только их; после результата не добавлять другие случаи или источники ради повышения score. Не распространять достаточность на другие вопросы, языки или целый broad evidence-unit. Оба примера выбраны после исторического разбора, поэтому наблюдаемый эффект не оценивает распространённость проблемы во всём корпусе.

Для FR005 RU проверить поддержку восьмисекундного предела и углового в заданных фактах. Во введении получатель углового не назван буквально — это отдельное inference/authority limitation, которое рецензент обязан отметить. Для FR050 EN проверить Law14 (не shoot-out Law10), случайность/немедленность/опорную ногу, гол и повтор, без переноса на умышленное касание.

Сформировать отдельный candidate manifest с source spans, text hashes и provenance; не менять `evidence.jsonl`. Два свежих assistant-reviewers получают вопрос, rubric, canonical source text и candidate source page, **без модели, retrieval-contexts и scores**. Они оценивают достаточность для конкретного вопроса, условия/actor/consequence и ограничения. Это два AI-reviews, не независимая экспертиза арбитром. В scoring включать только candidates с согласованным `candidate_sufficient` у обоих; спорные/недостаточные исключить, не искать замену после отказа. Expert review остаётся pending даже при согласии. Сохранить исходные reviews.

## Критерий — OR полных witness sets, не смесь фрагментов

Canonical required evidence остаётся одним полным AND-набором. Каждая принятая альтернатива — ещё один полный AND-набор достаточных оснований **для этой пары scenario/language**. `alternative_complete=any(complete(option))`; внутри option все units/locators по-прежнему AND, порог80% прежний. Для strict —100%. Нельзя собрать «достаточность» из половины canonical и половины alternative. Валидировать все options даже при уже полном canonical. При отсутствии альтернатив критерий должен точно совпадать с v2.

Не интерпретировать изменение scores между версиями разметки как improvement системы. Не использовать максимум coverage отдельных options как откалиброванный непрерывный quality score. Здесь считаются только binary CER/Strict CER до/после, bounds неэкспертной гипотезы и конкретные изменения.

## Frozen данные и запуск

Только142 dev contexts каждого из FINISHED E21 `174a45eee3c243e2a7bf21be9ddd7bae`, E23 `005cc004be224106af364013e5dd3c64`, E24 `ca86f33245c343869dcd0eacfe879895`, E25 `a5cd577ec6184069ae7060f95bbebe08`: всего568 snapshots. Никаких новых contexts, packing, model/GPU inference, API, test-evaluation или корректировки ответов. E24 оценивается по фактическим merged source spans, не по parent IDs. Source/annotation/code/review hashes зафиксировать до scoring, после проверить неизменность.

Native MLflow dataset discovery/reuse/create, `to_df()` и deep copy при merge. Отдельный analysis/evaluation run, native `mlflow.genai.evaluate` с четырьмя source-controlled deterministic scorers: canonical CER, candidate-alternative CER, canonical strict, candidate-alternative strict. Persistent custom scorer registration не включать. Predict — только replay сохранённого context по snapshot ID; gold/option sets остаются evaluator. Включить tracing, telemetry disabled, workers1/1.

Smoke3 — заранее E21 FR005 RU, E21 FR050 EN и E21 FR001 RU (контроль без alternative),12 assessments; одно trace readback≤60s. Этот targeted smoke только technical. Full568 — только после FINISHED matching smoke и после фиксации approved manifest/reviews/code в Git. Внешние deadlines smoke120s/full300s; ошибок/undefined scores не заменять нулями. Все2272 full assessments должны быть finite, canonical exact-match со старым run, optional score≥canonical по конструкции. По всем непокрытым manifest случаям exact equality.

## Reporting и граница вывода

Показать по каждому frozen method RU/EN counts/means old vs candidate version, исходные ranking differences между methods при одном и том же evaluator, все изменившиеся snapshot IDs и принятый complete witness. Если улучшение E23 над E21 исчезнет при alternate evidence, это sensitivity прежнего сравнения, не доказанная эквивалентность систем. Если существенного эффекта нет/alternatives rejected — так и записать. Не выбирать победителя и не менять defaults; expert calibration pending. Документы/кеши/старые scores не переписывать. Provider calls/cost0; работа assistants в редакторе в эту стоимость не входит.
