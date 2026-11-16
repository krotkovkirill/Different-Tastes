import sqlite3

import flet as ft

import database as db
from ui import ACCENT, ERROR, MUTED, SOFT, avatar, primary, stack, surface, sync_text, text_field


class FriendsPanel(ft.Column):
    def __init__(self, page, user, on_change=None, is_authenticated=None):
        super().__init__(spacing=20, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
        self.host = page
        self.user = user
        self.on_change_callback = on_change
        self.is_authenticated = is_authenticated or (lambda: True)
        self.search = text_field("Найти по нику", expand=True, on_change=sync_text)
        self.search.on_submit = self.search_user
        self.message = ft.Text("", visible=False, size=18)
        self.results = stack([])
        self.incoming = stack([])
        self.outgoing = stack([])
        self.friends = stack([])
        self.incoming_title = ft.Text("Заявки", size=24, weight=ft.FontWeight.BOLD)
        self.outgoing_title = ft.Text("Отправленные", size=24, weight=ft.FontWeight.BOLD)
        self.friends_title = ft.Text("Мои друзья", size=24, weight=ft.FontWeight.BOLD)
        self.controls = [
            ft.Row(controls=[ft.Text("Друзья", size=32, weight=ft.FontWeight.BOLD, expand=True),
                             ft.IconButton(icon=ft.Icons.REFRESH, tooltip="Обновить друзей", width=48, height=48, on_click=self.refresh)]),
            ft.Row(controls=[self.search, ft.IconButton(icon=ft.Icons.SEARCH, tooltip="Найти друга", width=52, height=56, bgcolor=SOFT, on_click=self.search_user)]),
            self.message, self.results, self.incoming_title, self.incoming,
            self.friends_title, self.friends, self.outgoing_title, self.outgoing,
        ]
        self.refresh()

    def tell(self, message, error=False):
        self.message.value = message
        self.message.visible = bool(message)
        self.message.color = ERROR if error else ACCENT

    def person(self, person, actions):
        return surface(stack([
            ft.Row(controls=[avatar(person["username"], avatar_path=person.get("avatar_path")),
                ft.Text(person["username"], size=20, weight=ft.FontWeight.BOLD,
                        max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, expand=True),
            ]),
            ft.Row(controls=actions, wrap=True, spacing=8),
        ]))

    def refresh(self, event=None):
        if not self.is_authenticated():
            return
        try:
            rows = db.get_friendships(self.user["id"])
        except sqlite3.Error:
            self.tell("Не удалось загрузить друзей. Попробуй обновить список.", True)
            self.host.update()
            return
        self.incoming.controls.clear()
        self.outgoing.controls.clear()
        self.friends.controls.clear()
        counts = {"incoming": 0, "friends": 0, "outgoing": 0}
        for row in rows:
            rid = row["id"]
            if row["status"] == "accepted":
                counts["friends"] += 1
                actions = [ft.TextButton(content="Удалить из друзей", height=48, on_click=lambda e, rid=rid: self.confirm_remove(rid))]
                self.friends.controls.append(self.person(row, actions))
            elif row["recipient_id"] == self.user["id"]:
                counts["incoming"] += 1
                actions = [primary("Принять", lambda e, rid=rid: self.change(rid, "accept")),
                           ft.TextButton(content="Отклонить", height=48, on_click=lambda e, rid=rid: self.change(rid, "decline"))]
                self.incoming.controls.append(self.person(row, actions))
            else:
                counts["outgoing"] += 1
                actions = [ft.TextButton(content="Отменить заявку", height=48, on_click=lambda e, rid=rid: self.change(rid, "remove"))]
                self.outgoing.controls.append(self.person(row, actions))
        self.incoming_title.visible = bool(counts["incoming"])
        self.incoming_title.value = f"Заявки · {counts['incoming']}"
        self.outgoing_title.visible = bool(counts["outgoing"])
        self.friends_title.value = f"Мои друзья · {counts['friends']}"
        if not counts["friends"]:
            self.friends.controls = [surface(ft.Text("Найди друга по нику и отправь первую заявку.", size=20, color=MUTED))]
        if self.on_change_callback:
            self.on_change_callback()
        self.host.update()

    def change(self, request_id, action):
        if not self.is_authenticated():
            return
        try:
            changed = db.remove_friendship(request_id, self.user["id"]) if action == "remove" else db.respond_friend_request(request_id, self.user["id"], action == "accept")
            self.tell("Готово" if changed else "Заявка уже изменилась. Список обновлён.")
        except sqlite3.Error:
            self.tell("Не удалось сохранить изменение. Попробуй ещё раз.", True)
        self.results.controls.clear()
        self.refresh()

    def confirm_remove(self, request_id):
        if not self.is_authenticated():
            return
        def confirm(event):
            self.host.pop_dialog()
            self.change(request_id, "remove")
        self.host.show_dialog(ft.AlertDialog(
            modal=True, title=ft.Text("Удалить друга?"),
            content=ft.Text("Вы перестанете видеть публикации друг друга."),
            actions=[ft.TextButton(content="Отмена", on_click=lambda e: self.host.pop_dialog()),
                     ft.Button(content="Удалить", on_click=confirm)],
        ))

    def send(self, recipient_id):
        if not self.is_authenticated():
            return
        try:
            db.send_friend_request(self.user["id"], recipient_id)
            self.tell("Заявка отправлена")
            self.results.controls.clear()
        except ValueError as error:
            self.tell(str(error), True)
        except sqlite3.Error:
            self.tell("Не удалось отправить заявку. Попробуй ещё раз.", True)
        self.refresh()

    def search_user(self, event=None):
        if not self.is_authenticated():
            return
        if event is not None and event.control is self.search and isinstance(event.data, str):
            self.search.value = event.data
        self.results.controls.clear()
        username = (self.search.value or "").strip()
        self.tell("")
        if not username:
            self.tell("Введи ник друга", True)
        else:
            try:
                found = db.find_user(username, self.user["id"])
                relationships = db.get_friendships(self.user["id"])
                relationship = next((r for r in relationships if found and r["user_id"] == found["id"]), None)
                if not found:
                    self.tell("Другой пользователь с таким ником не найден", True)
                elif relationship:
                    self.tell("Вы уже друзья" if relationship["status"] == "accepted" else "Между вами уже есть заявка")
                else:
                    self.results.controls = [self.person(found, [primary("Добавить в друзья", lambda e: self.send(found["id"]))])]
            except sqlite3.Error:
                self.tell("Не удалось выполнить поиск. Попробуй ещё раз.", True)
        self.host.update()


def create_friends_panel(page, user, on_change=None, is_authenticated=None):
    return FriendsPanel(page, user, on_change, is_authenticated)
