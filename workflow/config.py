"""加载 YAML 工作流配置。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class WorkflowConfig(BaseModel):
    """与 workflows/*.yaml 对应的结构。"""

    name: str = "default"
    text_image_platforms: list[str] = Field(default_factory=list)
    video_platforms: list[str] = Field(default_factory=list)
    slide_duration_seconds: float = 3.0
    video_width: int = 1080
    video_height: int = 1920


def load_workflow_config(path: Path) -> WorkflowConfig:
    raw: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return WorkflowConfig.model_validate(raw)
