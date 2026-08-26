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
  globalThis.fetch = vi.fn().mockResolvedValue({ json: async () => [] });
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
  sessionStorage.clear();
  globalThis.fetch.mockReset();
  globalThis.fetch.mockResolvedValue({ json: async () => [] });
  app.setState({
    ws: null,
    lobbyId: "abcdef",
    userId: "me",
    userName: "Me",
    sessionToken: "secret",
    isHost: false,
    currentPlayer: "other",
    game_over: false,
    lobbyMaxPlayers: 4,
    selectedLobbySize: 4,
    currentPhase: "home",
    reconnectDeadline: 0,
    reconnecting: false,
    reconnectRequested: false,
    leavingGame: false,
    lobbyIsPublic: false,
    lobbyPlayerCount: 0,
    lobbyCapabilities: ["kick_users"]
  });
  app.elements.errorMessage.innerHTML = "";
  app.elements.playerHand.innerHTML = "";
  app.elements.usersList.innerHTML = "";
    app.elements.availableLobbiesList.innerHTML = "";
    app.elements.availableLobbiesEmpty.hidden = false;
  app.elements.createLobbyWidget.style.display = "none";
  app.elements.lobbyControls.style.display = "none";
  app.elements.homeLobbyActions.style.display = "grid";
  app.elements.lobbyBrowserWidget.style.display = "none";
  app.elements.reconnectGameWidget.style.display = "none";
  app.elements.leaveGameConfirmWidget.style.display = "none";
  app.elements.currentCards.style.display = "none";
  app.elements.playerContainer.style.display = "none";
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
    expect(app.elements.usersHeader.classList.contains("lobby-users-header")).toBe(true);
    expect(app.elements.startButton.style.display).toBe("block");
    expect(app.elements.addBotButton.style.display).toBe("block");
    app.setLobbyUI(false);
    expect(app.elements.startButton.style.display).toBe("none");
    expect(app.elements.addBotButton.style.display).toBe("none");
  });

  test("configures public and private lobbies with an exact player count", () => {
    globalThis.fetch.mockResolvedValue({ json: async () => [] });
    app.elements.createLobbyButton.click();
    expect(app.elements.createLobbyWidget.style.display).toBe("flex");
    expect(app.getState().selectedLobbySize).toBe(4);

    app.elements.playerCountButtons[0].click();
    expect(app.getState().selectedLobbySize).toBe(2);
    expect(app.elements.playerCountButtons[0].getAttribute("aria-pressed")).toBe("true");
    app.elements.createPublicLobbyButton.click();
    const publicSocket = FakeWebSocket.instances.at(-1);
    publicSocket.onopen();
    expect(publicSocket.sent[0]).toEqual({
      type: "crl", user_name: "Me", is_public: true, max_players: 2
    });
    expect(app.elements.createLobbyWidget.style.display).toBe("none");
    expect(app.getState().isHost).toBe(false);
    expect(app.elements.lobbyControls.style.display).not.toBe("block");

    app.setState({ ws: null });
    app.elements.playerCountButtons[1].click();
    app.elements.createPrivateLobbyButton.click();
    const privateSocket = FakeWebSocket.instances.at(-1);
    privateSocket.onopen();
    expect(privateSocket.sent[0]).toEqual({
      type: "crl", user_name: "Me", is_public: false, max_players: 3
    });

    app.openCreateLobbyWidget();
    app.elements.createLobbyWidget.click();
    expect(app.elements.createLobbyWidget.style.display).toBe("none");
  });

  test("hides kick controls when an older server does not advertise support", () => {
    app.setState({ isHost: true, userId: "me", lobbyCapabilities: [] });
    app.updateUsers([
      { user_id: "me", user_name: "Me" },
      { user_id: "other", user_name: "Other" }
    ], true);
    expect(app.elements.usersList.querySelectorAll(".kick-player-button")).toHaveLength(0);
  });

  test("adds bots only for an enabled host control and clears delayed touch focus", async () => {
    vi.useFakeTimers();
    const socket = new FakeWebSocket("lobby");
    const blur = vi.spyOn(app.elements.addBotButton, "blur");
    app.setState({ ws: socket, isHost: true });
    app.toggleAddBotButton(true);
    app.addBot();
    expect(socket.sent).toEqual([{ type: "ab" }]);
    expect(blur).not.toHaveBeenCalled();
    await vi.runAllTimersAsync();
    expect(blur).toHaveBeenCalledOnce();

    app.toggleAddBotButton(false);
    app.addBot();
    app.setState({ isHost: false });
    app.toggleAddBotButton(true);
    app.addBot();
    expect(socket.sent).toHaveLength(1);
    expect(blur).toHaveBeenCalledOnce();
  });

  test("renders kick controls only for the host and sends the target id", () => {
    const socket = new FakeWebSocket("lobby");
    app.setState({ ws: socket, isHost: true, userId: "me" });
    app.updateUsers(
      [
        { user_id: "me", user_name: "Me", is_bot: false },
        { user_id: "bot-1", user_name: "Alex Bot", is_bot: true }
      ],
      true
    );

    const kickButtons = app.elements.usersList.querySelectorAll(".kick-player-button");
    expect(kickButtons).toHaveLength(1);
    expect(kickButtons[0].getAttribute("aria-label")).toBe("Remove Alex Bot from lobby");
    kickButtons[0].click();
    expect(socket.sent).toEqual([{ type: "ku", user_id: "bot-1" }]);

    app.kickUser("me");
    app.setState({ isHost: false });
    app.kickUser("bot-1");
    app.updateUsers([{ user_id: "other", user_name: "Other" }], false);
    expect(app.elements.usersList.querySelectorAll(".kick-player-button")).toHaveLength(0);
    expect(socket.sent).toHaveLength(1);
  });

  test("removes lobby controls from the game player list", () => {
    app.setState({ isHost: true, userId: "me" });
    app.updateUsers(
      [
        { user_id: "me", user_name: "Me", is_host: true },
        { user_id: "other", user_name: "Other" }
      ],
      true
    );
    expect(app.elements.usersList.querySelectorAll(".kick-player-button")).toHaveLength(1);
    expect(app.elements.usersList.querySelector(".host-label").textContent).toBe("HOST");
    app.setGameUI();
    expect(app.elements.usersList.querySelectorAll(".kick-player-button")).toHaveLength(0);
    expect(app.elements.usersHeader.classList.contains("lobby-users-header")).toBe(false);
    expect(app.elements.usersList.querySelector(".host-label")).toBeNull();
  });

  test("creates, joins and rejects a missing lobby", async () => {
    vi.useFakeTimers();
    globalThis.fetch.mockResolvedValue({ json: async () => [] });
    app.createLobby();
    const socket = FakeWebSocket.instances[0];
    socket.onopen();
    expect(socket.sent[0]).toEqual({
      type: "crl", user_name: "Me", is_public: false, max_players: 4
    });

    app.elements.joinLobbyInput.value = "abcdef";
    await app.joinLobby();
    expect(FakeWebSocket.instances.at(-1).url).toContain("/ws/lobby/");

    app.elements.joinLobbyInput.value = "";
    await app.joinLobby();
  });

  test("preloads images and renders safe public and private lobby details", async () => {
    globalThis.fetch.mockResolvedValue({ json: async () => ["/a.png", "/b.png"] });
    app.preloadCardImages();
    await Promise.resolve();
    await Promise.resolve();

    vi.useFakeTimers();
    app.renderLobbyDetails({
      lobby_id: "abcdef",
      lobby_name: "Me's lobby",
      is_public: false,
      max_players: 3
    });
    const codeButton = app.elements.lobbyMessage.querySelector(".lobby-code-button");
    codeButton.click();
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith("abcdef");
    expect(codeButton.textContent).toContain("Code copied");
    await vi.runAllTimersAsync();
    expect(codeButton.textContent).toContain("tap to copy");
    expect(app.getState().lobbyMaxPlayers).toBe(3);
    expect(document.getElementById("lobbySummaryMeta").textContent).toContain("1/3 players");

    app.renderLobbyDetails({
      lobby_id: "fedcba",
      lobby_name: "<Host>'s lobby",
      is_public: true,
      max_players: 2
    });
    expect(app.elements.lobbyMessage.textContent).toContain("<Host>'s lobby");
    expect(app.elements.lobbyMessage.querySelector(".lobby-code-button")).toBeNull();
    app.renderLobbyDetails({
      lobby_id: "legacy",
      lobby_name: "Legacy lobby",
      is_public: true
    });
    expect(app.getState().lobbyMaxPlayers).toBe(4);
  });

  test("lists public and private lobbies, reveals Join after selection, and refreshes", async () => {
    globalThis.fetch
      .mockResolvedValueOnce({ json: async () => [{
        lobby_id: "abc123", name: "Alice's lobby", players: 1, max_players: 3,
        is_private: false
      }, {
        name: "Bob's lobby", players: 2, max_players: 4, is_private: true
      }] })
      .mockResolvedValueOnce({ json: async () => [] });

    await app.refreshAvailableLobbies();
    expect(app.elements.availableLobbiesList.textContent).toContain("Alice's lobby");
    expect(app.elements.availableLobbiesEmpty.hidden).toBe(true);
    expect(app.elements.availableLobbiesList.textContent).toContain("1/3");
    expect(app.elements.availableLobbiesList.textContent).toContain("🔒");
    expect(app.elements.availableLobbiesList.querySelector("strong").textContent).toBe("Alice");
    const publicRow = app.elements.availableLobbiesList.querySelector(".available-lobby-row");
    expect(publicRow.querySelector(".available-lobby-join-button").style.display).toBe("");
    publicRow.click();
    expect(publicRow.classList.contains("selected")).toBe(true);
    publicRow.querySelector(".available-lobby-join-button").click();
    await Promise.resolve();
    await Promise.resolve();
    expect(FakeWebSocket.instances.at(-1).url).toContain("/ws/lobby/");

    globalThis.fetch.mockResolvedValueOnce({ json: async () => [] });
    await app.refreshAvailableLobbies();
    expect(app.elements.availableLobbiesEmpty.textContent).toBe("No lobbies are available yet");
    expect(app.elements.availableLobbiesEmpty.hidden).toBe(false);

    globalThis.fetch.mockRejectedValueOnce(new Error("offline"));
    await app.refreshAvailableLobbies();
    expect(app.elements.refreshLobbiesButton.disabled).toBe(false);
  });

  test("joins a private code from the unified lobby browser and reports a wrong code", async () => {
    vi.useFakeTimers();
    globalThis.fetch.mockResolvedValueOnce({ json: async () => [] });
    app.openLobbyBrowser();
    await Promise.resolve();
    expect(app.elements.lobbyBrowserWidget.style.display).toBe("flex");

    app.elements.joinLobbyInput.value = "deadbe";
    app.elements.joinLobbyInput.dispatchEvent(new Event("input"));
    app.elements.joinLobbyInput.focus();
    await app.joinLobby();
    expect(document.activeElement).not.toBe(app.elements.joinLobbyInput);
    expect(app.elements.joinLobbyInput.value).toBe("");
    expect(app.elements.joinLobbyButton.disabled).toBe(true);
    const socket = FakeWebSocket.instances.at(-1);
    socket.onopen();
    expect(socket.sent[0]).toMatchObject({ lobby_id: "deadbe", private_only: true });
    app.handleWebSocketMessage({
      data: JSON.stringify({ type: "se", msg: "The lobby doesn't exist or no slots." })
    });
    expect(app.elements.lobbyBrowserError.textContent).toBe("The private lobby was not found");
    expect(app.elements.lobbyControls.style.display).not.toBe("block");
    await vi.advanceTimersByTimeAsync(2999);
    expect(app.elements.lobbyBrowserError.textContent).toBe("The private lobby was not found");
    await vi.advanceTimersByTimeAsync(1);
    expect(app.elements.lobbyBrowserError.textContent).toBe("");

    app.closeLobbyBrowser();
    expect(app.elements.lobbyBrowserWidget.style.display).toBe("none");
    vi.useRealTimers();
  });

  test("shows a global error when a listed public lobby disappears", async () => {
    vi.useFakeTimers();
    await app.joinLobbyById("deadbe");
    app.handleWebSocketMessage({
      data: JSON.stringify({ type: "se", msg: "The lobby doesn't exist or no slots." })
    });
    await vi.runAllTimersAsync();
    expect(app.elements.errorMessage.style.display).toBe("none");
  });

  test("supports lobby modal closing, keyboard selection, and private code focus", async () => {
    globalThis.fetch.mockResolvedValue({ json: async () => [] });
    app.elements.joinPublicLobbyButton.click();
    await Promise.resolve();
    expect(app.elements.lobbyBrowserWidget.style.display).toBe("flex");
    app.elements.closeLobbyBrowserWidget.click();
    expect(app.elements.lobbyBrowserWidget.style.display).toBe("none");
    app.openLobbyBrowser();
    app.elements.lobbyBrowserWidget.click();
    expect(app.elements.lobbyBrowserWidget.style.display).toBe("none");

    app.renderAvailableLobbies([
      { name: "Private", players: 1, max_players: 4, is_private: true },
      { lobby_id: "public", name: "Public", players: 1, max_players: 4, is_private: false }
    ]);
    app.elements.lobbyBrowserWidget.style.display = "flex";
    const rows = app.elements.availableLobbiesList.querySelectorAll(".available-lobby-row");
    rows[0].dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
    expect(rows[0].classList.contains("selected")).toBe(true);
    rows[1].dispatchEvent(new KeyboardEvent("keydown", { key: " ", bubbles: true }));
    expect(rows[1].classList.contains("selected")).toBe(true);
    rows[1].dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowDown", bubbles: true }));
    rows[0].querySelector(".available-lobby-join-button").click();
    expect(app.elements.lobbyBrowserWidget.style.display).toBe("flex");
    expect(document.activeElement).toBe(app.elements.joinLobbyInput);
  });

  test("refreshes an open lobby list every four seconds and stops when closed", async () => {
    vi.useFakeTimers();
    globalThis.fetch.mockResolvedValue({ json: async () => [] });
    app.openLobbyBrowser();
    await Promise.resolve();
    expect(globalThis.fetch).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(4000);
    expect(globalThis.fetch).toHaveBeenCalledTimes(2);
    app.closeLobbyBrowser();
    await vi.advanceTimersByTimeAsync(8000);
    expect(globalThis.fetch).toHaveBeenCalledTimes(2);

    app.startLobbyAutoRefresh();
    app.elements.lobbyBrowserWidget.style.display = "none";
    await vi.advanceTimersByTimeAsync(4000);
    expect(globalThis.fetch).toHaveBeenCalledTimes(2);
    app.stopLobbyAutoRefresh();
  });

  test("quick play joins an available public lobby and handles no availability", async () => {
    globalThis.fetch
      .mockResolvedValueOnce({ json: async () => ({ lobby_id: "quick1" }) })
      .mockResolvedValueOnce({ json: async () => [] });
    await app.quickPlay();
    expect(FakeWebSocket.instances.at(-1).url).toContain("/ws/lobby/");

    vi.useFakeTimers();
    globalThis.fetch.mockResolvedValueOnce({ json: async () => null });
    const noLobby = app.quickPlay();
    await Promise.resolve();
    await vi.runAllTimersAsync();
    await noLobby;
    expect(app.elements.quickPlayButton.disabled).toBe(false);
  });

  test("quick play recovers from a discovery error", async () => {
    vi.useFakeTimers();
    globalThis.fetch.mockRejectedValueOnce(new Error("offline"));
    const request = app.quickPlay();
    await Promise.resolve();
    await vi.runAllTimersAsync();
    await request;
    expect(app.elements.quickPlayButton.disabled).toBe(false);
  });

  test("enters lobby UI only after a server confirmation", () => {
    app.elements.homeLobbyActions.style.display = "grid";
    app.createLobby(true);
    expect(app.elements.homeLobbyActions.style.display).toBe("grid");
    app.handleWebSocketMessage({
      data: JSON.stringify({
        type: "lcr", lobby_id: "created", lobby_name: "Me's lobby",
        is_public: true, max_players: 4
      })
    });
    expect(app.elements.homeLobbyActions.style.display).toBe("none");
    expect(app.getState().isHost).toBe(true);

    app.returnToMainPage();
    app.handleWebSocketMessage({ data: JSON.stringify({ type: "se", msg: "Invalid lobby message." }) });
    expect(app.elements.homeLobbyActions.style.display).toBe("grid");
    expect(app.getState().isHost).toBe(false);
  });

  test("stores and restores only active game sessions", async () => {
    app.setState({
      userId: "saved-user", userName: "Saved", sessionToken: "x".repeat(32),
      lobbyId: "abcdef", isHost: true, currentPhase: "lobby"
    });
    app.storeSession();
    expect(app.readStoredSession()).toBeNull();

    sessionStorage.setItem("backyardBridgeSession", JSON.stringify({
      userId: "saved-user", userName: "Saved", sessionToken: "x".repeat(32),
      lobbyId: "abcdef", isHost: true, phase: "lobby"
    }));
    app.setState({ currentPhase: "home", ws: null });
    expect(app.restoreStoredSession()).toBe(false);
    expect(FakeWebSocket.instances).toHaveLength(0);

    sessionStorage.setItem("backyardBridgeSession", JSON.stringify({
      userId: "saved-user", userName: "Saved", sessionToken: "x".repeat(32),
      lobbyId: "abcdef", isHost: false, phase: "game"
    }));
    app.setState({ currentPhase: "home" });
    expect(app.restoreStoredSession()).toBe(true);
    expect(app.elements.welcomeMessage.style.display).toBe("block");
    expect(app.elements.homeLobbyActions.style.display).toBe("grid");
    expect(app.elements.nameForm.style.display).toBe("none");
    expect(app.elements.reconnectGameWidget.style.display).toBe("flex");
    app.reconnectGame();
    const gameSocket = FakeWebSocket.instances.at(-1);
    await gameSocket.onopen();
    expect(gameSocket.sent).toEqual([{ type: "auth", token: "x".repeat(32) }]);

    sessionStorage.setItem("backyardBridgeSession", "{");
    expect(app.readStoredSession()).toBeNull();
    sessionStorage.setItem("backyardBridgeSession", JSON.stringify({ phase: "lobby" }));
    expect(app.restoreStoredSession()).toBe(false);
    sessionStorage.setItem("backyardBridgeSession", JSON.stringify({
      userId: "saved-user", userName: "Saved", sessionToken: "x".repeat(32),
      lobbyId: "abcdef", phase: "unknown"
    }));
    expect(app.restoreStoredSession()).toBe(false);
    expect(sessionStorage.getItem("backyardBridgeSession")).toBeNull();
  });

  test("retries only game sockets and gives up after sixty seconds", async () => {
    vi.useFakeTimers();
    globalThis.fetch.mockResolvedValue({ json: async () => [] });
    app.setState({
      userId: "me", sessionToken: "x".repeat(32), lobbyId: "abcdef",
      currentPhase: "home", reconnectDeadline: 0
    });
    app.scheduleReconnect("lobby");
    await vi.advanceTimersByTimeAsync(1000);
    expect(FakeWebSocket.instances).toHaveLength(0);

    app.setState({ currentPhase: "lobby", reconnectDeadline: 0 });
    app.scheduleReconnect("lobby");
    await vi.advanceTimersByTimeAsync(1000);
    expect(FakeWebSocket.instances).toHaveLength(0);

    app.setState({
      currentPhase: "game", reconnectDeadline: 0, reconnectRequested: true, ws: null
    });
    app.scheduleReconnect("game");
    await vi.advanceTimersByTimeAsync(1000);
    const gameSocket = FakeWebSocket.instances.at(-1);
    expect(gameSocket.url).toContain("/ws/game/");
    gameSocket.onclose();

    app.setState({
      currentPhase: "game", reconnectDeadline: Date.now() - 1, reconnectRequested: true
    });
    app.scheduleReconnect("game");
    expect(app.getState().currentPhase).toBe("home");
    await vi.runAllTimersAsync();
  });

  test("shows, expires, and leaves the manual reconnect dialog", async () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-08-26T00:00:00Z"));
    app.setState({
      currentPhase: "game", reconnectDeadline: 0, leavingGame: false,
      userId: "me", lobbyId: "abcdef", sessionToken: "x".repeat(32)
    });
    window.dispatchEvent(new Event("pagehide"));
    expect(app.readStoredSession().reconnectDeadline).toBe(Date.now() + 60000);

    app.showReconnectGameWidget();
    expect(app.elements.reconnectGameWidget.style.display).toBe("flex");
    expect(app.elements.reconnectGameTimer.textContent).toBe("60");
    const statusSocket = FakeWebSocket.instances.at(-1);
    statusSocket.onopen();
    expect(statusSocket.sent).toEqual([{
      type: "auth", token: "x".repeat(32), intent: "status"
    }]);
    statusSocket.onmessage({ data: JSON.stringify({ type: "other", seconds: 42 }) });
    statusSocket.onmessage({ data: JSON.stringify({ type: "rs", seconds: "bad" }) });
    statusSocket.onmessage({ data: JSON.stringify({ type: "rs", seconds: 42.5 }) });
    expect(app.elements.reconnectGameTimer.textContent).toBe("43");

    app.leaveDisconnectedGame();
    const leaveSocket = FakeWebSocket.instances.at(-1);
    leaveSocket.onopen();
    expect(leaveSocket.sent).toEqual([{
      type: "auth", token: "x".repeat(32), intent: "leave"
    }]);
    expect(app.getState().currentPhase).toBe("home");

    app.setState({ currentPhase: "game", reconnectDeadline: Date.now() - 1 });
    app.updateReconnectCountdown();
    expect(app.getState().currentPhase).toBe("home");
    expect(app.elements.errorMessage.textContent).toBe("The reconnect time has expired");

    app.setState({ currentPhase: "game", reconnectDeadline: Date.now() - 1 });
    app.reconnectGame();
    expect(app.getState().currentPhase).toBe("home");

    app.setState({
      currentPhase: "game", reconnectDeadline: Date.now() + 60000,
      userId: "me", lobbyId: "abcdef", sessionToken: "x".repeat(32)
    });
    app.syncReconnectDeadline();
    FakeWebSocket.instances.at(-1).onmessage({ data: JSON.stringify({ type: "se" }) });
    expect(app.getState().currentPhase).toBe("home");
    expect(app.elements.errorMessage.textContent).toBe("The game is no longer available");
    await vi.runAllTimersAsync();
  });

  test("handles game socket closure branches and explicit in-game leave", async () => {
    vi.useFakeTimers();
    app.setState({
      currentPhase: "game", reconnectDeadline: 0, reconnectRequested: false,
      leavingGame: false, ws: null
    });
    app.connectGameWebSocket(true);
    const disconnected = FakeWebSocket.instances.at(-1);
    disconnected.onclose();
    expect(app.elements.reconnectGameWidget.style.display).toBe("flex");

    app.setState({ currentPhase: "game", reconnectRequested: true, leavingGame: false });
    app.connectGameWebSocket(true);
    FakeWebSocket.instances.at(-1).onclose();
    await vi.advanceTimersByTimeAsync(1000);
    expect(FakeWebSocket.instances.at(-1).url).toContain("/ws/game/");

    app.setState({ currentPhase: "home", ws: null });
    app.showLeaveGameConfirmation();
    expect(app.elements.leaveGameConfirmWidget.style.display).toBe("none");
    app.setState({ currentPhase: "game", ws: new FakeWebSocket("active") });
    const active = app.getState().ws;
    app.showLeaveGameConfirmation();
    expect(app.elements.leaveGameConfirmWidget.style.display).toBe("flex");
    expect(active.sent).toEqual([]);
    app.elements.continueActiveGameButton.click();
    expect(app.getState().currentPhase).toBe("game");
    expect(active.sent).toEqual([]);
    app.showLeaveGameConfirmation();
    app.elements.leaveGameConfirmWidget.click();
    expect(app.elements.leaveGameConfirmWidget.style.display).toBe("none");
    app.showLeaveGameConfirmation();
    app.confirmLeaveActiveGame();
    expect(active.sent).toEqual([{ type: "lg" }]);
    expect(app.getState().currentPhase).toBe("home");

    window.dispatchEvent(new Event("pagehide"));
    app.connectGameWebSocket(true);
    FakeWebSocket.instances.at(-1).onclose();
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

    app.setState({ currentPhase: "lobby" });
    socket.onclose();
    expect(app.getState().currentPhase).toBe("home");
    expect(app.elements.homeLobbyActions.style.display).toBe("grid");

    app.setState({ currentPhase: "home" });
    socket.onclose();
  });
});

describe("messages and game UI", () => {
  test("handles session, lobby and simple game messages", () => {
    app.handleWebSocketMessage({
      data: JSON.stringify({ type: "sid", user_id: "legacy-id", session_token: "legacy-token" })
    });
    expect(app.getState().lobbyCapabilities).toEqual([]);

    app.handleWebSocketMessage({
      data: JSON.stringify({
        type: "sid",
        user_id: "server-id",
        session_token: "token",
        capabilities: ["kick_users"]
      })
    });
    expect(app.getState().userId).toBe("server-id");
    expect(app.getState().lobbyCapabilities).toEqual(["kick_users"]);

    const lobbyData = {
      lobby_id: "abcdef", lobby_name: "Host's lobby", is_public: true, max_players: 2
    };
    app.handleWebSocketMessage({ data: JSON.stringify({ type: "lcr", ...lobbyData }) });
    app.handleWebSocketMessage({ data: JSON.stringify({ type: "jdl", ...lobbyData, users: [] }) });
    app.handleWebSocketMessage({ data: JSON.stringify({ type: "uu", users: [], is_host: true, max_players: 2 }) });
    app.handleWebSocketMessage({ data: JSON.stringify({ type: "tsb", enable: true }) });
    expect(app.elements.startButton.disabled).toBe(false);
    app.handleWebSocketMessage({ data: JSON.stringify({ type: "lg", player_id: "missing" }) });
    app.handleWebSocketMessage({ data: JSON.stringify({ type: "se", msg: "Error" }) });
    expect(app.elements.errorMessage.innerHTML).toBe("Error");
  });

  test("returns lobby clients home when the host closes the lobby", () => {
    app.handleWebSocketMessage({
      data: JSON.stringify({
        type: "jdl", lobby_id: "abcdef", lobby_name: "Host's lobby",
        is_public: false, max_players: 4, users: [
          { user_id: "me", user_name: "Host", is_host: true }
        ], is_host: true
      })
    });
    expect(app.getState().isHost).toBe(true);
    expect(app.elements.startButton.style.display).toBe("block");
    expect(document.getElementById("lobbySummaryMeta").textContent).toContain("1/4 players");

    app.handleWebSocketMessage({
      data: JSON.stringify({
        type: "lcl", msg: "The host left the lobby, so you were returned to the home page"
      })
    });
    expect(app.getState().currentPhase).toBe("home");
    expect(sessionStorage.getItem("backyardBridgeSession")).toBeNull();
    expect(app.elements.errorMessage.textContent).toContain("The host left the lobby");
  });

  test("clears an active game session when reconnect authentication fails", () => {
    app.setState({ reconnecting: true, currentPhase: "game" });
    sessionStorage.setItem("backyardBridgeSession", "saved");
    app.handleWebSocketMessage({
      data: JSON.stringify({ type: "se", msg: "Unable to restore this game session." })
    });
    expect(app.getState().currentPhase).toBe("home");
    expect(app.elements.homeLobbyActions.style.display).toBe("grid");
    expect(sessionStorage.getItem("backyardBridgeSession")).toBeNull();
  });

  test("retries a game restore while the previous socket is still closing", async () => {
    vi.useFakeTimers();
    app.setState({
      reconnecting: true, reconnectRequested: true,
      currentPhase: "game", reconnectDeadline: 0, ws: null
    });
    app.handleWebSocketMessage({
      data: JSON.stringify({ type: "se", msg: "This player is already connected." })
    });
    expect(app.getState().currentPhase).toBe("game");
    await vi.advanceTimersByTimeAsync(1000);
    expect(FakeWebSocket.instances.at(-1).url).toContain("/ws/game/");
  });

  test("returns a kicked player to the main page with an explanation", () => {
    app.setLobbyUI(false);
    app.handleWebSocketMessage({
      data: JSON.stringify({ type: "kfl", msg: "The host removed you from the lobby." })
    });
    expect(app.elements.homeLobbyActions.style.display).toBe("grid");
    expect(app.elements.errorMessage.innerHTML).toBe("The host removed you from the lobby.");
    expect(app.getState().isHost).toBe(false);
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
    app.elements.playerContainer.style.display = "flex";
    const playableCard = document.createElement("div");
    app.setCardAction(playableCard, vi.fn(), "Play card");
    app.elements.playerHand.append(playableCard);
    const animationClone = document.createElement("div");
    animationClone.className = "card";
    document.body.append(animationClone);
    app.leaveLobby();
    expect(socket.sent[0].type).toBe("cll");
    expect(app.elements.homeLobbyActions.style.display).toBe("grid");
    expect(app.elements.playerContainer.style.display).toBe("none");
    expect(app.elements.playerHand.children).toHaveLength(0);
    expect(playableCard.onclick).toBeNull();
    expect(document.body.contains(animationClone)).toBe(false);
    const player = document.createElement("div");
    player.id = "gone";
    document.body.append(player);
    app.leaveGame("gone");
    expect(document.getElementById("gone")).toBeNull();
    app.leaveGame("missing");
    app.removeHighlighted("#missing-card");
  });

  test("renders users, opponent hands and scores", () => {
    app.setState({ isHost: true });
    app.updateUsers(
      [
        { user_id: "me", user_name: "Me" },
        { user_id: "other", user_name: "Other" }
      ],
      true,
      2
    );
    expect(app.elements.usersList.children).toHaveLength(2);
    expect(app.elements.startButton.disabled).toBe(false);
    expect(app.elements.addBotButton.disabled).toBe(true);

    app.updateUsers(
      Array.from({ length: 4 }, (_, index) => ({
        user_id: `player-${index}`,
        user_name: index ? `Player ${index}` : "Alex Bot",
        is_bot: index === 0
      })),
      undefined,
      4
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
    expect(window.location.href).toBe("http://localhost:8000/");
  });
});
