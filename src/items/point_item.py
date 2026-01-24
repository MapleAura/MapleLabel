from PySide6.QtCore import QPointF, Qt, QRectF
from PySide6.QtGui import QColor, QPen, QBrush, QPainter, QPainterPath
from PySide6.QtWidgets import QGraphicsItem

class PointItem(QGraphicsItem):
    """可编辑的点标注"""
    
    def __init__(self, pos=None, radius=3, label="point", group_id=None, parent=None):
        super().__init__(parent)
        
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        self.setFlag(QGraphicsItem.ItemIsFocusable, True)
        
        # 点样式
        self.radius = radius
        self.normal_color = QColor(255, 0, 0, 200)
        self.selected_color = QColor(255, 255, 0, 200)
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
        self.shape_type = 'point'
        
        # 所属分组
        self.group_id = group_id
        self.group_item = None
        
        # 用于JSON序列化的唯一ID
        self.item_id = id(self)
        # 可编辑属性字典，序列化到 'flags'
        self.attributes = {}
        
        # 设置Z值，确保点在最上层
        self.setZValue(10)
    
    def boundingRect(self):
        """返回边界矩形"""
        return QRectF(-self.radius, -self.radius, 2*self.radius, 2*self.radius)
    
    def shape(self):
        """返回精确的形状用于碰撞检测"""
        path = QPainterPath()
        path.addEllipse(-self.radius, -self.radius, 2*self.radius, 2*self.radius)
        return path
    
    def paint(self, painter, option, widget=None):
        """绘制点"""
        if self.isSelected():
            self.color = self.selected_color
        else:
            self.color = self.normal_color
        
        painter.setBrush(QBrush(self.color))
        painter.setPen(QPen(Qt.black, 1))
        painter.drawEllipse(-self.radius, -self.radius, 2*self.radius, 2*self.radius)
    
    def itemChange(self, change, value):
        """处理项变化"""
        if change in [QGraphicsItem.ItemPositionHasChanged, 
                     QGraphicsItem.ItemTransformHasChanged]:
            # 如果属于分组，更新分组框
            if hasattr(self, 'group_item') and self.group_item:
                self.group_item.update_bounds()
                
        return super().itemChange(change, value)
    
    def to_dict(self):
        """转换为字典用于JSON序列化"""
        return {
            'label': self.label,
            'points': [[self.pos().x(), self.pos().y()]],
            'group_id': self.group_id,
            'shape_type': 'point',
            'flags': self.attributes.copy() if self.attributes else {}
        }
    
    @classmethod
    def from_dict(cls, data, scene):
        """从字典创建点项"""
        points = data['points']
        if len(points) != 1:
            return None
        
        pos = QPointF(points[0][0], points[0][1])
        radius = 3
        label = data.get('label', 'point')
        item = cls(pos, radius, label, data.get('group_id'))
        # 恢复自定义属性
        item.attributes = data.get('flags', {}) or {}
        
        return item