import socket
import struct
import subprocess
import sys
import unittest
from collections import deque
from pathlib import Path

from code.protocol import FrameDecoder, decode_message, encode_message


ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "code" / "server.py"


class TestClient:
    def __init__(self, client_socket):
        self.socket = client_socket
        self.decoder = FrameDecoder()
        self.pending = deque()

    def send(self, message_type, payload):
        self.socket.sendall(encode_message(message_type, payload))

    def receive(self):
        while not self.pending:
            data = self.socket.recv(4096)
            if not data:
                raise AssertionError("Server closed the connection unexpectedly.")
            self.pending.extend(
                decode_message(frame) for frame in self.decoder.feed(data)
            )
        return self.pending.popleft()

    def receive_type(self, message_type):
        message = self.receive()
        if message["message"] != message_type:
            raise AssertionError(f"Expected {message_type}, received {message}.")
        return message

    def close(self):
        self.socket.close()


class ServerIntegrationTests(unittest.TestCase):
    def setUp(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind(("127.0.0.1", 0))
            self.port = probe.getsockname()[1]

        self.process = subprocess.Popen(
            [sys.executable, "-u", str(SERVER), "-p", str(self.port)],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        startup = self.process.stdout.readline()
        self.assertIn("Server listening", startup)
        self.clients = []

    def tearDown(self):
        for client in self.clients:
            client.close()
        self.process.terminate()
        self.process.wait(timeout=5)
        self.process.stdout.close()

    def connect_client(self):
        client_socket = socket.create_connection(("127.0.0.1", self.port), timeout=3)
        client_socket.settimeout(3)
        client = TestClient(client_socket)
        self.clients.append(client)
        return client

    def test_multiplayer_lifecycle(self):
        player_x = self.connect_client()
        player_x.socket.sendall(struct.pack("!I", 3) + b"bad")
        self.assertEqual(player_x.receive_type("ERROR")["payload"]["code"], "BAD_MESSAGE")
        player_x.send("CONNECT", {})
        player_x.receive_type("LOBBY_WAIT")

        player_o = self.connect_client()
        player_o.send("CONNECT", {})
        self.assertEqual(player_x.receive_type("GAME_START")["payload"]["your_symbol"], "X")
        self.assertEqual(player_o.receive_type("GAME_START")["payload"]["your_symbol"], "O")
        self.assertEqual(player_x.receive_type("TURN")["payload"]["player"], "X")

        player_o.send("STATE_CHANGE", {"row": 2, "column": 2})
        self.assertEqual(player_o.receive_type("ERROR")["payload"]["code"], "NOT_YOUR_TURN")

        for player, row, column, next_player in [
            (player_x, 0, 0, player_o),
            (player_o, 1, 0, player_x),
            (player_x, 0, 1, player_o),
            (player_o, 1, 1, player_x),
        ]:
            player.send("STATE_CHANGE", {"row": row, "column": column})
            player_x.receive_type("STATE_ASSERT")
            player_o.receive_type("STATE_ASSERT")
            next_player.receive_type("TURN")

        player_x.send("STATE_CHANGE", {"row": 0, "column": 2})
        player_x.receive_type("STATE_ASSERT")
        player_o.receive_type("STATE_ASSERT")
        self.assertEqual(player_x.receive_type("GAME_OVER")["payload"]["winner"], "X")
        self.assertEqual(player_o.receive_type("GAME_OVER")["payload"]["winner"], "X")

        third_player = self.connect_client()
        third_player.send("CONNECT", {})
        self.assertEqual(third_player.receive_type("ERROR")["payload"]["code"], "BUSY")

        player_x.send("PLAY_AGAIN", {"accept": True})
        self.assertEqual(player_x.receive_type("LOBBY_WAIT")["payload"]["phase"], "REMATCH")
        player_o.send("PLAY_AGAIN", {"accept": True})
        player_x.receive_type("GAME_START")
        player_o.receive_type("GAME_START")
        player_x.receive_type("TURN")

        player_o.send("DISCONNECT", {"reason": "QUIT"})
        self.assertEqual(player_x.receive_type("LOBBY_WAIT")["payload"]["phase"], "LOBBY")

        replacement = self.connect_client()
        replacement.send("CONNECT", {})
        player_x.receive_type("GAME_START")
        replacement.receive_type("GAME_START")
        player_x.receive_type("TURN")


if __name__ == "__main__":
    unittest.main()