import datetime
import re
import sys
import urllib.request

from ortools.sat.python import cp_model

MAP = ""
MAX_WALLS = 0
GRID = []
ROWS = 0
COLS = 0


HORSE = r"H"
LAND = r"\."
WATER = r"~"
WALL = r"W"
PORTAL = r"[0-9a-z]"
CHERRY = r"C"
GOLDEN_CHERRY = r"G"
BEES = r"S"


def is_(cell_type: str, cell: str) -> bool:
    return re.fullmatch(cell_type, cell) is not None


def fetch_puzzle(level_code: str) -> tuple[str, int]:
    url = f"https://enclose.horse/play/{level_code}"
    html = urllib.request.urlopen(url).read().decode("utf-8")
    map_str = (
        re.search(r'"map":"(.*?)"', html, re.S).group(1).strip().replace("\\n", "\n")
    )
    max_walls = int(re.search(r'"budget":(\d+)', html).group(1))
    return map_str, max_walls


def get_portal_exit(pos):
    i, j = pos
    cell: str = GRID[i][j]

    assert is_(PORTAL, cell), "Cell is not a portal"

    for r in range(ROWS):
        for c in range(COLS):
            if (r != i or c != j) and GRID[r][c] == cell:
                return (r, c)

    return None


def get_neighbors(pos) -> list[tuple[int, int]]:
    i, j = pos
    rows = len(GRID)
    cols = len(GRID[0])
    positions = []
    if i > 0:
        positions.append((i - 1, j))
    if i < rows - 1:
        positions.append((i + 1, j))
    if j > 0:
        positions.append((i, j - 1))
    if j < cols - 1:
        positions.append((i, j + 1))

    for ni, nj in positions.copy():
        cell: str = GRID[ni][nj]

        if is_(PORTAL, cell):
            portal_pos = get_portal_exit((ni, nj))

            if portal_pos:
                positions.append(portal_pos)

    return positions


def solve_enclose_horse() -> list[list[str]] | None:
    """Optimize wall placement to maximize reachable value under a wall limit.

    Let W[r,c] be wall, R[r,c] be reachable, D[r,c] be distance.
    For all cells:
    - R[r,c] <-> D[r,c] >= 0
    - W[r,c] -> D[r,c] = -1
    - cell is WATER -> not W[r,c] and not R[r,c] and D[r,c] = -1
    - cell in {CHERRY, GOLDEN_CHERRY, BEES, PORTAL} -> not W[r,c]
    - cell is HORSE -> D[r,c] = 0 and not W[r,c]
    - cell != HORSE -> D[r,c] != 0
    - boundary LAND and R[r,c] -> W[r,c]
    - boundary PORTAL -> R[r,c] = 0 and R[portal_exit(r,c)] = 0
    - for each neighbor n: (not W[r,c] and R[n]) -> R[r,c]
    - D[r,c] >= 1 -> exists neighbor n with R[n] and D[r,c] = D[n] + 1
    - no neighbors -> D[r,c] <= 0
    Objective: maximize sum(R) + 3 * sum(R on CHERRY), with sum(W) <= max_walls.
    Portals: any digit or lowercase letter neighbors connect to all matching cells.
    """
    max_dist = sum(1 for r in range(ROWS) for c in range(COLS) if GRID[r][c] != WATER)

    model = cp_model.CpModel()
    wall = [
        [model.new_bool_var(f"is_wall_{r}_{c}") for c in range(COLS)]
        for r in range(ROWS)
    ]
    reachable = [
        [model.new_bool_var(f"reachable_{r}_{c}") for c in range(COLS)]
        for r in range(ROWS)
    ]
    distance = [
        [model.NewIntVar(-1, max_dist, f"distance_{r}_{c}") for c in range(COLS)]
        for r in range(ROWS)
    ]

    for i in range(ROWS):
        for j in range(COLS):
            cell: str = GRID[i][j]
            neighbors = get_neighbors((i, j))
            is_boundary = i == 0 or i == ROWS - 1 or j == 0 or j == COLS - 1

            model.add(distance[i][j] >= 0).only_enforce_if(reachable[i][j])
            model.add(distance[i][j] <= -1).only_enforce_if(reachable[i][j].Not())
            model.add(distance[i][j] == -1).only_enforce_if(wall[i][j])

            if is_(WATER, cell):
                model.add(wall[i][j] == 0)
                model.add(distance[i][j] == -1)
                model.add(reachable[i][j] == 0)
                continue

            if (
                is_(CHERRY, cell)
                or is_(GOLDEN_CHERRY, cell)
                or is_(BEES, cell)
                or is_(PORTAL, cell)
            ):
                model.add(wall[i][j] == 0)

            if is_(HORSE, cell):
                model.add(reachable[i][j] == 1)
                model.add(distance[i][j] == 0)
                model.add(wall[i][j] == 0)
            else:
                model.add(distance[i][j] != 0)

            if is_boundary and is_(LAND, cell):
                model.add(wall[i][j] == 1).only_enforce_if(reachable[i][j])

            if is_boundary and is_(PORTAL, cell):
                en, ej = get_portal_exit((i, j))

                model.add(reachable[i][j] == 0)
                model.add(reachable[en][ej] == 0)

            for nr, nc in neighbors:
                model.add(reachable[i][j] == 1).only_enforce_if(
                    wall[i][j].Not(), reachable[nr][nc]
                )

            is_positive = model.new_bool_var(f"is_positive_{i}_{j}")
            model.add(distance[i][j] >= 1).only_enforce_if(is_positive)
            model.add(distance[i][j] <= 0).only_enforce_if(is_positive.Not())

            preds = []
            for nr, nc in neighbors:
                pred = model.new_bool_var(f"pred_{i}_{j}_{nr}_{nc}")
                model.add(distance[i][j] == distance[nr][nc] + 1).only_enforce_if(pred)
                model.add(reachable[nr][nc] == 1).only_enforce_if(pred)
                preds.append(pred)

            if preds:
                model.add_bool_or(preds).only_enforce_if(is_positive)
            else:
                model.add(is_positive == 0)

    model.add(sum(wall[r][c] for r in range(ROWS) for c in range(COLS)) <= MAX_WALLS)

    score = 0

    for r in range(ROWS):
        for c in range(COLS):
            cell: str = GRID[r][c]
            score += reachable[r][c]

            if is_(CHERRY, cell):
                score += reachable[r][c] * 3
            elif is_(GOLDEN_CHERRY, cell):
                score += reachable[r][c] * 10
            elif is_(BEES, cell):
                score += reachable[r][c] * -5

    model.maximize(score)

    solver = cp_model.CpSolver()
    status = solver.Solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        print("unsat")
        return None

    print(
        "Walls used:",
        sum(1 for r in range(ROWS) for c in range(COLS) if solver.Value(wall[r][c])),
    )
    print("Objective value:", int(solver.ObjectiveValue()))

    return [
        [WALL if solver.Value(wall[r][c]) else GRID[r][c] for c in range(COLS)]
        for r in range(ROWS)
    ], [[solver.Value(reachable[r][c]) for c in range(COLS)] for r in range(ROWS)]


def render_grid(grid: list[list[str]]) -> str:
    emojis = {
        HORSE: "🐴",
        LAND: "🟩",
        WATER: "🟦",
        WALL: "🟥",
        PORTAL: "🌀",
        CHERRY: "🍒",
        GOLDEN_CHERRY: "💰",
        BEES: "🐝",
    }
    lines = []
    for row in grid:
        cells = []
        for cell in row:
            for cell_type, emoji in emojis.items():
                if is_(cell_type, cell):
                    cells.append(emoji)
                    break

        lines.append("".join(cells))
    return "\n".join(lines)


def render_reachable(grid: list[list[str]], reachable: list[list[bool]]) -> str:
    lines = []
    for r in range(len(grid)):
        cells = []
        for c in range(len(grid[0])):
            if reachable[r][c]:
                cells.append("✅")
            else:
                cells.append("❌")
        lines.append("".join(cells))
    return "\n".join(lines)


if __name__ == "__main__":
    level_code = sys.argv[1] if len(sys.argv) > 1 else datetime.date.today().isoformat()
    MAP, MAX_WALLS = fetch_puzzle(level_code)
    GRID = [list(line) for line in MAP.strip().split("\n")]
    ROWS = len(GRID)
    COLS = len(GRID[0])

    solved_grid, reachable = solve_enclose_horse()

    print(render_grid(solved_grid))
    print(render_reachable(solved_grid, reachable))
