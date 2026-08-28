let ws;
let lobbyId;
let userId = Date.now().toString().slice(-9);
let userName = userId;
let sessionToken = "";
let isHost = false;
let currentPlayer = "";
let eventHandlersAdded = false;
let game_over = false;
let errorTimeout;
let lobbyBrowserErrorTimeout;
let loadingTimeout;
let loadingFailureTimeout;
let scoresRateAnimationTimeout;
let lastScoresRate = "x1";
let cardImagesReady = Promise.resolve();
let lobbyCapabilities = new Set();
let lobbyMaxPlayers = 4;
let selectedLobbySize = 4;
let lobbyIsPublic = false;
let lobbyPlayerCount = 0;
let lobbyRefreshInterval;
let selectedLobbyKey = "";
let privateJoinPending = false;
let currentPhase = "home";
let reconnectDeadline = 0;
let reconnectTimer;
let reconnectCountdownInterval;
let reconnecting = false;
let reconnectRequested = false;
let automaticReconnectAttempts = 0;
let leavingGame = false;
const reconnectWindowMs = 60000;
const automaticReconnectMaxAttempts = 5;
const automaticReconnectDelayMs = 1000;
const storedSessionKey = "backyardBridgeSession";
const orderedGameEventTypes = new Set([
    "gd", "wt", "ft", "iib", "go", "godc", "apc", "adc", "gr",
]);


class GameEventQueue {
    constructor() {
        this.pending = [];
        this.running = false;
        this.generation = 0;
    }

    enqueue(task) {
        return new Promise((resolve, reject) => {
            const item = { task, resolve, reject };
            if (this.running) {
                this.pending.push(item);
            } else {
                this.run(item, this.generation);
            }
        });
    }

    run(item, generation) {
        this.running = true;
        let result;
        try {
            result = item.task();
        } catch (error) {
            this.finish(item, generation, error);
            return;
        }

        if (result && typeof result.then === "function") {
            result.then(
                value => this.finish(item, generation, null, value),
                error => this.finish(item, generation, error),
            );
        } else {
            this.finish(item, generation, null, result);
        }
    }

    finish(item, generation, error, value) {
        if (error) item.reject(error);
        else item.resolve(value);

        if (generation !== this.generation) return;
        const next = this.pending.shift();
        if (next) this.run(next, generation);
        else this.running = false;
    }

    reset() {
        this.generation += 1;
        this.running = false;
        this.pending.splice(0).forEach(item => item.resolve());
    }
}


const gameEventQueue = new GameEventQueue();


const elements = {
    wsId: document.querySelector("#ws-id"),
    pS: document.querySelector("#pS"),
    nameForm: document.getElementById("nameForm"),
    createLobbyButton: document.getElementById("createLobbyButton"),
    createLobbyWidget: document.getElementById("create-lobby-widget"),
    closeCreateLobbyWidget: document.getElementById("closeCreateLobbyWidget"),
    createPublicLobbyButton: document.getElementById("createPublicLobbyButton"),
    createPrivateLobbyButton: document.getElementById("createPrivateLobbyButton"),
    playerCountButtons: document.querySelectorAll("[data-player-count]"),
    homeLobbyActions: document.getElementById("homeLobbyActions"),
    joinPublicLobbyButton: document.getElementById("joinPublicLobbyButton"),
    quickPlayButton: document.getElementById("quickPlayButton"),
    lobbyBrowserWidget: document.getElementById("lobby-browser-widget"),
    closeLobbyBrowserWidget: document.getElementById("closeLobbyBrowserWidget"),
    availableLobbiesList: document.getElementById("availableLobbiesList"),
    availableLobbiesEmpty: document.getElementById("availableLobbiesEmpty"),
    refreshLobbiesButton: document.getElementById("refreshLobbiesButton"),
    lobbyBrowserError: document.getElementById("lobbyBrowserError"),
    joinLobbyInput: document.getElementById("lobbyInput"),
    joinLobbyButton: document.getElementById("joinLobbyButton"),
    startButton: document.getElementById("startButton"),
    addBotButton: document.getElementById("addBotButton"),
    leaveLobbyButton: document.getElementById("leaveButton"),
    errorMessage: document.getElementById("errorMessage"),
    lobbyControls: document.getElementById("lobbyControls"),
    lobbyMessage: document.getElementById("lobbyMessage"),
    usersHeader: document.getElementById("usersHeader"),
    usersList: document.getElementById("usersList"),
    currentCards: document.getElementById("currentCards"),
    nameInput: document.getElementById("nameInput"),
    playerHand: document.getElementById("playerHand"),
    turnText: document.getElementById("turnText"),
    cardsLeft: document.getElementById("cardsLeft"),
    rightCard: document.getElementById("rightCard"),
    leftCard: document.getElementById("leftCard"),
    jackWidget: document.getElementById("jack-widget"),
    rulesWidget: document.getElementById("rules-widget"),
    scoresRate: document.getElementById("scoresRate"),
    nameAndScores: document.getElementById("nameAndScores"),
    playerScores: document.getElementById("scores"),
    gameOverWidget: document.getElementById("game-over-widget"),
    playerContainer: document.getElementById("playerContainer"),
    welcomeMessage: document.getElementById("welcomeMessage"),
    rulesButton: document.getElementById("rulesButton"),
    continueGameButton: document.getElementById("continueGameButton"),
    leaveGameButton: document.getElementById("leaveGameButton"),
    leaveActiveGameButton: document.getElementById("leaveActiveGameButton"),
    reconnectGameWidget: document.getElementById("reconnect-game-widget"),
    reconnectGameTimer: document.getElementById("reconnectGameTimer"),
    reconnectGameButton: document.getElementById("reconnectGameButton"),
    leaveDisconnectedGameButton: document.getElementById("leaveDisconnectedGameButton"),
    leaveGameConfirmWidget: document.getElementById("leave-game-confirm-widget"),
    confirmLeaveGameButton: document.getElementById("confirmLeaveGameButton"),
    continueActiveGameButton: document.getElementById("continueActiveGameButton"),
};


elements.wsId.textContent = userName;
elements.nameInput.placeholder = userName;


elements.joinLobbyInput.addEventListener("input", function () {
    elements.joinLobbyButton.disabled = !/^[0-9a-f]{6}$/i.test(elements.joinLobbyInput.value.trim());
});

elements.nameInput.addEventListener("input", function () {
    const inputText = elements.nameInput.value.trim();
    document.getElementById("changeName").disabled = inputText.length === 0;
});

elements.nameForm.addEventListener("submit", updateUsername);
elements.rulesButton.addEventListener("click", showRulesWidget);
elements.joinLobbyButton.addEventListener("click", joinLobby);
elements.joinPublicLobbyButton.addEventListener("click", openLobbyBrowser);
elements.quickPlayButton.addEventListener("click", quickPlay);
elements.createLobbyButton.addEventListener("click", openCreateLobbyWidget);
elements.closeCreateLobbyWidget.addEventListener("click", closeCreateLobbyWidget);
elements.createPublicLobbyButton.addEventListener("click", () => createLobby(true));
elements.createPrivateLobbyButton.addEventListener("click", () => createLobby(false));
elements.playerCountButtons.forEach(button => {
    button.addEventListener("click", () => selectLobbySize(Number(button.dataset.playerCount)));
});
elements.createLobbyWidget.addEventListener("click", event => {
    if (event.target === elements.createLobbyWidget) closeCreateLobbyWidget();
});
elements.closeLobbyBrowserWidget.addEventListener("click", closeLobbyBrowser);
elements.lobbyBrowserWidget.addEventListener("click", event => {
    if (event.target === elements.lobbyBrowserWidget) closeLobbyBrowser();
});
elements.refreshLobbiesButton.addEventListener("click", refreshAvailableLobbies);
elements.startButton.addEventListener("click", startGame);
elements.addBotButton.addEventListener("click", addBot);
elements.leaveLobbyButton.addEventListener("click", leaveLobby);
elements.continueGameButton.addEventListener("click", startNewGame);
elements.leaveGameButton.addEventListener("click", leaveGameFromWidget);
elements.leaveActiveGameButton.addEventListener("click", showLeaveGameConfirmation);
elements.reconnectGameButton.addEventListener("click", reconnectGame);
elements.leaveDisconnectedGameButton.addEventListener("click", leaveDisconnectedGame);
elements.confirmLeaveGameButton.addEventListener("click", confirmLeaveActiveGame);
elements.continueActiveGameButton.addEventListener("click", closeLeaveGameConfirmation);
elements.leaveGameConfirmWidget.addEventListener("click", event => {
    if (event.target === elements.leaveGameConfirmWidget) closeLeaveGameConfirmation();
});
document.addEventListener("keydown", event => {
    if (event.key === "Escape") {
        closeCreateLobbyWidget();
        closeLobbyBrowser();
        closeLeaveGameConfirmation();
    }
});

window.addEventListener("pagehide", () => {
    if (currentPhase === "game" && !leavingGame) {
        storeSession();
    }
});

document.addEventListener("visibilitychange", () => {
    if (document.visibilityState !== "visible") return;
    resumeGameConnection();
});

window.addEventListener("pageshow", event => {
    if (event.persisted) resumeGameConnection();
});

restoreStoredSession();


function getWsBaseUrl(path) {
    const protocol = window.location.protocol === "https:" ? "wss" : "ws";
    return `${protocol}://${window.location.host}${path}`;
}


function getHttpBaseUrl(path = "") {
    return `${window.location.origin}${path}`;
}


function storeSession() {
    if (currentPhase !== "game" || !sessionToken || !lobbyId) return;
    sessionStorage.setItem(storedSessionKey, JSON.stringify({
        userId, userName, sessionToken, lobbyId, isHost, phase: currentPhase, reconnectDeadline,
    }));
}


function clearStoredSession() {
    sessionStorage.removeItem(storedSessionKey);
    currentPhase = "home";
    reconnectDeadline = 0;
    reconnecting = false;
    reconnectRequested = false;
    automaticReconnectAttempts = 0;
    leavingGame = false;
    clearTimeout(reconnectTimer);
    clearInterval(reconnectCountdownInterval);
}


function readStoredSession() {
    try {
        return JSON.parse(sessionStorage.getItem(storedSessionKey));
    } catch {
        sessionStorage.removeItem(storedSessionKey);
        return null;
    }
}


function scheduleReconnect(phase) {
    if (phase !== "game" || currentPhase !== "game" || !reconnectRequested) return;
    if (document.visibilityState !== "visible") {
        pauseAutomaticReconnect();
        return;
    }
    if (!reconnectDeadline) reconnectDeadline = Date.now() + reconnectWindowMs;
    if (Date.now() >= reconnectDeadline) {
        clearStoredSession();
        returnToMainPage();
        void showError("Couldn't reconnect within 60 seconds", 5);
        return;
    }
    if (automaticReconnectAttempts >= automaticReconnectMaxAttempts) {
        showReconnectGameWidget();
        return;
    }
    reconnecting = true;
    clearTimeout(reconnectTimer);
    reconnectTimer = setTimeout(() => {
        automaticReconnectAttempts += 1;
        connectGameWebSocket(true);
    }, automaticReconnectDelayMs);
}


function pauseAutomaticReconnect() {
    clearTimeout(reconnectTimer);
    reconnectRequested = false;
    reconnecting = false;
    automaticReconnectAttempts = 0;
    markGameDisconnected();
}


function beginAutomaticReconnect() {
    if (document.visibilityState !== "visible"
        || currentPhase !== "game" || leavingGame || reconnectRequested) return false;
    markGameDisconnected();
    reconnectRequested = true;
    reconnecting = true;
    automaticReconnectAttempts = 1;
    closeReconnectGameWidget();
    setGameUI();
    connectGameWebSocket(true);
    return true;
}


function resumeGameConnection() {
    if (document.visibilityState !== "visible"
        || currentPhase !== "game" || leavingGame || reconnectRequested) return false;
    const socketIsUnavailable = !ws
        || ws.readyState === 2
        || ws.readyState === 3;
    return socketIsUnavailable ? beginAutomaticReconnect() : false;
}


function restoreStoredSession() {
    const stored = readStoredSession();
    if (!stored?.userId || !stored?.sessionToken || !stored?.lobbyId) return false;
    ({ userId, userName, sessionToken, lobbyId, isHost } = stored);
    if (stored.phase !== "game") {
        clearStoredSession();
        return false;
    }
    currentPhase = "game";
    reconnectDeadline = Number(stored.reconnectDeadline) || Date.now() + reconnectWindowMs;
    elements.wsId.textContent = userName;
    elements.nameInput.placeholder = userName;
    reconnecting = false;
    reconnectRequested = false;
    automaticReconnectAttempts = 0;
    showReconnectGameWidget();
    return true;
}


function markGameDisconnected() {
    if (!reconnectDeadline) reconnectDeadline = Date.now() + reconnectWindowMs;
    storeSession();
}


function updateReconnectCountdown() {
    const seconds = Math.max(0, Math.ceil((reconnectDeadline - Date.now()) / 1000));
    elements.reconnectGameTimer.textContent = String(seconds);
    if (seconds === 0) {
        elements.reconnectGameWidget.style.display = "none";
        clearStoredSession();
        returnToMainPage();
        void showError("Reconnect time expired", 4);
    }
}


function syncReconnectDeadline() {
    const statusSocket = new WebSocket(getWsBaseUrl(`/ws/game/${lobbyId}/${userId}`));
    statusSocket.onopen = () => statusSocket.send(JSON.stringify({
        type: "auth", token: sessionToken, intent: "status",
    }));
    statusSocket.onmessage = event => {
        const data = JSON.parse(event.data);
        if (data.type === "se") {
            closeReconnectGameWidget();
            clearStoredSession();
            returnToMainPage();
            void showError("Game unavailable", 4);
            return;
        }
        if (data.type !== "rs" || !Number.isFinite(data.seconds)) return;
        reconnectDeadline = Date.now() + Math.max(0, data.seconds * 1000);
        storeSession();
        updateReconnectCountdown();
    };
}


function showReconnectGameWidget() {
    markGameDisconnected();
    clearTimeout(reconnectTimer);
    reconnectRequested = false;
    reconnecting = false;
    automaticReconnectAttempts = 0;
    finishLoadingAnimation();
    returnToMainPage(true);
    elements.reconnectGameWidget.style.display = "flex";
    updateReconnectCountdown();
    clearInterval(reconnectCountdownInterval);
    reconnectCountdownInterval = setInterval(updateReconnectCountdown, 250);
    syncReconnectDeadline();
}


function closeReconnectGameWidget() {
    elements.reconnectGameWidget.style.display = "none";
    clearInterval(reconnectCountdownInterval);
    reconnectCountdownInterval = undefined;
}


function reconnectGame() {
    if (Date.now() >= reconnectDeadline) {
        updateReconnectCountdown();
        return;
    }
    reconnectRequested = true;
    reconnecting = true;
    automaticReconnectAttempts = 1;
    closeReconnectGameWidget();
    setGameUI();
    connectGameWebSocket(true);
}


function leaveDisconnectedGame() {
    const leaveSocket = new WebSocket(getWsBaseUrl(`/ws/game/${lobbyId}/${userId}`));
    leaveSocket.onopen = () => leaveSocket.send(JSON.stringify({
        type: "auth", token: sessionToken, intent: "leave",
    }));
    leavingGame = true;
    closeReconnectGameWidget();
    clearStoredSession();
    returnToMainPage();
}


function leaveGameFromWidget() {
    closeGameOverWidget();
    performLeaveActiveGame();
    return showError("Thanks for playing! Bye!", 0.3);
}


function updateUsername(event) {
    event.preventDefault();

    const newName = elements.nameInput.value.trim();

    if (newName) {
        userName = newName;
        elements.wsId.textContent = userName;
        elements.nameForm.style.display = "none";
        elements.wsId.style.display = "block";
    }
}


function setLobbyUI(isHostView) {
    elements.wsId.style.display = "block";
    elements.welcomeMessage.style.display = "none";
    elements.homeLobbyActions.style.display = "none";
    elements.nameForm.style.display = "none";
    elements.lobbyControls.style.display = "block";
    elements.usersHeader.classList.add("lobby-users-header");
    elements.leaveLobbyButton.style.display = "inline";
    elements.startButton.style.display = isHostView ? "block" : "none";
    elements.addBotButton.style.display = isHostView ? "block" : "none";
    elements.addBotButton.disabled = false;
    isHost = isHostView;
}


function openCreateLobbyWidget() {
    selectLobbySize(4);
    elements.createLobbyWidget.style.display = "flex";
}


function closeCreateLobbyWidget() {
    elements.createLobbyWidget.style.display = "none";
}


function selectLobbySize(size) {
    selectedLobbySize = size;
    elements.playerCountButtons.forEach(button => {
        const selected = Number(button.dataset.playerCount) === size;
        button.classList.toggle("selected", selected);
        button.setAttribute("aria-pressed", String(selected));
    });
}


function createLobby(isPublic = false) {
    closeCreateLobbyWidget();
    startLoadingAnimation(0.3, 0.8);
    initializeWebSocket("crl", {
        user_name: userName,
        is_public: isPublic,
        max_players: selectedLobbySize,
    });
}


function addBot() {
    if (isHost && !elements.addBotButton.disabled) {
        ws.send(JSON.stringify({ type: "ab" }));
        setTimeout(() => elements.addBotButton.blur(), 0);
    }
}


function preloadCardImages() {
    return fetch('/get_cards')
        .then(response => response.json())
        .then(cardUrls => Promise.all(
            cardUrls.map(url => {
                const img = new Image();
                img.src = url;
                return typeof img.decode === "function"
                    ? img.decode().catch(() => undefined)
                    : Promise.resolve();
            })
        ))
        .catch(() => undefined);
}


async function joinLobby() {
    const inputLobbyId = elements.joinLobbyInput.value.trim().toLowerCase();
    if (!inputLobbyId) return;

    elements.joinLobbyInput.value = "";
    elements.joinLobbyButton.disabled = true;
    elements.joinLobbyInput.blur();
    elements.joinLobbyButton.blur();
    await joinLobbyById(inputLobbyId, true);
}


async function joinLobbyById(inputLobbyId, privateOnly = false) {
    privateJoinPending = privateOnly;
    clearTimeout(lobbyBrowserErrorTimeout);
    elements.lobbyBrowserError.textContent = "";
    startLoadingAnimation(0.4, 0.9);
    initializeWebSocket("jl", {
        user_name: userName,
        lobby_id: inputLobbyId,
        private_only: privateOnly,
    });
}


function openLobbyBrowser() {
    selectedLobbyKey = "";
    clearTimeout(lobbyBrowserErrorTimeout);
    elements.lobbyBrowserError.textContent = "";
    elements.joinLobbyInput.value = "";
    elements.joinLobbyButton.disabled = true;
    elements.lobbyBrowserWidget.style.display = "flex";
    void refreshAvailableLobbies();
    startLobbyAutoRefresh();
}


function closeLobbyBrowser() {
    clearTimeout(lobbyBrowserErrorTimeout);
    elements.lobbyBrowserWidget.style.display = "none";
    elements.lobbyBrowserError.textContent = "";
    stopLobbyAutoRefresh();
}


function renderLobbyDetails(data) {
    lobbyId = data.lobby_id;
    lobbyMaxPlayers = data.max_players || 4;
    lobbyIsPublic = data.is_public;
    lobbyPlayerCount = data.users?.length || 1;
    elements.lobbyMessage.replaceChildren();

    const name = document.createElement("p");
    name.className = "lobby-summary-name";
    name.textContent = data.lobby_name;
    elements.lobbyMessage.appendChild(name);

    const meta = document.createElement("p");
    meta.className = "lobby-summary-meta";
    meta.id = "lobbySummaryMeta";
    elements.lobbyMessage.appendChild(meta);
    updateLobbySummaryCapacity(lobbyPlayerCount);

    if (!data.is_public) {
        const codeButton = document.createElement("button");
        const lobbyCode = lobbyId;
        codeButton.type = "button";
        codeButton.className = "lobby-code-button";
        codeButton.textContent = `Invite code: ${lobbyCode} · tap to copy`;
        codeButton.addEventListener("click", () => {
            navigator.clipboard.writeText(lobbyCode);
            codeButton.textContent = `Code copied: ${lobbyCode}`;
            setTimeout(() => {
                codeButton.textContent = `Invite code: ${lobbyCode} · tap to copy`;
            }, 2000);
        });
        elements.lobbyMessage.appendChild(codeButton);
    }
}


function updateLobbySummaryCapacity(playerCount) {
    lobbyPlayerCount = playerCount;
    const meta = document.getElementById("lobbySummaryMeta");
    if (meta) {
        meta.textContent = `${lobbyIsPublic ? "Public" : "Private"} lobby · ${playerCount}/${lobbyMaxPlayers} players`;
    }
}


function renderAvailableLobbies(lobbies) {
    elements.availableLobbiesList.replaceChildren();
    elements.availableLobbiesEmpty.hidden = lobbies.length > 0;
    if (!lobbies.length) {
        return;
    }

    lobbies.forEach(lobby => {
        const lobbyKey = lobby.lobby_id || `private:${lobby.name}`;
        const row = document.createElement("div");
        row.className = "available-lobby-row";
        row.classList.toggle("selected", selectedLobbyKey === lobbyKey);
        row.tabIndex = 0;
        row.setAttribute("role", "button");
        row.setAttribute("aria-label", `Select ${lobby.name}`);

        const details = document.createElement("div");
        details.className = "available-lobby-details";
        const name = document.createElement("p");
        name.className = "available-lobby-name";
        const suffix = "'s lobby";
        const hostName = lobby.name.endsWith(suffix) ? lobby.name.slice(0, -suffix.length) : lobby.name;
        const host = document.createElement("strong");
        host.textContent = hostName;
        name.append(host, document.createTextNode(lobby.name.slice(hostName.length)));
        const capacity = document.createElement("p");
        capacity.className = "available-lobby-capacity";
        capacity.textContent = `${lobby.players}/${lobby.max_players}`;
        details.append(name, capacity);

        const actions = document.createElement("span");
        actions.className = "available-lobby-actions";
        if (lobby.is_private) {
            const lock = document.createElement("span");
            lock.className = "private-lobby-lock";
            lock.textContent = "🔒";
            lock.setAttribute("role", "img");
            lock.setAttribute("aria-label", "Private lobby");
            actions.appendChild(lock);
        }
        const joinButton = document.createElement("button");
        joinButton.type = "button";
        joinButton.className = "available-lobby-join-button";
        joinButton.textContent = "Join";
        joinButton.setAttribute("aria-label", `Join ${lobby.name}`);
        joinButton.addEventListener("click", event => {
            event.stopPropagation();
            if (lobby.is_private) {
                elements.joinLobbyInput.focus();
            } else {
                void joinLobbyById(lobby.lobby_id);
            }
        });
        actions.appendChild(joinButton);
        row.addEventListener("click", () => {
            selectedLobbyKey = lobbyKey;
            elements.availableLobbiesList.querySelectorAll(".available-lobby-row")
                .forEach(item => item.classList.remove("selected"));
            row.classList.add("selected");
        });
        row.addEventListener("keydown", event => {
            if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                row.click();
            }
        });
        row.append(details, actions);
        elements.availableLobbiesList.appendChild(row);
    });
}


async function refreshAvailableLobbies() {
    elements.refreshLobbiesButton.disabled = true;
    try {
        const response = await fetch("/lobbies");
        renderAvailableLobbies(await response.json());
    } catch {
        renderAvailableLobbies([]);
    } finally {
        elements.refreshLobbiesButton.disabled = false;
        setTimeout(() => elements.refreshLobbiesButton.blur(), 0);
    }
}


function startLobbyAutoRefresh() {
    stopLobbyAutoRefresh();
    lobbyRefreshInterval = setInterval(() => {
        if (elements.lobbyBrowserWidget.style.display === "flex") {
            void refreshAvailableLobbies();
        }
    }, 4000);
}


function stopLobbyAutoRefresh() {
    clearInterval(lobbyRefreshInterval);
    lobbyRefreshInterval = undefined;
}


async function quickPlay() {
    elements.quickPlayButton.disabled = true;
    try {
        const response = await fetch("/quick_play");
        const lobby = await response.json();
        if (lobby) {
            await joinLobbyById(lobby.lobby_id);
        } else {
            await showError("No public lobbies are available yet.", 2);
        }
    } catch {
        await showError("Couldn't find a public lobby. Try again.", 2);
    } finally {
        elements.quickPlayButton.disabled = false;
    }
}


function initializeWebSocket(type, message, isReconnect = false) {
    if (ws) {
        ws.onclose = null;
        ws.close(1000);
    }

    gameEventQueue.reset();
    ws = new WebSocket(getWsBaseUrl(`/ws/lobby/${userId}`));

    ws.onopen = () => ws.send(JSON.stringify({type, ...message}));

    ws.onmessage = handleWebSocketMessage;
    ws.onclose = () => {
        if (currentPhase === "lobby") {
            clearStoredSession();
            returnToMainPage();
        }
    };
    reconnecting = isReconnect;
    cardImagesReady = preloadCardImages();
}


function handleWebSocketMessage(event) {
    const data = JSON.parse(event.data);

    if (orderedGameEventTypes.has(data.type)) {
        const pending = gameEventQueue.enqueue(() => processWebSocketMessage(data));
        pending.catch(error => console.error("WebSocket message failed", error));
        return pending;
    }
    return Promise.resolve(processWebSocketMessage(data));
}


function processWebSocketMessage(data) {

    switch (data.type) {
        case "sid":
            userId = data.user_id;
            sessionToken = data.session_token;
            lobbyCapabilities = new Set(data.capabilities || []);
            reconnectDeadline = 0;
            break;

        case "lcr":
            currentPhase = "lobby";
            reconnecting = false;
            setLobbyUI(true);
            renderLobbyDetails(data);
            break;

        case "jdl":
            currentPhase = "lobby";
            reconnecting = false;
            privateJoinPending = false;
            elements.lobbyBrowserWidget.style.display = "none";
            stopLobbyAutoRefresh();
            setLobbyUI(data.is_host === true);
            renderLobbyDetails(data);
            updateUsers(data.users, false, data.max_players);
            finishLoadingAnimation();
            break;

        case "uu":
            updateUsers(data.users, data.is_host, data.max_players);
            finishLoadingAnimation();
            break;

        case "sg":
            startGame();
            break;

        case "lcl":
            clearStoredSession();
            returnToMainPage();
            if (data.msg) showError(data.msg, 5);
            break;

        case "kfl":
            clearStoredSession();
            returnToMainPage();
            showError(data.msg, 3);
            break;

        case "tsb":
            toggleStartButton(data.enable);
            break;

        case "gd":
            isHost = data.is_host;
            closeReconnectGameWidget();
            reconnectRequested = false;
            automaticReconnectAttempts = 0;
            ensureGamePlayers(data.players);
            updateGameScores(data.players);
            reconnecting = false;
            reconnectDeadline = 0;
            storeSession();
            checkScoresRate(data.scores_rate, data.scores_rate_changed === true);
            updatePlayerHand(
                data.hand,
                data.current_player && !data.automatic_action_pending,
                data.playable_cards,
                "current",
            );
            updateOpponentData(data.players_hands);
            updateCurrentCards(
                data.current_card,
                data.deck_len,
                data.chosen_suit,
                data.player_options,
                data.automatic_action_pending,
            );
            finishLoadingAnimation();
            break;

        case "wt":
            whoseTurn(data.msg, data.current_player);
            break;

        case "ft":
            firstTurn(data.current_card);
            break;

        case "nep":
            clearStoredSession();
            backToHomePage(data.msg, 3);
            break;

        case "se":
            finishLoadingAnimation();
            if (reconnecting) {
                if (currentPhase === "game" && data.msg === "This player is already connected.") {
                    scheduleReconnect("game");
                    break;
                }
                clearStoredSession();
                returnToMainPage();
            }
            if (privateJoinPending) {
                showLobbyBrowserError("The private lobby was not found");
                elements.lobbyBrowserWidget.style.display = "flex";
                privateJoinPending = false;
            } else {
                showError(data.msg, 2);
            }
            break;

        case "iib":
            showError(data.msg, 4);
            isItBridge(data.current_card);
            break;

        case "go":
            removeHighlighted("#leftCard img");
            showError(data.error_msg, 5).then(() => {
                showGameOverWidget(data.widget_msg, data.players_scores, data.player_scores, data.is_host);
            });
            break;

        case "godc":
            game_over = true;
            return drawCard();

        case "lg":
            leaveGame(data.player_id);
            break;

        case "apc":
            return playCard(data.card, "opponent");

        case "adc":
            change_player(data.current_player);
            return animateDrawCard(
                data.current_player === userId ? "current" : "opponent",
                data.current_player,
            );

        case "gr":
            reset_game(data.players_scores, data.player_scores);
            break;
    }
}


function showError(message, seconds) {
    clearTimeout(errorTimeout);

    elements.errorMessage.innerHTML = message;
    elements.errorMessage.style.display = "block";

    return new Promise((resolve) => {
        errorTimeout = setTimeout(() => {
            elements.errorMessage.innerHTML = "";
            elements.errorMessage.style.display = "none";
            resolve();
        }, seconds * 1000);
    });
}


function showLobbyBrowserError(message) {
    clearTimeout(lobbyBrowserErrorTimeout);
    elements.lobbyBrowserError.textContent = message;
    lobbyBrowserErrorTimeout = setTimeout(() => {
        elements.lobbyBrowserError.textContent = "";
    }, 3000);
}


function startGame() {
    if (isHost) {
        ws.send(JSON.stringify({ type: "sg" }));
    }

    ws.onclose = null;
    currentPhase = "game";
    reconnectDeadline = 0;
    automaticReconnectAttempts = 0;
    leavingGame = false;
    storeSession();
    connectGameWebSocket(false);
    setGameUI();
}


function connectGameWebSocket(isReconnect = false) {
    if (ws) ws.onclose = null;

    gameEventQueue.reset();
    ws = new WebSocket(getWsBaseUrl(`/ws/game/${lobbyId}/${userId}`));

    startLoadingAnimation(1, 1.5);

    ws.onopen = async () => {
        ws.send(JSON.stringify({ type: "auth", token: sessionToken }));
        if (!isReconnect) {
            await cardImagesReady;
            ws.send(JSON.stringify({ type: "gs" }));
        }
    };

    ws.onmessage = handleWebSocketMessage;
    ws.onclose = () => {
        if (currentPhase === "game" && !leavingGame) {
            if (document.visibilityState !== "visible") {
                pauseAutomaticReconnect();
                return;
            }
            if (reconnectRequested) {
                scheduleReconnect("game");
                return;
            }
            beginAutomaticReconnect();
        }
    };
    reconnecting = isReconnect;
}


function setGameUI() {
    elements.lobbyControls.style.display = "none";
    elements.welcomeMessage.style.display = "none";
    elements.homeLobbyActions.style.display = "none";
    elements.nameForm.style.display = "none";
    elements.wsId.style.display = "block";
    elements.leaveActiveGameButton.style.display = "block";
    elements.currentCards.style.display = "flex";
    elements.playerContainer.style.display = "flex";
    elements.nameAndScores.style.flexDirection = "row";
    resetScoresRate();
    elements.playerScores.style.display = "block";

    elements.usersHeader.style.fontSize = "12px";
    elements.usersHeader.classList.remove("lobby-users-header");
    elements.usersList.style.fontSize = "12px";
    elements.usersList.style.flexDirection = "row";
    document.querySelectorAll(".kick-player-button").forEach(button => button.remove());
    document.querySelectorAll(".host-label").forEach(label => label.remove());

    const currentPlayerContainer = document.getElementById(userId);
    if (currentPlayerContainer) currentPlayerContainer.style.display = "none";

    const opponentScores = document.querySelectorAll('.opponentScores');
    opponentScores.forEach(scores => {
        scores.style.display = "flex";
        scores.style.justifyContent = "center";
    })

    const opponentHands = document.querySelectorAll('.opponent_hand');
        opponentHands.forEach(hand => {
            hand.style.display = "flex";
        });
}


function ensureGamePlayers(players) {
    const expectedIds = players.map(player => player.user_id).sort();
    const renderedIds = Array.from(elements.usersList.children).map(element => element.id).sort();
    const isComplete = expectedIds.length === renderedIds.length
        && expectedIds.every((playerId, index) => playerId === renderedIds[index]);

    if (!isComplete) {
        updateUsers(players, false);
    }
    setGameUI();
}


function leaveGame(playerId) {
    const playerContainer = document.getElementById(playerId);
    if (playerContainer) {
        playerContainer.remove();
    }
}


function leaveLobby() {
    ws.onclose = null;
    ws.send(JSON.stringify({ type: "cll", lobby_id: lobbyId }));
    clearStoredSession();
    returnToMainPage();
}


function showLeaveGameConfirmation() {
    if (currentPhase !== "game" || !ws) return;
    elements.leaveGameConfirmWidget.style.display = "flex";
}


function closeLeaveGameConfirmation() {
    elements.leaveGameConfirmWidget.style.display = "none";
}


function confirmLeaveActiveGame() {
    closeLeaveGameConfirmation();
    performLeaveActiveGame();
}


function performLeaveActiveGame() {
    if (currentPhase !== "game" || !ws) return;
    leavingGame = true;
    ws.onclose = null;
    ws.send(JSON.stringify({ type: "lg" }));
    clearStoredSession();
    returnToMainPage();
}


function returnToMainPage(preserveGameSession = false) {
    elements.lobbyControls.style.display = "none";
    elements.welcomeMessage.style.display = "block";
    elements.homeLobbyActions.style.display = "grid";
    elements.nameForm.style.display = "none";
    elements.lobbyBrowserWidget.style.display = "none";
    elements.reconnectGameWidget.style.display = "none";
    elements.leaveGameConfirmWidget.style.display = "none";
    stopLobbyAutoRefresh();
    elements.joinLobbyInput.value ="";
    elements.joinLobbyButton.style.display = "inline";
    elements.joinLobbyButton.disabled = true;
    elements.leaveLobbyButton.style.display = "none";
    elements.addBotButton.style.display = "none";
    elements.leaveActiveGameButton.style.display = "none";
    elements.errorMessage.style.display = "none";
    elements.currentCards.style.display = "none";
    elements.playerContainer.style.display = "none";
    Array.from(elements.playerHand.children).forEach(clearCardAction);
    elements.playerHand.replaceChildren();
    elements.turnText.textContent = "";
    document.querySelectorAll("body > .card").forEach(card => card.remove());
    clearCardAction(elements.leftCard);
    clearCardAction(elements.rightCard);
    removeHighlighted("#leftCard img");
    removeHighlighted("#rightCard img");
    elements.usersHeader.style.display = "none";
    elements.usersHeader.classList.remove("lobby-users-header");
    elements.usersList.style.display = "none";
    if (!preserveGameSession) {
        isHost = false;
        currentPhase = "home";
    }
}


function updateUsers(users, isHostView, maxPlayers = lobbyMaxPlayers) {
    lobbyMaxPlayers = maxPlayers;
    elements.usersList.style.display = "flex";
    elements.usersList.innerHTML ="";
    elements.usersHeader.style.display = "block";
    const canManageLobby = (isHost || isHostView === true) && lobbyCapabilities.has("kick_users");

    users.forEach(user => {
        const opponentContainer = document.createElement("div");
        opponentContainer.className = user.user_id;
        opponentContainer.classList.add("player-entry");
        opponentContainer.id = user.user_id;

        const playerNameRow = document.createElement("div");
        playerNameRow.className = "player-name-row";

        const userElement = document.createElement("p");
        userElement.textContent = user.user_name;
        playerNameRow.appendChild(userElement);

        if (user.is_host) {
            const hostLabel = document.createElement("span");
            hostLabel.className = "host-label";
            hostLabel.textContent = "HOST";
            playerNameRow.appendChild(hostLabel);
        }

        if (canManageLobby && user.user_id !== userId) {
            const kickButton = document.createElement("button");
            kickButton.type = "button";
            kickButton.className = "kick-player-button";
            kickButton.textContent = "×";
            kickButton.title = `Remove ${user.user_name}`;
            kickButton.setAttribute("aria-label", `Remove ${user.user_name} from lobby`);
            kickButton.addEventListener("click", () => kickUser(user.user_id));
            playerNameRow.appendChild(kickButton);
        }

        opponentContainer.appendChild(playerNameRow);
        elements.usersList.appendChild(opponentContainer);

        const opponentHand = document.createElement("div");
        opponentHand.className = "opponent_hand";
        opponentHand.id = `${user.user_id}_hand`;

        const opponentScores = document.createElement("div");
        opponentScores.className = "opponentScores";
        opponentScores.id = "opponentScores";

        const scoresName = document.createElement("p");
        scoresName.innerHTML = "Score:";
        scoresName.style.marginRight = "3px";

        const oS = document.createElement("span");
        oS.id = `${user.user_id}_oS`;
        oS.style.fontWeight = "bold";
        oS.textContent = "0";

        opponentScores.appendChild(scoresName);
        opponentScores.appendChild(oS);

        opponentContainer.appendChild(opponentScores);

        opponentContainer.appendChild(opponentHand);

    });

    updateLobbySummaryCapacity(users.length);
    if (isHost || isHostView === true) {
        toggleStartButton(users.length >= 2);
        toggleAddBotButton(users.length < lobbyMaxPlayers);
    }
}


function kickUser(targetId) {
    if (isHost && targetId !== userId) {
        ws.send(JSON.stringify({ type: "ku", user_id: targetId }));
    }
}


function updateOpponentData(playersHands) {
    playersHands.forEach(player => {
        const opponentHand = document.getElementById(`${player.player_id}_hand`);
        opponentHand.innerHTML ="";

        const containerWidth = 100;
        const cardWidth = 20;
        const gap = 1;

        const totalCardsWidth = player.hand_len * (cardWidth + gap) - gap;

        let overlap = 0;
        let startLeftPosition = 0;

        if (totalCardsWidth > containerWidth) {
            overlap = (totalCardsWidth - containerWidth) / (player.hand_len - 1);
            overlap = Math.min(overlap, cardWidth - gap);
        } else {
            startLeftPosition = (containerWidth - totalCardsWidth) / 2;
        }

        for (let i = 0; i < player.hand_len; i++) {
            const cardDiv = document.createElement("div");
            cardDiv.classList.add("opponent_card");
            cardDiv.style.left = `${startLeftPosition + i * (cardWidth - overlap) + gap * i}px`;

            const cardImage = document.createElement("img");
            cardImage.src = "/static/cards/opponent_card.png";
            cardImage.alt = "opponent_card";

            cardDiv.appendChild(cardImage);
            opponentHand.appendChild(cardDiv);
        }
    });
}


function updateGameScores(players) {
    players.forEach(player => {
        if (typeof player.scores !== "number") return;

        if (player.user_id === userId) {
            elements.pS.textContent = player.scores;
        }

        const opponentScore = document.getElementById(`${player.user_id}_oS`);
        if (opponentScore) opponentScore.textContent = player.scores;
    });
}


function toggleStartButton(enable) {
    elements.startButton.disabled = !enable;
}


function toggleAddBotButton(enable) {
    elements.addBotButton.disabled = !enable;
}


function activateWithKeyboard(event) {
    if ((event.key === "Enter" || event.key === " ") && typeof event.currentTarget.onclick === "function") {
        event.preventDefault();
        event.currentTarget.onclick();
    }
}


function setCardAction(element, action, label) {
    element.onclick = action;
    element.onkeydown = activateWithKeyboard;
    element.style.cursor = "pointer";
    element.tabIndex = 0;
    element.setAttribute("role", "button");
    element.setAttribute("aria-disabled", "false");
    element.setAttribute("aria-label", label);
}


function clearCardAction(element) {
    element.onclick = null;
    element.onkeydown = null;
    element.style.cursor = "default";
    element.tabIndex = -1;
    element.setAttribute("aria-disabled", "true");
    element.removeAttribute("aria-label");
}


function updatePlayerHand(hand, player, playableCards, whose) {
    elements.playerHand.innerHTML = "";

    const containerWidth = elements.playerHand.offsetWidth;
    const cardWidth = 90;
    const gap = 5;
    const sideMargin = 15;

    const totalCardsWidth = hand.length * (cardWidth + gap) - gap;
    let startLeftPosition = sideMargin;


    let overlap = 0;
    if (totalCardsWidth > containerWidth - 2 * sideMargin) {
        overlap = (totalCardsWidth - (containerWidth - 2 * sideMargin)) / (hand.length - 1);
        overlap = Math.min(overlap, cardWidth - gap);
    } else {
        startLeftPosition += (containerWidth - totalCardsWidth - 2 * sideMargin + gap) / 2;
    }

    hand.forEach((card, index) => {
        const cardDiv = document.createElement("div");
        cardDiv.classList.add("card");
        cardDiv.style.left = `${startLeftPosition + index * (cardWidth - overlap) + gap * index}px`;

        const isPlayable = playableCards.some(playableCard =>
            playableCard.rank === card.rank && playableCard.suit === card.suit
        );

        if (player && isPlayable) {
            cardDiv.classList.add("highlighted-card-img");
            cardDiv.style.bottom = "50px";
            setCardAction(cardDiv, () => playCard(card, whose), `Play ${card.rank} ${card.suit}`);
        }

        const cardImage = document.createElement("img");
        const cardName = `${card.rank}_${card.suit}`;
        cardImage.src = `/static/cards/${cardName}.png`;
        cardImage.alt = cardName;

        cardDiv.appendChild(cardImage);
        elements.playerHand.appendChild(cardDiv);
    });
}


function whoseTurn(message, current_player) {
    elements.turnText.textContent = message;

    change_player(current_player);

    elements.turnText.classList.add("wave-effect");
    setTimeout(() => {
        elements.turnText.classList.remove("wave-effect");
    }, 5000);
}


function change_player(whoIsCurrent) {
    if (whoIsCurrent) {
        currentPlayer = whoIsCurrent;
    }
}


function updateCurrentCards(currentCard, deckLen, chosenSuit, playerOptions, automaticActionPending = false) {
    elements.cardsLeft.textContent = deckLen;

    const oldImage = elements.rightCard.querySelector("img");
    if (oldImage) oldImage.remove();

    const newRightCardImage = document.createElement("img");
    if (chosenSuit) {
        newRightCardImage.src = `/static/cards/${chosenSuit.suit}.png`;
        newRightCardImage.alt = chosenSuit.suit;
    } else {
        newRightCardImage.src = `/static/cards/${currentCard.rank}_${currentCard.suit}.png`;
        newRightCardImage.alt = `${currentCard.rank}_${currentCard.suit}`;
    }

    elements.rightCard.appendChild(newRightCardImage);
    if (automaticActionPending) {
        setDefaultDrawCard();
        setDefaultSkipTurn();
    } else {
        checkCurrentPlayerOptions(playerOptions);
    }
}


async function playCard(card, whose) {
    if (whose === "current") {
        const cardDiv = [...elements.playerHand.children].find(cardElement => {
            const img = cardElement.querySelector('img');
            return img.alt === `${card.rank}_${card.suit}`;
        });

        await animatePlayedCard(cardDiv);
    } else {
        const playerTopContainer = document.getElementById(currentPlayer);
        const cardImg = playerTopContainer.querySelector(".opponent_card img");

        await animatePlayedCard(cardImg);
    }

    if (whose === "current") {
        updateRightCard(card);
        if (card.rank === "J") {
            showJackWidget(card);
        } else {
            ws.send(JSON.stringify({ type: "pc", card: card, chosen_suit: null }));
        }
    }
}


function updateRightCard(card) {
    const oldImage = elements.rightCard.querySelector("img");
    if (oldImage) oldImage.remove();

    const newCardImage = document.createElement("img");
    newCardImage.src = `/static/cards/${card.rank}_${card.suit}.png`;
    newCardImage.alt = `${card.rank}_${card.suit}`;
    elements.rightCard.appendChild(newCardImage);
}


function waitForCardTransition(cardElement, fallbackMs = 450) {
    return new Promise((resolve) => {
        let fallbackTimeout;
        const finish = () => {
            clearTimeout(fallbackTimeout);
            cardElement.removeEventListener("transitionend", finish);
            cardElement.removeEventListener("transitioncancel", finish);
            resolve();
        };

        cardElement.addEventListener("transitionend", finish);
        cardElement.addEventListener("transitioncancel", finish);
        fallbackTimeout = setTimeout(finish, fallbackMs);
    });
}


async function animatePlayedCard(cardElement) {
    const startRect = cardElement.getBoundingClientRect();
    const endRect = elements.rightCard.getBoundingClientRect();

    const cardClone = cardElement.cloneNode(true);
    document.body.appendChild(cardClone);

    cardClone.style.position = "absolute";
    cardClone.style.left = `${startRect.left}px`;
    cardClone.style.top = `${startRect.top}px`;
    cardClone.style.width = `${startRect.width}px`;
    cardClone.style.height = `${startRect.height}px`;
    cardClone.style.transition = "all 0.35s ease";

    setTimeout(() => {
        cardElement.style.display = "none";
        cardClone.style.left = `${endRect.left}px`;
        cardClone.style.top = `${endRect.top}px`;
        cardClone.style.width = "90px";
        cardClone.style.height = "135px";
    }, 30);

    await waitForCardTransition(cardClone);
    if (document.body.contains(cardClone)) {
        cardClone.remove();
    }
}


async function drawCard() {
    await animateDrawCard("current");

    if (game_over) {
        ws.send(JSON.stringify({ type: "go" }));
        game_over = false;
    } else {
        ws.send(JSON.stringify({ type: "dc" }));
    }

}


async function animateDrawCard(whose, drawingPlayer = currentPlayer) {
    const startRect = elements.leftCard.getBoundingClientRect();
    const cardClone = elements.leftCard.querySelector("img").cloneNode(true);

    document.body.appendChild(cardClone);

    cardClone.style.position = "absolute";
    cardClone.style.left = `${startRect.left}px`;
    cardClone.style.top = `${startRect.top}px`;
    cardClone.style.width = `${startRect.width}px`;
    cardClone.style.height = `${startRect.height}px`;
    cardClone.style.transition = "all 0.35s ease";

    setTimeout(() => {
        let endRect;
        let centerX, centerY;

        if (whose === "current") {
            endRect = elements.playerHand.getBoundingClientRect();
            centerX = endRect.left + (endRect.width / 2) - (startRect.width / 2);
            centerY = endRect.bottom - startRect.height - 10;
            cardClone.style.width = `${startRect.width}px`;
            cardClone.style.height = `${startRect.height}px`;
        } else {
            const opponentContainer = document.getElementById(`${drawingPlayer}_hand`);
            const cardImg = opponentContainer.querySelector(".opponent_card");
            endRect = cardImg.getBoundingClientRect();
            centerX = endRect.left;
            centerY = endRect.top;
            cardClone.style.width = "20px";
            cardClone.style.height = "30px";
        }

        cardClone.style.left = `${centerX}px`;
        cardClone.style.top = `${centerY}px`;
    }, 30);

    await waitForCardTransition(cardClone);
    if (document.body.contains(cardClone)) {
        cardClone.remove();
    }
}


function skip_turn() {
    if (currentPlayer === userId) {
        ws.send(JSON.stringify({ type: "st" }));

        elements.errorMessage.style.display = "none";
    }
}


function colorSkipTurn() {
    const rightCardImage = document.querySelector("#rightCard img");
    if (currentPlayer === userId) {
        rightCardImage.classList.add("highlighted-card-img");
    }
}


function colorDrawCard() {
    const leftCardImage = document.querySelector("#leftCard img");
    if (currentPlayer === userId) {
        leftCardImage.classList.add("highlighted-card-img");
    }
}


function firstTurn(card) {
    if (currentPlayer === userId) {
        if (card.rank === "J") {
            showJackWidget(card)
        } else {
            ws.send(JSON.stringify({ type: "pc", card: card, chosen_suit: null }));
        }
    }
}


function showJackWidget(card) {
    elements.jackWidget.style.display = "block";

    const playerCards = elements.playerHand.querySelectorAll(".card");
    playerCards.forEach(cardDiv => {
        clearCardAction(cardDiv);
        cardDiv.style.bottom = "10px";
        cardDiv.classList.remove("highlighted-card-img");
    });

    const suits = ["♠", "♥", "♦", "♣"];
    const cells = document.querySelectorAll(".jack-widget-grid div");

    cells.forEach((cell, index) => {
        let newCell = cell.cloneNode(true);
        cell.replaceWith(newCell);

        setCardAction(newCell, function() {
            const selectedSuit = suits[index];

            elements.jackWidget.style.display = "none";

            ws.send(JSON.stringify({ type: "pc", card: card, chosen_suit: selectedSuit }));
        }, `Choose ${suits[index]} suit`);
    });
}


function checkCurrentPlayerOptions(playerOptions) {
    setDefaultDrawCard();
    setDefaultSkipTurn();

    if (currentPlayer === userId) {
        if (!playerOptions.must_draw && !playerOptions.must_skip) {
            if (playerOptions.can_draw) {
                colorDrawCard();
                setCardAction(elements.leftCard, drawCard, "Draw a card");
            }
            if (playerOptions.can_skip) {
                colorSkipTurn();
                setCardAction(elements.rightCard, skip_turn, "Skip turn");
            }
        }
    }
}


function setDefaultDrawCard() {
    if (currentPlayer === userId) {
        removeHighlighted("#leftCard img");
    }
    clearCardAction(elements.leftCard);
}


function setDefaultSkipTurn() {
    if (currentPlayer === userId) {
        removeHighlighted("#rightCard img");
    }
    clearCardAction(elements.rightCard);
}


function removeHighlighted(img) {
    const object = document.querySelector(img);
    if (object) object.classList.remove("highlighted-card-img");
}


async function showRulesWidget() {
    const response = await fetch("/rules");
    const data = await response.json();

    document.querySelector(".rules-column p").innerHTML = data.rules;

    elements.rulesWidget.style.display = "flex";

    if (!eventHandlersAdded) {
        document.getElementById("closeRulesWidget").addEventListener("click", closeRulesWidget);
        document.getElementById("rules-widget").addEventListener("click", function(event) {
            if (event.target === elements.rulesWidget) {
                closeRulesWidget();
            }
        });
        document.addEventListener("keydown", function(event) {
            if (event.key === "Escape") {
                closeRulesWidget();
            }
        });

        eventHandlersAdded = true;
    }
}


function closeRulesWidget() {
    elements.rulesWidget.style.display = "none";
    document.querySelector(".rules-column p").textContent ="";
}


async function backToHomePage(message, seconds) {
    returnToMainPage();
    await showError(message, seconds);
}


function checkScoresRate(scoresRate, scoresRateChanged = false) {
    if (scoresRate === lastScoresRate) return;

    lastScoresRate = scoresRate;
    elements.scoresRate.textContent = scoresRate;
    if (!scoresRateChanged) return;

    elements.scoresRate.classList.add("scores-rate-change");
    clearTimeout(scoresRateAnimationTimeout);
    scoresRateAnimationTimeout = setTimeout(() => {
        elements.scoresRate.classList.remove("scores-rate-change");
    }, 5000);
}


function resetScoresRate() {
    clearTimeout(scoresRateAnimationTimeout);
    scoresRateAnimationTimeout = undefined;
    lastScoresRate = "x1";
    elements.scoresRate.textContent = lastScoresRate;
    elements.scoresRate.classList.remove("scores-rate-change");
}


function startNewGame() {
    if (isHost) {
        ws.send(JSON.stringify({ type: "rg" }));
    }
}


function reset_game(playersScores, playerScores) {
    closeGameOverWidget();
    elements.pS.textContent = playerScores;
    resetScoresRate();

    playersScores.forEach(player => {
        const oS = document.getElementById(`${player.player_id}_oS`);
        oS.textContent = player.scores;
    })
}


function isItBridge(card) {
    setTimeout(() => {
        elements.leftCard.querySelector("img").src = "/static/cards/bridge.png";
        elements.leftCard.querySelector("img").alt = "bridge";
        colorDrawCard();

        setCardAction(elements.leftCard, () => {
            ws.send(JSON.stringify({ type: "go" }));
            resetCardState(card);
        }, "Finish bridge");

        elements.rightCard.querySelector("img").src = "/static/cards/continue.png";
        elements.rightCard.querySelector("img").alt = "continue";

        setCardAction(elements.rightCard, () => {
            skip_turn();
            resetCardState(card);
        }, "Continue game");
    }, 50);
}


function resetCardState(card) {
    elements.leftCard.querySelector("img").src = "/static/cards/closed_card.png";
    elements.leftCard.querySelector("img").alt = "closed_card";
    setDefaultDrawCard();

    elements.rightCard.querySelector("img").src = `/static/cards/${card.rank}_${card.suit}.png`;
    elements.rightCard.querySelector("img").alt = `${card.rank}_${card.suit}`;
    setDefaultSkipTurn();
}


function showGameOverWidget(results, playersScores, playerScores, hostCanRestart) {
    playersScores.forEach(player => {
        const oS = document.getElementById(`${player.player_id}_oS`);
        oS.textContent = player.scores;
    })

    elements.pS.textContent = playerScores;

    document.querySelector(".results-column p").innerHTML = results;
    document.getElementById("continueGameButton").style.display = hostCanRestart ? "inline" : "none";
    elements.gameOverWidget.style.display = "flex";
}


function closeGameOverWidget() {
    elements.gameOverWidget.style.display = "none";
    document.querySelector(".results-column p").textContent ="";
}


function startLoadingAnimation() {
    const overlay = document.getElementById("overlay");
    const progress = document.querySelector(".progress");

    clearTimeout(loadingTimeout);
    overlay.style.display = "flex";

    progress.style.width = "0%";
    progress.style.transition = "width 8s cubic-bezier(0.1, 0.7, 0.2, 1)";
    loadingTimeout = setTimeout(() => {
        progress.style.width = "100%";
    }, 50);
    loadingFailureTimeout = setTimeout(() => {
        finishLoadingAnimation();
        showError("Connection timed out. Try again.", 5);
    }, 20000);
}

function finishLoadingAnimation() {
    const overlay = document.getElementById("overlay");
    const progress = document.querySelector(".progress");

    clearTimeout(loadingTimeout);
    clearTimeout(loadingFailureTimeout);
    progress.style.transition = "none";
    progress.style.width = "100%";
    overlay.style.display = "none";
}


/* v8 ignore next -- production-only guard for the test API */
if (globalThis.__BACKYARD_BRIDGE_TEST__) {
    globalThis.__backyardBridge = {
        GameEventQueue,
        elements,
        getWsBaseUrl,
        getHttpBaseUrl,
        leaveGameFromWidget,
        updateUsername,
        setLobbyUI,
        openCreateLobbyWidget,
        closeCreateLobbyWidget,
        selectLobbySize,
        createLobby,
        addBot,
        preloadCardImages,
        joinLobby,
        joinLobbyById,
        openLobbyBrowser,
        closeLobbyBrowser,
        renderLobbyDetails,
        renderAvailableLobbies,
        refreshAvailableLobbies,
        startLobbyAutoRefresh,
        stopLobbyAutoRefresh,
        quickPlay,
        initializeWebSocket,
        handleWebSocketMessage,
        showError,
        showLobbyBrowserError,
        startGame,
        connectGameWebSocket,
        setGameUI,
        ensureGamePlayers,
        leaveGame,
        leaveLobby,
        returnToMainPage,
        updateUsers,
        kickUser,
        updateOpponentData,
        updateGameScores,
        toggleStartButton,
        toggleAddBotButton,
        updatePlayerHand,
        whoseTurn,
        change_player,
        updateCurrentCards,
        playCard,
        updateRightCard,
        waitForCardTransition,
        animatePlayedCard,
        drawCard,
        animateDrawCard,
        skip_turn,
        colorSkipTurn,
        colorDrawCard,
        firstTurn,
        showJackWidget,
        checkCurrentPlayerOptions,
        setDefaultDrawCard,
        setDefaultSkipTurn,
        activateWithKeyboard,
        setCardAction,
        clearCardAction,
        removeHighlighted,
        showRulesWidget,
        closeRulesWidget,
        backToHomePage,
        checkScoresRate,
        resetScoresRate,
        startNewGame,
        reset_game,
        isItBridge,
        resetCardState,
        showGameOverWidget,
        closeGameOverWidget,
        startLoadingAnimation,
        finishLoadingAnimation,
        storeSession,
        clearStoredSession,
        readStoredSession,
        scheduleReconnect,
        pauseAutomaticReconnect,
        beginAutomaticReconnect,
        resumeGameConnection,
        restoreStoredSession,
        markGameDisconnected,
        updateReconnectCountdown,
        syncReconnectDeadline,
        showReconnectGameWidget,
        closeReconnectGameWidget,
        reconnectGame,
        leaveDisconnectedGame,
        showLeaveGameConfirmation,
        closeLeaveGameConfirmation,
        confirmLeaveActiveGame,
        performLeaveActiveGame,
        updateLobbySummaryCapacity,
        getState: () => ({
            ws,
            lobbyId,
            userId,
            userName,
            sessionToken,
            isHost,
            currentPlayer,
            game_over,
            lobbyMaxPlayers,
            selectedLobbySize,
            currentPhase,
            reconnectDeadline,
            reconnecting,
            reconnectRequested,
            automaticReconnectAttempts,
            leavingGame,
            lobbyIsPublic,
            lobbyPlayerCount,
            lobbyCapabilities: [...lobbyCapabilities],
        }),
        setState: (state) => {
            if ("ws" in state) ws = state.ws;
            if ("lobbyId" in state) lobbyId = state.lobbyId;
            if ("userId" in state) userId = state.userId;
            if ("userName" in state) userName = state.userName;
            if ("sessionToken" in state) sessionToken = state.sessionToken;
            if ("isHost" in state) isHost = state.isHost;
            if ("currentPlayer" in state) currentPlayer = state.currentPlayer;
            if ("game_over" in state) game_over = state.game_over;
            if ("lobbyMaxPlayers" in state) lobbyMaxPlayers = state.lobbyMaxPlayers;
            if ("selectedLobbySize" in state) selectedLobbySize = state.selectedLobbySize;
            if ("currentPhase" in state) currentPhase = state.currentPhase;
            if ("reconnectDeadline" in state) reconnectDeadline = state.reconnectDeadline;
            if ("reconnecting" in state) reconnecting = state.reconnecting;
            if ("reconnectRequested" in state) reconnectRequested = state.reconnectRequested;
            if ("automaticReconnectAttempts" in state) {
                automaticReconnectAttempts = state.automaticReconnectAttempts;
            }
            if ("leavingGame" in state) leavingGame = state.leavingGame;
            if ("lobbyIsPublic" in state) lobbyIsPublic = state.lobbyIsPublic;
            if ("lobbyPlayerCount" in state) lobbyPlayerCount = state.lobbyPlayerCount;
            if ("lobbyCapabilities" in state) lobbyCapabilities = new Set(state.lobbyCapabilities);
            if ("cardImagesReady" in state) cardImagesReady = state.cardImagesReady;
        }
    };
}
