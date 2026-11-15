"""Server-authoritative Tic Tac Toe game and lobby state."""

from dataclasses import dataclass


@dataclass(frozen=True)
class GameAction:
    recipient: object
    message: str
    payload: dict


class GameSession:
    def __init__(self):
        self.players = {}
        self.board = self._empty_board()
        self.current_turn = None
        self.phase = "WAITING"
        self.rematch_votes = set()

    @staticmethod
    def _empty_board():
        return [[None for _ in range(3)] for _ in range(3)]

    def connect(self, player_id):
        if player_id in self.players:
            return [self._error(player_id, "ALREADY_CONNECTED", "This connection already joined.")]
        if len(self.players) >= 2:
            return [self._error(player_id, "BUSY", "The game already has two players.")]

        symbol = "X" if "X" not in self.players.values() else "O"
        self.players[player_id] = symbol

        if len(self.players) == 1:
            self.phase = "WAITING"
            return [self._lobby_wait(player_id)]

        return self._start_game()

    def handle(self, player_id, message_type, payload):
        if player_id not in self.players:
            return [self._error(player_id, "NOT_CONNECTED", "Send CONNECT before playing.")]

        if message_type == "STATE_CHANGE":
            return self._move(player_id, payload)
        if message_type == "PLAY_AGAIN":
            return self._play_again(player_id, payload["accept"])
        if message_type == "DISCONNECT":
            return self.disconnect(player_id)
        if message_type == "CONNECT":
            return [self._error(player_id, "ALREADY_CONNECTED", "This connection already joined.")]
        return [self._error(player_id, "INVALID_MESSAGE", "This message is not valid from a client.")]

    def disconnect(self, player_id):
        if player_id not in self.players:
            return []

        del self.players[player_id]
        self.rematch_votes.clear()
        self.board = self._empty_board()
        self.current_turn = None

        if not self.players:
            self.phase = "WAITING"
            return []

        self.phase = "WAITING"
        remaining_player = next(iter(self.players))
        return [self._lobby_wait(remaining_player)]

    def _move(self, player_id, payload):
        if self.phase != "PLAYING":
            return [self._error(player_id, "GAME_NOT_ACTIVE", "The game is not accepting moves.")]
        if self.players[player_id] != self.current_turn:
            return [self._error(player_id, "NOT_YOUR_TURN", f"It is {self.current_turn}'s turn.")]

        row = payload["row"]
        column = payload["column"]
        if self.board[row][column] is not None:
            return [self._error(player_id, "CELL_OCCUPIED", "That cell is already occupied.")]

        symbol = self.players[player_id]
        self.board[row][column] = symbol

        if self._has_won(symbol):
            self.phase = "GAME_OVER"
            self.current_turn = None
            actions = self._broadcast(
                "STATE_ASSERT",
                {"board": self._copy_board(), "next_turn": None},
            )
            actions.extend(self._broadcast("GAME_OVER", {"result": "WIN", "winner": symbol}))
            return actions

        if all(cell is not None for board_row in self.board for cell in board_row):
            self.phase = "GAME_OVER"
            self.current_turn = None
            actions = self._broadcast(
                "STATE_ASSERT",
                {"board": self._copy_board(), "next_turn": None},
            )
            actions.extend(self._broadcast("GAME_OVER", {"result": "DRAW", "winner": None}))
            return actions

        self.current_turn = "O" if symbol == "X" else "X"
        actions = self._broadcast(
            "STATE_ASSERT",
            {"board": self._copy_board(), "next_turn": self.current_turn},
        )
        next_player = self._player_for_symbol(self.current_turn)
        actions.append(GameAction(next_player, "TURN", {"player": self.current_turn}))
        return actions

    def _play_again(self, player_id, accept):
        if self.phase != "GAME_OVER":
            return [self._error(player_id, "GAME_NOT_OVER", "A rematch can only be requested after a game.")]

        if not accept:
            self.rematch_votes.clear()
            return self._broadcast(
                "ERROR",
                {"code": "REMATCH_DECLINED", "reason": "A player declined the rematch."},
            )

        self.rematch_votes.add(player_id)
        if len(self.rematch_votes) == 2:
            return self._start_game()

        return [
            GameAction(
                player_id,
                "LOBBY_WAIT",
                {"players_waiting": 1, "players_needed": 2, "phase": "REMATCH"},
            )
        ]

    def _start_game(self):
        self.phase = "PLAYING"
        self.board = self._empty_board()
        self.current_turn = "X"
        self.rematch_votes.clear()
        actions = []

        for player_id, symbol in self.players.items():
            actions.append(
                GameAction(
                    player_id,
                    "GAME_START",
                    {
                        "your_symbol": symbol,
                        "starting_player": "X",
                        "board": self._copy_board(),
                    },
                )
            )

        actions.append(
            GameAction(self._player_for_symbol("X"), "TURN", {"player": "X"})
        )
        return actions

    def _has_won(self, symbol):
        lines = self.board + [
            [self.board[row][column] for row in range(3)]
            for column in range(3)
        ]
        lines.extend(
            [
                [self.board[index][index] for index in range(3)],
                [self.board[index][2 - index] for index in range(3)],
            ]
        )
        return any(all(cell == symbol for cell in line) for line in lines)

    def _player_for_symbol(self, symbol):
        return next(player_id for player_id, player_symbol in self.players.items()
                    if player_symbol == symbol)

    def _copy_board(self):
        return [row.copy() for row in self.board]

    def _broadcast(self, message, payload):
        return [GameAction(player_id, message, payload) for player_id in self.players]

    @staticmethod
    def _error(player_id, code, reason):
        return GameAction(player_id, "ERROR", {"code": code, "reason": reason})

    @staticmethod
    def _lobby_wait(player_id):
        return GameAction(
            player_id,
            "LOBBY_WAIT",
            {"players_waiting": 1, "players_needed": 2, "phase": "LOBBY"},
        )