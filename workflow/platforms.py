"""各平台图文/视频发布适配器（声明式 + 可替换实现）。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from workflow.models import ArticleBundle, PublishResult


class TextImagePublisher(ABC):
    """图文发布抽象基类。"""

    name: str

    @abstractmethod
    def publish(self, bundle: ArticleBundle) -> PublishResult:
        """将图文发布到对应平台。"""


class VideoPublisher(ABC):
    """短视频发布抽象基类。"""

    name: str

    @abstractmethod
    def publish(self, video_path: Path, title: str, description: str) -> PublishResult:
        """上传视频及元数据。"""


class StubPublisher(TextImagePublisher):
    """占位：记录意图，真实发布需对接官方 API 或浏览器自动化（如 Playwright）。"""

    def __init__(self, platform_id: str) -> None:
        self.name = platform_id

    def publish(self, bundle: ArticleBundle) -> PublishResult:
        return PublishResult(
            platform=self.name,
            ok=True,
            message="占位：未调用真实 API。请实现具体 Publisher 或接入 social-push / MultiPost 等工具。",
            external_id=None,
        )


class StubVideoPublisher(VideoPublisher):
    """占位视频上传。"""

    def __init__(self, platform_id: str) -> None:
        self.name = platform_id

    def publish(self, video_path: Path, title: str, description: str) -> PublishResult:
        _ = description
        return PublishResult(
            platform=self.name,
            ok=video_path.exists(),
            message=f"占位：可将 {video_path.name} 上传至 {self.name}（需平台凭证与 SDK）",
            external_id=None,
        )


# 平台标识与中文说明（文档/日志用）
PLATFORM_LABELS: dict[str, str] = {
    "xiaohongshu": "小红书",
    "zhihu": "知乎",
    "wechat_mp": "微信公众号",
    "weibo": "微博",
    "douyin": "抖音",
    "channels": "微信视频号",
    "bilibili": "哔哩哔哩",
    "kuaishou": "快手",
}


def build_text_publishers(platform_ids: list[str]) -> list[TextImagePublisher]:
    return [StubPublisher(pid) for pid in platform_ids]


def build_video_publishers(platform_ids: list[str]) -> list[VideoPublisher]:
    return [StubVideoPublisher(pid) for pid in platform_ids]
