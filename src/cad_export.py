"""
CAD export: turns the final 2D layout into a DXF file.

Written as a raw ASCII DXF (R12 entity set: POLYLINE/VERTEX, TEXT,
3DFACE) using nothing but the standard library — no `ezdxf` dependency
needed, so this runs anywhere Python runs. DXF R12's entity set is
simple enough to hand-write correctly and opens in AutoCAD, FreeCAD,
LibreCAD, and any other CAD software.

Two things happen here:
  1. 2D export: each room becomes a closed POLYLINE outline + a TEXT
     label; furniture becomes its own closed POLYLINE per item.
  2. 3D wall extrusion (polygon extrusion / boolean-geometry family):
     each 2D room-outline edge is a wall segment. "Extruding" it to a
     wall height just means adding a second, height-offset copy of that
     edge and stitching the two into a vertical rectangular 3DFACE —
     literally turning a 2D footprint into a 3D solid face, the same
     operation FreeCAD's "Extrude" tool performs on a sketch.
"""

from typing import Dict, List, Optional
from .models import Rect
from .interior_rules import FurnitureItem


def _room_polygon(rect: Rect) -> List[tuple]:
    """Closed polygon (5 points, last == first) for a room outline."""
    return [
        (rect.x, rect.y), (rect.x2, rect.y),
        (rect.x2, rect.y2), (rect.x, rect.y2), (rect.x, rect.y),
    ]


class DXFWriter:
    """Minimal hand-rolled DXF R12 ASCII writer — just the entities this
    project needs (POLYLINE, TEXT, 3DFACE), nothing else."""

    def __init__(self):
        self._lines: List[str] = ["0", "SECTION", "2", "ENTITIES"]

    def _pair(self, code: int, value):
        self._lines.append(str(code))
        self._lines.append(str(value))

    def add_polyline(self, points: List[tuple], layer: str):
        self._pair(0, "POLYLINE")
        self._pair(8, layer)
        self._pair(66, 1)   # "vertices follow" flag
        self._pair(70, 1)   # closed polyline flag
        for x, y in points:
            self._pair(0, "VERTEX")
            self._pair(8, layer)
            self._pair(10, round(x, 4))
            self._pair(20, round(y, 4))
        self._pair(0, "SEQEND")

    def add_text(self, text: str, x: float, y: float, height: float, layer: str):
        self._pair(0, "TEXT")
        self._pair(8, layer)
        self._pair(10, round(x, 4))
        self._pair(20, round(y, 4))
        self._pair(40, height)
        self._pair(1, text)

    def add_3dface(self, p1, p2, p3, p4, layer: str):
        self._pair(0, "3DFACE")
        self._pair(8, layer)
        for code_base, (x, y, z) in zip((10, 11, 12, 13), (p1, p2, p3, p4)):
            self._pair(code_base, round(x, 4))
            self._pair(code_base + 10, round(y, 4))
            self._pair(code_base + 20, round(z, 4))

    def save(self, out_path: str) -> str:
        self._lines += ["0", "ENDSEC", "0", "EOF"]
        with open(out_path, "w") as f:
            f.write("\n".join(self._lines) + "\n")
        return out_path


def export_floorplan_dxf(assignment: Dict[str, Rect],
                          furniture: Optional[Dict[str, List[FurnitureItem]]] = None,
                          out_path: str = "floorplan.dxf",
                          wall_height: Optional[float] = None) -> str:
    """
    Writes a DXF file with:
      - ROOMS layer: closed polyline outline per room
      - LABELS layer: room name as text, centered in each room
      - FURNITURE layer: closed polyline + label per furniture item, if provided
      - WALLS_3D layer: vertical extruded wall faces, only if wall_height is given
    """
    dxf = DXFWriter()

    for name, rect in assignment.items():
        poly = _room_polygon(rect)
        dxf.add_polyline(poly, layer="ROOMS")
        cx, cy = rect.x + rect.w / 2, rect.y + rect.h / 2
        dxf.add_text(name, cx, cy, height=0.3, layer="LABELS")

        if wall_height:
            for (x1, y1), (x2, y2) in zip(poly[:-1], poly[1:]):
                dxf.add_3dface(
                    (x1, y1, 0), (x2, y2, 0), (x2, y2, wall_height), (x1, y1, wall_height),
                    layer="WALLS_3D",
                )

    if furniture:
        for items in furniture.values():
            for item in items:
                poly = [
                    (item.x, item.y), (item.x + item.w, item.y),
                    (item.x + item.w, item.y + item.h), (item.x, item.y + item.h),
                    (item.x, item.y),
                ]
                dxf.add_polyline(poly, layer="FURNITURE")
                dxf.add_text(item.name, item.x + item.w / 2, item.y + item.h / 2,
                             height=0.15, layer="FURNITURE")

    return dxf.save(out_path)
