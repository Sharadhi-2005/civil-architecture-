"""
mesh_generator.py
==================
Converts a 2D floor plan (room rectangles) into a 3D mesh via procedural
extrusion, and exports it as a Wavefront OBJ file that can be imported
directly into Three.js, Unity, or Unreal.

Algorithm (see README.md section 3 for full pseudocode):
  1. For each room -> derive its 4 bounding walls as line segments.
  2. De-duplicate shared walls between adjacent rooms (within tolerance)
     so we don't emit a double-thickness wall where two rooms touch.
  3. Extrude each unique wall segment into a rectangular box (8 verts).
  4. Emit a floor quad per room at z = 0.
  5. Write everything as OBJ (v / f records).

Usage:
    python3 mesh_generator.py            # reads layout.json -> floor_plan.obj
"""

import json
from dataclasses import dataclass
from typing import List, Tuple, Dict


WALL_THICKNESS = 0.15   # meters
WALL_HEIGHT = 2.7        # meters


@dataclass
class Wall:
    x1: float
    y1: float
    x2: float
    y2: float

    def key(self, tol: float = 0.05) -> Tuple[float, float, float, float]:
        """Rounded, order-independent key so shared walls collapse to one entry."""
        pts = sorted([(round(self.x1 / tol) * tol, round(self.y1 / tol) * tol),
                      (round(self.x2 / tol) * tol, round(self.y2 / tol) * tol)])
        return (pts[0][0], pts[0][1], pts[1][0], pts[1][1])


class OBJMesh:
    """Minimal OBJ vertex/face accumulator."""

    def __init__(self):
        self.vertices: List[Tuple[float, float, float]] = []
        self.faces: List[Tuple[int, int, int, int]] = []  # 1-indexed quads

    def add_quad(self, v0, v1, v2, v3):
        start = len(self.vertices) + 1
        self.vertices.extend([v0, v1, v2, v3])
        self.faces.append((start, start + 1, start + 2, start + 3))

    def add_box(self, x1, y1, x2, y2, z0, z1):
        """Extrude a rectangle in the XY plane from z0 to z1 into a box (6 faces)."""
        # bottom face
        self.add_quad((x1, y1, z0), (x2, y1, z0), (x2, y2, z0), (x1, y2, z0))
        # top face
        self.add_quad((x1, y1, z1), (x1, y2, z1), (x2, y2, z1), (x2, y1, z1))
        # 4 side faces
        self.add_quad((x1, y1, z0), (x1, y2, z0), (x1, y2, z1), (x1, y1, z1))
        self.add_quad((x2, y1, z0), (x2, y1, z1), (x2, y2, z1), (x2, y2, z0))
        self.add_quad((x1, y1, z0), (x1, y1, z1), (x2, y1, z1), (x2, y1, z0))
        self.add_quad((x1, y2, z0), (x2, y2, z0), (x2, y2, z1), (x1, y2, z1))

    def add_floor(self, x1, y1, x2, y2, z=0.0):
        self.add_quad((x1, y1, z), (x2, y1, z), (x2, y2, z), (x1, y2, z))

    def write(self, path: str, object_name: str = "FloorPlan"):
        with open(path, "w") as f:
            f.write(f"# Generated procedural mesh: {object_name}\n")
            f.write(f"o {object_name}\n")
            for v in self.vertices:
                f.write(f"v {v[0]:.4f} {v[1]:.4f} {v[2]:.4f}\n")
            for face in self.faces:
                f.write("f " + " ".join(str(i) for i in face) + "\n")


def walls_from_room(room: dict) -> List[Wall]:
    x, y, w, h = room["x"], room["y"], room["w"], room["h"]
    return [
        Wall(x, y, x + w, y),          # bottom
        Wall(x + w, y, x + w, y + h),  # right
        Wall(x + w, y + h, x, y + h),  # top
        Wall(x, y + h, x, y),          # left
    ]


def build_mesh(layout: dict) -> OBJMesh:
    mesh = OBJMesh()

    # 1. floors, one per room
    for room in layout["rooms"]:
        mesh.add_floor(room["x"], room["y"], room["x"] + room["w"], room["y"] + room["h"])

    # 2. deduplicate walls shared between adjacent rooms
    unique_walls: Dict[Tuple, Wall] = {}
    for room in layout["rooms"]:
        for wall in walls_from_room(room):
            unique_walls[wall.key()] = wall

    # 3. extrude each unique wall into a box
    for wall in unique_walls.values():
        dx, dy = wall.x2 - wall.x1, wall.y2 - wall.y1
        length = (dx ** 2 + dy ** 2) ** 0.5
        if length == 0:
            continue
        nx, ny = -dy / length, dx / length  # unit normal
        hw = WALL_THICKNESS / 2
        x1a, y1a = wall.x1 + nx * hw, wall.y1 + ny * hw
        x2a, y2a = wall.x2 + nx * hw, wall.y2 + ny * hw
        x1b, y1b = wall.x1 - nx * hw, wall.y1 - ny * hw
        x2b, y2b = wall.x2 - nx * hw, wall.y2 - ny * hw
        min_x, max_x = min(x1a, x2a, x1b, x2b), max(x1a, x2a, x1b, x2b)
        min_y, max_y = min(y1a, y2a, y1b, y2b), max(y1a, y2a, y1b, y2b)
        mesh.add_box(min_x, min_y, max_x, max_y, 0.0, WALL_HEIGHT)

    return mesh


def demo():
    with open("layout.json") as f:
        layout = json.load(f)

    mesh = build_mesh(layout)
    mesh.write("floor_plan.obj")
    print(f"Wrote floor_plan.obj: {len(mesh.vertices)} vertices, {len(mesh.faces)} faces")
    print("Import this directly into Three.js (OBJLoader), Unity, or Unreal.")
    print("\nReal-time update note: on each optimizer tick, regenerate only the "
          "boxes/floors for rooms that changed and push updated buffers to the "
          "GPU (see README.md section 3, step 4) rather than rebuilding the "
          "whole mesh every frame.")


if __name__ == "__main__":
    demo()
