# Q3 — чувствительность CER к альтернативному официальному evidence

31.10.2026. Ветка `experiment/q3-alternative-evidence`. [Протокол](evaluation-q3-protocol.md), [машинная сводка](evaluation-q3-summary.json), [независимая техническая проверка](evaluation-q3-verification.json).

## Что проверяли

Не новый retriever и не обучение на dev. На **568 неизменных контекстах** E21/E23/E24/E25 проверили, зависит ли сравнение методов от единственного канонического расположения нормы. Взяты только два ранее описанных случая: FR005 RU и FR050 EN. Они выбраны после исторического разбора, поэтому результат не оценивает распространённость проблемы в датасете.

Два свежих assistant-reviewers получили вопросы, rubric, canonical excerpts и кандидатные страницы **без retrieval-contexts, названий методов и scores**. Оба признали оба фрагмента достаточными для конкретных сценариев: [review A](evaluation-q3-review-a.json), [review B](evaluation-q3-review-b.json), [слепой пакет](evaluation-q3-review-packet.json). Это AI-проверка, **не независимая калибровка арбитром**; expert review pending.

Альтернативы сохранены отдельно в [manifest](../data/evaluation/evidence-alternatives-q3.json). Исходные `evidence.jsonl`, scenarios, references, test, исторические scores и defaults не изменены.

- **FR005 RU:** введение, PDF12 / printed10, диапазон `[182,291)`. Прямо названы вратарь, контроль руками более восьми секунд и угловой. Получатель углового **не назван буквально**: «сопернику» — обычный вывод из санкции за нарушение вратаря. Территориальное условие и отсчёт даны вопросом. Это сценарно-достаточная гипотеза, не универсальная замена полного keeper-time unit. При стандарте только буквальной поддержки всех элементов её следовало бы отклонить.
- **FR050 EN:** изменения Law14, PDF182, `[4,357)`. Заголовок отличает матчевый пенальти от серии Law10; правило прямо связывает случайное немедленное касание неопорной ноги и гол с повтором. Вывод не распространяется на умышленное касание или отсутствие гола.

Новый binary критерий — **OR полных AND-наборов**: целый canonical witness либо целый одобренный alternative witness. Склеивать неполные наборы нельзя. CER использует прежние80%, strict100%. Все options валидируются, даже если canonical уже проходит. Без alternatives результат точно совпадает с v2. Это покрытие координат источника, не accuracy ответа.

## До и после

В каждой ячейке знаменатель **71 вопрос**. «После» означает другой evaluator на том же контексте, **а не улучшение системы**. CER и strict CER здесь совпали во всех восьми группах.

| Frozen method | RU canonical → alternative | EN canonical → alternative |
|---|---:|---:|
| E21 — исходная упаковка | 55 → 56 (77.46% → 78.87%) | 60 → 61 (84.51% → 85.92%) |
| E23 — anchor-first | 55 → 56 (77.46% → 78.87%) | 61 → 61 (85.92% → 85.92%) |
| E24 — overlap compaction | 55 → 56 (77.46% → 78.87%) | 60 → 61 (84.51% → 85.92%) |
| E25 — full-union rerank | 54 → 55 (76.06% → 77.46%) | 58 → 59 (81.69% → 83.10%) |

**Сравнение методов при одном evaluator:**

- E23 против E21: раньше RU0 / EN+1 вопрос; с альтернативами RU0 / EN0. Единственное преимущество по CER исчезает. Это чувствительность прежнего сравнения, **не доказанная эквивалентность систем** и не доказательство одинаковых ответов.
- E24 против E21: RU0 / EN0 при обеих версиях.
- E25 против E21: RU−1 / EN−2 при обеих версиях. Отрицательный вывод E25 сохраняется.
- Все четыре метода получают FR005 RU; E21/E24/E25 дополнительно FR050 EN. E23 уже проходил FR050 EN по canonical. Всего **7 изменившихся snapshots**, каждый0→1 и по CER, и по strict.

Полный список: `E21-FR005-ru`, `E21-FR050-en`, `E23-FR005-ru`, `E24-FR005-ru`, `E24-FR050-en`, `E25-FR005-ru`, `E25-FR050-en`. Полные witnesses и hashes приведены в машинной сводке.

## Запуск и проверка

Код/manifest/reviews зафиксированы до оценки: `289151d`; исправление пути артефактов до успешного smoke/full: `06cf3b9`.

- Первый smoke `d8cb5745836d4738826b6ad323756a3c` — FAILED до scoring: MLflow отверг `reproduction/.`. Путь исправлен; неудачный run сохранён,0 feedback assessments.
- Успешный smoke `e89e5400df3343adb4f02479fbb41eaf`:3 snapshots,12 assessments; trace `tr-d5ff6289fd708d369266232c74ab7021`,1 replay span, readback4.81s при лимите60s.
- Full `c67931321bab4a00b5902abc50fe0745` — **FINISHED**,568 snapshots,2272 finite native assessments (по568 каждого из четырёх scorers),568 OK evaluation traces. Native evaluation занял≈82s в лимите300s.
- Независимый технический readback подтвердил **1136/1136 canonical scores** исторических runs,560 out-of-scope rows /1120 score-pair equalities без изменений; монотонность сохранена. Это проверка вычислений, не дополнительная экспертиза источников.
- Native datasets, `mlflow.genai.evaluate`, direct source-controlled scorers; persistent custom registration не включалась. Предсказание — только replay; gold не передавался в predict. Source/context/code/review hashes проверены до и после scoring.
- **0 вызовов моделей/provider API, provider cost0**. Работа assistants в редакторе в эту цифру не включена.

Воспроизведение из корня репозитория (с внешними deadlines120s/300s):

```sh
uv run --no-sync python scripts/evaluate_q3_alternatives.py --smoke --review-file docs/evaluation-q3-review-a.json --review-file docs/evaluation-q3-review-b.json
uv run --no-sync python scripts/evaluate_q3_alternatives.py --full --review-file docs/evaluation-q3-review-a.json --review-file docs/evaluation-q3-review-b.json
```

`prepare_q3_alternatives.py` готовит исходные **неодобренные** candidates/пакет, а не восстанавливает решения reviewers; не перезаписывать им согласованный manifest без нового review. Для full требуются закоммиченные исходники и matching FINISHED smoke.

## Тесты и инцидент окружения

7 новых tests: canonical/alternative success, exact v2 fallback, запрет stitching, все units/locators обязательны,80% против100%, fail-fast на некорректной альтернативе даже при полном canonical. Профильный набор evidence:20 tests OK.

Во время подготовки подагент ошибочно использовал `uv run` без `--no-sync`, началась автоматическая синхронизация окружения. После неё PyTorch оказался неполным (`torch.tensor` отсутствовал), общий прогон178 tests завершился одной ошибкой. Исходный **torch2.14.1+cu130 восстановлен offline из локального uv cache**, без новых версий, сети, изменений `pyproject.toml`/`uv.lock` или169 остальных установленных пакетов. Проверены CPU/CUDA tensor operations и RTX3060. После восстановления **все178 tests OK**,0 skips; `git diff --check` также проходит. Инцидент не затронул model-free scores Q3.

## Решение и следующий шаг

Не продвигать E23 на основании единственного canonical CER gain; E24/E25 также не продвигать. Не подменять старый gold новым автоматически. Показать эксперту эти два источника и границы допустимого вывода; затем зафиксировать отдельную версию evidence, если он согласится. При недоступности эксперта следующие улучшения проверять с двумя версиями evaluator и явным сообщением расхождений, а не объявлять ростом accuracy сдвиг координат evidence. Test остаётся нетронутым. Дальнейший подбор retrieval-эвристик на многократно использованном dev не даёт независимого подтверждения качества.
