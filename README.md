## Enclosed Horse

Python script that solves the daily [enclose.horse](https://enclose.horse) puzzle by placing walls that maximize the score.

Scoring and rules modeled:
- Reachability starts from the horse and spreads through 4-neighbor adjacency plus portal links.
- Portals are paired by matching digit/lowercase letter; stepping onto a portal connects to its exit.
- Boundary land, cherries, golden cherries, and bees are forced unreachable.
- Boundary portals are forced unreachable along with their paired exits.
- Score = reachable cells + 3 per reachable cherry + 10 per reachable golden cherry - 5 per reachable bees.

The `main.py` performs the following:
- Fetches the puzzle from `https://enclose.horse/play/<code>` (date or community level code).
- Uses Google OR-Tools CP-SAT to optimize wall placement.

Usage:

```bash
python main.py            # today
python main.py 2026-01-01 # specific date
python main.py abcdef     # community level code
```
