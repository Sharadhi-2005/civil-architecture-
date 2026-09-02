"""
report_generator.py
====================
Turns structured floor-plan data (room areas, adjacency compliance,
material estimates) into a formatted, client-ready PDF technical report
using template-based NLG (natural language generation) + ReportLab
Platypus for layout.

NLG here is deterministic template selection + slot-filling, NOT an LLM
call -- this guarantees numbers in the report are always exactly what's
in the structured data, with no hallucination risk, while still varying
phrasing across rooms/sections so the report doesn't read like a raw
data dump.

Usage:
    python3 report_generator.py     # reads layout.json -> report.pdf
"""

import json
import random
from datetime import date
from dataclasses import dataclass
from typing import List, Dict, Optional

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak,
)


# ---------------------------------------------------------------------------
# Compliance rules (data-driven; add more rule types freely)
# ---------------------------------------------------------------------------

MIN_HABITABLE_AREA = {
    "bedroom": 9.0,
    "living": 14.0,
    "kitchen": 6.5,
    "bathroom": 3.0,
    "circulation": 2.0,
}

# --- NLG template banks: {rule_type: [templates]} -----------------------
# {room}, {value}, {threshold} are filled in at render time.
PASS_TEMPLATES = {
    "area": [
        "The {room} ({value:.1f} m²) meets the minimum habitable area "
        "requirement of {threshold:.1f} m².",
        "At {value:.1f} m², the {room} satisfies the {threshold:.1f} m² "
        "minimum area standard for its room type.",
        "{room} is compliant on area, providing {value:.1f} m² against a "
        "{threshold:.1f} m² requirement.",
    ],
    "adjacency": [
        "{room} is correctly positioned adjacent to {other}, as required.",
        "The required adjacency between {room} and {other} is satisfied "
        "in this layout.",
    ],
}

FAIL_TEMPLATES = {
    "area": [
        "The {room} falls short of the minimum habitable area: {value:.1f} m² "
        "provided against a {threshold:.1f} m² requirement.",
        "{room} does not meet the area standard for its room type "
        "({value:.1f} m² vs. a required {threshold:.1f} m²).",
    ],
    "adjacency": [
        "{room} is not adjacent to {other}, which the brief requires.",
        "The layout does not satisfy the required adjacency between "
        "{room} and {other}.",
    ],
}


@dataclass
class ComplianceCheck:
    rule_type: str          # "area" | "adjacency"
    room: str
    passed: bool
    value: float = 0.0
    threshold: float = 0.0
    other: Optional[str] = None


@dataclass
class MaterialEstimate:
    material: str
    quantity: float
    unit: str
    unit_cost: float

    @property
    def total_cost(self) -> float:
        return self.quantity * self.unit_cost


# ---------------------------------------------------------------------------
# NLG layer
# ---------------------------------------------------------------------------

def narrate(check: ComplianceCheck) -> str:
    bank = PASS_TEMPLATES if check.passed else FAIL_TEMPLATES
    template = random.choice(bank[check.rule_type])
    return template.format(room=check.room, value=check.value,
                            threshold=check.threshold, other=check.other or "")


def run_compliance_checks(rooms: List[dict], adjacency_requirements: List[tuple]) -> List[ComplianceCheck]:
    checks = []
    for room in rooms:
        threshold = MIN_HABITABLE_AREA.get(room["room_type"], 0.0)
        area = room["w"] * room["h"]
        checks.append(ComplianceCheck(
            rule_type="area", room=room["name"], passed=area >= threshold,
            value=area, threshold=threshold,
        ))

    room_by_name = {r["name"]: r for r in rooms}

    def touches(a, b, tol=0.05):
        ax1, ay1, ax2, ay2 = a["x"], a["y"], a["x"] + a["w"], a["y"] + a["h"]
        bx1, by1, bx2, by2 = b["x"], b["y"], b["x"] + b["w"], b["y"] + b["h"]
        vertical = (abs(ax2 - bx1) < tol or abs(bx2 - ax1) < tol) and (ay1 < by2 and by1 < ay2)
        horizontal = (abs(ay2 - by1) < tol or abs(by2 - ay1) < tol) and (ax1 < bx2 and bx1 < ax2)
        return vertical or horizontal

    for room_name, other_name in adjacency_requirements:
        if room_name not in room_by_name or other_name not in room_by_name:
            continue
        ok = touches(room_by_name[room_name], room_by_name[other_name])
        checks.append(ComplianceCheck(
            rule_type="adjacency", room=room_name, other=other_name, passed=ok,
        ))
    return checks


def estimate_materials(rooms: List[dict]) -> List[MaterialEstimate]:
    """Simple rule-based quantity takeoff -- swap in a real BOQ engine later."""
    total_floor_area = sum(r["w"] * r["h"] for r in rooms)
    total_wall_length = sum(2 * (r["w"] + r["h"]) for r in rooms) * 0.5  # rough, shared walls counted once-ish
    wall_area = total_wall_length * 2.7  # wall height

    return [
        MaterialEstimate("Flooring (tile/wood)", round(total_floor_area * 1.05, 1), "m²", 28.0),
        MaterialEstimate("Wall plaster/paint", round(wall_area, 1), "m²", 6.5),
        MaterialEstimate("Concrete (slab)", round(total_floor_area * 0.12, 1), "m³", 145.0),
        MaterialEstimate("Bricks/blockwork", round(wall_area * 55, 0), "units", 0.45),
    ]


# ---------------------------------------------------------------------------
# PDF assembly
# ---------------------------------------------------------------------------

def build_report(layout: dict, project_name: str = "Residence Design",
                  iteration: int = 1, adjacency_requirements: Optional[List[tuple]] = None,
                  floor_plan_image: Optional[str] = None, out_path: str = "report.pdf"):

    rooms = layout["rooms"]
    adjacency_requirements = adjacency_requirements or []
    checks = run_compliance_checks(rooms, adjacency_requirements)
    materials = estimate_materials(rooms)

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="ReportBody", parent=styles["Normal"], spaceAfter=8, leading=15))
    styles.add(ParagraphStyle(name="SectionHeading", parent=styles["Heading2"], spaceBefore=16, spaceAfter=8))

    doc = SimpleDocTemplate(out_path, pagesize=letter,
                             topMargin=2 * cm, bottomMargin=2 * cm,
                             leftMargin=2 * cm, rightMargin=2 * cm)
    story = []

    # --- Cover ---
    story.append(Spacer(1, 4 * cm))
    story.append(Paragraph(project_name, styles["Title"]))
    story.append(Paragraph(f"Design Iteration {iteration}", styles["Heading3"]))
    story.append(Paragraph(f"Generated {date.today().isoformat()}", styles["Normal"]))
    story.append(PageBreak())

    # --- Floor plan image ---
    if floor_plan_image:
        from reportlab.platypus import Image
        story.append(Paragraph("Floor Plan", styles["SectionHeading"]))
        story.append(Image(floor_plan_image, width=16 * cm, height=11 * cm, kind="proportional"))
        story.append(PageBreak())

    # --- Room schedule table ---
    story.append(Paragraph("Room Schedule", styles["SectionHeading"]))
    table_data = [["Room", "Type", "Width (m)", "Height (m)", "Area (m²)"]]
    total_area = 0.0
    for r in rooms:
        area = r["w"] * r["h"]
        total_area += area
        table_data.append([r["name"], r["room_type"], f'{r["w"]:.2f}', f'{r["h"]:.2f}', f"{area:.2f}"])
    table_data.append(["", "", "", "Total", f"{total_area:.2f}"])

    t = Table(table_data, colWidths=[4.5 * cm, 3 * cm, 3 * cm, 3 * cm, 3 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2b3a55")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, colors.HexColor("#f2f4f8")]),
        ("ALIGN", (2, 0), (-1, -1), "CENTER"),
    ]))
    story.append(t)
    story.append(Spacer(1, 12))

    # --- Compliance narrative (NLG) ---
    story.append(Paragraph("Code & Design Compliance", styles["SectionHeading"]))
    passed = [c for c in checks if c.passed]
    failed = [c for c in checks if not c.passed]
    summary = (f"Of {len(checks)} checks performed against area and adjacency "
               f"requirements, {len(passed)} passed and {len(failed)} require attention.")
    story.append(Paragraph(summary, styles["ReportBody"]))

    for check in checks:
        sentence = narrate(check)
        color = "#1a7a3c" if check.passed else "#b3261e"
        story.append(Paragraph(f'<font color="{color}">●</font> {sentence}', styles["ReportBody"]))

    story.append(Spacer(1, 12))

    # --- Material estimate table ---
    story.append(Paragraph("Material Estimate", styles["SectionHeading"]))
    mat_data = [["Material", "Quantity", "Unit", "Unit Cost", "Est. Cost"]]
    grand_total = 0.0
    for m in materials:
        grand_total += m.total_cost
        mat_data.append([m.material, f"{m.quantity:g}", m.unit, f"{m.unit_cost:.2f}", f"{m.total_cost:,.2f}"])
    mat_data.append(["", "", "", "Total", f"{grand_total:,.2f}"])

    mt = Table(mat_data, colWidths=[5 * cm, 2.5 * cm, 2 * cm, 3 * cm, 3.5 * cm])
    mt.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2b3a55")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, colors.HexColor("#f2f4f8")]),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
    ]))
    story.append(mt)

    # --- Appendix: raw data snapshot ---
    story.append(PageBreak())
    story.append(Paragraph("Appendix: Raw Data Snapshot", styles["SectionHeading"]))
    story.append(Paragraph(f"<font face='Courier' size=8>{json.dumps(layout, indent=2)}</font>",
                            styles["ReportBody"]))

    doc.build(story)


def demo():
    with open("layout.json") as f:
        layout = json.load(f)

    adjacency_requirements = [
        ("Living Room", "Kitchen"),
        ("Living Room", "Entry"),
        ("Bathroom", "Bedroom 1"),
    ]

    build_report(layout, project_name="Sample Residence",
                 iteration=1, adjacency_requirements=adjacency_requirements,
                 out_path="report.pdf")
    print("Wrote report.pdf")


if __name__ == "__main__":
    demo()
