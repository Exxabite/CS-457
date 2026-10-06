| Message | Direction | Description |
| :--- | :--- | :--- |
| CONNECT | Client $\rightarrow$ Server | Message that the client sends to join the game |
| LOBBY_WAIT | Server $\rightarrow$ Client | Server telling the client that it is still waiting for player 2 to join
| GAME_START | Server $\rightarrow$ Client | Server Message to indicate to the clients that the game has started.
| TURN | Server $\rightarrow$ Client | Server telling a specific client that it is now that players turn. 
| STATE_CHANGE | Client $\rightarrow$ Server | Client sending the players move to the server.
| STATE_ASSERT | Server $\rightarrow$ Client | Server sending the full state of the board to the clients. This message is the definitive board state sent after the server has processed a move.
| ERROR | Server $\rightarrow$ Client | Message that can indicate eny kind of error, from an invalid state message, to a in game move that breaks the rules.
| DISCONNECT | Client $\rightarrow$ Server | Client announcing that it is disconnecting. 
| GAME_OVER | Server $\rightarrow$ Client | Server anouncing the game has ended, and anouncing who wins, or if the game is a tie. |
| PLAY_AGAIN | Client $\rightarrow$ Server | Tells the server that the client wants to play again |