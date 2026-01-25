from typing import Any, Dict

from src.utils.registry import register_module


@register_module("Demo")
class DemoAI:
    @staticmethod
    def init(cfg: Dict[str, Any]):
        print("[DemoAI] init called with cfg:", cfg)

    @staticmethod
    def infer(path: str, options: Dict[str, Any] | None = None):
        print(f"[DemoAI] infer on {path} with options: {options}")
        return {"ok": True, "path": path, "options": options or {}}

    @staticmethod
    def uninit():
        print("[DemoAI] uninit called")
