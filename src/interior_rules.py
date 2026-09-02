"""
Rule-based expert system for interior furniture placement.

Once a room's rectangle and type are known, this places furniture using
explicit IF-THEN heuristics (an "expert system" in the classical AI
sense) instead of learning them from data — cheap, explainable, and
mirrors how architects actually follow convention:
  - beds go against a wall
  - tables get centered in dining/living spaces
  - kitchen counters run along the longest wall
  - wardrobes take an unused corner
Every placement is validated against geometry_utils so nothing overlaps
and (where checked) clearance gaps are respected.
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple
from .models import Rect
from .geometry_utils import aabb_overlap, min_clearance_ok

MIN_CLEARANCE = 0.6  # required walkway clearance, in the same units as room area/position


@dataclass
class FurnitureItem:
    name: str
    x: float
    y: float
    w: float
    h: float


def _place_against_wall(room: Rect, w: float, h: float, wall: str, margin: float = 0.0) -> Tuple[float, float]:
    if wall == "top":
        return room.x + (room.w - w) / 2, room.y + margin
    if wall == "bottom":
        return room.x + (room.w - w) / 2, room.y + room.h - h - margin
    if wall == "left":
        return room.x + margin, room.y + (room.h - h) / 2
    if wall == "right":
        return room.x + room.w - w - margin, room.y + (room.h - h) / 2
    raise ValueError(f"unknown wall '{wall}'")


def _place_centered(room: Rect, w: float, h: float) -> Tuple[float, float]:
    return room.x + (room.w - w) / 2, room.y + (room.h - h) / 2


def _fits(room: Rect, x: float, y: float, w: float, h: float) -> bool:
    return room.x <= x and room.y <= y and x + w <= room.x2 and y + h <= room.y2


def _no_collision(placed: List[FurnitureItem], x, y, w, h) -> bool:
    return all(not aabb_overlap(x, y, w, h, it.x, it.y, it.w, it.h) for it in placed)


def _try_add(placed: List[FurnitureItem], room: Rect, name: str, w: float, h: float, candidates) -> bool:
    """Try each candidate (x, y) in priority order; place the first that
    fits inside the room and doesn't collide with what's already placed."""
    for x, y in candidates:
        if _fits(room, x, y, w, h) and _no_collision(placed, x, y, w, h):
            placed.append(FurnitureItem(name, x, y, w, h))
            return True
    return False


def place_bedroom(room: Rect) -> List[FurnitureItem]:
    placed: List[FurnitureItem] = []
    bed_w, bed_h = min(2.0, room.w * 0.5), min(2.0, room.h * 0.5)
    # Rule: bed against a long wall, trying the top wall first
    _try_add(placed, room, "bed", bed_w, bed_h, [
        _place_against_wall(room, bed_w, bed_h, "top"),
        _place_against_wall(room, bed_w, bed_h, "left"),
        _place_against_wall(room, bed_w, bed_h, "bottom"),
    ])
    # Rule: wardrobe takes a corner not already occupied
    wr_w, wr_h = min(1.2, room.w * 0.3), 0.6
    _try_add(placed, room, "wardrobe", wr_w, wr_h, [
        (room.x, room.y), (room.x2 - wr_w, room.y),
        (room.x, room.y2 - wr_h), (room.x2 - wr_w, room.y2 - wr_h),
    ])
    return placed


def place_living(room: Rect) -> List[FurnitureItem]:
    placed: List[FurnitureItem] = []
    # Rule: sofa against the longest wall
    sofa_w, sofa_h = min(2.2, room.w * 0.6), 0.8
    wall = "top" if room.w >= room.h else "left"
    _try_add(placed, room, "sofa", sofa_w, sofa_h, [_place_against_wall(room, sofa_w, sofa_h, wall)])
    # Rule: coffee table centered
    table_w, table_h = 1.0, 0.6
    _try_add(placed, room, "coffee_table", table_w, table_h, [_place_centered(room, table_w, table_h)])
    return placed


def place_dining(room: Rect) -> List[FurnitureItem]:
    placed: List[FurnitureItem] = []
    table_w, table_h = min(1.6, room.w * 0.5), min(1.0, room.h * 0.5)
    _try_add(placed, room, "dining_table", table_w, table_h, [_place_centered(room, table_w, table_h)])
    return placed


def place_kitchen(room: Rect) -> List[FurnitureItem]:
    placed: List[FurnitureItem] = []
    # Rule: counter runs along the longest wall
    if room.w >= room.h:
        counter_w, counter_h, wall = room.w, 0.6, "top"
    else:
        counter_w, counter_h, wall = 0.6, room.h, "left"
    _try_add(placed, room, "counter", counter_w, counter_h, [_place_against_wall(room, counter_w, counter_h, wall)])
    return placed


def place_bathroom(room: Rect) -> List[FurnitureItem]:
    placed: List[FurnitureItem] = []
    fx_w, fx_h = 0.7, 0.5
    _try_add(placed, room, "fixture", fx_w, fx_h, [_place_against_wall(room, fx_w, fx_h, "left")])
    return placed


RULES = {
    "bedroom": place_bedroom,
    "living": place_living,
    "dining": place_dining,
    "kitchen": place_kitchen,
    "bathroom": place_bathroom,
    "bath": place_bathroom,
}


def place_furniture(room_name: str, room_rect: Rect) -> List[FurnitureItem]:
    """Dispatch to the rule set matching this room's type (by name prefix).
    Rooms with no matching rule (e.g. 'entrance') simply get no furniture."""
    lower = room_name.lower()
    for prefix, rule_fn in RULES.items():
        if lower.startswith(prefix):
            return rule_fn(room_rect)
    return []


def place_all_furniture(assignment: Dict[str, Rect]) -> Dict[str, List[FurnitureItem]]:
    return {name: place_furniture(name, rect) for name, rect in assignment.items()}


def validate_clearances(furniture: List[FurnitureItem], min_clearance: float = MIN_CLEARANCE) -> List[str]:
    """Returns human-readable clearance violations (empty list = all clear)."""
    violations = []
    for i in range(len(furniture)):
        for j in range(i + 1, len(furniture)):
            a, b = furniture[i], furniture[j]
            if not min_clearance_ok(a.x, a.y, a.w, a.h, b.x, b.y, b.w, b.h, min_clearance):
                violations.append(f"{a.name} and {b.name} are closer than {min_clearance}m apart")
    return violations
