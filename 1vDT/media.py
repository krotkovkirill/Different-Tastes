import io
import re
import warnings
from pathlib import Path
from uuid import uuid4

from PIL import Image, ImageOps, UnidentifiedImageError

import database

MAX_PHOTO_BYTES = 8 * 1024 * 1024
MAX_PHOTO_PIXELS = 25_000_000
Image.MAX_IMAGE_PIXELS = MAX_PHOTO_PIXELS


def normalize_photo(data):
    if not isinstance(data, (bytes, bytearray)) or not data:
        raise ValueError("Фотография пустая")
    if len(data) > MAX_PHOTO_BYTES:
        raise ValueError("Фотография должна быть не больше 8 МБ")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as original:
                if original.format not in {"JPEG", "PNG", "WEBP"}:
                    raise ValueError("Выбери фотографию JPG, PNG или WebP")
                if original.width * original.height > MAX_PHOTO_PIXELS:
                    raise ValueError("Слишком большое разрешение фотографии")
                original.load()
                image = ImageOps.exif_transpose(original)
                image.thumbnail((1600, 1600))
                if image.mode in {"RGBA", "LA"} or "transparency" in image.info:
                    rgba = image.convert("RGBA")
                    image = Image.new("RGB", rgba.size, "white")
                    image.paste(rgba, mask=rgba.getchannel("A"))
                else:
                    image = image.convert("RGB")
                output = io.BytesIO()
                image.save(output, format="JPEG", quality=88, optimize=True)
                return output.getvalue()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning) as error:
        raise ValueError("Не удалось прочитать фото. Выбери JPG, PNG или WebP.") from error


def photo_file(stored_path):
    photos = (database.DATA_DIR / "photos").resolve()
    path = Path(stored_path)
    if path.is_absolute() and path.parent.resolve() != photos:
        if path.parent.name != "photos" or not re.fullmatch(r"[a-f0-9]{32}\.(bin|jpg)", path.name):
            raise ValueError("Недопустимый путь к фотографии")
        path = photos / path.name
    elif not path.is_absolute():
        path = database.DATA_DIR / path
    path = path.resolve()
    if path.parent != photos:
        raise ValueError("Недопустимый путь к фотографии")
    return path


def save_photo(data):
    photos = database.DATA_DIR / "photos"
    photos.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid4().hex}.jpg"
    path = photos / filename
    try:
        path.write_bytes(data)
    except OSError:
        path.unlink(missing_ok=True)
        raise
    return f"photos/{filename}"


def read_photo(stored_path):
    path = photo_file(stored_path)
    with path.open("rb") as stream:
        data = stream.read(MAX_PHOTO_BYTES + 1)
    if len(data) > MAX_PHOTO_BYTES:
        raise ValueError("Слишком большой файл фотографии")
    return data


def delete_photo(stored_path):
    photo_file(stored_path).unlink(missing_ok=True)
