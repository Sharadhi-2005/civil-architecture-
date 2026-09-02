"""
Rectangular space partitioning — the "slicing floorplan" algorithm.

Turns an abstract, ordered list of rooms into actual wall geometry by
recursively slicing the plot rectangle in two: at each step, cut the
current rectangle along its longer side, split the room list into two
contiguous groups sized proportional to their combined target area, and
recurse on each half with its own sub-rectangle. Recursion stops when a
group has exactly one room, which becomes a leaf.

The split *fractions* (where along the axis each cut happens) are stored
per internal node and can be perturbed later without touching the tree
structure or room order — that's what SimulatedAnnealing (src/simulated_
annealing.py) does: it nudges these fractions to locally improve fit
after the GA has already chosen a good room order.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from .models import Plot, Room, Rect


@dataclass
class BSPNode:
    room_names: List[str]
    axis: Optional[str] = None       # 'H' or 'V', set on render for internal nodes
    fraction: float = 0.5            # 0..1 position of the cut along `axis`
    left: Optional["BSPNode"] = None
    right: Optional["BSPNode"] = None

    @property
    def is_leaf(self) -> bool:
        return len(self.room_names) <= 1


class BSPTree:
    def __init__(self, plot: Plot, rooms: List[Room], order: List[str]):
        self.plot = plot
        self.rooms_by_name = {r.name: r for r in rooms}
        missing = set(order) - set(self.rooms_by_name)
        if missing:
            raise ValueError(f"order references unknown rooms: {missing}")
        if set(order) != set(self.rooms_by_name):
            raise ValueError("order must contain every room exactly once")
        self.order = order
        self.root = self._build(order)

    def _target_area(self, name: str) -> float:
        room = self.rooms_by_name[name]
        return (room.min_area + room.max_area) / 2

    def _build(self, names: List[str]) -> BSPNode:
        node = BSPNode(room_names=list(names))
        if len(names) <= 1:
            return node
        total = sum(self._target_area(n) for n in names)
        cum = 0.0
        split_idx = 1
        for i, n in enumerate(names):
            cum += self._target_area(n)
            if cum >= total / 2:
                split_idx = max(1, min(len(names) - 1, i + 1))
                break
        left_names, right_names = names[:split_idx], names[split_idx:]
        left_area = sum(self._target_area(n) for n in left_names)
        node.fraction = (left_area / total) if total > 0 else 0.5
        node.left = self._build(left_names)
        node.right = self._build(right_names)
        return node

    def render(self) -> Dict[str, Rect]:
        """Walk the tree and compute actual room rectangles from current fractions."""
        assignment: Dict[str, Rect] = {}
        self._render_node(self.root, Rect(0, 0, self.plot.width, self.plot.height), assignment)
        return assignment

    def _render_node(self, node: BSPNode, rect: Rect, out: Dict[str, Rect]):
        if node.is_leaf:
            if node.room_names:
                out[node.room_names[0]] = rect
            return
        axis = "V" if rect.w >= rect.h else "H"  # always cut the longer side
        node.axis = axis
        frac = min(max(node.fraction, 0.05), 0.95)  # keep both children non-degenerate
        if axis == "V":
            split_w = round(rect.w * frac)
            left_rect = Rect(rect.x, rect.y, split_w, rect.h)
            right_rect = Rect(rect.x + split_w, rect.y, rect.w - split_w, rect.h)
        else:
            split_h = round(rect.h * frac)
            left_rect = Rect(rect.x, rect.y, rect.w, split_h)
            right_rect = Rect(rect.x, rect.y + split_h, rect.w, rect.h - split_h)
        self._render_node(node.left, left_rect, out)
        self._render_node(node.right, right_rect, out)

    def all_internal_nodes(self) -> List[BSPNode]:
        """Every split node in the tree — what simulated annealing perturbs."""
        nodes: List[BSPNode] = []

        def walk(n: BSPNode):
            if not n.is_leaf:
                nodes.append(n)
                walk(n.left)
                walk(n.right)

        walk(self.root)
        return nodes
