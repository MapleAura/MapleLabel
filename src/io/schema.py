from __future__ import annotations

from typing import Any, Dict, List, Optional

ANNOTATION_VERSION = "maplelabel-1.0"
ALLOWED_SHAPES = {"rectangle", "point", "polygon"}


def _coerce_rectangle_points(points: List[List[float]]) -> List[List[float]]:
    """Ensure rectangles are stored as two points [min,max]."""
    if not points:
        return []
    xs = [p[0] for p in points if isinstance(p, (list, tuple)) and len(p) >= 2]
    ys = [p[1] for p in points if isinstance(p, (list, tuple)) and len(p) >= 2]
    if not xs or not ys:
        return []
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    return [[min_x, min_y], [max_x, max_y]]


def normalize_shape(shape: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a single shape dict to a consistent schema."""
    shape = dict(shape)  # shallow copy to avoid mutating callers
    shape_type = shape.get("shape_type") or shape.get("type")
    if shape_type not in ALLOWED_SHAPES:
        return {}

    attrs = shape.get("attributes")
    if attrs is None:
        attrs = shape.get("flags") or {}
    shape["attributes"] = attrs or {}
    shape.setdefault("flags", {})
    shape.setdefault("description", "")
    shape.setdefault("mask", None)

    pts = shape.get("points", [])
    if shape_type == "rectangle":
        shape["points"] = _coerce_rectangle_points(pts)
        # 保留 angle 字段如果存在
        if "angle" not in shape and "angle" in shape:
            try:
                shape["angle"] = float(shape.get("angle", 0)) % 360.0
            except Exception:
                pass
    else:
        # leave other shapes as-is but coerce to float pairs when possible
        new_pts: List[List[float]] = []
        for p in pts:
            if isinstance(p, (list, tuple)) and len(p) >= 2:
                try:
                    new_pts.append([float(p[0]), float(p[1])])
                except Exception:
                    continue
        shape["points"] = new_pts

    return shape


def build_annotation(
    shapes: List[Dict[str, Any]],
    image_path: str,
    image_height: int,
    image_width: int,
    include_image_data: bool = False,
) -> Dict[str, Any]:
    """Construct a normalized annotation payload."""
    normalized = [s for s in (normalize_shape(s) for s in shapes) if s]
    return {
        "version": ANNOTATION_VERSION,
        "flags": {},
        "shapes": normalized,
        "imagePath": image_path,
        "imageData": None if not include_image_data else None,
        "imageHeight": int(image_height),
        "imageWidth": int(image_width),
    }
