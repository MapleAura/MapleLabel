"""可调整大小的矩形 QGraphicsItem，带调整手柄和移动支持。

提供 `ResizableRectItem`，这是应用中用于矩形标注的 QGraphicsRectItem 子类。
该项包含调整大小的手柄并实现自定义移动逻辑，使得矩形可以原地更新并正确序列化。
同时支持旋转功能。
"""

import math
from typing import Any, Optional

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen, QTransform
from PySide6.QtWidgets import QGraphicsEllipseItem, QGraphicsRectItem, QGraphicsItem


class RotateHandle(QGraphicsEllipseItem):
    """旋转句柄 - 圆形按钮，圈上有旋转箭头图标"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.handle_size = 10
        self.setRect(-self.handle_size / 2, -self.handle_size / 2, self.handle_size, self.handle_size)
        
        # 样式设置
        self.setPen(QPen(QColor(255, 165, 0), 2))  # 橙色边框
        self.setBrush(QBrush(QColor(255, 255, 255)))  # 白色填充
        self.setVisible(False)
        self.setZValue(1)
        self.setAcceptHoverEvents(False)

    def paint(self, painter: QPainter, option, widget=None) -> None:
        """绘制旋转句柄 - 圆形加旋转箭头"""
        # 绘制圆形背景
        painter.setPen(self.pen())
        painter.setBrush(self.brush())
        painter.drawEllipse(self.rect())

        # 绘制圆上的旋转箭头
        arrow_color = QColor(255, 100, 0)
        painter.setPen(QPen(arrow_color, 1.5))
        
        # 圆心
        center = self.rect().center()
        radius = self.handle_size / 2 - 2  # 圆的半径，留一点边距
        
        # 绘制弧形箭头（顺时针旋转，从上方开始）
        # 弧从 45 度开始，顺时针转 270 度
        path = QPainterPath()
        path.arcMoveTo(center.x() - radius, center.y() - radius, 
                       radius * 2, radius * 2, 45)
        path.arcTo(center.x() - radius, center.y() - radius, 
                   radius * 2, radius * 2, 45, 270)
        painter.drawPath(path)
        
        # 绘制箭头头部（在结束位置）
        # 270 度旋转后的位置是下方左边
        end_angle = math.radians(45 - 270)  # 最后的角度
        end_x = center.x() + radius * math.cos(end_angle)
        end_y = center.y() + radius * math.sin(end_angle)
        
        # 箭头尖端方向（指向弧的切线方向）
        arrow_size = 3
        # 切线方向是垂直于半径的
        arrow_angle1 = end_angle + math.pi / 2
        arrow_angle2 = end_angle - math.pi / 2
        
        p1 = QPointF(
            end_x + arrow_size * math.cos(arrow_angle1),
            end_y + arrow_size * math.sin(arrow_angle1)
        )
        p2 = QPointF(
            end_x + arrow_size * math.cos(arrow_angle2),
            end_y + arrow_size * math.sin(arrow_angle2)
        )
        
        painter.drawLine(QPointF(end_x, end_y), p1)
        painter.drawLine(QPointF(end_x, end_y), p2)


class ResizableRectItem(QGraphicsRectItem):
    """可调整大小的矩形标注项"""

    def __init__(self, rect=None, label="rect", group_id=None, parent=None):
        super().__init__(rect, parent)

        # 设置矩形的样式
        self.default_pen_color = QColor(0, 255, 0)
        self.default_brush_color = QColor(0, 255, 0, 50)
        self.normal_pen = QPen(self.default_pen_color, 1)
        self.selected_pen = QPen(QColor(255, 165, 0), 1)
        self.setPen(self.normal_pen)
        self.setBrush(QBrush(self.default_brush_color))

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

        # 旋转角度（角度制，OpenCV 兼容），默认为 0
        self.angle = 0.0

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

        # 创建旋转按钮（位于矩形顶部中心）
        self.rotate_handle = RotateHandle(self)
        self.rotate_handle.setVisible(False)

        # 立即初始化句柄位置
        self.update_handles()
        self.resizing = False
        self.rotating = False
        # 自定义移动状态（用于在平移时更新 rect 而不是仅改变 pos）
        self._moving = False
        self._move_start_scene_pos = None
        self._move_start_rect = None
        # 撤销支持：记录移动/旋转起始状态
        self._undo_move_start_rect = None
        self._undo_rotate_start_angle = None

    def apply_group_color(self, color: QColor) -> None:
        """Apply a group color to the rectangle (border + translucent fill)."""
        line_color = QColor(color)
        line_color.setAlpha(255)
        fill_color = QColor(color)
        fill_color.setAlpha(50)
        self.normal_pen = QPen(line_color, self.normal_pen.width())
        self.setPen(self.normal_pen)
        self.setBrush(QBrush(fill_color))
        self.update_handles()
        self.update()

    def reset_color(self) -> None:
        """Restore default green colors after ungrouping."""
        self.normal_pen = QPen(self.default_pen_color, self.normal_pen.width())
        self.setPen(self.normal_pen)
        self.setBrush(QBrush(self.default_brush_color))
        self.update_handles()
        self.update()

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

        # 更新旋转按钮位置（位于矩形顶部中心，靠近矩形框）
        rotate_x = rect.x() + rect.width() / 2
        rotate_y = rect.y() - 12  # 距离顶部 12 像素，更靠近矩形框
        self.rotate_handle.setPos(rotate_x, rotate_y)

    def _get_undo_manager(self):
        """尝试从视图/主窗口获取撤销管理器。"""
        try:
            scene = self.scene()
            if not scene:
                return None
            views = scene.views()
            if not views:
                return None
            view = views[0]
            win = view.window() if hasattr(view, "window") else None
            if win is not None and hasattr(win, "undo_manager"):
                return win.undo_manager
        except Exception:
            return None
        return None

    def _apply_state(self, rect=None, angle=None) -> None:
        """应用矩形状态（用于撤销/重做）。"""
        if rect is not None:
            self.setRect(QRectF(rect))
        if angle is not None:
            try:
                self.angle = float(angle) % 360.0
            except Exception:
                self.angle = 0.0

        # 根据当前角度刷新变换
        self._apply_rotation_transform()
        self.update_handles()

        if hasattr(self, "group_item") and self.group_item:
            self.group_item.update_bounds()

        try:
            scene = self.scene()
            if scene:
                views = scene.views()
                if views:
                    view = views[0]
                    if hasattr(view, "update_property_coords"):
                        view.update_property_coords()
        except Exception:
            pass

    def _rect_equals(self, a: QRectF, b: QRectF, eps: float = 1e-6) -> bool:
        return (
            abs(a.x() - b.x()) <= eps
            and abs(a.y() - b.y()) <= eps
            and abs(a.width() - b.width()) <= eps
            and abs(a.height() - b.height()) <= eps
        )

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

        # 如果被选中，显示手柄和旋转按钮
        if self.isSelected():
            self.update_handles()
            for pos, handle in self.handles.items():
                handle.setVisible(True)
            self.rotate_handle.setVisible(True)
        else:
            # 未被选中时隐藏手柄和旋转按钮
            for pos, handle in self.handles.items():
                handle.setVisible(False)
            self.rotate_handle.setVisible(False)

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

    def contains_rotate_handle(self, pos: QPointF) -> bool:
        """检查是否点击到旋转按钮。"""
        if not self.rotate_handle.isVisible():
            return False

        # 获取旋转句柄在场景坐标系中的矩形
        handle_scene_rect = self.rotate_handle.mapRectToScene(self.rotate_handle.rect())

        # 扩大热区范围，确保边缘部分也能被检测到
        hotspot_rect = QRectF(
            handle_scene_rect.x() - 10,
            handle_scene_rect.y() - 10,
            handle_scene_rect.width() + 20,
            handle_scene_rect.height() + 20,
        )
        return hotspot_rect.contains(pos)

    def boundingRect(self) -> QRectF:
        """重写边界矩形，包含所有手柄的可见区域。"""
        rect = super().boundingRect()

        # 如果被选中，扩展边界以包含所有手柄和旋转句柄
        if self.isSelected():
            for handle in self.handles.values():
                if handle.isVisible():
                    handle_rect = handle.mapRectToParent(handle.rect())
                    rect = rect.united(handle_rect)
            
            # 包含旋转句柄
            if self.rotate_handle.isVisible():
                rotate_rect = self.rotate_handle.mapRectToParent(self.rotate_handle.rect())
                rect = rect.united(rotate_rect)

        return rect

    def shape(self) -> QPainterPath:
        """重写形状，确保点击检测包含所有手柄区域。"""
        path = super().shape()

        # 如果被选中，添加所有手柄和旋转句柄的形状
        if self.isSelected():
            for handle in self.handles.values():
                if handle.isVisible():
                    handle_path = QPainterPath()
                    handle_path.addRect(handle.mapRectToParent(handle.rect()))
                    path = path.united(handle_path)
            
            # 添加旋转句柄的形状
            if self.rotate_handle.isVisible():
                rotate_path = QPainterPath()
                rotate_path.addRect(self.rotate_handle.mapRectToParent(self.rotate_handle.rect()))
                path = path.united(rotate_path)

        return path

    def mousePressEvent(self, event) -> None:
        """处理鼠标按下事件。

        在句柄上按下进入缩放状态，在旋转按钮上按下进入旋转状态，否则进入自定义平移模式。
        """
        if self.isSelected():
            # 先检查是否点击到旋转按钮
            if self.contains_rotate_handle(event.scenePos()):
                self.rotating = True
                self.rotate_start_scene_pos = event.scenePos()
                self.rotate_start_angle = self.angle
                self._undo_rotate_start_angle = self.angle
                # 不记录旋转中心，每次旋转时实时计算
                self.setCursor(Qt.OpenHandCursor)
                event.accept()
                return

            # 使用场景坐标检查是否点击到调整大小的手柄
            handle_pos = self.contains_handle(event.scenePos())
            if handle_pos:
                self.resizing = True
                self.resize_pos = handle_pos
                self.resize_start_rect = self.rect()
                self.resize_start_scene_pos = event.scenePos()

                # 保存固定角的项坐标（未旋转状态下的坐标）
                if handle_pos == "bottom_right":
                    # 右下角拉伸时，左上角固定
                    self.resize_fixed_corner_item = QPointF(
                        self.resize_start_rect.left(),
                        self.resize_start_rect.top()
                    )
                elif handle_pos == "top_left":
                    # 左上角拉伸时，右下角固定
                    self.resize_fixed_corner_item = QPointF(
                        self.resize_start_rect.right(),
                        self.resize_start_rect.bottom()
                    )

                # 同时保存固定角在场景坐标中的位置（用于最终对齐）
                try:
                    self.resize_fixed_corner_scene = self.mapToScene(self.resize_fixed_corner_item)
                except Exception:
                    self.resize_fixed_corner_scene = None

                # 记录当前变换矩阵
                self.resize_start_transform = self.transform()

                # 设置光标为SizeFDiagCursor（斜箭头）
                self.setCursor(Qt.SizeFDiagCursor)
                event.accept()
                return

        # 非手柄区域：进入自定义移动模式（不调用 super，这样我们可以在移动时更新 rect）
        self.resizing = False
        self.rotating = False
        self._moving = True
        self._move_start_scene_pos = event.scenePos()
        self._move_start_rect = self.rect()
        self._undo_move_start_rect = QRectF(self._move_start_rect)
        # 记录平移开始时的场景坐标位置（用于准确计算偏移）
        self._move_start_scene_rect_topLeft = self.mapToScene(self._move_start_rect.topLeft())
        self.setCursor(Qt.SizeAllCursor)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        """处理鼠标移动事件 - 支持缩放、旋转与自定义平移。"""
        if self.rotating:
            # 计算旋转角度
            # 每次都重新计算旋转中心（确保基于最新的 rect 状态）
            rect = self.rect()
            center_local = QPointF(rect.x() + rect.width() / 2, rect.y() + rect.height() / 2)
            center_scene = self.mapToScene(center_local)
            
            start_vec = self.rotate_start_scene_pos - center_scene
            current_vec = event.scenePos() - center_scene

            # 计算角度差（使用反正切）
            start_angle = math.atan2(start_vec.y(), start_vec.x()) * 180.0 / math.pi
            current_angle = math.atan2(current_vec.y(), current_vec.x()) * 180.0 / math.pi

            angle_delta = current_angle - start_angle

            # 更新旋转角度
            self.angle = (self.rotate_start_angle + angle_delta) % 360.0

            # 更新变换矩阵（应用旋转）
            self._apply_rotation_transform()

            # 更新句柄位置
            self.update_handles()

            # 如果属于分组，更新分组框
            if hasattr(self, "group_item") and self.group_item:
                self.group_item.update_bounds()

            # 通知视图更新
            self.prepareGeometryChange()
            self.update()

        elif self.resizing:
            # 在项坐标系中工作（避免旋转变换的影响）
            # 通过逆变换将场景坐标转换为项坐标
            current_scene_pos = event.scenePos()
            inv_transform, _ = self.resize_start_transform.inverted()
            current_item_pos = inv_transform.map(current_scene_pos)
            
            if self.resize_pos == "bottom_right":
                # 右下角拉伸，左上角固定
                fixed_tl_item = self.resize_fixed_corner_item
                active_br_item = current_item_pos
                
                # 构造新矩形
                new_rect = QRectF(
                    min(fixed_tl_item.x(), active_br_item.x()),
                    min(fixed_tl_item.y(), active_br_item.y()),
                    abs(active_br_item.x() - fixed_tl_item.x()),
                    abs(active_br_item.y() - fixed_tl_item.y())
                )
                
            elif self.resize_pos == "top_left":
                # 左上角拉伸，右下角固定
                active_tl_item = current_item_pos
                fixed_br_item = self.resize_fixed_corner_item
                
                # 构造新矩形
                new_rect = QRectF(
                    min(active_tl_item.x(), fixed_br_item.x()),
                    min(active_tl_item.y(), fixed_br_item.y()),
                    abs(fixed_br_item.x() - active_tl_item.x()),
                    abs(fixed_br_item.y() - active_tl_item.y())
                )
            else:
                return

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

                # 在拉伸过程中不要重复应用变换，避免坐标系混淆。
                # 仅更新分组边界并通知视图，最终在 mouseReleaseEvent 中统一应用变换。
                if hasattr(self, "group_item") and self.group_item:
                    self.group_item.update_bounds()

                # 通知视图更新
                self.prepareGeometryChange()

        elif self._moving:
            # 直接基于起始位置计算偏移（避免 sceneBoundingRect 动态变化的问题）
            # 计算鼠标在场景坐标中的偏移量
            delta_x = event.scenePos().x() - self._move_start_scene_pos.x()
            delta_y = event.scenePos().y() - self._move_start_scene_pos.y()
            
            # 计算新的场景坐标位置
            new_scene_pos_x = self._move_start_scene_rect_topLeft.x() + delta_x
            new_scene_pos_y = self._move_start_scene_rect_topLeft.y() + delta_y
            
            # 转换回项坐标系
            new_pos_item = self.mapFromScene(QPointF(new_scene_pos_x, new_scene_pos_y))
            
            # 根据起始矩形大小，设置新的矩形位置
            rect = self._move_start_rect
            self.setRect(QRectF(
                new_pos_item.x(),
                new_pos_item.y(),
                rect.width(),
                rect.height()
            ))
            
            # 平移后如果有旋转角度，需要重新应用旋转变换以保持旋转中心的物理位置不变
            if self.angle != 0.0:
                self._apply_rotation_transform()
            
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
        if self.rotating:
            self.rotating = False
            # 记录旋转撤销
            try:
                old_angle = getattr(self, "_undo_rotate_start_angle", None)
                new_angle = self.angle
                if old_angle is not None and abs(new_angle - old_angle) > 1e-6:
                    um = self._get_undo_manager()
                    if um:
                        def _undo():
                            self._apply_state(angle=old_angle)

                        def _redo():
                            self._apply_state(angle=new_angle)

                        um.push_action(_undo, _redo, name="rotate_rect")
            except Exception:
                pass
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
        elif self.resizing:
            self.resizing = False
            # 在拉伸结束后统一应用旋转变换（如果存在角度），并对齐固定角到原始场景坐标
            try:
                # 记录原始固定角在场景中的期望位置
                fixed_scene = getattr(self, "resize_fixed_corner_scene", None)
                fixed_item = getattr(self, "resize_fixed_corner_item", None)

                # 先应用旋转变换（基于当前 angle 和新的 rect）
                if self.angle != 0.0:
                    self._apply_rotation_transform()

                # 如果我们有固定角的场景期望位置，则计算偏移并移动项以对齐
                if fixed_scene is not None and fixed_item is not None:
                    try:
                        # 当前位置下固定角的实际场景坐标
                        actual_scene = self.mapToScene(fixed_item)
                        dx = fixed_scene.x() - actual_scene.x()
                        dy = fixed_scene.y() - actual_scene.y()
                        if abs(dx) > 1e-6 or abs(dy) > 1e-6:
                            # 将项在场景中移动该偏移量
                            pos = self.pos()
                            self.setPos(QPointF(pos.x() + dx, pos.y() + dy))
                    except Exception:
                        pass

            except Exception:
                pass

            # 更新分组边界并通知视图
            try:
                if hasattr(self, "group_item") and self.group_item:
                    self.group_item.update_bounds()
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

            # 鼠标释放后，需要重新检查悬停位置来设置正确的光标
            self.update_cursor(event.scenePos())
            event.accept()
        else:
            if self._moving:
                self._moving = False
                # 记录移动撤销
                try:
                    old_rect = getattr(self, "_undo_move_start_rect", None)
                    new_rect = self.rect()
                    if old_rect is not None and not self._rect_equals(old_rect, new_rect):
                        um = self._get_undo_manager()
                        if um:
                            def _undo():
                                self._apply_state(rect=old_rect)

                            def _redo():
                                self._apply_state(rect=new_rect)

                            um.push_action(_undo, _redo, name="move_rect")
                except Exception:
                    pass
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
        # 检查是否在旋转按钮上（仅在选中状态下）
        if self.isSelected():
            if self.contains_rotate_handle(scene_pos):
                # 旋转光标
                self.setCursor(Qt.ClosedHandCursor)
                return

            # 检查是否在调整大小的句柄上
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

    def _apply_rotation_transform(self) -> None:
        """应用旋转变换到项。"""
        rect = self.rect()
        center = QPointF(rect.x() + rect.width() / 2, rect.y() + rect.height() / 2)

        transform = QTransform()
        transform.translate(center.x(), center.y())
        transform.rotate(self.angle)
        transform.translate(-center.x(), -center.y())

        self.setTransform(transform)

    def to_dict(self) -> dict:
        """转换为字典用于JSON序列化（LabelMe shapes 条目）。"""
        rect = self.rect()
        x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()
        attrs = self.attributes.copy() if self.attributes else {}
        # LabelMe rectangle: use two points [top-left, bottom-right]
        result = {
            "label": self.label,
            "points": [[x, y], [x + w, y + h]],
            "group_id": self.group_id,
            "shape_type": "rectangle",
            "attributes": attrs,
            "flags": {},
        }
        # 如果有旋转角度，添加 angle 字段
        if self.angle != 0.0:
            result["angle"] = round(self.angle, 2)
        return result

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
        # 恢复自定义属性：优先使用 'attributes'/'attrs'，兼容 'flags'
        item.attributes = data.get("attributes", None)
        if item.attributes is None:
            item.attributes = data.get("flags", {}) or {}

        # 恢复旋转角度
        if "angle" in data:
            try:
                item.angle = float(data["angle"]) % 360.0
                item._apply_rotation_transform()
            except Exception:
                pass

        return item
