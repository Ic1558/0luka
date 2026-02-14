from core.geometry.canonicalize import canonicalize_geometry


def test_canonicalize_deterministic_hash_same_input() -> None:
    payload = {
        "unit": "mm",
        "polygons": [
            {
                "id": "poly-a",
                "vertices": [
                    [0, 0],
                    [2000, 0],
                    [2000, 1000],
                    [0, 1000],
                    [0, 0],
                ],
            }
        ],
    }

    c1, h1 = canonicalize_geometry(payload)
    c2, h2 = canonicalize_geometry(payload)

    assert c1 == c2
    assert h1 == h2


def test_canonicalize_hash_stable_under_vertex_rotation_and_polygon_order() -> None:
    payload_a = {
        "unit": "m",
        "polygons": [
            {
                "id": "b",
                "vertices": [[0, 0], [0, 2], [2, 2], [2, 0], [0, 0]],
            },
            {
                "id": "a",
                "vertices": [[10, 10], [12, 10], [12, 12], [10, 12], [10, 10]],
            },
        ],
    }
    payload_b = {
        "unit": "m",
        "polygons": [
            {
                "id": "a",
                "vertices": [[12, 10], [12, 12], [10, 12], [10, 10], [12, 10]],
            },
            {
                "id": "b",
                "vertices": [[2, 0], [0, 0], [0, 2], [2, 2], [2, 0]],
            },
        ],
    }

    c_a, h_a = canonicalize_geometry(payload_a)
    c_b, h_b = canonicalize_geometry(payload_b)

    assert c_a == c_b
    assert h_a == h_b
