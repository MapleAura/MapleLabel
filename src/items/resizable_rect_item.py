from PySide6.QtCore import QRectF, Qt, QPointF
from PySide6.QtGui import QColor, QPen, QBrush, QPainter, QPainterPath
from PySide6.QtWidgets import QGraphicsRectItem


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
        
        # 所属分组
        self.group_id = group_id
        self.group_item = None
        
        # 用于JSON序列化的唯一ID
        self.item_id = id(self)
        
        # 调整大小的手柄设置
        self.handle_size = 6
        self.handles = {}
        
        # 只保留左上和右下两个句柄
        self.handle_positions = [
            (0, 0, "top_left"), 
            (1, 1, "bottom_right")
        ]
        
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
    
    def update_handles(self):
        """更新手柄位置 - 将手柄放在矩形边缘上"""
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
    
    def itemChange(self, change, value):
        """处理项变化"""
        if change in [QGraphicsRectItem.ItemPositionHasChanged, 
                     QGraphicsRectItem.ItemTransformHasChanged]:
            # 如果属于分组，更新分组框
            if hasattr(self, 'group_item') and self.group_item:
                self.group_item.update_bounds()
            self.update_handles()
            
        return super().itemChange(change, value)
    
    def paint(self, painter, option, widget=None):
        """绘制矩形"""
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
    
    def contains_handle(self, pos):
        """检查是否点击到手柄 - 修复坐标转换问题"""
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
                handle_scene_rect.height() + 20
            )
            
            # 检查点击位置是否在热区内
            if hotspot_rect.contains(pos):
                return handle_pos
        return None
    
    def boundingRect(self):
        """重写边界矩形，包含所有手柄的可见区域"""
        rect = super().boundingRect()
        
        # 如果被选中，扩展边界以包含所有手柄
        if self.isSelected():
            for handle in self.handles.values():
                if handle.isVisible():
                    handle_rect = handle.mapRectToParent(handle.rect())
                    rect = rect.united(handle_rect)
        
        return rect
    
    def shape(self):
        """重写形状，确保点击检测包含所有手柄区域"""
        path = super().shape()
        
        # 如果被选中，添加所有手柄的形状
        if self.isSelected():
            for handle in self.handles.values():
                if handle.isVisible():
                    handle_path = QPainterPath()
                    handle_path.addRect(handle.mapRectToParent(handle.rect()))
                    path = path.united(handle_path)
        
        return path
    
    def mousePressEvent(self, event):
        """处理鼠标按下事件"""
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
        
        self.resizing = False
        # 当在矩形内部按下鼠标时，设置为SizeAllCursor（四向箭头，表示移动）
        self.setCursor(Qt.SizeAllCursor)
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        """处理鼠标移动事件 - 修复坐标转换问题"""
        if self.resizing:
            # 使用场景坐标计算偏移
            current_scene_pos = event.scenePos()
            dx = current_scene_pos.x() - self.resize_start_scene_pos.x()
            dy = current_scene_pos.y() - self.resize_start_scene_pos.y()
            
            # 考虑项变换的影响
            if not self.transform().isIdentity():
                # 获取相对于项的局部偏移
                local_offset = self.mapFromScene(current_scene_pos) - self.mapFromScene(self.resize_start_scene_pos)
                dx = local_offset.x()
                dy = local_offset.y()
            
            rect = self.resize_start_rect
            
            if self.resize_pos == "top_left":
                # 左上角调整：同时改变位置和大小
                new_rect = QRectF(
                    rect.left() + dx, 
                    rect.top() + dy, 
                    rect.width() - dx, 
                    rect.height() - dy
                )
            elif self.resize_pos == "bottom_right":
                # 右下角调整：只改变大小
                new_rect = QRectF(
                    rect.left(), 
                    rect.top(), 
                    rect.width() + dx, 
                    rect.height() + dy
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
                if hasattr(self, 'group_item') and self.group_item:
                    self.group_item.update_bounds()
                
                # 通知视图更新
                self.prepareGeometryChange()
            
            event.accept()
        else:
            super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event):
        """处理鼠标释放事件"""
        if self.resizing:
            self.resizing = False
            # 鼠标释放后，需要重新检查悬停位置来设置正确的光标
            self.update_cursor(event.scenePos())
            event.accept()
        else:
            super().mouseReleaseEvent(event)
    
    def update_cursor(self, scene_pos):
        """根据鼠标位置更新光标"""
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
    
    def hoverMoveEvent(self, event):
        """处理悬停移动事件，更新光标"""
        # 更新光标基于当前位置
        self.update_cursor(event.scenePos())
        super().hoverMoveEvent(event)
    
    def hoverEnterEvent(self, event):
        """处理悬停进入事件"""
        # 当鼠标进入矩形区域时，更新光标
        self.update_cursor(event.scenePos())
        super().hoverEnterEvent(event)
    
    def hoverLeaveEvent(self, event):
        """处理悬离开事件"""
        # 当鼠标离开矩形区域时，恢复为普通箭头光标
        self.setCursor(Qt.ArrowCursor)
        super().hoverLeaveEvent(event)
    
    def to_dict(self):
        """转换为字典用于JSON序列化"""
        # LabelMe格式：矩形用四个点表示
        rect = self.rect()
        x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()
        
        return {
            'label': self.label,
            'points': [
                [x, y],          # 左上
                [x + w, y],      # 右上
                [x + w, y + h],  # 右下
                [x, y + h]       # 左下
            ],
            'group_id': self.group_id,
            'shape_type': 'rectangle',
            'flags': {}
        }
    
    @classmethod
    def from_dict(cls, data, scene):
        """从字典创建矩形项"""
        # LabelMe格式：矩形用四个点表示
        points = data['points']
        if len(points) != 4:
            return None
        
        # 计算最小包围矩形
        x_values = [p[0] for p in points]
        y_values = [p[1] for p in points]
        min_x, max_x = min(x_values), max(x_values)
        min_y, max_y = min(y_values), max(y_values)
        
        rect = QRectF(min_x, min_y, max_x - min_x, max_y - min_y)
        label = data.get('label', 'rect')
        item = cls(rect, label, data.get('group_id'))
        
        return item