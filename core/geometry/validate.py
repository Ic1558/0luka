"""Fail-closed validator for canonical geometry payloads (PR-B)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .canonicalize import DEFAULT_CONTRACT_PATH, canonicalize_geometry, load_contract


@dataclass(frozen=True)
class ValidationErrorItem:
    code: str
    path: str
    message: str


class GeometryValidationError(ValueError):
    def __init__(self, errors: list[ValidationErrorItem]) -> None:
        ordered = sorted(errors, key=lambda e: (e.path, e.code, e.message))
        self.errors = ordered
        text = "\n".join(f"{e.path} [{e.code}] {e.message}" for e in ordered)
        super().__init__(text)


@dataclass(frozen=True)
class ValidationRules:
    schema_version: str
    canonical_unit: str
    min_vertices: int
    require_closed_ring: bool
    require_non_self_intersection: bool
    require_non_zero_area: bool
    adjacency_m: float
    closure_m: float
    area_min_m2: float


def _load_validation_rules(contract_path: str | Path | None = None) -> ValidationRules:
    path = Path(contract_path) if contract_path else DEFAULT_CONTRACT_PATH
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("geometry contract must be a mapping")

    contract = load_contract(path)
    tol = raw.get("tolerances") or {}
    pv = raw.get("polygon_validity") or {}

    return ValidationRules(
        schema_version=contract.schema_version,
        canonical_unit=contract.canonical_unit,
        min_vertices=contract.min_vertices,
        require_closed_ring=contract.require_closed_ring,
        require_non_self_intersection=bool(pv.get("require_non_self_intersection", True)),
        require_non_zero_area=bool(pv.get("require_non_zero_area", True)),
        adjacency_m=float(tol.get("adjacency_m", 0.0)),
        closure_m=float(tol.get("closure_m", 0.0)),
        area_min_m2=float(tol.get("area_min_m2", 0.0)),
    )


def _distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _shoelace_area(vertices: list[tuple[float, float]]) -> float:
    if len(vertices) < 4:
        return 0.0
    area2 = 0.0
    for i in range(len(vertices) - 1):
        x1, y1 = vertices[i]
        x2, y2 = vertices[i + 1]
        area2 += (x1 * y2) - (x2 * y1)
    return abs(area2) / 2.0


def _orientation(a: tuple[float, float], b: tuple[float, float], c: tuple[float, float], eps: float) -> int:
    v = (b[1] - a[1]) * (c[0] - b[0]) - (b[0] - a[0]) * (c[1] - b[1])
    if abs(v) <= eps:
        return 0
    return 1 if v > 0 else 2


def _on_segment(a: tuple[float, float], b: tuple[float, float], c: tuple[float, float], eps: float) -> bool:
    return (
        min(a[0], c[0]) - eps <= b[0] <= max(a[0], c[0]) + eps
        and min(a[1], c[1]) - eps <= b[1] <= max(a[1], c[1]) + eps
    )


def _segments_intersect(
    p1: tuple[float, float],
    q1: tuple[float, float],
    p2: tuple[float, float],
    q2: tuple[float, float],
    eps: float,
) -> bool:
    o1 = _orientation(p1, q1, p2, eps)
    o2 = _orientation(p1, q1, q2, eps)
    o3 = _orientation(p2, q2, p1, eps)
    o4 = _orientation(p2, q2, q1, eps)

    if o1 != o2 and o3 != o4:
        return True

    if o1 == 0 and _on_segment(p1, p2, q1, eps):
        return True
    if o2 == 0 and _on_segment(p1, q2, q1, eps):
        return True
    if o3 == 0 and _on_segment(p2, p1, q2, eps):
        return True
    if o4 == 0 and _on_segment(p2, q1, q2, eps):
        return True
    return False


def _as_point(raw: Any) -> tuple[float, float] | None:
    if not isinstance(raw, list) or len(raw) != 2:
        return None
    x, y = raw[0], raw[1]
    if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
        return None
    if not math.isfinite(float(x)) or not math.isfinite(float(y)):
        return None
    return float(x), float(y)


def validate_canonical_geometry(data: dict[str, Any], contract_path: str | Path | None = None) -> None:
    if not isinstance(data, dict):
        raise GeometryValidationError([ValidationErrorItem("type", "root", "payload must be a mapping")])

    rules = _load_validation_rules(contract_path)
    errors: list[ValidationErrorItem] = []

    schema = data.get("schema_version")
    if schema != rules.schema_version:
        errors.append(
            ValidationErrorItem("schema_version", "schema_version", f"expected {rules.schema_version}, got {schema}")
        )

    unit = data.get("unit")
    if unit != rules.canonical_unit:
        errors.append(ValidationErrorItem("unit", "unit", f"expected {rules.canonical_unit}, got {unit}"))

    polygons = data.get("polygons")
    if not isinstance(polygons, list) or len(polygons) == 0:
        errors.append(ValidationErrorItem("polygons", "polygons", "must be a non-empty list"))
    else:
        eps = max(rules.closure_m, 1e-12)
        for pidx, poly in enumerate(polygons):
            ppath = f"polygons[{pidx}]"
            if not isinstance(poly, dict):
                errors.append(ValidationErrorItem("polygon_type", ppath, "polygon must be a mapping"))
                continue

            vertices_raw = poly.get("vertices")
            if not isinstance(vertices_raw, list):
                errors.append(ValidationErrorItem("vertices_type", f"{ppath}.vertices", "must be a list"))
                continue

            points: list[tuple[float, float]] = []
            for vidx, raw in enumerate(vertices_raw):
                pt = _as_point(raw)
                if pt is None:
                    errors.append(
                        ValidationErrorItem(
                            "vertex_numeric",
                            f"{ppath}.vertices[{vidx}]",
                            "vertex must be finite numeric [x, y]",
                        )
                    )
                    continue
                points.append(pt)

            if len(points) != len(vertices_raw):
                continue

            base_len = len(points) - 1 if len(points) >= 2 and points[0] == points[-1] else len(points)
            if base_len < rules.min_vertices:
                errors.append(
                    ValidationErrorItem(
                        "min_vertices",
                        f"{ppath}.vertices",
                        f"requires at least {rules.min_vertices} unique vertices",
                    )
                )

            if rules.require_closed_ring:
                if len(points) < 2 or _distance(points[0], points[-1]) > rules.closure_m:
                    errors.append(
                        ValidationErrorItem(
                            "closure",
                            f"{ppath}.vertices",
                            f"ring must close within {rules.closure_m}",
                        )
                    )

            if len(points) >= 2:
                for vidx in range(len(points) - 1):
                    edge = _distance(points[vidx], points[vidx + 1])
                    if edge < rules.adjacency_m:
                        errors.append(
                            ValidationErrorItem(
                                "adjacency",
                                f"{ppath}.vertices[{vidx}:{vidx + 1}]",
                                f"adjacent vertices distance {edge} below tolerance {rules.adjacency_m}",
                            )
                        )

            area = _shoelace_area(points)
            if rules.require_non_zero_area and area <= rules.area_min_m2:
                errors.append(
                    ValidationErrorItem(
                        "area",
                        f"{ppath}.area",
                        f"area {area} must be > {rules.area_min_m2}",
                    )
                )

            if rules.require_non_self_intersection and len(points) >= 4:
                segs = [(points[i], points[i + 1]) for i in range(len(points) - 1)]
                for i, (a1, a2) in enumerate(segs):
                    for j, (b1, b2) in enumerate(segs):
                        if j <= i:
                            continue
                        if abs(i - j) <= 1:
                            continue
                        if i == 0 and j == len(segs) - 1:
                            continue
                        if _segments_intersect(a1, a2, b1, b2, eps):
                            errors.append(
                                ValidationErrorItem(
                                    "self_intersection",
                                    f"{ppath}.segments[{i},{j}]",
                                    "non-adjacent segments intersect",
                                )
                            )

    try:
        canonical_obj, _ = canonicalize_geometry(data, contract_path=contract_path)
    except Exception as exc:
        errors.append(ValidationErrorItem("canonicalize", "root", f"canonicalization failed: {exc}"))
    else:
        if canonical_obj != data:
            errors.append(
                ValidationErrorItem(
                    "canonical_form",
                    "root",
                    "payload is not canonical (ordering/rounding/unit/closure mismatch)",
                )
            )

    if errors:
        raise GeometryValidationError(errors)
