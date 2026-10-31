# Q4 — сохранность ответа перед оценкой

31.10.2026. Ветка `experiment/q4-answer-integrity`, код/протокол/reviews до scoring: `909df8c`. [Протокол](evaluation-q4-protocol.md), [сводка](evaluation-q4-summary.json), [независимая техническая проверка](evaluation-q4-verification.json).

## Что сделано

Добавлен экспериментальный [answer envelope](../src/football_rules/answer_envelope.py): один `whole_answer` фрагмент с исходным текстом, snapshot ID, SHA256 и диапазоном `[0,len(answer))` в Unicode code points. Пробелы, CRLF, emoji, combining marks и язык не нормализуются. Валидатор отклоняет неизвестные поля, неверные hash/ID, неполные диапазоны, неверные цитаты, bool вместо integer offset и другие нарушения. Пустой ответ явно отклоняется, не подменяется успешным пустым результатом.

**Привязка к ответу не означает привязку к норме IFAB.** Это не атомарная декомпозиция и не доказательство поддержки источником. Сохраняются все исходные ошибки и пропуски ответа. Целый ответ нельзя без отдельного исследования поставить на место атомарного statement в старом NLI и сравнить средние по разным знаменателям.

Дизайн намеренно ограничен: exact copy сохраняет смысл по конструкции, поэтому structural100% ожидаемы и сами по себе не доказывают улучшения judge. В действующий Ragas path оболочка не подключена; исторические scores, генерация, retrieval, gold/references, defaults и test неизменны.

## Структурный эксперимент на frozen Q1

48 исходных ответов:24 random/24 targeted,24 RU/24 EN. Исходный Q1 run `0efab3b7199845e9b4ba2942399f106c` FINISHED. Сверены исходные fingerprints, а не только совпадение с новым review-пакетом.

| Проверка | Результат |
|---|---:|
| `envelope_integrity` | 48/48, mean1.0 |
| `corruption_rejected` — все8 повреждений отвергнуты для ответа | 48/48, mean1.0 |
| Индивидуальные синтетические повреждения | 384/384 отвергнуты |
| Конечные native feedback assessments | 96/96 |

Восемь типов повреждений: replacement quote, wrong hash, wrong snapshot, truncated range, missing unit, extra unit, bool offset, дополнительное claim-поле. Это искусственные negative tests, **не384 обнаруженные ошибки Ragas**. Старые парафразы не проверялись на exact-quote contract, которого они не обещали.

## Сравнение сохранности смысла

Два свежих AI-reviewers независимо рассмотрели12 перемешанных объектов:6 исходных ответов × два представления. Им показали только исходный answer и units, без Q IDs, методов, исторических scores, ролей и labels Q1. Форма whole-answer всё равно узнаваема; полного method blinding нет. Критерий один для обоих представлений: добавился, потерялся или изменился ли смысл, с допустимыми переводом и перефразированием. Футбольная правильность не оценивалась.

Пакет: [12 объектов](evaluation-q4-review-packet.json); исходные [review A](evaluation-q4-review-a.json) и [review B](evaluation-q4-review-b.json); [раскрытый mapping](evaluation-q4-review-mapping.json).

| Представление / reviewer | Meaning changed | Preserved | Uncertain |
|---|---:|---:|---:|
| Исторические claims, A | 3/6 | 3/6 | 0/6 |
| Исторические claims, B | 3/6 | 2/6 | 1/6 |
| Whole answer, A | 0/6 | 6/6 | 0/6 |
| Whole answer, B | 0/6 | 6/6 | 0/6 |

Оба reviewers подтвердили известные дефекты:

- **Q015 / P008:** `only penalized` превратилось в `not penalized`; новый P011 сохраняет исходную формулировку.
- **Q026 / P002:** `свободный удар` стал `direct free kick`; новый P003 оставляет русский текст без перевода.
- **Q033 / P001:** уточняющие вопросы стали фактами, OR условий распалось на два отдельных ONLY IF; новый P007 сохраняет вопрос и условную структуру.

Контроли:

- **Q003 / P009:** A считает старые statements совместно эквивалентными; B оставляет `null` из-за неоднозначного распределения условий между statements. Разногласие не разрешали голосованием и не заменяли нулём. Whole-answer P006 сохранён у обоих.
- **Q010:** старое разложение и новое представление сохраняют смысл, но это не исправляет известную ошибку последующего verifier, который отрицал угловой вопреки источнику.
- **Q025:** оба представления сохраняют исходное ошибочное «должно быть одиннадцать игроков». Это наглядно отделяет сохранность смысла от истинности.

Выборка специально включает3 известных дефекта и3 диагностических контроля из уже изученного Q1. Числа3/6→0/6 — **не accuracy, не оценка частоты ошибок на новых данных и не доказательство превосходства нового scorer**. Нельзя объединять24 review entries как независимые наблюдения. Рецензенты — assistants, expert calibration pending.

## MLflow и независимая проверка

- Smoke `e362d5578ff840fa95e8d438104b0430` FINISHED: Q015/Q026/Q033,6 assessments. Fresh trace `tr-d8866e4f4e573d83b512932772d7dda9`,1 CHAIN span `Q4_answer_envelope`; readback3.25s при лимите60s.
- Full `a2f68bdac7844a74a6de76ee20b6d05e` FINISHED:48 ответов,96 finite native feedback assessments. Native evaluate≈5s в лимите180s; дополнительных96 expectation assessments не включали в feedback count.
- Native datasets discovery/reuse/create, deep-copy merge, `to_df()`, direct source-controlled scorers. Persistent registration не включали. Predict получает только snapshot ID; генерации и проверки Ragas нет.
- Независимый backend/artifact readback подтвердил48 original answers,65 исторических occurrences,100 исторических source hashes,115/115 manifest hashes,96/96 оценок,384/384 независимо восстановленных mutants. Input/output manifests и Git provenance совпали; исходные19 артефактов full run не изменены при добавлении verification.
- Provider/API/model calls0; provider cost0. Работа assistants в редакторе не включена в эту цифру.

Команды из корня репозитория, с внешними deadlines120s/180s:

```sh
uv run --no-sync python scripts/evaluate_q4_integrity.py --prepare-only
uv run --no-sync python scripts/evaluate_q4_integrity.py --smoke --review-file docs/evaluation-q4-review-a.json --review-file docs/evaluation-q4-review-b.json
uv run --no-sync python scripts/evaluate_q4_integrity.py --full --review-file docs/evaluation-q4-review-a.json --review-file docs/evaluation-q4-review-b.json
```

`--prepare-only` детерминированно восстанавливает review packet и локальный mapping, но не reviews. Full требует committed inputs и matching FINISHED smoke. Source/code/review hashes проверяются до и после scoring.

## Тесты и решение

15 новых unit tests, в том числе positive/negative schema/range/hash cases, Unicode и отсутствие скрытого исправления. `uv run --no-sync python -m unittest discover -s tests` — **193 tests OK**, `git diff --check` OK. Существующий SQLite ResourceWarning не приводит к падению тестов. Синхронизация или установка зависимостей не выполнялась.

**Принять только integrity seam как проверенный исследовательский компонент. Не заменять Ragas/default и не объявлять рост качества ответов.** Он исключает переписывание на своём этапе, но потребует другого downstream оценщика для полного ответа. Следующий содержательный опыт — отдельный whole-answer judge по QUESTION+CONTEXT с раздельными критериями применимости, полноты последствий и поддержки; перед сравнением нужны заранее замороженные calibration/validation данные и независимые labels. Без них результат допустим только как ограниченный диагностический пилот, не экспертно валидированная accuracy.
