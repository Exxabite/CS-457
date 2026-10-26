## Concurrency
For this project I plan on using selectors to handle concurrency.
The server be able to establish a network connection with an arbitrary amount of clients, but the game logic system will only support two. Once two clients have succesfully connected, the game will start. 
The server will process all messages sent from either client on a single message queue, than records both the message content, and the client it came from. 
With this queue the server can run all of the game logic for both players on a single thread.
By simply reading the next message, checking if that player is allowed to make that move, updating state accordingly and sending the results back it can keep track of all nescicary game state for both players.
If a player makes a move out of turn, the server will know that the client is sending an out of turn move, and will send back an error without changing any game state, before moving on to the next message in the queue.
The details of the network connections will be handled by a sepperate part of the server than the game loop.
Because the game loop can proccess a message from any client at any time, it wont be confused by invalid or out of turn messages.
The server will only update state if a message describes an action that can legally be taken at a given time, any other requests will be responded to with an error. If the network handeler receives a malformed packet, it will send back an error to the client without sending a message to the game loop.


## Shared Resources
Since Tic Tac Toe is turn based, this makes keeping state in sync much easier than it would be for a real time game. The main game data that needs to be kept in sync is the state of the board and who's turn it is.
To keep this data in sync the server will start by picking and recording which player will go first.
That player will be sent a TURN message indicating that it is now their turn. 
Once that player makes a move, the server will verify the move and if it is valid, the server wil update its copy of the board, send the full board state to both clients, flip its internal record of whos turn it is, and send the other player a TURN message.
