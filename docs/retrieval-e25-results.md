# E25 — полный union перед reranking: отрицательный результат

**Решение: не продвигать.** Перенос отсечения top50 после Qwen reranker улучшил полноту выбранного пула на RU, но ухудшил готовый контекст: RU55/71→54/71, EN60/71→58/71. Предварительный gate не пройден. Default, model weights, gold/references и test не менялись; настройки после scores не подбирались.

[Протокол до inference](retrieval-e25-protocol.md), [проверенная сводка](retrieval-e25-summary.json), [runner](../scripts/evaluate_full_union_reranker.py), [helper](../src/football_rules/candidate_expansion.py).

## Что проверили

В E21 исходный Dense50+BM2550 union обрезается по RRF до50 **до** reranking. В полном сохранённом E10 union есть64–92 candidates на вопрос; по coordinate gold он полнее первоначального top50 (RU64/71 против61/71, EN68/71 против67/71).

E25 меняет только место candidate cutoff: **Qwen rerank всего сохранённого union → top50 → прежние E21 neighbor ordering и B2048 packing**. Не использованы E23 anchor-first или E24 compaction, новые search/embeddings, query rewriting, training или scenario-specific правила. Helper объединяет scores без query/evidence; локальная модель получает только исходный вопрос и passage text.

Источник кандидатов E10 `b50e71e2d39d4145ae2f7e08fd49416e`, старые scores E15 `b8b229800f4246d090eea03a4d5c9900`, основной контроль E21 `174a45eee3c243e2a7bf21be9ddd7bae`. Корпус773 chunks, прежние142 dev-вопроса/71+71, source-based evidence v2 и BGE budget-tokenizer сохранены.

## Cache и реальный локальный inference

- Все **7100** prefix scores взяты из frozen E15 без изменения, не вычислены заново для нового качества.
- Для отсутствовавших в старом top50 **3960** query/chunk-пар получены новые локальные scores `Qwen/Qwen3-Reranker-0.6B`, revision `e61197ed45024b0ed8a2d74b80b4d909f1255473`. CUDA FP32/batch2, max1024, исходная инструкция/chat template и yes-minus-no logits полностью совпадают с E15. CPU fallback, truncation и смены рецепта нет.
- Перед оценкой tails smoke отдельно пересчитал все150 prefix pairs первых трёх вопросов: **max absolute difference0.0**, exact sorted IDs совпали. Это контроль совместимости, не независимое повторное измерение всех7100 scores и не новые baseline outcomes.
- Smoke:3 head calls/150 pairs и3 tail calls/83 pairs. Full:0 новых head calls,139 tail calls/**3877 новых pairs**, плюс reuse83 smoke pairs. Всего в цикле **4110 новых локальных pair scores** (3960 tails+150 controls),145 вызовов метода по запросам, внутри batch2.
- Ответы модели durable сохранены до metric logging, exact-input cache keys содержат query/raw docs/model parameters/model hashes, но не gold. На завершении142 уникальных tail responses и3 head responses; unresolved `.pending` нет. Повторный predict/native validation не дублирует inference.

Полный ranking11060 pairs собран из совместимых cached/fresh scores, затем top50 выбран по score descending/ID ascending. Нельзя интерпретировать этот offline cache-assisted run как измерение полной online latency reranking11060 пар с нуля.

## Контекстные метрики — все142 dev

| Метрика | E21 RU | E25 RU | E21 EN | E25 EN |
|---|---:|---:|---:|---:|
| CER | 0.77465 | **0.76056** | 0.84507 | **0.81690** |
| Strict CER | 0.77465 | 0.76056 | 0.84507 | 0.81690 |
| Evidence Recall | 0.81455 | 0.80751 | 0.87089 | 0.85446 |
| Evidence Coverage | 0.84914 | 0.83633 | 0.89122 | 0.88091 |
| Source Redundancy | 0.03070 | 0.03172 | 0.03251 | 0.03533 |

- RU: **1 улучшение / 2 регрессии**,55→54, Δ−1.41 п.п.
- EN: **0 улучшений / 2 регрессии**,60→58, Δ−2.82 п.п.
- MeanCER: **115/142=80.99% →112/142=78.87%**, Δ−2.11 п.п.
- Gate требует роста meanCER и падения языка не более1/71. Не выполнены оба условия: среднее снизилось, EN потерял2/71.

### Полнота пула — отдельно от качества контекста

Это CER объединения документов **без бюджетного ограничения**, не точность ответа и не actual context CER.

| Пул | RU /71 | EN /71 |
|---|---:|---:|
| Первоначальный RRF top50 | 61 | 67 |
| Весь union, до и после reranking | 64 | 68 |
| Новый Qwen-selected top50 | **63** | **67** |
| E25 фактический context B2048 | **54** | **58** |

Новый selected50 получил FR063/090/091 RU, но потерял FR094 RU; EN получил FR063, но потерял FR069. Это net+2 RU/0 EN на стадии пула, которое **не превратилось** в рост packed-context CER. Strict pool CER нового RU62/71, а пороговый CER63/71: эти определения не смешиваются. Full-union coverage при ranking не менялась.

## Разбор всех пяти смен context CER

Чтение source chunks coding assistant, не экспертная футбольная калибровка. Страницы — PDF; короткие IDs доступны полностью в artifacts. Added/removed chunks — сравнение candidate sets, не pairwise причинное соответствие замен.

| Случай | Где потеряно/добавлено основание | Что изменилось |
|---|---|---|
| **FR020 RU**, правильно допущенный запасной сразу подаёт угловой | **Packing**, gold ещё в selected50 | Chunk `d2928c6d70...`, PDF62, с разрешением вошедшему запасному участвовать в любом restart, остался rank9, но получил `token_budget`. Новый tail-кандидат RRF65 и другие поднятые соседи заняли место раньше. Tokens2036→2038. Явная норма any-restart в новый контекст не попала. |
| **FR094 RU**, обычный пас головой вратарю без трюка | **Новый top50** | Продолжение ограничения передачи ногой/вбрасывания `4a8c07b5a7...`, PDF121, old rerank46→new union64; его уже нельзя вернуть neighbor packing. На PDF120/125 остаётся прямая норма об умышленном трюке, но продолжение про kicked pass/direct throw-in потеряно. Tokens2014→2000. |
| **FR090 RU**, явно ошибочное второе предупреждение | **Tail admission + neighbor promotion** | `e82c0b09d7...`, RRF68, за пределами старого top50, теперь new rank48 и продвинут после существующего PDF79 neighbor. Дополняет canonical span259–1014 до полного coverage. Tokens2036→2048. |
| **FR017 EN**, мяч лопнул в обычной открытой игре | **Packing**, gold ещё в selected50 | `e21822e00f...`, PDF56, о stop play/dropped ball остался rank8, но пропущен по бюджету. Дополнительные tail-кандидаты PDF138 о нарушениях пенальти вместе с predecessor вошли раньше. Tokens2023→1953; остаток95 токенов не означает, что целый gold chunk мог поместиться. Общая норма dropped ball не заменяет прямое условие лопнувшего мяча. |
| **FR069 EN**, касание защитника перед получением мяча атакующим в офсайдной позиции | **Новый top50** | `1de6f95081...`, PDF110, old rerank47/RRF41, выпал из new50. Начало определения deliberate play и различие deflection/save сохранились, но продолжение о неудачном контролируемом действии и признаках контроля потеряно. Tokens2024→2024. Это не полная потеря всей смысловой нормы. |

Две регрессии возникли при выборе new50, две — при упаковке. В RU FR090 расширение действительно вернуло candidate из tail, но **не впервые дало правило об ошибочной второй жёлтой**: E21 уже содержал эту норму в первой части PDF79 и прямые подтверждения PDF159/162/177. CER вырос за счёт завершения canonical source span. Нельзя объявлять единственный CER gain доказательством улучшения ответа.

## Исполнение, проверки и стоимость

- Smoke **`5c16311c0a3a489ebddec28075dc62cd` FINISHED**,3 вопроса,15 finite assessments,≈192.31s. Trace `tr-83bdd38889f977cbe4a458d339a519c5`,3 spans CHAIN/RERANKER, readback≈6.30s.
- Full **`a5cd577ec6184069ae7060f95bbebe08` FINISHED**,142 вопроса,**710/710 finite assessments**,≈647.98s при supervisor deadline720s. Warnings/errors в обоих runs нет. Политика после scores не менялась, повторного полного варианта не запускалось.
- Frozen inputs11 hashes, reproduction code11 hashes и model/config/metadata24 hashes проверены. Веса local-only с pinned revision, параметры/versions/GPU совпали с E15. Полный template preflight11060 pairs: максимум**538** токенов при лимите1024, truncation отсутствует.
- Пересчитаны E10/E15/E21 contexts и source metrics для всех142 до inference. Проверено exact prefix membership/provenance, original scores7100, ordered full union, top50 slice, E21 neighbor ordering, whole source chunks, exact renderer/B2048 и все pool diagnostics.
- Независимый readback дополнительно проверил142 exact-input tail caches,3 controls, merged common ranking каждого union, все710 native assessments по question/language/metric,142 traces и native means. Ни missing, ни error assessments не заменены нулями.
- Worker defaults1/1, synchronous tracing, native datasets/scorers/`mlflow.genai.evaluate` сохранены. Unsafe persistent custom-scorer registration не включалась. SDK получает copy при merge; inputs/expectations сравниваются отдельно от несериализуемого DatasetRecordSource. Эта ошибка сериализации была поймана regression test до inference и исправлена до preregistration commit.

Full replay≈113.32s, template preflight≈7.02s, native evaluation≈482.32s, включая≈406.78s **нового tail inference**. Smoke дополнительно потратил≈17.88s на head controls и≈9.10s на tails. Суммарный новый локальный inference≈433.75s; GPU время и электроэнергия не являются бесплатным ресурсом. Provider API cost **$0**, Gemini calls0; новых внешних API/search/embedding запросов нет. Вложенные интервалы времени не складывать и не выдавать за online SLA.

**171 unittest tests, OK**, syntax/`py_compile`/`git diff --check` прошли. Восемь новых tests проверяют membership, provenance, finite scores, deterministic ties, отсутствие мутаций, prefix/tail validation и native dataset metadata serialization. Ruff/Black/strict mypy не запускались, зависимости не добавлялись. Старые SQLAlchemy deprecation/SQLite ResourceWarning в общем test suite остаются предупреждениями, не failures.

## Вывод

Более полный candidate pool не гарантирует лучшего итогового контекста: новые высокие reranker scores вытесняют полезные продолжения при cutoff и вводят новые budget-конкурирующие группы соседей. Для выбранной frozen policy прирост pool recall не оправдал дополнительных локальных вычислений; **E25 не продвигать; E21 как исследовательский контроль и текущие CLI defaults сохранить**. Dev многократно использован, RU/EN зависимы, coordinate gold не исчерпывает альтернативы; результаты не измеряют качество генерации и не являются независимым holdout. Test, references и gold не использовались для изменения policy и не менялись.
