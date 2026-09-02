# AI Floor Plan Designer

An AI-based civil architecture design system that generates optimized
building floor plans (and eventually interior layouts + CAD export) from
high-level user requirements like plot size, room count, and design
preferences.

All 8 algorithms from the design doc are implemented:

| # | Algorithm | File |
|---|---|---|
| 1 | CSP solver (structural validity) | `src/csp_solver.py` |
| 2 | Genetic Algorithm (multi-objective optimization) | `src/genetic_algorithm.py` |
| 3 | Graph-based room adjacency modeling | `src/graph_model.py` |
| 4 | Rectangular space partitioning (BSP) | `src/bsp_partition.py` |
| 5 | Simulated Annealing (local refinement) | `src/simulated_annealing.py` |
| 6 | Rule-based interior placement | `src/interior_rules.py` |
| 7 | Collision/overlap detection (AABB + SAT) | `src/geometry_utils.py` |
| 8 | CAD export (DXF + 3D wall extrusion) | `src/cad_export.py` |

## Two independent pipelines in this repo

There are two ways to generate a floor plan here, and they're
deliberately separate:

- **CSP pipeline** (`src/main.py`) — the original backtracking solver.
  Guarantees validity by construction; doesn't optimize *among* valid
  layouts.
- **GA/BSP pipeline** (`src/demo_full_pipeline.py`) — graph model -> GA
  (searches room orderings) -> BSP (turns an ordering into geometry) ->
  simulated annealing (locally refines wall positions) -> rule-based
  furniture placement -> collision/clearance validation -> DXF export.
  This one actively optimizes for space utilization, ventilation, and
  adjacency satisfaction, and carries the layout all the way to CAD
  output with furniture.

## How each stage works

**CSP solver** — the plot is discretized into a grid; each room is a CSP
variable whose domain is every candidate rectangle satisfying its own
area/shape rules. Backtracking search assigns one rectangle per room
using MRV (branch on the room with fewest options left) and forward
checking (prune other rooms' domains the instant a room is placed,
backtrack immediately if any domain empties).

**Graph model** — rooms are nodes, required adjacencies (from
`Room.adjacent_to`) are edges — the "bubble diagram" architects sketch
before any geometry exists. Provides degree/BFS ordering and an
`adjacency_score()` used by the optimizers below.

**BSP partitioning** — recursively slices the plot in two along its
longer side, splitting an *ordered* room list into two area-proportional
groups at each cut, recursing until each group is one room. Split
fractions are stored per node so they can be perturbed later without
changing the tree structure.

**Genetic Algorithm** — searches over room *orderings* (the permutation
fed into BSP) to maximize a weighted combination of space utilization,
ventilation exposure, adjacency satisfaction, and shape quality. Uses
tournament selection, order crossover (valid for permutations), swap
mutation, and elitism.

**Simulated Annealing** — after the GA fixes a room order, SA nudges the
BSP tree's *split fractions* (continuous) to locally improve fit, using
the Metropolis criterion so it can still escape small local optima
instead of getting stuck, with a cooling schedule that makes it greedier
over time.

**Interior placement** — a rule-based expert system: explicit IF-THEN
heuristics per room type (bed against a wall, table centered, counter
along the longest wall), validated against `geometry_utils` so nothing
overlaps.

**Collision detection** — AABB overlap for the common axis-aligned case,
plus a full Separating Axis Theorem implementation for rotated furniture,
plus minimum-clearance (walkway gap) checks.

**CAD export** — writes a raw ASCII DXF (R12 entity set: POLYLINE, TEXT,
3DFACE) by hand, no external library required. Each room outline can
optionally be extruded into vertical 3D wall faces at a given wall
height.

## Project structure

```
src/
  models.py             # Rect, Plot, Room, FloorPlanRequest
  csp_solver.py          # 1. CSP backtracking solver
  genetic_algorithm.py   # 2. GA optimizer
  graph_model.py          # 3. adjacency graph / bubble diagram
  bsp_partition.py        # 4. BSP space partitioning
  simulated_annealing.py  # 5. SA refinement
  interior_rules.py       # 6. rule-based furniture placement
  geometry_utils.py       # 7. AABB + SAT collision detection
  cad_export.py            # 8. DXF export
  main.py                 # demo: CSP pipeline
  demo_full_pipeline.py    # demo: full GA/BSP pipeline, all 8 stages
  visualize.py             # matplotlib PNG rendering
tests/
  test_csp_solver.py
  test_optimizers.py
```

## Running it

```bash
pip install -r requirements.txt   # matplotlib only
python -m src.main                 # CSP pipeline
python -m src.demo_full_pipeline   # full GA/BSP pipeline (all 8 algorithms)
python -m src.visualize            # save a PNG of the CSP pipeline's plan
```

Example output:

```
Solved in 8 search steps.

Plot: 14 x 10

  bedroom2   -> x= 0 y= 0 w= 3 h= 4 (area=12)
  bedroom1   -> x= 0 y= 4 w= 3 h= 4 (area=12)
  entrance   -> x= 1 y= 8 w= 2 h= 2 (area=4)
  living     -> x= 3 y= 4 w= 3 h= 6 (area=18)
  dining     -> x= 3 y= 0 w= 3 h= 4 (area=12)
  kitchen    -> x= 6 y= 0 w= 2 h= 4 (area=8)
  bathroom   -> x= 6 y= 4 w= 2 h= 2 (area=4)

BBBDDDKK......
BBBDDDKK......
BBBDDDKK......
BBBDDDKK......
BBBLLLBB......
BBBLLLBB......
BBBLLL........
BBBLLL........
.EELLL........
.EELLL........
```

### Running tests

```bash
python -m unittest discover -s tests -v
```

## Roadmap

- [x] CSP solver — structurally valid floor plan generation
- [x] Genetic Algorithm + Simulated Annealing — optimize among valid
      layouts for space utilization, ventilation, adjacency
- [x] Rule-based interior element placement (furniture per room)
- [x] Collision/overlap checks (AABB + SAT) for furniture placement
- [x] CAD export (hand-written DXF, 2D + 3D wall extrusion)
- [ ] Merge the CSP and GA/BSP pipelines into one configurable entry point
- [ ] Door/window placement (currently assumed, not modeled)

## Tech stack

- Python 3, stdlib only for every algorithm except visualization
- `matplotlib` for PNG rendering (only external dependency)
- DXF export is hand-written (no `ezdxf` dependency) but compatible with
  it if you'd rather swap in that library
