import asyncio
import sqlite3

import flet as ft

from auth import login_user, register_user


def create_auth_form(page, on_success):
    registration_mode = False
    submitting = False
    heading = ft.Text("Вход", size=32)
    username = ft.TextField(label="Логин", text_size=18)
    display_name = ft.TextField(label="Имя", text_size=18, visible=False)
    password = ft.TextField(
        label="Пароль", password=True, can_reveal_password=True, text_size=18
    )
    error_text = ft.Text(color="red")

    def clear_error(event):
        ft.context.disable_auto_update()
        if isinstance(event.data, str):
            event.control.value = event.data
        if not form.disabled and error_text.value:
            error_text.value = ""
            error_text.update()

    username.on_change = clear_error
    display_name.on_change = clear_error
    password.on_change = clear_error

    def switch_mode(event):
        nonlocal registration_mode
        if submitting:
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
        nonlocal submitting
        if submitting:
            return
        submitting = True
        ft.context.disable_auto_update()
        if event is not None and event.control is password and isinstance(event.data, str):
            password.value = event.data
        submitted_username = username.value or ""
        submitted_name = display_name.value or ""
        submitted_password = password.value or ""
        is_registration = registration_mode
        form.disabled = True
        submit_button.disabled = True
        switch_button.disabled = True
        error_text.value = ""
        page.update()
        try:
            if is_registration:
                user = await asyncio.to_thread(
                    register_user,
                    submitted_username,
                    submitted_name,
                    submitted_password,
                )
            else:
                user = await asyncio.to_thread(
                    login_user, submitted_username, submitted_password
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
            submit_button.disabled = False
            switch_button.disabled = False
            submitting = False
            page.update()

    password.on_submit = submit

    submit_button = ft.Button(content="Войти", height=56, on_click=submit)
    switch_button = ft.TextButton(content="Создать аккаунт", height=56, on_click=switch_mode)
    form = ft.Column(
        controls=[heading, username, display_name, password, error_text, submit_button, switch_button],
        spacing=20,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
    )
    return form
