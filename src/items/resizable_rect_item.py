"""可调整大小的矩形 QGraphicsItem，带调整手柄和移动支持。

提供 `ResizableRectItem`，这是应用中用于矩形标注的 QGraphicsRectItem 子类。
该项包含调整大小的手柄并实现自定义移动逻辑，使得矩形可以原地更新并正确序列化。
"""

from typing import Any, Optional

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPainterPath, QPen
from PySide6.QtWidgets import QGraphicsRectItem, QGraphicsItem


class ResizableRectItem(QGraphicsRectItem):
    """可调整大小的矩形标注项"""

    def __init__(self, rect=None, label="rect", group_id=None, parent=None):
        super().__init__(rect, parent)

        # 设置矩形的样式
        self.normal_pen = QPen(QColor(0, 255, 0), 1)
        self.selected_pen = QPen(QColor(255, 165, 0), 1)
        self.setPen(self.normal_pen)
        self.setBrush(QBrush(QColor(0, 255, 0, 50)))

        # 允许矩形被选择和移动
        self.setFlag(QGraphicsRectItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsRectItem.ItemIsMovable, True)
        self.setFlag(QGraphicsRectItem.ItemSendsGeometryChanges, True)

        # 重要：启用悬停事件
        self.setAcceptHoverEvents(True)

        # 标注标签
        self.label = label
        # 形状类型
        self.shape_type = "rectangle"

        # 所属分组
        self.group_id = group_id
        self.group_item = None

        # 用于JSON序列化的唯一ID
        self.item_id = id(self)

        # 可编辑属性字典（对应 label.json 中定义的属性），序列化时放到 'flags'
        self.attributes = {}

        # 调整大小的手柄设置
        self.handle_size = 6
        self.handles = {}

        # 只保留左上和右下两个句柄
        self.handle_positions = [(0, 0, "top_left"), (1, 1, "bottom_right")]

        # 创建调整大小的手柄
        for x, y, pos in self.handle_positions:
            handle = QGraphicsRectItem(0, 0, self.handle_size, self.handle_size, self)
            handle.setPen(QPen(QColor(255, 255, 255)))
            handle.setBrush(QBrush(QColor(0, 0, 255)))
            handle.setVisible(False)
            handle.setZValue(1)
            # 允许手柄被选择和接收鼠标事件
            handle.setFlag(QGraphicsRectItem.ItemIsSelectable, False)
            handle.setFlag(QGraphicsRectItem.ItemIsMovable, False)
            handle.setAcceptHoverEvents(False)
            self.handles[pos] = handle

        # 立即初始化句柄位置
        self.update_handles()
        self.resizing = False
        # 自定义移动状态（用于在平移时更新 rect 而不是仅改变 pos）
        self._moving = False
        self._move_start_scene_pos = None
        self._move_start_rect = None

    def update_handles(self) -> None:
        """更新手柄位置 - 将手柄放在矩形边缘上。"""
        rect = self.rect()
        for x, y, pos in self.handle_positions:
            handle = self.handles[pos]

            # 计算句柄在矩形边缘的位置（而不是内部）
            if x == 0:  # 左边
                handle_x = rect.x() - self.handle_size / 2
            else:  # 右边
                handle_x = rect.x() + rect.width() - self.handle_size / 2

            if y == 0:  # 上边
                handle_y = rect.y() - self.handle_size / 2
            else:  # 下边
                handle_y = rect.y() + rect.height() - self.handle_size / 2

            handle.setRect(handle_x, handle_y, self.handle_size, self.handle_size)

    def itemChange(self, change: Any, value: Any) -> Any:
        """处理项变化。

        当位置或变换发生变化时，更新手柄和分组边界，并尝试通知视图刷新
        修改标志与属性面板坐标显示。
        """
        if change in [
            QGraphicsRectItem.ItemPositionHasChanged,
            QGraphicsRectItem.ItemTransformHasChanged,
        ]:
            # 如果属于分组，更新分组框
            if hasattr(self, "group_item") and self.group_item:
                self.group_item.update_bounds()
            self.update_handles()

            # 通知视图更新状态与属性坐标（若存在视图）
            try:
                scene = self.scene()
                if scene:
                    views = scene.views()
                    if views:
                        view = views[0]
                        if hasattr(view, "set_modified"):
                            view.set_modified(True)
                        if hasattr(view, "update_property_coords"):
                            view.update_property_coords()
            except Exception:
                pass

        return super().itemChange(change, value)

    def paint(self, painter, option, widget=None) -> None:
        """绘制矩形。"""
        if self.isSelected():
            painter.setPen(self.selected_pen)
        else:
            painter.setPen(self.normal_pen)

        painter.setBrush(self.brush())
        painter.drawRect(self.rect())

        # 如果被选中，显示手柄
        if self.isSelected():
            self.update_handles()
            for pos, handle in self.handles.items():
                handle.setVisible(True)
        else:
            # 未被选中时隐藏手柄
            for pos, handle in self.handles.items():
                handle.setVisible(False)

    def contains_handle(self, pos: QPointF) -> Optional[str]:
        """检查是否点击到手柄 - 修复坐标转换问题。

        返回被点击的句柄标识（如 'top_left'），若无则返回 None。
        """
        for handle_pos, handle in self.handles.items():
            if not handle.isVisible():
                continue

            # 获取手柄在场景坐标系中的矩形
            handle_scene_rect = handle.mapRectToScene(handle.rect())

            # 扩大热区范围，确保边缘部分也能被检测到
            hotspot_rect = QRectF(
                handle_scene_rect.x() - 10,
                handle_scene_rect.y() - 10,
                handle_scene_rect.width() + 20,
                handle_scene_rect.height() + 20,
            )

            # 检查点击位置是否在热区内
            if hotspot_rect.contains(pos):
                return handle_pos
        return None

    def boundingRect(self) -> QRectF:
        """重写边界矩形，包含所有手柄的可见区域。"""
        rect = super().boundingRect()

        # 如果被选中，扩展边界以包含所有手柄
        if self.isSelected():
            for handle in self.handles.values():
                if handle.isVisible():
                    handle_rect = handle.mapRectToParent(handle.rect())
                    rect = rect.united(handle_rect)

        return rect

    def shape(self) -> QPainterPath:
        """重写形状，确保点击检测包含所有手柄区域。"""
        path = super().shape()

        # 如果被选中，添加所有手柄的形状
        if self.isSelected():
            for handle in self.handles.values():
                if handle.isVisible():
                    handle_path = QPainterPath()
                    handle_path.addRect(handle.mapRectToParent(handle.rect()))
                    path = path.united(handle_path)

        return path

    def mousePressEvent(self, event) -> None:
        """处理鼠标按下事件。

        在句柄上按下进入缩放状态，否则进入自定义平移模式。
        """
        if self.isSelected():
            # 使用场景坐标检查是否点击到手柄
            handle_pos = self.contains_handle(event.scenePos())
            if handle_pos:
                self.resizing = True
                self.resize_pos = handle_pos
                self.resize_start_rect = self.rect()
                self.resize_start_scene_pos = event.scenePos()

                # 记录当前变换矩阵
                self.resize_start_transform = self.transform()

                # 设置光标为SizeFDiagCursor（斜箭头）
                self.setCursor(Qt.SizeFDiagCursor)
                event.accept()
                return

        # 非手柄区域：进入自定义移动模式（不调用 super，这样我们可以在移动时更新 rect）
        self.resizing = False
        self._moving = True
        self._move_start_scene_pos = event.scenePos()
        self._move_start_rect = self.rect()
        self.setCursor(Qt.SizeAllCursor)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        """处理鼠标移动事件 - 支持缩放与自定义平移。"""
        if self.resizing:
            # 使用场景坐标计算偏移
            current_scene_pos = event.scenePos()
            dx = current_scene_pos.x() - self.resize_start_scene_pos.x()
            dy = current_scene_pos.y() - self.resize_start_scene_pos.y()

            # 考虑项变换的影响
            if not self.transform().isIdentity():
                # 获取相对于项的局部偏移
                local_offset = self.mapFromScene(current_scene_pos) - self.mapFromScene(
                    self.resize_start_scene_pos
                )
                dx = local_offset.x()
                dy = local_offset.y()

            rect = self.resize_start_rect

            if self.resize_pos == "top_left":
                # 左上角调整：同时改变位置和大小
                new_rect = QRectF(
                    rect.left() + dx,
                    rect.top() + dy,
                    rect.width() - dx,
                    rect.height() - dy,
                )
            elif self.resize_pos == "bottom_right":
                # 右下角调整：只改变大小
                new_rect = QRectF(
                    rect.left(), rect.top(), rect.width() + dx, rect.height() + dy
                )

            # 确保矩形不会太小
            if new_rect.width() > 10 and new_rect.height() > 10:
                # 确保矩形不会颠倒
                if new_rect.width() < 0:
                    new_rect.setLeft(new_rect.left() + new_rect.width())
                    new_rect.setWidth(-new_rect.width())
                if new_rect.height() < 0:
                    new_rect.setTop(new_rect.top() + new_rect.height())
                    new_rect.setHeight(-new_rect.height())

                self.setRect(new_rect)
                self.update_handles()

                # 如果属于分组，更新分组框
                if hasattr(self, "group_item") and self.group_item:
                    self.group_item.update_bounds()

                # 通知视图更新
                self.prepareGeometryChange()

        elif self._moving:
            # 计算场景坐标的偏移并转换到项的本地坐标系
            start_scene = self._move_start_scene_pos
            current_scene = event.scenePos()
            local_start = self.mapFromScene(start_scene)
            local_current = self.mapFromScene(current_scene)
            dx = local_current.x() - local_start.x()
            dy = local_current.y() - local_start.y()

            rect = self._move_start_rect
            # 平移矩形
            new_rect = QRectF(rect.x() + dx, rect.y() + dy, rect.width(), rect.height())
            self.setRect(new_rect)
            self.update_handles()
            if hasattr(self, "group_item") and self.group_item:
                self.group_item.update_bounds()
            # 更新几何并通知视图
            self.prepareGeometryChange()
            try:
                scene = self.scene()
                if scene:
                    views = scene.views()
                    if views:
                        view = views[0]
                        if hasattr(view, "set_modified"):
                            view.set_modified(True)
                        if hasattr(view, "update_property_coords"):
                            view.update_property_coords()
            except Exception:
                pass
            # event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        """处理鼠标释放事件。"""
        if self.resizing:
            self.resizing = False
            # 鼠标释放后，需要重新检查悬停位置来设置正确的光标
            self.update_cursor(event.scenePos())
            event.accept()
        else:
            if self._moving:
                self._moving = False
                # 触发一次坐标/状态更新
                try:
                    scene = self.scene()
                    if scene:
                        views = scene.views()
                        if views:
                            view = views[0]
                            if hasattr(view, "set_modified"):
                                view.set_modified(True)
                            if hasattr(view, "update_property_coords"):
                                view.update_property_coords()
                except Exception:
                    pass
                # 恢复光标状态
                self.update_cursor(event.scenePos())
                event.accept()
            else:
                super().mouseReleaseEvent(event)

    def update_cursor(self, scene_pos: QPointF) -> None:
        """根据鼠标位置更新光标。"""
        # 检查是否在句柄上（仅在选中状态下）
        if self.isSelected():
            handle_pos = self.contains_handle(scene_pos)
            if handle_pos:
                # 如果在句柄上，设置为调整大小光标
                self.setCursor(Qt.SizeFDiagCursor)
                return

        # 检查是否在矩形内部（使用局部坐标）
        local_pos = self.mapFromScene(scene_pos)
        if self.rect().contains(local_pos):
            # 如果在矩形内部，设置为移动光标
            self.setCursor(Qt.SizeAllCursor)
        else:
            # 否则恢复默认光标
            self.setCursor(Qt.ArrowCursor)

    def hoverMoveEvent(self, event) -> None:
        """处理悬停移动事件，更新光标。"""
        # 更新光标基于当前位置
        self.update_cursor(event.scenePos())
        super().hoverMoveEvent(event)

    def hoverEnterEvent(self, event) -> None:
        """处理悬停进入事件。"""
        # 当鼠标进入矩形区域时，更新光标
        self.update_cursor(event.scenePos())
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event) -> None:
        """处理悬离开事件。"""
        # 当鼠标离开矩形区域时，恢复为普通箭头光标
        self.setCursor(Qt.ArrowCursor)
        super().hoverLeaveEvent(event)

    def to_dict(self) -> dict:
        """转换为字典用于JSON序列化（LabelMe shapes 条目）。"""
        rect = self.rect()
        x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()
        # LabelMe rectangle: use two points [top-left, bottom-right]
        return {
            "label": self.label,
            "points": [[x, y], [x + w, y + h]],
            "group_id": self.group_id,
            "shape_type": "rectangle",
            "attrs": self.attributes.copy() if self.attributes else {},
            "flags": {},
        }

    @classmethod
    def from_dict(cls, data: dict, scene: Optional[Any] = None) -> Optional["ResizableRectItem"]:
        """从字典创建矩形项。

        返回新创建的 `ResizableRectItem` 或在数据无效时返回 None。
        """
        # Accept LabelMe rectangles represented as 2 points ([tl, br])
        # or 4 points (clockwise). Coerce any >=2 points to bounding box.
        points = data.get("points")
        if not isinstance(points, list) or len(points) < 2:
            return None

        try:
            x_values = [float(p[0]) for p in points]
            y_values = [float(p[1]) for p in points]
        except Exception:
            return None

        min_x, max_x = min(x_values), max(x_values)
        min_y, max_y = min(y_values), max(y_values)

        rect = QRectF(min_x, min_y, max_x - min_x, max_y - min_y)
        label = data.get("label", "rect")
        item = cls(rect, label, data.get("group_id"))
        # 恢复自定义属性：优先使用 'attrs'，兼容 'flags'
        item.attributes = data.get("attrs", None)
        if item.attributes is None:
            item.attributes = data.get("flags", {}) or {}

        return item
