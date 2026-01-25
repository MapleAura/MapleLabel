from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPen
from PySide6.QtWidgets import QGraphicsRectItem


class GroupItem(QGraphicsRectItem):
    """分组框，用于显示一组元素的边界"""

    def __init__(self, rect=None, parent=None):
        super().__init__(parent)
        if rect:
            self.setRect(rect)

        # 分组框样式 - 默认隐藏，颜色交给分组内元素呈现
        self.group_pen = QPen(Qt.transparent, 0)
        self.selected_pen = QPen(Qt.transparent, 0)
        self.setPen(self.group_pen)
        self.setBrush(QBrush(Qt.NoBrush))

        # 允许选择（用于取消分组），但不允许移动
        self.setFlag(QGraphicsRectItem.ItemIsSelectable, False)
        self.setFlag(QGraphicsRectItem.ItemIsMovable, False)
        self.setFlag(QGraphicsRectItem.ItemSendsGeometryChanges, True)

        # 存储组内元素
        self.group_items = []
        self.group_id = None

        # 设置Z值，确保分组框在最上层显示
        self.setZValue(1000)

    def update_bounds(self):
        """根据组内元素更新分组框边界 - 计算最小外接矩形"""
        if not self.group_items:
            return

        # 计算所有元素的边界
        min_x = float("inf")
        min_y = float("inf")
        max_x = float("-inf")
        max_y = float("-inf")

        for item in self.group_items:
            if hasattr(item, "sceneBoundingRect"):
                bounds = item.sceneBoundingRect()
            else:
                bounds = item.boundingRect()
                bounds = item.mapRectToScene(bounds)

            min_x = min(min_x, bounds.left())
            min_y = min(min_y, bounds.top())
            max_x = max(max_x, bounds.right())
            max_y = max(max_y, bounds.bottom())

        if min_x == float("inf"):
            return

        # 添加边距
        margin = 5
        bounds = QRectF(
            min_x - margin,
            min_y - margin,
            max_x - min_x + 2 * margin,
            max_y - min_y + 2 * margin,
        )
        self.setRect(bounds)
        self.setPos(0, 0)  # 分组框在场景坐标中

        # 强制更新显示
        self.update()

    def paint(self, painter, option, widget=None):
        """绘制分组框"""
        if self.isSelected():
            painter.setPen(self.selected_pen)
        else:
            painter.setPen(self.group_pen)
        painter.setBrush(self.brush())
        painter.drawRect(self.rect())
