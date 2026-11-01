"""Strict CAD specifications and construction-independent geometric constraints."""
from __future__ import annotations

import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

DEFAULTS = {
    "bracket": dict(height=80.0, width=50.0, depth=40.0, thickness=4.0, hole_count=2, hole_diameter=5.0),
    "plate": dict(length=100.0, width=60.0, thickness=4.0, hole_count=4, hole_diameter=5.0),
    "box": dict(length=100.0, width=70.0, height=50.0, wall_thickness=3.0),
}
TITLES = {"bracket": "L-shaped bracket", "plate": "Mounting plate", "box": "Open-top box"}
EDGE_CLEARANCE = 0.5


class Hole(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    face: Literal["base", "upright"] = "base"
    x: float
    y: float
    diameter: float = Field(gt=0, le=500)


def auto_holes(shape: str, d: dict) -> list[Hole]:
    """On brackets, holes run up the upright. Plates use corners for four holes."""
    count = int(d.get("hole_count", 0))
    if not count:
        return []
    diameter = d["hole_diameter"]
    if shape == "bracket":
        t = d["thickness"]
        return [Hole(face="upright", x=d["width"] / 2,
                     y=t + (d["height"] - t) * (i + 1) / (count + 1), diameter=diameter)
                for i in range(count)]
    length, width = d["length"], d["width"]
    if count == 4:
        mx = max(diameter / 2 + 1, length * .12)
        my = max(diameter / 2 + 1, width * .15)
        return [Hole(x=x, y=y, diameter=diameter)
                for x, y in [(mx, my), (length-mx, my), (length-mx, width-my), (mx, width-my)]]
    return [Hole(x=length*(i+1)/(count+1), y=width/2, diameter=diameter) for i in range(count)]


class ShapeSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    shape_type: Literal["bracket", "plate", "box"]
    dimensions: dict[str, float]
    units: Literal["mm"] = "mm"
    hole_layout: Literal["auto", "custom"] = "auto"
    holes: list[Hole] = Field(default_factory=list, max_length=12)
    assumptions: list[str] = Field(default_factory=list, max_length=30)
    missing_parameters: list[str] = Field(default_factory=list, max_length=20)
    invalid_parameters: list[str] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def geometric_constraints(self):
        if self.invalid_parameters:
            raise ValueError("Please clarify: " + "; ".join(self.invalid_parameters))
        defaults = DEFAULTS[self.shape_type]
        unknown = set(self.dimensions) - set(defaults)
        if unknown:
            raise ValueError("Unsupported dimensions: " + ", ".join(sorted(unknown)))
        self.assumptions = list(dict.fromkeys(self.assumptions))
        for name, value in defaults.items():
            if name not in self.dimensions:
                self.dimensions[name] = value
                self.assumptions.append(f"Default {name.replace('_', ' ')}: {value:g}{'' if name == 'hole_count' else ' mm'}.")
        d = self.dimensions
        for name, value in d.items():
            if not math.isfinite(value):
                raise ValueError(f"{name} must be finite.")
            if name == "hole_count":
                if value != int(value) or not 0 <= value <= 12:
                    raise ValueError("Hole count must be a whole number between 0 and 12.")
            elif not .5 <= value <= 1000:
                raise ValueError(f"{name.replace('_', ' ').capitalize()} must be between 0.5 and 1000 mm.")
        if self.shape_type == "box":
            t = d["wall_thickness"]
            if 2*t >= min(d["length"], d["width"]) or t >= d["height"]:
                raise ValueError("Wall thickness must be less than half the length/width and less than the height.")
            if self.holes:
                raise ValueError("The open-top box does not support holes in this MVP.")
        else:
            t = d["thickness"]
            limits = [d["width"], d.get("length", d.get("depth")), d.get("height", 1000)]
            if t >= min(limits):
                raise ValueError("Thickness must be smaller than every outside dimension.")
            if self.hole_layout == "auto":
                self.holes = auto_holes(self.shape_type, d)
            if len(self.holes) != int(d["hole_count"]):
                raise ValueError("Hole count must match the number of custom hole locations.")
        for i, hole in enumerate(self.holes):
            if self.shape_type == "plate" and hole.face != "base":
                raise ValueError("Plate holes must be on the base face.")
            xmax = d["width"] if self.shape_type == "bracket" else d["length"]
            ymin = d["thickness"] if self.shape_type == "bracket" else 0
            ymax = d["height"] if hole.face == "upright" else d.get("depth", d["width"])
            radius = hole.diameter / 2
            if not (radius+EDGE_CLEARANCE <= hole.x <= xmax-radius-EDGE_CLEARANCE
                    and ymin+radius+EDGE_CLEARANCE <= hole.y <= ymax-radius-EDGE_CLEARANCE):
                raise ValueError(f"Hole {i+1} breaks through an edge or the bracket corner. Move it inward, reduce its diameter, or enlarge the part (0.5 mm minimum clearance).")
            for other in self.holes[:i]:
                if hole.face == other.face and math.hypot(hole.x-other.x, hole.y-other.y) < (hole.diameter+other.diameter)/2 + EDGE_CLEARANCE:
                    raise ValueError("Holes overlap or have less than 0.5 mm material between them. Reduce their count/diameter or increase spacing.")
        return self


def default_spec(shape: str = "bracket") -> ShapeSpec:
    return ShapeSpec(shape_type=shape, dimensions={})


def validation_message(exc: Exception) -> str:
    if hasattr(exc, "errors"):
        return " · ".join(str(e["msg"]).removeprefix("Value error, ") for e in exc.errors(include_url=False))
    return str(exc)
