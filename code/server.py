"""Selector-based TCP server for the two-player Tic Tac Toe game."""

import argparse
from dataclasses import dataclass, field
import queue
import selectors
import socket

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


def start_server(port):
    selector = selectors.DefaultSelector()
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, port))
    server.listen()
    server.setblocking(False)

    clients = {}
    game = GameSession()
    message_queue = queue.Queue()
    selector.register(server, selectors.EVENT_READ)

    def update_events(client_socket):
        state = clients.get(client_socket)
        if state is None:
            return

        events = 0
        if not state.close_after_write:
            events |= selectors.EVENT_READ
        if state.output:
            events |= selectors.EVENT_WRITE
        if events == 0:
            close_connection(client_socket)
            return

        try:
            selector.modify(client_socket, events, state)
        except (KeyError, OSError):
            close_connection(client_socket)

    def close_connection(client_socket):
        state = clients.pop(client_socket, None)
        if state is None:
            return

        try:
            selector.unregister(client_socket)
        except (KeyError, ValueError):
            pass
        try:
            client_socket.close()
        except OSError:
            pass

        print(f"[-] Client disconnected: {state.address}")
        if state.joined:
            deliver_actions(game.disconnect(client_socket))

    def queue_message(client_socket, message_type, payload):
        state = clients.get(client_socket)
        if state is None or state.close_after_write:
            return
        try:
            frame = encode_message(message_type, payload)
        except ProtocolError as error:
            print(f"[!] Could not encode {message_type}: {error}")
            close_connection(client_socket)
            return

        if len(state.output) + len(frame) > MAX_PENDING_OUTPUT:
            state.output.clear()
            state.close_after_write = True
        else:
            state.output.extend(frame)
        update_events(client_socket)

    def deliver_actions(actions):
        for action in actions:
            queue_message(action.recipient, action.message, action.payload)

    def handle_message(client_socket, message):
        state = clients.get(client_socket)
        if state is None:
            return

        message_type = message["message"]
        if not state.joined:
            if message_type != "CONNECT":
                queue_message(
                    client_socket,
                    "ERROR",
                    {"code": "NOT_CONNECTED", "reason": "Send CONNECT before playing."},
                )
                return

            actions = game.connect(client_socket)
            is_busy = any(
                action.message == "ERROR" and action.payload.get("code") == "BUSY"
                for action in actions
            )
            if not is_busy:
                state.joined = True
            deliver_actions(actions)
            if is_busy:
                state.close_after_write = True
                update_events(client_socket)
            return

        if message_type == "DISCONNECT":
            deliver_actions(game.handle(client_socket, message_type, message["payload"]))
            close_connection(client_socket)
            return

        deliver_actions(game.handle(client_socket, message_type, message["payload"]))

    def process_messages():
        while True:
            try:
                event, client_socket, content = message_queue.get_nowait()
            except queue.Empty:
                return

            if client_socket not in clients:
                continue
            if event == "message":
                handle_message(client_socket, content)
            elif event == "protocol_error":
                queue_message(
                    client_socket,
                    "ERROR",
                    {"code": "BAD_MESSAGE", "reason": content},
                )
                if content == "Invalid or oversized frame length.":
                    state = clients.get(client_socket)
                    if state is not None:
                        state.close_after_write = True
                        update_events(client_socket)
            elif event == "disconnect":
                close_connection(client_socket)

    try:
        print(f"[*] Server listening on {HOST}:{port}")
        while True:
            for key, mask in selector.select():
                if key.fileobj is server:
                    while True:
                        try:
                            client_socket, address = server.accept()
                        except BlockingIOError:
                            break

                        client_socket.setblocking(False)
                        clients[client_socket] = ClientConnection(address)
                        selector.register(
                            client_socket,
                            selectors.EVENT_READ,
                            clients[client_socket],
                        )
                        print(f"[+] Client connected: {address}")
                    continue

                client_socket = key.fileobj
                state = clients.get(client_socket)
                if state is None:
                    continue

                if mask & selectors.EVENT_READ:
                    try:
                        data = client_socket.recv(4096)
                    except (ConnectionResetError, OSError):
                        message_queue.put(("disconnect", client_socket, None))
                    else:
                        if not data:
                            message_queue.put(("disconnect", client_socket, None))
                        else:
                            try:
                                frames = state.decoder.feed(data)
                                for frame in frames:
                                    try:
                                        message = decode_message(frame)
                                    except ProtocolError as error:
                                        message_queue.put(
                                            ("protocol_error", client_socket, str(error))
                                        )
                                    else:
                                        message_queue.put(("message", client_socket, message))
                            except ProtocolError as error:
                                message_queue.put(
                                    ("protocol_error", client_socket, str(error))
                                )

                if mask & selectors.EVENT_WRITE:
                    try:
                        sent = client_socket.send(state.output)
                    except (ConnectionResetError, OSError):
                        message_queue.put(("disconnect", client_socket, None))
                    else:
                        del state.output[:sent]
                        if state.close_after_write and not state.output:
                            message_queue.put(("disconnect", client_socket, None))
                        else:
                            update_events(client_socket)

            process_messages()
    except KeyboardInterrupt:
        print("\n[*] Shutting down server.")
    finally:
        for client_socket in list(clients):
            try:
                selector.unregister(client_socket)
            except (KeyError, ValueError):
                pass
            client_socket.close()
        selector.close()
        server.close()


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