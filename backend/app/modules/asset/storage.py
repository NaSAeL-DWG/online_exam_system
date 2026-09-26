from io import BytesIO
from pathlib import Path
import warnings

from PIL import Image, UnidentifiedImageError

from app.core.errors import BusinessError


def validate_image(data):
    """解码真实图片，拒绝脚本、损坏文件和解压炸弹；只接受静态常见格式。"""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as image:
                image_format = image.format
                if image_format not in {"PNG", "JPEG", "WEBP"} or getattr(
                    image, "is_animated", False
                ):
                    raise BusinessError("INVALID_IMAGE", "仅支持静态 PNG、JPEG、WebP 图片")
                image.verify()
            with Image.open(BytesIO(data)) as image:
                image.load()
    except (
        UnidentifiedImageError,
        OSError,
        SyntaxError,
        ValueError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ):
        raise BusinessError("INVALID_IMAGE", "图片内容无效或尺寸过大") from None
    return {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp"}[image_format]


def write_new(root, storage_key, data):
    directory = Path(root).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    # 名称始终由服务端随机 UUID 产生；独占创建禁止覆盖既有快照资源。
    with (directory / storage_key).open("xb") as target:
        target.write(data)


def read_bytes(root, storage_key):
    return (Path(root).resolve() / storage_key).read_bytes()
