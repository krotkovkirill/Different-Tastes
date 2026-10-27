import base64
import sqlite3
from pathlib import Path
from uuid import uuid4

from database import DATA_DIR, init_db, save_post, get_posts, delete_post, update_post

import flet as ft
import flet_camera as fc


def main(page: ft.Page):
    init_db()
    photos_dir = DATA_DIR / "photos"
    photos_dir.mkdir(parents=True, exist_ok=True)

    page.title = "Different Tastes"
    page.scroll = ft.ScrollMode.AUTO

    title = ft.Text("Different Tastes", size=28)
    status = ft.Text("Поделись впечатлениями")
    camera = fc.Camera(width=360, height=270)
    photo_bytes = None
    preview = ft.Column()
    comment = ft.TextField(
        label="Отзыв:",
        width=360,
    )
    rating = ft.Dropdown(
        label="Оценка",
        options=[ft.DropdownOption(key=str(value), text=str(value)) for value in range(1, 6)],
        width=180,
    )
    feed = ft.Column(spacing=16)
    empty_feed = ft.Text("Пока нет публикаций. Сделай первый снимок.")

    def make_image(image_bytes):
        return ft.Image(
            src=base64.b64encode(image_bytes).decode("ascii"),
            width=360,
            height=270,
            fit=ft.BoxFit.CONTAIN,
            error_content=ft.Text("Не удалось отобразить фотографию"),
        )

    def remove_post(post_id):
        try:
            saved_path = delete_post(post_id)
        except sqlite3.Error as error:
            status.value = f"Не удалось удалить публикацию: {error}"
            page.update()
            return

        status.value = "Публикация удалена" if saved_path else "Публикация уже удалена"
        if saved_path:
            try:
                photo_path = Path(saved_path).resolve()
                if photo_path.parent != photos_dir.resolve():
                    raise OSError("Фотография находится вне папки снимков")
                photo_path.unlink(missing_ok=True)
            except OSError:
                status.value = "Пост удалён, но файл фотографии удалить не удалось"

        load_feed()
        page.update()

    def edit_post(post):
        edit_comment = ft.TextField(label="Отзыв:", value=post["comment"], width=360)
        edit_rating = ft.Dropdown(
            label="Оценка",
            value=str(post["rating"]),
            options=[ft.DropdownOption(key=str(value), text=str(value)) for value in range(1, 6)],
            width=180,
        )
        edit_error = ft.Text(color="red")

        def cancel_edit(event):
            page.pop_dialog()

        def save_edit(event):
            text = (edit_comment.value or "").strip()
            edit_comment.error_text = None
            edit_rating.error_text = None
            edit_error.value = ""

            if len(text) > 30:
                edit_comment.error_text = "Не более 30 символов"
            if edit_rating.value not in {"1", "2", "3", "4", "5"}:
                edit_rating.error_text = "Выбери оценку от 1 до 5"
            if edit_comment.error_text or edit_rating.error_text:
                page.update()
                return

            try:
                updated = update_post(post["id"], int(edit_rating.value), text)
            except sqlite3.Error as error:
                edit_error.value = f"Не удалось сохранить изменения: {error}"
                page.update()
                return

            page.pop_dialog()
            status.value = "Публикация обновлена" if updated else "Публикация уже удалена"
            load_feed()
            page.update()

        page.show_dialog(
            ft.AlertDialog(
                modal=True,
                title=ft.Text("Редактировать публикацию"),
                content=ft.Column(
                    controls=[edit_comment, edit_rating, edit_error],
                    tight=True,
                    spacing=12,
                ),
                actions=[
                    ft.TextButton(content="Отмена", on_click=cancel_edit),
                    ft.Button(content="Сохранить", on_click=save_edit),
                ],
            )
        )

    def make_post_card(post):
        return ft.Card(
            content=ft.Container(
                padding=16,
                content=ft.Column(
                    controls=[
                        ft.Text("Ты", weight=ft.FontWeight.BOLD),
                        make_image(post["photo"]) if post["photo"] else ft.Text("Файл фотографии недоступен"),
                        ft.Text(f"Оценка: {post['rating']}/5"),
                        *([ft.Text(post["comment"], size=18)] if post["comment"] else []),
                        ft.Button(
                            content="Редактировать",
                            on_click=lambda event: edit_post(post),
                        ),
                        ft.Button(
                            content="Удалить",
                            on_click=lambda event: remove_post(post["id"]),
                        ),
                    ],
                    spacing=10,
                ),
            )
        )

    def load_feed():
        try:
            posts = get_posts()
        except sqlite3.Error as error:
            status.value = f"Не удалось загрузить ленту: {error}"
            return

        feed.controls.clear()
        for post in posts:
            try:
                post["photo"] = Path(post["photo_path"]).read_bytes()
            except OSError:
                post["photo"] = None
            feed.controls.append(make_post_card(post))
        empty_feed.visible = not bool(posts)

    async def open_camera(event):
        camera_button.disabled = True
        photo_button.disabled = True
        status.value = "Подключение камеры"
        page.update()
        camera_ready = False

        try:
            cameras = await camera.get_available_cameras()
            if not cameras:
                status.value = "Камера не найдена"
            else:
                await camera.initialize(
                    description=cameras[0],
                    resolution_preset=fc.ResolutionPreset.MEDIUM,
                    enable_audio=False,
                )
                camera_ready = True
                status.value = "Камера подключена"
        except Exception as error:
            status.value = f"Ошибка подключения камеры: {error}"
        finally:
            camera_button.disabled = camera_ready
            photo_button.disabled = not camera_ready
            page.update()

    async def take_photo(event):
        nonlocal photo_bytes
        photo_button.disabled = True
        draft_form.disabled = True
        page.update()
        try:
            captured = await camera.take_picture()
            if not captured:
                raise ValueError("Камера вернула пустой снимок")
            photo_bytes = bytes(captured)
            preview.controls = [make_image(photo_bytes)]
            draft_form.visible = True
            photo_button.content = "Переснять"
            status.value = "Добавь подпись и оценку"
        except Exception as error:
            status.value = f"Ошибка при съёмке: {error}"
        finally:
            photo_button.disabled = False
            draft_form.disabled = False
            page.update()

    def reset_draft():
        nonlocal photo_bytes
        photo_bytes = None
        preview.controls.clear()
        comment.value = ""
        comment.error_text = None
        rating.value = None
        rating.error_text = None
        draft_form.visible = False
        photo_button.content = "Сделать снимок"

    def clear_photo(event):
        reset_draft()
        status.value = "Можно сделать новый снимок"
        page.update()

    def publish_post(event):
        text = (comment.value or "").strip()
        comment.error_text = None
        rating.error_text = None

        if photo_bytes is None:
            status.value = "Сначала сделай снимок"
            page.update()
            return

        if len(text) > 30:
            comment.error_text = "Не более 30 символов"
        if rating.value not in {"1", "2", "3", "4", "5"}:
            rating.error_text = "Выбери оценку от 1 до 5"
        if comment.error_text or rating.error_text:
            page.update()
            return

        post = {
            "photo": photo_bytes,
            "rating": int(rating.value),
            "comment": text,
        }
        photo_path = photos_dir / f"{uuid4().hex}.bin"
        try:
            photo_path.write_bytes(photo_bytes)
            post["id"] = save_post(photo_path, post["rating"], post["comment"])
        except (OSError, sqlite3.Error) as error:
            try:
                photo_path.unlink(missing_ok=True)
            except OSError:
                pass
            status.value = f"Не удалось сохранить публикацию: {error}"
            page.update()
            return

        card = make_post_card(post)
        feed.controls.insert(0, card)
        empty_feed.visible = False
        reset_draft()
        status.value = "Публикация сохранена"
        page.update()

    camera_button = ft.Button(content="Подключить камеру", on_click=open_camera)
    photo_button = ft.Button(
        content="Сделать снимок", on_click=take_photo, disabled=True
    )
    draft_form = ft.Column(
        controls=[
            preview,
            comment,
            rating,
            ft.Button(content="Опубликовать", on_click=publish_post),
            ft.Button(content="Убрать снимок", on_click=clear_photo),
        ],
        visible=False,
        spacing=12,
    )
    load_feed()
    page.add(
        title,
        status,
        camera_button,
        camera,
        photo_button,
        draft_form,
        ft.Divider(),
        ft.Text("Лента", size=24),
        ft.Text("Публикации сохраняются на этом компьютере."),
        empty_feed,
        feed,
    )


if __name__ == "__main__":
    ft.run(main, view=ft.AppView.WEB_BROWSER)
