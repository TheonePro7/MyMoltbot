"""将图文幻灯片合成为竖屏滑动风格 MP4（依赖系统 ffmpeg）。"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from workflow.models import ArticleBundle


def ensure_placeholder_image(path: Path, width: int, height: int, label: str) -> None:
    """生成简单占位图（需 Pillow）。"""
    from PIL import Image, ImageDraw, ImageFont

    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (width, height), color=(24, 24, 32))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 36)
    except OSError:
        font = ImageFont.load_default()
    text = label[:80]
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((width - tw) // 2, (height - th) // 2), text, fill=(230, 230, 240), font=font)
    img.save(path, format="PNG")


def bundle_to_slideshow_mp4(
    bundle: ArticleBundle,
    out_path: Path,
    *,
    width: int,
    height: int,
    slide_seconds: float,
) -> Path:
    """
    每张 slide 一张图 + 底部文字条，用 ffmpeg concat + 缩放合成。
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    slides = bundle.slides
    if not slides:
        raise ValueError("ArticleBundle.slides 为空，无法生成视频")

    for i, s in enumerate(slides):
        p = Path(s.image_path)
        if not p.exists():
            ensure_placeholder_image(p, width, height, s.title or s.caption or f"第{i + 1}页")

    with tempfile.TemporaryDirectory(prefix="slideshow_") as tmp:
        tmp_path = Path(tmp)
        segment_files: list[Path] = []
        for i, s in enumerate(slides):
            seg = tmp_path / f"seg_{i:03d}.mp4"
            # 图铺满竖屏，底部留条显示 caption（文案写入文件，避免 drawtext 转义问题）
            img = Path(s.image_path).resolve().as_posix()
            cap_file = tmp_path / f"cap_{i:03d}.txt"
            cap_file.write_text((s.caption or s.title or "")[:200], encoding="utf-8")
            font = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
            vf = (
                f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
                f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black,"
                f"drawbox=y=ih*0.78:color=black@0.6:width=iw:height=ih*0.22:t=fill,"
                f"drawtext=textfile={cap_file.as_posix()}:fontcolor=white:fontsize=28:"
                f"reload=1:x=(w-text_w)/2:y=h*0.82:fontfile={font}"
            )
            cmd = [
                "ffmpeg",
                "-y",
                "-loop",
                "1",
                "-i",
                img,
                "-t",
                str(slide_seconds),
                "-vf",
                vf,
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-an",
                str(seg),
            ]
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            segment_files.append(seg)

        list_file = tmp_path / "concat.txt"
        list_file.write_text(
            "\n".join(f"file '{p.as_posix()}'" for p in segment_files),
            encoding="utf-8",
        )
        cmd_final = [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_file),
            "-c",
            "copy",
            str(out_path),
        ]
        subprocess.run(cmd_final, check=True, capture_output=True, text=True)

    return out_path
