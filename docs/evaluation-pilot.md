# Пилот оценки: 12 ситуаций RU/EN

Пилот сохранён для истории обсуждения. Канонические записи этих ситуаций теперь FR001–FR012 в [датасете](../data/evaluation/README.md); [версия всех 100 ситуаций для чтения](dataset-review.md). Ниже — исходные формулировки пилота, не отдельная тестовая выборка.

Дата: 2026-10-22. Редакция: IFAB 2026/27. Аудитория: болельщик.

Статус: авторские черновики, сверенные агентом с текстом скачанных PDF. Не проверены независимым судьёй и пока не утверждены разработчиком. Это материал для совместного разбора, не измеренный benchmark. Платные LLM для подготовки не вызывались.

## Как читаем и оцениваем

Каждая ситуация имеет один ID и два вопроса с одинаковыми существенными условиями. Итого 12 ситуаций / 24 вопроса. Ответы ниже пересказывают положения своими словами; это не выдержки из PDF. Правильность определяем по смыслу и условиям, а не по совпадению слов.

Источники: [EN PDF](https://www.theifab.com/downloads/laws-of-the-game-202627-single-pages?l=en), [RU PDF РФС](https://www.rfs.ru/subject/1/documents/preview?documentId=2079). Точные файлы и SHA-256 записаны в [source-manifest.json](source-manifest.json). Номер PDF-страницы считается с 1. Напечатанная страница указывается отдельно. Идентификатор `law/section` относится к редакции 2026/27, а не гарантирует неизменность между сезонами.

Для каждой ссылки далее формат: `язык: PDF-страница (напечатанная страница)`.

Пока весь пилот — development material. Позже формируем отдельный test: обе языковые версии и перефразировки одной ситуации всегда попадают в одну часть. Пилотные примеры, которые обсуждаем и используем при настройке, в итоговый test не включаем.

Для answerable-вопросов проверяем: решение, обязательные условия, подтверждающие ссылки, отсутствие выдуманных фактов. Для неполных вопросов — объяснение ограничения и полезные уточнения. Для out-of-scope — отсутствие неподтверждённого конкретного ответа. Retrieval оцениваем по разделам и подтверждающим фрагментам, независимо от chunk ID; пустой набор источников у out-of-scope не включаем в обычный Recall@K.

## P01. Мяч над боковой линией

- Тип: answerable; прямое правило. Источник: 9.1. EN: 101 (101); RU: 103 (101).
- RU: Часть мяча ещё находится над боковой линией, остальная часть уже за ней. Судья игру не останавливал. Мяч уже вне игры?
- EN: Part of the ball still overhangs the touchline and the rest is beyond it. The referee has not stopped play. Is the ball out of play?
- Ответ RU: Нет. Для выхода через боковую линию мяч должен полностью пересечь её, в том числе по воздуху.
- Answer EN: No. The entire ball must cross the touchline, including when it is in the air.
- Проверяем: отсутствие ошибочного критерия «центр мяча пересёк линию».

## P02. Положение само по себе

- Тип: answerable; исключение из бытового упрощения. Источник: 11.1–11.2. EN: 109–110 (109–110); RU: 111–112 (109–110).
- RU: В момент паса партнёра нападающий находится в положении «вне игры», но затем не играет в мяч, не мешает соперникам и не получает преимущества после отскока или спасения ворот. Нужно ли останавливать игру только из-за его позиции?
- EN: At the moment of a team-mate's pass, an attacker is in an offside position but subsequently neither plays the ball nor interferes with opponents nor gains an advantage from a rebound or save. Must play stop just because of the position?
- Ответ RU: Нет. Одной позиции недостаточно: для наказания нужны активные действия, предусмотренные Правилом 11.
- Answer EN: No. Position alone is insufficient; an offence requires active involvement of the kinds specified in Law 11.
- Проверяем: различение позиции и нарушения, без утверждения, что только касание мяча образует нарушение.

## P03. Непосредственно после вбрасывания

- Тип: answerable; исключение. Источник: 11.3. EN: 111 (111); RU: 114 (112).
- RU: Нападающий получает мяч непосредственно после правильно выполненного вбрасывания партнёром. Других нарушений нет. Можно ли наказать его за «вне игры» при таком получении мяча?
- EN: An attacker receives the ball directly from a correctly taken throw-in by a team-mate. There is no other offence. Can the attacker be penalised for offside on receiving it?
- Ответ RU: Нет. При непосредственном получении мяча после вбрасывания нарушения «вне игры» нет.
- Answer EN: No. Receiving the ball directly from a throw-in does not constitute an offside offence.
- Проверяем: существенность слова «непосредственно»; исключение не распространяется автоматически на следующий пас.

## P04. Выбегание со своей половины

- Тип: answerable; применение временного условия. Источник: 11.1–11.2. EN: 109 (109); RU: 111 (109).
- RU: В момент, когда партнёр играет в мяч, нападающий целиком на своей половине. Он выбегает за защитников и принимает этот пас уже на половине соперника; новых касаний партнёров не было. Есть ли «вне игры» из-за его позиции при приёме?
- EN: When a team-mate plays the ball, an attacker is entirely in their own half. The attacker runs beyond the defenders and receives that pass in the opponents' half, with no further team-mate touches. Is the position at reception an offside offence?
- Ответ RU: Нет. Для этой передачи важна позиция в момент игры партнёра в мяч; тогда нападающий был на своей половине.
- Answer EN: No. For this pass, position is assessed when the team-mate plays the ball; the attacker was then in their own half.
- Проверяем: момент оценки; не принимать общее утверждение, что любое нарушение «вне игры» невозможно на своей половине.

## P05. Вратарь держит мяч девять секунд

- Тип: answerable; проверка редакции. Источник: 12.3. EN: 119 (119); RU: 121–122 (119–120).
- RU: По Правилам 2026/27 вратарь в своей штрафной контролирует мяч руками девять секунд. Судья определил начало контроля и показал отсчёт последних пяти секунд. Как возобновляется игра за превышение времени?
- EN: Under the 2026/27 Laws, a goalkeeper controls the ball with the hands in their own penalty area for nine seconds. The referee established the start of control and displayed the final five-second countdown. What restart follows the time violation?
- Ответ RU: Угловой в пользу соперника: превышен восьмисекундный предел контроля руками.
- Answer EN: A corner kick to the opponents, because hand control exceeded the eight-second limit.
- Проверяем: правильную редакцию; свободный удар за старое шестисекундное ограничение — ошибка.

## P06. Безрассудная подножка в штрафной

- Тип: answerable; несколько положений. Источники: 12.1, 12.4, вступление к 14. EN: 115, 122, 135; RU: 117 (115), 124 (122), 139 (137).
- RU: Мяч в игре. Защитник в своей штрафной делает сопернику подножку с контактом. Судья оценил действие как безрассудное, но без чрезмерной силы; явная возможность забить гол не была сорвана. Игра сразу остановлена. Каковы возобновление и дисциплинарная санкция?
- EN: The ball is in play. A defender trips an opponent with contact inside the defender's penalty area. The referee judges it reckless, without excessive force, and no obvious goal-scoring opportunity was denied. Play is stopped immediately. What restart and disciplinary sanction follow?
- Ответ RU: Пенальти и предупреждение защитнику: подножка относится к нарушениям для штрафного удара, место нарушения даёт пенальти, а безрассудность требует жёлтой карточки.
- Answer EN: A penalty kick and a caution: tripping is a direct-free-kick offence, its location makes the restart a penalty, and recklessness requires a yellow card.
- Проверяем: оба решения и связь каждого с условиями; не смешивать безрассудность с чрезмерной силой.

## P07. Свободный удар сразу в ворота

- Тип: answerable; терминология и исключение. Источник: 13.1. EN: 131 (131); RU: 135 (133).
- RU: Судья правильно показал, что удар свободный. После правильного выполнения мяч без касаний других игроков попадает прямо в ворота соперника. Гол засчитывается? Если нет, что дальше?
- EN: The referee correctly signals an indirect free kick. It is correctly taken and enters the opponents' goal without touching another player. Does the goal count, and if not, what is the restart?
- Ответ RU: Гол не засчитывается; назначается удар от ворот.
- Answer EN: The goal does not count; the restart is a goal kick.
- Проверяем: перевод indirect free kick как «свободный»; условие о правильном сигнале исключает повтор удара из-за отсутствия сигнала.

## P08. Гол непосредственно с вбрасывания

- Тип: answerable; исключение. Источник: вступление к 15. EN: 141 (141); RU: 147 (145).
- RU: При правильном вбрасывании мяч входит в поле и без касаний других игроков попадает в ворота соперника. Гол или другое решение?
- EN: From a correctly taken throw-in, the ball enters the field and then the opponents' goal without touching another player. Is it a goal, or what is the decision?
- Ответ RU: Гол не засчитывается; соперник выполняет удар от ворот.
- Answer EN: No goal is awarded; the opponents take a goal kick.
- Проверяем: запрет гола непосредственно с вбрасывания, отсутствие придуманного повторного вбрасывания.

## P09. Вратарь берёт пас ногой от партнёра

- Тип: answerable; условия и исключение. Источник: 12.2. EN: 118 (118); RU: 120–121 (118–119).
- RU: Партнёр умышленно пасует вратарю ногой с игры. Вратарь в своей штрафной сразу берёт мяч руками, не пытаясь сначала выбить его ногой. Какое возобновление предусмотрено?
- EN: During open play, a team-mate deliberately kicks the ball to the goalkeeper. Inside the goalkeeper's own penalty area, the goalkeeper immediately picks it up without first attempting a clearance with the foot. What restart is required?
- Ответ RU: Свободный удар в пользу соперника. Вратарь коснулся руками мяча после намеренного паса ногой от партнёра; описанное исключение с попыткой выбить мяч не применяется.
- Answer EN: An indirect free kick to the opponents. The goalkeeper handled a deliberate kick from a team-mate, and the stated clearance-attempt exception does not apply.
- Проверяем: свободный удар вместо пенальти; не обобщать запрет на любые передачи от партнёра.

## P10. Одного касания руки недостаточно

- Тип: insufficient_information; объяснение и уточнение. Источник: 12.1, игра рукой. EN: 116 (116); RU: 118 (116).
- RU: Мяч попал в руку защитнику в его штрафной. Больше об эпизоде ничего не известно. Это точно пенальти?
- EN: The ball hit a defender's arm inside their own penalty area. Nothing else about the incident is known. Is it definitely a penalty?
- Ответ RU: Одного этого факта недостаточно: не каждое касание руки — нарушение. Нужно выяснить, было ли движение руки к мячу, как располагалась рука и оправдывалось ли её положение движением тела в этой ситуации. Без этих данных нельзя уверенно назначить пенальти или исключить его.
- Answer EN: That fact alone is insufficient: arm contact is not automatically an offence. We need to know whether the arm moved towards the ball and whether its position made the body unnaturally bigger or was justified by the movement in that situation. Neither a definite penalty nor a definite no-penalty decision is supported.
- Проверяем: полезное объяснение вместо голого отказа; нельзя выдумывать положение руки, намерение или движение.

## P11. Недоигранный матч

- Тип: conditional_answer; правило плюс внешнее условие. Источник: 7.5. EN: 94 (94); RU: 96 (94).
- RU: Матч окончательно прекращён из-за погоды. Название турнира и его регламент неизвестны. Он обязательно переигрывается с начала?
- EN: A match is abandoned because of the weather. The competition and its rules are unknown. Must it necessarily be replayed from the start?
- Ответ RU: В Правилах предусмотрена переигровка, но регламент или организатор соревнования может определить иначе. Поэтому обязательную переигровку именно этого матча утверждать нельзя; нужен регламент или решение организатора.
- Answer EN: The Laws provide for a replay unless the competition rules or organisers determine otherwise. A mandatory replay for this particular match cannot be asserted without those rules or a decision by the organisers.
- Проверяем: общее правило вместе с исключением; не придумывать технический результат или продолжение с конкретной минуты.

## P12. Срок дисквалификации

- Тип: out_of_scope; отсутствует необходимый документ. Подтверждающего раздела для числа матчей нет. Связанные положения об удалении: 12.4, EN: 123–124; RU: 126–127 (124–125); они не задают универсальный срок дисквалификации для этого вопроса.
- RU: Игрок получил прямую красную карточку за агрессивное поведение. На сколько следующих матчей его дисквалифицируют? Турнир не указан, его дисциплинарного регламента в корпусе нет.
- EN: A player receives a straight red card for violent conduct. How many subsequent matches will the suspension last? The competition is unspecified and its disciplinary regulations are not in the corpus.
- Ответ RU: По доступным документам нельзя установить число матчей. Нужны название соревнования, применимый дисциплинарный регламент и, при необходимости, решение дисциплинарного органа. Последствия удаления в текущем матче не определяют сами по себе срок будущей дисквалификации.
- Answer EN: The available documents do not establish a number of matches. We need the competition, its applicable disciplinary regulations and, where relevant, the disciplinary body's decision. Removal from the current match does not itself establish the length of a future suspension.
- Проверяем: отсутствие выдуманных «один/три матча»; не приписывать срок Правилам IFAB.

## Ограничения и следующий шаг

Пилот охватывает правила 7, 9, 11–15, не все 17 правил. В нём 9 answerable, 1 insufficient_information, 1 conditional_answer и 1 out_of_scope. Этого достаточно, чтобы обсудить формат; недостаточно для статистически убедительного сравнения систем или измерения полноты корпуса.

Источники каждого примера сверены по извлечённому тексту соответствующих страниц обоих PDF; визуально выборочно проверены обложки и положения о восьми секундах. Полный визуальный аудит PDF и экспертная судейская проверка не выполнены. Проверка полноты парсинга — отдельный следующий этап.

После совместного разбора исправляем вопросы и эталоны, затем переносим согласованную структуру в JSONL. Синтетические кандидаты могут ускорить расширение, но без проверки источника не получают статус эталона. При расширении добавляем оставшиеся правила, естественные пользовательские формулировки, несколько обязательных источников и отдельный закрытый от настройки test. Отдельно планируем оценку иллюстраций; эти 12 ситуаций текстовые.
