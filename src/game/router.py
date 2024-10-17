from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from src.lobby.router import connection_manager, game_manager


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
            break

    try:
        while game.is_active:

            data = await websocket.receive_json()

            match data["type"]:
                case "game_started":
                    player = game.get_player_or_none(user_id=user_id)
                    current_player = game.get_current_player()
                    is_current_player = game.is_current_player(player_id=user_id)
                    message = "It's your turn!" if is_current_player else f"It's {current_player.user_name}'s turn!"

                    await game_manager.send_whose_turn(websocket=player.websocket,
                                                       message=message,
                                                       user_id=current_player.user_id)

                    await game_manager.send_game_data(player=player,
                                                      current_player=is_current_player,
                                                      game=game,
                                                      playable_cards=False)

                    if is_current_player and game.first_move:
                        await connection_manager.send_message(
                            websocket=current_player.websocket,
                            message={
                                "type": "first_turn",
                                "current_card": game.current_card.card_to_dict()
                            }
                        )

                case "played_card":
                    current_player = game.get_current_player()
                    card = current_player.dict_to_card(card=data["card"])
                    game.current_card = card

                    chosen_suit = data["chosen_suit"]
                    game.chosen_suit = {
                        "suit": chosen_suit,
                        "color": game.deck.color_map[chosen_suit],
                        "chooser_id": current_player.user_id
                    } if chosen_suit else None

                    game.handle_special_cards(current_player=current_player, card=card)

                    next_player = game.get_current_player()

                    for player in game.players:
                        is_current_player = player.user_id == next_player.user_id
                        message = "It's your turn!" if is_current_player else f"It's {next_player.user_name}'s turn!"

                        await game_manager.send_whose_turn(websocket=player.websocket,
                                                           message=message,
                                                           user_id=next_player.user_id)

                        await game_manager.send_game_data(player=player,
                                                          current_player=is_current_player,
                                                          game=game,
                                                          chosen_suit=game.chosen_suit)

                case "drew_card":
                    current_player = game.get_current_player()
                    current_player.draw_card(deck=game.deck)

                    playable_cards = current_player.get_playable_cards(
                        current_card=game.current_card,
                        chosen_suit=game.chosen_suit
                    )

                    if game.current_card.rank == "6":
                        game.handle_card_six(current_player=current_player)
                    else:
                        if current_player.options.must_draw:
                            current_player.options.must_draw -= 1
                        elif current_player.options.must_skip:
                            current_player.options.must_skip = False
                        elif current_player.options.can_draw and not playable_cards:
                            current_player.options.must_skip = True
                        elif current_player.options.can_draw:
                            current_player.options.can_draw = False
                            current_player.options.can_skip = True

                    for player in game.players:
                        is_current_player = player.user_id == current_player.user_id
                        await game_manager.send_game_data(player=player, current_player=is_current_player, game=game, chosen_suit=game.chosen_suit)

                    if all((not current_player.options.can_draw, current_player.options.can_skip)):
                        current_player.set_default_options()

                case "skip_turn":
                    current_player = game.get_current_player()

                    if current_player.options.must_skip:
                        current_player.options.must_skip = False

                    game.next_player()

                    next_player = game.get_current_player()

                    for player in game.players:
                        is_current_player = player.user_id == next_player.user_id
                        message = "It's your turn!" if is_current_player else f"It's {next_player.user_name}'s turn!"

                        await game_manager.send_whose_turn(websocket=player.websocket,
                                                           message=message,
                                                           user_id=next_player.user_id)

                        await game_manager.send_game_data(player=player, current_player=is_current_player, game=game, chosen_suit=game.chosen_suit)

                case _:
                    pass

    except WebSocketDisconnect:
        pass
