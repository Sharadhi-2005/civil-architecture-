"""
Core data models for the floor plan CSP.

A Plot is the outer boundary. Each Room is a variable in the CSP whose
domain is the set of candidate rectangles (grid-aligned) it could occupy.
Constraints are checked against a full or partial assignment of
room -> rectangle.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class Rect:
    """An axis-aligned rectangle on the grid, in grid cells (not meters)."""
    x: int
    y: int
    w: int
    h: int

    @property
    def x2(self) -> int:
        return self.x + self.w

    @property
    def y2(self) -> int:
        return self.y + self.h

    @property
    def area(self) -> int:
        return self.w * self.h

    def overlaps(self, other: "Rect") -> bool:
        return not (
            self.x2 <= other.x or other.x2 <= self.x or
            self.y2 <= other.y or other.y2 <= self.y
        )

    def touches(self, other: "Rect") -> bool:
        """True if the two rectangles share a wall segment (adjacent, not overlapping)."""
        if self.overlaps(other):
            return False
        horiz_touch = (self.x2 == other.x or other.x2 == self.x) and \
            (min(self.y2, other.y2) - max(self.y, other.y) > 0)
        vert_touch = (self.y2 == other.y or other.y2 == self.y) and \
            (min(self.x2, other.x2) - max(self.x, other.x) > 0)
        return horiz_touch or vert_touch


@dataclass
class Plot:
    """The outer building boundary, in grid cells."""
    width: int
    height: int

    def contains(self, r: Rect) -> bool:
        return r.x >= 0 and r.y >= 0 and r.x2 <= self.width and r.y2 <= self.height


@dataclass
class Room:
    """A room to be placed. min/max_area are in grid cells (area units)."""
    name: str
    min_area: int
    max_area: int
    min_dim: int = 2          # smallest allowed side length (avoids sliver rooms)
    needs_exterior_wall: bool = False  # ventilation/lighting requirement
    adjacent_to: list = field(default_factory=list)  # room names that must touch this one


@dataclass
class FloorPlanRequest:
    plot: Plot
    rooms: list  # list[Room]
