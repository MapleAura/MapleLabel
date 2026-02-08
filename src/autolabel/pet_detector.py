from __future__ import annotations

import base64
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
from ultralytics import YOLO

from src.utils.registry import register_module


ANNOTATION_VERSION = "maplelabel-1.0"


def _make_labelme(
    image_path: str,
    img_h: int,
    img_w: int,
    dets: List[Tuple[str, np.ndarray]],
    image_data: Optional[str] = None,
) -> Dict[str, Any]:
    shapes = []
    group_id = 1
    for label, bbox in dets:
        x1, y1, x2, y2, score = bbox.tolist()
        shapes.append(
            {
                "label": label,
                "points": [[float(x1), float(y1)], [float(x2), float(y2)]],
                "group_id": group_id,
                "description": "",
                "shape_type": "rectangle",
                "flags": {},
                "attributes": {"cls": label},
                "mask": None,
                "score": float(score),
            }
        )
        group_id += 1

    return {
        "version": ANNOTATION_VERSION,
        "flags": {},
        "shapes": shapes,
        "imagePath": os.path.basename(image_path),
        "imageData": image_data,
        "imageHeight": int(img_h),
        "imageWidth": int(img_w),
    }


@register_module("PetDetector")
class PetDetector:
    detector: Optional[YOLO] = None
    conf_thresh: float = 0.25
    iou_thresh: float = 0.45
    min_size: int = 8
    include_image_data: bool = False
    class_filter: Optional[List[int]] = None
    name_filter: Optional[List[str]] = None

    @staticmethod
    def init(cfg: Dict[str, Any]):
        """
        初始化宠物检测器（Ultralytics YOLO PT）
        """
        if PetDetector.detector is not None:
            return True

        root = Path(__file__).resolve().parents[2]
        model_path = Path(cfg.get("model_path", root / "models" / "pet.pt"))
        if not model_path.exists():
            raise FileNotFoundError(f"宠物检测模型未找到: {model_path}")

        PetDetector.conf_thresh = float(cfg.get("conf_thresh", PetDetector.conf_thresh))
        PetDetector.iou_thresh = float(cfg.get("iou_thresh", PetDetector.iou_thresh))
        PetDetector.min_size = int(cfg.get("min_size", PetDetector.min_size))
        PetDetector.include_image_data = bool(cfg.get("include_image_data", False))

        class_filter = cfg.get("class_filter")
        if isinstance(class_filter, (list, tuple)) and class_filter:
            PetDetector.class_filter = [int(x) for x in class_filter]
        else:
            PetDetector.class_filter = None

        name_filter = cfg.get("name_filter")
        if isinstance(name_filter, (list, tuple)) and name_filter:
            PetDetector.name_filter = [str(x) for x in name_filter]
        else:
            PetDetector.name_filter = None

        PetDetector.detector = YOLO(str(model_path))

        print("PetDetector 模块初始化完成:")
        print(f"- 模型: {model_path.name}")
        print(f"- 置信度阈值: {PetDetector.conf_thresh}")
        print(f"- IOU 阈值: {PetDetector.iou_thresh}")
        return True

    @staticmethod
    def infer(path: str, options: Dict[str, Any] | None = None):
        """
        对单张图片进行宠物检测，返回LabelMe格式的标注结果
        """
        if PetDetector.detector is None:
            return {}

        img = cv2.imread(path)
        if img is None:
            return {}

        img_height, img_width = img.shape[:2]

        results = PetDetector.detector(
            img,
            conf=PetDetector.conf_thresh,
            iou=PetDetector.iou_thresh,
            verbose=False,
        )

        dets: List[Tuple[str, np.ndarray]] = []
        for r in results:
            names = r.names or {}
            boxes = r.boxes
            for box in boxes:
                score = float(box.conf[0])
                cls_id = int(box.cls[0]) if box.cls is not None else -1
                label = names.get(cls_id, "pet")

                if PetDetector.class_filter is not None and cls_id not in PetDetector.class_filter:
                    continue
                if PetDetector.name_filter is not None and label not in PetDetector.name_filter:
                    continue

                x1, y1, x2, y2 = map(float, box.xyxy[0].tolist())
                w = x2 - x1
                h = y2 - y1
                if w < PetDetector.min_size or h < PetDetector.min_size:
                    continue

                dets.append((label, np.array([x1, y1, x2, y2, score], dtype=np.float32)))

        if not dets:
            return {}

        image_data = None
        if PetDetector.include_image_data:
            ok, buf = cv2.imencode(".jpg", img)
            if ok:
                image_data = base64.b64encode(buf).decode("utf-8")

        labelme = _make_labelme(path, img_height, img_width, dets, image_data)
        labelme["flags"]["pet_count"] = len(dets)
        return labelme

    @staticmethod
    def batch_infer(image_dir: str, output_dir: str, options: Dict[str, Any] | None = None):
        """
        批量处理目录中的所有图片
        """
        if PetDetector.detector is None:
            return {"success": False, "message": "检测器未初始化"}

        image_dir = Path(image_dir)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        supported_formats = {".jpg", ".jpeg", ".png", ".bmp", ".tiff"}
        image_files = [f for f in image_dir.iterdir() if f.suffix.lower() in supported_formats]

        if not image_files:
            return {"success": False, "message": "未找到支持的图片文件"}

        results = {
            "success": True,
            "processed": 0,
            "total": len(image_files),
            "pet_count": 0,
            "failed": [],
        }

        for image_file in image_files:
            try:
                labelme_data = PetDetector.infer(str(image_file), options)
                if labelme_data:
                    output_file = output_dir / f"{image_file.stem}.json"
                    with open(output_file, "w", encoding="utf-8") as f:
                        import json
                        json.dump(labelme_data, f, indent=2, ensure_ascii=False)

                    results["processed"] += 1
                    results["pet_count"] += labelme_data["flags"].get("pet_count", 0)
                    print(f"已处理: {image_file.name} -> 宠物: {labelme_data['flags'].get('pet_count', 0)}")
                else:
                    print(f"未检测到目标: {image_file.name}")
                    results["processed"] += 1
            except Exception as e:
                error_msg = f"处理 {image_file.name} 时出错: {str(e)}"
                print(error_msg)
                results["failed"].append({"file": image_file.name, "error": str(e)})

        print("\n批量处理完成:")
        print(f"- 总图片数: {results['total']}")
        print(f"- 成功处理: {results['processed']}")
        print(f"- 总宠物数: {results['pet_count']}")
        print(f"- 失败数: {len(results['failed'])}")

        return results

    @staticmethod
    def uninit():
        """
        清理资源
        """
        PetDetector.detector = None
        print("PetDetector 模块已卸载")
