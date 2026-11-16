```mermaid
stateDiagram-v2
    [*] --> INIT
    INIT --> Waiting
    Waiting --> Waiting: [first player connects] assign X slot; send LOBBY_WAIT
    Waiting --> Game_Start: [second player connects] assign O slot
    Game_Start --> Player_Turn: reset board; X starts; send GAME_START and TURN to X
    Player_Turn --> Evaluate_Move: [current player submits STATE_CHANGE]
    Evaluate_Move --> Player_Turn: [sender is not current player] send ERROR, keep current turn
    Evaluate_Move --> Player_Turn: [cell is invalid or occupied] send ERROR, keep current turn
    Evaluate_Move --> Player_Turn: [valid move, no win or draw] update board, broadcast STATE_ASSERT, switch turn, send TURN
    Evaluate_Move --> Game_Over: [valid move wins] update board, broadcast STATE_ASSERT, send GAME_OVER with winner
    Evaluate_Move --> Game_Over: [valid move fills board with no winner] update board, broadcast STATE_ASSERT, send GAME_OVER as draw
    Game_Over --> End_Lobby: [a player accepts PLAY_AGAIN] record vote; send LOBBY_WAIT with phase REMATCH
    End_Lobby --> Game_Start: [both players accept PLAY_AGAIN] reset board; X starts
    End_Lobby --> Game_Over: [a player declines PLAY_AGAIN] clear votes; send REMATCH_DECLINED error to both
    Waiting --> Waiting: [a player disconnects] release slot
    Player_Turn --> Waiting: [a player disconnects] reset game; release slot; send LOBBY_WAIT to survivor
    Game_Over --> Waiting: [a player disconnects] reset game; release slot; send LOBBY_WAIT to survivor
    End_Lobby --> Waiting: [a player disconnects] reset game; release slot; send LOBBY_WAIT to survivor
```
