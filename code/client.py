"""Interactive console client for the Tic Tac Toe game."""

import argparse
import socket
import threading

if __package__:
    from .protocol import FrameDecoder, ProtocolError, decode_message, encode_message
else:
    from protocol import FrameDecoder, ProtocolError, decode_message, encode_message


def parse_port(value):
    """Validate a CLI port value and convert it to an integer."""
    try:
        port = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("port must be an integer") from error
    if not 1024 <= port <= 65535:
        raise argparse.ArgumentTypeError("port must be between 1024 and 65535")
    return port


def parse_args(argv=None):
    """Parse the client's required host and port command-line options."""
    parser = argparse.ArgumentParser(description="Play Tic Tac Toe over TCP.")
    parser.add_argument("-i", "--host", required=True, help="server hostname or IPv4 address")
    parser.add_argument("-p", "--port", required=True, type=parse_port)
    return parser.parse_args(argv)


def connect_to_server(host, port):
    """Resolve the server address and return a connected TCP socket."""
    address = socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM)[0][4]
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        client_socket.connect(address)
    except OSError:
        client_socket.close()
        raise
    return client_socket


def format_board(board):
    """Format a board as a readable three-row text grid."""
    rows = [" | ".join(cell or " " for cell in row) for row in board]
    return "\n-----------\n".join(rows)


class GameClient:
    def __init__(self, client_socket):
        """Initialize the client socket, synchronization primitives, and game state."""
        self.socket = client_socket
        self.state_lock = threading.Lock()
        self.send_lock = threading.Lock()
        self.stop_event = threading.Event()
        self.phase = "LOBBY"
        self.symbol = None
        self.my_turn = False
        self.board = [[None] * 3 for _ in range(3)]

    def send(self, message_type, payload):
        """Encode and send one protocol message to the server."""
        frame = encode_message(message_type, payload)
        with self.send_lock:
            self.socket.sendall(frame)

    def receive_messages(self):
        """Receive, decode, and dispatch complete server messages until stopped."""
        decoder = FrameDecoder()
        try:
            while not self.stop_event.is_set():
                data = self.socket.recv(4096)
                if not data:
                    print("Server disconnected.")
                    break
                for frame in decoder.feed(data):
                    try:
                        message = decode_message(frame)
                    except ProtocolError as error:
                        print(f"Received an invalid server message: {error}")
                        continue
                    self.handle_server_message(message)
        except (OSError, ProtocolError) as error:
            if not self.stop_event.is_set():
                print(f"Connection ended: {error}")
        finally:
            self.stop_event.set()

    def handle_server_message(self, message):
        """Dispatch a decoded server message to its type-specific handler."""
        message_type = message["message"]
        payload = message["payload"]

        match message_type:
            case "LOBBY_WAIT":
                self._handle_lobby_wait(payload)
            case "GAME_START":
                self._handle_game_start(payload)
            case "TURN":
                self._handle_turn(payload)
            case "STATE_ASSERT":
                self._handle_state_assert(payload)
            case "ERROR":
                self._handle_error(payload)
            case "GAME_OVER":
                self._handle_game_over(payload)

    def _handle_lobby_wait(self, payload):
        """Update lobby or rematch-waiting state and print the appropriate status."""
        phase = payload.get("phase", "LOBBY")
        with self.state_lock:
            self.phase = "REMATCH" if phase == "REMATCH" else "LOBBY"
        if phase == "REMATCH":
            print("Waiting for the other player to accept a rematch.")
        else:
            print("Waiting for another player to join.")

    def _handle_game_start(self, payload):
        """Set the player's symbol and initial board when a game begins."""
        with self.state_lock:
            self.phase = "PLAYING"
            self.symbol = payload["your_symbol"]
            self.board = payload["board"]
            self.my_turn = False
        print(f"Game started. You are {self.symbol}; X moves first.")
        print(format_board(payload["board"]))

    def _handle_turn(self, payload):
        """Update whose turn it is and print the relevant turn status."""
        with self.state_lock:
            self.my_turn = payload["player"] == self.symbol
        if self.my_turn:
            print(f"Your turn ({self.symbol}). Enter: row column")
        else:
            print(f"Waiting for {payload['player']} to move.")

    def _handle_state_assert(self, payload):
        """Replace the local board with the server's asserted state and display it."""
        with self.state_lock:
            self.board = payload["board"]
        print("Board updated:")
        print(format_board(payload["board"]))

    def _handle_error(self, payload):
        """Display a server error and update state when a rematch is declined."""
        print(f"Error [{payload['code']}]: {payload['reason']}")
        if payload["code"] == "REMATCH_DECLINED":
            with self.state_lock:
                self.phase = "GAME_OVER"

    def _handle_game_over(self, payload):
        """Update finished-game state and display the result and rematch prompt."""
        with self.state_lock:
            self.phase = "GAME_OVER"
            self.my_turn = False
        if payload["result"] == "DRAW":
            print("The game is a draw.")
        else:
            result = "You win!" if payload["winner"] == self.symbol else "You lose."
            print(f"Game over. {result} Winner: {payload['winner']}.")
        print("Enter 'again' to request a rematch, 'no' to decline, or 'quit'.")

    def run_input_loop(self):
        """Run the interactive command loop and cleanly stop the receiver and socket."""
        self.send("CONNECT", {})
        receiver = threading.Thread(target=self.receive_messages, daemon=True)
        receiver.start()

        try:
            while not self.stop_event.is_set():
                try:
                    command = input("> ").strip()
                except EOFError:
                    command = "quit"

                if command.lower() in ("quit", "exit"):
                    self.send("DISCONNECT", {"reason": "QUIT"})
                    break
                if not command:
                    continue

                lowered = command.lower()
                if lowered in ("again", "yes", "y"):
                    self._request_rematch(True)
                    continue
                if lowered in ("no", "n"):
                    self._request_rematch(False)
                    continue

                self._submit_move(command)
        except (KeyboardInterrupt, OSError, ProtocolError) as error:
            if isinstance(error, (OSError, ProtocolError)):
                print(f"Connection ended: {error}")
        finally:
            self.stop_event.set()
            try:
                self.socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            self.socket.close()
            receiver.join(timeout=1)

    def _request_rematch(self, accept):
        """Send a rematch decision if the client is in a finished-game state."""
        with self.state_lock:
            is_game_over = self.phase in ("GAME_OVER", "REMATCH")
        if not is_game_over:
            print("A rematch can only be requested after a game.")
            return
        self.send("PLAY_AGAIN", {"accept": accept})

    def _submit_move(self, command):
        """Parse and validate a console move before sending it to the server."""
        parts = command.replace(",", " ").split()
        if len(parts) != 2:
            print("Enter a move as two coordinates, for example: 1 2")
            return
        try:
            row, column = (int(part) for part in parts)
        except ValueError:
            print("Row and column must be integers from 0 to 2.")
            return
        if not 0 <= row <= 2 or not 0 <= column <= 2:
            print("Row and column must be from 0 to 2.")
            return

        with self.state_lock:
            if self.phase != "PLAYING":
                print("The game is not currently accepting moves.")
                return
            if not self.my_turn:
                print("It is not your turn yet.")
                return
        self.send("STATE_CHANGE", {"row": row, "column": column})


def main(argv=None):
    """Parse client options, connect to the server, and run the game client."""
    args = parse_args(argv)
    try:
        client_socket = connect_to_server(args.host, args.port)
    except socket.gaierror:
        print(f"Could not resolve server hostname: {args.host}")
        return 1
    except OSError as error:
        print(f"Could not connect to {args.host}:{args.port}: {error}")
        return 1

    print(f"Connected to {args.host}:{args.port}.")
    GameClient(client_socket).run_input_loop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())