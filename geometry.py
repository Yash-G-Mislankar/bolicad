"""Deterministic solids. Only validated parameters enter these constructors."""
import io

import numpy as np
import trimesh

from cad_schema import ShapeSpec


def connected_bodies(mesh: trimesh.Trimesh) -> int:
    """Union-find avoids pulling SciPy into this lightweight deployment."""
    parents = list(range(len(mesh.vertices)))

    def root(index):
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    for a, b in mesh.edges_unique:
        a, b = root(int(a)), root(int(b))
        if a != b:
            parents[b] = a
    return len({root(i) for i in range(len(parents))})


def _block(extents, origin=(0, 0, 0)):
    mesh = trimesh.creation.box(extents=extents)
    mesh.apply_translation(np.asarray(origin) + np.asarray(extents)/2)
    return mesh


def build_mesh(spec: ShapeSpec) -> trimesh.Trimesh:
    # Revalidate even when called by scripts rather than the UI.
    spec = ShapeSpec.model_validate(spec.model_dump())
    d = spec.dimensions
    if spec.shape_type == "box":
        length, width, height, t = (d[k] for k in ("length", "width", "height", "wall_thickness"))
        outside = _block((length, width, height))
        inside = _block((length-2*t, width-2*t, height), (t, t, t))
        mesh = trimesh.boolean.difference([outside, inside], engine="manifold")
    elif spec.shape_type == "plate":
        mesh = _block((d["length"], d["width"], d["thickness"]))
    else:
        t = d["thickness"]
        base = _block((d["width"], d["depth"], t))
        upright = _block((d["width"], t, d["height"]))
        mesh = trimesh.boolean.union([base, upright], engine="manifold")
    if spec.holes:
        cutters = []
        for hole in spec.holes:
            # Extend cylinders through both surfaces, avoiding coplanar caps.
            cylinder = trimesh.creation.cylinder(radius=hole.diameter/2, height=d["thickness"]+2, sections=96)
            if hole.face == "upright":
                cylinder.apply_transform(trimesh.transformations.rotation_matrix(np.pi/2, (1, 0, 0)))
                cylinder.apply_translation((hole.x, d["thickness"]/2, hole.y))
            else:
                cylinder.apply_translation((hole.x, hole.y, d["thickness"]/2))
            cutters.append(cylinder)
        mesh = trimesh.boolean.difference([mesh, *cutters], engine="manifold")
    if not isinstance(mesh, trimesh.Trimesh) or mesh.is_empty or not mesh.is_watertight or not mesh.is_volume:
        raise ValueError("Geometry did not produce a closed solid. Please adjust the dimensions.")
    expected = {
        "bracket": [d.get("width"), d.get("depth"), d.get("height")],
        "plate": [d.get("length"), d.get("width"), d.get("thickness")],
        "box": [d.get("length"), d.get("width"), d.get("height")],
    }[spec.shape_type]
    if not np.allclose(mesh.extents, expected, atol=1e-3, rtol=1e-5):
        raise ValueError("The generated bounds do not match the requested dimensions.")
    if connected_bodies(mesh) != 1:
        raise ValueError("The dimensions split this part into disconnected solids. Adjust the holes.")
    return mesh


def export_stl(mesh: trimesh.Trimesh) -> bytes:
    """Export the same mesh the viewer uses and verify the actual STL round trip."""
    data = mesh.export(file_type="stl")
    check = trimesh.load(io.BytesIO(data), file_type="stl", force="mesh")
    if not check.is_watertight or not check.is_volume or connected_bodies(check) != 1:
        raise ValueError("STL verification failed. Adjust dimensions and regenerate.")
    if not np.allclose(check.extents, mesh.extents, atol=1e-3, rtol=1e-5):
        raise ValueError("STL dimensions differ from the preview.")
    return data
