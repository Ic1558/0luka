"""Geometry canonicalization for deterministic hashing.

PR-A scope only: contract loading + canonicalization + stable hashing.
Validation and broader policy enforcement are intentionally deferred.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_EVEN, ROUND_HALF_UP
from pathlib import Path
from typing import Any

import yaml


DEFAULT_CONTRACT_PATH = Path(__file__).with_name("geometry_contract.yaml")


@dataclass(frozen=True)
class GeometryContract:
    schema_version: str
    frozen: bool
    decimals: int
    rounding_mode: str
    canonical_unit: str
    conversion_to_m: dict[str, float]
    min_vertices: int
    require_closed_ring: bool


def load_contract(contract_path: str | Path | None = None) -> GeometryContract:
    path = Path(contract_path) if contract_path else DEFAULT_CONTRACT_PATH
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("geometry contract must be a mapping")

    if raw.get("frozen") is not True:
        raise ValueError("geometry contract must be frozen=true")

    np = raw.get("numeric_precision") or {}
    un = raw.get("unit_normalization") or {}
    pv = raw.get("polygon_validity") or {}

    return GeometryContract(
        schema_version=str(raw.get("schema_version", "")),
        frozen=True,
        decimals=int(np.get("decimals", 6)),
        rounding_mode=str(np.get("rounding_mode", "half_even")),
        canonical_unit=str(un.get("canonical_unit", "m")),
        conversion_to_m={k: float(v) for k, v in (un.get("conversion_to_m") or {}).items()},
        min_vertices=int(pv.get("min_vertices", 3)),
        require_closed_ring=bool(pv.get("require_closed_ring", True)),
    )


def _round_float(value: float, decimals: int, rounding_mode: str) -> float:
    quant = Decimal("1").scaleb(-decimals)
    dec = Decimal(str(value))
    mode = ROUND_HALF_EVEN if rounding_mode == "half_even" else ROUND_HALF_UP
    return float(dec.quantize(quant, rounding=mode))


def _point_to_xy(point: Any) -> tuple[float, float]:
    if isinstance(point, (list, tuple)) and len(point) == 2:
        return float(point[0]), float(point[1])
    if isinstance(point, dict) and "x" in point and "y" in point:
        return float(point["x"]), float(point["y"])
    raise ValueError("point must be [x, y] or {x, y}")


def _canonicalize_ring(points: list[tuple[float, float]], min_vertices: int, require_closed_ring: bool) -> list[list[float]]:
    if len(points) < min_vertices:
        raise ValueError("ring has fewer than minimum vertices")

    base = points[:]
    if len(base) >= 2 and base[0] == base[-1]:
        base = base[:-1]

    if len(base) < min_vertices:
        raise ValueError("ring has fewer than minimum vertices after closure normalization")

    def rotations(seq: list[tuple[float, float]]) -> list[list[tuple[float, float]]]:
        min_pt = min(seq)
        idxs = [i for i, p in enumerate(seq) if p == min_pt]
        out = []
        for i in idxs:
            out.append(seq[i:] + seq[:i])
        return out

    candidates = rotations(base) + rotations(list(reversed(base)))
    chosen = min(candidates)

    if require_closed_ring:
        chosen = chosen + [chosen[0]]

    return [[x, y] for x, y in chosen]


def _stable_json_dump(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def canonicalize_geometry(data: dict[str, Any], contract_path: str | Path | None = None) -> tuple[dict[str, Any], str]:
    if not isinstance(data, dict):
        raise ValueError("geometry payload must be a mapping")

    contract = load_contract(contract_path)

    unit = str(data.get("unit", contract.canonical_unit))
    factor = contract.conversion_to_m.get(unit)
    if factor is None:
        raise ValueError(f"unsupported unit: {unit}")

    polygons = data.get("polygons")
    if not isinstance(polygons, list) or len(polygons) == 0:
        raise ValueError("payload must include non-empty polygons list")

    canonical_polygons: list[dict[str, Any]] = []
    for idx, poly in enumerate(polygons):
        if not isinstance(poly, dict):
            raise ValueError("polygon must be a mapping")

        raw_vertices = poly.get("vertices")
        if not isinstance(raw_vertices, list):
            raise ValueError("polygon.vertices must be a list")

        norm_points: list[tuple[float, float]] = []
        for raw_point in raw_vertices:
            x, y = _point_to_xy(raw_point)
            x = _round_float(x * factor, contract.decimals, contract.rounding_mode)
            y = _round_float(y * factor, contract.decimals, contract.rounding_mode)
            norm_points.append((x, y))

        canonical_vertices = _canonicalize_ring(
            points=norm_points,
            min_vertices=contract.min_vertices,
            require_closed_ring=contract.require_closed_ring,
        )

        canonical_polygon: dict[str, Any] = {"vertices": canonical_vertices}
        if "id" in poly:
            canonical_polygon["id"] = str(poly["id"])
        else:
            canonical_polygon["id"] = str(idx)

        canonical_polygons.append(canonical_polygon)

    canonical_polygons.sort(key=lambda p: (_stable_json_dump(p["vertices"]), p["id"]))

    canonical_obj: dict[str, Any] = {
        "schema_version": contract.schema_version,
        "unit": contract.canonical_unit,
        "polygons": canonical_polygons,
    }

    stable = _stable_json_dump(canonical_obj)
    digest = hashlib.sha256(stable.encode("utf-8")).hexdigest()
    return canonical_obj, digest
