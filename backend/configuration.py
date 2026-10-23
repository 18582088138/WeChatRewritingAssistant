"""Editable, versioned runtime configuration; API keys remain in environment variables."""

import hashlib
import json
import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOUNDS = {
    "port": (1, 65535), "window_days": (0, 30), "max_sources": (1, 20),
    "max_candidates": (1, 40), "context_chars": (1000, 100000),
    "image_limit": (1, 30), "video_limit": (0, 10),
    "image_bytes": (1000, 25000000), "video_bytes": (1000, 100000000),
    "download_retries": (0, 3), "word_count": (300, 6000),
    "fusion_retries": (0, 2),
    "min_images": (1, 10), "max_images": (1, 10), "compression_retries": (0, 4),
    "length_tolerance": (1, 2), "temperature": (0, 2), "review_temperature": (0, 2),
    "max_tokens": (500, 16000), "review_max_tokens": (500, 16000),
    "timeout_seconds": (10, 600), "review_timeout_seconds": (10, 600),
    "card_width": (720, 2160), "card_height": (960, 2880),
    "card_chars": (80, 320), "preview_chars": (200, 2000), "minimum_font_size": (26, 34),
}


def directory():
    return Path(os.getenv("CONFIG_DIR", ROOT / "config")).resolve()


def settings(name):
    value = json.loads((directory() / (name + ".json")).read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError("配置必须是 JSON 对象：" + name)
    for key, (low, high) in BOUNDS.items():
        if key in value and (isinstance(value[key], bool) or not isinstance(value[key], (int, float)) or not low <= value[key] <= high):
            raise ValueError(f"配置 {name}.{key} 必须在 {low} 到 {high} 之间")
    integer_fields = set(BOUNDS) - {"temperature", "review_temperature", "length_tolerance"}
    if any(key in value and not isinstance(value[key], int) for key in integer_fields):
        raise ValueError("配置计数、尺寸、字数与超时必须使用整数：" + name)
    if "min_images" in value and value["min_images"] > value["max_images"]:
        raise ValueError("min_images 不能超过 max_images")
    if "card_width" in value and value["card_width"] * 4 != value["card_height"] * 3:
        raise ValueError("图文卡片必须保持 3:4 比例")
    return value


def prompt(name):
    return (directory() / "prompts" / (name + ".md")).read_text(encoding="utf-8-sig")


def fingerprint():
    digest = hashlib.sha256()
    for path in sorted(directory().rglob("*")):
        if path.is_file():
            digest.update(path.relative_to(directory()).as_posix().encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()[:16]


def writer_prompt():
    return prompt("rewriting") + "\n统一语言风格：\n" + prompt("language-style")


def archive_configuration(article_root):
    version = fingerprint()
    target = Path(article_root) / "config-history" / version
    if not target.exists():
        shutil.copytree(directory(), target)
    return version
