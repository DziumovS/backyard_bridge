# Backyard bridge
Multiplayer card game, very similar to UNO.
![Create a lobby, join a game, and play cards](/src/static/demo.gif)
There are no winners. Only losers.

### DEMO
To expose a local server temporarily, run `ngrok http 8000` and add its HTTPS
origin to `BACKYARD_BRIDGE_ALLOWED_ORIGINS`.

---

### NUMBER OF PLAYERS
`2 - 4`

The lobby host can fill open seats with server-controlled bots. Bots use
American first names followed by `Bot`, follow the same authoritative rules as
human players, and choose moves aimed at emptying their hand. Before the game
starts, the host can remove either human guests or bots from the lobby.

Hosts choose a maximum lobby size from 2 to 4 players. The lobby browser shows
all open lobbies with their current capacity and marks private ones with a
lock, without exposing their six-character invitation codes. Public lobbies
can be joined from the list or through Quick Play. The same lobby browser has
an invitation-code field for private lobbies, so public discovery and private
joining do not need separate screens. Lobby state is kept in memory and each
lobby is named after its host, for example `Alice's lobby`.

The open lobby browser refreshes automatically every four seconds and can also
be refreshed manually. Discovery and Quick Play are read-only HTTP GET
requests; joining is an authenticated WebSocket command whose capacity, code,
and game-state checks are enforced by the server.

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
## LOCAL DEVELOPMENT

Requires [uv](https://docs.astral.sh/uv/) and Node.js 22+. Python 3.14 is
installed automatically by `uv` when it is not already available.

```bash
uv sync --locked
npm ci
BACKYARD_BRIDGE_DEV_ASSETS=1 uv run uvicorn main:app --reload
```

Use `uv add <package>` for application dependencies and
`uv add --dev <package>` for development dependencies. Run `uv lock --upgrade`
when intentionally updating the complete Python dependency tree, and commit
both `pyproject.toml` and `uv.lock`.

The editable frontend sources are `src/static/js/script.dev.js`,
`src/static/css/styles.dev.css`, and `src/templates/index.dev.html`. The command
above serves them directly, so minification is unnecessary during development.
Run `npm run build` before committing; `npm test` verifies that committed
production assets are current.

## TESTS

```bash
uv run pytest
npm test
```

The server suite includes real WebSocket sessions for every supported player
count (2, 3, and 4). Both server and client coverage thresholds are at least
99%. Browser tests cover responsive lobby geometry, mobile touch focus,
public/private discovery and joining, private codes, and Quick Play capacity
selection. Install Chromium
once with `npx playwright install chromium` before running `npm test` locally.
GitHub Actions runs every suite for pushes and pull requests.

## DEPLOYMENT

Install the locked production dependencies, build the frontend, and start the
ASGI application:

```bash
uv sync --locked --no-dev
npm ci
npm run build
uv run --locked --no-dev uvicorn main:app --host 0.0.0.0 --port 8000
```

Restart the ASGI process after every backend update. Static files can otherwise
come from the new checkout while a long-running Python process still uses the
old WebSocket protocol.

Configure comma-separated browser/mobile origins when the frontend is hosted
separately from the API:

```bash
BACKYARD_BRIDGE_ALLOWED_ORIGINS=https://game.example,capacitor://localhost
```

Bot actions use a short delay so their moves remain readable in the UI. It can
be configured in seconds when needed:

```bash
BACKYARD_BRIDGE_BOT_ACTION_DELAY=0.45
```

Disconnected clients have 60 seconds to restore the same token-authenticated
session after a game has started. The home screen displays a server-synchronized
countdown with explicit reconnect and leave actions. Session credentials use
per-tab storage, preventing another tab on the same browser from inheriting a
player's seat. The timeout can be changed for development or testing without
changing production behavior:

```bash
BACKYARD_BRIDGE_RECONNECT_GRACE_SECONDS=60
```

Before a game starts, disconnecting from a lobby removes that player
immediately; disconnecting the host closes the lobby for everyone. During an
active game, an expired timeout from the host closes the game. A regular player
is removed and the remaining game continues when enough players remain. Players
can also leave immediately from the game header: a host departure ends the game,
while a guest's hand is shuffled back into the draw deck and any pending draw or
skip effect moves to the next player.

`GET /health` is available for platform health checks. WebSocket connections
remain client-to-server by design; all authoritative game state and rule
validation stay on the backend.
