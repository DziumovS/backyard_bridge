import { vi } from "vitest";

document.body.innerHTML = `
  <header><button id="leaveActiveGameButton"></button><button id="rulesButton"></button></header>
  <div id="nameAndScores"><span id="ws-id"></span><form id="nameForm"></form></div>
  <span id="pS"></span><input id="nameInput"><button id="changeName"></button>
  <div id="homeLobbyActions"><button id="createLobbyButton"></button><button id="quickPlayButton"></button>
    <button id="joinPublicLobbyButton"></button></div>
  <div id="create-lobby-widget"><button id="closeCreateLobbyWidget"></button>
    <button id="createPublicLobbyButton"></button><button id="createPrivateLobbyButton"></button>
    <button data-player-count="2"></button><button data-player-count="3"></button>
    <button data-player-count="4" class="selected"></button>
  </div>
  <div id="lobby-browser-widget"><button id="closeLobbyBrowserWidget"></button>
    <p id="availableLobbiesEmpty">No lobbies are available yet</p>
    <div id="lobbyBrowserError"></div><input id="lobbyInput">
    <button id="joinLobbyButton"></button><button id="refreshLobbiesButton"></button>
    <div id="availableLobbiesList"></div></div>
  <div id="reconnect-game-widget"><span id="reconnectGameTimer"></span>
    <button id="reconnectGameButton"></button><button id="leaveDisconnectedGameButton"></button></div>
  <div id="leave-game-confirm-widget"><button id="confirmLeaveGameButton"></button>
    <button id="continueActiveGameButton"></button></div>
  <button id="startButton"></button><button id="addBotButton"></button><button id="leaveButton"></button>
  <div id="errorMessage"></div><div id="lobbyControls"></div><div id="lobbyMessage"></div>
  <div id="usersHeader"></div><div id="usersList"></div><div id="currentCards"></div>
  <div id="playerHand"></div><div id="turnText"></div><div id="cardsLeft"></div>
  <div id="rightCard"><img src="/right.png"></div>
  <div id="leftCard"><img src="/static/cards/closed_card.png"></div>
  <div id="jack-widget"><div class="jack-widget-grid"><div>♠</div><div>♥</div><div>♦</div><div>♣</div></div></div>
  <div id="rules-widget"><span id="closeRulesWidget"></span><div class="rules-column"><p></p></div></div>
  <div id="scoresRate"></div><div id="scores"></div>
  <div id="game-over-widget"><div class="results-column"><p></p></div></div>
  <div id="playerContainer"></div><div id="welcomeMessage"></div>
  <button id="continueGameButton"></button>
  <button id="leaveGameButton"></button>
  <div id="overlay"><div class="progress"></div></div>
`;

Object.defineProperty(window, "location", {
  configurable: true,
  value: {
    hostname: "localhost",
    host: "localhost:8000",
    origin: "http://localhost:8000",
    protocol: "http:",
    href: "http://localhost:8000/"
  }
});

Object.defineProperty(navigator, "clipboard", {
  configurable: true,
  value: { writeText: vi.fn(() => Promise.resolve()) }
});

globalThis.__BACKYARD_BRIDGE_TEST__ = true;
