import importlib
import os
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional


@dataclass
class ModuleEntry:
    name: str
    init: Callable[[Dict[str, Any]], Any]
    infer: Callable[[str], Any]
    uninit: Callable[[], Any]
    initialized: bool = False


REGISTRY: Dict[str, ModuleEntry] = {}


def register_module(name: str):
    """装饰器：注册一个包含 Init/Infer/UnInit 的类。"""

    def decorator(obj):
        init = getattr(obj, "Init", None)
        infer = getattr(obj, "Infer", None)
        uninit = getattr(obj, "UnInit", None)
        if not callable(init) or not callable(infer) or not callable(uninit):
            raise ValueError(
                f"模块 {name} 必须提供可调用的 Init/Infer/UnInit"
            )
        REGISTRY[name] = ModuleEntry(name=name, init=init, infer=infer, uninit=uninit)
        return obj

    return decorator


def list_modules() -> List[ModuleEntry]:
    return list(REGISTRY.values())


def get_module(name: str) -> Optional[ModuleEntry]:
    return REGISTRY.get(name)


def init_module(name: str, cfg: Optional[Dict[str, Any]] = None) -> bool:
    entry = REGISTRY.get(name)
    if not entry:
        return False
    if entry.initialized:
        return True
    try:
        entry.init(cfg or {})
        entry.initialized = True
        return True
    except Exception:
        return False


def uninit_module(name: str) -> bool:
    entry = REGISTRY.get(name)
    if not entry:
        return False
    if not entry.initialized:
        return True
    try:
        entry.uninit()
        entry.initialized = False
        return True
    except Exception:
        return False


def discover_modules() -> List[str]:
    """扫描并导入 src.autolabel 下所有模块，以触发注册装饰器。"""
    imported: List[str] = []
    # 定位到 src/autolabel 路径
    utils_dir = os.path.dirname(__file__)
    pkg_dir = os.path.normpath(os.path.join(utils_dir, "..", "autolabel"))
    if not os.path.isdir(pkg_dir):
        return imported
    for fname in os.listdir(pkg_dir):
        if not fname.endswith(".py"):
            continue
        mod = os.path.splitext(fname)[0]
        if mod in {"__init__"}:
            continue
        try:
            importlib.import_module(f"src.autolabel.{mod}")
            imported.append(mod)
        except Exception:
            # 忽略导入失败的模块以不影响其他模块
            pass
    return imported
