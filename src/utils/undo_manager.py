from typing import Callable, List


class UndoRedoManager:
    """简单的撤销/重做管理器。

    存储可执行的 undo/redo 回调，适用于 QGraphicsItems 的增删。
    """

    def __init__(self, canvas, max_stack: int = 200):
        self.canvas = canvas
        self.undo_stack: List[dict] = []
        self.redo_stack: List[dict] = []
        self.max_stack = max_stack

    def push_action(self, undo: Callable, redo: Callable, name: str = ""):
        # 记录当前画布对应的图片路径，以便在撤销/重做时恢复到正确的图片上下文
        image_path = None
        try:
            image_path = getattr(self.canvas, "current_image_path", None)
        except Exception:
            image_path = None

        self.undo_stack.append({"undo": undo, "redo": redo, "name": name, "image": image_path})
        if len(self.undo_stack) > self.max_stack:
            self.undo_stack.pop(0)
        self.redo_stack.clear()

    def undo(self):
        if not self.undo_stack:
            return False
        action = self.undo_stack.pop()
        try:
            # 如果动作属于其它图片，先切换到对应图片
            try:
                self._ensure_action_image(action)
            except Exception:
                pass

            action["undo"]()
            self.redo_stack.append(action)
            # 标记为已修改
            try:
                self.canvas.set_modified(True)
            except Exception:
                pass
            return True
        except Exception:
            return False

    def redo(self):
        if not self.redo_stack:
            return False
        action = self.redo_stack.pop()
        try:
            # 如果动作属于其它图片，先切换到对应图片
            try:
                self._ensure_action_image(action)
            except Exception:
                pass

            action["redo"]()
            self.undo_stack.append(action)
            try:
                self.canvas.set_modified(True)
            except Exception:
                pass
            return True
        except Exception:
            return False

    def _add_item_to_scene_and_collections(self, item):
        if item not in self.canvas.scene.items():
            try:
                self.canvas.scene.addItem(item)
            except Exception:
                pass
        # 添加到对应列表
        from ..items import ResizableRectItem, PointItem, PolygonItem, GroupItem

        try:
            if isinstance(item, ResizableRectItem):
                if item not in self.canvas.rect_items:
                    self.canvas.rect_items.append(item)
            elif isinstance(item, PointItem):
                if item not in self.canvas.point_items:
                    self.canvas.point_items.append(item)
            elif isinstance(item, PolygonItem):
                if item not in self.canvas.polygon_items:
                    self.canvas.polygon_items.append(item)
            elif isinstance(item, GroupItem):
                # group handling: try to restore groups dict
                gid = getattr(item, "group_id", None)
                if gid is not None and gid not in self.canvas.groups:
                    self.canvas.groups[gid] = {"items": getattr(item, "group_items", []), "group_item": item}
        except Exception:
            pass

    def _remove_item_from_scene_and_collections(self, item):
        from ..items import ResizableRectItem, PointItem, PolygonItem, GroupItem

        try:
            if isinstance(item, ResizableRectItem) and item in self.canvas.rect_items:
                try:
                    self.canvas.rect_items.remove(item)
                except Exception:
                    pass
            elif isinstance(item, PointItem) and item in self.canvas.point_items:
                try:
                    self.canvas.point_items.remove(item)
                except Exception:
                    pass
            elif isinstance(item, PolygonItem) and item in self.canvas.polygon_items:
                try:
                    self.canvas.polygon_items.remove(item)
                except Exception:
                    pass
            elif isinstance(item, GroupItem):
                gid = getattr(item, "group_id", None)
                if gid in self.canvas.groups:
                    try:
                        del self.canvas.groups[gid]
                    except Exception:
                        pass
        except Exception:
            pass

        try:
            if item in self.canvas.scene.items():
                self.canvas.scene.removeItem(item)
        except Exception:
            pass

    def _ensure_action_image(self, action: dict):
        """若动作属于不同图片，尝试切换到动作记录的图片路径。"""
        target = action.get("image")
        try:
            current = getattr(self.canvas, "current_image_path", None)
        except Exception:
            current = None

        if target and target != current:
            try:
                win = None
                try:
                    win = self.canvas.window()
                except Exception:
                    win = None

                if win is not None and hasattr(win, "load_image_by_path"):
                    try:
                        win.load_image_by_path(target)
                        return True
                    except Exception:
                        pass

                # 兜底直接让 canvas 加载图片
                try:
                    self.canvas.set_image(target)
                    return True
                except Exception:
                    pass
            except Exception:
                pass
        return False

    def push_create(self, item, name: str = "create"):
        def undo():
            self._remove_item_from_scene_and_collections(item)

        def redo():
            self._add_item_to_scene_and_collections(item)

        self.push_action(undo, redo, name)

    def push_and_execute_delete(self, items: List, name: str = "delete"):
        # capture items
        captured = list(items)

        def do_remove():
            for it in captured:
                self._remove_item_from_scene_and_collections(it)

        def undo_add():
            for it in captured:
                self._add_item_to_scene_and_collections(it)

        # perform removal now
        do_remove()
        self.push_action(undo_add, do_remove, name)
