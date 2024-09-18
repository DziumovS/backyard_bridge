import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from src.lobby.router import connection_manager, game_manager
from src.game.models import Game


router = APIRouter(
    prefix="",
    tags=["Game"]
)


@router.websocket("/ws/game/{game_id}/{user_id}")
async def websocket_game(websocket: WebSocket, game_id: str, user_id: str):
    await connection_manager.connect(websocket=websocket)
    game = game_manager.get_game(game_id=game_id)

    players = game_manager.get_players(game_id)

    for player in players:
        if player.user_id == user_id:
            player.websocket = websocket
            await websocket.send_json({
                "type": "player_hand",
                "hand": player.hand_to_dict()
            })
            break


    try:
        while game.is_active:
            await asyncio.sleep(0.1)
            # await asyncio.sleep(0.1)
            # player = game.players[game.current_player_index]
            # print(f"\n{player.user_name}'s turn. Current card: {game.current_card}")
            # print(f"Hand: {', '.join(str(card) for card in player.hand)}")
            #
            # if game.first_move:
            #     game.first_turn(player=player)
            # else:
            #     game.player_turn(player=player)
            #
            # if player.has_won():
            #     print(f"{player.user_name} has won the game!")
            #     game.end_game()
            #     break
            #
            # game.next_player()

    except WebSocketDisconnect:
        pass
