let ws;
let lobbyId;
let userId = Date.now().toString().slice(-9);
let userName = userId;
let isHost = false;
let currentPlayer = "";
let eventHandlersAdded = false;
let game_over = false;
let errorTimeout;


const elements = {
    wsId: document.querySelector("#ws-id"),
    pS: document.querySelector("#pS"),
    nameForm: document.getElementById("nameForm"),
    createLobbyButton: document.getElementById("createLobbyButton"),
    joinLobbyInput: document.getElementById("lobbyInput"),
    joinLobbyButton: document.getElementById("joinLobbyButton"),
    startButton: document.getElementById("startButton"),
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
};


elements.wsId.textContent = userName;
elements.nameInput.placeholder = userName;


elements.joinLobbyInput.addEventListener("input", function () {
    elements.joinLobbyButton.disabled = !elements.joinLobbyInput.value.trim();
});

elements.nameInput.addEventListener("input", function () {
    const inputText = elements.nameInput.value.trim();
    document.getElementById("changeName").disabled = inputText.length === 0;
});


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
    elements.createLobbyButton.style.display = "none";
    elements.nameForm.style.display = "none";
    elements.joinLobbyInput.style.display = "none";
    elements.joinLobbyButton.style.display = "none";
    elements.lobbyControls.style.display = "block";
    elements.leaveLobbyButton.style.display = "inline";
    elements.startButton.style.display = isHostView ? "block" : "none";
    isHost = isHostView;
}


function createLobby() {
    startLoadingAnimation(0.3, 0.8);
    setLobbyUI(true);
    initializeWebSocket("crl", { user_name: userName });
}


function preloadCardImages() {
    fetch('/get_cards')
        .then(response => response.json())
        .then(cardUrls => {
            cardUrls.forEach(url => {
                const img = new Image();
                img.src = url;
            });
        })
}


async function joinLobby() {
    const inputLobbyId = elements.joinLobbyInput.value.trim();
    if (!inputLobbyId) return;

    const response = await fetch(`/check_lobby/${inputLobbyId}`);
    const data = await response.json();

    if (data.exists) {
        startLoadingAnimation(0.4, 0.9);
        setLobbyUI(false);
        initializeWebSocket("jl", { user_name: userName, lobby_id: inputLobbyId });
    } else {
        await showError(data.msg, 2);
    }
}


function setAndCopyLobbyId(lobby_id, msg) {
    lobbyId = lobby_id;
    const pre_click = `<br><span class="small-text">(click to copy ID to clipboard)</span>`;
    const post_click = `<br><span class="small-text" style="color: #ffa500" id="copyInfo">ID copied!</span>`;
    elements.lobbyMessage.innerHTML = msg + pre_click;

    elements.lobbyMessage.removeEventListener("click", copyToClipboard);
    elements.lobbyMessage.addEventListener("click", copyToClipboard);

    function copyToClipboard() {
        navigator.clipboard.writeText(lobby_id);

        if (!document.getElementById("copyInfo")) {
            elements.lobbyMessage.innerHTML = msg + post_click;
        }

        setTimeout(() => {
            const copyInfo = document.getElementById("copyInfo");
            if (copyInfo) {
                copyInfo.remove();
            }
            elements.lobbyMessage.innerHTML = msg + pre_click;
        }, 2000);
    }
}


function initializeWebSocket(type, message) {
    if (ws) {
        ws.close(1000);
    }

    ws = new WebSocket(`wss://${window.location.hostname}/ws/lobby/${userId}`);  // https
    // ws = new WebSocket(`ws://localhost:8000/ws/lobby/${userId}`);  // http

    ws.onopen = () => ws.send(JSON.stringify({type, ...message}));

    ws.onmessage = handleWebSocketMessage;
    preloadCardImages();
}


function handleWebSocketMessage(event) {
    const data = JSON.parse(event.data);

    switch (data.type) {
        case "lcr":
            setAndCopyLobbyId(data.lobby_id, data.msg);
            break;

        case "jdl":
            setAndCopyLobbyId(data.lobby_id, data.msg);
            updateUsers(data.users, false);
            break;

        case "uu":
            updateUsers(data.users, data.is_host);
            break;

        case "sg":
            startGame();
            break;

        case "lcl":
            returnToMainPage();
            break;

        case "tsb":
            toggleStartButton(data.enable);
            break;

        case "gd":
            checkScoresRate(data.scores_rate);
            updatePlayerHand(data.hand, data.current_player, data.playable_cards, "current");
            updateOpponentData(data.players_hands);
            updateCurrentCards(data.current_card, data.deck_len, data.chosen_suit, data.player_options);
            break;

        case "wt":
            whoseTurn(data.msg, data.current_player);
            break;

        case "ft":
            firstTurn(data.current_card);
            break;

        case "nep":
            backToHomePage(data.msg, 3);
            break;

        case "se":
            showError(data.msg, 2);
            break;

        case "iib":
            showError(data.msg, 4);
            isItBridge(data.current_card);
            break;

        case "go":
            removeHighlighted("#leftCard img");
            showError(data.error_msg, 5).then(() => {
                showGameOverWidget(data.widget_msg, data.players_scores, data.player_scores);
            });
            break;

        case "godc":
            game_over = true;
            drawCard();
            break;

        case "lg":
            leaveGame(data.player_id);
            break;

        case "apc":
            playCard(data.card, "opponent");
            break;

        case "adc":
            change_player(data.current_player);
            animateDrawCard("opponent");
            break;

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


function startGame() {
    if (isHost) {
        ws.send(JSON.stringify({ type: "sg" }));
    }

    ws = new WebSocket(`wss://${window.location.hostname}/ws/game/${lobbyId}/${userId}`);  // https
    // ws = new WebSocket(`ws://localhost:8000/ws/game/${lobbyId}/${userId}`);  // http

    startLoadingAnimation(1, 1.5);

    ws.onopen = () => ws.send(JSON.stringify({ type: "gs" }));

    ws.onmessage = function (event) {
        handleWebSocketMessage(event);
    };

    setGameUI();
}


function setGameUI() {
    elements.lobbyControls.style.display = "none";
    elements.currentCards.style.display = "flex";
    elements.playerContainer.style.display = "flex";
    elements.nameAndScores.style.flexDirection = "row";
    elements.pS.innerHTML = "0";
    elements.scoresRate.innerHTML = "x1";
    elements.playerScores.style.display = "block";

    elements.usersHeader.style.fontSize = "12px";
    elements.usersList.style.fontSize = "12px";
    elements.usersList.style.flexDirection = "row";

    const currentPlayerContainer = document.getElementById(userId);
    currentPlayerContainer.style.display = "none";

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


function leaveGame(playerId) {
    const playerContainer = document.getElementById(playerId);
    if (playerContainer) {
        playerContainer.remove();
    }
}


function leaveLobby() {
    ws.send(JSON.stringify({ type: "cll", lobby_id: lobbyId }));

    returnToMainPage();
}


function returnToMainPage() {
    elements.lobbyControls.style.display = "none";
    elements.welcomeMessage.style.display = "block";
    elements.createLobbyButton.style.display = "inline";
    elements.nameForm.style.display = "none";
    elements.joinLobbyInput.style.display = "inline";
    elements.joinLobbyInput.value ="";
    elements.joinLobbyButton.style.display = "inline";
    elements.joinLobbyButton.disabled = true;
    elements.leaveLobbyButton.style.display = "none";
    elements.errorMessage.style.display = "none";
    elements.currentCards.style.display = "none";
    elements.usersHeader.style.display = "none";
    elements.usersList.style.display = "none";
}


function updateUsers(users, isHost) {
    elements.usersList.style.display = "flex";
    elements.usersList.innerHTML ="";
    elements.usersHeader.style.display = "block";

    users.forEach(user => {
        const opponentContainer = document.createElement("div");
        opponentContainer.className = user.user_id;
        opponentContainer.id = user.user_id;

        const userElement = document.createElement("p");
        userElement.textContent = user.user_name;
        opponentContainer.appendChild(userElement);
        elements.usersList.appendChild(opponentContainer);

        const opponentHand = document.createElement("div");
        opponentHand.className = "opponent_hand";
        opponentHand.id = `${user.user_id}_hand`;

        const opponentScores = document.createElement("div");
        opponentScores.className = "opponentScores";
        opponentScores.id = "opponentScores";

        const scoresName = document.createElement("p");
        scoresName.innerHTML = "Scores:";
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

    if (isHost) toggleStartButton(true);
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


function toggleStartButton(enable) {
    elements.startButton.disabled = !enable;
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
            cardDiv.onclick = () => playCard(card, whose);
            cardDiv.style.cursor = "pointer";
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


function updateCurrentCards(currentCard, deckLen, chosenSuit, playerOptions) {
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
    setTimeout(() => {
        checkCurrentPlayerOptions(playerOptions);
    }, 50);
}


async function playCard(card, whose) {
    if (whose === "current") {
        ws.send(JSON.stringify({ type: "smm", card: card }));

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

    updateRightCard(card);

    if (whose === "current") {
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

    await new Promise((resolve) => {
        setTimeout(() => {
            if (document.body.contains(cardClone)) {
                cardClone.remove();
            }
            resolve();
        }, 370);
    });
}


async function drawCard() {
    ws.send(JSON.stringify({ type: "smm" }));

    await animateDrawCard("current");

    if (game_over) {
        ws.send(JSON.stringify({ type: "go" }));
        game_over = false;
    } else {
        ws.send(JSON.stringify({ type: "dc" }));
    }

}


async function animateDrawCard(whose) {
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
            const opponentContainer = document.getElementById(`${currentPlayer}_hand`);
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

    await new Promise((resolve) => {
        setTimeout(() => {
            if (document.body.contains(cardClone)) {
                cardClone.remove();
            }
            resolve();
        }, 370);
    });
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
        cardDiv.onclick = null;
        cardDiv.style.cursor = "default";
        cardDiv.style.bottom = "10px";
        cardDiv.classList.remove("highlighted-card-img");
    });

    const suits = ["♠", "♥", "♦", "♣"];
    const cells = document.querySelectorAll(".jack-widget-grid div");

    cells.forEach((cell, index) => {
        let newCell = cell.cloneNode(true);
        cell.replaceWith(newCell);

        newCell.addEventListener("click", function() {
            const selectedSuit = suits[index];

            elements.jackWidget.style.display = "none";

            ws.send(JSON.stringify({ type: "pc", card: card, chosen_suit: selectedSuit }));
        });
    });
}


function checkCurrentPlayerOptions(playerOptions) {
    setDefaultDrawCard();
    setDefaultSkipTurn();

    if (currentPlayer === userId) {
        if (playerOptions.must_draw) {
            colorDrawCard();
            elements.leftCard.style.cursor = "pointer";
            elements.leftCard.onclick = drawCard;
        } else if (playerOptions.must_skip) {
            colorSkipTurn();
            elements.rightCard.style.cursor = "pointer";
            elements.rightCard.onclick = skip_turn;
        } else {
            if (playerOptions.can_draw) {
                colorDrawCard();
                elements.leftCard.style.cursor = "pointer";
                elements.leftCard.onclick = drawCard;
            }
            if (playerOptions.can_skip) {
                colorSkipTurn();
                elements.rightCard.style.cursor = "pointer";
                elements.rightCard.onclick = skip_turn;
            }
        }
    }
}


function setDefaultDrawCard() {
    if (currentPlayer === userId) {
        removeHighlighted("#leftCard img");
    }
    elements.leftCard.style.cursor = "default";
    elements.leftCard.onclick = null;
}


function setDefaultSkipTurn() {
    if (currentPlayer === userId) {
        removeHighlighted("#rightCard img");
    }
    elements.rightCard.style.cursor = "default";
    elements.rightCard.onclick = null;
}


function removeHighlighted(img) {
    const object = document.querySelector(img);
    object.classList.remove("highlighted-card-img");
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
    await showError(message, seconds);
    window.location.href = `${window.location.origin}`;  // https
    // window.location.href = "http://localhost:8000";  // http
}


function checkScoresRate(scoresRate) {
    if (scoresRate !== elements.scoresRate.innerHTML) {
        elements.scoresRate.innerHTML = scoresRate;
        elements.scoresRate.classList.add("wave-effect");

        setTimeout(() => {
            elements.scoresRate.classList.remove("wave-effect");
        }, 5000);
    }
}


function startNewGame() {
    ws.send(JSON.stringify({ type: "rg" }));
}


function reset_game(playersScores, playerScores) {
    closeGameOverWidget();
    elements.pS.textContent = playerScores;
    elements.scoresRate.innerHTML = "x1";

    playersScores.forEach(player => {
        const oS = document.getElementById(`${player.player_id}_oS`);
        oS.textContent = player.scores;
    })
}


function isItBridge(card) {
    setTimeout(() => {
        elements.leftCard.querySelector("img").src = "/static/cards/bridge.png";
        elements.leftCard.querySelector("img").alt = "bridge";
        elements.leftCard.style.cursor = "pointer";
        colorDrawCard();

        elements.leftCard.onclick = () => {
            ws.send(JSON.stringify({ type: "go" }));
            resetCardState(card);
        };

        elements.rightCard.querySelector("img").src = "/static/cards/continue.png";
        elements.rightCard.querySelector("img").alt = "continue";

        elements.rightCard.onclick = () => {
            skip_turn();
            resetCardState(card);
        };
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


function showGameOverWidget(results, playersScores, playerScores) {
    playersScores.forEach(player => {
        const oS = document.getElementById(`${player.player_id}_oS`);
        oS.textContent = player.scores;
    })

    elements.pS.textContent = playerScores;

    document.querySelector(".results-column p").innerHTML = results;
    elements.gameOverWidget.style.display = "flex";
}


function closeGameOverWidget() {
    elements.gameOverWidget.style.display = "none";
    document.querySelector(".results-column p").textContent ="";
}


function startLoadingAnimation(progress_sec, timer_sec) {
            const overlay = document.getElementById("overlay");
            const progress = document.querySelector(".progress");

            overlay.style.display = "flex";

            progress.style.width = "0%";
            progress.style.transition = `width ${progress_sec}s linear`;
            setTimeout(() => {
                progress.style.width = "100%";
            }, 50);

            setTimeout(() => {
                overlay.style.display = "none";
            }, timer_sec * 1000);
        }