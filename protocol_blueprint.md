| Message | Direction | Description | Example JSON Message |
| :--- | :--- | :--- | :--- |
| CONNECT | Client $\rightarrow$ Server | Message that the client sends to join the game | `{"message":"CONNECT","payload":{}}` |
| LOBBY_WAIT | Server $\rightarrow$ Client | Server telling a client that it is waiting for another player or a rematch vote | `{"message":"LOBBY_WAIT","payload":{"players_waiting":1,"players_needed":2,"phase":"LOBBY"}}` |
| GAME_START | Server $\rightarrow$ Client | Server message to indicate to the clients that the game has started | `{"message":"GAME_START","payload":{"your_symbol":"X","starting_player":"X","board":[[null,null,null],[null,null,null],[null,null,null]]}}` |
| TURN | Server $\rightarrow$ Client | Server telling a specific client that it is now that player's turn | `{"message":"TURN","payload":{"player":"X"}}` |
| STATE_CHANGE | Client $\rightarrow$ Server | Client sending the player's move to the server | `{"message":"STATE_CHANGE","payload":{"row":0,"column":2}}` |
| STATE_ASSERT | Server $\rightarrow$ Client | Server sending the full state of the board to the clients; this is the definitive board state after the server has processed a move | `{"message":"STATE_ASSERT","payload":{"board":[["X",null,null],[null,"O",null],[null,null,null]],"next_turn":"X"}}` |
| ERROR | Server $\rightarrow$ Client | Message that can indicate any kind of error, from an invalid state message to a move that breaks the rules | `{"message":"ERROR","payload":{"code":"NOT_YOUR_TURN","reason":"It is O's turn"}}` |
| DISCONNECT | Client $\rightarrow$ Server | Client announcing that it is disconnecting | `{"message":"DISCONNECT","payload":{"reason":"QUIT"}}` |
| GAME_OVER | Server $\rightarrow$ Client | Server announcing the game has ended and who wins, or whether it is a tie | `{"message":"GAME_OVER","payload":{"result":"WIN","winner":"X"}}` |
| PLAY_AGAIN | Client $\rightarrow$ Server | Tells the server that the client wants to play again | `{"message":"PLAY_AGAIN","payload":{"accept":true}}` |

Coordinates in `STATE_CHANGE` are zero-based, from 0 to 2. Empty board cells are represented by `null`. The server identifies the sender from the connection and assigns player symbols; the `GAME_START` example is the message sent to the client assigned `X`.

## Wire Framing

Each JSON message is UTF-8 encoded and prefixed by a 4-byte unsigned big-endian integer containing the JSON byte length. The maximum JSON payload is 65,536 bytes. TCP reads may split a frame or contain multiple frames; implementations must buffer and decode complete frames before parsing JSON.

`LOBBY_WAIT` uses `phase: "LOBBY"` while waiting for a second player and `phase: "REMATCH"` while waiting for the other player's rematch vote. `STATE_ASSERT.next_turn` is `null` after a win or draw. A declined rematch clears both votes and sends `ERROR` with code `REMATCH_DECLINED` to both players.

Common `ERROR` codes are `ALREADY_CONNECTED`, `BAD_MESSAGE`, `BUSY`, `CELL_OCCUPIED`, `GAME_NOT_ACTIVE`, `GAME_NOT_OVER`, `INVALID_MESSAGE`, `NOT_CONNECTED`, `NOT_YOUR_TURN`, and `REMATCH_DECLINED`. A client must send `CONNECT` before any other game message. The server rejects a third player with `BUSY`; it never trusts a player identity supplied by a client.