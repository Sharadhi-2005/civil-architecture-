"""
Full pipeline demo: runs every algorithm in the project in sequence, on
the same example house from main.py.

    graph model -> GA (optimizes room order) -> simulated annealing
    (refines split fractions) -> rule-based interior placement ->
    collision/clearance validation -> DXF export

Run:
    python -m src.demo_full_pipeline
"""

from .models import Plot, Room, FloorPlanRequest
from .graph_model import AdjacencyGraph
from .genetic_algorithm import FloorPlanGA
from .simulated_annealing import LayoutSimulatedAnnealing
from .interior_rules import place_all_furniture, validate_clearances
from .cad_export import export_floorplan_dxf
from .visualize import render_floorplan_with_furniture


def build_example_request() -> FloorPlanRequest:
    plot = Plot(width=14, height=10)
    rooms = [
        Room(name="living", min_area=16, max_area=24, min_dim=3,
             needs_exterior_wall=True, adjacent_to=["entrance", "dining"]),
        Room(name="entrance", min_area=4, max_area=8, min_dim=2,
             needs_exterior_wall=True, adjacent_to=[]),
        Room(name="dining", min_area=10, max_area=16, min_dim=3, adjacent_to=["kitchen"]),
        Room(name="kitchen", min_area=8, max_area=12, min_dim=2, needs_exterior_wall=True, adjacent_to=[]),
        Room(name="bedroom1", min_area=12, max_area=16, min_dim=3, needs_exterior_wall=True, adjacent_to=[]),
        Room(name="bedroom2", min_area=10, max_area=14, min_dim=3, needs_exterior_wall=True, adjacent_to=[]),
        Room(name="bathroom", min_area=4, max_area=6, min_dim=2, adjacent_to=[]),
    ]
    return FloorPlanRequest(plot=plot, rooms=rooms)


def main():
    request = build_example_request()

    print("=" * 60)
    print("STAGE 1: Graph model (bubble diagram)")
    print("=" * 60)
    graph = AdjacencyGraph(request.rooms)
    print(graph.describe())
    print(f"Connected: {graph.is_connected()}")
    print(f"BFS placement order: {graph.bfs_order()}\n")

    print("=" * 60)
    print("STAGE 2: Genetic Algorithm (optimize room order)")
    print("=" * 60)
    ga = FloorPlanGA(request.plot, request.rooms, graph,
                      population_size=40, generations=60, seed=42)
    ga_layout = ga.run()
    print(f"Best fitness after {ga.generations} generations: {ga.best_fitness:.4f}")
    print(f"Best room order found: {ga.best_genome}\n")

    print("=" * 60)
    print("STAGE 3: Simulated Annealing (refine split fractions)")
    print("=" * 60)
    sa = LayoutSimulatedAnnealing(request.plot, request.rooms, graph,
                                   order=ga.best_genome, iterations=500, seed=42)
    sa_layout = sa.run()
    print(f"SA score before: {sa._score(ga_layout):.4f} -> after: {sa.best_score:.4f}\n")

    print("=" * 60)
    print("STAGE 4: Rule-based interior furniture placement")
    print("=" * 60)
    furniture = place_all_furniture(sa_layout)
    for room, items in furniture.items():
        if items:
            names = ", ".join(f"{it.name}({it.w:.1f}x{it.h:.1f})" for it in items)
            print(f"  {room:10s} -> {names}")

    print("\n" + "=" * 60)
    print("STAGE 5: Collision/clearance validation")
    print("=" * 60)
    all_violations = []
    for room, items in furniture.items():
        violations = validate_clearances(items)
        all_violations.extend(f"[{room}] {v}" for v in violations)
    if all_violations:
        for v in all_violations:
            print(f"  VIOLATION: {v}")
    else:
        print("  No clearance violations detected.")

    print("\n" + "=" * 60)
    print("STAGE 6: CAD export (DXF)")
    print("=" * 60)
    dxf_path = export_floorplan_dxf(sa_layout, furniture, out_path="floorplan.dxf", wall_height=2.8)
    print(f"  Wrote {dxf_path}")

    png_path = render_floorplan_with_furniture(request.plot, sa_layout, furniture,
                                                 out_path="floorplan_full.png",
                                                 title="Optimized floor plan with furniture")
    print(f"  Wrote {png_path}")


if __name__ == "__main__":
    main()
