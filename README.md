# Backyard bridge
Multiplayer card game, very similar to UNO.
![](/src/static/readme.png)
There are no winners. Only losers.

### DEMO
To try the game you can get a temporary link in `ngrok`: `ngrok http 8000`,  
remembering to specify it in `origins` list in `main.py`.

---

### NUMBER OF PLAYERS
`2 - 4`

### MAIN RULES:
1) `Players are dealt` 5 cards each; the first player automatically plays a random card from his hand.  
2) `The game starts` with each player having 0 points. The number of points can range from negative infinity to more than 125.  
3) `If you score` more than 125 points, you lose. If you score exactly 125 points, your score resets to zero.  
4) `Only one` card can be played at a time (except for the Jack).  
5) `You can` play a card if it has the same rank (e.g., Queen on Queen), the same suit (e.g., Clubs on Clubs), or if it's a Jack.  
6) `A Jack` can be played on any rank or suit and in any quantity.  
7) `The game` can end early in two scenarios:  
  &nbsp;&nbsp;• If 4 cards of the same rank are played consecutively, the player who played the 4th card <b>can</b> call "Bridge" (exception - a card with a value of 6);  
  &nbsp;&nbsp;• If a player must draw a card from the deck, but there aren't enough cards in the deck.  
In these cases, all players will be given points based on their cards in their hands.  
8) `The point multiplier` increases by +1 with each reshuffle of the deck.  

### SPECIAL CARDS
`6` — You must cover it with a card of the same suit / rank / any Jack.  
`7` — The next player must draw 1 card.  
`8` — The next player must draw 2 cards and skip their turn.  
`Jack` — You must declare a suit for the next player; can be played on any card; can be played multiple.  
`Ace` — The next player must skip their turn.  

### CARD VALUES
`6` — 0 points  
`7` — 0 points  
`8` — 0 points  
`9` — 0 points  
`10` — 10 points  
*`Jack` — -20 / 10 / 20 points  
`Queen` — 10 points  
`King` — 10 points  
`Ace` — 15 points

*Jack:  
  &nbsp;&nbsp;• 20 points if at the end of the game, only Jack(s) remain in your hand;  
  &nbsp;&nbsp;• 10 points if you end the game with a Jack and another card besides the Jack(s);  
  &nbsp;&nbsp;• -20 points if you finish the game by playing the Jack(s).

### Objective
The object of the game is to get rid of the cards in your hand as quickly as possible without scoring more than 125 points.

---
## DEPLOY
1) Clone this repo
2) Install dependencies: `pip install -r requirements.txt`
3) From `src/utils/` run `create_card_imgs.py` to create cards images
4) And run common `uvicorn main:app --reload`