# Dashboard walkthrough

Start `smart-home serve` and open [127.0.0.1:8766](http://127.0.0.1:8766).
The initial state is simulated; no physical devices are connected.

1. Enter `turn on lights in Bedroom` and check the bedroom lamp.
2. Enter `dim Main Light to 30` and check its brightness.
3. Run the movie-time scene and inspect the light, curtain and fan states.
4. Try a negated or misspelled command. It should refuse the action or suggest
   supported wording without changing a device.
5. Try opening the locked door. Unlock it with the configured simulator code,
   then open it and observe the five-second auto-close.
6. Filter a room, inspect activity and compare the displayed state with
   `smart-home status` when using the same explicit state file.

Use `smart-home --state-file state.json serve` when you want state to survive
server restarts. Separate commands without a state file start fresh simulations.

For scripted use, follow the [interface guide](feature-matrix.md). Run the test
suite to check the same controller policies without the browser. Optional
voice, face and serial setup is described in [hardware.md](hardware.md).
