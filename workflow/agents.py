"""图文生成智能体（可接 LLM；无密钥时使用占位内容）。"""

from __future__ import annotations

import os
from pathlib import Path

from workflow.models import ArticleBundle, ImageSlide


def _placeholder_bundle(topic: str, output_dir: Path) -> ArticleBundle:
    """无 API 时的占位图文，便于联调流水线。"""
    output_dir.mkdir(parents=True, exist_ok=True)
    # 使用 Pillow 在 pipeline 里也可生成；此处仅返回结构，图片由 ensure_placeholder_image 创建
    img = output_dir / "slide_01.png"
    title = f"{topic}｜智能体草稿"
    body = (
        f"# {title}\n\n"
        "这是一段由工作流生成的示例正文。配置 OPENAI_API_KEY 或 ANTHROPIC_API_KEY 后，"
        "可将 `generate_article_bundle` 接至真实模型。\n\n"
        "## 要点\n\n"
        "- 多平台适配在 `workflow/platforms.py`\n"
        "- 滑动视频在 `workflow/video.py`\n"
    )
    return ArticleBundle(
        title=title,
        body_markdown=body,
        tags=["智能体", "多平台"],
        slides=[
            ImageSlide(image_path=img, title="封面", caption="第一张滑动页说明"),
            ImageSlide(image_path=output_dir / "slide_02.png", title="内页", caption="第二张滑动页说明"),
        ],
        platform_extras={},
    )


def generate_article_bundle(topic: str, output_dir: Path) -> ArticleBundle:
    """
    根据主题生成图文包。
    若环境变量中存在 OPENAI_API_KEY，可扩展为调用 OpenAI；当前保留占位实现以不破坏离线环境。
    """
    _ = os.environ.get("OPENAI_API_KEY")  # 预留：接入时读取
    return _placeholder_bundle(topic, output_dir)
