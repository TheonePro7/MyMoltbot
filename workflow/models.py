"""工作流领域模型。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class ImageSlide(BaseModel):
    """单张图文页：配图路径与配文。"""

    image_path: Path
    caption: str = ""
    title: str = ""


class ArticleBundle(BaseModel):
    """一篇可多端分发的图文包。"""

    title: str
    body_markdown: str
    tags: list[str] = Field(default_factory=list)
    slides: list[ImageSlide] = Field(default_factory=list)
    # 各平台定制字段（标题长度、话题等），由适配器读取
    platform_extras: dict[str, Any] = Field(default_factory=dict)


class PublishResult(BaseModel):
    """单次发布结果。"""

    platform: str
    ok: bool
    message: str = ""
    external_id: str | None = None


class WorkflowRunSummary(BaseModel):
    """一次完整流水线摘要。"""

    article_title: str
    video_path: Path | None = None
    text_results: list[PublishResult] = Field(default_factory=list)
    video_results: list[PublishResult] = Field(default_factory=list)
