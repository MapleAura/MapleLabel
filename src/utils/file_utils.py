import os
import json
import base64
import shutil

def save_temp_annotations(annotation_view, temp_dir=None):
    """保存标注到临时文件"""
    if not annotation_view.current_image_path:
        return False
    
    # 获取临时目录
    if not temp_dir:
        temp_dir = os.path.join(os.path.expanduser("~"), ".maplabel_temp")
    
    # 确保临时目录存在
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir, exist_ok=True)
    
    # 生成临时文件名
    image_name = os.path.basename(annotation_view.current_image_path)
    temp_name = f"temp_{image_name}.json"
    temp_path = os.path.join(temp_dir, temp_name)
    
    return annotation_view.save_annotations_to_json(temp_path, include_image_data=False)

def load_temp_annotations(annotation_view, temp_dir=None):
    """从临时文件加载标注"""
    if not annotation_view.current_image_path:
        return False
    
    # 获取临时目录
    if not temp_dir:
        temp_dir = os.path.join(os.path.expanduser("~"), ".maplabel_temp")
    
    # 检查临时文件是否存在
    image_name = os.path.basename(annotation_view.current_image_path)
    temp_name = f"temp_{image_name}.json"
    temp_path = os.path.join(temp_dir, temp_name)
    
    if not os.path.exists(temp_path):
        return False
    
    return annotation_view.load_annotations_from_json(temp_path)

def clear_temp_files(temp_dir=None):
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