import asyncio
import sqlite3

import flet as ft

from auth import login_user, register_user


def create_auth_form(page, on_success):
    registration_mode = False
    heading = ft.Text("Вход", size=24)
    username = ft.TextField(label="Логин", width=360)
    display_name = ft.TextField(label="Имя", width=360, visible=False)
    password = ft.TextField(
        label="Пароль", password=True, can_reveal_password=True, width=360
    )
    error_text = ft.Text(color="red")

    def switch_mode(event):
        nonlocal registration_mode
        if form.disabled:
            return
        registration_mode = not registration_mode
        display_name.visible = registration_mode
        heading.value = "Регистрация" if registration_mode else "Вход"
        submit_button.content = "Создать аккаунт" if registration_mode else "Войти"
        switch_button.content = "Уже есть аккаунт? Войти" if registration_mode else "Создать аккаунт"
        password.value = ""
        error_text.value = ""
        page.update()

    async def submit(event):
        if form.disabled:
            return
        form.disabled = True
        error_text.value = ""
        page.update()
        try:
            if registration_mode:
                user = await asyncio.to_thread(
                    register_user,
                    username.value or "",
                    display_name.value or "",
                    password.value or "",
                )
            else:
                user = await asyncio.to_thread(
                    login_user, username.value or "", password.value or ""
                )
        except ValueError as error:
            error_text.value = str(error)
        except sqlite3.Error:
            error_text.value = "Не удалось обратиться к базе. Попробуй ещё раз."
        else:
            password.value = ""
            on_success(user)
        finally:
            form.disabled = False
            page.update()

    submit_button = ft.Button(content="Войти", on_click=submit)
    switch_button = ft.TextButton(content="Создать аккаунт", on_click=switch_mode)
    form = ft.Column(
        controls=[heading, username, display_name, password, error_text, submit_button, switch_button],
        spacing=12,
    )
    return form
