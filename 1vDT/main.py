import flet as ft
import flet_camera as fc

def main(page: ft.Page):
    page.title = "Different Tastes"

    title = ft.Text("different tastes", size=28)
    status = ft.Text("поделись впечатлениями")
    camera = fc.Camera(width=640, height=480)


    async def open_camera(event):
        camera_button.disabled = True
        status.value = "подключение камеры"
        page.update()

        try:
            cameras = await camera.get_available_cameras()
            if not cameras:
                status.value = "Camera not found"
            else:
                await camera.initialize(
                    description=cameras[0],
                    resolution_preset = fc.ResolutionPreset.MEDIUM,
                    enable_audio = False
                )
                status.value = "камера подключена"
        except Exception as error:
            status.value = f"Ошибка подключения камеры: {error}"
        finally:
            camera_button.disabled = False
            page.update()

    camera_button = ft.Button("Подключить камеру", on_click=open_camera)
    page.add(title, status, camera_button, camera)
      

ft.run(main, view=ft.AppView.WEB_BROWSER)

