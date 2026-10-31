# E24 — lossless compaction перекрытий: отрицательный результат

**Решение: не продвигать кандидат.** Строгое объединение перекрытий удалило повторы исходных символов, но CER на всём dev не вырос: RU55/71, EN60/71, как у E21. Предварительный gate не пройден. Default/CLI не менялись, дополнительный подбор вариантов и generation не выполнялись.

[Протокол до scores](retrieval-e24-protocol.md), [проверенная сводка](retrieval-e24-summary.json), [core](../src/football_rules/context_compaction.py), [runner](../scripts/evaluate_overlap_packing.py).

## Гипотеза и неизменные условия

Повторное представление перекрывающегося текста соседних чанков расходует бюджет; его lossless compaction могла бы вернуть недостающие основания без нового поиска. Проверен один вариант, **отдельно от anchor-first E23**.

Контроль E21 `174a45eee3c243e2a7bf21be9ddd7bae`; исходные E15 top50/scores `b8b229800f4246d090eea03a4d5c9900`, E21 ordering, корпус/cleaning/chunking, evidence v2, local BGE tokenizer и B2048 сохранены. Только142 dev-вопроса,71+71. Веса не обучались; gold не передавался selector. `pack_overlap_context(documents, pages, budget, count_tokens)` использует только candidate text/provenance и общие исходные страницы.

Для каждой greedy попытки строго перекрывающиеся cleaned intervals одной страницы объединяются в точный union, включая транзитивное перекрытие. Touching/disjoint/cross-page не объединяются; gap не заполняется. Блок получает exact source slice, source-spans из исходной карты, synthetic ID и constituent IDs. Singleton остаётся неизменённым original. Бюджет проверяется по всей фактической строке с labels. Принятые originals внутри E24 не удаляются; очередной кандидат либо добавляется целиком, либо пропускается.

**Lossless относится к собственным selected originals E24, не ко всему контексту E21.** Экономия может позволить раньше принять более крупный candidate и тем самым изменить место для последующих chunks. Поэтому сохранение уникального текста внутри compaction не гарантирует, что ни один raw chunk контроля E21 не выпадет.

## Метрики

| Метрика | E21 RU | E24 RU | E21 EN | E24 EN |
|---|---:|---:|---:|---:|
| CER | 0.77465 | 0.77465 | 0.84507 | 0.84507 |
| Strict CER | 0.77465 | 0.77465 | 0.84507 | 0.84507 |
| Evidence Recall | 0.81455 | 0.81455 | 0.87089 | 0.87089 |
| Evidence Coverage | 0.84914 | **0.85842** | 0.89122 | 0.89122 |
| Source Redundancy | 0.03070 | **0** | 0.03251 | **0** |

- CER RU55/71, EN60/71; **0 улучшений / 0 регрессий CER** по обоим языкам.
- MeanCER115/142=**80.99%**, Δ0. Gate требует строгого роста meanCER, поэтому **fail**.
- Прирост среднего RU coverage всего+0.009283 (+0.9283 п.п.), целиком из одного FR091 RU.
- В остальных141 вопросах coverage, recall и complete/strict rates не изменились.

Redundancy=0 ожидается **по конструкции** и не является отдельным доказательством качества. Сравнение selected raw и actual merged показало полное равенство четырёх coverage/completeness-метрик для каждого вопроса: координатный gold не раздувался синтетическими блоками.

## Что изменилось в контекстах

У127/142 вопросов изменился набор выбранных originals относительно E21: суммарно163 добавления и86 выпадений по парам chunk/question. В E24 принято1580 originals, отрендерено1263 блока; среди них301 merged block. Повторы между разными страницами/документами, даже при одинаковом смысле, эта policy не устраняет.

### FR091 RU — единственный рост coverage, но не CER

Вопрос: обычная жёлтая за фол в центре поля; нет удаления/пенальти/гола, нарушитель идентифицирован правильно. Обязывает ли жалоба тренера VAR позвать судью к монитору?

- E24 добавил `507cfa9bbd7c...`, PDF79/печатная77, source3–759: ограничение помощи VAR и перечень разрешённых категорий инцидентов. Это релевантный текст к вопросу, не просто шум.
- Выпал `71b9ede6da86...`, PDF160/печатная158, source1744–1983: VAR автоматически проверяет ситуации, тренерам и игрокам не нужно запрашивать просмотр. Это тоже релевантный фрагмент к жалобе тренера.
- Добавленный candidate стоит16-м, выпавший24-м в frozen ordering. Это изменение greedy admissions относительно контроля, не eviction уже принятого внутри E24.
- Токены1975→2031; canonical coverage0→**0.659091**, ниже порога0.8. Gold `var_scope` на PDF79 source259–1014 включает также окончание о помощи через повторы и окончательном решении судьи на основе информации VAR либо собственного просмотра.
- Нужный хвост находится в следующем original `e82c0b09d735...`, отсутствующем в top50 данного вопроса. Одна упаковка его не создаст. CER/recall остаются0.

При этом E21 уже имел альтернативные смысловые основания на PDF159/печатная157 и162/160. Рост canonical coverage не доказывает, что раньше ответ «нет» вообще нельзя было обосновать.

### Освободившийся бюджет не обязательно достаётся нужной норме

Прочитаны добавленные/потерянные тексты в показательных случаях (assistant review, не экспертная калибровка):

| Вопрос | Дополнительный фрагмент | Почему CER не улучшился |
|---|---|---|
| FR005 RU: контроль руками9 секунд | PDF1, обложка/название издания | Нет решения об угловом за8 секунд; coverage остаётся0.5 |
| FR063 RU: сначала сыграл в мяч, затем снёс соперника | PDF132, бросок предметом запасным/официальным лицом | Не возвращает нужные критерии оценки единоборства; coverage0 |
| FR089 RU: вратарь вне штрафной рукой лишает гола | PDF142/198, нарушения при выполнении пенальти | Не собирает полную связку правил для руки/DOGSO вне штрафной; coverage1/3 |
| FR050 EN: случайное двойное касание, затем гол, пенальти в матче | PDF191, строка таблицы | Canonical gold на PDF136 не возвращён, CER0; прямое альтернативное правило PDF182 уже было в обоих контекстах |

Таким образом, устранение overlap экономит место, но не даёт способа выбрать следующий **смыслово необходимый** фрагмент из rank-order. Оно также не устраняет отсутствие нужного candidate в пуле и не исправляет ограниченность canonical evidence.

## Исполнение и проверки

- Первичный smoke preflight остановился **до создания run и до любых scores**: установленный SDK `merge_records` добавляет provenance/tags в переданные dicts. Проверка обнаружила мутацию; inputs/expectations в native dataset совпадают с fresh records. Исправлен только runner: SDK получает deep JSON copy. Policy, budget и разметка не менялись; guard не ослаблен. История сохранена в Git/protocol.
- Smoke **`671dbd9237eb46ac9e2997995dbc5fbe` FINISHED**,3 вопроса/15 конечных scores. Trace `tr-bd5dee5d3e0a5c28683005e8bd3c97fe` прочитана за≈3.35s,1 CHAIN span.
- Full **`ca86f33245c343869dcd0eacfe879895` FINISHED**,142 вопроса,**710/710 finite native assessments без ошибок**; warnings/errors в полном запуске нет.
- Использованы native datasets, repository scorers, `mlflow.genai.evaluate` и tracing с workers1/1. Persistent arbitrary-code scorer registration не включалась. Main predict замыкает только retrieval candidates, source pages/maps и tokenizer — не baseline/gold records.
- Перед оценкой прошли exact replay142 E21/E15, source metadata/maps и10 pinned input hashes. Все12 code hashes проверены повторно после оценки.
- Runner и независимый readback проверили selected originals⊆frozen top50, immutable records, ordered once-only skipped complement, synthetic/constituent IDs, strict connected components, earliest-admission block order, exact source slices/spans, raw↔merged coordinate/source-character unions и whole-render budget≤2048. Искусственного расширения gold coverage нет.
- Независимый readback сверил все710 assessments по question/language/metric с сохранёнными и повторно вычисленными значениями actual merged context; native means совпали. Сохранены verification JSON и анализатор, полные inputs/outputs и reproduction files.

Full command≈**136.09s**, baseline replay≈64.07s, native evaluation≈63.40s, сумма core packing≈48.35s (входит в evaluation). Это offline replay, не online latency и не SLA; вложенные интервалы не складывать. Сравнение runtime с E23 не является контролируемым benchmark, т.к. здесь добавлены source/provenance validations.

**163 unittest tests, OK**, `py_compile` и `git diff --check` прошли. Семь новых behavior tests покрывают overlap/transitive bridge, touching/disjoint/cross-page, earliest-rank display, source gaps/removed text, exact tokenization и invalid provenance. Ruff/Black/strict mypy не запускались; инструменты не добавлялись. В общих tests остаются ранее замеченные SQLAlchemy deprecation/SQLite ResourceWarning, не failures.

Новых provider API, embeddings, reranker inference, генерации или test-evaluation не было; provider experiment cost **$0**. Исходные chunks/index/gold/references и application defaults сохранены. Проверка общей структуры датасета не равна оценке test.

## Вывод

Зафиксирован **отрицательный результат** для гипотезы «точное удаление overlap при прежнем greedy ordering повысит CER». Улучшение лишь частичное и координатное; вероятность правильного ответа не измерялась. Не комбинировать post-hoc с E23 и не подбирать фильтры на этих scores в рамках E24. Для следующей работы важнее различить missing candidates, нерелевантные admissions и альтернативные достаточные основания, чем считать redundancy0 признаком решённого retrieval.
