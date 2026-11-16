"""Selector-based TCP server for the two-player Tic Tac Toe game."""

import argparse
import queue
import selectors
import socket
from dataclasses import dataclass, field

if __package__:
    from .game import GameSession
    from .protocol import FrameDecoder, ProtocolError, decode_message, encode_message
else:
    from game import GameSession
    from protocol import FrameDecoder, ProtocolError, decode_message, encode_message

HOST = "0.0.0.0"
MAX_PENDING_OUTPUT = 256 * 1024


@dataclass
class ClientConnection:
    address: tuple
    decoder: FrameDecoder = field(default_factory=FrameDecoder)
    output: bytearray = field(default_factory=bytearray)
    joined: bool = False
    close_after_write: bool = False


def parse_port(value):
    try:
        port = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("port must be an integer") from error
    if not 1024 <= port <= 65535:
        raise argparse.ArgumentTypeError("port must be between 1024 and 65535")
    return port


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Run the Tic Tac Toe game server.")
    parser.add_argument("-p", "--port", required=True, type=parse_port)
    return parser.parse_args(argv)


class GameServer:
    def __init__(self, port):
        self.selector = selectors.DefaultSelector()
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind((HOST, port))
        self.server.listen()
        self.server.setblocking(False)

        self.clients = {}
        self.game = GameSession()
        self.message_queue = queue.Queue()
        self.selector.register(self.server, selectors.EVENT_READ)

    def run(self):
        try:
            print(f"[*] Server listening on {HOST}:{self.server.getsockname()[1]}")
            while True:
                for key, mask in self.selector.select():
                    if key.fileobj is self.server:
                        self._accept_clients()
                    else:
                        self._handle_client_event(key.fileobj, mask)
                self._process_messages()
        except KeyboardInterrupt:
            print("\n[*] Shutting down server.")
        finally:
            self.close()

    def close(self):
        for client_socket in list(self.clients):
            try:
                self.selector.unregister(client_socket)
            except (KeyError, ValueError):
                pass
            client_socket.close()
        self.selector.close()
        self.server.close()

    def _accept_clients(self):
        while True:
            try:
                client_socket, address = self.server.accept()
            except BlockingIOError:
                return

            client_socket.setblocking(False)
            state = ClientConnection(address)
            self.clients[client_socket] = state
            self.selector.register(client_socket, selectors.EVENT_READ, state)
            print(f"[+] Client connected: {address}")

    def _handle_client_event(self, client_socket, mask):
        if client_socket not in self.clients:
            return
        if mask & selectors.EVENT_READ:
            self._read_client(client_socket)
        if mask & selectors.EVENT_WRITE:
            self._write_client(client_socket)

    def _read_client(self, client_socket):
        state = self.clients.get(client_socket)
        if state is None:
            return

        try:
            data = client_socket.recv(4096)
        except (ConnectionResetError, OSError):
            self.message_queue.put(("disconnect", client_socket, None))
            return
        if not data:
            self.message_queue.put(("disconnect", client_socket, None))
            return

        try:
            frames = state.decoder.feed(data)
            for frame in frames:
                try:
                    message = decode_message(frame)
                except ProtocolError as error:
                    self.message_queue.put(("protocol_error", client_socket, str(error)))
                else:
                    self.message_queue.put(("message", client_socket, message))
        except ProtocolError as error:
            self.message_queue.put(("protocol_error", client_socket, str(error)))

    def _write_client(self, client_socket):
        state = self.clients.get(client_socket)
        if state is None:
            return

        try:
            sent = client_socket.send(state.output)
        except (ConnectionResetError, OSError):
            self.message_queue.put(("disconnect", client_socket, None))
            return

        del state.output[:sent]
        if state.close_after_write and not state.output:
            self.message_queue.put(("disconnect", client_socket, None))
        else:
            self._update_events(client_socket)

    def _process_messages(self):
        while True:
            try:
                event, client_socket, content = self.message_queue.get_nowait()
            except queue.Empty:
                return

            if client_socket not in self.clients:
                continue
            if event == "message":
                self._handle_message(client_socket, content)
            elif event == "protocol_error":
                self._queue_message(
                    client_socket,
                    "ERROR",
                    {"code": "BAD_MESSAGE", "reason": content},
                )
                if content == "Invalid or oversized frame length.":
                    state = self.clients.get(client_socket)
                    if state is not None:
                        state.close_after_write = True
                        self._update_events(client_socket)
            elif event == "disconnect":
                self._close_connection(client_socket)

    def _handle_message(self, client_socket, message):
        state = self.clients.get(client_socket)
        if state is None:
            return

        message_type = message["message"]
        if not state.joined:
            self._handle_unjoined_message(client_socket, state, message_type)
            return

        if message_type == "DISCONNECT":
            actions = self.game.handle(client_socket, message_type, message["payload"])
            self._deliver_actions(actions)
            self._close_connection(client_socket)
            return

        actions = self.game.handle(client_socket, message_type, message["payload"])
        self._deliver_actions(actions)

    def _handle_unjoined_message(self, client_socket, state, message_type):
        if message_type != "CONNECT":
            self._queue_message(
                client_socket,
                "ERROR",
                {"code": "NOT_CONNECTED", "reason": "Send CONNECT before playing."},
            )
            return

        actions = self.game.connect(client_socket)
        is_busy = any(
            action.message == "ERROR" and action.payload.get("code") == "BUSY"
            for action in actions
        )
        if not is_busy:
            state.joined = True
        self._deliver_actions(actions)
        if is_busy:
            state.close_after_write = True
            self._update_events(client_socket)

    def _deliver_actions(self, actions):
        for action in actions:
            self._queue_message(action.recipient, action.message, action.payload)

    def _queue_message(self, client_socket, message_type, payload):
        state = self.clients.get(client_socket)
        if state is None or state.close_after_write:
            return
        try:
            frame = encode_message(message_type, payload)
        except ProtocolError as error:
            print(f"[!] Could not encode {message_type}: {error}")
            self._close_connection(client_socket)
            return

        if len(state.output) + len(frame) > MAX_PENDING_OUTPUT:
            state.output.clear()
            state.close_after_write = True
        else:
            state.output.extend(frame)
        self._update_events(client_socket)

    def _update_events(self, client_socket):
        state = self.clients.get(client_socket)
        if state is None:
            return

        events = 0
        if not state.close_after_write:
            events |= selectors.EVENT_READ
        if state.output:
            events |= selectors.EVENT_WRITE
        if events == 0:
            self._close_connection(client_socket)
            return

        try:
            self.selector.modify(client_socket, events, state)
        except (KeyError, OSError):
            self._close_connection(client_socket)

    def _close_connection(self, client_socket):
        state = self.clients.pop(client_socket, None)
        if state is None:
            return

        try:
            self.selector.unregister(client_socket)
        except (KeyError, ValueError):
            pass
        try:
            client_socket.close()
        except OSError:
            pass

        print(f"[-] Client disconnected: {state.address}")
        if state.joined:
            self._deliver_actions(self.game.disconnect(client_socket))


def start_server(port):
    GameServer(port).run()


def main(argv=None):
    args = parse_args(argv)
    try:
        start_server(args.port)
    except OSError as error:
        print(f"Server error: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())