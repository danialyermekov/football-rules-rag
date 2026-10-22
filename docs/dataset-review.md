# Датасет v0.2: 100 ситуаций для ревью

Сгенерировано агентом по IFAB 2026/27. 100 ситуаций / 200 вопросов. Dev: 75 ситуаций / 150 вопросов; test: 25 / 50. Статус: проверка источников тем же агентом; независимой судейской проверки нет. Это черновик, не отчёт о качестве RAG.

Канонические данные: [scenarios.jsonl](../data/evaluation/scenarios.jsonl). [Схема, проверка и ограничения](../data/evaluation/README.md). Этот файл — представление JSONL для чтения; изменять нужно канонические записи и обновлять представление.

В строках источников: язык, PDF-страница и напечатанная страница в скобках. required — необходимые доказательства, related — связанный материал, который не даёт отсутствующий ответ. Полные тексты источников здесь не воспроизводятся.

## FR001 — ball_boundary

Тип: `answerable`. Split: `dev`.

**RU:** Часть мяча ещё находится над боковой линией, остальная часть уже за ней. Судья игру не останавливал. Мяч уже вне игры?

**EN:** Part of the ball still overhangs the touchline and the rest is beyond it. The referee has not stopped play. Is the ball out of play?

**Эталон RU:** Нет. Для выхода через боковую линию мяч должен полностью пересечь её, в том числе по воздуху.

**Reference EN:** No. The entire ball must cross the touchline, including when it is in the air.

**Обязательные пункты RU:**

- Мяч ещё в игре.
- Весь мяч должен пересечь линию.

**Required points EN:**

- The ball is still in play.
- The entire ball must cross the line.

**Недопустимо:** Центра мяча за линией достаточно.

**Must not claim:** The centre crossing the line is sufficient.

**Источники:**

- required_evidence: `ball_out`, раздел 9.1; EN: 101 (101); RU: 103 (101).

## FR002 — offside_active

Тип: `answerable`. Split: `dev`.

**RU:** В момент паса партнёра нападающий находится в положении «вне игры», но затем не играет в мяч, не мешает соперникам и не получает преимущества после отскока или спасения ворот. Нужно ли останавливать игру только из-за его позиции?

**EN:** At the moment of a team-mate's pass, an attacker is in an offside position but subsequently neither plays the ball nor interferes with opponents nor gains an advantage from a rebound or save. Must play stop just because of the position?

**Эталон RU:** Нет. Одной позиции недостаточно: для наказания нужны активные действия, предусмотренные Правилом 11.

**Reference EN:** No. Position alone is insufficient; an offence requires active involvement of the kinds specified in Law 11.

**Обязательные пункты RU:**

- Позиция сама по себе не нарушение.
- Нужно активное участие по Правилу 11.

**Required points EN:**

- Position alone is not an offence.
- Active involvement under Law 11 is required.

**Недопустимо:** Нарушение возможно только при касании мяча.

**Must not claim:** Only touching the ball can be an offside offence.

**Источники:**

- required_evidence: `offside_position`, раздел 11.1; EN: 109 (109); RU: 111 (109).
- required_evidence: `offside_active`, раздел 11.2; EN: 109 (109), 110 (110); RU: 111 (109), 112 (110).

## FR003 — offside_restart

Тип: `answerable`. Split: `dev`.

**RU:** Нападающий получает мяч непосредственно после правильно выполненного вбрасывания партнёром. Других нарушений нет. Можно ли наказать его за «вне игры» при таком получении мяча?

**EN:** An attacker receives the ball directly from a correctly taken throw-in by a team-mate. There is no other offence. Can the attacker be penalised for offside on receiving it?

**Эталон RU:** Нет. При непосредственном получении мяча после вбрасывания нарушения «вне игры» нет.

**Reference EN:** No. Receiving the ball directly from a throw-in does not constitute an offside offence.

**Обязательные пункты RU:**

- Нет нарушения при непосредственном получении после вбрасывания.

**Required points EN:**

- There is no offence when receiving directly from a throw-in.

**Недопустимо:** Исключение автоматически действует и на следующий пас.

**Must not claim:** The exception automatically applies to the next pass.

**Источники:**

- required_evidence: `offside_exceptions`, раздел 11.3; EN: 111 (111); RU: 114 (112).

## FR004 — offside_timing

Тип: `answerable`. Split: `dev`.

**RU:** В момент, когда партнёр играет в мяч, нападающий целиком на своей половине. Он выбегает за защитников и принимает этот пас уже на половине соперника; новых касаний партнёров не было. Есть ли «вне игры» из-за его позиции при приёме?

**EN:** When a team-mate plays the ball, an attacker is entirely in their own half. The attacker runs beyond the defenders and receives that pass in the opponents' half, with no further team-mate touches. Is the position at reception an offside offence?

**Эталон RU:** Нет. Для этой передачи важна позиция в момент игры партнёра в мяч; тогда нападающий был на своей половине.

**Reference EN:** No. For this pass, position is assessed when the team-mate plays the ball; the attacker was then in their own half.

**Обязательные пункты RU:**

- Нет нарушения по описанной позиции.
- Важна позиция в момент игры партнёра в мяч.

**Required points EN:**

- There is no offence from the described position.
- Position is assessed when the team-mate plays the ball.

**Недопустимо:** Позиция при приёме определяет нарушение для этой передачи.

**Must not claim:** Position at reception determines offside for this pass.

**Источники:**

- required_evidence: `offside_position`, раздел 11.1; EN: 109 (109); RU: 111 (109).
- required_evidence: `offside_active`, раздел 11.2; EN: 109 (109), 110 (110); RU: 111 (109), 112 (110).

## FR005 — keeper_time

Тип: `answerable`. Split: `dev`.

**RU:** По Правилам 2026/27 вратарь в своей штрафной контролирует мяч руками девять секунд. Судья определил начало контроля и показал отсчёт последних пяти секунд. Как возобновляется игра за превышение времени?

**EN:** Under the 2026/27 Laws, a goalkeeper controls the ball with the hands in their own penalty area for nine seconds. The referee established the start of control and displayed the final five-second countdown. What restart follows the time violation?

**Эталон RU:** Угловой в пользу соперника: превышен восьмисекундный предел контроля руками.

**Reference EN:** A corner kick to the opponents, because hand control exceeded the eight-second limit.

**Обязательные пункты RU:**

- Угловой сопернику.
- Предел контроля руками — восемь секунд.

**Required points EN:**

- A corner kick to the opponents.
- The hand-control limit is eight seconds.

**Недопустимо:** Свободный удар за превышение шести секунд.

**Must not claim:** An indirect free kick for exceeding six seconds.

**Источники:**

- required_evidence: `keeper_time`, раздел 12.3; EN: 119 (119); RU: 121 (119), 122 (120).

## FR006 — reckless_penalty

Тип: `answerable`. Split: `dev`.

**RU:** Мяч в игре. Защитник в своей штрафной делает сопернику подножку с контактом. Судья оценил действие как безрассудное, но без чрезмерной силы; явная возможность забить гол не была сорвана. Игра сразу остановлена. Каковы возобновление и дисциплинарная санкция?

**EN:** The ball is in play. A defender trips an opponent with contact inside the defender's penalty area. The referee judges it reckless, without excessive force, and no obvious goal-scoring opportunity was denied. Play is stopped immediately. What restart and disciplinary sanction follow?

**Эталон RU:** Пенальти и предупреждение защитнику: подножка относится к нарушениям для штрафного удара, место нарушения даёт пенальти, а безрассудность требует жёлтой карточки.

**Reference EN:** A penalty kick and a caution: tripping is a direct-free-kick offence, its location makes the restart a penalty, and recklessness requires a yellow card.

**Обязательные пункты RU:**

- Пенальти.
- Предупреждение за безрассудность.

**Required points EN:**

- A penalty kick.
- A caution for recklessness.

**Недопустимо:** За описанное действие обязательно удаляют.

**Must not claim:** The described challenge necessarily requires a sending-off.

**Источники:**

- required_evidence: `reckless`, раздел 12.1; EN: 115 (115); RU: 117 (115).
- required_evidence: `penalty_award`, раздел 14.intro; EN: 135 (135); RU: 139 (137).

## FR007 — restart_direct_goal

Тип: `answerable`. Split: `dev`.

**RU:** Судья правильно показал, что удар свободный. После правильного выполнения мяч без касаний других игроков попадает прямо в ворота соперника. Гол засчитывается? Если нет, что дальше?

**EN:** The referee correctly signals an indirect free kick. It is correctly taken and enters the opponents' goal without touching another player. Does the goal count, and if not, what is the restart?

**Эталон RU:** Гол не засчитывается; назначается удар от ворот.

**Reference EN:** The goal does not count; the restart is a goal kick.

**Обязательные пункты RU:**

- Гол не засчитывается.
- Удар от ворот.

**Required points EN:**

- No goal.
- A goal kick.

**Недопустимо:** Повторить удар несмотря на правильный сигнал судьи.

**Must not claim:** Retake despite the correct referee signal.

**Источники:**

- required_evidence: `free_goal`, раздел 13.1; EN: 131 (131); RU: 135 (133).

## FR008 — restart_direct_goal

Тип: `answerable`. Split: `dev`.

**RU:** При правильном вбрасывании мяч входит в поле и без касаний других игроков попадает в ворота соперника. Гол или другое решение?

**EN:** From a correctly taken throw-in, the ball enters the field and then the opponents' goal without touching another player. Is it a goal, or what is the decision?

**Эталон RU:** Гол не засчитывается; соперник выполняет удар от ворот.

**Reference EN:** No goal is awarded; the opponents take a goal kick.

**Обязательные пункты RU:**

- Гол не засчитывается.
- Удар от ворот сопернику.

**Required points EN:**

- No goal.
- A goal kick to the opponents.

**Недопустимо:** Гол непосредственно с вбрасывания засчитывается.

**Must not claim:** A goal directly from a throw-in counts.

**Источники:**

- required_evidence: `throw_goal`, раздел 15.intro; EN: 141 (141); RU: 147 (145).

## FR009 — keeper_backpass

Тип: `answerable`. Split: `dev`.

**RU:** Партнёр умышленно пасует вратарю ногой с игры. Вратарь в своей штрафной сразу берёт мяч руками, не пытаясь сначала выбить его ногой. Какое возобновление предусмотрено?

**EN:** During open play, a team-mate deliberately kicks the ball to the goalkeeper. Inside the goalkeeper's own penalty area, the goalkeeper immediately picks it up without first attempting a clearance with the foot. What restart is required?

**Эталон RU:** Свободный удар в пользу соперника. Вратарь коснулся руками мяча после намеренного паса ногой от партнёра; описанное исключение с попыткой выбить мяч не применяется.

**Reference EN:** An indirect free kick to the opponents. The goalkeeper handled a deliberate kick from a team-mate, and the stated clearance-attempt exception does not apply.

**Обязательные пункты RU:**

- Свободный удар сопернику.
- Намеренный пас ногой и последующее касание руками.

**Required points EN:**

- An indirect free kick to the opponents.
- A deliberate team-mate kick followed by handling.

**Недопустимо:** Пенальти за это касание вратаря.

**Must not claim:** A penalty kick for this handling.

**Источники:**

- required_evidence: `backpass`, раздел 12.2; EN: 118 (118); RU: 120 (118), 121 (119).

## FR010 — handball_uncertainty

Тип: `insufficient_information`. Split: `dev`.

**RU:** Мяч попал в руку защитнику в его штрафной. Больше об эпизоде ничего не известно. Это точно пенальти?

**EN:** The ball hit a defender's arm inside their own penalty area. Nothing else about the incident is known. Is it definitely a penalty?

**Эталон RU:** Одного этого факта недостаточно: не каждое касание руки — нарушение. Нужно выяснить, было ли движение руки к мячу, как располагалась рука и оправдывалось ли её положение движением тела в этой ситуации. Без этих данных нельзя уверенно назначить пенальти или исключить его.

**Reference EN:** That fact alone is insufficient: arm contact is not automatically an offence. We need to know whether the arm moved towards the ball and whether its position made the body unnaturally bigger or was justified by the movement in that situation. Neither a definite penalty nor a definite no-penalty decision is supported.

**Обязательные пункты RU:**

- Одного факта касания недостаточно.
- Нужно выяснить движение и положение руки в ситуации.

**Required points EN:**

- Contact alone is insufficient.
- The arm movement and position in the situation must be established.

**Недопустимо:** Это точно пенальти либо точно не пенальти.

**Must not claim:** It is definitely a penalty or definitely not a penalty.

**Источники:**

- required_evidence: `handball`, раздел 12.1.handball; EN: 116 (116); RU: 118 (116).

## FR011 — competition_outcome

Тип: `conditional_answer`. Split: `dev`.

**RU:** Матч окончательно прекращён из-за погоды. Название турнира и его регламент неизвестны. Он обязательно переигрывается с начала?

**EN:** A match is abandoned because of the weather. The competition and its rules are unknown. Must it necessarily be replayed from the start?

**Эталон RU:** В Правилах предусмотрена переигровка, но регламент или организатор соревнования может определить иначе. Поэтому обязательную переигровку именно этого матча утверждать нельзя; нужен регламент или решение организатора.

**Reference EN:** The Laws provide for a replay unless the competition rules or organisers determine otherwise. A mandatory replay for this particular match cannot be asserted without those rules or a decision by the organisers.

**Обязательные пункты RU:**

- Общее правило — переигровка.
- Регламент или организатор может определить иначе.
- Нельзя дать обязательное решение для конкретного матча.

**Required points EN:**

- The default is a replay.
- Competition rules or organisers may determine otherwise.
- A mandatory outcome for this match cannot be asserted.

**Недопустимо:** Всегда переигрывается без исключений.

**Must not claim:** A replay is mandatory without exceptions.

**Источники:**

- required_evidence: `abandoned`, раздел 7.5; EN: 94 (94); RU: 96 (94).

## FR012 — disciplinary_regulations

Тип: `out_of_scope`. Split: `dev`.

**RU:** Игрок получил прямую красную карточку за агрессивное поведение. На сколько следующих матчей его дисквалифицируют? Турнир не указан, его дисциплинарного регламента в корпусе нет.

**EN:** A player receives a straight red card for violent conduct. How many subsequent matches will the suspension last? The competition is unspecified and its disciplinary regulations are not in the corpus.

**Эталон RU:** По доступным документам нельзя установить число матчей. Нужны название соревнования, применимый дисциплинарный регламент и, при необходимости, решение дисциплинарного органа. Последствия удаления в текущем матче не определяют сами по себе срок будущей дисквалификации.

**Reference EN:** The available documents do not establish a number of matches. We need the competition, its applicable disciplinary regulations and, where relevant, the disciplinary body's decision. Removal from the current match does not itself establish the length of a future suspension.

**Обязательные пункты RU:**

- Число матчей неизвестно.
- Нужны дисциплинарный регламент соревнования и применимое решение.

**Required points EN:**

- The number of matches is unknown.
- The competition disciplinary regulations and applicable decision are needed.

**Недопустимо:** Универсальный срок в один или три матча установлен IFAB.

**Must not claim:** IFAB establishes a universal one- or three-match ban.

**Источники:**

- related_evidence: `sending_off`, раздел 12.4; EN: 123 (123); RU: 126 (124).
- Доказательства конкретного ответа в корпусе отсутствуют; не включать вопрос в обычный Recall@K.

## FR013 — penalty_boundary

Тип: `answerable`. Split: `test`.

**RU:** Защитник при мяче в игре совершил нарушение против соперника, наказуемое штрафным ударом, точно на линии собственной штрафной площади. Это пенальти или штрафной снаружи?

**EN:** With the ball in play, a defender commits a direct-free-kick offence against an opponent exactly on the boundary line of their own penalty area. Is it a penalty or a free kick outside?

**Эталон RU:** Пенальти. Линия относится к площади, которую ограничивает.

**Reference EN:** A penalty kick. The boundary line belongs to the area it encloses.

**Обязательные пункты RU:**

- Пенальти.
- Линия относится к площади, которую ограничивает.

**Required points EN:**

- A penalty kick.
- The boundary line belongs to the area it encloses.

**Недопустимо:** Линия штрафной находится вне штрафной площади.

**Must not claim:** The penalty-area line is outside that area.

**Источники:**

- required_evidence: `field_lines`, раздел 1.2; EN: 45 (45); RU: 45 (43).
- required_evidence: `penalty_award`, раздел 14.intro; EN: 135 (135); RU: 139 (137).

## FR014 — goal_dimensions

Тип: `answerable`. Split: `dev`.

**RU:** Каковы ширина и высота стандартных ворот по Правилам IFAB для обычного футбола? Откуда их измеряют?

**EN:** What are the standard goal width and height under IFAB Laws for association football, and where are they measured from?

**Эталон RU:** Ширина 7,32 м между внутренними сторонами стоек. Высота 2,44 м от земли до нижней кромки перекладины.

**Reference EN:** Width is 7.32 m between the inside edges of the posts. Height is 2.44 m from the ground to the lower edge of the crossbar.

**Обязательные пункты RU:**

- Ширина 7,32 м между внутренними сторонами стоек.
- Высота 2,44 м от земли до нижней кромки перекладины.

**Required points EN:**

- Width is 7.32 m between the inside edges of the posts.
- Height is 2.44 m from the ground to the lower edge of the crossbar.

**Недопустимо:** Размеры измеряются по наружным краям стоек и верху перекладины.

**Must not claim:** Measurements use the outside edges of the posts and top of the crossbar.

**Источники:**

- required_evidence: `goal_dimensions`, раздел 1.10; EN: 50 (50); RU: 49 (47).

## FR015 — broken_goal

Тип: `answerable`. Split: `dev`.

**RU:** Перекладина сломалась во время игры. Можно ли заменить её верёвкой и продолжить матч?

**EN:** The crossbar breaks during play. Can a rope replace it so the match can continue?

**Эталон RU:** Нет, верёвка не допускается. Игру останавливают до ремонта или замены перекладины; после ремонта — спорный мяч. Если ремонт невозможен, матч прекращают.

**Reference EN:** No, a rope is not allowed. Play stops for repair or replacement; after repair the restart is a dropped ball. If repair is impossible, the match is abandoned.

**Обязательные пункты RU:**

- Нет, верёвка не допускается.
- Игру останавливают до ремонта или замены перекладины; после ремонта — спорный мяч.
- Если ремонт невозможен, матч прекращают.

**Required points EN:**

- No, a rope is not allowed.
- Play stops for repair or replacement; after repair the restart is a dropped ball.
- If repair is impossible, the match is abandoned.

**Недопустимо:** Верёвка допустима по согласию капитанов.

**Must not claim:** A rope is allowed if the captains agree.

**Источники:**

- required_evidence: `broken_crossbar`, раздел 1.10; EN: 50 (50); RU: 50 (48).

## FR016 — ball_specification

Тип: `answerable`. Split: `test`.

**RU:** Какими должны быть окружность и масса мяча в начале матча обычного футбола по IFAB?

**EN:** What circumference and weight must an association-football ball have at the start of a match under IFAB Laws?

**Эталон RU:** Окружность 68–70 см. Масса в начале матча 410–450 г.

**Reference EN:** Circumference is 68–70 cm. Weight at the start of the match is 410–450 g.

**Обязательные пункты RU:**

- Окружность 68–70 см.
- Масса в начале матча 410–450 г.

**Required points EN:**

- Circumference is 68–70 cm.
- Weight at the start of the match is 410–450 g.

**Недопустимо:** Эти требования гарантируют пригодность мяча для любой возрастной модификации.

**Must not claim:** These specifications necessarily apply to every youth modification.

**Источники:**

- required_evidence: `ball_specs`, раздел 2.1; EN: 55 (55); RU: 55 (53).

## FR017 — defective_ball

Тип: `answerable`. Split: `dev`.

**RU:** Мяч лопнул во время обычной игры, не при выполнении возобновления. Что делает судья и как возобновляет игру?

**EN:** The ball bursts during ordinary open play, not while a restart is being taken. What must the referee do and how is play restarted?

**Эталон RU:** Остановить игру. Заменить мяч и возобновить спорным мячом.

**Reference EN:** Stop play. Replace the ball and restart with a dropped ball.

**Обязательные пункты RU:**

- Остановить игру.
- Заменить мяч и возобновить спорным мячом.

**Required points EN:**

- Stop play.
- Replace the ball and restart with a dropped ball.

**Недопустимо:** Всегда назначается свободный удар команде последнего касания.

**Must not claim:** An indirect free kick always goes to the team that last touched it.

**Источники:**

- required_evidence: `ball_defective`, раздел 2.2; EN: 56 (56); RU: 56 (54).

## FR018 — defective_ball

Тип: `answerable`. Split: `dev`.

**RU:** При пенальти мяч лопнул, двигаясь вперёд, до касания любого игрока, стойки или перекладины. Каково решение?

**EN:** During a penalty kick, the ball bursts while moving forward before touching a player, goalpost or crossbar. What is the decision?

**Эталон RU:** Пенальти повторяется. Существенны движение вперёд и отсутствие указанных касаний.

**Reference EN:** The penalty kick is retaken. Forward movement and the absence of those contacts are material.

**Обязательные пункты RU:**

- Пенальти повторяется.
- Существенны движение вперёд и отсутствие указанных касаний.

**Required points EN:**

- The penalty kick is retaken.
- Forward movement and the absence of those contacts are material.

**Недопустимо:** Назначается спорный мяч вместо повторного пенальти.

**Must not claim:** A dropped ball replaces the penalty retake.

**Источники:**

- required_evidence: `ball_defective_penalty`, раздел 2.2; EN: 56 (56); RU: 56 (54).

## FR019 — minimum_players

Тип: `answerable`. Split: `dev`.

**RU:** На момент начала матча у команды шесть игроков, включая вратаря. Может ли судья начать матч?

**EN:** At kick-off a team has six players including the goalkeeper. May the referee start the match?

**Эталон RU:** Нет. Для начала матча необходимо не менее семи игроков у каждой команды.

**Reference EN:** No. Each team needs at least seven players for the match to start.

**Обязательные пункты RU:**

- Нет.
- Для начала матча необходимо не менее семи игроков у каждой команды.

**Required points EN:**

- No.
- Each team needs at least seven players for the match to start.

**Недопустимо:** Согласия соперника достаточно для начала с шестью.

**Must not claim:** The opponents agreeing permits a six-player start.

**Источники:**

- required_evidence: `minimum_players`, раздел 3.1; EN: 59 (59); RU: 59 (57).

## FR020 — substitution_completion

Тип: `answerable`. Split: `dev`.

**RU:** Запасной правильно вышел на поле вместо заменённого игрока с разрешения судьи. Может ли он сразу выполнить угловой?

**EN:** A substitute correctly enters for the replaced player with the referee’s permission. May that substitute immediately take a corner kick?

**Эталон RU:** Да. После выхода замена завершена и новый игрок вправе выполнить любое возобновление.

**Reference EN:** Yes. Entry completes the substitution and the new player may take any restart.

**Обязательные пункты RU:**

- Да.
- После выхода замена завершена и новый игрок вправе выполнить любое возобновление.

**Required points EN:**

- Yes.
- Entry completes the substitution and the new player may take any restart.

**Недопустимо:** Сначала другой игрок обязательно должен коснуться мяча.

**Must not claim:** Another player must touch the ball first.

**Источники:**

- required_evidence: `sub_completion`, раздел 3.3; EN: 62 (62); RU: 62 (60).

## FR021 — goalkeeper_change

Тип: `answerable`. Split: `test`.

**RU:** Может ли полевой игрок поменяться местами с вратарём без замены? Какие условия нужно соблюсти?

**EN:** May an outfield player change places with the goalkeeper without a substitution, and under what conditions?

**Эталон RU:** Да. Судью заранее информируют. Смена происходит во время остановки игры.

**Reference EN:** Yes. The referee must be informed beforehand. The change takes place during a stoppage.

**Обязательные пункты RU:**

- Да.
- Судью заранее информируют.
- Смена происходит во время остановки игры.

**Required points EN:**

- Yes.
- The referee must be informed beforehand.
- The change takes place during a stoppage.

**Недопустимо:** Достаточно поменяться футболками на ходу без уведомления.

**Must not claim:** Swapping shirts during play without informing the referee is sufficient.

**Источники:**

- required_evidence: `keeper_change`, раздел 3.4; EN: 62 (62); RU: 62 (60).

## FR022 — sending_off_replacement

Тип: `answerable`. Split: `dev`.

**RU:** Игрок удалён после начала матча. Может ли команда заменить его запасным, если ещё остались обычные замены?

**EN:** A player is sent off after kick-off. May a substitute replace that player if ordinary substitutions are still available?

**Эталон RU:** Нет. Удалённого после начала матча игрока заменить нельзя.

**Reference EN:** No. A player sent off after kick-off cannot be replaced.

**Обязательные пункты RU:**

- Нет.
- Удалённого после начала матча игрока заменить нельзя.

**Required points EN:**

- No.
- A player sent off after kick-off cannot be replaced.

**Недопустимо:** Неиспользованная замена позволяет восстановить число игроков.

**Must not claim:** An unused substitution allows the team to restore its numbers.

**Источники:**

- required_evidence: `red_replacement`, раздел 3.6; EN: 63 (63); RU: 63 (61).

## FR023 — equipment_safety

Тип: `answerable`. Split: `dev`.

**RU:** Судья признал аксессуар игрока опасным. Достаточно ли заклеить его тейпом, чтобы играть с ним?

**EN:** The referee judges a player’s accessory dangerous. Is covering it with tape enough to allow it?

**Эталон RU:** Нет. Опасный предмет нужно снять; заклеивание не заменяет удаление.

**Reference EN:** No. A dangerous item must be removed; taping does not make it permissible.

**Обязательные пункты RU:**

- Нет.
- Опасный предмет нужно снять; заклеивание не заменяет удаление.

**Required points EN:**

- No.
- A dangerous item must be removed; taping does not make it permissible.

**Недопустимо:** Любой опасный аксессуар можно оставить под тейпом.

**Must not claim:** Any dangerous accessory may remain if taped.

**Источники:**

- required_evidence: `dangerous_equipment`, раздел 4.1; EN: 67 (67); RU: 67 (65).

## FR024 — lost_boot

Тип: `answerable`. Split: `test`.

**RU:** Игрок случайно потерял бутсу и до следующей остановки забил гол. Других нарушений не было. Отменяется ли гол только из-за бутсы и когда её вернуть?

**EN:** A player accidentally loses a boot and scores before the next stoppage, with no other offence. Is the goal disallowed just for that, and when must the boot be replaced?

**Эталон RU:** Гол засчитывается. Бутсу нужно вернуть как можно скорее, не позднее следующего выхода мяча из игры.

**Reference EN:** The goal counts. The boot must be replaced as soon as possible and no later than when the ball next goes out of play.

**Обязательные пункты RU:**

- Гол засчитывается.
- Бутсу нужно вернуть как можно скорее, не позднее следующего выхода мяча из игры.

**Required points EN:**

- The goal counts.
- The boot must be replaced as soon as possible and no later than when the ball next goes out of play.

**Недопустимо:** Любой удар без бутсы автоматически запрещён.

**Must not claim:** Every kick without a boot is automatically illegal.

**Источники:**

- required_evidence: `lost_boot`, раздел 4.2; EN: 68 (68); RU: 68 (66).

## FR025 — keeper_colours

Тип: `answerable`. Split: `dev`.

**RU:** У вратарей обеих команд одинаковые по цвету футболки, запасных нет. Остальная экипировка соответствует правилам. Запрещено ли проводить матч только из-за этого?

**EN:** Both goalkeepers have the same shirt colour and neither has an alternative. All other equipment complies. Must the match be prevented solely for that reason?

**Эталон RU:** Нет. Судья разрешает матч при отсутствии другой футболки у обоих вратарей.

**Reference EN:** No. The referee allows the match when neither goalkeeper has another shirt.

**Обязательные пункты RU:**

- Нет.
- Судья разрешает матч при отсутствии другой футболки у обоих вратарей.

**Required points EN:**

- No.
- The referee allows the match when neither goalkeeper has another shirt.

**Недопустимо:** Матч обязательно отменяют из-за совпадения цветов вратарей.

**Must not claim:** Matching goalkeeper colours necessarily cancel the match.

**Источники:**

- required_evidence: `keeper_colours`, раздел 4.3; EN: 68 (68); RU: 68 (66).

## FR026 — advantage

Тип: `answerable`. Split: `dev`.

**RU:** Судья дал преимущество после нарушения, но ожидаемая выгода не возникла в течение нескольких секунд. Можно ли вернуться к первоначальному нарушению?

**EN:** The referee applies advantage after an offence, but the expected benefit does not arise within a few seconds. May the referee return to the original offence?

**Эталон RU:** Да. Если ожидаемое преимущество не реализовалось сразу или за несколько секунд, судья наказывает первоначальное нарушение.

**Reference EN:** Yes. The original offence is penalised if the anticipated advantage does not arise immediately or within a few seconds.

**Обязательные пункты RU:**

- Да.
- Если ожидаемое преимущество не реализовалось сразу или за несколько секунд, судья наказывает первоначальное нарушение.

**Required points EN:**

- Yes.
- The original offence is penalised if the anticipated advantage does not arise immediately or within a few seconds.

**Недопустимо:** Преимущество позволяет вернуться к нарушению через любое время.

**Must not claim:** Advantage permits returning to the offence after any amount of time.

**Источники:**

- required_evidence: `advantage`, раздел 5.3; EN: 74 (74); RU: 76 (74).

## FR027 — incapacitated_referee

Тип: `answerable`. Split: `test`.

**RU:** Судья получил травму и не может выполнять обязанности, но мяч ещё в игре и другие официальные лица контролируют происходящее. Всегда ли игра должна немедленно остановиться?

**EN:** The referee becomes incapacitated while the ball is still in play and other match officials are supervising. Must play always stop immediately?

**Эталон RU:** Нет. Игра может продолжаться под контролем других официальных лиц до следующего выхода мяча из игры.

**Reference EN:** No. Play may continue under other match officials until the ball next goes out of play.

**Обязательные пункты RU:**

- Нет.
- Игра может продолжаться под контролем других официальных лиц до следующего выхода мяча из игры.

**Required points EN:**

- No.
- Play may continue under other match officials until the ball next goes out of play.

**Недопустимо:** Без главного судьи можно доиграть матч без ограничения.

**Must not claim:** The entire match can continue without a referee without limitation.

**Источники:**

- required_evidence: `ref_incapacitated`, раздел 5.2; EN: 74 (74); RU: 76 (74).

## FR028 — assistant_role

Тип: `answerable`. Split: `dev`.

**RU:** Какие сигналы помощника судьи относятся к выходу мяча за пределы поля и выбору возобновления?

**EN:** What does an assistant referee indicate when the ball leaves the field and a restart must be identified?

**Эталон RU:** Полный выход мяча за пределы поля. Какая команда получает угловой, удар от ворот или вбрасывание.

**Reference EN:** That the whole ball has left the field. Which team is entitled to a corner kick, goal kick or throw-in.

**Обязательные пункты RU:**

- Полный выход мяча за пределы поля.
- Какая команда получает угловой, удар от ворот или вбрасывание.

**Required points EN:**

- That the whole ball has left the field.
- Which team is entitled to a corner kick, goal kick or throw-in.

**Недопустимо:** Частичного пересечения линии достаточно для сигнала о выходе.

**Must not claim:** Partial crossing is sufficient for an out-of-play indication.

**Источники:**

- required_evidence: `assistant_role`, раздел 6.1; EN: 86 (86); RU: 88 (86).

## FR029 — fourth_official

Тип: `answerable`. Split: `test`.

**RU:** Какова роль резервного судьи при замене и показе добавленного времени?

**EN:** What is the fourth official’s role in substitutions and the display of additional time?

**Эталон RU:** Контролирует процедуру замены. Показывает минимальное добавленное время, определённое главным судьёй.

**Reference EN:** Supervises the substitution procedure. Indicates the minimum additional time decided by the referee.

**Обязательные пункты RU:**

- Контролирует процедуру замены.
- Показывает минимальное добавленное время, определённое главным судьёй.

**Required points EN:**

- Supervises the substitution procedure.
- Indicates the minimum additional time decided by the referee.

**Недопустимо:** Резервный судья единолично определяет точную секунду финального свистка.

**Must not claim:** The fourth official alone fixes the exact second of the final whistle.

**Источники:**

- required_evidence: `fourth_role`, раздел 6.2; EN: 86 (86); RU: 88 (86).

## FR030 — additional_time

Тип: `answerable`. Split: `test`.

**RU:** Резервный судья показал минимум четыре добавленные минуты. В добавленное время были новые задержки. Может ли судья сыграть больше четырёх минут?

**EN:** The fourth official displays a minimum of four added minutes. Further delays occur during added time. May the referee allow more than four minutes?

**Эталон RU:** Да. Показанное время — минимум; судья может увеличить его, но не уменьшить.

**Reference EN:** Yes. The displayed time is a minimum and may be increased but not reduced.

**Обязательные пункты RU:**

- Да.
- Показанное время — минимум; судья может увеличить его, но не уменьшить.

**Required points EN:**

- Yes.
- The displayed time is a minimum and may be increased but not reduced.

**Недопустимо:** Четыре минуты — обязательный верхний предел.

**Must not claim:** Four minutes is a mandatory upper limit.

**Источники:**

- required_evidence: `added_time`, раздел 7.3; EN: 94 (94); RU: 96 (94).

## FR031 — half_time

Тип: `answerable`. Split: `dev`.

**RU:** Какой максимальный перерыв между таймами предусмотрен обычными Правилами IFAB, без специальных модификаций?

**EN:** What is the maximum half-time interval under the ordinary IFAB Laws, without special modifications?

**Эталон RU:** Не более 15 минут. Продолжительность указывается в регламенте; изменить её можно только с разрешения судьи.

**Reference EN:** No more than 15 minutes. Competition rules specify its duration; alteration requires the referee’s permission.

**Обязательные пункты RU:**

- Не более 15 минут.
- Продолжительность указывается в регламенте; изменить её можно только с разрешения судьи.

**Required points EN:**

- No more than 15 minutes.
- Competition rules specify its duration; alteration requires the referee’s permission.

**Недопустимо:** В каждом матче перерыв обязательно ровно 15 минут.

**Must not claim:** Every match must have an interval of exactly 15 minutes.

**Источники:**

- required_evidence: `half_time`, раздел 7.2; EN: 93 (93); RU: 95 (93).

## FR032 — restart_direct_goal

Тип: `answerable`. Split: `dev`.

**RU:** Игрок правильно выполнил начальный удар назад, и мяч без других касаний попал в его собственные ворота. Засчитывается ли автогол?

**EN:** A player correctly takes a kick-off backwards and the ball enters their own goal without another touch. Does an own goal count?

**Эталон RU:** Нет. Сопернику назначается угловой.

**Reference EN:** No. A corner kick is awarded to the opponents.

**Обязательные пункты RU:**

- Нет.
- Сопернику назначается угловой.

**Required points EN:**

- No.
- A corner kick is awarded to the opponents.

**Недопустимо:** Назначается повтор начального удара только из-за направления назад.

**Must not claim:** The kick-off is retaken solely because it went backwards.

**Источники:**

- required_evidence: `kickoff_goal`, раздел 8.1; EN: 98 (98); RU: 100 (98).

## FR033 — dropped_ball_procedure

Тип: `answerable`. Split: `dev`.

**RU:** При спорном мяче судья выделил одного игрока для получения мяча. На каком расстоянии должны быть все остальные, включая его партнёров?

**EN:** At a dropped ball the referee designates one player to receive it. How far away must all other players, including team-mates, remain?

**Эталон RU:** Не менее 4 м. До момента, когда мяч войдёт в игру, коснувшись земли.

**Reference EN:** At least 4 m. Until the ball is in play on touching the ground.

**Обязательные пункты RU:**

- Не менее 4 м.
- До момента, когда мяч войдёт в игру, коснувшись земли.

**Required points EN:**

- At least 4 m.
- Until the ball is in play on touching the ground.

**Недопустимо:** Партнёры получающего игрока могут стоять вплотную.

**Must not claim:** The receiving player’s team-mates may stand immediately next to the ball.

**Источники:**

- required_evidence: `drop_distance`, раздел 8.2; EN: 98 (98); RU: 100 (98).

## FR034 — dropped_ball_procedure

Тип: `answerable`. Split: `dev`.

**RU:** При спорном мяче игрок коснулся мяча до его касания земли. Как возобновить игру?

**EN:** At a dropped ball a player touches the ball before it touches the ground. How is play restarted?

**Эталон RU:** Спорный мяч выполняют снова. Мяч ещё не вошёл в игру.

**Reference EN:** Drop the ball again. It was not yet in play.

**Обязательные пункты RU:**

- Спорный мяч выполняют снова.
- Мяч ещё не вошёл в игру.

**Required points EN:**

- Drop the ball again.
- It was not yet in play.

**Недопустимо:** Сразу назначается свободный удар сопернику.

**Must not claim:** An indirect free kick is immediately awarded to the opponents.

**Источники:**

- required_evidence: `drop_retake`, раздел 8.2; EN: 98 (98); RU: 100 (98).

## FR035 — restart_direct_goal

Тип: `answerable`. Split: `dev`.

**RU:** Вратарь из своей штрафной бросил мяч рукой прямо в ворота соперника. Других касаний не было. Засчитывается ли гол?

**EN:** A goalkeeper throws the ball from their own penalty area directly into the opponents’ goal, without another touch. Does it count?

**Эталон RU:** Нет. Назначается удар от ворот сопернику.

**Reference EN:** No. A goal kick is awarded to the opponents.

**Обязательные пункты RU:**

- Нет.
- Назначается удар от ворот сопернику.

**Required points EN:**

- No.
- A goal kick is awarded to the opponents.

**Недопустимо:** Вратарь может забить рукой напрямую в ворота соперника.

**Must not claim:** A goalkeeper may score directly by throwing into the opponents’ goal.

**Источники:**

- required_evidence: `keeper_throw_goal`, раздел 10.1; EN: 103 (103); RU: 105 (103).

## FR036 — shootout_order

Тип: `answerable`. Split: `test`.

**RU:** В серии пенальти лучший бьющий уже выполнил удар, а один из остальных допущенных игроков его команды ещё не бил. Можно ли снова выбрать лучшего бьющего?

**EN:** In a penalty shoot-out the best kicker has already taken a kick, while another eligible team-mate has not. May the best kicker be chosen again now?

**Эталон RU:** Нет. Все допущенные игроки должны выполнить удар до второго удара любого из них.

**Reference EN:** No. Every eligible player must take a kick before any player takes a second.

**Обязательные пункты RU:**

- Нет.
- Все допущенные игроки должны выполнить удар до второго удара любого из них.

**Required points EN:**

- No.
- Every eligible player must take a kick before any player takes a second.

**Недопустимо:** Тренер может выбирать одного бьющего для всех ударов серии.

**Must not claim:** The coach may choose one player for every kick of the shoot-out.

**Источники:**

- required_evidence: `shootout_order`, раздел 10.3; EN: 106 (106); RU: 109 (107).

## FR037 — shootout_cautions

Тип: `answerable`. Split: `dev`.

**RU:** У игрока была одна жёлтая карточка в матче, он не удалён. Переносится ли это предупреждение в серию пенальти?

**EN:** A player received one yellow card during the match and was not sent off. Is that caution carried into the penalty shoot-out?

**Эталон RU:** Нет. Предупреждения матча в серию пенальти не переносятся.

**Reference EN:** No. Cautions from the match are not carried forward into the shoot-out.

**Обязательные пункты RU:**

- Нет.
- Предупреждения матча в серию пенальти не переносятся.

**Required points EN:**

- No.
- Cautions from the match are not carried forward into the shoot-out.

**Недопустимо:** Удалённый в матче игрок тоже получает право участвовать в серии.

**Must not claim:** A player sent off during the match also becomes eligible for the shoot-out.

**Источники:**

- required_evidence: `shootout_cautions`, раздел 10.3; EN: 103 (103); RU: 107 (105).

## FR038 — referee_ball_contact

Тип: `answerable`. Split: `test`.

**RU:** Мяч коснулся судьи, остался на поле, и из-за этого владение перешло к другой команде. Какое решение?

**EN:** The ball hits the referee, stays on the field, and possession changes to the other team as a result. What is the decision?

**Эталон RU:** Игру останавливают. Возобновление — спорный мяч.

**Reference EN:** Stop play. Restart with a dropped ball.

**Обязательные пункты RU:**

- Игру останавливают.
- Возобновление — спорный мяч.

**Required points EN:**

- Stop play.
- Restart with a dropped ball.

**Недопустимо:** Любое касание судьи всегда игнорируется.

**Must not claim:** Every contact with the referee is always ignored.

**Источники:**

- required_evidence: `ref_contact`, раздел 9.1; EN: 101 (101); RU: 103 (101).

## FR039 — ball_rebound

Тип: `answerable`. Split: `dev`.

**RU:** Мяч отскочил от перекладины обратно в поле, полностью линию ворот не пересекал, судья не останавливал игру. Можно продолжать?

**EN:** The ball rebounds from the crossbar into the field without wholly crossing the goal line, and the referee has not stopped play. May play continue?

**Эталон RU:** Да. Сам по себе отскок от перекладины при сохранении мяча на поле не выводит его из игры.

**Reference EN:** Yes. A crossbar rebound that stays on the field does not itself put the ball out of play.

**Обязательные пункты RU:**

- Да.
- Сам по себе отскок от перекладины при сохранении мяча на поле не выводит его из игры.

**Required points EN:**

- Yes.
- A crossbar rebound that stays on the field does not itself put the ball out of play.

**Недопустимо:** После любого попадания в перекладину назначается удар от ворот.

**Must not claim:** Every crossbar rebound requires a goal kick.

**Источники:**

- required_evidence: `ball_in`, раздел 9.2; EN: 101 (101); RU: 103 (101).

## FR040 — offside_position

Тип: `answerable`. Split: `dev`.

**RU:** В момент паса нападающий на половине соперника находится ровно на одной линии с предпоследним соперником. Находится ли он в положении «вне игры»?

**EN:** At the moment of a pass an attacker in the opponents’ half is exactly level with the second-last opponent. Is that an offside position?

**Эталон RU:** Нет. Одна линия с предпоследним соперником не является положением «вне игры».

**Reference EN:** No. Being level with the second-last opponent is not an offside position.

**Обязательные пункты RU:**

- Нет.
- Одна линия с предпоследним соперником не является положением «вне игры».

**Required points EN:**

- No.
- Being level with the second-last opponent is not an offside position.

**Недопустимо:** Нападающий обязан находиться строго позади предпоследнего соперника.

**Must not claim:** The attacker must be strictly behind the second-last opponent.

**Источники:**

- required_evidence: `offside_level`, раздел 11.1; EN: 109 (109); RU: 111 (109).

## FR041 — offside_save

Тип: `answerable`. Split: `dev`.

**RU:** В момент удара партнёра нападающий был в положении «вне игры». Вратарь соперника спас ворота, отбив удар, после чего нападающий сыграл в отскочивший мяч. Каково решение?

**EN:** An attacker was in an offside position when a team-mate shot. The opposing goalkeeper deliberately saved the shot, and the attacker then played the rebound. What is the decision?

**Эталон RU:** Нарушение «вне игры». Спасение ворот не отменяет исходное положение; за игру в отскок назначается свободный удар.

**Reference EN:** An offside offence. A deliberate save does not reset that position; playing the rebound results in an indirect free kick.

**Обязательные пункты RU:**

- Нарушение «вне игры».
- Спасение ворот не отменяет исходное положение; за игру в отскок назначается свободный удар.

**Required points EN:**

- An offside offence.
- A deliberate save does not reset that position; playing the rebound results in an indirect free kick.

**Недопустимо:** Любое намеренное касание вратаря автоматически отменяет «вне игры».

**Must not claim:** Any deliberate goalkeeper touch automatically resets offside.

**Источники:**

- required_evidence: `offside_save`, раздел 11.2; EN: 110 (110); RU: 112 (110).
- required_evidence: `offside_sanction`, раздел 11.4; EN: 111 (111); RU: 114 (112).

## FR042 — accidental_hand_goal

Тип: `answerable`. Split: `dev`.

**RU:** Нападающий случайно коснулся мяча своей рукой и сразу же сам забил ногой в ворота соперника. Можно ли засчитать гол только потому, что касание было случайным?

**EN:** An attacker accidentally touches the ball with their own arm and immediately scores with the foot. May the goal count simply because the contact was accidental?

**Эталон RU:** Нет. Гол сразу после касания собственной руки является нарушением даже при случайном касании.

**Reference EN:** No. Scoring immediately after the scorer’s own arm contact is an offence even if accidental.

**Обязательные пункты RU:**

- Нет.
- Гол сразу после касания собственной руки является нарушением даже при случайном касании.

**Required points EN:**

- No.
- Scoring immediately after the scorer’s own arm contact is an offence even if accidental.

**Недопустимо:** Случайность всегда делает гол после руки допустимым.

**Must not claim:** Accidental contact always makes a subsequent goal legal.

**Источники:**

- required_evidence: `hand_goal`, раздел 12.1.handball; EN: 116 (116); RU: 118 (116).

## FR043 — dangerous_play

Тип: `conditional_answer`. Split: `test`.

**RU:** Игрок выполнил удар через себя. Других подробностей нет. Такое действие всегда запрещено?

**EN:** A player attempts a bicycle kick. No other details are given. Is that action always prohibited?

**Эталон RU:** Нет, сам приём не запрещён. Он допустим, если не опасен сопернику. Для оценки этого эпизода нужны обстоятельства опасности.

**Reference EN:** No, the technique itself is not prohibited. It is permitted if not dangerous to an opponent. The danger in this particular incident needs to be established.

**Обязательные пункты RU:**

- Нет, сам приём не запрещён.
- Он допустим, если не опасен сопернику.
- Для оценки этого эпизода нужны обстоятельства опасности.

**Required points EN:**

- No, the technique itself is not prohibited.
- It is permitted if not dangerous to an opponent.
- The danger in this particular incident needs to be established.

**Недопустимо:** Любой удар через себя автоматически требует карточки.

**Must not claim:** Every bicycle kick automatically requires a card.

**Источники:**

- required_evidence: `bicycle`, раздел 12.2; EN: 118 (118); RU: 121 (119).

## FR044 — holding_penalty

Тип: `answerable`. Split: `dev`.

**RU:** При мяче в игре защитник начал держать нападающего за пределами своей штрафной и продолжил держать уже внутри. Где назначается возобновление?

**EN:** With the ball in play, a defender starts holding an attacker outside their own penalty area and continues holding inside it. What restart is awarded?

**Эталон RU:** Пенальти. Задержка продолжалась внутри штрафной, хотя началась снаружи.

**Reference EN:** A penalty kick. The holding continued inside the penalty area even though it began outside.

**Обязательные пункты RU:**

- Пенальти.
- Задержка продолжалась внутри штрафной, хотя началась снаружи.

**Required points EN:**

- A penalty kick.
- The holding continued inside the penalty area even though it began outside.

**Недопустимо:** Место начала задержки всегда исключает пенальти.

**Must not claim:** The initial location always rules out a penalty.

**Источники:**

- required_evidence: `holding_continues`, раздел 12.4; EN: 121 (121); RU: 123 (121).

## FR045 — goal_celebration

Тип: `answerable`. Split: `dev`.

**RU:** Игрок снял футболку, празднуя гол. Потом гол отменили. Исчезает ли основание для жёлтой карточки за футболку?

**EN:** A player removes their shirt celebrating a goal, which is subsequently disallowed. Does that remove the reason for a yellow card for removing the shirt?

**Эталон RU:** Нет. Предупреждение за снятую футболку выносится и при отменённом голе.

**Reference EN:** No. Removing the shirt requires a caution even if the goal is disallowed.

**Обязательные пункты RU:**

- Нет.
- Предупреждение за снятую футболку выносится и при отменённом голе.

**Required points EN:**

- No.
- Removing the shirt requires a caution even if the goal is disallowed.

**Недопустимо:** Отмена гола автоматически отменяет предупреждение за футболку.

**Must not claim:** Disallowing the goal automatically cancels the shirt-removal caution.

**Источники:**

- required_evidence: `shirt_celebration`, раздел 12.4; EN: 123 (123); RU: 125 (123), 126 (124).

## FR046 — restart_direct_goal

Тип: `answerable`. Split: `dev`.

**RU:** Правильно выполненный штрафной удар без касаний других игроков попал прямо в собственные ворота бьющего. Какое возобновление?

**EN:** A correctly taken direct free kick enters the kicker’s own goal without another player touching it. What is the restart?

**Эталон RU:** Гол не засчитывается. Угловой в пользу соперника.

**Reference EN:** No goal. A corner kick to the opponents.

**Обязательные пункты RU:**

- Гол не засчитывается.
- Угловой в пользу соперника.

**Required points EN:**

- No goal.
- A corner kick to the opponents.

**Недопустимо:** Засчитывается автогол напрямую со штрафного удара.

**Must not claim:** An own goal counts directly from the free kick.

**Источники:**

- required_evidence: `free_goal`, раздел 13.1; EN: 131 (131); RU: 135 (133).

## FR047 — free_kick_wall

Тип: `answerable`. Split: `test`.

**RU:** Защитники построили стенку из четырёх игроков. Какое минимальное расстояние должны держать от неё атакующие до ввода мяча в игру со штрафного?

**EN:** Four defenders form a wall at a free kick. What minimum distance must attacking players keep from that wall until the ball is in play?

**Эталон RU:** Не менее 1 м. Правило относится к стенке из трёх или более защитников.

**Reference EN:** At least 1 m. The requirement applies to a wall of three or more defending players.

**Обязательные пункты RU:**

- Не менее 1 м.
- Правило относится к стенке из трёх или более защитников.

**Required points EN:**

- At least 1 m.
- The requirement applies to a wall of three or more defending players.

**Недопустимо:** Атакующим обязательно держаться в 9,15 м от стенки.

**Must not claim:** Attackers must stay 9.15 m from the wall.

**Источники:**

- required_evidence: `wall_distance`, раздел 13.2; EN: 132 (132); RU: 136 (134).

## FR048 — quick_free_kick

Тип: `answerable`. Split: `dev`.

**RU:** Команда быстро выполнила штрафной, и соперник в пяти метрах перехватил мяч. Он не мешал выполнять удар и специально его не задерживал. Нужно ли автоматически повторить удар из-за расстояния?

**EN:** A team takes a quick free kick and an opponent five metres away intercepts it without deliberately preventing or delaying the kick. Must it automatically be retaken because of the distance?

**Эталон RU:** Нет. При таком быстром выполнении судья разрешает продолжить игру.

**Reference EN:** No. The referee allows play to continue after that quick free kick.

**Обязательные пункты RU:**

- Нет.
- При таком быстром выполнении судья разрешает продолжить игру.

**Required points EN:**

- No.
- The referee allows play to continue after that quick free kick.

**Недопустимо:** Любой перехват ближе 9,15 м всегда требует повтора.

**Must not claim:** Any interception within 9.15 m always requires a retake.

**Источники:**

- required_evidence: `quick_free`, раздел 13.3; EN: 133 (133); RU: 137 (135).

## FR049 — penalty_direction

Тип: `answerable`. Split: `test`.

**RU:** После сигнала судьи игрок выполнил пенальти назад. Других нарушений нет. Каково возобновление?

**EN:** After the referee’s signal the kicker takes a penalty kick backwards. There are no other offences. What is the restart?

**Эталон RU:** Свободный удар сопернику. Пенальти должен направляться вперёд.

**Reference EN:** An indirect free kick to the opponents. A penalty kick must be directed forwards.

**Обязательные пункты RU:**

- Свободный удар сопернику.
- Пенальти должен направляться вперёд.

**Required points EN:**

- An indirect free kick to the opponents.
- A penalty kick must be directed forwards.

**Недопустимо:** Пенальти просто повторяется из-за направления назад.

**Must not claim:** The penalty is simply retaken for being directed backwards.

**Источники:**

- required_evidence: `penalty_backwards`, раздел 14.2; EN: 137 (137); RU: 141 (139).

## FR050 — penalty_accidental_double

Тип: `answerable`. Split: `dev`.

**RU:** При пенальти в ходе матча бьющий поскользнулся: сразу после удара мяч случайно коснулся его опорной ноги и затем попал в ворота. Других нарушений нет. Решение по редакции 2026/27?

**EN:** During a penalty kick in the match, the kicker slips: immediately after the kick the ball accidentally touches the non-kicking leg and then enters the goal. No other offence occurs. What is the 2026/27 decision?

**Эталон RU:** Пенальти повторяется. Речь о случайном немедленном втором касании с голом, а не об умышленной повторной игре.

**Reference EN:** Retake the penalty. This is an accidental immediate second contact followed by a goal, not deliberate second play.

**Обязательные пункты RU:**

- Пенальти повторяется.
- Речь о случайном немедленном втором касании с голом, а не об умышленной повторной игре.

**Required points EN:**

- Retake the penalty.
- This is an accidental immediate second contact followed by a goal, not deliberate second play.

**Недопустимо:** За любое второе касание всегда свободный удар без исключения.

**Must not claim:** Every second contact always results in an indirect free kick without exception.

**Источники:**

- required_evidence: `penalty_accidental`, раздел 14.2; EN: 136 (136); RU: 140 (138).

## FR051 — penalty_deliberate_double

Тип: `answerable`. Split: `dev`.

**RU:** Пенальти в ходе матча попал в стойку и отскочил к бьющему. Никто другой мяча не касался. Бьющий намеренно добил ногой. Какое решение?

**EN:** A penalty during the match rebounds from a goalpost to the kicker without anyone else touching it. The kicker deliberately plays it again with the foot. What is the decision?

**Эталон RU:** Свободный удар сопернику. Касание стойки не заменяет касание другого игрока.

**Reference EN:** An indirect free kick to the opponents. A goalpost contact is not another player’s touch.

**Обязательные пункты RU:**

- Свободный удар сопернику.
- Касание стойки не заменяет касание другого игрока.

**Required points EN:**

- An indirect free kick to the opponents.
- A goalpost contact is not another player’s touch.

**Недопустимо:** Отскок от стойки разрешает бьющему сразу играть снова.

**Must not claim:** A goalpost rebound allows the kicker to play again immediately.

**Источники:**

- required_evidence: `penalty_second`, раздел 14.2; EN: 138 (138); RU: 142 (140).

## FR052 — throw_procedure

Тип: `answerable`. Split: `dev`.

**RU:** При вбрасывании часть каждой стопы находится на боковой линии, остальные требования выполнены. Нарушение ли это только из-за постановки ног на линию?

**EN:** At a throw-in part of each foot is on the touchline and all other requirements are met. Is placing the feet on the line itself an offence?

**Эталон RU:** Нет. Часть каждой стопы может находиться на линии или на земле за её пределами.

**Reference EN:** No. Part of each foot may be on the touchline or on the ground outside it.

**Обязательные пункты RU:**

- Нет.
- Часть каждой стопы может находиться на линии или на земле за её пределами.

**Required points EN:**

- No.
- Part of each foot may be on the touchline or on the ground outside it.

**Недопустимо:** Обе стопы обязательно должны быть целиком за линией.

**Must not claim:** Both feet must be entirely outside the line.

**Источники:**

- required_evidence: `throw_feet`, раздел 15.1; EN: 141 (141); RU: 147 (145).

## FR053 — throw_procedure

Тип: `answerable`. Split: `dev`.

**RU:** Вбрасывание было выполнено правильно, но мяч коснулся земли до того, как вошёл в поле. Кто выполняет следующее вбрасывание?

**EN:** A throw-in is otherwise correctly taken but the ball hits the ground before entering the field. Who takes the next throw-in?

**Эталон RU:** Та же команда. Повтор с того же места.

**Reference EN:** The same team. Retake from the same position.

**Обязательные пункты RU:**

- Та же команда.
- Повтор с того же места.

**Required points EN:**

- The same team.
- Retake from the same position.

**Недопустимо:** Любое касание земли перед входом автоматически передаёт мяч сопернику.

**Must not claim:** Ground contact before entry automatically transfers the throw-in to the opponents.

**Источники:**

- required_evidence: `throw_ground`, раздел 15.1; EN: 141 (141); RU: 147 (145).

## FR054 — goal_kick_procedure

Тип: `answerable`. Split: `test`.

**RU:** При правильно выполненном ударе от ворот мяч ударили ногой и он явно двинулся, но ещё внутри штрафной. Он уже в игре?

**EN:** At a correctly taken goal kick the ball is kicked and clearly moves but is still inside the penalty area. Is it already in play?

**Эталон RU:** Да. Выхода из штрафной ждать не нужно.

**Reference EN:** Yes. It need not leave the penalty area first.

**Обязательные пункты RU:**

- Да.
- Выхода из штрафной ждать не нужно.

**Required points EN:**

- Yes.
- It need not leave the penalty area first.

**Недопустимо:** Мяч входит в игру только после выхода из штрафной.

**Must not claim:** The ball is in play only after leaving the penalty area.

**Источники:**

- required_evidence: `goal_kick_in`, раздел 16.1; EN: 145 (145); RU: 151 (149).

## FR055 — restart_direct_goal

Тип: `answerable`. Split: `dev`.

**RU:** При правильном ударе от ворот мяч без других касаний попал в собственные ворота выполняющей команды. Какое решение?

**EN:** A correctly taken goal kick enters the taking team’s own goal without another touch. What is the decision?

**Эталон RU:** Гол не засчитывается. Угловой в пользу соперника.

**Reference EN:** No goal. A corner kick to the opponents.

**Обязательные пункты RU:**

- Гол не засчитывается.
- Угловой в пользу соперника.

**Required points EN:**

- No goal.
- A corner kick to the opponents.

**Недопустимо:** Удар от ворот нужно повторить только из-за автогола.

**Must not claim:** The goal kick must be retaken solely because it entered the team’s own goal.

**Источники:**

- required_evidence: `goal_kick_goal`, раздел 16.intro; EN: 145 (145); RU: 151 (149).

## FR056 — corner_procedure

Тип: `answerable`. Split: `dev`.

**RU:** При правильном угловом мяч ударили ногой и он явно двинулся, оставаясь в угловой площади. Он уже в игре?

**EN:** At a correctly taken corner the ball is kicked and clearly moves but remains in the corner area. Is it in play?

**Эталон RU:** Да. Покидать угловую площадь для ввода в игру не требуется.

**Reference EN:** Yes. It need not leave the corner area to be in play.

**Обязательные пункты RU:**

- Да.
- Покидать угловую площадь для ввода в игру не требуется.

**Required points EN:**

- Yes.
- It need not leave the corner area to be in play.

**Недопустимо:** Мяч обязательно должен полностью покинуть угловую площадь.

**Must not claim:** The ball must entirely leave the corner area first.

**Источники:**

- required_evidence: `corner_in`, раздел 17.1; EN: 149 (149); RU: 155 (153).

## FR057 — corner_procedure

Тип: `answerable`. Split: `dev`.

**RU:** Мешает угловой флаг. Можно ли убрать его только на время выполнения углового и вернуть после удара?

**EN:** The corner flag is in the way. May it be removed just for taking a corner and replaced afterwards?

**Эталон RU:** Нет. Угловой флагшток перемещать нельзя.

**Reference EN:** No. The corner flagpost must not be moved.

**Обязательные пункты RU:**

- Нет.
- Угловой флагшток перемещать нельзя.

**Required points EN:**

- No.
- The corner flagpost must not be moved.

**Недопустимо:** Согласие соперника разрешает временно убрать флаг.

**Must not claim:** The opponents agreeing allows temporary removal of the flag.

**Источники:**

- required_evidence: `corner_flag`, раздел 17.1; EN: 149 (149); RU: 155 (153).

## FR058 — offside_missing_facts

Тип: `insufficient_information`. Split: `test`.

**RU:** Форвард стоял ближе к воротам, чем защитник, когда получил пас. Этого достаточно, чтобы точно объявить офсайд? Других данных нет.

**EN:** A forward was closer to goal than a defender when receiving a pass. Is that enough to definitely call offside? No other information is available.

**Эталон RU:** Недостаточно данных. Нужна позиция в момент игры партнёра: относительно мяча, предпоследнего соперника и половины поля. Нужно установить участие в активной игре.

**Reference EN:** The information is insufficient. Position when the team-mate plays the ball is needed relative to the ball, second-last opponent and half of the field. Active involvement must be established.

**Обязательные пункты RU:**

- Недостаточно данных.
- Нужна позиция в момент игры партнёра: относительно мяча, предпоследнего соперника и половины поля.
- Нужно установить участие в активной игре.

**Required points EN:**

- The information is insufficient.
- Position when the team-mate plays the ball is needed relative to the ball, second-last opponent and half of the field.
- Active involvement must be established.

**Недопустимо:** Достаточно положения относительно одного защитника при приёме.

**Must not claim:** Position relative to one defender at reception is sufficient.

**Источники:**

- required_evidence: `offside_position`, раздел 11.1; EN: 109 (109); RU: 111 (109).
- required_evidence: `offside_active`, раздел 11.2; EN: 109 (109), 110 (110); RU: 111 (109), 112 (110).

## FR059 — competition_points

Тип: `out_of_scope`. Split: `test`.

**RU:** Сколько очков начислят за победу в моём любительском турнире? Его регламент не предоставлен.

**EN:** How many standings points does a win earn in my amateur tournament? Its regulations have not been provided.

**Эталон RU:** По этому корпусу нельзя определить число очков. Нужен регламент конкретного турнира.

**Reference EN:** The number of points cannot be determined from this corpus. The specific tournament regulations are required.

**Обязательные пункты RU:**

- По этому корпусу нельзя определить число очков.
- Нужен регламент конкретного турнира.

**Required points EN:**

- The number of points cannot be determined from this corpus.
- The specific tournament regulations are required.

**Недопустимо:** Во всех турнирах IFAB гарантирует три очка за победу.

**Must not claim:** IFAB guarantees three points for a win in every competition.

**Источники:**

- Доказательства конкретного ответа в корпусе отсутствуют; не включать вопрос в обычный Recall@K.

## FR060 — live_match_result

Тип: `out_of_scope`. Split: `dev`.

**RU:** Какой счёт был во вчерашнем матче моей команды? В системе есть только тексты правил, название команды и матч не указаны.

**EN:** What was the score in my team’s match yesterday? The system has only Laws texts and neither the team nor match is identified.

**Эталон RU:** Из правил нельзя узнать результат матча. Нужны идентификация матча и источник результатов.

**Reference EN:** Match results cannot be inferred from the Laws. The match must be identified and a results source is needed.

**Обязательные пункты RU:**

- Из правил нельзя узнать результат матча.
- Нужны идентификация матча и источник результатов.

**Required points EN:**

- Match results cannot be inferred from the Laws.
- The match must be identified and a results source is needed.

**Недопустимо:** Придуманный конкретный счёт.

**Must not claim:** An invented specific score.

**Источники:**

- Доказательства конкретного ответа в корпусе отсутствуют; не включать вопрос в обычный Recall@K.

## FR061 — free_kick_wall

Тип: `answerable`. Split: `test`.

**RU:** В стенке только два защитника. Нападающий стоит в полуметре сбоку и никому не мешает. Обязан ли он отойти на метр именно по правилу о стенке?

**EN:** Only two defenders form a wall. An attacker stands half a metre to the side without interfering with anyone. Must the attacker move one metre away specifically under the wall-distance rule?

**Эталон RU:** Правило о метре относится к стенке из трёх и более защитников. При двух защитниках именно это требование не применяется; остальные правила сохраняются.

**Reference EN:** The one-metre rule applies to a wall of three or more defenders. With two defenders that particular requirement does not apply; other Laws still apply.

**Обязательные пункты RU:**

- Правило о метре относится к стенке из трёх и более защитников.
- При двух защитниках именно это требование не применяется; остальные правила сохраняются.

**Required points EN:**

- The one-metre rule applies to a wall of three or more defenders.
- With two defenders that particular requirement does not apply; other Laws still apply.

**Недопустимо:** У любой стенки независимо от числа игроков обязателен метр.

**Must not claim:** A one-metre gap is required for every wall regardless of its size.

**Источники:**

- required_evidence: `wall_distance`, раздел 13.2; EN: 132 (132); RU: 136 (134).

## FR062 — penalty_boundary

Тип: `insufficient_information`. Split: `test`.

**RU:** Защитник сбил нашего прямо возле линии штрафной. Почему не пенальти? Где именно был контакт, я не видел; мяч был в игре.

**EN:** A defender brought our player down right near the penalty-area line. Why was it not a penalty? I did not see the exact contact location; the ball was in play.

**Эталон RU:** Слова «возле линии» недостаточно. Нужно установить место и характер нарушения. Если наказуемое штрафным ударом нарушение было на линии собственной штрафной или внутри, назначается пенальти; снаружи — штрафной.

**Reference EN:** “Near the line” is insufficient. The location and nature of the offence must be established. A direct-free-kick offence on the boundary of the defender’s penalty area or inside it results in a penalty; outside it results in a free kick.

**Обязательные пункты RU:**

- Слова «возле линии» недостаточно.
- Нужно установить место и характер нарушения.
- Если наказуемое штрафным ударом нарушение было на линии собственной штрафной или внутри, назначается пенальти; снаружи — штрафной.

**Required points EN:**

- “Near the line” is insufficient.
- The location and nature of the offence must be established.
- A direct-free-kick offence on the boundary of the defender’s penalty area or inside it results in a penalty; outside it results in a free kick.

**Недопустимо:** Слово «возле» доказывает, что нарушение было внутри.

**Must not claim:** The word “near” proves that the offence was inside.

**Источники:**

- required_evidence: `field_lines`, раздел 1.2; EN: 45 (45); RU: 45 (43).
- required_evidence: `penalty_award`, раздел 14.intro; EN: 135 (135); RU: 139 (137).

## FR063 — tackle_assessment

Тип: `conditional_answer`. Split: `dev`.

**RU:** Он сначала выбил мяч, а потом снёс соперника. Раз сыграл в мяч первым, фола точно нет?

**EN:** He got the ball first and then knocked the opponent over. Getting the ball first means it definitely cannot be a foul, right?

**Эталон RU:** Первое касание мяча само по себе не исключает нарушение. Нужно оценить способ единоборства, неосторожность, безрассудность и чрезмерную силу. По одному описанию нельзя уверенно выбрать решение и карточку.

**Reference EN:** Touching the ball first does not itself rule out an offence. The challenge must be assessed for carelessness, recklessness and excessive force. This description alone does not support a definite decision or card.

**Обязательные пункты RU:**

- Первое касание мяча само по себе не исключает нарушение.
- Нужно оценить способ единоборства, неосторожность, безрассудность и чрезмерную силу.
- По одному описанию нельзя уверенно выбрать решение и карточку.

**Required points EN:**

- Touching the ball first does not itself rule out an offence.
- The challenge must be assessed for carelessness, recklessness and excessive force.
- This description alone does not support a definite decision or card.

**Недопустимо:** Касание мяча первым автоматически делает любое последующее действие законным.

**Must not claim:** Touching the ball first automatically makes every subsequent action legal.

**Источники:**

- required_evidence: `reckless`, раздел 12.1; EN: 115 (115); RU: 117 (115).

## FR064 — offside_position

Тип: `answerable`. Split: `dev`.

**RU:** В момент паса голова, туловище и ноги нападающего на одной линии с предпоследним соперником, но вытянутая кисть впереди. Офсайд из-за кисти?

**EN:** When the pass is played, the attacker’s head, body and feet are level with the second-last opponent, but an outstretched hand is beyond them. Is the hand enough for offside?

**Эталон RU:** Нет. Руки не учитываются при определении положения «вне игры»; указанное положение остальных частей тела не образует офсайд.

**Reference EN:** No. Hands and arms are excluded from offside-position assessment; the stated position of the other body parts is not offside.

**Обязательные пункты RU:**

- Нет.
- Руки не учитываются при определении положения «вне игры»; указанное положение остальных частей тела не образует офсайд.

**Required points EN:**

- No.
- Hands and arms are excluded from offside-position assessment; the stated position of the other body parts is not offside.

**Недопустимо:** Любая часть руки впереди защитника означает офсайд.

**Must not claim:** Any part of an arm beyond a defender means offside.

**Источники:**

- required_evidence: `offside_hands`, раздел 11.1; EN: 109 (109); RU: 111 (109).
- required_evidence: `offside_level`, раздел 11.1; EN: 109 (109); RU: 111 (109).

## FR065 — handball_uncertainty

Тип: `insufficient_information`. Split: `dev`.

**RU:** Мяч попал ему сюда, между плечом и рукой. Это рука? Изображения нет, точку контакта точнее описать не могу.

**EN:** The ball hit him here, between the shoulder and arm. Is that handball? There is no image and I cannot describe the contact point more precisely.

**Эталон RU:** Нужно уточнить точку контакта. Верхняя граница руки для этого правила проходит по нижнему краю подмышечной впадины. Даже контакт с рукой не всегда является нарушением; нужны обстоятельства.

**Reference EN:** The contact point needs clarification. For this Law the upper arm boundary is in line with the bottom of the armpit. Even arm contact is not always an offence; the circumstances matter.

**Обязательные пункты RU:**

- Нужно уточнить точку контакта.
- Верхняя граница руки для этого правила проходит по нижнему краю подмышечной впадины.
- Даже контакт с рукой не всегда является нарушением; нужны обстоятельства.

**Required points EN:**

- The contact point needs clarification.
- For this Law the upper arm boundary is in line with the bottom of the armpit.
- Even arm contact is not always an offence; the circumstances matter.

**Недопустимо:** Ассистент видел изображение или точно определил точку контакта.

**Must not claim:** The assistant saw an image or determined the exact contact point.

**Источники:**

- required_evidence: `handball`, раздел 12.1.handball; EN: 116 (116); RU: 118 (116).

## FR066 — offside_deliberate_play

Тип: `answerable`. Split: `dev`.

**RU:** Защитник контролировал мяч и намеренно попытался отдать пас, но ошибся и отдал его стоявшему в офсайде сопернику. Это не спасение ворот; до паса нападающий не вмешивался. Офсайд автоматически сохраняется из-за неточного паса?

**EN:** A defender controlled the ball and deliberately attempted a pass but misplayed it to an opponent in an offside position. It was not a save, and the attacker had not interfered before the pass. Does the inaccurate pass automatically preserve offside?

**Эталон RU:** Нет. Неточная или неудачная передача не отменяет умышленную игру контролировавшего мяч защитника. При указанных условиях получение мяча не считается получением преимущества из прежнего положения.

**Reference EN:** No. An inaccurate or unsuccessful pass does not negate deliberate play by a defender in control. Under the stated conditions receiving the ball is not gaining an advantage from the earlier position.

**Обязательные пункты RU:**

- Нет.
- Неточная или неудачная передача не отменяет умышленную игру контролировавшего мяч защитника.
- При указанных условиях получение мяча не считается получением преимущества из прежнего положения.

**Required points EN:**

- No.
- An inaccurate or unsuccessful pass does not negate deliberate play by a defender in control.
- Under the stated conditions receiving the ball is not gaining an advantage from the earlier position.

**Недопустимо:** Любая ошибка защитника считается только рикошетом.

**Must not claim:** Every defensive mistake is merely a deflection.

**Источники:**

- required_evidence: `deliberate_play`, раздел 11.2; EN: 110 (110); RU: 112 (110).

## FR067 — offside_position

Тип: `answerable`. Split: `dev`.

**RU:** Вратарь выбежал далеко вперёд. Для офсайда всё равно надо сравнивать нападающего с вратарём и последним защитником, а не считать соперников?

**EN:** The goalkeeper has moved a long way forward. For offside do we still compare the attacker with the goalkeeper and last defender instead of counting opponents?

**Эталон RU:** Роль вратаря не задаёт отдельную линию офсайда. Учитываются мяч и предпоследний соперник независимо от его позиции в составе, а также половина поля.

**Reference EN:** The goalkeeper’s role does not define a separate offside line. The ball and second-last opponent, regardless of playing role, and the half of the field are considered.

**Обязательные пункты RU:**

- Роль вратаря не задаёт отдельную линию офсайда.
- Учитываются мяч и предпоследний соперник независимо от его позиции в составе, а также половина поля.

**Required points EN:**

- The goalkeeper’s role does not define a separate offside line.
- The ball and second-last opponent, regardless of playing role, and the half of the field are considered.

**Недопустимо:** Предпоследний соперник всегда обязан быть полевым игроком.

**Must not claim:** The second-last opponent must always be an outfield player.

**Источники:**

- required_evidence: `offside_position`, раздел 11.1; EN: 109 (109); RU: 111 (109).

## FR068 — offside_timing

Тип: `conditional_answer`. Split: `dev`.

**RU:** Пас пошёл назад, значит офсайда точно не бывает? Позиции принимающего в момент паса я не помню.

**EN:** The pass went backwards, so offside is definitely impossible, right? I do not remember the receiver’s position when it was played.

**Эталон RU:** Направление паса само по себе не решает вопрос. Нужна позиция принимающего относительно мяча, предпоследнего соперника и половины поля в момент игры партнёра, затем его участие. Нельзя объявить или исключить нарушение только по направлению передачи.

**Reference EN:** Pass direction alone does not decide it. The receiver’s position relative to the ball, second-last opponent and half of the field when the team-mate plays it, followed by involvement, is needed. Direction alone cannot establish or exclude an offence.

**Обязательные пункты RU:**

- Направление паса само по себе не решает вопрос.
- Нужна позиция принимающего относительно мяча, предпоследнего соперника и половины поля в момент игры партнёра, затем его участие.
- Нельзя объявить или исключить нарушение только по направлению передачи.

**Required points EN:**

- Pass direction alone does not decide it.
- The receiver’s position relative to the ball, second-last opponent and half of the field when the team-mate plays it, followed by involvement, is needed.
- Direction alone cannot establish or exclude an offence.

**Недопустимо:** Любой пас назад автоматически исключает офсайд независимо от положения игроков.

**Must not claim:** Every backwards pass automatically rules out offside regardless of player positions.

**Источники:**

- required_evidence: `offside_position`, раздел 11.1; EN: 109 (109); RU: 111 (109).
- required_evidence: `offside_active`, раздел 11.2; EN: 109 (109), 110 (110); RU: 111 (109), 112 (110).

## FR069 — offside_deliberate_play

Тип: `insufficient_information`. Split: `dev`.

**RU:** Мяч задел защитника и прилетел к нашему, который до этого был в офсайде. Защитник коснулся — значит теперь всё чисто?

**EN:** The ball touched a defender and reached our player, who had been in an offside position. A defender touched it, so it is legal now, right?

**Эталон RU:** Самого касания недостаточно. Нужно отличить умышленную игру с контролем от рикошета или спасения ворот. Нужны обстоятельства касания и участия нападающего; нельзя автоматически отменять офсайд.

**Reference EN:** A touch alone is insufficient. Deliberate play with control must be distinguished from a deflection or save. The defender’s touch and attacker’s involvement need clarification; offside is not automatically reset.

**Обязательные пункты RU:**

- Самого касания недостаточно.
- Нужно отличить умышленную игру с контролем от рикошета или спасения ворот.
- Нужны обстоятельства касания и участия нападающего; нельзя автоматически отменять офсайд.

**Required points EN:**

- A touch alone is insufficient.
- Deliberate play with control must be distinguished from a deflection or save.
- The defender’s touch and attacker’s involvement need clarification; offside is not automatically reset.

**Недопустимо:** Любое касание соперника отменяет предыдущее положение.

**Must not claim:** Any opponent touch resets the previous position.

**Источники:**

- required_evidence: `deliberate_play`, раздел 11.2; EN: 110 (110); RU: 112 (110).
- required_evidence: `offside_save`, раздел 11.2; EN: 110 (110); RU: 112 (110).

## FR070 — sending_off_replacement

Тип: `answerable`. Split: `dev`.

**RU:** Игрок из стартового состава удалён после подачи заявки, но до начального удара. Можно ли поставить вместо него заявленного запасного и уменьшится ли число разрешённых замен?

**EN:** A starting player is sent off after the team list is submitted but before kick-off. May a named substitute replace the player, and is the substitution allowance reduced?

**Эталон RU:** Можно заменить заявленным запасным. Выбывшего из списка запасного нельзя восполнить. Количество разрешённых замен не уменьшается.

**Reference EN:** A named substitute may replace the player. The resulting vacancy among the named substitutes cannot be filled. The substitution allowance is not reduced.

**Обязательные пункты RU:**

- Можно заменить заявленным запасным.
- Выбывшего из списка запасного нельзя восполнить.
- Количество разрешённых замен не уменьшается.

**Required points EN:**

- A named substitute may replace the player.
- The resulting vacancy among the named substitutes cannot be filled.
- The substitution allowance is not reduced.

**Недопустимо:** Любое удаление до начала матча обязательно оставляет команду вдесятером.

**Must not claim:** Every pre-kick-off sending-off necessarily leaves the team with ten players.

**Источники:**

- required_evidence: `red_replacement`, раздел 3.6; EN: 63 (63); RU: 63 (61).

## FR071 — substitution_delay

Тип: `conditional_answer`. Split: `dev`.

**RU:** В сезоне 2026/27 заменяемый не уложился в десять секунд, хотя не было травмы или угрозы безопасности. Запасной может сразу выйти? И жёлтая автоматически?

**EN:** In 2026/27 the replaced player fails to leave within ten seconds without injury or a safety issue. May the substitute enter immediately, and is a yellow card automatic?

**Эталон RU:** Запасной сразу не выходит; игра возобновляется. Он может выйти с разрешения судьи в первую остановку после истечения минуты с возобновления. Предупреждение не автоматически за сам выход за десять секунд, а при чрезмерной задержке сверх них.

**Reference EN:** The substitute cannot enter immediately; play restarts. Entry requires the referee’s permission at the first stoppage after one minute has elapsed from the restart. Exceeding ten seconds alone does not automatically require a caution; excessive further delay does.

**Обязательные пункты RU:**

- Запасной сразу не выходит; игра возобновляется.
- Он может выйти с разрешения судьи в первую остановку после истечения минуты с возобновления.
- Предупреждение не автоматически за сам выход за десять секунд, а при чрезмерной задержке сверх них.

**Required points EN:**

- The substitute cannot enter immediately; play restarts.
- Entry requires the referee’s permission at the first stoppage after one minute has elapsed from the restart.
- Exceeding ten seconds alone does not automatically require a caution; excessive further delay does.

**Недопустимо:** Запасной может выйти сразу либо любой выход за десять секунд автоматически требует жёлтой.

**Must not claim:** The substitute may enter immediately, or any ten-second overrun automatically requires a yellow.

**Источники:**

- required_evidence: `sub_delay`, раздел 3.5; EN: 63 (63); RU: 63 (61).

## FR072 — bleeding_return

Тип: `answerable`. Split: `dev`.

**RU:** Мне остановили кровь за боковой, на форме крови нет. Можно самому вернуться в игру, не дожидаясь сигнала?

**EN:** My bleeding has been stopped off the field and there is no blood on my kit. May I return without waiting for a signal?

**Эталон RU:** Нет. Нужен сигнал судьи; он должен убедиться, что кровотечение остановлено и на экипировке нет крови.

**Reference EN:** No. The referee’s signal is required; the referee must be satisfied that bleeding has stopped and there is no blood on the equipment.

**Обязательные пункты RU:**

- Нет.
- Нужен сигнал судьи; он должен убедиться, что кровотечение остановлено и на экипировке нет крови.

**Required points EN:**

- No.
- The referee’s signal is required; the referee must be satisfied that bleeding has stopped and there is no blood on the equipment.

**Недопустимо:** Решения самого игрока или врача достаточно для возвращения без сигнала.

**Must not claim:** The player or doctor alone can authorise re-entry without a referee signal.

**Источники:**

- required_evidence: `blood_return`, раздел 5.3; EN: 76 (76); RU: 78 (76).

## FR073 — equipment_safety

Тип: `conditional_answer`. Split: `dev`.

**RU:** Я слышал, любые аксессуары запрещены даже под защитной повязкой. Это всё ещё так в Правилах 2026/27?

**EN:** I heard every accessory is prohibited even under a protective covering. Is that still the rule in 2026/27?

**Эталон RU:** Нет, общего запрета на любые аксессуары в этой редакции нет. Они допустимы, если безопасны и надёжно закрыты. Опасный предмет нужно снять; повязка не делает его допустимым.

**Reference EN:** No, this edition does not impose a blanket ban on all accessories. They are permitted if non-dangerous and safely and securely covered. Dangerous items must be removed; covering does not make them permissible.

**Обязательные пункты RU:**

- Нет, общего запрета на любые аксессуары в этой редакции нет.
- Они допустимы, если безопасны и надёжно закрыты.
- Опасный предмет нужно снять; повязка не делает его допустимым.

**Required points EN:**

- No, this edition does not impose a blanket ban on all accessories.
- They are permitted if non-dangerous and safely and securely covered.
- Dangerous items must be removed; covering does not make them permissible.

**Недопустимо:** Можно разрешить любой опасный аксессуар, просто закрыв его.

**Must not claim:** Any dangerous accessory may be allowed simply by covering it.

**Источники:**

- required_evidence: `dangerous_equipment`, раздел 4.1; EN: 67 (67); RU: 67 (65).

## FR074 — drop_recipient

Тип: `answerable`. Split: `test`.

**RU:** Судья остановил игру вне штрафной, нужен спорный мяч. Последней коснулась команда А, но судья ясно определил, что владение получила бы Б. Кому он бросит мяч по редакции 2026/27?

**EN:** Play stops outside the penalty area and requires a dropped ball. Team A touched it last, but the referee can clearly determine that Team B would have gained possession. Who receives the ball under 2026/27?

**Эталон RU:** Одному игроку команды Б. Вне штрафной сначала учитывается определимое сохранение или получение владения; последнее касание используется, если это определить нельзя.

**Reference EN:** One player of Team B. Outside the penalty area, determinable retained or gained possession takes priority; last touch is used when that cannot be determined.

**Обязательные пункты RU:**

- Одному игроку команды Б.
- Вне штрафной сначала учитывается определимое сохранение или получение владения; последнее касание используется, если это определить нельзя.

**Required points EN:**

- One player of Team B.
- Outside the penalty area, determinable retained or gained possession takes priority; last touch is used when that cannot be determined.

**Недопустимо:** Спорный мяч всегда отдаётся только последней коснувшейся команде.

**Must not claim:** A dropped ball always goes solely to the last team to touch it.

**Источники:**

- required_evidence: `drop_recipient`, раздел 8.2; EN: 98 (98); RU: 100 (98).

## FR075 — restart_direct_goal

Тип: `answerable`. Split: `dev`.

**RU:** Получив спорный мяч после касания земли, игрок сразу забил в ворота соперника. Мяча не коснулся больше никто. Гол?

**EN:** After a dropped ball touches the ground, its recipient immediately scores into the opponents’ goal. No other player touches it. Is it a goal?

**Эталон RU:** Гол не засчитывается. Без касания как минимум двух игроков назначается удар от ворот при попадании в ворота соперника.

**Reference EN:** No goal. Without touches by at least two players, entry into the opponents’ goal results in a goal kick.

**Обязательные пункты RU:**

- Гол не засчитывается.
- Без касания как минимум двух игроков назначается удар от ворот при попадании в ворота соперника.

**Required points EN:**

- No goal.
- Without touches by at least two players, entry into the opponents’ goal results in a goal kick.

**Недопустимо:** Двух касаний одного и того же игрока достаточно вместо двух игроков.

**Must not claim:** Two touches by the same player suffice instead of touches by two players.

**Источники:**

- required_evidence: `drop_goal`, раздел 8.2; EN: 98 (98); RU: 100 (98).

## FR076 — referee_ball_contact

Тип: `answerable`. Split: `test`.

**RU:** Мяч слегка задел судью и остался у той же команды на поле. Перспективная атака не началась, в ворота он не попал. Само касание требует свистка?

**EN:** The ball lightly touches the referee and stays on the field with the same team. No promising attack begins and it does not enter a goal. Does contact itself require a whistle?

**Эталон RU:** Нет. При отсутствии перечисленных последствий само касание судьи не выводит мяч из игры.

**Reference EN:** No. Without the listed consequences, referee contact alone does not put the ball out of play.

**Обязательные пункты RU:**

- Нет.
- При отсутствии перечисленных последствий само касание судьи не выводит мяч из игры.

**Required points EN:**

- No.
- Without the listed consequences, referee contact alone does not put the ball out of play.

**Недопустимо:** Любое касание судьи обязательно означает спорный мяч.

**Must not claim:** Every referee contact necessarily requires a dropped ball.

**Источники:**

- required_evidence: `ref_contact`, раздел 9.1; EN: 101 (101); RU: 103 (101).
- required_evidence: `ball_in`, раздел 9.2; EN: 101 (101); RU: 103 (101).

## FR077 — throw_procedure

Тип: `answerable`. Split: `dev`.

**RU:** При ауте соперник обязан отойти на два метра от меня или от какой точки? Сколько точно по правилам?

**EN:** At a throw-in must the opponent stay two metres from me or from some other point? What exactly is the required distance?

**Эталон RU:** Не менее 2 м от точки на боковой линии, откуда выполняется вбрасывание.

**Reference EN:** At least 2 m from the point on the touchline where the throw-in is taken.

**Обязательные пункты RU:**

- Не менее 2 м от точки на боковой линии, откуда выполняется вбрасывание.

**Required points EN:**

- At least 2 m from the point on the touchline where the throw-in is taken.

**Недопустимо:** Расстояние всегда измеряется от фактического положения туловища вбрасывающего.

**Must not claim:** Distance is always measured from the thrower’s actual torso position.

**Источники:**

- required_evidence: `throw_distance`, раздел 15.1; EN: 141 (141); RU: 147 (145).

## FR078 — throw_procedure

Тип: `answerable`. Split: `dev`.

**RU:** Правильно вбросил мяч в поле и сам побежал за ним. Сыграл ногой раньше, чем кто-либо ещё его коснулся. Что назначат?

**EN:** I correctly throw the ball into the field, chase it and play it with my foot before anyone else touches it. What is awarded?

**Эталон RU:** Свободный удар сопернику. После ввода в игру вбрасывающий не может повторно играть до касания другого игрока.

**Reference EN:** An indirect free kick to the opponents. After the ball is in play the thrower cannot play it again before another player touches it.

**Обязательные пункты RU:**

- Свободный удар сопернику.
- После ввода в игру вбрасывающий не может повторно играть до касания другого игрока.

**Required points EN:**

- An indirect free kick to the opponents.
- After the ball is in play the thrower cannot play it again before another player touches it.

**Недопустимо:** Достаточно, что мяч коснулся земли: можно сразу сыграть самому.

**Must not claim:** The ball touching the ground is enough to permit the thrower to play again.

**Источники:**

- required_evidence: `throw_second`, раздел 15.2; EN: 142 (142); RU: 148 (146).

## FR079 — corner_procedure

Тип: `answerable`. Split: `dev`.

**RU:** На угловом защитник стоит в девяти метрах от дуги угловой площади. Он уже на разрешённом расстоянии?

**EN:** At a corner a defender stands nine metres from the corner arc. Is that already the required distance?

**Эталон RU:** Нет. Нужно не менее 9,15 м от дуги угловой площади, пока мяч не войдёт в игру.

**Reference EN:** No. Opponents must remain at least 9.15 m from the corner arc until the ball is in play.

**Обязательные пункты RU:**

- Нет.
- Нужно не менее 9,15 м от дуги угловой площади, пока мяч не войдёт в игру.

**Required points EN:**

- No.
- Opponents must remain at least 9.15 m from the corner arc until the ball is in play.

**Недопустимо:** Девять метров достаточно либо расстояние всегда считают от флагштока.

**Must not claim:** Nine metres is sufficient, or distance is always measured from the flagpost.

**Источники:**

- required_evidence: `corner_distance`, раздел 17.1; EN: 149 (149); RU: 155 (153).

## FR080 — restart_direct_goal

Тип: `answerable`. Split: `dev`.

**RU:** Закрутил мяч с углового прямо в чужие ворота, никто не коснулся, нарушений не было. Такое можно засчитать?

**EN:** I curl a corner directly into the opponents’ goal without another touch or any offence. Can that count?

**Эталон RU:** Да. Гол непосредственно с углового разрешён в ворота соперника.

**Reference EN:** Yes. A goal may be scored directly from a corner into the opponents’ goal.

**Обязательные пункты RU:**

- Да.
- Гол непосредственно с углового разрешён в ворота соперника.

**Required points EN:**

- Yes.
- A goal may be scored directly from a corner into the opponents’ goal.

**Недопустимо:** Для любого гола с углового обязательно второе касание.

**Must not claim:** Every goal from a corner requires another touch.

**Источники:**

- required_evidence: `corner_goal`, раздел 17.intro; EN: 149 (149); RU: 155 (153).

## FR081 — goal_kick_procedure

Тип: `answerable`. Split: `test`.

**RU:** Удар от ворот обязательно должен выполнять вратарь или защитник тоже может?

**EN:** Must the goalkeeper take a goal kick, or may a defender take it too?

**Эталон RU:** Может любой игрок обороняющейся команды. Остальные требования процедуры удара сохраняются.

**Reference EN:** Any player of the defending team may take it. The other goal-kick procedure requirements still apply.

**Обязательные пункты RU:**

- Может любой игрок обороняющейся команды.
- Остальные требования процедуры удара сохраняются.

**Required points EN:**

- Any player of the defending team may take it.
- The other goal-kick procedure requirements still apply.

**Недопустимо:** Удар от ворот разрешён только вратарю.

**Must not claim:** Only the goalkeeper may take a goal kick.

**Источники:**

- required_evidence: `goal_kick_in`, раздел 16.1; EN: 145 (145); RU: 151 (149).

## FR082 — referee_ball_contact

Тип: `answerable`. Split: `test`.

**RU:** Удар задел судью и прямо от него залетел в ворота, без других касаний. Можно засчитать как обычный рикошет?

**EN:** A shot hits the referee and goes directly into the goal without another touch. Can it count like an ordinary deflection?

**Эталон RU:** Нет. При таком попадании непосредственно в ворота после судьи игру возобновляют спорным мячом.

**Reference EN:** No. Direct entry into a goal after contact with a match official leads to a dropped ball.

**Обязательные пункты RU:**

- Нет.
- При таком попадании непосредственно в ворота после судьи игру возобновляют спорным мячом.

**Required points EN:**

- No.
- Direct entry into a goal after contact with a match official leads to a dropped ball.

**Недопустимо:** Судья в этой ситуации приравнивается к стойке и гол всегда засчитывают.

**Must not claim:** The referee is equivalent to a goalpost here and the goal always counts.

**Источники:**

- required_evidence: `ref_contact`, раздел 9.1; EN: 101 (101); RU: 103 (101).

## FR083 — penalty_feint

Тип: `conditional_answer`. Split: `test`.

**RU:** Он сделал паузу на пенальти. Разве за любую паузу сразу жёлтая и свободный? Не знаю, пауза была во время разбега или перед самим ударом.

**EN:** He paused while taking a penalty. Does every pause mean a yellow card and indirect free kick? I do not know whether it was during the run-up or at the final kick.

**Эталон RU:** Не всякая пауза автоматически нарушение. Обманные движения в разбеге разрешены; запрещено обманное движение при ударе после завершения разбега. В последнем случае — предупреждение и свободный удар независимо от гола; нужно уточнить действие и его момент.

**Reference EN:** Not every pause is automatically an offence. Feinting during the run-up is permitted; feinting to kick after completing the run-up is prohibited. The latter requires a caution and indirect free kick regardless of a goal; the action and timing need clarification.

**Обязательные пункты RU:**

- Не всякая пауза автоматически нарушение.
- Обманные движения в разбеге разрешены; запрещено обманное движение при ударе после завершения разбега.
- В последнем случае — предупреждение и свободный удар независимо от гола; нужно уточнить действие и его момент.

**Required points EN:**

- Not every pause is automatically an offence.
- Feinting during the run-up is permitted; feinting to kick after completing the run-up is prohibited.
- The latter requires a caution and indirect free kick regardless of a goal; the action and timing need clarification.

**Недопустимо:** Любая остановка в разбеге обязательно наказывается.

**Must not claim:** Every pause in the run-up necessarily requires punishment.

**Источники:**

- required_evidence: `penalty_feint`, раздел 14.2; EN: 137 (137); RU: 141 (139).

## FR084 — keeper_penalty_position

Тип: `answerable`. Split: `dev`.

**RU:** При ударе с пенальти одна стопа вратаря в воздухе прямо над линией ворот, другая впереди. Нарушение только потому, что ни одна стопа не касается газона на линии?

**EN:** When a penalty is kicked one goalkeeper foot is in the air directly in line with the goal line and the other is in front. Is it an offence solely because neither foot touches the ground on the line?

**Эталон RU:** Нет. Часть хотя бы одной стопы может касаться линии, находиться над ней или позади неё в момент удара.

**Reference EN:** No. At least part of one foot may be touching, in line with or behind the goal line at the moment of the kick.

**Обязательные пункты RU:**

- Нет.
- Часть хотя бы одной стопы может касаться линии, находиться над ней или позади неё в момент удара.

**Required points EN:**

- No.
- At least part of one foot may be touching, in line with or behind the goal line at the moment of the kick.

**Недопустимо:** Обе стопы обязательно должны физически касаться линии.

**Must not claim:** Both feet must physically touch the line.

**Источники:**

- required_evidence: `keeper_penalty_line`, раздел 14.1; EN: 135 (135); RU: 140 (138).

## FR085 — keeper_penalty_position

Тип: `insufficient_information`. Split: `dev`.

**RU:** Вратарь вышел с линии раньше удара, а бьющий пробил мимо. Повторяем автоматически? Повлиял ли выход на бьющего, непонятно.

**EN:** The goalkeeper left the line early and the kicker shot wide. Is it an automatic retake? It is unclear whether the movement affected the kicker.

**Эталон RU:** Не автоматически. При промахе повтор из-за этого нарушения нужен, если оно явно повлияло на бьющего. Нужно установить влияние; сам ранний выход не даёт однозначного решения о повторе при промахе.

**Reference EN:** Not automatically. For a shot wide, a retake for that offence requires a clear impact on the kicker. That impact needs to be established; leaving early alone does not settle the retake question after a miss.

**Обязательные пункты RU:**

- Не автоматически.
- При промахе повтор из-за этого нарушения нужен, если оно явно повлияло на бьющего.
- Нужно установить влияние; сам ранний выход не даёт однозначного решения о повторе при промахе.

**Required points EN:**

- Not automatically.
- For a shot wide, a retake for that offence requires a clear impact on the kicker.
- That impact needs to be established; leaving early alone does not settle the retake question after a miss.

**Недопустимо:** Любой ранний выход вратаря требует повтора при любом промахе.

**Must not claim:** Every early goalkeeper movement requires a retake after any miss.

**Источники:**

- required_evidence: `keeper_penalty_offence`, раздел 14.2; EN: 137 (137); RU: 141 (139), 142 (140).

## FR086 — penalty_encroachment

Тип: `answerable`. Split: `test`.

**RU:** Партнёр бьющего рано вошёл в штрафную, но не повлиял на вратаря и не участвовал в дальнейшем эпизоде. Пенальти сразу залетел, других нарушений нет. Обязательно повторять?

**EN:** A team-mate of the penalty taker enters the penalty area early but does not affect the goalkeeper or participate afterwards. The kick goes straight in and there is no other offence. Must it be retaken?

**Эталон RU:** Нет, гол засчитывается. В описанной ситуации нет требуемого влияния или участия, из-за которого наказывают за ранний вход.

**Reference EN:** No, the goal counts. The described encroachment lacks the impact or involvement required for it to be penalised.

**Обязательные пункты RU:**

- Нет, гол засчитывается.
- В описанной ситуации нет требуемого влияния или участия, из-за которого наказывают за ранний вход.

**Required points EN:**

- No, the goal counts.
- The described encroachment lacks the impact or involvement required for it to be penalised.

**Недопустимо:** Любое раннее вбегание партнёра автоматически отменяет гол.

**Must not claim:** Any early entry by a team-mate automatically cancels the goal.

**Источники:**

- required_evidence: `attacker_encroachment`, раздел 14.2; EN: 136 (136); RU: 141 (139).

## FR087 — dead_ball_discipline

Тип: `answerable`. Split: `dev`.

**RU:** Мяч уже вышел в аут, вбрасывание ещё не выполнено. Защитник в своей штрафной сильно ударил соперника кулаком в лицо. Это красная плюс пенальти?

**EN:** The ball is already out for a throw-in, which has not been taken. A defender punches an opponent hard in the face inside their own penalty area. Is that a red card plus a penalty?

**Эталон RU:** За агрессивное поведение — удаление. Пенальти за этот эпизод не назначается, потому что мяч уже был вне игры. Возобновление остаётся прежним вбрасыванием.

**Reference EN:** Violent conduct requires a sending-off. No penalty is awarded for this incident because the ball was already out of play. The restart remains the previously awarded throw-in.

**Обязательные пункты RU:**

- За агрессивное поведение — удаление.
- Пенальти за этот эпизод не назначается, потому что мяч уже был вне игры.
- Возобновление остаётся прежним вбрасыванием.

**Required points EN:**

- Violent conduct requires a sending-off.
- No penalty is awarded for this incident because the ball was already out of play.
- The restart remains the previously awarded throw-in.

**Недопустимо:** Место удара в штрафной автоматически меняет аут на пенальти.

**Must not claim:** The punch occurring inside the penalty area automatically changes the throw-in to a penalty.

**Источники:**

- required_evidence: `dead_ball_restart`, раздел 12.5; EN: 127 (127); RU: 131 (129).
- required_evidence: `violent_conduct`, раздел 12.4; EN: 125 (125); RU: 128 (126).
- required_evidence: `sending_off`, раздел 12.4; EN: 123 (123); RU: 126 (124).

## FR088 — dogso_penalty

Тип: `conditional_answer`. Split: `dev`.

**RU:** Судья назначил пенальти за срыв явной возможности забить гол. Нарушение не было безрассудным или чрезмерно силовым. Красная всё равно обязательна? Был ли отбор мяча или задержка, не уточнили.

**EN:** The referee awards a penalty for denying an obvious goal-scoring opportunity. The offence was neither reckless nor excessively forceful. Is a red card still mandatory? It is unclear whether it was a challenge for the ball or holding.

**Эталон RU:** Не обязательно. При попытке сыграть в мяч или борьбе за него с назначением пенальти — предупреждение. При задержке, толчке или отсутствии возможности сыграть в мяч — удаление; нужен характер нарушения.

**Reference EN:** Not necessarily. An attempt to play or challenge for the ball with a penalty awarded results in a caution. Holding, pushing or no possibility to play the ball requires a sending-off; the nature of the offence must be established.

**Обязательные пункты RU:**

- Не обязательно.
- При попытке сыграть в мяч или борьбе за него с назначением пенальти — предупреждение.
- При задержке, толчке или отсутствии возможности сыграть в мяч — удаление; нужен характер нарушения.

**Required points EN:**

- Not necessarily.
- An attempt to play or challenge for the ball with a penalty awarded results in a caution.
- Holding, pushing or no possibility to play the ball requires a sending-off; the nature of the offence must be established.

**Недопустимо:** Любой пенальти за лишение явной возможности всегда означает красную либо всегда только жёлтую.

**Must not claim:** Every DOGSO penalty always means a red card, or always only a yellow card.

**Источники:**

- required_evidence: `dogso_penalty`, раздел 12.4; EN: 124 (124); RU: 127 (125).

## FR089 — keeper_outside_handball

Тип: `answerable`. Split: `dev`.

**RU:** Вратарь за пределами своей штрафной умышленно поймал рукой летящий в пустые ворота мяч и этим лишил соперника гола. Мяч был в игре. Пенальти или штрафной, и какая карточка?

**EN:** Outside their own penalty area, a goalkeeper deliberately catches a ball heading into the empty goal and thereby denies a goal while the ball is in play. Is it a penalty or free kick, and what card?

**Эталон RU:** Штрафной удар с места нарушения, не пенальти. Удаление за умышленную игру рукой, лишившую гола. Вне своей штрафной вратарь подчиняется обычным ограничениям игры рукой.

**Reference EN:** A direct free kick at the offence location, not a penalty. A sending-off for deliberate handball denying a goal. Outside their own penalty area the goalkeeper has the ordinary handball restrictions.

**Обязательные пункты RU:**

- Штрафной удар с места нарушения, не пенальти.
- Удаление за умышленную игру рукой, лишившую гола.
- Вне своей штрафной вратарь подчиняется обычным ограничениям игры рукой.

**Required points EN:**

- A direct free kick at the offence location, not a penalty.
- A sending-off for deliberate handball denying a goal.
- Outside their own penalty area the goalkeeper has the ordinary handball restrictions.

**Недопустимо:** Вратарь вправе ловить мяч руками где угодно либо за такое нарушение снаружи назначается пенальти.

**Must not claim:** A goalkeeper may handle anywhere, or this offence outside the area results in a penalty.

**Источники:**

- required_evidence: `keeper_outside_handball`, раздел 12.1.handball; EN: 116 (116); RU: 120 (118).
- required_evidence: `dogso_handball`, раздел 12.4; EN: 124 (124); RU: 127 (125).
- required_evidence: `handball_restart`, раздел 12.1; EN: 115 (115); RU: 118 (116).

## FR090 — var_scope

Тип: `answerable`. Split: `dev`.

**RU:** Мне говорят, VAR никогда не вмешивается во вторую жёлтую. Для явно ошибочного второго предупреждения это верно по редакции 2026/27?

**EN:** I am told VAR can never intervene in a second yellow card. Is that true for a clearly incorrect second caution under the 2026/27 edition?

**Эталон RU:** Нет. В этой редакции помощь VAR в категории удаления включает явно ошибочное второе предупреждение. Это не разрешение проверять любое обычное предупреждение.

**Reference EN:** No. In this edition the sending-off category includes a clearly incorrect second caution. That does not permit reviewing every ordinary caution.

**Обязательные пункты RU:**

- Нет.
- В этой редакции помощь VAR в категории удаления включает явно ошибочное второе предупреждение.
- Это не разрешение проверять любое обычное предупреждение.

**Required points EN:**

- No.
- In this edition the sending-off category includes a clearly incorrect second caution.
- That does not permit reviewing every ordinary caution.

**Недопустимо:** В редакции 2026/27 любые вторые предупреждения безусловно исключены из VAR.

**Must not claim:** Every second caution is categorically outside VAR in 2026/27.

**Источники:**

- required_evidence: `var_scope`, раздел 5.4; EN: 77 (77); RU: 79 (77).

## FR091 — var_scope

Тип: `conditional_answer`. Split: `dev`.

**RU:** Тренер не согласен с обычной жёлтой за фол в центре поля. Игрок не удалён, пенальти или гола нет, личность нарушителя определена правильно. VAR обязан позвать судью к монитору из-за жалобы?

**EN:** A coach disputes an ordinary yellow card for a midfield foul. There is no sending-off, penalty or goal incident and no mistaken identity. Must VAR call the referee to the monitor because of the complaint?

**Эталон RU:** Нет, жалоба сама по себе не основание. Обычная жёлтая в описанных условиях не является самостоятельной категорией вмешательства VAR. Проверка возможна при наличии другого предусмотренного протоколом основания, которого здесь не указано.

**Reference EN:** No, a complaint alone is not a basis. An ordinary yellow card in the stated circumstances is not a standalone VAR intervention category. Another protocol-authorised basis would be needed, and none is specified here.

**Обязательные пункты RU:**

- Нет, жалоба сама по себе не основание.
- Обычная жёлтая в описанных условиях не является самостоятельной категорией вмешательства VAR.
- Проверка возможна при наличии другого предусмотренного протоколом основания, которого здесь не указано.

**Required points EN:**

- No, a complaint alone is not a basis.
- An ordinary yellow card in the stated circumstances is not a standalone VAR intervention category.
- Another protocol-authorised basis would be needed, and none is specified here.

**Недопустимо:** Тренер имеет право обязательного видеопросмотра любого фола по требованию.

**Must not claim:** A coach can demand a mandatory video review of any foul.

**Источники:**

- required_evidence: `var_scope`, раздел 5.4; EN: 77 (77); RU: 79 (77).

## FR092 — offside_missing_facts

Тип: `insufficient_information`. Split: `test`.

**RU:** На стоп-кадре приёма форвард уже за защитниками. Момент паса не показан и других данных нет. Это доказывает офсайд?

**EN:** A freeze-frame at reception shows the forward beyond the defenders. The pass moment is not shown and there is no other information. Does that prove offside?

**Эталон RU:** Нет, одного кадра приёма недостаточно. Нужна позиция при игре партнёра в мяч, включая положение мяча и предпоследнего соперника, и участие в эпизоде. Нельзя утверждать, что ассистент видел отсутствующий кадр паса.

**Reference EN:** No, a reception frame alone is insufficient. Position when the team-mate plays the ball, including the ball and second-last opponent, and involvement are needed. The assistant must not claim to have seen the unavailable pass frame.

**Обязательные пункты RU:**

- Нет, одного кадра приёма недостаточно.
- Нужна позиция при игре партнёра в мяч, включая положение мяча и предпоследнего соперника, и участие в эпизоде.
- Нельзя утверждать, что ассистент видел отсутствующий кадр паса.

**Required points EN:**

- No, a reception frame alone is insufficient.
- Position when the team-mate plays the ball, including the ball and second-last opponent, and involvement are needed.
- The assistant must not claim to have seen the unavailable pass frame.

**Недопустимо:** Положение при приёме само по себе доказывает офсайд при пасе.

**Must not claim:** Position at reception alone proves offside when the pass was played.

**Источники:**

- required_evidence: `offside_position`, раздел 11.1; EN: 109 (109); RU: 111 (109).
- required_evidence: `offside_active`, раздел 11.2; EN: 109 (109), 110 (110); RU: 111 (109), 112 (110).

## FR093 — handball_uncertainty

Тип: `conditional_answer`. Split: `dev`.

**RU:** Рука вообще не двигалась к мячу. Значит, игры рукой быть не может, даже если она была отставлена?

**EN:** The arm did not move towards the ball at all. So there cannot be handball, even if it was held away from the body, right?

**Эталон RU:** Отсутствие движения к мячу не исключает нарушение. Имеет значение, делала ли рука тело неестественно больше и оправдывалось ли положение движением в этой ситуации. Без этих обстоятельств нельзя решить конкретный эпизод.

**Reference EN:** Not moving towards the ball does not rule out an offence. Whether the arm made the body unnaturally bigger and whether its position was justified by that movement matter. The specific incident cannot be decided without those circumstances.

**Обязательные пункты RU:**

- Отсутствие движения к мячу не исключает нарушение.
- Имеет значение, делала ли рука тело неестественно больше и оправдывалось ли положение движением в этой ситуации.
- Без этих обстоятельств нельзя решить конкретный эпизод.

**Required points EN:**

- Not moving towards the ball does not rule out an offence.
- Whether the arm made the body unnaturally bigger and whether its position was justified by that movement matter.
- The specific incident cannot be decided without those circumstances.

**Недопустимо:** Неподвижная рука никогда не образует нарушения.

**Must not claim:** A stationary arm can never constitute a handball offence.

**Источники:**

- required_evidence: `handball`, раздел 12.1.handball; EN: 116 (116); RU: 118 (116).

## FR094 — keeper_backpass

Тип: `answerable`. Split: `dev`.

**RU:** Партнёр обычным игровым движением головой вернул мяч вратарю, тот взял его руками в своей штрафной. Умышленного трюка для обхода правил не было. Это запрещённый пас назад?

**EN:** A team-mate heads the ball back in an ordinary passage of play and the goalkeeper handles it inside their own penalty area. There is no deliberate trick to circumvent the Law. Is that a prohibited back-pass?

**Эталон RU:** Нет, описанное действие не подпадает под запрет намеренного паса ногой. Обычная передача головой не равна умышленному трюку; в условии он исключён.

**Reference EN:** No, this does not fall under the deliberate-kick restriction. An ordinary header is not the same as a deliberate trick, which the question excludes.

**Обязательные пункты RU:**

- Нет, описанное действие не подпадает под запрет намеренного паса ногой.
- Обычная передача головой не равна умышленному трюку; в условии он исключён.

**Required points EN:**

- No, this does not fall under the deliberate-kick restriction.
- An ordinary header is not the same as a deliberate trick, which the question excludes.

**Недопустимо:** Любая намеренная передача партнёра вратарю запрещает брать мяч руками.

**Must not claim:** Every intentional pass from a team-mate prohibits goalkeeper handling.

**Источники:**

- required_evidence: `backpass`, раздел 12.2; EN: 118 (118); RU: 120 (118), 121 (119).
- required_evidence: `keeper_trick_restart`, раздел 12.2; EN: 118 (118); RU: 120 (118).

## FR095 — keeper_trick

Тип: `answerable`. Split: `dev`.

**RU:** Игрок специально подбросил мяч ногой и передал головой вратарю, чтобы обойти запрет паса ногой. Судья установил умышленный трюк, но вратарь руками не сыграл. Нарушения уже нет?

**EN:** A player deliberately flicks the ball up and heads it to the goalkeeper to circumvent the kick restriction. The referee identifies a deliberate trick, but the goalkeeper does not handle it. Is there no offence now?

**Эталон RU:** Нарушение есть независимо от последующего касания руками. Свободный удар сопернику. Инициировавший трюк игрок предупреждается за неспортивное поведение.

**Reference EN:** There is an offence regardless of subsequent handling. An indirect free kick to the opponents. The player who initiated the trick is cautioned for unsporting behaviour.

**Обязательные пункты RU:**

- Нарушение есть независимо от последующего касания руками.
- Свободный удар сопернику.
- Инициировавший трюк игрок предупреждается за неспортивное поведение.

**Required points EN:**

- There is an offence regardless of subsequent handling.
- An indirect free kick to the opponents.
- The player who initiated the trick is cautioned for unsporting behaviour.

**Недопустимо:** Без касания вратаря руками умышленный трюк всегда разрешён.

**Must not claim:** A deliberate trick is always allowed if the goalkeeper never handles.

**Источники:**

- required_evidence: `keeper_trick_restart`, раздел 12.2; EN: 118 (118); RU: 120 (118).
- required_evidence: `keeper_trick_card`, раздел 12.4; EN: 122 (122); RU: 124 (122), 125 (123).

## FR096 — live_match_result

Тип: `out_of_scope`. Split: `dev`.

**RU:** Вчера у Реала отменили гол. Судья точно ошибся? Матч и эпизод не уточняю, видео или описания нет.

**EN:** Real Madrid had a goal disallowed yesterday. Was the referee definitely wrong? I am not identifying the match or incident and have no footage or description.

**Эталон RU:** По имеющимся данным нельзя оценить конкретное решение. Нужны идентификация матча и обстоятельства эпизода или доступная запись. В корпусе правил нет фактов вчерашнего матча.

**Reference EN:** The specific decision cannot be assessed from the available information. The match must be identified and the incident described or footage supplied. The Laws corpus does not contain the facts of yesterday’s match.

**Обязательные пункты RU:**

- По имеющимся данным нельзя оценить конкретное решение.
- Нужны идентификация матча и обстоятельства эпизода или доступная запись.
- В корпусе правил нет фактов вчерашнего матча.

**Required points EN:**

- The specific decision cannot be assessed from the available information.
- The match must be identified and the incident described or footage supplied.
- The Laws corpus does not contain the facts of yesterday’s match.

**Недопустимо:** Ассистент знает точный матч, видел эпизод и подтвердил ошибку судьи.

**Must not claim:** The assistant knows the exact match, saw the incident and confirmed a refereeing error.

**Источники:**

- Доказательства конкретного ответа в корпусе отсутствуют; не включать вопрос в обычный Recall@K.

## FR097 — unavailable_edition

Тип: `out_of_scope`. Split: `dev`.

**RU:** Что именно было написано о времени контроля мяча вратарём в редакции 2024/25? У вас загружена только 2026/27; не подменяйте старый текст новым.

**EN:** What exactly did the 2024/25 edition say about goalkeeper ball-control time? Only 2026/27 is loaded; do not substitute the new text for the old.

**Эталон RU:** Текст 2024/25 отсутствует в корпусе. Для проверяемого ответа о той редакции нужно получить соответствующий документ. Нельзя ссылаться на нынешний PDF как на доказательство старой формулировки.

**Reference EN:** The 2024/25 text is absent from the corpus. A verifiable answer about that edition requires the corresponding document. The current PDF cannot substantiate the old wording.

**Обязательные пункты RU:**

- Текст 2024/25 отсутствует в корпусе.
- Для проверяемого ответа о той редакции нужно получить соответствующий документ.
- Нельзя ссылаться на нынешний PDF как на доказательство старой формулировки.

**Required points EN:**

- The 2024/25 text is absent from the corpus.
- A verifiable answer about that edition requires the corresponding document.
- The current PDF cannot substantiate the old wording.

**Недопустимо:** Выдуманная точная цитата или страница из отсутствующей редакции.

**Must not claim:** An invented exact quotation or page from the unavailable edition.

**Источники:**

- related_evidence: `keeper_time`, раздел 12.3; EN: 119 (119); RU: 121 (119), 122 (120).
- Доказательства конкретного ответа в корпусе отсутствуют; не включать вопрос в обычный Recall@K.

## FR098 — appeal_regulations

Тип: `out_of_scope`. Split: `test`.

**RU:** За сколько часов наш клуб должен подать протест на результат матча? Лига не названа, её регламента и процедуры протестов нет.

**EN:** Within how many hours must our club protest the match result? The league is not identified and its regulations and protest procedure are unavailable.

**Эталон RU:** Универсальный срок по этому корпусу определить нельзя. Нужны соревнование и применимая процедура протестов.

**Reference EN:** A universal deadline cannot be determined from this corpus. The competition and applicable protest procedure are required.

**Обязательные пункты RU:**

- Универсальный срок по этому корпусу определить нельзя.
- Нужны соревнование и применимая процедура протестов.

**Required points EN:**

- A universal deadline cannot be determined from this corpus.
- The competition and applicable protest procedure are required.

**Недопустимо:** Для всех соревнований обязательно действует придуманный срок в 24 или 48 часов.

**Must not claim:** An invented 24- or 48-hour deadline applies to every competition.

**Источники:**

- Доказательства конкретного ответа в корпусе отсутствуют; не включать вопрос в обычный Recall@K.

## FR099 — kickoff_toss

Тип: `answerable`. Split: `dev`.

**RU:** Выиграли жребий перед матчем. Мы обязаны выбрать ворота, а соперник начать с центра, или можно самим выбрать начальный удар?

**EN:** We win the pre-match toss. Must we choose an end and let the opponents kick off, or may we choose to take the kick-off?

**Эталон RU:** Можно выбрать ворота для первого тайма или начальный удар. Если выбрали ворота, соперник выполняет начальный удар; если выбрали начальный удар, соперник выбирает ворота.

**Reference EN:** The winner may choose which goal to attack in the first half or to take the kick-off. If the winner chooses an end the opponents kick off; if the winner chooses to kick off the opponents choose an end.

**Обязательные пункты RU:**

- Можно выбрать ворота для первого тайма или начальный удар.
- Если выбрали ворота, соперник выполняет начальный удар; если выбрали начальный удар, соперник выбирает ворота.

**Required points EN:**

- The winner may choose which goal to attack in the first half or to take the kick-off.
- If the winner chooses an end the opponents kick off; if the winner chooses to kick off the opponents choose an end.

**Недопустимо:** Победитель жребия всегда обязан выбирать только ворота.

**Must not claim:** The toss winner must always choose only an end.

**Источники:**

- required_evidence: `kickoff_toss`, раздел 8.1; EN: 97 (97); RU: 99 (97).

## FR100 — competition_tiebreaker

Тип: `conditional_answer`. Split: `dev`.

**RU:** Закончили 1:1. Теперь по IFAB всегда надо играть дополнительное время, а потом бить пенальти? Турнир не указан.

**EN:** We finished 1–1. Does IFAB always require extra time and then penalties? The competition is unspecified.

**Эталон RU:** Нет, матч может закончиться вничью. Если регламент требует победителя, он определяет допустимый порядок его выявления. Без регламента нельзя назначить этому матчу обязательное дополнительное время и серию.

**Reference EN:** No, a match may end in a draw. If competition rules require a winner, they determine the permitted deciding procedure. Without those rules extra time and a shoot-out cannot be imposed on this match.

**Обязательные пункты RU:**

- Нет, матч может закончиться вничью.
- Если регламент требует победителя, он определяет допустимый порядок его выявления.
- Без регламента нельзя назначить этому матчу обязательное дополнительное время и серию.

**Required points EN:**

- No, a match may end in a draw.
- If competition rules require a winner, they determine the permitted deciding procedure.
- Without those rules extra time and a shoot-out cannot be imposed on this match.

**Недопустимо:** Любая ничья в футболе автоматически ведёт к дополнительному времени и пенальти.

**Must not claim:** Every football draw automatically leads to extra time and penalties.

**Источники:**

- required_evidence: `tiebreakers`, раздел 10.2; EN: 103 (103); RU: 105 (103).
