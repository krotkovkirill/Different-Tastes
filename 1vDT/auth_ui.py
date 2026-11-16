import asyncio
import inspect
import logging
import sqlite3

import flet as ft

from auth import sign_in
from ui import ERROR, MUTED, primary, stack, sync_text, text_field

logger = logging.getLogger(__name__)


def create_auth_form(page, on_success):
    submitting = False
    heading = ft.Text("Твой вкус — твои друзья", size=32, weight=ft.FontWeight.BOLD)
    username = text_field("Ник", autocorrect=False, enable_suggestions=False,
                          autofill_hints=[ft.AutofillHint.USERNAME], on_change=sync_text)
    password = text_field("Пароль", password=True, can_reveal_password=True,
                          autofill_hints=[ft.AutofillHint.PASSWORD], on_change=sync_text)
    error_text = ft.Text("", color=ERROR, visible=False, size=18)
    subtitle = ft.Text("Введи ник и пароль. Если аккаунта ещё нет, создадим его автоматически.", color=MUTED, size=18)

    async def submit(event):
        nonlocal submitting
        if submitting:
            return
        ft.context.disable_auto_update()
        if event is not None and event.control is password and isinstance(event.data, str):
            event.control.value = event.data
        values = (username.value or "", password.value or "")
        submitting = True
        form.disabled = True
        error_text.visible = False
        page.update()
        try:
            user = await asyncio.to_thread(sign_in, *values)
            password.value = ""
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

    password.on_submit = submit
    submit_button = primary("Продолжить", submit)
    form = stack([heading, subtitle, username, password, error_text, submit_button], spacing=20)
    form.username = username
    form.password = password
    form.error_text = error_text
    form.submit_button = submit_button
    return form
