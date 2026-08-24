import { beforeAll, beforeEach, describe, expect, test, vi } from "vitest";

class FakeWebSocket {
  static instances = [];

  constructor(url) {
    this.url = url;
    this.sent = [];
    this.closed = false;
    FakeWebSocket.instances.push(this);
  }

  send(value) {
    this.sent.push(JSON.parse(value));
  }

  close(code) {
    this.closed = true;
    this.closeCode = code;
  }
}

class FakeImage {
  set src(value) {
    this._src = value;
  }

  get src() {
    return this._src;
  }
}

let app;

beforeAll(async () => {
  globalThis.WebSocket = FakeWebSocket;
  globalThis.Image = FakeImage;
  globalThis.fetch = vi.fn();
  HTMLElement.prototype.getBoundingClientRect = () => ({
    left: 10,
    top: 20,
    right: 110,
    bottom: 155,
    width: 100,
    height: 135
  });
  await import("../../src/static/js/script.dev.js");
  app = globalThis.__backyardBridge;
});

beforeEach(() => {
  vi.useRealTimers();
  FakeWebSocket.instances.length = 0;
  globalThis.fetch.mockReset();
  app.setState({
    ws: null,
    lobbyId: "abcdef",
    userId: "me",
    userName: "Me",
    sessionToken: "secret",
    isHost: false,
    currentPlayer: "other",
    game_over: false
  });
  app.elements.errorMessage.innerHTML = "";
  app.elements.playerHand.innerHTML = "";
  app.elements.usersList.innerHTML = "";
  app.elements.rightCard.innerHTML = '<img src="/right.png">';
  app.elements.leftCard.innerHTML = '<img src="/static/cards/closed_card.png">';
  app.resetScoresRate();
});

describe("URLs, identity and lobby", () => {
  test("builds local and deployed URLs", () => {
    expect(app.getWsBaseUrl("/ws")).toBe("ws://localhost:8000/ws");
    expect(app.getHttpBaseUrl("/rules")).toBe("http://localhost:8000/rules");
    const location = window.location;
    location.hostname = "game.example";
    location.host = "game.example";
    location.origin = "https://game.example";
    location.protocol = "https:";
    expect(app.getWsBaseUrl("/ws")).toBe("wss://game.example/ws");
    expect(app.getHttpBaseUrl("/rules")).toBe("https://game.example/rules");
    location.hostname = "localhost";
    location.host = "localhost:8000";
    location.origin = "http://localhost:8000";
    location.protocol = "http:";
  });

  test("updates a non-empty username and lobby UI", () => {
    app.elements.nameInput.value = "Alice";
    app.updateUsername({ preventDefault: vi.fn() });
    expect(app.getState().userName).toBe("Alice");
    expect(app.elements.wsId.textContent).toBe("Alice");
    app.elements.nameInput.value = "  ";
    app.updateUsername({ preventDefault: vi.fn() });
    expect(app.getState().userName).toBe("Alice");

    app.setLobbyUI(true);
    expect(app.getState().isHost).toBe(true);
    expect(app.elements.startButton.style.display).toBe("block");
    expect(app.elements.addBotButton.style.display).toBe("block");
    app.setLobbyUI(false);
    expect(app.elements.startButton.style.display).toBe("none");
    expect(app.elements.addBotButton.style.display).toBe("none");
  });

  test("adds bots only for an enabled host control", () => {
    const socket = new FakeWebSocket("lobby");
    app.setState({ ws: socket, isHost: true });
    app.toggleAddBotButton(true);
    app.addBot();
    expect(socket.sent).toEqual([{ type: "ab" }]);

    app.toggleAddBotButton(false);
    app.addBot();
    app.setState({ isHost: false });
    app.toggleAddBotButton(true);
    app.addBot();
    expect(socket.sent).toHaveLength(1);
  });

  test("creates, joins and rejects a missing lobby", async () => {
    vi.useFakeTimers();
    globalThis.fetch.mockResolvedValue({ json: async () => [] });
    app.createLobby();
    const socket = FakeWebSocket.instances[0];
    socket.onopen();
    expect(socket.sent[0]).toEqual({ type: "crl", user_name: "Me" });

    globalThis.fetch
      .mockResolvedValueOnce({ json: async () => ({ exists: true }) })
      .mockResolvedValueOnce({ json: async () => [] });
    app.elements.joinLobbyInput.value = "abcdef";
    await app.joinLobby();
    expect(FakeWebSocket.instances.at(-1).url).toContain("/ws/lobby/");

    globalThis.fetch.mockResolvedValueOnce({
      json: async () => ({ exists: false, msg: "Missing" })
    });
    const rejectedJoin = app.joinLobby();
    await Promise.resolve();
    await vi.runAllTimersAsync();
    await rejectedJoin;
    expect(app.elements.errorMessage.style.display).toBe("none");
    app.elements.joinLobbyInput.value = "";
    await app.joinLobby();
  });

  test("preloads images and copies the lobby id", async () => {
    globalThis.fetch.mockResolvedValue({ json: async () => ["/a.png", "/b.png"] });
    app.preloadCardImages();
    await Promise.resolve();
    await Promise.resolve();

    vi.useFakeTimers();
    app.setAndCopyLobbyId("abcdef", "Lobby");
    app.elements.lobbyMessage.click();
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith("abcdef");
    app.elements.lobbyMessage.click();
    await vi.runAllTimersAsync();
    expect(app.elements.lobbyMessage.innerHTML).toContain("click to copy");
  });

  test("preload tolerates decode and network failures", async () => {
    const OriginalImage = globalThis.Image;
    globalThis.Image = class {
      set src(value) { this._src = value; }
      decode() { return Promise.reject(new Error("decode failed")); }
    };
    globalThis.fetch.mockResolvedValueOnce({ json: async () => ["/broken.png"] });
    await expect(app.preloadCardImages()).resolves.toEqual([undefined]);

    globalThis.fetch.mockRejectedValueOnce(new Error("offline"));
    await expect(app.preloadCardImages()).resolves.toBeUndefined();
    globalThis.Image = OriginalImage;
  });

  test("initializes and replaces a lobby socket", () => {
    const previous = new FakeWebSocket("old");
    app.setState({ ws: previous });
    globalThis.fetch.mockResolvedValue({ json: async () => [] });
    app.initializeWebSocket("jl", { lobby_id: "abcdef", user_name: "Me" });
    expect(previous.closed).toBe(true);
    const socket = FakeWebSocket.instances.at(-1);
    socket.onopen();
    expect(socket.sent[0].type).toBe("jl");
    expect(socket.onmessage).toBe(app.handleWebSocketMessage);
  });
});

describe("messages and game UI", () => {
  test("handles session, lobby and simple game messages", () => {
    app.handleWebSocketMessage({ data: JSON.stringify({ type: "sid", user_id: "server-id", session_token: "token" }) });
    expect(app.getState().userId).toBe("server-id");

    app.handleWebSocketMessage({ data: JSON.stringify({ type: "lcr", lobby_id: "abcdef", msg: "Created" }) });
    app.handleWebSocketMessage({ data: JSON.stringify({ type: "jdl", lobby_id: "abcdef", msg: "Joined", users: [] }) });
    app.handleWebSocketMessage({ data: JSON.stringify({ type: "uu", users: [], is_host: true }) });
    app.handleWebSocketMessage({ data: JSON.stringify({ type: "tsb", enable: true }) });
    expect(app.elements.startButton.disabled).toBe(false);
    app.handleWebSocketMessage({ data: JSON.stringify({ type: "lg", player_id: "missing" }) });
    app.handleWebSocketMessage({ data: JSON.stringify({ type: "se", msg: "Error" }) });
    expect(app.elements.errorMessage.innerHTML).toBe("Error");
  });

  test("starts a token-authenticated game after card assets are ready", async () => {
    document.body.insertAdjacentHTML(
      "beforeend",
      '<div id="me"><div class="opponentScores"></div><div class="opponent_hand"></div></div>'
    );
    const lobbySocket = new FakeWebSocket("lobby");
    let finishPreload;
    const assetsReady = new Promise(resolve => { finishPreload = resolve; });
    app.setState({
      ws: lobbySocket,
      isHost: true,
      userId: "me",
      sessionToken: "a b",
      cardImagesReady: assetsReady
    });
    app.startGame();
    expect(lobbySocket.sent[0]).toEqual({ type: "sg" });
    const gameSocket = FakeWebSocket.instances.at(-1);
    expect(gameSocket.url).not.toContain("token=");
    const opening = gameSocket.onopen();
    expect(gameSocket.sent).toEqual([{ type: "auth", token: "a b" }]);
    finishPreload();
    await opening;
    expect(gameSocket.sent[1]).toEqual({ type: "gs" });
    expect(app.elements.currentCards.style.display).toBe("flex");
    document.getElementById("me").remove();
  });

  test("returns home and leaves lobby or game", () => {
    const socket = new FakeWebSocket("lobby");
    app.setState({ ws: socket, lobbyId: "abcdef" });
    app.leaveLobby();
    expect(socket.sent[0].type).toBe("cll");
    expect(app.elements.createLobbyButton.style.display).toBe("inline");
    const player = document.createElement("div");
    player.id = "gone";
    document.body.append(player);
    app.leaveGame("gone");
    expect(document.getElementById("gone")).toBeNull();
    app.leaveGame("missing");
  });

  test("renders users, opponent hands and scores", () => {
    app.setState({ isHost: true });
    app.updateUsers(
      [
        { user_id: "me", user_name: "Me" },
        { user_id: "other", user_name: "Other" }
      ],
      true
    );
    expect(app.elements.usersList.children).toHaveLength(2);
    expect(app.elements.startButton.disabled).toBe(false);
    expect(app.elements.addBotButton.disabled).toBe(false);

    app.updateUsers(
      Array.from({ length: 4 }, (_, index) => ({
        user_id: `player-${index}`,
        user_name: index ? `Player ${index}` : "Alex Bot",
        is_bot: index === 0
      })),
      undefined
    );
    expect(app.elements.addBotButton.disabled).toBe(true);

    app.updateUsers([{ user_id: "me", user_name: "Me", is_bot: false }], true);
    expect(app.elements.startButton.disabled).toBe(true);
    expect(app.elements.addBotButton.disabled).toBe(false);

    app.updateUsers(
      [
        { user_id: "me", user_name: "Me" },
        { user_id: "other", user_name: "Other" }
      ],
      true
    );
    app.updateOpponentData([
      { player_id: "me", hand_len: 2 },
      { player_id: "other", hand_len: 8 }
    ]);
    expect(document.getElementById("other_hand").children).toHaveLength(8);
    app.reset_game(
      [
        { player_id: "me", scores: 10 },
        { player_id: "other", scores: 20 }
      ],
      10
    );
    expect(document.getElementById("other_oS").textContent).toBe("20");
  });

  test.each([2, 3, 4])("renders and updates every client in a %i-player game", (playerCount) => {
    const users = Array.from({ length: playerCount }, (_, index) => ({
      user_id: index === 0 ? "me" : `player-${index + 1}`,
      user_name: `Player ${index + 1}`
    }));
    const playersHands = users.map((user, index) => ({
      player_id: user.user_id,
      hand_len: index + 2
    }));

    app.updateUsers(users, playerCount > 1);
    app.updateOpponentData(playersHands);

    expect(app.elements.usersList.children).toHaveLength(playerCount);
    for (const [index, user] of users.entries()) {
      expect(document.getElementById(user.user_id)).not.toBeNull();
      expect(document.getElementById(`${user.user_id}_hand`).children).toHaveLength(index + 2);
      expect(document.getElementById(`${user.user_id}_oS`).textContent).toBe("0");
    }
  });

  test("renders hand and current cards", () => {
    Object.defineProperty(app.elements.playerHand, "offsetWidth", { configurable: true, value: 500 });
    const hand = [
      { rank: "9", suit: "♠" },
      { rank: "Q", suit: "♥" }
    ];
    app.updatePlayerHand(hand, true, [hand[0]], "current");
    expect(app.elements.playerHand.children).toHaveLength(2);
    expect(app.elements.playerHand.firstChild.classList.contains("highlighted-card-img")).toBe(true);
    Object.defineProperty(app.elements.playerHand, "offsetWidth", { configurable: true, value: 50 });
    app.updatePlayerHand(hand, false, [], "current");

    app.updateCurrentCards(hand[0], 22, null, { must_draw: 0, must_skip: false, can_draw: true, can_skip: false });
    expect(app.elements.cardsLeft.textContent).toBe("22");
    app.updateCurrentCards(hand[0], 21, { suit: "♥" }, { must_draw: 0, must_skip: false, can_draw: false, can_skip: false });
    expect(app.elements.rightCard.querySelector("img").alt).toBe("♥");
    app.updateRightCard(hand[1]);
    expect(app.elements.rightCard.querySelector("img").alt).toBe("Q_♥");
  });
});

describe("turn actions and widgets", () => {
  test("plays local and opponent cards with animations", async () => {
    vi.useFakeTimers();
    const card = { rank: "9", suit: "♠" };
    app.updatePlayerHand([card], true, [card], "current");
    const socket = new FakeWebSocket("game");
    app.setState({ ws: socket, currentPlayer: "me", userId: "me" });
    const playing = app.playCard(card, "current");
    await vi.runAllTimersAsync();
    await playing;
    expect(socket.sent.at(-1)).toEqual({ type: "pc", card, chosen_suit: null });

    app.updateUsers([{ user_id: "other", user_name: "Other" }], false);
    app.updateOpponentData([{ player_id: "other", hand_len: 1 }]);
    app.setState({ currentPlayer: "other" });
    const opponent = app.playCard(card, "opponent");
    await vi.runAllTimersAsync();
    await opponent;
  });

  test("draws cards and handles the old game-over callback", async () => {
    vi.useFakeTimers();
    const socket = new FakeWebSocket("game");
    app.setState({ ws: socket, currentPlayer: "me", userId: "me", game_over: false });
    const draw = app.drawCard();
    await vi.runAllTimersAsync();
    await draw;
    expect(socket.sent.at(-1)).toEqual({ type: "dc" });

    app.setState({ game_over: true });
    const finalDraw = app.drawCard();
    await vi.runAllTimersAsync();
    await finalDraw;
    expect(socket.sent.at(-1)).toEqual({ type: "go" });

    app.updateUsers([{ user_id: "other", user_name: "Other" }], false);
    app.updateOpponentData([{ player_id: "other", hand_len: 1 }]);
    app.setState({ currentPlayer: "other" });
    const opponent = app.animateDrawCard("opponent");
    await vi.runAllTimersAsync();
    await opponent;
  });

  test("animation cleanup tolerates an already removed clone", async () => {
    vi.useFakeTimers();
    const card = document.createElement("div");
    card.innerHTML = "<img>";
    document.body.append(card);
    const played = app.animatePlayedCard(card);
    document.body.lastChild.remove();
    await vi.runAllTimersAsync();
    await played;

    const drawn = app.animateDrawCard("current");
    document.body.lastChild.remove();
    await vi.runAllTimersAsync();
    await drawn;
    card.remove();
  });

  test("supports Jack selection and first turn", () => {
    const socket = new FakeWebSocket("game");
    app.setState({ ws: socket, userId: "me", currentPlayer: "me" });
    const jack = { rank: "J", suit: "♠" };
    app.showJackWidget(jack);
    document.querySelector(".jack-widget-grid div").click();
    expect(socket.sent.at(-1).chosen_suit).toBe("♠");
    app.firstTurn({ rank: "9", suit: "♠" });
    expect(socket.sent.at(-1).type).toBe("pc");
    app.firstTurn(jack);
    app.setState({ currentPlayer: "other" });
    app.firstTurn(jack);
  });

  test("enables allowed draw and skip actions", () => {
    const socket = new FakeWebSocket("game");
    app.setState({ ws: socket, userId: "me", currentPlayer: "me" });
    app.checkCurrentPlayerOptions({ must_draw: 1, must_skip: false, can_draw: false, can_skip: false });
    app.elements.leftCard.onclick();
    app.checkCurrentPlayerOptions({ must_draw: 0, must_skip: true, can_draw: false, can_skip: false });
    expect(app.elements.rightCard.getAttribute("aria-disabled")).toBe("false");
    expect(app.elements.rightCard.tabIndex).toBe(0);
    app.elements.rightCard.onclick();
    expect(socket.sent.at(-1).type).toBe("st");
    app.checkCurrentPlayerOptions({ must_draw: 0, must_skip: false, can_draw: true, can_skip: true });
    app.checkCurrentPlayerOptions({ must_draw: 0, must_skip: false, can_draw: false, can_skip: false });
    app.setState({ currentPlayer: "other" });
    app.skip_turn();
    app.colorDrawCard();
    app.colorSkipTurn();
    app.setDefaultDrawCard();
    app.setDefaultSkipTurn();
    expect(app.elements.rightCard.getAttribute("aria-disabled")).toBe("true");
    expect(app.elements.rightCard.tabIndex).toBe(-1);
  });

  test("activates playable cards from the keyboard", () => {
    const action = vi.fn();
    const preventDefault = vi.fn();
    app.setCardAction(app.elements.rightCard, action, "Skip turn");

    app.activateWithKeyboard({ key: "Escape", currentTarget: app.elements.rightCard, preventDefault });
    expect(action).not.toHaveBeenCalled();
    app.activateWithKeyboard({ key: "Enter", currentTarget: app.elements.rightCard, preventDefault });
    app.activateWithKeyboard({ key: " ", currentTarget: app.elements.rightCard, preventDefault });

    expect(action).toHaveBeenCalledTimes(2);
    expect(preventDefault).toHaveBeenCalledTimes(2);
    expect(app.elements.rightCard.getAttribute("aria-label")).toBe("Skip turn");
    app.clearCardAction(app.elements.rightCard);
    expect(app.elements.rightCard.hasAttribute("aria-label")).toBe(false);
  });

  test("keeps Ace-forced skip highlighted after opponent animation finishes", async () => {
    vi.useFakeTimers();
    const socket = new FakeWebSocket("game");
    const ace = { rank: "A", suit: "♠" };
    const players = [
      { user_id: "me", user_name: "Me" },
      { user_id: "opponent", user_name: "Opponent" }
    ];
    app.updateUsers(players, false);
    app.updateOpponentData([
      { player_id: "me", hand_len: 1 },
      { player_id: "opponent", hand_len: 1 }
    ]);
    app.setState({ ws: socket, userId: "me", currentPlayer: "opponent" });

    app.handleWebSocketMessage({ data: JSON.stringify({ type: "apc", card: ace }) });
    app.handleWebSocketMessage({
      data: JSON.stringify({ type: "wt", msg: "It's your turn!", current_player: "me" })
    });
    app.handleWebSocketMessage({
      data: JSON.stringify({
        type: "gd",
        scores_rate: "x1",
        hand: [{ rank: "9", suit: "♥" }],
        current_player: true,
        playable_cards: [],
        players,
        players_hands: [
          { player_id: "me", hand_len: 1 },
          { player_id: "opponent", hand_len: 0 }
        ],
        current_card: ace,
        deck_len: 20,
        chosen_suit: null,
        player_options: { must_draw: 0, must_skip: true, can_draw: false, can_skip: false },
        is_host: false
      })
    });

    await vi.runAllTimersAsync();

    expect(app.elements.rightCard.querySelector("img").alt).toBe("A_♠");
    expect(app.elements.rightCard.querySelector("img").classList.contains("highlighted-card-img")).toBe(true);
    app.elements.rightCard.onclick();
    expect(socket.sent.at(-1)).toEqual({ type: "st" });
  });

  test("shows bridge choices and restores cards", async () => {
    vi.useFakeTimers();
    const socket = new FakeWebSocket("game");
    const card = { rank: "Q", suit: "♥" };
    app.setState({ ws: socket, userId: "me", currentPlayer: "me" });
    app.isItBridge(card);
    await vi.runAllTimersAsync();
    app.elements.leftCard.onclick();
    expect(socket.sent.at(-1).type).toBe("go");
    app.isItBridge(card);
    await vi.runAllTimersAsync();
    app.elements.rightCard.onclick();
    expect(socket.sent.at(-1).type).toBe("st");
    app.resetCardState(card);
  });
});

describe("messages, rules, scores and loading", () => {
  test("runs input listeners and remaining message variants", async () => {
    vi.useFakeTimers();
    app.elements.joinLobbyInput.value = "abcdef";
    app.elements.joinLobbyInput.dispatchEvent(new Event("input"));
    expect(app.elements.joinLobbyButton.disabled).toBe(false);
    app.elements.nameInput.value = "Name";
    app.elements.nameInput.dispatchEvent(new Event("input"));
    expect(document.getElementById("changeName").disabled).toBe(false);

    app.updateUsers(
      [{ user_id: "me", user_name: "Me" }, { user_id: "other", user_name: "Other" }],
      false
    );
    app.updateOpponentData([{ player_id: "me", hand_len: 1 }, { player_id: "other", hand_len: 1 }]);
    app.setState({ userId: "me", currentPlayer: "other", isHost: false, ws: new FakeWebSocket("lobby") });

    app.handleWebSocketMessage({ data: JSON.stringify({ type: "sg" }) });
    const gameSocket = FakeWebSocket.instances.at(-1);
    gameSocket.onmessage({ data: JSON.stringify({ type: "se", msg: "Socket message" }) });
    app.handleWebSocketMessage({ data: JSON.stringify({ type: "lcl" }) });
    app.handleWebSocketMessage({ data: JSON.stringify({ type: "nep", msg: "Not enough" }) });
    app.handleWebSocketMessage({
      data: JSON.stringify({ type: "iib", msg: "Bridge?", current_card: { rank: "Q", suit: "♥" } })
    });
    app.handleWebSocketMessage({
      data: JSON.stringify({
        type: "go",
        error_msg: "Over",
        widget_msg: "Results",
        players_scores: [{ player_id: "me", scores: 1 }, { player_id: "other", scores: 2 }],
        player_scores: 1,
        is_host: false
      })
    });
    app.handleWebSocketMessage({ data: JSON.stringify({ type: "godc" }) });
    app.handleWebSocketMessage({ data: JSON.stringify({ type: "apc", card: { rank: "9", suit: "♠" } }) });
    app.handleWebSocketMessage({
      data: JSON.stringify({
        type: "gr",
        players_scores: [{ player_id: "me", scores: 3 }, { player_id: "other", scores: 4 }],
        player_scores: 3
      })
    });
    await vi.runAllTimersAsync();
  });

  test("dispatches game data, turn and animation messages", async () => {
    vi.useFakeTimers();
    app.updateUsers([{ user_id: "me", user_name: "Me" }, { user_id: "other", user_name: "Other" }], false);
    app.setState({ userId: "me", currentPlayer: "me" });
    app.handleWebSocketMessage({
      data: JSON.stringify({
        type: "gd",
        scores_rate: "x2",
        hand: [],
        current_player: true,
        playable_cards: [],
        players: [{ user_id: "me", user_name: "Me" }, { user_id: "other", user_name: "Other" }],
        players_hands: [{ player_id: "me", hand_len: 0 }, { player_id: "other", hand_len: 1 }],
        current_card: { rank: "9", suit: "♠" },
        deck_len: 20,
        chosen_suit: null,
        player_options: { must_draw: 0, must_skip: false, can_draw: false, can_skip: false },
        is_host: true
      })
    });
    app.handleWebSocketMessage({ data: JSON.stringify({ type: "wt", msg: "Turn", current_player: "other" }) });
    app.handleWebSocketMessage({ data: JSON.stringify({ type: "ft", current_card: { rank: "9", suit: "♠" } }) });
    app.handleWebSocketMessage({ data: JSON.stringify({ type: "adc", current_player: "other" }) });
    await vi.runAllTimersAsync();
  });

  test("opens and closes rules", async () => {
    globalThis.fetch.mockResolvedValue({ json: async () => ({ rules: "<b>Rules</b>" }) });
    await app.showRulesWidget();
    expect(document.querySelector(".rules-column p").innerHTML).toBe("<b>Rules</b>");
    document.getElementById("closeRulesWidget").click();
    await app.showRulesWidget();
    document.getElementById("rules-widget").dispatchEvent(new MouseEvent("click", { bubbles: true }));
    await app.showRulesWidget();
    document.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter" }));
    document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));
    app.closeRulesWidget();
  });

  test("animates the score rate only when its value changes", async () => {
    vi.useFakeTimers();
    app.checkScoresRate("x2", true);
    expect(app.elements.scoresRate.classList.contains("scores-rate-change")).toBe(true);

    await vi.advanceTimersByTimeAsync(5000);
    expect(app.elements.scoresRate.classList.contains("scores-rate-change")).toBe(false);

    app.checkScoresRate("x2", true);
    expect(app.elements.scoresRate.classList.contains("scores-rate-change")).toBe(false);

    app.checkScoresRate("x3", false);
    expect(app.elements.scoresRate.classList.contains("scores-rate-change")).toBe(false);
    app.checkScoresRate("x4", true);
    expect(app.elements.scoresRate.classList.contains("scores-rate-change")).toBe(true);

    app.resetScoresRate();
    expect(app.elements.scoresRate.textContent).toBe("x1");
    expect(app.elements.scoresRate.classList.contains("scores-rate-change")).toBe(false);
    app.checkScoresRate("x2", true);
    expect(app.elements.scoresRate.classList.contains("scores-rate-change")).toBe(true);
  });

  test("updates scores and game-over controls", () => {
    app.updateUsers([{ user_id: "me", user_name: "Me" }], false);
    app.showGameOverWidget("Results", [{ player_id: "me", scores: 12 }], 12, true);
    expect(document.getElementById("continueGameButton").style.display).toBe("inline");
    app.showGameOverWidget("Results", [{ player_id: "me", scores: 12 }], 12, false);
    expect(document.getElementById("continueGameButton").style.display).toBe("none");
    app.closeGameOverWidget();
  });

  test("only host starts a new round and loader follows actual readiness", async () => {
    vi.useFakeTimers();
    const socket = new FakeWebSocket("game");
    app.setState({ ws: socket, isHost: false });
    app.startNewGame();
    expect(socket.sent).toHaveLength(0);
    app.setState({ isHost: true });
    app.startNewGame();
    expect(socket.sent[0]).toEqual({ type: "rg" });
    app.startLoadingAnimation();
    await vi.advanceTimersByTimeAsync(50);
    expect(document.getElementById("overlay").style.display).toBe("flex");
    app.finishLoadingAnimation();
    expect(document.getElementById("overlay").style.display).toBe("none");
  });

  test("loader reports a real connection timeout", async () => {
    vi.useFakeTimers();
    app.startLoadingAnimation();
    await vi.advanceTimersByTimeAsync(20000);
    expect(document.getElementById("overlay").style.display).toBe("none");
    expect(app.elements.errorMessage.innerHTML).toBe("Connection timed out. Please try again.");
  });

  test("repairs an incomplete player list from authoritative game data", () => {
    const completePlayers = [
      { user_id: "me", user_name: "Me" },
      { user_id: "two", user_name: "Two" },
      { user_id: "three", user_name: "Three" },
      { user_id: "four", user_name: "Four" }
    ];
    app.updateUsers([{ user_id: "me", user_name: "Me" }], false);
    app.ensureGamePlayers(completePlayers);
    expect(app.elements.usersList.children).toHaveLength(4);
    expect(document.getElementById("me").style.display).toBe("none");
    expect(document.querySelectorAll(".opponentScores")).toHaveLength(4);

    app.ensureGamePlayers(completePlayers);
    app.ensureGamePlayers(completePlayers.map(player => (
      player.user_id === "four" ? { user_id: "five", user_name: "Five" } : player
    )));
    expect(document.getElementById("five")).not.toBeNull();
  });

  test("covers optional card and navigation paths", async () => {
    vi.useFakeTimers();
    const socket = new FakeWebSocket("game");
    const jack = { rank: "J", suit: "♠" };
    app.setState({ ws: socket, userId: "me", currentPlayer: "me" });
    Object.defineProperty(app.elements.playerHand, "offsetWidth", { configurable: true, value: 300 });
    app.updatePlayerHand([jack], true, [jack], "current");
    app.elements.playerHand.firstChild.click();
    await vi.runAllTimersAsync();
    document.querySelector(".jack-widget-grid div").click();
    app.change_player("");

    app.elements.rightCard.innerHTML = "";
    app.updateRightCard({ rank: "9", suit: "♥" });
    app.elements.rightCard.innerHTML = "";
    app.updateCurrentCards(
      { rank: "9", suit: "♥" },
      10,
      null,
      { must_draw: 0, must_skip: false, can_draw: false, can_skip: false }
    );
    await vi.runAllTimersAsync();

    const navigation = app.leaveGameFromWidget();
    await vi.runAllTimersAsync();
    await navigation;
    expect(window.location.href).toBe("http://localhost:8000");
  });
});
