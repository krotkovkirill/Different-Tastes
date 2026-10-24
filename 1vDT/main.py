import flet as ft

def main(page: ft.Page):
    page.title = "Different Tastes"

    title = ft.Text("different tastes", size=28)
    status = ft.Text("поделись впечатлениями")

    def open_camera(event):
        status.value = "Открытие камеры..."
        page.update()

    camera_button = ft.Button("Открыть камеру", on_click=open_camera)
    page.add(title, status, camera_button)

ft.run(main)

