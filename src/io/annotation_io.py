import json
import os
from typing import Optional



def save_annotations_to_json(
    view, json_path: str, include_image_data: bool = False
) -> bool:
    """Save annotations from a view to a LabelMe-format JSON file.

    This extracts shapes from the view (`rect_items`, `point_items`, `polygon_items`)
    and writes a LabelMe-style dict to `json_path`.
    """
    if not getattr(view, "current_image_path", None):
        return False

    image_width = getattr(view, "image_width", 0)
    image_height = getattr(view, "image_height", 0)

    labelme_data = {
        "version": "4.5.6",
        "flags": {},
        "shapes": [],
        "imagePath": os.path.basename(view.current_image_path),
        "imageData": None,
        "imageHeight": image_height,
        "imageWidth": image_width,
    }

    # rectangles
    for rect in getattr(view, "rect_items", []):
        shape_data = rect.to_dict()
        if shape_data:
            # ensure description field exists for LabelMe compatibility
            if "description" not in shape_data:
                shape_data["description"] = ""
            # ensure rectangle uses two points: left-top and right-bottom
            if shape_data.get("shape_type") == "rectangle":
                pts = shape_data.get("points", [])
                if isinstance(pts, list):
                    # if four points provided, reduce to two (min/max)
                    if len(pts) == 4:
                        xs = [p[0] for p in pts]
                        ys = [p[1] for p in pts]
                        min_x, max_x = min(xs), max(xs)
                        min_y, max_y = min(ys), max(ys)
                        shape_data["points"] = [[min_x, min_y], [max_x, max_y]]
                    elif len(pts) == 2:
                        x1, y1 = pts[0]
                        x2, y2 = pts[1]
                        min_x, max_x = min(x1, x2), max(x1, x2)
                        min_y, max_y = min(y1, y2), max(y1, y2)
                        shape_data["points"] = [[min_x, min_y], [max_x, max_y]]
                    else:
                        # unexpected format: try to coerce to bounding two points
                        try:
                            xs = [p[0] for p in pts]
                            ys = [p[1] for p in pts]
                            min_x, max_x = min(xs), max(xs)
                            min_y, max_y = min(ys), max(ys)
                            shape_data["points"] = [[min_x, min_y], [max_x, max_y]]
                        except Exception:
                            pass
            # ensure mask field exists per our protocol
            shape_data["mask"] = None
            labelme_data["shapes"].append(shape_data)

    # points
    for point in getattr(view, "point_items", []):
        shape_data = point.to_dict()
        if shape_data:
            if "description" not in shape_data:
                shape_data["description"] = ""
            shape_data["mask"] = None
            labelme_data["shapes"].append(shape_data)

    # polygons
    for polygon in getattr(view, "polygon_items", []):
        shape_data = polygon.to_dict()
        if shape_data:
            if "description" not in shape_data:
                shape_data["description"] = ""
            shape_data["mask"] = None
            labelme_data["shapes"].append(shape_data)

    # Do not embed image binary data; keep `imageData` as null per new requirement
    if include_image_data:
        labelme_data["imageData"] = None

    try:
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(labelme_data, f, indent=2, ensure_ascii=False)
        # reset modified flag on view if exists
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
            shape_type = shape_data.get("shape_type", "")
            group_id = shape_data.get("group_id")
            item = None
            if shape_type == "rectangle":
                item = (
                    view.__class__.__module__
                )  # placeholder; actual construction handled below
                # use the existing item constructors available in the view's module imports
                from ..items import PointItem, PolygonItem, ResizableRectItem

                item = ResizableRectItem.from_dict(shape_data, None)
            elif shape_type == "point":
                from ..items import PointItem, PolygonItem, ResizableRectItem

                item = PointItem.from_dict(shape_data, None)
            elif shape_type == "polygon":
                from ..items import PointItem, PolygonItem, ResizableRectItem

                item = PolygonItem.from_dict(shape_data, None)

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
