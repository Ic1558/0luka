import pytest

from core.geometry.canonicalize import canonicalize_geometry
from core.geometry.validate import GeometryValidationError, validate_canonical_geometry


def _canonical_payload() -> dict:
    raw = {
        "unit": "mm",
        "polygons": [
            {
                "id": "p0",
                "vertices": [[0, 0], [2000, 0], [2000, 1000], [0, 1000], [0, 0]],
            }
        ],
    }
    canonical, _ = canonicalize_geometry(raw)
    return canonical


def test_validate_accepts_canonical_payload() -> None:
    payload = _canonical_payload()
    validate_canonical_geometry(payload)


def test_validate_rejects_schema_version_mismatch() -> None:
    payload = _canonical_payload()
    payload["schema_version"] = "9.9.9"
    with pytest.raises(GeometryValidationError, match=r"schema_version"):
        validate_canonical_geometry(payload)


def test_validate_rejects_non_canonical_unit() -> None:
    payload = _canonical_payload()
    payload["unit"] = "mm"
    with pytest.raises(GeometryValidationError, match=r"unit"):
        validate_canonical_geometry(payload)


def test_validate_rejects_non_numeric_vertex() -> None:
    payload = _canonical_payload()
    payload["polygons"][0]["vertices"][1] = ["x", 1.0]
    with pytest.raises(GeometryValidationError, match=r"vertex_numeric"):
        validate_canonical_geometry(payload)


def test_validate_rejects_open_ring_when_closure_required() -> None:
    payload = _canonical_payload()
    payload["polygons"][0]["vertices"] = payload["polygons"][0]["vertices"][:-1]
    with pytest.raises(GeometryValidationError, match=r"closure"):
        validate_canonical_geometry(payload)


def test_validate_rejects_area_below_minimum() -> None:
    payload = _canonical_payload()
    payload["polygons"][0]["vertices"] = [
        [0.0, 0.0],
        [0.0001, 0.0],
        [0.0001, 0.0001],
        [0.0, 0.0001],
        [0.0, 0.0],
    ]
    with pytest.raises(GeometryValidationError, match=r"area"):
        validate_canonical_geometry(payload)


def test_validate_rejects_self_intersection() -> None:
    payload = _canonical_payload()
    payload["polygons"][0]["vertices"] = [
        [0.0, 0.0],
        [2.0, 2.0],
        [0.0, 2.0],
        [2.0, 0.0],
        [0.0, 0.0],
    ]
    with pytest.raises(GeometryValidationError, match=r"self_intersection"):
        validate_canonical_geometry(payload)


def test_validate_rejects_adjacency_below_tolerance() -> None:
    payload = _canonical_payload()
    payload["polygons"][0]["vertices"] = [
        [0.0, 0.0],
        [0.00001, 0.0],
        [1.0, 0.0],
        [1.0, 1.0],
        [0.0, 0.0],
    ]
    with pytest.raises(GeometryValidationError, match=r"adjacency"):
        validate_canonical_geometry(payload)


def test_validate_rejects_non_canonical_ordering_and_rounding() -> None:
    payload = {
        "schema_version": "1.0.0",
        "unit": "m",
        "polygons": [
            {
                "id": "p0",
                "vertices": [
                    [2.0, 0.0],
                    [0.0, 0.0],
                    [0.0, 1.0000004],
                    [2.0, 1.0],
                    [2.0, 0.0],
                ],
            }
        ],
    }
    with pytest.raises(GeometryValidationError, match=r"canonical_form"):
        validate_canonical_geometry(payload)


def test_validate_errors_are_deterministically_ordered() -> None:
    payload = {
        "schema_version": "wrong",
        "unit": "mm",
        "polygons": [{"id": "p0", "vertices": [[0.0, 0.0], [0.0, 0.0], [0.0, 0.0]]}],
    }
    with pytest.raises(GeometryValidationError) as exc:
        validate_canonical_geometry(payload)

    lines = str(exc.value).splitlines()
    assert lines == sorted(lines)
