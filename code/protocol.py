"""JSON message validation and length-prefixed TCP framing."""

import json
import struct

HEADER_SIZE = 4
MAX_FRAME_SIZE = 64 * 1024

MESSAGE_TYPES = {
    "CONNECT",
    "LOBBY_WAIT",
    "GAME_START",
    "TURN",
    "STATE_CHANGE",
    "STATE_ASSERT",
    "ERROR",
    "DISCONNECT",
    "GAME_OVER",
    "PLAY_AGAIN",
}


class ProtocolError(ValueError):
    """Raised when a wire message is malformed or violates the schema."""


def _is_symbol(value):
    return value in ("X", "O")


def _validate_board(board):
    if not isinstance(board, list) or len(board) != 3:
        return False
    return all(
        isinstance(row, list)
        and len(row) == 3
        and all(cell is None or _is_symbol(cell) for cell in row)
        for row in board
    )


def _validate_connect(payload):
    if payload:
        raise ProtocolError("CONNECT payload must be empty.")


def _validate_state_change(payload):
    if set(payload) != {"row", "column"}:
        raise ProtocolError("STATE_CHANGE requires row and column.")
    for coordinate in (payload["row"], payload["column"]):
        if isinstance(coordinate, bool) or not isinstance(coordinate, int):
            raise ProtocolError("Move coordinates must be integers.")
        if not 0 <= coordinate <= 2:
            raise ProtocolError("Move coordinates must be between 0 and 2.")


def _validate_play_again(payload):
    if set(payload) != {"accept"} or not isinstance(payload["accept"], bool):
        raise ProtocolError("PLAY_AGAIN requires a boolean accept value.")


def _validate_disconnect(payload):
    if set(payload) != {"reason"} or not isinstance(payload["reason"], str):
        raise ProtocolError("DISCONNECT requires a string reason.")


def _validate_lobby_wait(payload):
    required = {"players_waiting", "players_needed"}
    if not required.issubset(payload) or set(payload) - required - {"phase"}:
        raise ProtocolError("LOBBY_WAIT has an invalid payload.")
    if payload["players_waiting"] != 1 or payload["players_needed"] != 2:
        raise ProtocolError("LOBBY_WAIT must describe a two-player lobby.")
    if payload.get("phase", "LOBBY") not in ("LOBBY", "REMATCH"):
        raise ProtocolError("LOBBY_WAIT phase must be LOBBY or REMATCH.")


def _validate_game_start(payload):
    if set(payload) != {"your_symbol", "starting_player", "board"}:
        raise ProtocolError("GAME_START has an invalid payload.")
    if not _is_symbol(payload["your_symbol"]):
        raise ProtocolError("GAME_START your_symbol must be X or O.")
    if payload["starting_player"] != "X" or not _validate_board(payload["board"]):
        raise ProtocolError("GAME_START has an invalid starting state.")


def _validate_turn(payload):
    if set(payload) != {"player"} or not _is_symbol(payload["player"]):
        raise ProtocolError("TURN requires a player symbol.")


def _validate_state_assert(payload):
    if set(payload) != {"board", "next_turn"}:
        raise ProtocolError("STATE_ASSERT has an invalid payload.")
    if not _validate_board(payload["board"]):
        raise ProtocolError("STATE_ASSERT board is invalid.")
    if payload["next_turn"] is not None and not _is_symbol(payload["next_turn"]):
        raise ProtocolError("STATE_ASSERT next_turn must be X, O, or null.")


def _validate_error(payload):
    if set(payload) != {"code", "reason"}:
        raise ProtocolError("ERROR requires code and reason.")
    if not all(isinstance(payload[key], str) for key in ("code", "reason")):
        raise ProtocolError("ERROR code and reason must be strings.")


def _validate_game_over(payload):
    if set(payload) != {"result", "winner"}:
        raise ProtocolError("GAME_OVER requires result and winner.")
    if payload["result"] == "WIN":
        if not _is_symbol(payload["winner"]):
            raise ProtocolError("A win must identify X or O as the winner.")
    elif payload["result"] == "DRAW":
        if payload["winner"] is not None:
            raise ProtocolError("A draw cannot have a winner.")
    else:
        raise ProtocolError("GAME_OVER result must be WIN or DRAW.")


def validate_message(message):
    if not isinstance(message, dict) or set(message) != {"message", "payload"}:
        raise ProtocolError("Message must contain only 'message' and 'payload'.")

    message_type = message["message"]
    payload = message["payload"]
    if message_type not in MESSAGE_TYPES:
        raise ProtocolError("Unknown message type.")
    if not isinstance(payload, dict):
        raise ProtocolError("Message payload must be an object.")

    match message_type:
        case "CONNECT":
            _validate_connect(payload)
        case "STATE_CHANGE":
            _validate_state_change(payload)
        case "PLAY_AGAIN":
            _validate_play_again(payload)
        case "DISCONNECT":
            _validate_disconnect(payload)
        case "LOBBY_WAIT":
            _validate_lobby_wait(payload)
        case "GAME_START":
            _validate_game_start(payload)
        case "TURN":
            _validate_turn(payload)
        case "STATE_ASSERT":
            _validate_state_assert(payload)
        case "ERROR":
            _validate_error(payload)
        case "GAME_OVER":
            _validate_game_over(payload)

    return message


def encode_message(message_type, payload):
    message = validate_message({"message": message_type, "payload": payload})
    body = json.dumps(message, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if not body or len(body) > MAX_FRAME_SIZE:
        raise ProtocolError("Message exceeds the maximum frame size.")
    return struct.pack("!I", len(body)) + body


def decode_message(body):
    try:
        message = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ProtocolError("Message must be valid UTF-8 JSON.") from error
    return validate_message(message)


class FrameDecoder:
    """Incrementally decode four-byte-length-prefixed JSON frames."""

    def __init__(self):
        self._buffer = bytearray()

    def feed(self, data):
        self._buffer.extend(data)
        frames = []

        while len(self._buffer) >= HEADER_SIZE:
            frame_size = struct.unpack("!I", self._buffer[:HEADER_SIZE])[0]
            if not 1 <= frame_size <= MAX_FRAME_SIZE:
                self._buffer.clear()
                raise ProtocolError("Invalid or oversized frame length.")
            if len(self._buffer) < HEADER_SIZE + frame_size:
                break

            frames.append(bytes(self._buffer[HEADER_SIZE:HEADER_SIZE + frame_size]))
            del self._buffer[:HEADER_SIZE + frame_size]

        return frames