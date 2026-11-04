import sqlite3

import flet as ft

from database import (
    find_user,
    get_friendships,
    remove_friendship,
    respond_friend_request,
    send_friend_request,
)


def create_friends_panel(page, user, on_change=None, is_authenticated=None):
    search = ft.TextField(label="Логин друга", text_size=18)
    message = ft.Text(visible=False, size=18)
    result = ft.Column(horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
    incoming = ft.Column(horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
    outgoing = ft.Column(horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
    friends = ft.Column(horizontal_alignment=ft.CrossAxisAlignment.STRETCH)

    def refresh(event=None):
        if is_authenticated is not None and not is_authenticated():
            return
        try:
            relationships = get_friendships(user["id"])
        except sqlite3.Error:
            message.value = "Не удалось загрузить друзей. Попробуй ещё раз."
            page.update()
            return
        incoming.controls.clear()
        outgoing.controls.clear()
        friends.controls.clear()
        for relationship in relationships:
            request_id = relationship["id"]
            label = ft.Text(f"{relationship['display_name']} (@{relationship['username']})")
            if relationship["status"] == "accepted":
                friends.controls.append(ft.Column(controls=[
                    label,
                    ft.TextButton(height=52, content="Удалить из друзей", on_click=lambda event, rid=request_id: change(rid, "remove")),
                ]))
            elif relationship["recipient_id"] == user["id"]:
                incoming.controls.append(ft.Column(controls=[
                    label,
                    ft.Button(height=56, content="Принять", on_click=lambda event, rid=request_id: change(rid, "accept")),
                    ft.TextButton(height=52, content="Отклонить", on_click=lambda event, rid=request_id: change(rid, "decline")),
                ]))
            else:
                outgoing.controls.append(ft.Column(controls=[
                    label,
                    ft.TextButton(height=52, content="Отменить заявку", on_click=lambda event, rid=request_id: change(rid, "remove")),
                ]))
        incoming_heading.visible = bool(incoming.controls)
        outgoing_heading.visible = bool(outgoing.controls)
        if not friends.controls:
            friends.controls.append(ft.Text("Пока нет друзей", size=20))
        message.visible = bool(message.value)
        if on_change is not None:
            on_change()
        page.update()

    def change(request_id, action):
        if is_authenticated is not None and not is_authenticated():
            return
        try:
            if action == "remove":
                changed = remove_friendship(request_id, user["id"])
            else:
                changed = respond_friend_request(request_id, user["id"], action == "accept")
        except sqlite3.Error:
            message.value = "Не удалось сохранить изменение. Попробуй ещё раз."
        else:
            message.value = "Готово" if changed else "Заявка уже изменилась или недоступна"
        refresh()

    def send(recipient_id):
        if is_authenticated is not None and not is_authenticated():
            return
        try:
            send_friend_request(user["id"], recipient_id)
        except ValueError as error:
            message.value = str(error)
        except sqlite3.Error:
            message.value = "Не удалось отправить заявку. Попробуй ещё раз."
        else:
            message.value = "Заявка отправлена"
            result.controls.clear()
        refresh()

    def search_user(event):
        if is_authenticated is not None and not is_authenticated():
            return
        result.controls.clear()
        message.value = ""
        username = (search.value or "").strip()
        if not username:
            message.value = "Введи логин друга"
        else:
            try:
                found = find_user(username, user["id"])
            except sqlite3.Error:
                message.value = "Не удалось выполнить поиск. Попробуй ещё раз."
            else:
                if found is None:
                    message.value = "Другой пользователь с таким логином не найден"
                else:
                    result.controls = [
                        ft.Text(f"{found['display_name']} (@{found['username']})"),
                        ft.Button(height=56, content="Добавить в друзья", on_click=lambda event: send(found["id"])),
                    ]
        message.visible = bool(message.value)
        page.update()

    incoming_heading = ft.Text("Заявки", size=24, weight=ft.FontWeight.BOLD)
    outgoing_heading = ft.Text("Отправлены", size=24, weight=ft.FontWeight.BOLD)
    panel = ft.Column(controls=[
        ft.Text("Друзья", size=32, weight=ft.FontWeight.BOLD),
        search,
        ft.Button(height=56, content="Найти", on_click=search_user),
        message,
        result,
        ft.Button(height=56, content="Обновить список", on_click=refresh),
        incoming_heading,
        incoming,
        outgoing_heading,
        outgoing,
        ft.Text("Мои друзья", size=24, weight=ft.FontWeight.BOLD),
        friends,
    ], spacing=20, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
    refresh()
    return panel
