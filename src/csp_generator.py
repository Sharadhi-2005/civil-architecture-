"""
csp_generator.py
================
Constraint Satisfaction (backtracking + forward checking) floor plan
generator, followed by Simulated Annealing for soft-objective optimization.

Usage:
    python3 csp_generator.py

Produces:
    layout.json  -- the final optimized floor plan, consumed by
                     mesh_generator.py and report_generator.py
"""

import json
import math
import random
from dataclasses import dataclass, field, asdict
from typing import List, Tuple, Dict, Optional


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class RoomSpec:
    name: str
    room_type: str
    min_area: float          # m^2
    max_area: float          # m^2
    min_dim: float = 2.0     # smallest allowed width/height (m)
    adjacent_to: List[str] = field(default_factory=list)      # required adjacency
    separated_from: List[str] = field(default_factory=list)   # required non-adjacency


@dataclass
class PlacedRoom:
    name: str
    room_type: str
    x: float
    y: float
    w: float
    h: float

    @property
    def area(self) -> float:
        return self.w * self.h

    @property
    def rect(self) -> Tuple[float, float, float, float]:
        return (self.x, self.y, self.x + self.w, self.y + self.h)


@dataclass
class Plot:
    width: float
    height: float
    setback: float = 0.6     # meters, distance from plot boundary


# ---------------------------------------------------------------------------
# Phase A: CSP backtracking with MRV ordering + forward checking
# ---------------------------------------------------------------------------

class CSPFloorPlanGenerator:
    def __init__(self, plot: Plot, rooms: List[RoomSpec], grid_step: float = 0.5):
        self.plot = plot
        self.rooms = rooms
        self.grid_step = grid_step
        self.usable_w = plot.width - 2 * plot.setback
        self.usable_h = plot.height - 2 * plot.setback

    # -- domain generation -------------------------------------------------
    def _generate_domain(self, room: RoomSpec) -> List[Tuple[float, float, float, float]]:
        """All (x, y, w, h) candidates on the grid satisfying size + boundary."""
        domain = []
        step = self.grid_step
        max_w = min(self.usable_w, math.sqrt(room.max_area * 3))
        max_h = min(self.usable_h, math.sqrt(room.max_area * 3))

        w = room.min_dim
        while w <= max_w:
            h = room.min_dim
            while h <= max_h:
                area = w * h
                if room.min_area <= area <= room.max_area:
                    x = self.plot.setback
                    while x + w <= self.plot.width - self.plot.setback:
                        y = self.plot.setback
                        while y + h <= self.plot.height - self.plot.setback:
                            domain.append((x, y, w, h))
                            y += step
                        x += step
                h += step
            w += step
        random.shuffle(domain)  # avoid degenerate left-to-right bias
        return domain

    # -- constraint checks ---------------------------------------------------
    @staticmethod
    def _overlaps(a: Tuple[float, float, float, float], b: Tuple[float, float, float, float]) -> bool:
        ax1, ay1, ax2, ay2 = a
        bx1, by1, bx2, by2 = b
        return not (ax2 <= bx1 or bx2 <= ax1 or ay2 <= by1 or by2 <= ay1)

    @staticmethod
    def _touches(a: Tuple[float, float, float, float], b: Tuple[float, float, float, float],
                 tol: float = 0.05) -> bool:
        """True if rectangles share an edge (adjacent) within tolerance."""
        ax1, ay1, ax2, ay2 = a
        bx1, by1, bx2, by2 = b
        vertical_touch = (abs(ax2 - bx1) < tol or abs(bx2 - ax1) < tol) and \
            (ay1 < by2 and by1 < ay2)
        horizontal_touch = (abs(ay2 - by1) < tol or abs(by2 - ay1) < tol) and \
            (ax1 < bx2 and bx1 < ax2)
        return vertical_touch or horizontal_touch

    def _consistent(self, candidate: Tuple[float, float, float, float], room: RoomSpec,
                     placed: Dict[str, PlacedRoom]) -> bool:
        cand_rect = (candidate[0], candidate[1], candidate[0] + candidate[2], candidate[1] + candidate[3])
        for other_name, other in placed.items():
            if self._overlaps(cand_rect, other.rect):
                return False
            if other_name in room.separated_from and self._touches(cand_rect, other.rect):
                return False
        return True

    # -- backtracking search ---------------------------------------------------
    def solve(self, max_restarts: int = 25) -> Optional[Dict[str, PlacedRoom]]:
        for attempt in range(max_restarts):
            domains = {r.name: self._generate_domain(r) for r in self.rooms}
            if any(len(d) == 0 for d in domains.values()):
                continue  # infeasible domain (room too big for plot), retry won't help much but loop anyway
            result = self._backtrack({}, domains)
            if result is not None:
                return result
        return None

    def _order_unassigned(self, domains: Dict[str, list], assigned: Dict[str, PlacedRoom]) -> List[str]:
        remaining = [r.name for r in self.rooms if r.name not in assigned]
        # MRV: fewest remaining legal values first
        return sorted(remaining, key=lambda n: len(domains[n]))

    def _backtrack(self, assigned: Dict[str, PlacedRoom], domains: Dict[str, list]) -> Optional[Dict[str, PlacedRoom]]:
        if len(assigned) == len(self.rooms):
            return assigned

        order = self._order_unassigned(domains, assigned)
        room_name = order[0]
        room = next(r for r in self.rooms if r.name == room_name)

        for candidate in list(domains[room_name]):
            if not self._consistent(candidate, room, assigned):
                continue

            x, y, w, h = candidate
            placed_room = PlacedRoom(room.name, room.room_type, x, y, w, h)
            new_assigned = dict(assigned)
            new_assigned[room.name] = placed_room

            # forward checking: prune candidates now invalid for remaining rooms
            pruned_domains = dict(domains)
            failed = False
            for other in self.rooms:
                if other.name in new_assigned:
                    continue
                filtered = [c for c in domains[other.name]
                            if self._consistent(c, other, new_assigned)]
                if not filtered:
                    failed = True
                    break
                pruned_domains[other.name] = filtered

            if failed:
                continue

            result = self._backtrack(new_assigned, pruned_domains)
            if result is not None:
                return result

        return None  # trigger backtrack / restart


# ---------------------------------------------------------------------------
# Phase B: Simulated Annealing for soft-objective refinement
# ---------------------------------------------------------------------------

class SimulatedAnnealingRefiner:
    def __init__(self, plot: Plot, rooms: List[RoomSpec],
                 t_initial: float = 50.0, t_min: float = 0.5, cooling_rate: float = 0.95,
                 iterations_per_temp: int = 30):
        self.plot = plot
        self.rooms = {r.name: r for r in rooms}
        self.t_initial = t_initial
        self.t_min = t_min
        self.cooling_rate = cooling_rate
        self.iterations_per_temp = iterations_per_temp

    # -- cost function ---------------------------------------------------------
    def _cost(self, layout: Dict[str, PlacedRoom]) -> float:
        cost = 0.0
        for room in layout.values():
            spec = self.rooms[room.name]
            # 1. aspect ratio penalty (prefer closer to square, ratio <= 2:1 ideal)
            ratio = max(room.w, room.h) / max(min(room.w, room.h), 0.01)
            cost += max(0.0, ratio - 2.0) * 5.0

            # 2. adjacency preference (soft): reward satisfied adjacency
            for adj_name in spec.adjacent_to:
                if adj_name in layout:
                    if not CSPFloorPlanGenerator._touches(room.rect, layout[adj_name].rect):
                        cost += 8.0  # penalty if preferred adjacency not met

        # 3. wasted circulation space = usable plot area not covered by any room
        plot_area = (self.plot.width - 2 * self.plot.setback) * (self.plot.height - 2 * self.plot.setback)
        covered = sum(r.area for r in layout.values())
        wasted_ratio = max(0.0, (plot_area - covered) / plot_area)
        cost += wasted_ratio * 20.0
        return cost

    # -- neighbor generation ---------------------------------------------------
    def _perturb(self, layout: Dict[str, PlacedRoom]) -> Dict[str, PlacedRoom]:
        new_layout = {k: PlacedRoom(**asdict(v)) for k, v in layout.items()}
        room_name = random.choice(list(new_layout.keys()))
        room = new_layout[room_name]

        move_type = random.choice(["shift", "resize"])
        step = 0.5
        if move_type == "shift":
            room.x += random.choice([-step, step])
            room.y += random.choice([-step, step])
        else:
            spec = self.rooms[room_name]
            new_w = max(spec.min_dim, room.w + random.choice([-step, step]))
            new_h = max(spec.min_dim, room.h + random.choice([-step, step]))
            if spec.min_area <= new_w * new_h <= spec.max_area:
                room.w, room.h = new_w, new_h

        # clamp inside plot/setback
        room.x = max(self.plot.setback, min(room.x, self.plot.width - self.plot.setback - room.w))
        room.y = max(self.plot.setback, min(room.y, self.plot.height - self.plot.setback - room.h))
        return new_layout

    def _hard_constraints_ok(self, layout: Dict[str, PlacedRoom]) -> bool:
        rooms_list = list(layout.values())
        for i in range(len(rooms_list)):
            for j in range(i + 1, len(rooms_list)):
                if CSPFloorPlanGenerator._overlaps(rooms_list[i].rect, rooms_list[j].rect):
                    return False
        return True

    # -- main annealing loop ---------------------------------------------------
    def refine(self, initial_layout: Dict[str, PlacedRoom]) -> Dict[str, PlacedRoom]:
        current = initial_layout
        current_cost = self._cost(current)
        best, best_cost = current, current_cost
        t = self.t_initial

        while t > self.t_min:
            for _ in range(self.iterations_per_temp):
                candidate = self._perturb(current)
                if not self._hard_constraints_ok(candidate):
                    continue
                candidate_cost = self._cost(candidate)
                delta = candidate_cost - current_cost
                if delta < 0 or random.random() < math.exp(-delta / t):
                    current, current_cost = candidate, candidate_cost
                    if current_cost < best_cost:
                        best, best_cost = current, current_cost
            t *= self.cooling_rate

        return best


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

def demo():
    plot = Plot(width=14.0, height=10.0, setback=0.6)

    rooms = [
        RoomSpec("Living Room", "living", min_area=18, max_area=28, min_dim=3.5,
                 adjacent_to=["Kitchen", "Entry"]),
        RoomSpec("Kitchen", "kitchen", min_area=9, max_area=14, min_dim=2.5,
                 adjacent_to=["Living Room"]),
        RoomSpec("Entry", "circulation", min_area=4, max_area=8, min_dim=1.8,
                 adjacent_to=["Living Room"]),
        RoomSpec("Bedroom 1", "bedroom", min_area=12, max_area=18, min_dim=3.0,
                 separated_from=["Kitchen"]),
        RoomSpec("Bedroom 2", "bedroom", min_area=10, max_area=15, min_dim=2.8,
                 separated_from=["Kitchen"]),
        RoomSpec("Bathroom", "bathroom", min_area=4, max_area=7, min_dim=1.8,
                 adjacent_to=["Bedroom 1"]),
    ]

    print("Running CSP backtracking search...")
    csp = CSPFloorPlanGenerator(plot, rooms, grid_step=0.5)
    solution = csp.solve()

    if solution is None:
        print("No feasible layout found — relax constraints or enlarge plot.")
        return

    print(f"Feasible layout found for {len(solution)} rooms. Refining with simulated annealing...")
    sa = SimulatedAnnealingRefiner(plot, rooms)
    refined = sa.refine(solution)

    output = {
        "plot": asdict(plot),
        "rooms": [asdict(r) for r in refined.values()],
    }

    with open("layout.json", "w") as f:
        json.dump(output, f, indent=2)

    print("\nFinal layout:")
    for r in refined.values():
        print(f"  {r.name:15s} ({r.room_type:11s})  x={r.x:5.2f} y={r.y:5.2f} "
              f"w={r.w:4.2f} h={r.h:4.2f}  area={r.area:5.2f} m^2")
    print("\nSaved to layout.json")


if __name__ == "__main__":
    demo()
