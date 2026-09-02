"""
Constraint Satisfaction Problem (CSP) solver for floor plan generation.

Approach
--------
- The plot is discretized into a grid.
- Each Room is a CSP *variable*. Its *domain* is every candidate Rect
  (position + size) that satisfies that room's own area/shape rules and
  fits inside the plot.
- We search for an assignment of one Rect per room such that:
    1. No two rooms overlap                      (hard constraint)
    2. Every room stays inside the plot           (hard constraint)
    3. Declared adjacencies actually share a wall (hard constraint)
    4. Rooms flagged needs_exterior_wall touch the plot boundary (hard constraint)
- Search uses backtracking with:
    * Minimum Remaining Values (MRV) heuristic — branch on the room with
      the fewest legal placements left, since it's most likely to fail
      fastest ("fail first" principle).
    * Forward checking — after placing a room, prune candidate rects for
      unassigned rooms that would now overlap it. If any room's domain
      becomes empty, backtrack immediately instead of discovering the
      dead end several rooms later.

This is intentionally a classical, explainable CSP — no ML involved.
It's the layer that guarantees structural validity; a Genetic Algorithm
or Simulated Annealing pass can run afterward to optimize *among* valid
solutions (e.g. for space efficiency), but every candidate it touches
is already guaranteed feasible by this solver.
"""

from typing import Dict, List, Optional
from .models import Plot, Room, Rect, FloorPlanRequest


class NoSolutionError(Exception):
    pass


class FloorPlanCSPSolver:
    def __init__(self, request: FloorPlanRequest, grid_step: int = 1, max_steps: int = 200_000):
        self.plot = request.plot
        self.rooms = request.rooms
        self.grid_step = grid_step
        self.max_steps = max_steps
        self._steps = 0

    # ---------- Domain generation ----------

    def _candidate_rects(self, room: Room) -> List[Rect]:
        """All grid-aligned rectangles that satisfy this room's own area/shape rules."""
        candidates = []
        step = self.grid_step
        for w in range(room.min_dim, self.plot.width + 1, step):
            for h in range(room.min_dim, self.plot.height + 1, step):
                area = w * h
                if area < room.min_area or area > room.max_area:
                    continue
                for x in range(0, self.plot.width - w + 1, step):
                    for y in range(0, self.plot.height - h + 1, step):
                        r = Rect(x, y, w, h)
                        if room.needs_exterior_wall and not self._on_boundary(r):
                            continue
                        candidates.append(r)
        return candidates

    def _on_boundary(self, r: Rect) -> bool:
        return r.x == 0 or r.y == 0 or r.x2 == self.plot.width or r.y2 == self.plot.height

    # ---------- Constraint checks ----------

    def _consistent(self, name: str, rect: Rect, assignment: Dict[str, Rect]) -> bool:
        if not self.plot.contains(rect):
            return False
        for other_name, other_rect in assignment.items():
            if rect.overlaps(other_rect):
                return False
        room = self._room_by_name(name)
        for neighbor_name in room.adjacent_to:
            if neighbor_name in assignment:
                if not rect.touches(assignment[neighbor_name]):
                    return False
        # also check reverse direction: if a later room declares this one as neighbor
        for other_name, other_rect in assignment.items():
            other_room = self._room_by_name(other_name)
            if name in other_room.adjacent_to and not rect.touches(other_rect):
                return False
        return True

    def _room_by_name(self, name: str) -> Room:
        return next(r for r in self.rooms if r.name == name)

    # ---------- Forward checking ----------

    def _forward_check(self, domains: Dict[str, List[Rect]], placed_name: str,
                        placed_rect: Rect, assignment: Dict[str, Rect]) -> Optional[Dict[str, List[Rect]]]:
        """Prune domains of unassigned rooms given the new placement.
        Returns the pruned domains, or None if any domain became empty (dead end)."""
        new_domains = dict(domains)
        for name, domain in domains.items():
            if name in assignment or name == placed_name:
                continue
            pruned = [r for r in domain if self._consistent(name, r, {**assignment, placed_name: placed_rect})]
            if not pruned:
                return None
            new_domains[name] = pruned
        return new_domains

    # ---------- Main search ----------

    def solve(self) -> Dict[str, Rect]:
        domains = {room.name: self._candidate_rects(room) for room in self.rooms}
        for room in self.rooms:
            if not domains[room.name]:
                raise NoSolutionError(
                    f"Room '{room.name}' has no valid placement at all "
                    f"(check min/max_area vs plot size)."
                )
        assignment: Dict[str, Rect] = {}
        result = self._backtrack(assignment, domains)
        if result is None:
            raise NoSolutionError(
                "No layout satisfies all constraints. Try relaxing adjacency "
                "requirements or area ranges, or increasing plot size."
            )
        return result

    def _select_unassigned_room(self, assignment: Dict[str, Rect], domains: Dict[str, List[Rect]]) -> str:
        """Minimum Remaining Values (MRV) heuristic: pick the room with the fewest options left."""
        unassigned = [r.name for r in self.rooms if r.name not in assignment]
        return min(unassigned, key=lambda n: len(domains[n]))

    def _backtrack(self, assignment: Dict[str, Rect], domains: Dict[str, List[Rect]]) -> Optional[Dict[str, Rect]]:
        self._steps += 1
        if self._steps > self.max_steps:
            return None  # search budget exhausted

        if len(assignment) == len(self.rooms):
            return dict(assignment)

        name = self._select_unassigned_room(assignment, domains)
        for rect in domains[name]:
            if not self._consistent(name, rect, assignment):
                continue
            assignment[name] = rect
            pruned_domains = self._forward_check(domains, name, rect, assignment)
            if pruned_domains is not None:
                result = self._backtrack(assignment, pruned_domains)
                if result is not None:
                    return result
            del assignment[name]
        return None
