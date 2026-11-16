import io
import re
import warnings
from pathlib import Path
from uuid import uuid4

from PIL import Image, ImageOps, UnidentifiedImageError
from pillow_heif import register_heif_opener

import database

MAX_PHOTO_BYTES = 8 * 1024 * 1024
MAX_PHOTO_PIXELS = 25_000_000
Image.MAX_IMAGE_PIXELS = MAX_PHOTO_PIXELS
register_heif_opener(thumbnails=False)


def normalize_photo(data):
    if not isinstance(data, (bytes, bytearray)) or not data:
        raise ValueError("Фотография пустая")
    if len(data) > MAX_PHOTO_BYTES:
        raise ValueError("Фотография должна быть не больше 8 МБ")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as original:
                if original.format not in {"JPEG", "PNG", "WEBP", "HEIF"}:
                    raise ValueError("Выбери фотографию JPG, PNG, WebP или HEIC")
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
        raise ValueError("Не удалось прочитать фото. Выбери JPG, PNG, WebP или HEIC.") from error


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


def normalize_avatar(data):
    normalized = normalize_photo(data)
    with Image.open(io.BytesIO(normalized)) as image:
        image = ImageOps.fit(image, (512, 512), method=Image.Resampling.LANCZOS)
        output = io.BytesIO()
        image.save(output, format="JPEG", quality=88, optimize=True)
        return output.getvalue()


def avatar_file(stored_path):
    folder = (database.DATA_DIR / "avatars").resolve()
    path = Path(stored_path)
    if path.is_absolute() or not re.fullmatch(r"avatars/[a-f0-9]{32}\.jpg", path.as_posix()):
        raise ValueError("Недопустимый путь к аватарке")
    path = (database.DATA_DIR / path).resolve()
    if path.parent != folder:
        raise ValueError("Недопустимый путь к аватарке")
    return path


def save_avatar(data):
    folder = database.DATA_DIR / "avatars"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{uuid4().hex}.jpg"
    try:
        path.write_bytes(data)
    except OSError:
        path.unlink(missing_ok=True)
        raise
    return f"avatars/{path.name}"


def read_avatar(stored_path):
    with avatar_file(stored_path).open("rb") as stream:
        data = stream.read(1024 * 1024 + 1)
    if len(data) > 1024 * 1024:
        raise ValueError("Слишком большой файл аватарки")
    return data


def delete_avatar(stored_path):
    avatar_file(stored_path).unlink(missing_ok=True)
