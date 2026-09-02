import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
from src.models import Plot, Room, Rect
from src.graph_model import AdjacencyGraph
from src.bsp_partition import BSPTree
from src.genetic_algorithm import FloorPlanGA
from src.simulated_annealing import LayoutSimulatedAnnealing
from src.geometry_utils import Polygon, polygons_overlap, aabb_overlap, min_clearance_ok
from src.interior_rules import place_all_furniture, validate_clearances


def make_rooms():
    return [
        Room(name="living", min_area=16, max_area=24, min_dim=3, needs_exterior_wall=True,
             adjacent_to=["entrance", "dining"]),
        Room(name="entrance", min_area=4, max_area=8, min_dim=2, needs_exterior_wall=True),
        Room(name="dining", min_area=10, max_area=16, min_dim=3, adjacent_to=["kitchen"]),
        Room(name="kitchen", min_area=8, max_area=12, min_dim=2, needs_exterior_wall=True),
    ]


class TestAdjacencyGraph(unittest.TestCase):
    def test_edges_and_degree(self):
        graph = AdjacencyGraph(make_rooms())
        self.assertEqual(graph.degree("living"), 2)  # entrance + dining
        self.assertIn(("dining", "living"), graph.edges() + [(b, a) for a, b in graph.edges()])

    def test_unknown_neighbor_raises(self):
        bad_room = Room(name="a", min_area=4, max_area=8, adjacent_to=["ghost"])
        with self.assertRaises(ValueError):
            AdjacencyGraph([bad_room])

    def test_adjacency_score(self):
        graph = AdjacencyGraph(make_rooms())
        assignment = {
            "living": Rect(0, 0, 4, 4), "entrance": Rect(4, 0, 2, 2),
            "dining": Rect(0, 4, 4, 4), "kitchen": Rect(4, 4, 2, 2),
        }
        # living-entrance touch, living-dining touch, dining-kitchen touch -> all 3 satisfied
        self.assertEqual(graph.adjacency_score(assignment), 1.0)


class TestBSPTree(unittest.TestCase):
    def test_tiles_plot_exactly(self):
        rooms = make_rooms()
        plot = Plot(10, 10)
        tree = BSPTree(plot, rooms, order=[r.name for r in rooms])
        assignment = tree.render()
        total_area = sum(r.area for r in assignment.values())
        self.assertEqual(total_area, plot.width * plot.height)

    def test_no_overlaps(self):
        rooms = make_rooms()
        plot = Plot(10, 10)
        tree = BSPTree(plot, rooms, order=[r.name for r in rooms])
        assignment = tree.render()
        names = list(assignment.keys())
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                self.assertFalse(assignment[names[i]].overlaps(assignment[names[j]]))


class TestGeneticAlgorithm(unittest.TestCase):
    def test_improves_over_generations(self):
        rooms = make_rooms()
        plot = Plot(10, 10)
        graph = AdjacencyGraph(rooms)
        ga = FloorPlanGA(plot, rooms, graph, population_size=20, generations=15, seed=1)
        ga.run()
        self.assertGreaterEqual(ga.history[-1], ga.history[0])

    def test_decode_produces_valid_permutation(self):
        rooms = make_rooms()
        plot = Plot(10, 10)
        graph = AdjacencyGraph(rooms)
        ga = FloorPlanGA(plot, rooms, graph, population_size=10, generations=5, seed=1)
        ga.run()
        self.assertEqual(set(ga.best_genome), {r.name for r in rooms})


class TestSimulatedAnnealing(unittest.TestCase):
    def test_does_not_crash_and_returns_full_assignment(self):
        rooms = make_rooms()
        plot = Plot(10, 10)
        graph = AdjacencyGraph(rooms)
        order = [r.name for r in rooms]
        sa = LayoutSimulatedAnnealing(plot, rooms, graph, order=order, iterations=50, seed=1)
        result = sa.run()
        self.assertEqual(set(result.keys()), {r.name for r in rooms})


class TestGeometryUtils(unittest.TestCase):
    def test_aabb_overlap(self):
        self.assertTrue(aabb_overlap(0, 0, 4, 4, 2, 2, 4, 4))
        self.assertFalse(aabb_overlap(0, 0, 4, 4, 4, 4, 4, 4))

    def test_sat_rotated_rectangles(self):
        a = Polygon.from_rect(0, 0, 4, 4, rotation_deg=0)
        b = Polygon.from_rect(3, 3, 4, 4, rotation_deg=45)
        self.assertTrue(polygons_overlap(a, b))
        c = Polygon.from_rect(20, 20, 4, 4, rotation_deg=45)
        self.assertFalse(polygons_overlap(a, c))

    def test_min_clearance(self):
        self.assertFalse(min_clearance_ok(0, 0, 2, 2, 2.1, 0, 2, 2, min_clearance=0.5))
        self.assertTrue(min_clearance_ok(0, 0, 2, 2, 3, 0, 2, 2, min_clearance=0.5))


class TestInteriorRules(unittest.TestCase):
    def test_furniture_placed_without_overlap(self):
        assignment = {"bedroom1": Rect(0, 0, 4, 4), "living": Rect(4, 0, 6, 5)}
        furniture = place_all_furniture(assignment)
        for room, items in furniture.items():
            self.assertEqual(validate_clearances(items, min_clearance=0.0), [])

    def test_unknown_room_type_gets_no_furniture(self):
        assignment = {"entrance": Rect(0, 0, 2, 2)}
        furniture = place_all_furniture(assignment)
        self.assertEqual(furniture["entrance"], [])


if __name__ == "__main__":
    unittest.main()
