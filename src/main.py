"""
Demo: generate a small house floor plan using the CSP + simulated
annealing generator (src/csp_generator.py).

Run:
    python -m src.main
"""

from .csp_generator import Plot, RoomSpec, CSPFloorPlanGenerator, SimulatedAnnealingRefiner


def render_ascii(plot: Plot, layout: dict) -> str:
    """Quick ASCII visualization: each cell shows the first letter of its room."""
    w, h = int(plot.width), int(plot.height)
    grid = [["." for _ in range(w)] for _ in range(h)]
    for name, room in layout.items():
        label = name[0].upper()
        x1, y1 = int(room.x), int(room.y)
        x2, y2 = int(room.x + room.w), int(room.y + room.h)
        for x in range(x1, min(x2, w)):
            for y in range(y1, min(y2, h)):
                grid[y][x] = label
    return "\n".join("".join(row) for row in grid)


def build_example_rooms():
    return [
        RoomSpec("living", "living", min_area=16, max_area=24, min_dim=3,
                 adjacent_to=["entrance", "dining"]),
        RoomSpec("entrance", "circulation", min_area=4, max_area=8, min_dim=2),
        RoomSpec("dining", "dining", min_area=10, max_area=16, min_dim=3,
                 adjacent_to=["kitchen"]),
        RoomSpec("kitchen", "kitchen", min_area=8, max_area=12, min_dim=2),
        RoomSpec("bedroom1", "bedroom", min_area=12, max_area=16, min_dim=3),
        RoomSpec("bedroom2", "bedroom", min_area=10, max_area=14, min_dim=3),
        RoomSpec("bathroom", "bathroom", min_area=4, max_area=6, min_dim=2),
    ]


def main():
    plot = Plot(width=14, height=10, setback=0.6)
    rooms = build_example_rooms()

    solver = CSPFloorPlanGenerator(plot, rooms, grid_step=1)
    layout = solver.solve()

    if layout is None:
        print("Failed to generate floor plan: no feasible layout found.")
        return

    sa = SimulatedAnnealingRefiner(plot, rooms)
    layout = sa.refine(layout)

    print(f"Plot: {plot.width} x {plot.height}\n")
    for name, room in layout.items():
        print(f"  {name:10s} -> x={room.x:5.2f} y={room.y:5.2f} "
              f"w={room.w:5.2f} h={room.h:5.2f} (area={room.area:.2f})")
    print()
    print(render_ascii(plot, layout))


if __name__ == "__main__":
    main()
