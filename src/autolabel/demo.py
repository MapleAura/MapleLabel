from typing import Any, Dict

from src.utils.registry import register_module


@register_module("Demo")
class DemoAI:
    @staticmethod
    def Init(cfg: Dict[str, Any]):
        print("[DemoAI] Init called with cfg:", cfg)

    @staticmethod
    def Infer(path: str):
        print(f"[DemoAI] Infer on {path}")
        return {"ok": True, "path": path}

    @staticmethod
    def UnInit():
        print("[DemoAI] UnInit called")
