import json
import os
from typing import Optional

from .schema import build_annotation, normalize_shape



def save_annotations_to_json(
    view, json_path: str, include_image_data: bool = False
) -> bool:
    """Save annotations from a view to a normalized LabelMe-format JSON file."""
    if not getattr(view, "current_image_path", None):
        return False

    image_width = getattr(view, "image_width", 0)
    image_height = getattr(view, "image_height", 0)
    image_name = os.path.basename(view.current_image_path)

    shapes = []

    for rect in getattr(view, "rect_items", []):
        data = normalize_shape(rect.to_dict())
        if data:
            shapes.append(data)

    for point in getattr(view, "point_items", []):
        data = normalize_shape(point.to_dict())
        if data:
            shapes.append(data)

    for polygon in getattr(view, "polygon_items", []):
        data = normalize_shape(polygon.to_dict())
        if data:
            shapes.append(data)

    labelme_data = build_annotation(
        shapes,
        image_name,
        image_height,
        image_width,
        include_image_data=include_image_data,
    )

    try:
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(labelme_data, f, indent=2, ensure_ascii=False)
        if hasattr(view, "modified"):
            view.modified = False
        return True
    except Exception:
        return False


def save_annotations_to_temp(view, temp_dir: Optional[str] = None) -> bool:
    """Save annotations to a temp file next to the user's home temp folder."""
    if not getattr(view, "current_image_path", None):
        return False

    if not temp_dir:
        temp_dir = os.path.join(os.path.expanduser("~"), ".maplabel_temp")

    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir, exist_ok=True)

    image_name = os.path.basename(view.current_image_path)
    temp_name = f"temp_{image_name}.json"
    temp_path = os.path.join(temp_dir, temp_name)

    return save_annotations_to_json(view, temp_path, include_image_data=False)


def load_annotations_from_json(view, json_path: str) -> bool:
    """Load annotations from a LabelMe-format JSON file into the provided view.

    Note: this will clear existing annotations on the view.
    """
    if not os.path.exists(json_path):
        return False

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # clear existing
        if hasattr(view, "clear_annotations"):
            view.clear_annotations()

        group_items_map = {}

        for shape_data in data.get("shapes", []):
            normalized = normalize_shape(shape_data)
            if not normalized:
                continue

            shape_type = normalized.get("shape_type", "")
            group_id = normalized.get("group_id")
            item = None
            if shape_type == "rectangle":
                from ..items import PointItem, PolygonItem, ResizableRectItem

                item = ResizableRectItem.from_dict(normalized, None)
            elif shape_type == "point":
                from ..items import PointItem, PolygonItem, ResizableRectItem

                item = PointItem.from_dict(normalized, None)
            elif shape_type == "polygon":
                from ..items import PointItem, PolygonItem, ResizableRectItem

                item = PolygonItem.from_dict(normalized, None)

            if item:
                view.scene.addItem(item)
                if shape_type == "rectangle":
                    view.rect_items.append(item)
                elif shape_type == "point":
                    view.point_items.append(item)
                elif shape_type == "polygon":
                    view.polygon_items.append(item)

                if group_id is not None:
                    if group_id not in group_items_map:
                        group_items_map[group_id] = []
                    group_items_map[group_id].append(item)
                    item.group_id = group_id

        # recreate groups
        for group_id, items in group_items_map.items():
            if len(items) >= 2 and hasattr(view, "_create_group_from_items"):
                view._create_group_from_items(group_id, items)

        groups_in_data = [
            s.get("group_id", 0) for s in data.get("shapes", []) if s.get("group_id")
        ]
        if groups_in_data:
            max_id = max(groups_in_data)
            view.next_group_id = max_id + 1

        return True
    except Exception:
        return False


def load_annotations_from_temp(view, temp_dir: Optional[str] = None) -> bool:
    if not getattr(view, "current_image_path", None):
        return False

    if not temp_dir:
        temp_dir = os.path.join(os.path.expanduser("~"), ".maplabel_temp")

    image_name = os.path.basename(view.current_image_path)
    temp_name = f"temp_{image_name}.json"
    temp_path = os.path.join(temp_dir, temp_name)

    if not os.path.exists(temp_path):
        return False

    return load_annotations_from_json(view, temp_path)
