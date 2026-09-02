"""
Computational geometry: collision/overlap detection.

Every other stage depends on this to stay valid:
  - room-vs-room and most furniture-vs-furniture checks only need
    axis-aligned bounding box (AABB) overlap — fast, and what
    models.Rect.overlaps() already does for rooms.
  - once furniture can be *rotated* (a bed turned 90 degrees, an angled
    sofa), AABB alone is wrong — you need the Separating Axis Theorem
    (SAT) for general convex polygons, implemented here.
  - clearance checks go one step further than "don't overlap": they
    validate a minimum walkway gap between items, not just non-collision.
"""

from dataclasses import dataclass
from typing import List, Tuple
import math

Point = Tuple[float, float]


@dataclass
class Polygon:
    """A convex polygon as an ordered list of (x, y) vertices."""
    points: List[Point]

    @classmethod
    def from_rect(cls, x: float, y: float, w: float, h: float, rotation_deg: float = 0.0) -> "Polygon":
        """Build a rectangle polygon, optionally rotated about its own center."""
        cx, cy = x + w / 2, y + h / 2
        corners = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
        if rotation_deg == 0:
            return cls(corners)
        theta = math.radians(rotation_deg)
        cos_t, sin_t = math.cos(theta), math.sin(theta)
        rotated = []
        for px, py in corners:
            dx, dy = px - cx, py - cy
            rotated.append((dx * cos_t - dy * sin_t + cx, dx * sin_t + dy * cos_t + cy))
        return cls(rotated)

    def edges(self) -> List[Tuple[Point, Point]]:
        n = len(self.points)
        return [(self.points[i], self.points[(i + 1) % n]) for i in range(n)]


def _axes(poly: Polygon) -> List[Point]:
    axes = []
    for (x1, y1), (x2, y2) in poly.edges():
        edge = (x2 - x1, y2 - y1)
        normal = (-edge[1], edge[0])
        length = math.hypot(*normal)
        if length > 1e-9:
            axes.append((normal[0] / length, normal[1] / length))
    return axes


def _project(poly: Polygon, axis: Point) -> Tuple[float, float]:
    dots = [px * axis[0] + py * axis[1] for px, py in poly.points]
    return min(dots), max(dots)


def polygons_overlap(a: Polygon, b: Polygon) -> bool:
    """Separating Axis Theorem: two convex polygons overlap if and only if
    there is NO axis (perpendicular to some edge of either polygon) along
    which their projections fail to overlap. Handles rotated rectangles;
    AABB checks alone give wrong answers once rotation is involved."""
    for axis in _axes(a) + _axes(b):
        min_a, max_a = _project(a, axis)
        min_b, max_b = _project(b, axis)
        if max_a < min_b or max_b < min_a:
            return False  # found a separating axis -> definitely no collision
    return True


def aabb_overlap(x1, y1, w1, h1, x2, y2, w2, h2) -> bool:
    """Fast axis-aligned bounding-box overlap test (the common, non-rotated case)."""
    return not (x1 + w1 <= x2 or x2 + w2 <= x1 or y1 + h1 <= y2 or y2 + h2 <= y1)


def min_clearance_ok(x1, y1, w1, h1, x2, y2, w2, h2, min_clearance: float) -> bool:
    """True if two axis-aligned rects don't overlap AND are at least
    min_clearance apart (a walkway/clearance check, stricter than plain
    non-overlap)."""
    if aabb_overlap(x1, y1, w1, h1, x2, y2, w2, h2):
        return False
    gap_x = max(x2 - (x1 + w1), x1 - (x2 + w2), 0)
    gap_y = max(y2 - (y1 + h1), y1 - (y2 + h2), 0)
    if gap_x > 0 and gap_y > 0:
        return math.hypot(gap_x, gap_y) >= min_clearance  # separated diagonally
    return max(gap_x, gap_y) >= min_clearance  # separated along one axis only


def point_in_rect(px: float, py: float, x: float, y: float, w: float, h: float) -> bool:
    return x <= px <= x + w and y <= py <= y + h
