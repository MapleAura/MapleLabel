"""AutoLabel 模块包。

用于承载所有可注册的 AI 模块，每个模块需实现（大小写均可）：
- init(cfg: dict): 加载/初始化
- infer(path: str, options: dict | None = None): 推理
- uninit(): 卸载/释放

并使用注册器提供的装饰器进行注册。
"""
from .demo import DemoAI
from .face_landmark import FaceLandmark

__all__ = ["DemoAI", "FaceLandmark"]