import secrets

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from src.game.enums import EventType
from src.game.errors import InvalidAction
from src.lobby.router import game_manager
from src.protocol import game_auth_adapter, game_message_adapter


router = APIRouter(
    prefix="",
    tags=["Game"]
)


@router.websocket("/ws/game/{game_id}/{user_id}")
async def websocket_game(websocket: WebSocket, game_id: str, user_id: str):
    game = game_manager.get_game(game_id=game_id)
    await game_manager.connection_manager.connect(websocket=websocket)
    try:
        auth = game_auth_adapter.validate_python(await websocket.receive_json())
    except (ValidationError, WebSocketDisconnect):
        await game_manager.connection_manager.send_message(
            websocket,
            {"type": EventType.SHOW_ERROR.value, "msg": "Invalid game session."},
        )
        await websocket.close(code=1008)
        return
    player = game.get_player_or_none(user_id=user_id) if game else None
    if not player or not secrets.compare_digest(player.session_token, auth.token):
        await game_manager.connection_manager.send_message(
            websocket,
            {"type": EventType.SHOW_ERROR.value, "msg": "Invalid game session."},
        )
        await websocket.close(code=1008)
        return

    if auth.intent == "leave":
        await game_manager.event_handler.handle_disconnect_game(player_id=user_id)
        await game_manager.connection_manager.disconnect(websocket)
        return


    if auth.intent == "status":
        await game_manager.connection_manager.send_message(websocket, {
            "type": "rs",
            "seconds": game_manager.reconnect_seconds_left(user_id),
        })
        await game_manager.connection_manager.disconnect(websocket)
        return

    if not game_manager.resume_player(game, player, websocket):
        await game_manager.connection_manager.send_message(
            websocket,
            {"type": EventType.SHOW_ERROR.value, "msg": "This player is already connected."},
        )
        await websocket.close(code=1008)
        return

    if game.has_started:
        current_player = game.get_current_player()
        await game_manager.send_whose_turn(
            websocket,
            "It's your turn!" if current_player.user_id == user_id else f"It's {current_player.user_name}'s turn!",
            current_player.user_id,
        )
        await game_manager.send_game_data(
            player,
            current_player.user_id == user_id,
            game,
            chosen_suit=game.chosen_suit,
        )
    elif not await game.wait_until_all_ready():
        await game_manager.abort_startup(game, websocket)
        return

    try:
        while game.is_active:

            try:
                message = game_message_adapter.validate_python(await websocket.receive_json())
            except ValidationError:
                await game_manager.connection_manager.send_message(
                    websocket,
                    {"type": EventType.SHOW_ERROR.value, "msg": "Invalid game message."},
                )
                continue
            data = message.model_dump(exclude_none=True)

            if message.type == EventType.LEAVE_GAME.value:
                await game_manager.event_handler.handle_disconnect_game(player_id=user_id)
                return

            try:
                if message.type == EventType.GAME_STARTED.value:
                    if not game.mark_client_ready(user_id):
                        raise InvalidAction("This client is already ready.")
                    if not await game.wait_until_all_clients_ready():
                        await game_manager.abort_startup(game, websocket)
                        return
                    await game_manager.event_handler.handle_game_started(
                        player_id=user_id, game=game, send_first_turn=False,
                    )
                    completed_initialization = game.mark_client_initialized(user_id)
                    if not await game.wait_until_all_clients_initialized():
                        await game_manager.abort_startup(game, websocket)
                        return
                    if completed_initialization:
                        async with game.action_lock:
                            if game.get_current_player().is_bot:
                                await game_manager.run_automatic_actions(game)
                            else:
                                await game_manager.event_handler.send_first_turn(game)
                    continue

                async with game.action_lock:
                    match message.type:
                        case EventType.PLAYED_CARD.value:
                            await game_manager.event_handler.handle_played_card(
                                played_card=data["card"],
                                chosen_suit=data.get("chosen_suit"),
                                game=game,
                                player_id=user_id,
                            )

                        case EventType.DREW_CARD.value:
                            await game_manager.event_handler.handle_drew_card(game=game, player_id=user_id)

                        case EventType.SKIP_TURN.value:
                            await game_manager.event_handler.handle_skip_turn(game=game, player_id=user_id)

                        case EventType.SHOW_MY_MOVE.value:
                            await game_manager.event_handler.handle_show_my_move(game=game, data=data)

                        case EventType.GAME_OVER.value:
                            await game_manager.event_handler.handle_game_over(game=game, player_id=user_id)

                        case EventType.RESET_GAME.value:
                            await game_manager.event_handler.handle_reset_game(game=game, player_id=user_id)
                    await game_manager.run_automatic_actions(game)
            except InvalidAction as error:
                await game_manager.connection_manager.send_message(
                    websocket,
                    {"type": EventType.SHOW_ERROR.value, "msg": str(error)},
                )

    except (WebSocketDisconnect, RuntimeError):
        if game.get_player_or_none(user_id=user_id):
            game_manager.schedule_disconnect(player_id=user_id, websocket=websocket)
