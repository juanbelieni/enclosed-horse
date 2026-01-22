## Enclosed Horse

Python script that solves the daily [enclose.horse](https://enclose.horse) puzzle by placing walls that maximize the score.

The `main.py` performs the following:
- Fetches the puzzle from `https://enclose.horse/play/<code>` (date or community level code).
- Uses Google OR-Tools CP-SAT to optimize wall placement.

Usage:

```bash
python main.py            # today
python main.py 2026-01-01 # specific date
python main.py abcdef     # community level code
```
