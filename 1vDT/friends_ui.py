import sqlite3

import flet as ft

from database import (
    find_user,
    get_friendships,
    remove_friendship,
    respond_friend_request,
    send_friend_request,
)


def create_friends_panel(page, user, on_change=None):
    search = ft.TextField(label="Логин друга", width=360)
    message = ft.Text()
    result = ft.Column()
    incoming = ft.Column()
    outgoing = ft.Column()
    friends = ft.Column()

    def refresh(event=None):
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
                    ft.TextButton(content="Удалить из друзей", on_click=lambda event, rid=request_id: change(rid, "remove")),
                ]))
            elif relationship["recipient_id"] == user["id"]:
                incoming.controls.append(ft.Column(controls=[
                    label,
                    ft.Button(content="Принять", on_click=lambda event, rid=request_id: change(rid, "accept")),
                    ft.TextButton(content="Отклонить", on_click=lambda event, rid=request_id: change(rid, "decline")),
                ]))
            else:
                outgoing.controls.append(ft.Column(controls=[
                    label,
                    ft.TextButton(content="Отменить заявку", on_click=lambda event, rid=request_id: change(rid, "remove")),
                ]))
        for section in (incoming, outgoing, friends):
            if not section.controls:
                section.controls.append(ft.Text("Пока пусто"))
        if on_change is not None:
            on_change()
        page.update()

    def change(request_id, action):
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
                        ft.Button(content="Добавить в друзья", on_click=lambda event: send(found["id"])),
                    ]
        page.update()

    panel = ft.Column(controls=[
        ft.Text("Друзья", size=24),
        search,
        ft.Button(content="Найти", on_click=search_user),
        message,
        result,
        ft.Button(content="Обновить список", on_click=refresh),
        ft.Text("Входящие заявки", weight=ft.FontWeight.BOLD),
        incoming,
        ft.Text("Отправленные заявки", weight=ft.FontWeight.BOLD),
        outgoing,
        ft.Text("Мои друзья", weight=ft.FontWeight.BOLD),
        friends,
    ], spacing=12)
    refresh()
    return panel
