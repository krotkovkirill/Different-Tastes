import flet as ft
import flet_camera as fc


def main(page: ft.Page):
    page.title = "Different Tastes"
    page.scroll = ft.ScrollMode.AUTO  # Позволяем прокрутить страницу до снимка

    title = ft.Text("Different Tastes", size=28)
    status = ft.Text("Поделись впечатлениями")
    camera = fc.Camera(width=360, height=270)
    photo = ft.Image(src="", visible=False, width=360)

    async def open_camera(event):
        camera_button.disabled = True
        photo_button.disabled = True
        status.value = "Подключение камеры"
        page.update()
        camera_ready = False  # Запоминаем, удалось ли подключение

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
            camera_button.disabled = camera_ready  # После успеха не подключаем повторно
            photo_button.disabled = not camera_ready
            page.update()

    async def take_photo(event):
        photo_button.disabled = True
        page.update()
        try:
            photo_bytes = await camera.take_picture()
            photo.src = photo_bytes  # Передаём байты фотографии в элемент изображения
            photo.visible = True
            clear_button.visible = True
            photo_button.content = "Переснять"
            status.value = "Снимок сделан"
        except Exception as error:
            status.value = f"Ошибка при съёмке: {error}"
        finally:
            photo_button.disabled = False
            page.update()

    def clear_photo(event):
        photo.visible = False  # Убираем снимок из интерфейса
        photo.src = ""  # Освобождаем ссылку на байты фотографии
        clear_button.visible = False
        photo_button.content = "Сделать снимок"
        status.value = "Можно сделать новый снимок"
        page.update()

    camera_button = ft.Button(content="Подключить камеру", on_click=open_camera)
    photo_button = ft.Button(
        content="Сделать снимок", on_click=take_photo, disabled=True
    )
    clear_button = ft.Button(
        content="Убрать снимок", on_click=clear_photo, visible=False
    )
    page.add(title, status, camera_button, camera, photo_button, photo, clear_button)


if __name__ == "__main__":  # Запускаем приложение только при запуске этого файла
    ft.run(main, view=ft.AppView.WEB_BROWSER)
