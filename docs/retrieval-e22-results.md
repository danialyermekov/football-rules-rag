# E22: частичный результат и блокер полного bound

Протокол: [retrieval-e22-protocol.md](retrieval-e22-protocol.md). Полного результата E22 нет: полный запуск превысил внешний лимит 20 минут. Не следует интерпретировать частичный smoke как оценку всех 142 вопросов.

## Что проверено

- На всех 142/142 dev-вопросах проверены сохранённые inputs/expectations, совпадение E15 и E21 top50 вместе с оценками и исходными чанками, хеши четырёх исходных файлов относительно параметров обоих запусков, revision локального budget tokenizer, точный replay порядка и `pack_context` E21 и совпадение всех сохранённых evidence metrics.
- Smoke FINISHED `d2f0eb9c18ec47b9a040dbec14980e11`: 3/3 FOUND, 0/3 IMPOSSIBLE_POOL, 0/3 UNKNOWN. Это FR001 RU/EN и FR002 RU. Native `complete_evidence/mean=1.0` на 3; trace `tr-33b5d3c10e4158868f12443fa9952ad4` прочитан и содержит spans.
- FR001 RU: baseline FOUND, 2027 tokens; FR001 EN: baseline FOUND, 2046 tokens. FR002 RU: baseline CER=0, найдено свидетельство из top50 после 7 сочетаний, 681 tokens и CER=1. См. полные witness, offsets, inputs и hash manifest в MLflow smoke artifacts `per-question-results.json` и `input-hashes.json`; краткая сводка также в `tmp/e22/smoke.json`.
- На smoke baseline CER: RU 1/2, EN 1/1; FOUND: RU 2/2, EN 1/1. Это не репрезентативные оценки.
- Три поведенческих unittest проверили границу 2048/2049, объединение source spans, различие страниц и UNKNOWN при таймауте. `pytest` в установленной среде отсутствует; зависимости не менялись.

## Незавершённый полный запуск

Run `ecb2be0318324fe68cfca07af3854f87` запущен после smoke. Перед оценкой 142/142 replay прошёл. Во время `mlflow.genai.evaluate` scorer `complete_evidence` неоднократно сообщал `timed out after 300 seconds`; прогресс дошёл до 11/142, после чего внешняя команда была остановлена по лимиту 20 минут. Невозможно корректно вывести числители FOUND/IMPOSSIBLE_POOL/UNKNOWN или bounds для 142 вопросов: ни полная таблица, ни summary не сформированы. После остановки MLflow первоначально показывал статус RUNNING. Процесс Python отсутствовал в `tasklist`, после чего статус этого run явно установлен на KILLED; результаты не дополнялись и не выдаются за завершённые. Причина задержки scorer не установлена. Для продолжения нужна диагностика/ограничение конкурентности локального native evaluate и новый полный запуск с заранее согласованным лимитом; увеличение таймаута само по себе не доказывает устранение проблемы.

Покрытие top50 и B2048 не доказывает семантической достаточности, а UNKNOWN не означает невозможности. Данные test, генерация, новые embeddings и внешние API не использовались.
