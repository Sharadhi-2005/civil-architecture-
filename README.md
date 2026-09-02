# AI Floor Plan Designer

An AI-based civil architecture design system that generates optimized
building floor plans (and eventually interior layouts + CAD export) from
high-level user requirements like plot size, room count, and design
preferences.

This repo currently implements **stage 1 of the pipeline: the Constraint
Satisfaction Problem (CSP) solver** that generates structurally valid
floor plans. Later stages (interior placement, CAD/DXF export) will build
on top of this.

## Why a CSP solver first

Floor plan generation has to satisfy *hard* constraints before anything
else matters — rooms can't overlap, they must fit inside the plot,
required adjacencies (e.g. kitchen next to dining) must hold, and rooms
needing natural light must touch an exterior wall. A CSP solver
guarantees every layout it returns is valid, which makes it a solid,
explainable foundation to build optimization (GA / simulated annealing)
and interior placement on top of later.

## How it works

- The plot is discretized into a grid.
- Each room is a CSP **variable**; its **domain** is every candidate
  rectangle (position + size) that satisfies that room's own area and
  shape rules.
- Backtracking search assigns one rectangle per room, using:
  - **MRV (Minimum Remaining Values)** heuristic — always branch on the
    room with the fewest legal placements left, so failures are
    discovered as early as possible.
  - **Forward checking** — after placing a room, immediately prune
    placements that would now be invalid for every unplaced room, and
    backtrack the moment any room's domain goes empty.
- Constraints enforced: no overlaps, stays inside the plot, declared
  adjacencies share a wall, exterior-facing rooms touch the boundary.

## Project structure

```
src/
  models.py       # Rect, Plot, Room, FloorPlanRequest data models
  csp_solver.py   # the CSP backtracking solver
  main.py         # runnable demo (generates + prints an example house)
tests/
  test_csp_solver.py
examples/
```

## Running it

```bash
pip install -r requirements.txt   # no external deps yet, stdlib only
python -m src.main
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
- [ ] Genetic Algorithm / Simulated Annealing layer — optimize among
      valid layouts for space utilization, ventilation, cost
- [ ] Rule-based interior element placement (furniture/units per room)
- [ ] Collision/overlap checks for furniture placement
- [ ] CAD export (DXF via `ezdxf`, and/or FreeCAD scripting for 3D)

## Tech stack

- Python 3 (stdlib only for the CSP solver — no dependencies to install)
- Planned: `ezdxf` for DXF/CAD export, `matplotlib` for visualization
