## Concurrency
For this project I use Python's `selectors` module to handle concurrent TCP connections without a worker thread per client. The server can accept connections, while one game session has exactly two player slots. A third client that sends `CONNECT` while both slots are occupied receives a `BUSY` error.

Each socket has an incremental frame decoder and an output buffer. Complete JSON messages are tagged with their originating connection and placed on one message queue. The selector loop processes that queue sequentially, keeping all game-state changes on one thread. Partial reads and writes are handled without blocking other clients.

The game logic validates the sender, current turn, coordinates, and cell occupancy before changing the board. Invalid or out-of-turn moves receive an error without mutating state. Malformed frames or JSON are rejected before reaching the game logic. The server broadcasts the complete board after each accepted move and sends `TURN` to the next player when the game continues.


## Shared Resources
The server is authoritative for the board and current turn. The first accepted player is X and always moves first. After validating a move, the server updates its board, sends the full board to both clients, then sends `TURN` to the next player if the game has not ended. On disconnect, the server releases the player's slot, resets the session, and returns the other connected player to the waiting lobby.
