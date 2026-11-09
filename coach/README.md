# Coach

Post-game walkthroughs for Chess.com games.

`walkthrough.py` fetches games from the Chess.com public API and runs Stockfish over every move. It picks the moments where your winning chance dropped, labels the thinking error behind each one, and writes a Markdown walkthrough plus a JSON file. The labels are: missed their check or capture, missed your own forcing move, allowed a forced mate, didn't punish their mistake, endgame technique, and quiet move with the wrong plan.

```
pip install python-chess        # and a stockfish binary on PATH
python coach/walkthrough.py jakem-r --latest 1          # most recent game
python coach/walkthrough.py jakem-r --latest 5          # last five
python coach/walkthrough.py jakem-r --url https://www.chess.com/game/live/185860567340
```

Output goes to `reviews/`, which is ignored by git. Do your own ten-minute review without an engine first, then run this and compare.
