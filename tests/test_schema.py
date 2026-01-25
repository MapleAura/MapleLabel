import os
import sys
import unittest

# Ensure project root on path for `src` imports when running directly
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.io.schema import ANNOTATION_VERSION, build_annotation, normalize_shape


class SchemaTests(unittest.TestCase):
    def test_rectangle_points_are_coerced_to_two(self):
        shape = {
            "shape_type": "rectangle",
            "points": [[0, 0], [10, 0], [10, 5], [0, 5]],
        }
        normalized = normalize_shape(shape)
        self.assertEqual(normalized.get("points"), [[0.0, 0.0], [10.0, 5.0]])

    def test_attributes_prefer_attributes_then_attrs_then_flags(self):
        shape = {
            "shape_type": "point",
            "points": [[1, 2]],
            "flags": {"a": 1},
            "attrs": {"b": 2},
            "attributes": {"c": 3},
        }
        normalized = normalize_shape(shape)
        self.assertEqual(normalized.get("attributes"), {"c": 3})
        self.assertEqual(normalized.get("attrs"), {"c": 3})

    def test_invalid_shape_type_returns_empty(self):
        self.assertEqual(normalize_shape({"shape_type": "line"}), {})

    def test_build_annotation_uses_version_and_names(self):
        shapes = [
            {"shape_type": "point", "points": [[1, 1]], "attributes": {}},
        ]
        ann = build_annotation(shapes, "img.png", 100, 200, include_image_data=False)
        self.assertEqual(ann["version"], ANNOTATION_VERSION)
        self.assertEqual(ann["imagePath"], "img.png")
        self.assertEqual(ann["imageHeight"], 100)
        self.assertEqual(ann["imageWidth"], 200)
        self.assertIsNone(ann["imageData"])
        self.assertEqual(len(ann["shapes"]), 1)


if __name__ == "__main__":
    unittest.main()
