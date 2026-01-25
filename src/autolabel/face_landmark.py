import base64
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
import onnxruntime as ort

from src.utils.registry import register_module


def distance2bbox(points: np.ndarray, distance: np.ndarray, max_shape: Optional[Tuple[int, int]] = None) -> np.ndarray:
    x1 = points[:, 0] - distance[:, 0]
    y1 = points[:, 1] - distance[:, 1]
    x2 = points[:, 0] + distance[:, 2]
    y2 = points[:, 1] + distance[:, 3]
    if max_shape is not None:
        x1 = np.clip(x1, 0, max_shape[1])
        y1 = np.clip(y1, 0, max_shape[0])
        x2 = np.clip(x2, 0, max_shape[1])
        y2 = np.clip(y2, 0, max_shape[0])
    return np.stack([x1, y1, x2, y2], axis=-1)


def distance2kps(points: np.ndarray, distance: np.ndarray, max_shape: Optional[Tuple[int, int]] = None) -> np.ndarray:
    preds = []
    for i in range(0, distance.shape[1], 2):
        px = points[:, i % 2] + distance[:, i]
        py = points[:, i % 2 + 1] + distance[:, i + 1]
        if max_shape is not None:
            px = np.clip(px, 0, max_shape[1])
            py = np.clip(py, 0, max_shape[0])
        preds.append(px)
        preds.append(py)
    return np.stack(preds, axis=-1)


def _nms(boxes: np.ndarray, scores: np.ndarray, iou_thresh: float = 0.45) -> List[int]:
    if boxes.size == 0:
        return []
    x1, y1, x2, y2 = boxes.T
    areas = (x2 - x1 + 1) * (y2 - y1 + 1)
    order = scores.argsort()[::-1]
    keep: List[int] = []
    while order.size > 0:
        i = order[0]
        keep.append(i)
        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])
        w = np.maximum(0.0, xx2 - xx1 + 1)
        h = np.maximum(0.0, yy2 - yy1 + 1)
        inter = w * h
        ovr = inter / (areas[i] + areas[order[1:]] - inter + 1e-6)
        inds = np.where(ovr <= iou_thresh)[0]
        order = order[inds + 1]
    return keep


def _make_labelme(
    image_path: str,
    img_h: int,
    img_w: int,
    dets: List[Tuple[np.ndarray, Optional[np.ndarray]]],
    image_data: Optional[str] = None,
) -> Dict[str, Any]:
    shapes = []
    group_id = 1
    for bbox, kps in dets:
        x1, y1, x2, y2, score = bbox.tolist()
        shapes.append(
            {
                "label": "face",
                "points": [[float(x1), float(y1)], [float(x2), float(y2)]],
                "group_id": group_id,
                "description": "",
                "shape_type": "rectangle",
                "flags": {},
                "mask": None,
                "score": float(score),
            }
        )
        if kps is not None and len(kps) >= 5:
            labels = ["left_eye", "right_eye", "nose", "left_mouth", "right_mouth"]
            for (x, y), lbl in zip(kps[:5], labels):
                shapes.append(
                    {
                        "label": lbl,
                        "points": [[float(x), float(y)]],
                        "group_id": group_id,
                        "description": "",
                        "shape_type": "point",
                        "flags": {},
                        "mask": None,
                    }
                )
        group_id += 1

    return {
        "version": "5.10.1",
        "flags": {},
        "shapes": shapes,
        "imagePath": os.path.basename(image_path),
        "imageData": None,
        "imageHeight": int(img_h),
        "imageWidth": int(img_w),
    }


class SCRFD:
    def __init__(self, model_file: str, providers: List[str]):
        if not os.path.exists(model_file):
            raise FileNotFoundError(model_file)
        self.model_file = model_file
        self.session = ort.InferenceSession(model_file, providers=providers)
        self.center_cache: Dict[Tuple[int, int, int], np.ndarray] = {}
        self.nms_thresh = 0.4
        self.batched = False
        self.use_kps = False
        self._num_anchors = 1
        self.input_size: Optional[Tuple[int, int]] = None
        self.input_name = ""
        self.output_names: List[str] = []
        self._feat_stride_fpn: List[int] = []
        self.fmc = 0
        self._init_vars()

    def _init_vars(self):
        input_cfg = self.session.get_inputs()[0]
        input_shape = input_cfg.shape
        if isinstance(input_shape[2], str):
            self.input_size = None
        else:
            self.input_size = tuple(input_shape[2:4][::-1])
        self.input_name = input_cfg.name
        outputs = self.session.get_outputs()
        self.batched = len(outputs[0].shape) == 3
        self.output_names = [o.name for o in outputs]
        if len(outputs) == 6:
            self.fmc = 3
            self._feat_stride_fpn = [8, 16, 32]
            self._num_anchors = 2
        elif len(outputs) == 9:
            self.fmc = 3
            self._feat_stride_fpn = [8, 16, 32]
            self._num_anchors = 2
            self.use_kps = True
        elif len(outputs) == 10:
            self.fmc = 5
            self._feat_stride_fpn = [8, 16, 32, 64, 128]
            self._num_anchors = 1
        elif len(outputs) == 15:
            self.fmc = 5
            self._feat_stride_fpn = [8, 16, 32, 64, 128]
            self._num_anchors = 1
            self.use_kps = True

    def prepare(self, ctx_id: int, **kwargs):
        if ctx_id < 0:
            self.session.set_providers(["CPUExecutionProvider"])
        nms_thresh = kwargs.get("nms_thresh")
        if nms_thresh is not None:
            self.nms_thresh = float(nms_thresh)
        input_size = kwargs.get("input_size")
        if input_size is not None:
            if self.input_size is None:
                self.input_size = tuple(input_size)
            else:
                self.input_size = tuple(input_size)

    def forward(self, img: np.ndarray, thresh: float) -> Tuple[List[np.ndarray], List[np.ndarray], List[np.ndarray]]:
        scores_list: List[np.ndarray] = []
        bboxes_list: List[np.ndarray] = []
        kpss_list: List[np.ndarray] = []
        input_size = tuple(img.shape[0:2][::-1])
        blob = cv2.dnn.blobFromImage(img, 1.0 / 128, input_size, (127.5, 127.5, 127.5), swapRB=True)
        net_outs = self.session.run(self.output_names, {self.input_name: blob})

        input_height = blob.shape[2]
        input_width = blob.shape[3]
        for idx, stride in enumerate(self._feat_stride_fpn):
            if self.batched:
                scores = net_outs[idx][0]
                bbox_preds = net_outs[idx + self.fmc][0] * stride
                if self.use_kps:
                    kps_preds = net_outs[idx + self.fmc * 2][0] * stride
            else:
                scores = net_outs[idx]
                bbox_preds = net_outs[idx + self.fmc] * stride
                if self.use_kps:
                    kps_preds = net_outs[idx + self.fmc * 2] * stride

            height = input_height // stride
            width = input_width // stride
            key = (height, width, stride)
            if key in self.center_cache:
                anchor_centers = self.center_cache[key]
            else:
                anchor_centers = np.stack(np.mgrid[:height, :width][::-1], axis=-1).astype(np.float32)
                anchor_centers = (anchor_centers * stride).reshape((-1, 2))
                if self._num_anchors > 1:
                    anchor_centers = np.stack([anchor_centers] * self._num_anchors, axis=1).reshape((-1, 2))
                if len(self.center_cache) < 100:
                    self.center_cache[key] = anchor_centers

            pos_inds = np.where(scores >= thresh)[0]
            bboxes = distance2bbox(anchor_centers, bbox_preds)
            pos_scores = scores[pos_inds]
            pos_bboxes = bboxes[pos_inds]
            scores_list.append(pos_scores)
            bboxes_list.append(pos_bboxes)
            if self.use_kps:
                kpss = distance2kps(anchor_centers, kps_preds)
                kpss = kpss.reshape((kpss.shape[0], -1, 2))
                pos_kpss = kpss[pos_inds]
                kpss_list.append(pos_kpss)
        return scores_list, bboxes_list, kpss_list

    def detect(self, img: np.ndarray, thresh: float = 0.5, input_size: Optional[Tuple[int, int]] = None, max_num: int = 0) -> Tuple[np.ndarray, Optional[np.ndarray]]:
        assert input_size is not None or self.input_size is not None
        input_size = self.input_size if input_size is None else input_size
     
        im_ratio = float(img.shape[0]) / img.shape[1]
        model_ratio = float(input_size[1]) / input_size[0]
        if im_ratio > model_ratio:
            new_height = input_size[1]
            new_width = int(new_height / im_ratio)
        else:
            new_width = input_size[0]
            new_height = int(new_width * im_ratio)
    
        det_scale = float(new_height) / img.shape[0]
        resized_img = cv2.resize(img, (new_width, new_height))
        det_img = np.zeros((input_size[1], input_size[0], 3), dtype=np.uint8)
        det_img[:new_height, :new_width, :] = resized_img
    
        scores_list, bboxes_list, kpss_list = self.forward(det_img, thresh)
    
        scores = np.vstack(scores_list) if scores_list else np.zeros((0,))
        scores_ravel = scores.ravel()
        order = scores_ravel.argsort()[::-1]
        bboxes = np.vstack(bboxes_list) / det_scale if bboxes_list else np.zeros((0, 4))
        if self.use_kps and kpss_list:
            kpss = np.vstack(kpss_list) / det_scale
        else:
            kpss = None
        pre_det = np.hstack((bboxes, scores.reshape(-1, 1))).astype(np.float32, copy=False) if bboxes.size else np.zeros((0, 5), dtype=np.float32)
        pre_det = pre_det[order, :]
        keep = self.nms(pre_det)
        det = pre_det[keep, :]
        if self.use_kps and kpss is not None:
            kpss = kpss[order, :, :]
            kpss = kpss[keep, :, :]
        else:
            kpss = None
        if max_num > 0 and det.shape[0] > max_num:
            area = (det[:, 2] - det[:, 0]) * (det[:, 3] - det[:, 1])
            img_center = img.shape[0] // 2, img.shape[1] // 2
            offsets = np.vstack(
                [
                    (det[:, 0] + det[:, 2]) / 2 - img_center[1],
                    (det[:, 1] + det[:, 3]) / 2 - img_center[0],
                ]
            )
            offset_dist_squared = np.sum(np.power(offsets, 2.0), 0)
            values = area - offset_dist_squared * 2.0
            bindex = np.argsort(values)[::-1]
            bindex = bindex[0:max_num]
            det = det[bindex, :]
            if kpss is not None:
                kpss = kpss[bindex, :]
        return det, kpss

    def nms(self, dets: np.ndarray) -> List[int]:
        if dets.size == 0:
            return []
        thresh = self.nms_thresh
        x1 = dets[:, 0]
        y1 = dets[:, 1]
        x2 = dets[:, 2]
        y2 = dets[:, 3]
        scores = dets[:, 4]
        areas = (x2 - x1 + 1) * (y2 - y1 + 1)
        order = scores.argsort()[::-1]
        keep: List[int] = []
        while order.size > 0:
            i = order[0]
            keep.append(i)
            xx1 = np.maximum(x1[i], x1[order[1:]])
            yy1 = np.maximum(y1[i], y1[order[1:]])
            xx2 = np.minimum(x2[i], x2[order[1:]])
            yy2 = np.minimum(y2[i], y2[order[1:]])
            w = np.maximum(0.0, xx2 - xx1 + 1)
            h = np.maximum(0.0, yy2 - yy1 + 1)
            inter = w * h
            ovr = inter / (areas[i] + areas[order[1:]] - inter)
            inds = np.where(ovr <= thresh)[0]
            order = order[inds + 1]
        return keep


@register_module("FaceLandmark")
class FaceLandmark:
    detector: Optional[SCRFD] = None
    conf_thresh: float = 0.1
    iou_thresh: float = 0.4
    min_face_size: int = 12
    include_image_data: bool = False
    input_size: Optional[Tuple[int, int]] = None

    @staticmethod
    def Init(cfg: Dict[str, Any]):
        if FaceLandmark.detector is not None:
            return True

        root = Path(__file__).resolve().parents[2]
        model_path = Path(cfg.get("model_path", root / "models" / "face_landmark.onnx"))
        if not model_path.exists():
            raise FileNotFoundError(f"model not found: {model_path}")

        FaceLandmark.conf_thresh = float(cfg.get("conf_thresh", FaceLandmark.conf_thresh))
        FaceLandmark.iou_thresh = float(cfg.get("iou_thresh", FaceLandmark.iou_thresh))
        FaceLandmark.min_face_size = int(cfg.get("min_face_size", FaceLandmark.min_face_size))
        FaceLandmark.include_image_data = bool(cfg.get("include_image_data", False))
        if "input_size" in cfg:
            size = cfg.get("input_size")
            if isinstance(size, (list, tuple)) and len(size) == 2:
                FaceLandmark.input_size = (int(size[0]), int(size[1]))

        providers = ort.get_available_providers()
        preferred = ["CUDAExecutionProvider"] if "CUDAExecutionProvider" in providers else ["CPUExecutionProvider"]
        detector = SCRFD(str(model_path), preferred)
        detector.prepare(ctx_id=0 if "CUDAExecutionProvider" in preferred else -1, input_size=FaceLandmark.input_size, nms_thresh=FaceLandmark.iou_thresh)
        FaceLandmark.detector = detector
        return True

    @staticmethod
    def Infer(path: str):
        if FaceLandmark.detector is None:
            return {}

        img = cv2.imread(path)
        if img is None:
            return {}
        
        det, kpss = FaceLandmark.detector.detect(img, thresh=FaceLandmark.conf_thresh, input_size=img.shape)
        if det is None or det.size == 0:
            return {}
        
        kps_list: List[Optional[np.ndarray]] = []
        if kpss is None:
            kps_list = [None] * det.shape[0]
        else:
            kps_list = list(kpss)

        results: List[Tuple[np.ndarray, Optional[np.ndarray]]] = []
        for bbox, kps in zip(det, kps_list):
            w = bbox[2] - bbox[0]
            h = bbox[3] - bbox[1]
            if w < FaceLandmark.min_face_size or h < FaceLandmark.min_face_size:
                continue
            results.append((bbox, kps))

        if not results:
            return {}

        image_data = None
        if FaceLandmark.include_image_data:
            ok, buf = cv2.imencode(".jpg", img)
            if ok:
                image_data = base64.b64encode(buf).decode("utf-8")

        labelme = _make_labelme(path, img.shape[0], img.shape[1], results, image_data)
        return labelme

    @staticmethod
    def UnInit():
        FaceLandmark.detector = None
