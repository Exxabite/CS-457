import unittest

from code.game import GameSession


def actions_for(actions, recipient):
    return [action for action in actions if action.recipient == recipient]


class GameSessionTests(unittest.TestCase):
    def setUp(self):
        self.game = GameSession()
        self.game.connect("player_one")
        self.game.connect("player_two")

    def move(self, player, row, column):
        return self.game.handle(player, "STATE_CHANGE", {"row": row, "column": column})

    def test_first_connected_player_is_x_and_starts(self):
        self.assertEqual(self.game.players["player_one"], "X")
        self.assertEqual(self.game.players["player_two"], "O")
        self.assertEqual(self.game.current_turn, "X")
        self.assertEqual(self.game.phase, "PLAYING")

    def test_rejects_out_of_turn_and_occupied_cell_without_mutating_board(self):
        original_board = [row.copy() for row in self.game.board]
        error = self.move("player_two", 0, 0)[0]
        self.assertEqual(error.payload["code"], "NOT_YOUR_TURN")
        self.assertEqual(self.game.board, original_board)

        self.move("player_one", 0, 0)
        original_board = [row.copy() for row in self.game.board]
        error = self.move("player_two", 0, 0)[0]
        self.assertEqual(error.payload["code"], "CELL_OCCUPIED")
        self.assertEqual(self.game.board, original_board)
        self.assertEqual(self.game.current_turn, "O")

    def test_detects_win_and_broadcasts_final_state(self):
        for player, row, column in [
            ("player_one", 0, 0),
            ("player_two", 1, 0),
            ("player_one", 0, 1),
            ("player_two", 1, 1),
        ]:
            self.move(player, row, column)

        actions = self.move("player_one", 0, 2)
        game_over = [action for action in actions if action.message == "GAME_OVER"]
        self.assertEqual(len(game_over), 2)
        self.assertTrue(all(action.payload == {"result": "WIN", "winner": "X"} for action in game_over))
        self.assertEqual(self.game.phase, "GAME_OVER")
        self.assertIsNone(self.game.current_turn)

    def test_detects_draw(self):
        moves = [
            ("player_one", 0, 0),
            ("player_two", 0, 1),
            ("player_one", 0, 2),
            ("player_two", 1, 1),
            ("player_one", 1, 0),
            ("player_two", 1, 2),
            ("player_one", 2, 1),
            ("player_two", 2, 0),
            ("player_one", 2, 2),
        ]
        actions = []
        for player, row, column in moves:
            actions = self.move(player, row, column)

        game_over = [action for action in actions if action.message == "GAME_OVER"]
        self.assertEqual(len(game_over), 2)
        self.assertTrue(all(action.payload == {"result": "DRAW", "winner": None} for action in game_over))

    def test_requires_both_players_for_rematch_and_resets_board(self):
        self.move("player_one", 0, 0)
        self.move("player_two", 1, 0)
        self.move("player_one", 0, 1)
        self.move("player_two", 1, 1)
        self.move("player_one", 0, 2)

        waiting = self.game.handle("player_one", "PLAY_AGAIN", {"accept": True})
        self.assertEqual(waiting[0].message, "LOBBY_WAIT")
        self.assertEqual(self.game.phase, "GAME_OVER")

        started = self.game.handle("player_two", "PLAY_AGAIN", {"accept": True})
        self.assertEqual(self.game.phase, "PLAYING")
        self.assertEqual(self.game.current_turn, "X")
        self.assertEqual(self.game.board, [[None] * 3 for _ in range(3)])
        self.assertEqual(len([action for action in started if action.message == "GAME_START"]), 2)

    def test_disconnect_returns_remaining_player_to_waiting(self):
        actions = self.game.disconnect("player_two")
        self.assertEqual(self.game.phase, "WAITING")
        self.assertEqual(self.game.players, {"player_one": "X"})
        self.assertEqual(actions[0].recipient, "player_one")
        self.assertEqual(actions[0].message, "LOBBY_WAIT")

    def test_rejects_third_player(self):
        actions = self.game.connect("player_three")
        self.assertEqual(actions[0].message, "ERROR")
        self.assertEqual(actions[0].payload["code"], "BUSY")


if __name__ == "__main__":
    unittest.main()