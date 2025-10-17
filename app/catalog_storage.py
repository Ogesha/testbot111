from __future__ import annotations

import hashlib
import mimetypes
import shutil
from pathlib import Path
from urllib.parse import urlparse

import requests


def _slugify(value: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() or ch in "-_" else "_" for ch in value)
    cleaned = "_".join(filter(None, cleaned.split("_")))
    return cleaned or "category"


def _guess_extension(url: str, content_type: str | None) -> str:
    parsed = urlparse(url)
    path_ext = Path(parsed.path).suffix
    if path_ext:
        return path_ext
    if content_type:
        ext = mimetypes.guess_extension(content_type.split(";")[0].strip())
        if ext:
            return ext
    return ".jpg"


class CatalogStorage:
    """Управляет локальным хранилищем изображений каталога."""

    def __init__(self, base_dir: str):
        self.base_dir = Path(base_dir)
        self.images_dir = self.base_dir / "images"

    def reset(self) -> None:
        """Полностью очищает и подготавливает каталог под новые данные."""

        if self.base_dir.exists():
            shutil.rmtree(self.base_dir)
        self.images_dir.mkdir(parents=True, exist_ok=True)

    def store_image(self, category_name: str, image_url: str | None) -> str | None:
        """Скачивает изображение и возвращает абсолютный путь до файла."""

        if not image_url:
            return None

        try:
            response = requests.get(image_url, timeout=20)
            response.raise_for_status()
        except Exception:
            return None

        slug = _slugify(category_name)
        category_dir = self.images_dir / slug
        category_dir.mkdir(parents=True, exist_ok=True)

        extension = _guess_extension(image_url, response.headers.get("Content-Type"))
        filename = hashlib.sha256(image_url.encode("utf-8")).hexdigest() + extension
        file_path = category_dir / filename

        try:
            file_path.write_bytes(response.content)
        except OSError:
            return None

        try:
            return str(file_path.resolve(strict=False))
        except OSError:
            return str(file_path)
