"""端到端编排：生成图文 → 发布图文 → 合成视频 → 发布视频。"""

from __future__ import annotations

from pathlib import Path

from workflow.agents import generate_article_bundle
from workflow.config import WorkflowConfig, load_workflow_config
from workflow.models import ArticleBundle, WorkflowRunSummary
from workflow.platforms import build_text_publishers, build_video_publishers
from workflow.video import bundle_to_slideshow_mp4


def run_workflow(
    topic: str,
    *,
    workflow_yaml: Path,
    work_dir: Path,
) -> WorkflowRunSummary:
    cfg = load_workflow_config(workflow_yaml)
    bundle = generate_article_bundle(topic, work_dir / "assets")
    _ensure_slide_images(bundle)
    summary = _publish_text_stages(bundle, cfg)
    video_path = work_dir / "output" / "slideshow.mp4"
    bundle_to_slideshow_mp4(
        bundle,
        video_path,
        width=cfg.video_width,
        height=cfg.video_height,
        slide_seconds=cfg.slide_duration_seconds,
    )
    summary.video_path = video_path
    summary.video_results = _publish_video_stages(video_path, bundle, cfg)
    return summary


def _ensure_slide_images(bundle: ArticleBundle) -> None:
    """若生成阶段未落盘图片，则补占位图。"""
    from workflow.video import ensure_placeholder_image

    w, h = 1080, 1920
    for i, s in enumerate(bundle.slides):
        p = Path(s.image_path)
        if not p.exists():
            ensure_placeholder_image(p, w, h, s.title or s.caption or f"slide-{i + 1}")


def _publish_text_stages(bundle: ArticleBundle, cfg: WorkflowConfig) -> WorkflowRunSummary:
    summary = WorkflowRunSummary(article_title=bundle.title)
    for pub in build_text_publishers(cfg.text_image_platforms):
        summary.text_results.append(pub.publish(bundle))
    return summary


def _publish_video_stages(
    video_path: Path,
    bundle: ArticleBundle,
    cfg: WorkflowConfig,
):
    from workflow.models import PublishResult

    results: list[PublishResult] = []
    desc = bundle.body_markdown[:500]
    for pub in build_video_publishers(cfg.video_platforms):
        results.append(pub.publish(video_path, bundle.title, desc))
    return results
