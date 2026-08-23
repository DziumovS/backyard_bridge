import { vi } from "vitest";

document.body.innerHTML = `
  <header><button id="rulesButton"></button></header>
  <div id="nameAndScores"><span id="ws-id"></span><form id="nameForm"></form></div>
  <span id="pS"></span><input id="nameInput"><button id="changeName"></button>
  <button id="createLobbyButton"></button><input id="lobbyInput"><button id="joinLobbyButton"></button>
  <button id="startButton"></button><button id="leaveButton"></button>
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
