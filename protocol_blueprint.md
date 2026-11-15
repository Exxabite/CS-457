| Message | Direction | Description | Example JSON Message |
| :--- | :--- | :--- | :--- |
| CONNECT | Client $\rightarrow$ Server | Message that the client sends to join the game | `{"message":"CONNECT","payload":{}}` |
| LOBBY_WAIT | Server $\rightarrow$ Client | Server telling the client that it is still waiting for player 2 to join | `{"message":"LOBBY_WAIT","payload":{"players_waiting":1,"players_needed":2}}` |
| GAME_START | Server $\rightarrow$ Client | Server message to indicate to the clients that the game has started | `{"message":"GAME_START","payload":{"your_symbol":"X","starting_player":"X","board":[[null,null,null],[null,null,null],[null,null,null]]}}` |
| TURN | Server $\rightarrow$ Client | Server telling a specific client that it is now that player's turn | `{"message":"TURN","payload":{"player":"X"}}` |
| STATE_CHANGE | Client $\rightarrow$ Server | Client sending the player's move to the server | `{"message":"STATE_CHANGE","payload":{"row":0,"column":2}}` |
| STATE_ASSERT | Server $\rightarrow$ Client | Server sending the full state of the board to the clients; this is the definitive board state after the server has processed a move | `{"message":"STATE_ASSERT","payload":{"board":[["X",null,null],[null,"O",null],[null,null,null]],"next_turn":"X"}}` |
| ERROR | Server $\rightarrow$ Client | Message that can indicate any kind of error, from an invalid state message to a move that breaks the rules | `{"message":"ERROR","payload":{"code":"NOT_YOUR_TURN","reason":"It is O's turn"}}` |
| DISCONNECT | Client $\rightarrow$ Server | Client announcing that it is disconnecting | `{"message":"DISCONNECT","payload":{"reason":"QUIT"}}` |
| GAME_OVER | Server $\rightarrow$ Client | Server announcing the game has ended and who wins, or whether it is a tie | `{"message":"GAME_OVER","payload":{"result":"WIN","winner":"X"}}` |
| PLAY_AGAIN | Client $\rightarrow$ Server | Tells the server that the client wants to play again | `{"message":"PLAY_AGAIN","payload":{"accept":true}}` |

Coordinates in `STATE_CHANGE` are zero-based, from 0 to 2. Empty board cells are represented by `null`. The server identifies the sender from the connection and assigns player symbols; the `GAME_START` example is the message sent to the client assigned `X`.