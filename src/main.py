"""
Demo: generate a small house floor plan using the CSP solver.

Run:
    python -m src.main
"""

from .models import Plot, Room, FloorPlanRequest
from .csp_solver import FloorPlanCSPSolver, NoSolutionError


def render_ascii(plot: Plot, assignment: dict) -> str:
    """Quick ASCII visualization: each cell shows the first letter of its room."""
    grid = [["." for _ in range(plot.width)] for _ in range(plot.height)]
    for name, rect in assignment.items():
        label = name[0].upper()
        for x in range(rect.x, rect.x2):
            for y in range(rect.y, rect.y2):
                grid[y][x] = label
    return "\n".join("".join(row) for row in grid)


def build_example_request() -> FloorPlanRequest:
    plot = Plot(width=14, height=10)  # e.g. 14m x 10m plot, 1 cell = 1m
    rooms = [
        Room(name="living", min_area=16, max_area=24, min_dim=3,
             needs_exterior_wall=True, adjacent_to=["entrance", "dining"]),
        Room(name="entrance", min_area=4, max_area=8, min_dim=2,
             needs_exterior_wall=True, adjacent_to=[]),
        Room(name="dining", min_area=10, max_area=16, min_dim=3,
             adjacent_to=["kitchen"]),
        Room(name="kitchen", min_area=8, max_area=12, min_dim=2,
             needs_exterior_wall=True, adjacent_to=[]),
        Room(name="bedroom1", min_area=12, max_area=16, min_dim=3,
             needs_exterior_wall=True, adjacent_to=[]),
        Room(name="bedroom2", min_area=10, max_area=14, min_dim=3,
             needs_exterior_wall=True, adjacent_to=[]),
        Room(name="bathroom", min_area=4, max_area=6, min_dim=2,
             adjacent_to=[]),
    ]
    return FloorPlanRequest(plot=plot, rooms=rooms)


def main():
    request = build_example_request()
    solver = FloorPlanCSPSolver(request, grid_step=1)

    try:
        assignment = solver.solve()
    except NoSolutionError as e:
        print(f"Failed to generate floor plan: {e}")
        return

    print(f"Solved in {solver._steps} search steps.\n")
    print(f"Plot: {request.plot.width} x {request.plot.height}\n")
    for name, rect in assignment.items():
        print(f"  {name:10s} -> x={rect.x:2d} y={rect.y:2d} w={rect.w:2d} h={rect.h:2d} (area={rect.area})")
    print()
    print(render_ascii(request.plot, assignment))


if __name__ == "__main__":
    main()
