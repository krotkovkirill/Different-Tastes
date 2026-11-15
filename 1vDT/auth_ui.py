import asyncio
import inspect
import logging
import sqlite3

import flet as ft

from auth import login_user, register_user
from ui import ERROR, MUTED, primary, stack, sync_text, text_field

logger = logging.getLogger(__name__)


def create_auth_form(page, on_success):
    registration_mode = False
    submitting = False
    heading = ft.Text("С возвращением", size=32, weight=ft.FontWeight.BOLD)
    username = text_field("Логин", autocorrect=False, enable_suggestions=False,
                          autofill_hints=[ft.AutofillHint.USERNAME], on_change=sync_text)
    display_name = text_field("Имя", visible=False, on_change=sync_text)
    password = text_field("Пароль", password=True, can_reveal_password=True,
                          autofill_hints=[ft.AutofillHint.PASSWORD], on_change=sync_text)
    confirmation = text_field("Повтори пароль", password=True, can_reveal_password=True,
                              visible=False, on_change=sync_text)
    error_text = ft.Text("", color=ERROR, visible=False, size=18)
    subtitle = ft.Text("Войди, чтобы увидеть, что пробуют друзья.", color=MUTED, size=18)

    def switch_mode(event):
        nonlocal registration_mode
        if submitting:
            return
        registration_mode = not registration_mode
        display_name.visible = registration_mode
        confirmation.visible = registration_mode
        heading.value = "Начнём знакомство"
        if not registration_mode:
            heading.value = "С возвращением"
        subtitle.value = "Выбери логин и пароль от 8 символов." if registration_mode else "Войди, чтобы увидеть, что пробуют друзья."
        submit_button.content = "Создать аккаунт" if registration_mode else "Войти"
        switch_button.content = "Уже есть аккаунт? Войти" if registration_mode else "Создать аккаунт"
        password.value = confirmation.value = ""
        error_text.visible = False
        page.update()

    async def submit(event):
        nonlocal submitting
        if submitting:
            return
        ft.context.disable_auto_update()
        if event is not None and event.control in (password, confirmation) and isinstance(event.data, str):
            event.control.value = event.data
        values = (username.value or "", display_name.value or "", password.value or "")
        if registration_mode and values[2] != (confirmation.value or ""):
            error_text.value = "Пароли не совпадают"
            error_text.visible = True
            page.update()
            return
        submitting = True
        form.disabled = True
        error_text.visible = False
        page.update()
        try:
            user = await asyncio.to_thread(register_user, *values) if registration_mode else await asyncio.to_thread(login_user, values[0], values[2])
            password.value = confirmation.value = ""
            result = on_success(user)
            if inspect.isawaitable(result):
                await result
        except ValueError as error:
            error_text.value = str(error)
            error_text.visible = True
        except sqlite3.Error:
            error_text.value = "Не удалось открыть аккаунт. Попробуй ещё раз."
            error_text.visible = True
        except Exception:
            logger.exception("Authentication interface failed")
            error_text.value = "Не удалось завершить вход. Попробуй ещё раз."
            error_text.visible = True
        finally:
            form.disabled = False
            submitting = False
            page.update()

    password.on_submit = confirmation.on_submit = submit
    submit_button = primary("Войти", submit)
    switch_button = ft.TextButton(content="Создать аккаунт", height=52, on_click=switch_mode)
    form = stack([heading, subtitle, username, display_name, password, confirmation,
                  error_text, submit_button, switch_button], spacing=20)
    form.username = username
    form.display_name = display_name
    form.password = password
    form.confirmation = confirmation
    form.error_text = error_text
    form.submit_button = submit_button
    form.switch_button = switch_button
    return form
