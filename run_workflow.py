#!/usr/bin/env python3
"""命令行入口：运行默认多平台智能体工作流。"""

from __future__ import annotations

import argparse
from pathlib import Path

from workflow.pipeline import run_workflow


def main() -> None:
    parser = argparse.ArgumentParser(description="智能体工作流：图文 + 多平台占位发布 + 滑动视频")
    parser.add_argument("topic", nargs="?", default="今日主题", help="内容主题")
    parser.add_argument(
        "-w",
        "--workflow",
        type=Path,
        default=Path("workflows/default.yaml"),
        help="工作流 YAML 路径",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=Path("output/run"),
        help="工作目录（资产与视频输出）",
    )
    args = parser.parse_args()
    summary = run_workflow(args.topic, workflow_yaml=args.workflow, work_dir=args.output_dir)
    print("=== 图文发布（占位）===")
    for r in summary.text_results:
        print(f"  [{r.platform}] ok={r.ok} {r.message}")
    print("=== 视频 ===")
    print(f"  文件: {summary.video_path}")
    print("=== 视频发布（占位）===")
    for r in summary.video_results:
        print(f"  [{r.platform}] ok={r.ok} {r.message}")


if __name__ == "__main__":
    main()
