let ws,lobbyId,userId=Date.now().toString().slice(-9),userName=userId,isHost=!1,currentPlayer="",eventHandlersAdded=!1,game_over=!1,errorTimeout;const elements={wsId:document.querySelector("#ws-id"),pS:document.querySelector("#pS"),nameForm:document.getElementById("nameForm"),createLobbyButton:document.getElementById("createLobbyButton"),joinLobbyInput:document.getElementById("lobbyInput"),joinLobbyButton:document.getElementById("joinLobbyButton"),startButton:document.getElementById("startButton"),leaveLobbyButton:document.getElementById("leaveButton"),errorMessage:document.getElementById("errorMessage"),lobbyControls:document.getElementById("lobbyControls"),lobbyMessage:document.getElementById("lobbyMessage"),usersHeader:document.getElementById("usersHeader"),usersList:document.getElementById("usersList"),currentCards:document.getElementById("currentCards"),nameInput:document.getElementById("nameInput"),playerHand:document.getElementById("playerHand"),turnText:document.getElementById("turnText"),cardsLeft:document.getElementById("cardsLeft"),rightCard:document.getElementById("rightCard"),leftCard:document.getElementById("leftCard"),jackWidget:document.getElementById("jack-widget"),rulesWidget:document.getElementById("rules-widget"),scoresRate:document.getElementById("scoresRate"),nameAndScores:document.getElementById("nameAndScores"),playerScores:document.getElementById("scores"),gameOverWidget:document.getElementById("game-over-widget"),playerContainer:document.getElementById("playerContainer"),welcomeMessage:document.getElementById("welcomeMessage")};function updateUsername(e){e.preventDefault();let t=elements.nameInput.value.trim();t&&(userName=t,elements.wsId.textContent=userName,elements.nameForm.style.display="none",elements.wsId.style.display="block")}function setLobbyUI(e){elements.wsId.style.display="block",elements.welcomeMessage.style.display="none",elements.createLobbyButton.style.display="none",elements.nameForm.style.display="none",elements.joinLobbyInput.style.display="none",elements.joinLobbyButton.style.display="none",elements.lobbyControls.style.display="block",elements.leaveLobbyButton.style.display="inline",elements.startButton.style.display=e?"block":"none",isHost=e}function createLobby(){startLoadingAnimation(.3,.8),setLobbyUI(!0),initializeWebSocket("crl",{user_name:userName})}function preloadCardImages(){fetch("/get_cards").then(e=>e.json()).then(e=>{e.forEach(e=>{let t=new Image;t.src=e})})}async function joinLobby(){let e=elements.joinLobbyInput.value.trim();if(!e)return;let t=await fetch(`/check_lobby/${e}`),n=await t.json();n.exists?(startLoadingAnimation(.4,.9),setLobbyUI(!1),initializeWebSocket("jl",{user_name:userName,lobby_id:e})):await showError(n.msg,2)}function setAndCopyLobbyId(e,t){lobbyId=e;let n='<br><span class="small-text">(click to copy ID to clipboard)</span>';function s(){navigator.clipboard.writeText(e),document.getElementById("copyInfo")||(elements.lobbyMessage.innerHTML=t+'<br><span class="small-text" style="color: #ffa500" id="copyInfo">ID copied!</span>'),setTimeout(()=>{let e=document.getElementById("copyInfo");e&&e.remove(),elements.lobbyMessage.innerHTML=t+n},2e3)}elements.lobbyMessage.innerHTML=t+n,elements.lobbyMessage.removeEventListener("click",s),elements.lobbyMessage.addEventListener("click",s)}function initializeWebSocket(e,t){ws&&ws.close(1e3),(ws=new WebSocket(`wss://${window.location.hostname}/ws/lobby/${userId}`)).onopen=()=>ws.send(JSON.stringify({type:e,...t})),ws.onmessage=handleWebSocketMessage,preloadCardImages()}function handleWebSocketMessage(e){let t=JSON.parse(e.data);switch(t.type){case"lcr":setAndCopyLobbyId(t.lobby_id,t.msg);break;case"jdl":setAndCopyLobbyId(t.lobby_id,t.msg),updateUsers(t.users,!1);break;case"uu":updateUsers(t.users,t.is_host);break;case"sg":startGame();break;case"lcl":returnToMainPage();break;case"tsb":toggleStartButton(t.enable);break;case"gd":checkScoresRate(t.scores_rate),updatePlayerHand(t.hand,t.current_player,t.playable_cards,"current"),updateOpponentData(t.players_hands),updateCurrentCards(t.current_card,t.deck_len,t.chosen_suit,t.player_options);break;case"wt":whoseTurn(t.msg,t.current_player);break;case"ft":firstTurn(t.current_card);break;case"nep":backToHomePage(t.msg,3);break;case"se":showError(t.msg,2);break;case"iib":showError(t.msg,4),isItBridge(t.current_card);break;case"go":removeHighlighted("#leftCard img"),showError(t.error_msg,5).then(()=>{showGameOverWidget(t.widget_msg,t.players_scores,t.player_scores)});break;case"godc":game_over=!0,drawCard();break;case"lg":leaveGame(t.player_id);break;case"apc":playCard(t.card,"opponent");break;case"adc":change_player(t.current_player),animateDrawCard("opponent");break;case"gr":reset_game(t.players_scores,t.player_scores)}}function showError(e,t){return clearTimeout(errorTimeout),elements.errorMessage.innerHTML=e,elements.errorMessage.style.display="block",new Promise(e=>{errorTimeout=setTimeout(()=>{elements.errorMessage.innerHTML="",elements.errorMessage.style.display="none",e()},1e3*t)})}function startGame(){isHost&&ws.send(JSON.stringify({type:"sg"})),ws=new WebSocket(`wss://${window.location.hostname}/ws/game/${lobbyId}/${userId}`),startLoadingAnimation(1,1.5),ws.onopen=()=>ws.send(JSON.stringify({type:"gs"})),ws.onmessage=function(e){handleWebSocketMessage(e)},setGameUI()}function setGameUI(){elements.lobbyControls.style.display="none",elements.currentCards.style.display="flex",elements.playerContainer.style.display="flex",elements.nameAndScores.style.flexDirection="row",elements.pS.innerHTML="0",elements.scoresRate.innerHTML="x1",elements.playerScores.style.display="block",elements.usersHeader.style.fontSize="12px",elements.usersList.style.fontSize="12px",elements.usersList.style.flexDirection="row";let e=document.getElementById(userId);e.style.display="none";let t=document.querySelectorAll(".opponentScores");t.forEach(e=>{e.style.display="flex",e.style.justifyContent="center"});let n=document.querySelectorAll(".opponent_hand");n.forEach(e=>{e.style.display="flex"})}function leaveGame(e){let t=document.getElementById(e);t&&t.remove()}function leaveLobby(){ws.send(JSON.stringify({type:"cll",lobby_id:lobbyId})),returnToMainPage()}function returnToMainPage(){elements.lobbyControls.style.display="none",elements.welcomeMessage.style.display="block",elements.createLobbyButton.style.display="inline",elements.nameForm.style.display="none",elements.joinLobbyInput.style.display="inline",elements.joinLobbyInput.value="",elements.joinLobbyButton.style.display="inline",elements.joinLobbyButton.disabled=!0,elements.leaveLobbyButton.style.display="none",elements.errorMessage.style.display="none",elements.currentCards.style.display="none",elements.usersHeader.style.display="none",elements.usersList.style.display="none"}function updateUsers(e,t){elements.usersList.style.display="flex",elements.usersList.innerHTML="",elements.usersHeader.style.display="block",e.forEach(e=>{let t=document.createElement("div");t.className=e.user_id,t.id=e.user_id;let n=document.createElement("p");n.textContent=e.user_name,t.appendChild(n),elements.usersList.appendChild(t);let s=document.createElement("div");s.className="opponent_hand",s.id=`${e.user_id}_hand`;let l=document.createElement("div");l.className="opponentScores",l.id="opponentScores";let r=document.createElement("p");r.innerHTML="Scores:",r.style.marginRight="3px";let a=document.createElement("span");a.id=`${e.user_id}_oS`,a.style.fontWeight="bold",a.textContent="0",l.appendChild(r),l.appendChild(a),t.appendChild(l),t.appendChild(s)}),t&&toggleStartButton(!0)}function updateOpponentData(e){e.forEach(e=>{let t=document.getElementById(`${e.player_id}_hand`);t.innerHTML="";let n=21*e.hand_len-1,s=0,l=0;n>100?s=Math.min(s=(n-100)/(e.hand_len-1),19):l=(100-n)/2;for(let r=0;r<e.hand_len;r++){let a=document.createElement("div");a.classList.add("opponent_card"),a.style.left=`${l+r*(20-s)+1*r}px`;let o=document.createElement("img");o.src="/static/cards/opponent_card.png",o.alt="opponent_card",a.appendChild(o),t.appendChild(a)}})}function toggleStartButton(e){elements.startButton.disabled=!e}function updatePlayerHand(e,t,n,s){elements.playerHand.innerHTML="";let l=elements.playerHand.offsetWidth,r=95*e.length-5,a=15,o=0;r>l-30?o=Math.min(o=(r-(l-30))/(e.length-1),85):a+=(l-r-30+5)/2,e.forEach((e,l)=>{let r=document.createElement("div");r.classList.add("card"),r.style.left=`${a+l*(90-o)+5*l}px`;let i=n.some(t=>t.rank===e.rank&&t.suit===e.suit);t&&i&&(r.classList.add("highlighted-card-img"),r.style.bottom="50px",r.onclick=()=>playCard(e,s),r.style.cursor="pointer");let d=document.createElement("img"),c=`${e.rank}_${e.suit}`;d.src=`/static/cards/${c}.png`,d.alt=c,r.appendChild(d),elements.playerHand.appendChild(r)})}function whoseTurn(e,t){elements.turnText.textContent=e,change_player(t),elements.turnText.classList.add("wave-effect"),setTimeout(()=>{elements.turnText.classList.remove("wave-effect")},5e3)}function change_player(e){e&&(currentPlayer=e)}function updateCurrentCards(e,t,n,s){elements.cardsLeft.textContent=t;let l=elements.rightCard.querySelector("img");l&&l.remove();let r=document.createElement("img");n?(r.src=`/static/cards/${n.suit}.png`,r.alt=n.suit):(r.src=`/static/cards/${e.rank}_${e.suit}.png`,r.alt=`${e.rank}_${e.suit}`),elements.rightCard.appendChild(r),setTimeout(()=>{checkCurrentPlayerOptions(s)},50)}async function playCard(e,t){if("current"===t){ws.send(JSON.stringify({type:"smm",card:e}));let n=[...elements.playerHand.children].find(t=>{let n=t.querySelector("img");return n.alt===`${e.rank}_${e.suit}`});await animatePlayedCard(n)}else{let s=document.getElementById(currentPlayer),l=s.querySelector(".opponent_card img");await animatePlayedCard(l)}updateRightCard(e),"current"===t&&("J"===e.rank?showJackWidget(e):ws.send(JSON.stringify({type:"pc",card:e,chosen_suit:null})))}function updateRightCard(e){let t=elements.rightCard.querySelector("img");t&&t.remove();let n=document.createElement("img");n.src=`/static/cards/${e.rank}_${e.suit}.png`,n.alt=`${e.rank}_${e.suit}`,elements.rightCard.appendChild(n)}async function animatePlayedCard(e){let t=e.getBoundingClientRect(),n=elements.rightCard.getBoundingClientRect(),s=e.cloneNode(!0);document.body.appendChild(s),s.style.position="absolute",s.style.left=`${t.left}px`,s.style.top=`${t.top}px`,s.style.width=`${t.width}px`,s.style.height=`${t.height}px`,s.style.transition="all 0.35s ease",setTimeout(()=>{e.style.display="none",s.style.left=`${n.left}px`,s.style.top=`${n.top}px`,s.style.width="90px",s.style.height="135px"},30),await new Promise(e=>{setTimeout(()=>{document.body.contains(s)&&s.remove(),e()},370)})}async function drawCard(){ws.send(JSON.stringify({type:"smm"})),await animateDrawCard("current"),game_over?(ws.send(JSON.stringify({type:"go"})),game_over=!1):ws.send(JSON.stringify({type:"dc"}))}async function animateDrawCard(e){let t=elements.leftCard.getBoundingClientRect(),n=elements.leftCard.querySelector("img").cloneNode(!0);document.body.appendChild(n),n.style.position="absolute",n.style.left=`${t.left}px`,n.style.top=`${t.top}px`,n.style.width=`${t.width}px`,n.style.height=`${t.height}px`,n.style.transition="all 0.35s ease",setTimeout(()=>{let s,l,r;if("current"===e)l=(s=elements.playerHand.getBoundingClientRect()).left+s.width/2-t.width/2,r=s.bottom-t.height-10,n.style.width=`${t.width}px`,n.style.height=`${t.height}px`;else{let a=document.getElementById(`${currentPlayer}_hand`),o=a.querySelector(".opponent_card");l=(s=o.getBoundingClientRect()).left,r=s.top,n.style.width="20px",n.style.height="30px"}n.style.left=`${l}px`,n.style.top=`${r}px`},30),await new Promise(e=>{setTimeout(()=>{document.body.contains(n)&&n.remove(),e()},370)})}function skip_turn(){currentPlayer===userId&&(ws.send(JSON.stringify({type:"st"})),elements.errorMessage.style.display="none")}function colorSkipTurn(){let e=document.querySelector("#rightCard img");currentPlayer===userId&&e.classList.add("highlighted-card-img")}function colorDrawCard(){let e=document.querySelector("#leftCard img");currentPlayer===userId&&e.classList.add("highlighted-card-img")}function firstTurn(e){currentPlayer===userId&&("J"===e.rank?showJackWidget(e):ws.send(JSON.stringify({type:"pc",card:e,chosen_suit:null})))}function showJackWidget(e){elements.jackWidget.style.display="block";let t=elements.playerHand.querySelectorAll(".card");t.forEach(e=>{e.onclick=null,e.style.cursor="default",e.style.bottom="10px",e.classList.remove("highlighted-card-img")});let n=["♠","♥","♦","♣"],s=document.querySelectorAll(".jack-widget-grid div");s.forEach((t,s)=>{let l=t.cloneNode(!0);t.replaceWith(l),l.addEventListener("click",function(){let t=n[s];elements.jackWidget.style.display="none",ws.send(JSON.stringify({type:"pc",card:e,chosen_suit:t}))})})}function checkCurrentPlayerOptions(e){setDefaultDrawCard(),setDefaultSkipTurn(),currentPlayer===userId&&(e.must_draw?(colorDrawCard(),elements.leftCard.style.cursor="pointer",elements.leftCard.onclick=drawCard):e.must_skip?(colorSkipTurn(),elements.rightCard.style.cursor="pointer",elements.rightCard.onclick=skip_turn):(e.can_draw&&(colorDrawCard(),elements.leftCard.style.cursor="pointer",elements.leftCard.onclick=drawCard),e.can_skip&&(colorSkipTurn(),elements.rightCard.style.cursor="pointer",elements.rightCard.onclick=skip_turn)))}function setDefaultDrawCard(){currentPlayer===userId&&removeHighlighted("#leftCard img"),elements.leftCard.style.cursor="default",elements.leftCard.onclick=null}function setDefaultSkipTurn(){currentPlayer===userId&&removeHighlighted("#rightCard img"),elements.rightCard.style.cursor="default",elements.rightCard.onclick=null}function removeHighlighted(e){let t=document.querySelector(e);t.classList.remove("highlighted-card-img")}async function showRulesWidget(){let e=await fetch("/rules"),t=await e.json();document.querySelector(".rules-column p").innerHTML=t.rules,elements.rulesWidget.style.display="flex",eventHandlersAdded||(document.getElementById("closeRulesWidget").addEventListener("click",closeRulesWidget),document.getElementById("rules-widget").addEventListener("click",function(e){e.target===elements.rulesWidget&&closeRulesWidget()}),document.addEventListener("keydown",function(e){"Escape"===e.key&&closeRulesWidget()}),eventHandlersAdded=!0)}function closeRulesWidget(){elements.rulesWidget.style.display="none",document.querySelector(".rules-column p").textContent=""}async function backToHomePage(e,t){await showError(e,t),window.location.href=`${window.location.origin}`}function checkScoresRate(e){e!==elements.scoresRate.innerHTML&&(elements.scoresRate.innerHTML=e,elements.scoresRate.classList.add("wave-effect"),setTimeout(()=>{elements.scoresRate.classList.remove("wave-effect")},5e3))}function startNewGame(){ws.send(JSON.stringify({type:"rg"}))}function reset_game(e,t){closeGameOverWidget(),elements.pS.textContent=t,elements.scoresRate.innerHTML="x1",e.forEach(e=>{let t=document.getElementById(`${e.player_id}_oS`);t.textContent=e.scores})}function isItBridge(e){setTimeout(()=>{elements.leftCard.querySelector("img").src="/static/cards/bridge.png",elements.leftCard.querySelector("img").alt="bridge",elements.leftCard.style.cursor="pointer",colorDrawCard(),elements.leftCard.onclick=()=>{ws.send(JSON.stringify({type:"go"})),resetCardState(e)},elements.rightCard.querySelector("img").src="/static/cards/continue.png",elements.rightCard.querySelector("img").alt="continue",elements.rightCard.onclick=()=>{skip_turn(),resetCardState(e)}},50)}function resetCardState(e){elements.leftCard.querySelector("img").src="/static/cards/closed_card.png",elements.leftCard.querySelector("img").alt="closed_card",setDefaultDrawCard(),elements.rightCard.querySelector("img").src=`/static/cards/${e.rank}_${e.suit}.png`,elements.rightCard.querySelector("img").alt=`${e.rank}_${e.suit}`,setDefaultSkipTurn()}function showGameOverWidget(e,t,n){t.forEach(e=>{let t=document.getElementById(`${e.player_id}_oS`);t.textContent=e.scores}),elements.pS.textContent=n,document.querySelector(".results-column p").innerHTML=e,elements.gameOverWidget.style.display="flex"}function closeGameOverWidget(){elements.gameOverWidget.style.display="none",document.querySelector(".results-column p").textContent=""}function startLoadingAnimation(e,t){let n=document.getElementById("overlay"),s=document.querySelector(".progress");n.style.display="flex",s.style.width="0%",s.style.transition=`width ${e}s linear`,setTimeout(()=>{s.style.width="100%"},50),setTimeout(()=>{n.style.display="none"},1e3*t)}elements.wsId.textContent=userName,elements.nameInput.placeholder=userName,elements.joinLobbyInput.addEventListener("input",function(){elements.joinLobbyButton.disabled=!elements.joinLobbyInput.value.trim()}),elements.nameInput.addEventListener("input",function(){let e=elements.nameInput.value.trim();document.getElementById("changeName").disabled=0===e.length});