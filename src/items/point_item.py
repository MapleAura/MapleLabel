"""点标注项模块。

提供 `PointItem`，这是一个可移动/可选中的点标注项，支持序列化为 LabelMe 格式。
所有注释与 docstring 使用中文，便于本地开发团队阅读。
"""

from typing import Any, Optional
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPainterPath, QPen
from PySide6.QtWidgets import QGraphicsItem


class PointItem(QGraphicsItem):
    """可编辑的点标注。

    属性:
        label: 标签名称
        attributes: 存储自定义属性（序列化到 flags）
    """

    def __init__(
        self,
        pos: Optional[QPointF] = None,
        radius: int = 3,
        label: str = "point",
        group_id: Optional[int] = None,
        parent: Optional[QGraphicsItem] = None,
    ) -> None:
        super().__init__(parent)

        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        self.setFlag(QGraphicsItem.ItemIsFocusable, True)

        # 点样式
        self.radius = radius
        self.default_normal_color = QColor(255, 0, 0, 200)
        self.default_selected_color = QColor(255, 255, 0, 200)
        self.normal_color = QColor(self.default_normal_color)
        self.selected_color = QColor(self.default_selected_color)
        self.color = self.normal_color

        # 当光标移到点上时使用平移/移动光标
        try:
            from PySide6.QtCore import Qt as _Qt

            self.setCursor(_Qt.SizeAllCursor)
        except Exception:
            pass

        # 设置位置
        if pos:
            self.setPos(pos)
        else:
            self.setPos(QPointF(0, 0))

        # 标注标签
        self.label = label
        # 形状类型
        self.shape_type = "point"

        # 所属分组
        self.group_id = group_id
        self.group_item = None

        # 用于JSON序列化的唯一ID
        self.item_id = id(self)
        # 可编辑属性字典，序列化到 'flags'
        self.attributes = {}

        # 设置Z值，确保点在最上层
        self.setZValue(10)

    def apply_group_color(self, color: QColor) -> None:
        """Apply a group color to the point and refresh its appearance."""
        group_color = QColor(color)
        group_color.setAlpha(200)
        self.normal_color = group_color
        self.selected_color = QColor(group_color)
        self.color = self.selected_color if self.isSelected() else self.normal_color
        self.update()

    def reset_color(self) -> None:
        """Restore default colors after ungrouping."""
        self.normal_color = QColor(self.default_normal_color)
        self.selected_color = QColor(self.default_selected_color)
        self.color = self.selected_color if self.isSelected() else self.normal_color
        self.update()

    def boundingRect(self) -> QRectF:
        """返回边界矩形。"""
        return QRectF(-self.radius, -self.radius, 2 * self.radius, 2 * self.radius)

    def shape(self) -> QPainterPath:
        """返回精确的形状用于碰撞检测。"""
        path = QPainterPath()
        path.addEllipse(-self.radius, -self.radius, 2 * self.radius, 2 * self.radius)
        return path

    def paint(self, painter, option, widget=None) -> None:
        """绘制点。"""
        if self.isSelected():
            self.color = self.selected_color
        else:
            self.color = self.normal_color

        painter.setBrush(QBrush(self.color))
        painter.setPen(QPen(Qt.black, 1))
        painter.drawEllipse(-self.radius, -self.radius, 2 * self.radius, 2 * self.radius)

    def itemChange(self, change: Any, value: Any) -> Any:
        """处理项变化。

        当位置或变换发生变化时，如果所在分组存在则更新分组边界。
        """
        if change in [
            QGraphicsItem.ItemPositionHasChanged,
            QGraphicsItem.ItemTransformHasChanged,
        ]:
            # 如果属于分组，更新分组框
            if hasattr(self, "group_item") and self.group_item:
                self.group_item.update_bounds()

        return super().itemChange(change, value)

    def to_dict(self) -> dict:
        """转换为字典用于 JSON 序列化（LabelMe shapes 条目）。"""
        attrs = self.attributes.copy() if self.attributes else {}
        return {
            "label": self.label,
            "points": [[self.pos().x(), self.pos().y()]],
            "group_id": self.group_id,
            "shape_type": "point",
            "attributes": attrs,
            "attrs": attrs,
            "flags": {},
        }

    @classmethod
    def from_dict(cls, data: dict, scene: Optional[Any] = None) -> Optional["PointItem"]:
        """从字典创建点项。

        返回 `PointItem` 实例或在数据无效时返回 None。
        """
        points = data.get("points", [])
        if len(points) != 1:
            return None

        pos = QPointF(points[0][0], points[0][1])
        radius = 3
        label = data.get("label", "point")
        item = cls(pos, radius, label, data.get("group_id"))
        # 恢复自定义属性
        item.attributes = data.get("attributes", None)
        if item.attributes is None:
            item.attributes = data.get("attrs", None)
        if item.attributes is None:
            item.attributes = data.get("flags", {}) or {}

        return item
