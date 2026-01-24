import os
import json
import base64
import shutil
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import (QPainter, QPen, QBrush, QColor, QPixmap, 
                          QWheelEvent, QMouseEvent, QKeyEvent, QTransform)
from PySide6.QtWidgets import (QGraphicsView, QGraphicsScene, QGraphicsPixmapItem,
                              QMessageBox)

from ..items import GroupItem, ResizableRectItem, PointItem, PolygonItem

class AnnotationView(QGraphicsView):
    """标注视图，支持缩放和标注绘制"""
    
    def __init__(self, parent=None):
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

 
        
    def set_image(self, image_path):
        """设置显示的图像"""
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
    
    def load_annotations_from_json(self, json_path):
        """从JSON文件加载标注（LabelMe格式）"""
        if not os.path.exists(json_path):
            return False
        
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 清除当前标注
            self.clear_annotations()
            
            # 创建分组映射
            group_items_map = {}
            
            # 加载所有形状
            for shape_data in data.get('shapes', []):
                shape_type = shape_data.get('shape_type', '')
                label = shape_data.get('label', '')
                group_id = shape_data.get('group_id')
                
                item = None
                if shape_type == 'rectangle':
                    item = ResizableRectItem.from_dict(shape_data, self.scene)
                elif shape_type == 'point':
                    item = PointItem.from_dict(shape_data, self.scene)
                elif shape_type == 'polygon':
                    item = PolygonItem.from_dict(shape_data, self.scene)
                
                if item:
                    self.scene.addItem(item)
                    
                    # 添加到对应的列表
                    if shape_type == 'rectangle':
                        self.rect_items.append(item)
                    elif shape_type == 'point':
                        self.point_items.append(item)
                    elif shape_type == 'polygon':
                        self.polygon_items.append(item)
                    
                    # 记录分组信息
                    if group_id is not None:
                        if group_id not in group_items_map:
                            group_items_map[group_id] = []
                        group_items_map[group_id].append(item)
                        item.group_id = group_id
            
            # 重新创建分组
            for group_id, items in group_items_map.items():
                if len(items) >= 2:
                    self._create_group_from_items(group_id, items)
            
            # 更新下一个分组ID
            groups_in_data = [s.get('group_id', 0) for s in data.get('shapes', []) if s.get('group_id')]
            if groups_in_data:
                max_id = max(groups_in_data)
                self.next_group_id = max_id + 1
            
            return True
            
        except Exception as e:
            print(f"加载LabelMe JSON时出错: {e}")
            return False
    
    def _create_group_from_items(self, group_id, items):
        """从项目列表创建分组"""
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
        self.groups[group_id] = {
            'items': items,
            'group_item': group_item
        }
        
        return group_item
    
    def save_annotations_to_json(self, json_path, include_image_data=False):
        """保存标注到JSON文件（LabelMe格式）"""
        if not self.current_image_path:
            return False
        
        # 构建LabelMe格式的标注数据
        labelme_data = {
            'version': '4.5.6',
            'flags': {},
            'shapes': [],
            'imagePath': os.path.basename(self.current_image_path),
            'imageData': None,
            'imageHeight': self.image_height,
            'imageWidth': self.image_width
        }
        
        # 保存矩形
        for rect in self.rect_items:
            shape_data = rect.to_dict()
            if shape_data:
                labelme_data['shapes'].append(shape_data)
        
        # 保存点
        for point in self.point_items:
            shape_data = point.to_dict()
            if shape_data:
                labelme_data['shapes'].append(shape_data)
        
        # 保存多边形
        for polygon in self.polygon_items:
            shape_data = polygon.to_dict()
            if shape_data:
                labelme_data['shapes'].append(shape_data)
        
        # 可选：包含图片数据
        if include_image_data:
            try:
                with open(self.current_image_path, 'rb') as f:
                    image_data = f.read()
                labelme_data['imageData'] = base64.b64encode(image_data).decode('utf-8')
            except Exception as e:
                print(f"无法读取图片数据: {e}")
        
        try:
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(labelme_data, f, indent=2, ensure_ascii=False)
            
            # 保存成功后，清除修改标志
            self.modified = False
            return True
        except Exception as e:
            print(f"保存LabelMe JSON时出错: {e}")
            return False
    
    def save_annotations_to_temp(self, temp_dir=None):
        """保存标注到临时文件"""
        if not self.current_image_path:
            return False
        
        # 获取临时目录
        if not temp_dir:
            temp_dir = os.path.join(os.path.expanduser("~"), ".maplabel_temp")
        
        # 确保临时目录存在
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir, exist_ok=True)
        
        # 生成临时文件名
        image_name = os.path.basename(self.current_image_path)
        temp_name = f"temp_{image_name}.json"
        temp_path = os.path.join(temp_dir, temp_name)
        
        return self.save_annotations_to_json(temp_path, include_image_data=False)
    
    def load_annotations_from_temp(self, temp_dir=None):
        """从临时文件加载标注"""
        if not self.current_image_path:
            return False
        
        # 获取临时目录
        if not temp_dir:
            temp_dir = os.path.join(os.path.expanduser("~"), ".maplabel_temp")
        
        # 检查临时文件是否存在
        image_name = os.path.basename(self.current_image_path)
        temp_name = f"temp_{image_name}.json"
        temp_path = os.path.join(temp_dir, temp_name)
        
        if not os.path.exists(temp_path):
            return False
        
        return self.load_annotations_from_json(temp_path)
    
    def has_unsaved_changes(self):
        """检查是否有未保存的更改"""
        return self.modified
    
    def set_modified(self, modified=True):
        """设置修改标志"""
        self.modified = modified
        return self.modified
    
    def set_tool(self, tool):
        """设置当前工具"""
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
            self.current_rect = ResizableRectItem(QRectF(self.start_pos, self.start_pos), label="rect")
            self.scene.addItem(self.current_rect)
            
        elif self.current_tool == "point" and event.button() == Qt.LeftButton:
            # 创建点
            point_item = PointItem(scene_pos, label="point")
            self.scene.addItem(point_item)
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
                if hasattr(self.current_polygon, 'preview_point'):
                    self.current_polygon.preview_point = scene_pos
                self.current_polygon.update()
        else:
            super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        """处理鼠标双击事件"""
        if self.current_tool == "polygon" and event.button() == Qt.LeftButton:
            if self.drawing_polygon and self.current_polygon and  self.current_polygon.close_polygon():
                # 封闭多边形
                if len(self.current_polygon.polygon_points) >= 3:
                    if hasattr(self.current_polygon, 'preview_point'):
                        self.current_polygon.preview_point = None
                    self.current_polygon.update()
                    if hasattr(self.current_polygon, 'preview_point'):
                        self.current_polygon.preview_point = None
                    self.current_polygon.update()
                    self.polygon_items.append(self.current_polygon)
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
            if not hasattr(self.current_polygon, 'preview_point'):
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
            if abs(end_pos.x() - self.start_pos.x()) < 10 or abs(end_pos.y() - self.start_pos.y()) < 10:
                self.scene.removeItem(self.current_rect)
            else:
                new_rect = self.current_rect
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
            if hasattr(item, 'group_id') and item.group_id is not None:
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
        group_item = self.groups[group_id]['group_item']
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
        if not hasattr(item, 'group_id') or item.group_id is None:
            return
        
        group_id = item.group_id
        if group_id in self.groups:
            group = self.groups[group_id]
            
            # 从分组中移除元素
            if item in group['items']:
                group['items'].remove(item)
                item.group_id = None
                item.group_item = None
                
                # 如果分组中还有元素，更新分组框
                if group['items']:
                    group['group_item'].group_items = group['items']
                    group['group_item'].update_bounds()
                else:
                    # 分组为空，删除分组框
                    self.remove_group(group['group_item'])
    
    def remove_group(self, group_item):
        """删除整个分组"""
        if not hasattr(group_item, 'group_id') or group_item.group_id is None:
            return
        
        group_id = group_item.group_id
        if group_id in self.groups:
            group = self.groups[group_id]
            
            # 移除所有元素的分组信息
            for item in group['items']:
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
            if group['group_item'] in self.scene.items():
                self.scene.removeItem(group['group_item'])
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