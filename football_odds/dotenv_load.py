"""
从项目根目录加载 .env 到环境变量（不覆盖已存在的变量）。
依赖 python-dotenv；未安装时静默跳过。
"""

from __future__ import annotations

import os
from pathlib import Path


def load_dotenv_from_root(root: Path | None = None) -> bool:
    """
    root 为仓库根目录（含 .env 的目录）。
    返回是否成功执行 load_dotenv（含文件不存在也算调用了）。
    """
    if root is None:
        root = Path(__file__).resolve().parent.parent
    path = root / ".env"
    if not path.is_file():
        return False
    try:
        from dotenv import load_dotenv
    except ImportError:
        return False
    load_dotenv(path, override=False)
    return True


def ensure_loaded() -> None:
    """幂等：供 Web/CLI 启动时调用一次。"""
    flag = "_MOLTBOT_DOTENV_LOADED"
    if os.environ.get(flag) == "1":
        return
    load_dotenv_from_root()
    os.environ[flag] = "1"
