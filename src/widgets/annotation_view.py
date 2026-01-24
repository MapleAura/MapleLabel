"""标注视图模块。

此模块提供 `AnnotationView`，它是基于 `QGraphicsView` 的标注画布，
负责图像展示、标注项管理、绘制交互（矩形/点/多边形）以及与
IO 层的对接（读取/保存 LabelMe 格式）。
"""

import os
import shutil
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPixmap,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
)

from ..io.annotation_io import (
    load_annotations_from_json as io_load_annotations_from_json,
)
from ..io.annotation_io import (
    load_annotations_from_temp as io_load_annotations_from_temp,
)
from ..io.annotation_io import save_annotations_to_json as io_save_annotations_to_json
from ..io.annotation_io import save_annotations_to_temp as io_save_annotations_to_temp
from ..items import GroupItem, PointItem, PolygonItem, ResizableRectItem


class AnnotationView(QGraphicsView):
    """标注视图，支持缩放和标注绘制。

    重要职责：
    - 展示图像并调整视图缩放
    - 管理 `rect_items/point_items/polygon_items` 列表
    - 响应鼠标/键盘交互以创建和编辑标注
    - 将读取/写入操作委托给 IO 层（`src.io.annotation_io`）
    """

    def __init__(self, parent: Optional[QGraphicsView] = None) -> None:
        super().__init__(parent)
        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.scene = QGraphicsScene(self)
        self.scene.setItemIndexMethod(QGraphicsScene.NoIndex)
        self.setScene(self.scene)
        self.pixmap_item = QGraphicsPixmapItem()
        self.scene.addItem(self.pixmap_item)

        self.zoom_factor = 1.0
        self.min_zoom = 0.1
        self.max_zoom = 10.0

        # 当前图片信息
        self.current_image_path = None
        self.image_width = 0
        self.image_height = 0

        # 绘制相关变量
        self.drawing_rect = False
        self.drawing_polygon = False
        self.start_pos = None
        self.current_rect = None
        self.current_polygon = None
        self.current_tool = None
        self.has_image = False

        # 存储所有标注
        self.rect_items = []
        self.point_items = []
        self.polygon_items = []

        # 分组相关变量
        self.groups = {}  # group_id -> {'items': list, 'group_item': GroupItem}
        self.next_group_id = 1

        # 多边形绘制临时点
        self.temp_points = []

        # 记录当前图片是否被修改过
        self.modified = False

    def set_image(self, image_path: str) -> bool:
        """设置显示的图像。

        返回 True 表示加载成功，False 表示失败（例如图片无法打开）。
        """
        pixmap = QPixmap(image_path)
        if pixmap.isNull():
            self.has_image = False
            return False

        self.has_image = True
        self.current_image_path = image_path

        # 清除之前的标注
        self.clear_annotations()

        self.pixmap_item.setPixmap(pixmap)
        self.setSceneRect(pixmap.rect())
        self.fitInView(self.sceneRect(), Qt.KeepAspectRatio)
        self.zoom_factor = 1.0

        # 保存图片尺寸
        self.image_width = pixmap.width()
        self.image_height = pixmap.height()

        # 重置修改标志
        self.modified = False

        return True

    def load_annotations_from_json(self, json_path: str) -> Any:
        """从 JSON 文件加载标注（委托到 IO 层）。"""
        return io_load_annotations_from_json(self, json_path)

    def _create_group_from_items(self, group_id: int, items: List[Any]) -> "GroupItem":
        """从项目列表创建分组并返回创建的 `GroupItem` 对象。"""
        # 创建分组框
        group_item = GroupItem()
        group_item.group_items = items
        group_item.group_id = group_id
        group_item.update_bounds()
        self.scene.addItem(group_item)

        # 将分组框引用存储到每个元素
        for item in items:
            item.group_item = group_item

        # 存储分组
        self.groups[group_id] = {"items": items, "group_item": group_item}

        return group_item

    def save_annotations_to_json(self, json_path: str, include_image_data: bool = False) -> Any:
        """保存标注到 JSON（委托到 IO 层）。"""
        return io_save_annotations_to_json(self, json_path, include_image_data=include_image_data)

    def save_annotations_to_temp(self, temp_dir: Optional[str] = None) -> Any:
        """保存标注到临时目录（委托到 IO 层）。"""
        return io_save_annotations_to_temp(self, temp_dir)

    def load_annotations_from_temp(self, temp_dir: Optional[str] = None) -> Any:
        """从临时目录加载标注（委托到 IO 层）。"""
        return io_load_annotations_from_temp(self, temp_dir)

    def has_unsaved_changes(self) -> bool:
        """检查是否有未保存的更改。"""
        return self.modified

    def set_modified(self, modified: bool = True) -> bool:
        """设置修改标志并返回新的标志值。"""
        self.modified = modified
        # 当发生修改时，自动保存到临时文件并立即通知主窗口刷新（使黄点即时显示）
        if self.modified:
            try:
                # 如果主窗口提供 temp_dir，则使用统一目录
                win = None
                try:
                    win = self.window()
                except Exception:
                    win = None

                temp_dir = None
                if win is not None:
                    temp_dir = getattr(win, "temp_dir", None)

                # 保存到临时目录（若 temp_dir 为 None 则使用默认实现）
                try:
                    self.save_annotations_to_temp(temp_dir)
                except Exception:
                    # 仍然忽略保存失败以不阻塞主流程
                    pass

                # 确保主窗口的 QFileSystemWatcher 关注该目录
                if win is not None and temp_dir and os.path.exists(temp_dir):
                    try:
                        if hasattr(win, "temp_watcher") and temp_dir not in win.temp_watcher.directories():
                            win.temp_watcher.addPath(temp_dir)
                    except Exception:
                        pass

                # 立即让主窗口刷新文件列表状态（传入当前索引以减少开销）
                if win is not None and hasattr(win, "update_file_list_status"):
                    try:
                        idx = getattr(win, "current_image_index", None)
                        win.update_file_list_status(idx)
                    except Exception:
                        pass
            except Exception:
                pass

        return self.modified

    def set_tool(self, tool: Optional[str]) -> None:
        """设置当前工具（例如 'select'/'rectangle'/'point'/'polygon'）。"""
        self.current_tool = tool
        if tool == "select":
            self.setDragMode(QGraphicsView.RubberBandDrag)
            self.setCursor(Qt.ArrowCursor)
        else:
            self.setDragMode(QGraphicsView.NoDrag)
            if tool == "polygon":
                self.setCursor(Qt.CrossCursor)

        # 取消正在进行的绘制
        if tool != "rectangle" and self.drawing_rect:
            if self.current_rect and self.current_rect in self.scene.items():
                self.scene.removeItem(self.current_rect)
            self.drawing_rect = False
            self.current_rect = None

        if tool != "polygon" and self.drawing_polygon:
            self.cancel_polygon_drawing()

    def wheelEvent(self, event: QWheelEvent):
        """处理滚轮事件，实现缩放"""
        zoom_in = event.angleDelta().y() > 0
        zoom_factor = 1.25 if zoom_in else 0.8

        new_zoom = self.zoom_factor * zoom_factor
        if new_zoom < self.min_zoom or new_zoom > self.max_zoom:
            return

        self.zoom_factor = new_zoom
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.scale(zoom_factor, zoom_factor)

    def mousePressEvent(self, event: QMouseEvent):
        """处理鼠标按下事件"""
        if not self.has_image:
            return
        scene_pos = self.mapToScene(event.pos())

        if self.current_tool == "select":
            super().mousePressEvent(event)
            return

        if self.current_tool == "rectangle" and event.button() == Qt.LeftButton:
            # 开始绘制矩形
            self.drawing_rect = True
            self.start_pos = scene_pos
            self.current_rect = ResizableRectItem(
                QRectF(self.start_pos, self.start_pos), label="rect"
            )
            self.scene.addItem(self.current_rect)

        elif self.current_tool == "point" and event.button() == Qt.LeftButton:
            # 创建点
            point_item = PointItem(scene_pos, label="point")
            self.scene.addItem(point_item)
            # 设置默认属性值（来自主窗口的 label_config）
            try:
                win = self.window()
                cfg = getattr(win, "label_config", {})
                defaults = cfg.get("point", {})
                for k, opts in defaults.items():
                    if opts:
                        point_item.attributes[k] = opts[0]
            except Exception:
                pass
            self.point_items.append(point_item)
            self.set_modified(True)

        elif self.current_tool == "polygon":
            if event.button() == Qt.LeftButton:
                # 获取场景坐标

                if not self.current_polygon:
                    # 创建新的多边形
                    self.current_polygon = PolygonItem()
                    self.scene.addItem(self.current_polygon)

                # 添加顶点
                self.current_polygon.add_vertex(scene_pos)
                self.drawing_polygon = True
                # 更新预览
                if hasattr(self.current_polygon, "preview_point"):
                    self.current_polygon.preview_point = scene_pos
                self.current_polygon.update()
        else:
            super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        """处理鼠标双击事件"""
        if self.current_tool == "polygon" and event.button() == Qt.LeftButton:
            if (
                self.drawing_polygon
                and self.current_polygon
                and self.current_polygon.close_polygon()
            ):
                # 封闭多边形
                if len(self.current_polygon.polygon_points) >= 3:
                    if hasattr(self.current_polygon, "preview_point"):
                        self.current_polygon.preview_point = None
                    self.current_polygon.update()
                    if hasattr(self.current_polygon, "preview_point"):
                        self.current_polygon.preview_point = None
                    self.current_polygon.update()
                    # 完成多边形并添加默认属性
                    poly = self.current_polygon
                    try:
                        win = self.window()
                        cfg = getattr(win, "label_config", {})
                        defaults = cfg.get("polygon", {})
                        for k, opts in defaults.items():
                            if opts:
                                poly.attributes[k] = opts[0]
                    except Exception:
                        pass
                    self.polygon_items.append(poly)
                    self.current_polygon = None

                    self.set_modified(True)
                else:
                    # 点太少，取消绘制
                    self.cancel_polygon_drawing()
                # event.accept()
                return

        super().mouseDoubleClickEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        """处理鼠标移动事件"""
        if self.drawing_rect and self.current_rect:
            # 更新正在绘制的矩形大小
            end_pos = self.mapToScene(event.position().toPoint())
            rect = QRectF(self.start_pos, end_pos).normalized()
            self.current_rect.setRect(rect)

        elif self.drawing_polygon and self.current_polygon:
            scene_pos = self.mapToScene(event.pos())
            if not hasattr(self.current_polygon, "preview_point"):
                self.current_polygon.preview_point = QPointF()
            self.current_polygon.preview_point = scene_pos
            self.current_polygon.update()
            super().mouseMoveEvent(event)
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        """处理鼠标释放事件"""
        if self.drawing_rect and self.current_rect and event.button() == Qt.LeftButton:
            # 完成矩形绘制
            self.drawing_rect = False
            end_pos = self.mapToScene(event.position().toPoint())

            # 如果矩形太小，则删除
            if (
                abs(end_pos.x() - self.start_pos.x()) < 10
                or abs(end_pos.y() - self.start_pos.y()) < 10
            ):
                self.scene.removeItem(self.current_rect)
            else:
                new_rect = self.current_rect
                # 设置默认属性（来自主窗口的 label_config）
                try:
                    win = self.window()
                    cfg = getattr(win, "label_config", {})
                    defaults = cfg.get("rectangle", {})
                    for k, opts in defaults.items():
                        if opts:
                            new_rect.attributes[k] = opts[0]
                except Exception:
                    pass
                # 取消其他选中项，仅选中新创建的矩形
                for it in list(self.scene.selectedItems()):
                    it.setSelected(False)
                self.rect_items.append(new_rect)
                # 选中新矩形以显示缩放手柄
                try:
                    new_rect.setSelected(True)
                    new_rect.update()
                except Exception:
                    pass
                self.current_rect = None
                self.set_modified(True)
        else:
            self.set_modified(True)
            super().mouseReleaseEvent(event)

    def keyPressEvent(self, event: QKeyEvent):
        """处理键盘事件 - 修复删除快捷键"""
        if event.key() == Qt.Key_Delete:
            # 删除所有选中的项
            for item in self.scene.selectedItems():
                if isinstance(item, ResizableRectItem) and item in self.rect_items:
                    self.rect_items.remove(item)
                elif isinstance(item, PointItem) and item in self.point_items:
                    self.point_items.remove(item)
                elif isinstance(item, PolygonItem) and item in self.polygon_items:
                    self.polygon_items.remove(item)
                elif isinstance(item, GroupItem):
                    # 删除分组
                    self.remove_group(item)
                self.scene.removeItem(item)
                self.set_modified(True)

        elif event.key() == Qt.Key_Escape:
            # 按ESC键取消绘制
            if self.drawing_polygon:
                self.cancel_polygon_drawing()
            elif self.drawing_rect and self.current_rect:
                if self.current_rect in self.scene.items():
                    self.scene.removeItem(self.current_rect)
                self.drawing_rect = False
                self.current_rect = None
        else:
            super().keyPressEvent(event)

    def group_selected_items(self):
        """将选中的项分组"""
        selected_items = self.scene.selectedItems()
        if len(selected_items) < 2:
            return False

        # 过滤掉已分组框本身
        valid_items = []
        for item in selected_items:
            if isinstance(item, GroupItem):
                continue
            valid_items.append(item)

        if len(valid_items) < 2:
            return False

        # 创建新组
        group_id = self.next_group_id
        self.next_group_id += 1

        # 收集组内元素
        group_items = []
        for item in valid_items:
            # 移除旧分组（如果存在）
            if hasattr(item, "group_id") and item.group_id is not None:
                self.remove_from_group(item)

            # 添加到新组
            item.group_id = group_id
            group_items.append(item)

        # 创建分组
        self._create_group_from_items(group_id, group_items)

        # 取消所有元素的选择状态
        for item in self.scene.selectedItems():
            item.setSelected(False)

        # 只选中分组框
        group_item = self.groups[group_id]["group_item"]
        group_item.setSelected(True)

        self.set_modified(True)
        return True

    def ungroup_selected_items(self):
        """取消选中的分组"""
        selected_items = self.scene.selectedItems()
        if not selected_items:
            return

        for item in selected_items:
            if isinstance(item, GroupItem):
                # 取消分组
                self.remove_group(item)
                self.set_modified(True)

    def remove_from_group(self, item):
        """从分组中移除元素"""
        if not hasattr(item, "group_id") or item.group_id is None:
            return

        group_id = item.group_id
        if group_id in self.groups:
            group = self.groups[group_id]

            # 从分组中移除元素
            if item in group["items"]:
                group["items"].remove(item)
                item.group_id = None
                item.group_item = None

                # 如果分组中还有元素，更新分组框
                if group["items"]:
                    group["group_item"].group_items = group["items"]
                    group["group_item"].update_bounds()
                else:
                    # 分组为空，删除分组框
                    self.remove_group(group["group_item"])

    def remove_group(self, group_item):
        """删除整个分组"""
        if not hasattr(group_item, "group_id") or group_item.group_id is None:
            return

        group_id = group_item.group_id
        if group_id in self.groups:
            group = self.groups[group_id]

            # 移除所有元素的分组信息
            for item in group["items"]:
                item.group_id = None
                item.group_item = None

            # 从场景中删除分组框
            if group_item in self.scene.items():
                self.scene.removeItem(group_item)

            # 从分组字典中移除
            del self.groups[group_id]

    def clear_annotations(self):
        """清除所有标注"""
        # 清除矩形
        for rect in self.rect_items:
            if rect in self.scene.items():
                self.scene.removeItem(rect)
        self.rect_items.clear()

        # 清除点
        for point in self.point_items:
            if point in self.scene.items():
                self.scene.removeItem(point)
        self.point_items.clear()

        # 清除多边形
        for polygon in self.polygon_items:
            if polygon in self.scene.items():
                self.scene.removeItem(polygon)
        self.polygon_items.clear()

        # 清除分组
        for group_id, group in self.groups.items():
            if group["group_item"] in self.scene.items():
                self.scene.removeItem(group["group_item"])
        self.groups.clear()
        self.next_group_id = 1

        # 取消正在绘制的多边形
        if self.drawing_polygon:
            self.cancel_polygon_drawing()

        # 清除修改标志
        self.modified = False

    def fit_to_view(self):
        """适应视图大小"""
        if self.has_image:
            self.fitInView(self.sceneRect(), Qt.KeepAspectRatio)
            self.zoom_factor = 1.0

    def cancel_polygon_drawing(self):
        """取消多边形绘制"""
        if self.current_polygon and self.current_polygon in self.scene.items():
            self.scene.removeItem(self.current_polygon)
            self.drawing_polygon = False
            self.temp_points = []
            self.current_polygon = None

    def clear_temp_files(self, temp_dir=None):
        """清除所有临时文件"""
        if not temp_dir:
            temp_dir = os.path.join(os.path.expanduser("~"), ".maplabel_temp")

        if os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
                return True
            except Exception as e:
                print(f"清除临时文件时出错: {e}")
                return False
        return True
