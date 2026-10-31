# Q4 — контракт сохранности текста перед оценкой

Протокол до scoring. Ветка `experiment/q4-answer-integrity`. Исследуем инженерную защиту от переписывания ответа, не accuracy нового judge. Provider calls0; Ragas/default/prompts/gold/references/test неизменны.

## Гипотеза и границы

Q1 подтвердил три механизма: отрицание/only (Q015), свободный→direct (Q026), вопрос→факт и разрушение OR (Q033). Вместо сгенерированных атомарных claims экспериментальная оболочка сохраняет **весь ответ одним неизменённым фрагментом**, с snapshot ID, SHA256 и координатами Unicode code points `[0,len(answer))`. Это привязка к **тексту ответа, не к норме IFAB**. Вопрос, документы и citations не смешиваются с ответом.

Сохранение смысла exact copy следует из конструкции: высокий structural score ожидаем и сам по себе **не доказывает улучшения оценки**. Не считать целый ответ атомарным claim, не усреднять по нему прежние claim-level NLI scores. Оболочка сохраняет также ошибки исходного ответа. Она не решает ошибки verifier, неполноту references, потерю фактов QUESTION или пропуск санкций. Сейчас это альтернативный integrity seam; в действующий Ragas path не интегрировать.

## Frozen материал и проверки

48 snapshots исходного Q1 (24 random/24 targeted, 24 RU/24 EN), источник FINISHED `0efab3b7199845e9b4ba2942399f106c`. Проверить hashes исходных файлов selection и Q1 source hashes; не выбирать новые примеры по Q4 scores. Native dataset discovery/reuse/create; direct source-controlled deterministic scorers (persistent registration заблокирована):

1. `envelope_integrity`: строгий schema/snapshot/hash/range/quote/whole-answer contract.
2. `corruption_rejected`: все заранее заданные повреждения отвергнуты валидатором — quote replacement, hash replacement, snapshot replacement, truncated range, missing unit, extra unit, bool offset, extra claim field. Эти mutants — синтетические проверки валидатора, не наблюдавшиеся ошибки Ragas.

Для нормального envelope оба результата1; недопустимый вход не чинить и не заменять молча пустым ответом. Пустой answer явно ValueError; whitespace/CRLF/emoji/combining marks не нормализовать. Unit tests проверяют и положительные, и отрицательные случаи.

Smoke3 Q015/Q026/Q033:6 native assessments, trace readback≤60s. Full48:96 finite assessments только после matching FINISHED smoke, committed code/protocol/reviews. Внешний deadline smoke120s/full180s. Workers1/1, synchronous tracing, telemetry disabled. Source/code/review hashes до/после. Не применять exact-quote contract к старым парафразам: у них не было такого обещания.

## Диагностическое semantic review

До scoring подготовить два представления шести заранее заданных ответов: известные failures Q015/Q026/Q033 и controls Q003 (rule+exception), Q010 (verifier defect вне scope), Q025 (реальная ошибочная деталь должна сохраниться). Оригинальные faithfulness statements из первого parsed response; кандидат — один whole-answer unit. Сохранить mapping; пакет12 объектов перемешать seed20261101, скрыть Q IDs, роли, модели, scores и прежние labels. Метод невозможно полностью скрыть по форме.

Два свежих assistant-reviewers для каждого объекта сравнивают исходный ответ с представленными units **по одному критерию**: добавлен/утрачен/изменён ли смысл (negation/actor/action/conditions/OR/questions). Разрешить `meaning_changed=null` при неопределённости; сохранять rationale и точные примеры. Не оценивать футбольную истинность и не требовать буквального совпадения от старых парафразов. Никакого редактирования исходных reviews или majority-подгонки; разногласия показать. Это targeted regression probes на изученном Q1, не независимая expert validation. Численные semantic counts — только описательные, отдельно от native structural scores.

## Решение

Все48 envelopes должны проходить contract и отвергать все8 mutants. Любой failure блокирует использование seam до исправления. Даже при успехе defaults не менять: сначала отдельная проверка downstream judge на полных ответах с фактическими входами QUESTION и CONTEXT и независимыми labels. Не объявлять structural100% ростом faithfulness/accuracy. Зафиксировать код/протокол и результаты отдельными небольшими коммитами; push не делать.
