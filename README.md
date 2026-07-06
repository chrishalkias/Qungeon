# Quantum puzzle game (Qungeon)
Simple puzzle game, reach the end to complete a level. This can be done by using gates in your toolbar ("bag") to manipulating the quantum state of pillars.
The player has to be next to an object to interact with it!

# Unitary Libary
The game was made using the Unitary library, which handles most of the quantum logic. More information can be found at:
https://github.com/quantumlib/unitary

Game examples can be found on this page and explanation on how to make use of the library.

# How to setup and start
Requires python3.8 or higher

First create a virtual environment and install the requirements.txt for example: 
  python3 -m venv QungeonEnv                    (creates the environment)
  source QungeonEnv/bin/activate                (activates environment)
  pip install -r requirements.txt               (installs the required packages)

After doing the above the game can be played by doing:
  python Qungeon.py

# Controls
Below are the controls for the game.

WASD - movement
R - Restart level
Q - Quit game

Click and drag gates from your inventory onto quantum objects to change their states.
A blue pillar is in state |1>, a white/transparent pillar is in a pure |0> state, when a pillar is red it is very close to |0>.
Entangled pillars can be seen by hovering over them with your mouse, lines will be drawn towards the entangled objects. 


