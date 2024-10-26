rules_ru = """
<b>КОЛИЧЕСТВО ИГРОКОВ</b><br>
2 - 4<br>
<br>
<br>


<b>ОСНОВНЫЕ ПРАВИЛА</b><br>
<b>1) Игрокам раздается</b> по 5 карт; первый игрок автоматически разыгрывает случайную карту из руки.<br>
<b>2) Игра начинается</b> с 0 очков у каждого из игроков. Количество очков может быть от минус бесконечности, до более чем плюс 125.<br>
<b>3) Если</b> набираешь более 125 очков — ты проиграл. Если набираешь ровно 125 очков — твои очки обнуляются.<br>
<b>4) Одновременно</b> можно класть только одну карту (исключение - валет).<br>
<b>5) На карту</b> можно класть либо карту того же номинала ("дама" на "даму"), либо карту той же масти ("трефы" на "трефы"), либо валет.<br>
<b>6) Валет</b> можно класть на карту любого номинала и масти, и в любом количестве.<br>
<b>7) Раннее окончание игры</b> возможно в двух сценариях:<br>
  &nbsp;&nbsp;• если будет сыграно подряд 4 карты одинакового номинала - в этом случае игрок, который сыграл 4-ю карту <b>может</b> нажать "бридж" (исключение - карта с номиналом 6);<br>
  &nbsp;&nbsp;• если игрок обязан взять карту из колоды, но в колоде недостаточно карт.<br>
В этих случаях всем игрокам будут зачтены все очки из их рук.<br>
<b>8) Рейт очков</b>, которые будут получены по окончанию партии, увеличивается на +1 с каждым переворотом колоды.<br>
<br>
<br>


<b>ОСОБЫЕ КАРТЫ</b><br>
<b>6</b> — ты обязан её накрыть той же мастью / номиналом / вальтом любой масти.<br>
<b>7</b> — следующий игрок обязан взять 1 карту.<br>
<b>8</b> — следующий игрок обязан взять 2 карты и пропустить ход.<br>
<b>валет</b> — ты обязан загадать масть для следующего игрока; можно класть на любую карту; можно сыграть несколько<br>
<b>туз</b> — следующий игрок обязан пропустить ход.<br>
<br>
<br>


<b>НОМИНАЛ КАРТ</b><br>
<b>6</b> — 0 очков<br>
<b>7</b> — 0 очков<br>
<b>8</b> — 0 очков<br>
<b>9</b> — 0 очков<br>
<b>10</b> — 10 очков<br>
<b>*Валет</b> — -20 / 10 / 20 очков<br>
<b>Дама</b> — 10 очков<br>
<b>Король</b> — 10 очков<br>
<b>Туз</b> — 15 очков<br>
*Валет:<br>
  &nbsp;&nbsp;• 20 очков, если при окончании игры в руке остается только валет(ы);<br>
  &nbsp;&nbsp;• 10 очков, если при окончании игры в руке остается валет и другая карта помимо валета(ов);<br>
  &nbsp;&nbsp;• -20 очков, если оканчиваешь игру вальтом(ами)
"""


rules_en = """
<b>NUMBER OF PLAYERS</b><br>
2 - 4<br>
<br>
<br>


<b>MAIN RULES</b><br>
<b>1) Players are dealt</b> 5 cards each; the first player automatically plays a random card from his hand.<br>
<b>2) The game starts</b> with each player having 0 points. The number of points can range from negative infinity to more than 125.<br>
<b>3) If you score</b> more than 125 points, you lose. If you score exactly 125 points, your score resets to zero.<br>
<b>4) Only one</b> card can be played at a time (except for the Jack).<br>
<b>5) You can</b> play a card if it has the same rank (e.g., Queen on Queen), the same suit (e.g., Clubs on Clubs), or if it's a Jack.<br>
<b>6) A Jack</b> can be played on any rank or suit and in any quantity.<br>
<b>7) The game</b> can end early in two scenarios:<br>
  &nbsp;&nbsp;• If 4 cards of the same rank are played consecutively, the player who played the 4th card <b>can</b> call "Bridge" (exception - a card with a value of 6);<br>
  &nbsp;&nbsp;• If a player must draw a card from the deck, but there aren't enough cards in the deck.<br>
In these cases, all players will be given points based on their cards in their hands.<br>
<b>8) The point multiplier</b> increases by +1 with each reshuffle of the deck.<br>
<br>
<br>


<b>SPECIAL CARDS</b><br>
<b>6</b> — You must cover it with a card of the same suit / rank / any Jack.<br>
<b>7</b> — The next player must draw 1 card.<br>
<b>8</b> — The next player must draw 2 cards and skip their turn.<br>
<b>Jack</b> — You must declare a suit for the next player; can be played on any card; can be played multiple.<br>
<b>Ace</b> — The next player must skip their turn.<br>
<br>
<br>


<b>CARD VALUES</b><br>
<b>6</b> — 0 points<br>
<b>7</b> — 0 points<br>
<b>8</b> — 0 points<br>
<b>9</b> — 0 points<br>
<b>10</b> — 10 points<br>
<b>*Jack</b> — -20 / 10 / 20 points<br>
<b>Queen</b> — 10 points<br>
<b>King</b> — 10 points<br>
<b>Ace</b> — 15 points<br>
*Jack:<br>
  &nbsp;&nbsp;• 20 points if at the end of the game, only Jack(s) remain in your hand;<br>
  &nbsp;&nbsp;• 10 points if you end the game with a Jack and another card besides the Jack(s);<br>
  &nbsp;&nbsp;• -20 points if you finish the game by playing the Jack(s).
"""
