import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
from src.models import Plot, Room, Rect, FloorPlanRequest
from src.csp_solver import FloorPlanCSPSolver, NoSolutionError


class TestRectGeometry(unittest.TestCase):
    def test_overlap_detection(self):
        a = Rect(0, 0, 4, 4)
        b = Rect(2, 2, 4, 4)
        c = Rect(4, 0, 4, 4)
        self.assertTrue(a.overlaps(b))
        self.assertFalse(a.overlaps(c))

    def test_touching_detection(self):
        a = Rect(0, 0, 4, 4)
        b = Rect(4, 0, 4, 4)   # shares the right wall of a
        c = Rect(5, 5, 4, 4)   # corner-only, not a real wall share
        self.assertTrue(a.touches(b))
        self.assertFalse(a.touches(c))


class TestCSPSolver(unittest.TestCase):
    def test_simple_two_room_solves(self):
        plot = Plot(width=6, height=4)
        rooms = [
            Room(name="a", min_area=6, max_area=12, min_dim=2),
            Room(name="b", min_area=6, max_area=12, min_dim=2, adjacent_to=["a"]),
        ]
        solver = FloorPlanCSPSolver(FloorPlanRequest(plot, rooms))
        result = solver.solve()
        self.assertEqual(set(result.keys()), {"a", "b"})
        self.assertTrue(result["a"].touches(result["b"]))
        self.assertFalse(result["a"].overlaps(result["b"]))

    def test_no_overlaps_in_full_example(self):
        plot = Plot(width=10, height=10)
        rooms = [
            Room(name="r1", min_area=9, max_area=16, min_dim=3),
            Room(name="r2", min_area=9, max_area=16, min_dim=3),
            Room(name="r3", min_area=9, max_area=16, min_dim=3),
        ]
        solver = FloorPlanCSPSolver(FloorPlanRequest(plot, rooms))
        result = solver.solve()
        names = list(result.keys())
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                self.assertFalse(result[names[i]].overlaps(result[names[j]]))

    def test_exterior_wall_constraint_respected(self):
        plot = Plot(width=8, height=8)
        rooms = [
            Room(name="ext", min_area=6, max_area=12, min_dim=2, needs_exterior_wall=True),
        ]
        solver = FloorPlanCSPSolver(FloorPlanRequest(plot, rooms))
        result = solver.solve()
        r = result["ext"]
        on_boundary = r.x == 0 or r.y == 0 or r.x2 == plot.width or r.y2 == plot.height
        self.assertTrue(on_boundary)

    def test_impossible_area_raises(self):
        plot = Plot(width=4, height=4)
        rooms = [Room(name="too_big", min_area=100, max_area=200, min_dim=2)]
        solver = FloorPlanCSPSolver(FloorPlanRequest(plot, rooms))
        with self.assertRaises(NoSolutionError):
            solver.solve()

    def test_unsatisfiable_adjacency_raises(self):
        # Plot too small to fit both rooms simultaneously -> no valid assignment
        plot = Plot(width=3, height=2)
        rooms = [
            Room(name="a", min_area=4, max_area=6, min_dim=2),
            Room(name="b", min_area=4, max_area=6, min_dim=2, adjacent_to=["a"]),
        ]
        solver = FloorPlanCSPSolver(FloorPlanRequest(plot, rooms))
        with self.assertRaises(NoSolutionError):
            solver.solve()


if __name__ == "__main__":
    unittest.main()
