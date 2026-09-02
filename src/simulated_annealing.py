"""
Simulated Annealing (SA) — local refinement after GA/BSP.

The GA searches the *discrete* space of room orderings. Once an order is
fixed, BSPTree still picks split fractions by a simple area-ratio
heuristic, which is often slightly off from optimal (e.g. two rooms with
very similar target areas but different min_dim constraints). SA polishes
the *continuous* split fractions of the same fixed tree structure: nudge
one wall position, keep the change if it helps, sometimes keep it even if
it doesn't (with probability shrinking over time) so it can escape small
local optima instead of getting stuck — the classic "shake a solid as it
cools" idea applied to wall positions instead of atoms.
"""

import math
import random
from typing import Dict, List, Optional
from .models import Plot, Room, Rect
from .graph_model import AdjacencyGraph
from .bsp_partition import BSPTree


class LayoutSimulatedAnnealing:
    def __init__(self, plot: Plot, rooms: List[Room], graph: AdjacencyGraph,
                 order: List[str], initial_temp: float = 1.0, cooling_rate: float = 0.97,
                 iterations: int = 500, seed: Optional[int] = None):
        self.plot = plot
        self.rooms = rooms
        self.graph = graph
        self.tree = BSPTree(plot, rooms, order)
        self.initial_temp = initial_temp
        self.cooling_rate = cooling_rate
        self.iterations = iterations
        self.rng = random.Random(seed)
        self.history: List[float] = []
        self.best_score: float = -1.0

    def _score(self, assignment: Dict[str, Rect]) -> float:
        rooms_by_name = {r.name: r for r in self.rooms}
        util_terms = []
        for name, rect in assignment.items():
            room = rooms_by_name[name]
            target = (room.min_area + room.max_area) / 2
            deviation = abs(rect.area - target) / target if target else 0
            util_terms.append(max(0.0, 1.0 - deviation))
        utilization = sum(util_terms) / len(util_terms) if util_terms else 0.0
        adjacency = self.graph.adjacency_score(assignment)
        return 0.6 * utilization + 0.4 * adjacency

    def run(self) -> Dict[str, Rect]:
        temp = self.initial_temp
        current_assignment = self.tree.render()
        current_score = self._score(current_assignment)
        internal_nodes = self.tree.all_internal_nodes()

        for _step in range(self.iterations):
            if not internal_nodes:
                break

            node = self.rng.choice(internal_nodes)
            old_fraction = node.fraction
            node.fraction = min(0.95, max(0.05, old_fraction + self.rng.uniform(-0.1, 0.1)))

            new_assignment = self.tree.render()
            new_score = self._score(new_assignment)
            score_delta = new_score - current_score

            # Metropolis criterion: always accept improvements; accept
            # worse moves with probability that shrinks as temp cools
            if score_delta > 0 or self.rng.random() < math.exp(score_delta / max(temp, 1e-6)):
                current_score = new_score
                current_assignment = new_assignment
            else:
                node.fraction = old_fraction  # reject: revert the nudge

            temp *= self.cooling_rate
            self.history.append(current_score)

        self.best_score = current_score
        return current_assignment
