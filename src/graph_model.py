"""
Graph-based room adjacency modeling ("bubble diagram").

Before any geometry exists, a floor plan is really a graph: rooms are
nodes, required connections (kitchen-dining, living-entrance, etc.) are
edges. This module builds that graph from Room.adjacent_to (already used
by the CSP solver) and provides the operations later stages need:
  - degree-based ordering, useful as a placement/partition order (rooms
    with more required connections are natural "hubs" to place centrally)
  - BFS traversal order, so adjacent-in-graph rooms end up adjacent-in-
    sequence for algorithms (like BSP partitioning) that only see a list
  - adjacency_score(assignment): given actual room rectangles, what
    fraction of required connections are physically satisfied (share a
    wall)? This is the core term the GA and SA optimizers maximize.
"""

from collections import defaultdict, deque
from typing import Dict, List, Set, Tuple
from .models import Room, Rect


class AdjacencyGraph:
    def __init__(self, rooms: List[Room]):
        self.rooms: Dict[str, Room] = {r.name: r for r in rooms}
        self._adj: Dict[str, Set[str]] = defaultdict(set)
        for room in rooms:
            for neighbor in room.adjacent_to:
                if neighbor not in self.rooms:
                    raise ValueError(
                        f"Room '{room.name}' declares adjacency to unknown room '{neighbor}'"
                    )
                # bubble diagrams are undirected: "living touches dining"
                # implies "dining touches living" even if only one side declared it
                self._adj[room.name].add(neighbor)
                self._adj[neighbor].add(room.name)

    def neighbors(self, name: str) -> Set[str]:
        return set(self._adj.get(name, set()))

    def degree(self, name: str) -> int:
        return len(self._adj.get(name, set()))

    def edges(self) -> List[Tuple[str, str]]:
        seen = set()
        result = []
        for a, ns in self._adj.items():
            for b in ns:
                key = tuple(sorted((a, b)))
                if key not in seen:
                    seen.add(key)
                    result.append(key)
        return result

    def is_connected(self) -> bool:
        if not self.rooms:
            return True
        start = next(iter(self.rooms))
        visited = {start}
        queue = deque([start])
        while queue:
            cur = queue.popleft()
            for n in self._adj.get(cur, ()):
                if n not in visited:
                    visited.add(n)
                    queue.append(n)
        return visited == set(self.rooms)

    def degree_order(self) -> List[str]:
        """Rooms sorted by how many required connections they have, most first."""
        return sorted(self.rooms, key=lambda n: -self.degree(n))

    def bfs_order(self, start: str = None) -> List[str]:
        """Traversal order starting from the highest-degree ("hub") room,
        so graph-adjacent rooms end up sequence-adjacent — a good default
        ordering to feed into a partitioning algorithm."""
        if not self.rooms:
            return []
        if start is None:
            start = max(self.rooms, key=self.degree)
        order = [start]
        seen = {start}
        queue = deque([start])
        while queue:
            cur = queue.popleft()
            for n in sorted(self._adj.get(cur, ()), key=lambda x: -self.degree(x)):
                if n not in seen:
                    seen.add(n)
                    order.append(n)
                    queue.append(n)
        for name in self.rooms:  # append any rooms disconnected from the main graph
            if name not in seen:
                order.append(name)
                seen.add(name)
        return order

    def adjacency_score(self, assignment: Dict[str, Rect]) -> float:
        """Fraction of required edges that are physically satisfied
        (i.e. the two rooms' rectangles actually share a wall)."""
        edges = self.edges()
        if not edges:
            return 1.0
        satisfied = sum(1 for a, b in edges if assignment[a].touches(assignment[b]))
        return satisfied / len(edges)

    def describe(self) -> str:
        """Human-readable bubble diagram summary, e.g. for logging/demo output."""
        lines = [f"{len(self.rooms)} rooms, {len(self.edges())} required connections:"]
        for a, b in self.edges():
            lines.append(f"  {a} <-> {b}")
        return "\n".join(lines)
