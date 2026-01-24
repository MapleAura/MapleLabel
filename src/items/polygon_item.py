import json
import math

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsPolygonItem,
)


class PolygonVertex(QGraphicsEllipseItem):
    """多边形顶点项"""

    def __init__(self, x, y, radius=3, parent=None):
        super().__init__(-radius, -radius, radius * 2, radius * 2, parent)
        self.setPos(x, y)
        self.setBrush(QBrush(Qt.red))
        self.setPen(QPen(Qt.black, 1))
        self.setFlag(QGraphicsEllipseItem.ItemIsMovable)
        self.setFlag(QGraphicsEllipseItem.ItemSendsGeometryChanges)
        self.setFlag(QGraphicsEllipseItem.ItemIsSelectable)
        self.radius = radius
        self.parent_polygon = parent
        self.setZValue(2)  # 顶点在最上层
        # 光标悬停在顶点上显示平移光标
        try:
            from PySide6.QtCore import Qt as _Qt

            self.setCursor(_Qt.SizeAllCursor)
        except Exception:
            pass

    def itemChange(self, change, value):
        """顶点位置变化时通知多边形更新"""
        if change == QGraphicsEllipseItem.ItemPositionChange and self.parent_polygon:
            # 通知多边形更新顶点位置
            new_pos = value
            self.parent_polygon.update_vertex_position(self, new_pos)
        return super().itemChange(change, value)


class PolygonItem(QGraphicsPolygonItem):
    """可编辑的多边形项，符合 labelme 格式协议"""

    vertex_selected = Signal(QGraphicsEllipseItem)

    def __init__(self, points=None, label="", group_id=None, flags=None):
        super().__init__()
        self.vertices = []  # 存储顶点项
        self.polygon_points = []  # 存储多边形点坐标
        self.label = label  # 多边形标签
        self.group_id = group_id  # 组ID
        # 标志字典/属性，用于存储额外属性（与 label.json 对应）
        self.flags = flags or {}
        # 统一属性名，方便外部访问
        self.attributes = self.flags
        # 形状类型
        self.shape_type = "polygon"
        self.is_closed = False  # 多边形是否已封闭
        self.vertex_radius = 3

        # 默认样式
        self.setPen(QPen(QColor(0, 255, 0), 1))  # labelme 通常用绿色
        self.setBrush(QBrush(QColor(0, 255, 0, 50)))  # 半透明绿色填充

        self.setFlag(QGraphicsPolygonItem.ItemIsMovable, False)
        self.setFlag(QGraphicsPolygonItem.ItemIsSelectable, True)
        self.setAcceptHoverEvents(True)
        self.setZValue(1)  # 多边形在中间层

        # 如果提供了点列表，直接创建多边形
        if points:
            for point in points:
                self.add_vertex(point)
            # 如果点足够多，自动封闭多边形
            if len(points) >= 3:
                self.close_polygon()

    def add_vertex(self, point):
        """添加顶点"""
        if self.is_closed:
            return None

        # 创建顶点项
        vertex = PolygonVertex(point.x(), point.y(), self.vertex_radius, self)
        vertex.setParentItem(self)
        self.vertices.append(vertex)
        self.polygon_points.append(point)

        # 更新多边形形状
        self.update_polygon_shape()

        return vertex

    def close_polygon(self):
        """封闭多边形"""
        if len(self.polygon_points) >= 3 and not self.is_closed:
            self.is_closed = True
            # 不设置整体移动标志，多边形不能整体移动
            self.update_polygon_shape()
            return True
        return False

    def update_vertex_position(self, vertex, new_pos):
        """更新顶点位置"""
        if vertex in self.vertices:
            index = self.vertices.index(vertex)
            self.polygon_points[index] = new_pos
            self.update_polygon_shape()

    def update_polygon_shape(self):
        """更新多边形形状"""
        if len(self.polygon_points) > 0:
            if self.is_closed and len(self.polygon_points) >= 3:
                # 封闭多边形：连接首尾点
                polygon = QPolygonF(self.polygon_points)
                self.setPolygon(polygon)
            else:
                # 未封闭：不设置多边形，让paint方法绘制开口形状
                self.prepareGeometryChange()
                self.update()

    def mousePressEvent(self, event):
        """鼠标按下事件"""
        if event.button() == Qt.LeftButton and self.is_closed:
            # 在选择模式下，检查是否点击了顶点
            pos = self.mapFromScene(event.scenePos())

            # 检查是否点击了顶点
            for vertex in self.vertices:
                vertex_center = vertex.pos()
                distance = math.sqrt(
                    (pos.x() - vertex_center.x()) ** 2
                    + (pos.y() - vertex_center.y()) ** 2
                )
                if distance <= self.vertex_radius + 2:  # 增加点击容差
                    # 选中顶点
                    vertex.setSelected(True)
                    self.setSelected(False)
                    event.accept()
                    return

            # 未点击顶点，可以选中整个多边形但不能移动
            self.setSelected(True)
            for vertex in self.vertices:
                vertex.setSelected(False)

        super().mousePressEvent(event)

    def paint(self, painter, option, widget=None):
        """自定义绘制"""
        painter.setPen(self.pen())
        painter.setBrush(self.brush())

        if len(self.polygon_points) > 1:
            if self.is_closed and len(self.polygon_points) >= 3:
                # 绘制封闭的多边形
                polygon = QPolygonF(self.polygon_points)
                painter.drawPolygon(polygon)
            else:
                # 绘制未封闭的多边形（开口状态）
                # 绘制顶点之间的连线
                path = QPainterPath()
                if self.polygon_points:
                    path.moveTo(self.polygon_points[0])
                    for i in range(1, len(self.polygon_points)):
                        path.lineTo(self.polygon_points[i])
                painter.drawPath(path)

                # 绘制从最后一个点到当前鼠标位置的预览线（如果有的话）
                if hasattr(self, "preview_point") and self.preview_point:
                    painter.setPen(QPen(Qt.blue, 1, Qt.DashLine))
                    if self.polygon_points:
                        painter.drawLine(self.polygon_points[-1], self.preview_point)

        # 绘制选中状态
        if self.isSelected():
            painter.setPen(QPen(Qt.red, 2, Qt.DashLine))
            painter.setBrush(Qt.NoBrush)
            rect = self.boundingRect()
            painter.drawRect(rect)

    def boundingRect(self):
        """返回边界矩形"""
        if len(self.polygon_points) == 0:
            return super().boundingRect()

        # 计算所有点的边界
        min_x = min(p.x() for p in self.polygon_points)
        min_y = min(p.y() for p in self.polygon_points)
        max_x = max(p.x() for p in self.polygon_points)
        max_y = max(p.y() for p in self.polygon_points)

        # 添加一些边距
        margin = 10
        return QRectF(
            min_x - margin,
            min_y - margin,
            max_x - min_x + 2 * margin,
            max_y - min_y + 2 * margin,
        )

    def to_dict(self):
        """
        转换为字典，符合 labelme 格式协议

        返回:
            dict: 包含多边形信息的字典，格式如下:
            {
                "label": str,  # 标签名称
                "points": list,  # [[x1, y1], [x2, y2], ...]
                "group_id": int/None,  # 分组ID
                "shape_type": "polygon",
                "flags": dict  # 额外属性
            }
        """
        return {
            "label": self.label,
            "points": [[p.x(), p.y()] for p in self.polygon_points],
            "group_id": self.group_id,
            "shape_type": "polygon",
            "flags": self.attributes.copy() if self.attributes else {},
        }

    @classmethod
    def from_dict(cls, data, scene=None):
        """
        从 labelme 格式字典创建多边形项

        参数:
            data (dict): 包含多边形信息的字典
            scene (QGraphicsScene, optional): 要添加到的场景

        返回:
            PolygonItem: 创建的多边形项
        """
        # 验证必要字段
        if "label" not in data or "points" not in data:
            raise ValueError("Invalid labelme format: missing required fields")

        # 解析点数据
        points = []
        for point in data["points"]:
            if len(point) >= 2:
                points.append(QPointF(point[0], point[1]))
            else:
                raise ValueError(f"Invalid point format: {point}")

        # 创建多边形项
        item = cls(
            points=points,
            label=data["label"],
            group_id=data.get("group_id"),
            flags=data.get("flags", {}),
        )

        # 如果点足够多且未封闭，自动封闭多边形
        if len(points) >= 3 and not item.is_closed:
            item.close_polygon()

        # 可选：添加到场景
        if scene:
            scene.addItem(item)

        # 恢复 attributes 已在构造时设置
        return item

    def to_json(self, indent=2):
        """
        转换为 JSON 字符串

        参数:
            indent (int): JSON 缩进

        返回:
            str: JSON 字符串
        """
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_json(cls, json_str, scene=None):
        """
        从 JSON 字符串创建多边形项

        参数:
            json_str (str): JSON 字符串
            scene (QGraphicsScene, optional): 要添加到的场景

        返回:
            PolygonItem: 创建的多边形项
        """
        data = json.loads(json_str)
        return cls.from_dict(data, scene)


# 示例使用
def save_polygons_to_labelme_format(
    polygons, image_path, image_data, image_height, image_width
):
    """
    将多个多边形保存为完整的 labelme 格式

    参数:
        polygons (list): PolygonItem 列表
        image_path (str): 图片路径
        image_data (str): 图片的 base64 编码数据（可选）
        image_height (int): 图片高度
        image_width (int): 图片宽度

    返回:
        dict: 完整的 labelme 格式数据
    """
    shapes = []
    for polygon in polygons:
        shapes.append(polygon.to_dict())

    labelme_data = {
        "version": "5.1.1",
        "flags": {},
        "shapes": shapes,
        "imagePath": image_path,
        "imageData": image_data,
        "imageHeight": image_height,
        "imageWidth": image_width,
    }

    return labelme_data


def load_polygons_from_labelme_format(labelme_data, scene):
    """
    从 labelme 格式数据加载多边形

    参数:
        labelme_data (dict): labelme 格式数据
        scene (QGraphicsScene): 要添加到的场景

    返回:
        list: 加载的 PolygonItem 列表
    """
    polygons = []

    if "shapes" in labelme_data:
        for shape_data in labelme_data["shapes"]:
            if shape_data.get("shape_type") == "polygon":
                polygon = PolygonItem.from_dict(shape_data, scene)
                polygons.append(polygon)

    return polygons
