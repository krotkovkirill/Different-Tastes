import flet as ft
import flet_camera as fc


def main(page: ft.Page):
    page.title = "Different Tastes"
    page.scroll = ft.ScrollMode.AUTO

    title = ft.Text("Different Tastes", size=28)
    status = ft.Text("Поделись впечатлениями")
    camera = fc.Camera(width=360, height=270)
    photo_bytes = None
    preview = ft.Column()
    comment = ft.TextField(
        label="Впечатление — необязательно, до 30 символов",
        hint_text="Например: вообще не кислые",
        max_length=30,
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
            src=image_bytes,
            width=360,
            height=270,
            fit=ft.BoxFit.CONTAIN,
            error_content=ft.Text("Не удалось отобразить фотографию"),
        )

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
        card = ft.Card(
            content=ft.Container(
                padding=16,
                content=ft.Column(
                    controls=[
                        ft.Text("Ты", weight=ft.FontWeight.BOLD),
                        make_image(post["photo"]),
                        ft.Text(f"Оценка: {post['rating']}/5"),
                        *([ft.Text(post["comment"], size=18)] if post["comment"] else []),
                    ],
                    spacing=10,
                ),
            )
        )
        feed.controls.insert(0, card)
        empty_feed.visible = False
        reset_draft()
        status.value = "Опубликовано в локальную ленту"
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
    page.add(
        title,
        status,
        camera_button,
        camera,
        photo_button,
        draft_form,
        ft.Divider(),
        ft.Text("Лента", size=24),
        ft.Text("Публикации хранятся только до перезапуска приложения."),
        empty_feed,
        feed,
    )


if __name__ == "__main__":
    ft.run(main, view=ft.AppView.WEB_BROWSER)
