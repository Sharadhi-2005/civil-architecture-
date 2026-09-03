# AI Floor Plan Designer

An AI-based civil architecture design system that generates optimized
building floor plans from high-level requirements (plot size, room
list, area/adjacency constraints), then carries that layout through
to a 3D mesh, a CAD file, and a compliance/materials PDF report.

## Algorithms and where they live

| # | Algorithm | File |
|---|---|---|
| 1 | CSP solver (backtracking + MRV + forward checking) | `src/csp_generator.py` |
| 2 | Simulated Annealing (local layout refinement) | `src/csp_generator.py` |
| 3 | Graph-based room adjacency modeling (bubble diagram) | `src/graph_model.py` |
| 4 | 3D mesh generation (wall/floor extrusion to OBJ) | `src/mesh_generator.py` |
| 5 | CAD export (hand-written DXF, 2D + 3D wall extrusion) | `src/cad_export.py` |
| 6 | Compliance checks + material estimation + PDF report | `src/report_generator.py` |

`src/models.py` holds the shared data classes (`Rect`, `Plot`, `Room`)
used across the project — it has no logic of its own to run.

## How each stage works

**CSP solver** (`csp_generator.py`, `CSPFloorPlanGenerator`) — the plot
is discretized on a grid; each room is a CSP variable whose domain is
every candidate rectangle satisfying its own area/dimension rules.
Backtracking search assigns one rectangle per room using MRV (branch on
the room with fewest options left) and forward checking (prune other
rooms' domains the instant a room is placed, backtrack immediately if
any domain empties).

**Simulated Annealing** (`csp_generator.py`, `SimulatedAnnealingRefiner`)
— once the CSP finds a valid layout, SA nudges room positions and sizes
to reduce a soft-cost function (aspect ratio, unmet adjacency
preferences, wasted circulation space), using the Metropolis criterion
so it can still escape small local optima, with a cooling schedule that
makes it greedier over time.

**Graph model** (`graph_model.py`) — rooms are nodes, required
adjacencies are edges — the "bubble diagram" architects sketch before
any geometry exists. Provides degree/BFS ordering and an
`adjacency_score()` used to evaluate how well a layout satisfies
required room connections.

**3D mesh generation** (`mesh_generator.py`) — turns the 2D room
layout into a 3D wall/floor mesh and writes it out as an OBJ file,
importable directly into Blender, Unity, Three.js, or Unreal.

**CAD export** (`cad_export.py`) — writes a raw ASCII DXF (R12 entity
set: POLYLINE, TEXT, 3DFACE) by hand, no external library required.
Each room outline can optionally be extruded into vertical 3D wall
faces at a given wall height.

**Compliance + report** (`report_generator.py`) — runs rule-based
compliance checks (e.g. required adjacencies), estimates material
quantities from room areas, and compiles everything into a formatted
PDF using `reportlab`.

## Project structure

```
src/
  models.py             # Rect, Plot, Room data classes (no logic to run)
  csp_generator.py       # 1-2. CSP solver + simulated annealing
  graph_model.py          # 3. adjacency graph / bubble diagram
  mesh_generator.py        # 4. 3D mesh (OBJ) export
  cad_export.py             # 5. CAD (DXF) export
  report_generator.py       # 6. compliance checks + PDF report
  main.py                    # demo: CSP + SA pipeline, ASCII output
  visualize.py                # demo: PNG render of the CSP pipeline's plan
tests/
  test_csp_solver.py
  test_optimizers.py
```

## Setup

```bash
pip install -r requirements.txt   # matplotlib
pip install reportlab              # needed by report_generator.py
```

## Running it

Run the CSP generator first — several other scripts read the
`layout.json` it produces.

```bash
python -c "from src.csp_generator import demo; demo()"    # writes layout.json
python -c "from src.mesh_generator import demo; demo()"   # writes floor_plan.obj
python -c "from src.report_generator import demo; demo()" # writes report.pdf
python -m src.main                                          # ASCII floor plan (self-contained demo)
python -m src.visualize                                     # writes floorplan.png
python -m src.cad_export                                    # writes floorplan.dxf (reads layout.json)
```

Example output (`python -m src.main`):

```
Plot: 14 x 10

  bedroom2   -> x= 7.60 y= 5.60 w= 4.00 h= 3.00 (area=12.00)
  dining     -> x= 0.60 y= 4.60 w= 3.00 h= 4.00 (area=12.00)
  bedroom1   -> x= 5.60 y= 0.60 w= 3.00 h= 4.00 (area=12.00)
  living     -> x= 3.60 y= 4.60 w= 4.00 h= 4.00 (area=16.00)
  kitchen    -> x= 0.60 y= 2.60 w= 4.50 h= 2.00 (area=9.00)
  bathroom   -> x= 9.60 y= 1.60 w= 2.00 h= 3.00 (area=6.00)
  entrance   -> x= 0.60 y= 0.60 w= 2.00 h= 2.00 (area=4.00)

EE...BBB......
EE...BBB.BB...
KKKKKBBB.BB...
KKKKKBBB.BB...
DDDLLLL.......
DDDLLLLBBBB...
DDDLLLLBBBB...
DDDLLLLBBBB...
..............
..............
```

### Running tests

```bash
python -m unittest discover -s tests -v
```

## Roadmap

- [x] CSP solver — structurally valid floor plan generation
- [x] Simulated Annealing — optimize among valid layouts for space
      utilization, ventilation, adjacency
- [x] 3D mesh export (OBJ, wall extrusion)
- [x] CAD export (hand-written DXF, 2D + 3D wall extrusion)
- [x] Compliance checks + material estimation + PDF report
- [ ] Genetic Algorithm / BSP-based optimization pipeline
- [ ] Rule-based interior/furniture placement
- [ ] Collision/overlap detection (AABB + SAT) for furniture
- [ ] Door/window placement (currently assumed, not modeled)

## Tech stack

- Python 3, stdlib only for the CSP/SA/graph/mesh/DXF algorithms
- `matplotlib` for PNG rendering (`src/visualize.py`)
- `reportlab` for PDF report generation (`src/report_generator.py`)
- DXF export is hand-written (no `ezdxf` dependency) but compatible
  with it if you'd rather swap in that library
