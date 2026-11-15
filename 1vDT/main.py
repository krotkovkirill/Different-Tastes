import asyncio
import base64
import logging
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import flet as ft
import flet_camera as fc

import auth
import database as db
import media
from auth_ui import create_auth_form
from friends_ui import create_friends_panel
from ui import ACCENT, ERROR, INK, LINE, MUTED, PAPER, SOFT, avatar, configure_page, primary, stack, surface, sync_text, text_field

logger = logging.getLogger(__name__)
PAGE_SIZE = 12


class Application:
    def __init__(self, page):
        self.page = page
        configure_page(page)
        db.init_db()
        self.preferences = ft.SharedPreferences()
        self.picker = ft.FilePicker()
        self.user = None
        self.token = None
        self.busy = False
        self.screen = 0
        self.photo_data = None
        self.camera_ready = False
        self.camera = fc.Camera()
        self.feed_mode = "friends"
        self.cursor = None
        self.friend_panel = None
        self.notice = ft.Text("", visible=False, size=18, color=ERROR)
        self.loading = ft.Container(content=ft.ProgressRing(width=36, height=36), padding=40, alignment=ft.Alignment.CENTER)
        self.auth_form = create_auth_form(page, self.authenticated)
        self.auth_slot = stack([self.auth_form], visible=False)
        self.feed = stack([], spacing=24)
        self.more_button = ft.OutlinedButton(content="Показать ещё", height=52, on_click=self.load_more, visible=False)
        self.empty_feed = surface(stack([
            ft.Container(content=ft.Icon(ft.Icons.RESTAURANT_ROUNDED, size=60, color=ACCENT),
                         width=112, height=112, bgcolor=SOFT, border_radius=32, alignment=ft.Alignment.CENTER),
            ft.Text("Что попробуем?", size=32, weight=ft.FontWeight.BOLD),
            ft.Text("Первый снимок — начало твоей ленты.", size=20, color=MUTED),
            primary("Поделиться вкусом", lambda e: self.show_screen(1), icon=ft.Icons.ADD),
            ft.TextButton(content="Найти друзей", height=52, on_click=lambda e: self.show_screen(2)),
        ], spacing=20), padding=24)
        self.all_filter = ft.Button(content="Друзья", height=48, expand=True, on_click=lambda e: self.filter_feed("friends"))
        self.own_filter = ft.Button(content="Мои", height=48, expand=True, on_click=lambda e: self.filter_feed("own"))
        self.feed_view = stack([
            ft.Row(controls=[ft.Text("Лента", size=32, weight=ft.FontWeight.BOLD, expand=True),
                ft.IconButton(icon=ft.Icons.REFRESH_ROUNDED, tooltip="Обновить ленту", icon_size=28, width=48, height=48, on_click=self.refresh_feed)]),
            ft.Row(controls=[self.all_filter, self.own_filter], spacing=12),
            self.empty_feed, self.feed, self.more_button,
        ])
        self.camera_slot = stack([])
        self.preview = stack([], visible=False)
        self.comment = text_field("Отзыв", hint_text="Можно оставить пустым", on_change=sync_text)
        self.rating = None
        self.rating_buttons = [ft.IconButton(icon=ft.Icons.STAR_BORDER_ROUNDED, icon_size=34,
            width=48, height=48, tooltip=f"Оценка {value} из 5", on_click=lambda e, value=value: self.set_rating(value)) for value in range(1, 6)]
        self.rating_error = ft.Text("", color=ERROR, visible=False)
        self.publish_button = primary("Опубликовать", self.publish, icon=ft.Icons.ARROW_UPWARD_ROUNDED)
        self.draft = stack([
            self.preview,
            ft.Text("Как тебе?", size=24, weight=ft.FontWeight.BOLD),
            ft.Row(controls=self.rating_buttons, spacing=0, alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            self.rating_error, self.comment, self.publish_button,
            ft.TextButton(content="Убрать снимок", height=52, on_click=self.discard_draft),
        ], visible=False)
        self.connect_button = primary("Открыть камеру", self.open_camera, icon=ft.Icons.CAMERA_ALT_OUTLINED)
        self.capture_button = primary("Сделать снимок", self.take_photo, icon=ft.Icons.CAMERA, visible=False)
        self.gallery_button = ft.OutlinedButton(content="Выбрать из галереи", icon=ft.Icons.PHOTO_LIBRARY_OUTLINED,
                                                height=56, on_click=self.pick_photo)
        self.camera_hint = ft.Container(
            content=stack([ft.Icon(ft.Icons.CAMERA_ALT_OUTLINED, size=64, color=ACCENT),
                ft.Text("Один снимок. Твой вкус.", size=26, weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER)], spacing=20),
            padding=32, alignment=ft.Alignment.CENTER, bgcolor=SOFT, border_radius=24,
        )
        self.composer = surface(stack([self.camera_hint, self.connect_button, self.gallery_button,
                                     self.camera_slot, self.capture_button, self.draft]), padding=20)
        self.camera_view = stack([ft.Text("Новый вкус", size=32, weight=ft.FontWeight.BOLD), self.composer], visible=False)
        self.friends_slot = stack([])
        self.friends_view = stack([self.friends_slot], visible=False)
        self.profile_name = text_field("Имя", on_change=sync_text)
        self.profile_heading = ft.Text("", size=28, weight=ft.FontWeight.BOLD)
        self.profile_login = ft.Text("", size=20, color=MUTED, selectable=True)
        self.profile_avatar = ft.Row(controls=[])
        self.stats_posts = ft.Text("0", size=32, weight=ft.FontWeight.BOLD)
        self.stats_friends = ft.Text("0", size=32, weight=ft.FontWeight.BOLD)
        self.profile_view = stack([
            ft.Text("Профиль", size=32, weight=ft.FontWeight.BOLD),
            surface(stack([self.profile_avatar, self.profile_heading, self.profile_login,
                ft.Row(controls=[ft.Column(controls=[self.stats_posts, ft.Text("публикаций", color=MUTED)], expand=True),
                                 ft.Column(controls=[self.stats_friends, ft.Text("друзей", color=MUTED)], expand=True)]),
                self.profile_name, primary("Сохранить имя", self.save_profile)])),
            ft.OutlinedButton(content="Сменить пароль", height=56, on_click=self.password_dialog),
            ft.TextButton(content="Выйти из аккаунта", icon=ft.Icons.LOGOUT, height=56, on_click=self.logout),
        ], visible=False)
        self.views = [self.feed_view, self.camera_view, self.friends_view, self.profile_view]
        self.app_view = stack(self.views, visible=False)
        destinations = [("Лента", ft.Icons.HOME_OUTLINED, ft.Icons.HOME),
                        ("Снимок", ft.Icons.ADD_A_PHOTO_OUTLINED, ft.Icons.ADD_A_PHOTO),
                        ("Друзья", ft.Icons.PEOPLE_OUTLINE, ft.Icons.PEOPLE),
                        ("Профиль", ft.Icons.PERSON_OUTLINE, ft.Icons.PERSON)]
        self.navigation = ft.NavigationBar(destinations=[ft.NavigationBarDestination(icon=icon, selected_icon=selected, label=label)
            for label, icon, selected in destinations], selected_index=0, visible=False, on_change=self.navigate)
        page.navigation_bar = self.navigation
        self.sidebar_buttons = [ft.TextButton(content=label, icon=icon, height=56,
            on_click=lambda e, index=index: self.show_screen(index)) for index, (label, icon, _) in enumerate(destinations)]
        self.sidebar = ft.Container(content=stack([
            ft.Row(controls=[ft.Icon(ft.Icons.RESTAURANT_ROUNDED, color=ACCENT, size=28),
                             ft.Text("Different\nTastes", size=24, weight=ft.FontWeight.BOLD)], spacing=12),
            ft.Container(height=20), *self.sidebar_buttons,
        ], spacing=12), width=232, padding=24, bgcolor="#FFFFFF", visible=False)
        self.brand = ft.Row(controls=[ft.Icon(ft.Icons.RESTAURANT_ROUNDED, color=ACCENT, size=28),
            ft.Text("Different Tastes", size=24, weight=ft.FontWeight.BOLD, expand=True)], expand=True, spacing=10)
        self.profile_button = ft.IconButton(icon=ft.Icons.PERSON_OUTLINE, tooltip="Мой профиль", width=48, height=48,
                                            on_click=lambda e: self.show_screen(3), visible=False)
        self.header = ft.Row(controls=[self.brand, self.profile_button], height=56)
        self.body = stack([self.loading, self.notice, self.auth_slot, self.app_view], spacing=20,
                           scroll=ft.ScrollMode.AUTO, expand=True)
        self.content_column = ft.Column(controls=[self.header, self.body], spacing=24,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER, expand=True)
        self.main_area = ft.Container(content=self.content_column, expand=True)
        self.root = ft.Row(controls=[self.sidebar, self.main_area], expand=True, spacing=0,
                           vertical_alignment=ft.CrossAxisAlignment.STRETCH)
        self.page.on_resize = self.resize

    async def start(self):
        self.page.add(self.root)
        self.resize()
        try:
            token = await self.preferences.get(auth.SESSION_STORAGE_KEY)
            user = await asyncio.to_thread(auth.resume_session, token)
            if user:
                self.token = token
                self.activate(user)
            elif token is not None:
                await self.preferences.remove(auth.SESSION_STORAGE_KEY)
        except Exception:
            logger.warning("Could not restore browser session", exc_info=True)
            self.auth_form.error_text.value = "Войди в аккаунт ещё раз."
            self.auth_form.error_text.visible = True
        finally:
            self.loading.visible = False
            self.auth_slot.visible = self.user is None
            self.resize()

    def resize(self, event=None):
        width = getattr(self.page, "width", None) or 390
        desktop = width >= 1000 and self.user is not None
        gutter = 32 if width >= 600 else 16
        self.sidebar.visible = desktop
        self.navigation.visible = self.user is not None and not desktop
        available = width - (232 if desktop else 0) - 2 * gutter
        content_width = min(720 if self.user else 480, max(240, available))
        self.header.width = self.body.width = content_width
        self.main_area.padding = ft.Padding.symmetric(horizontal=gutter, vertical=16)
        self.camera.width = max(1, content_width - 42)
        self.camera.height = self.camera.width * 3 / 4
        self.page.update()

    def tell(self, message, error=False):
        self.notice.value = message
        self.notice.visible = bool(message) and error
        if message and not error:
            self.page.show_dialog(ft.SnackBar(content=ft.Text(message, size=18), duration=3500))
        self.page.update()

    def set_busy(self, value):
        self.busy = value
        self.composer.disabled = value
        self.navigation.disabled = value
        self.profile_button.disabled = value
        self.profile_view.disabled = value
        self.sidebar.disabled = value
        self.loading.visible = value
        self.page.update()

    def require_login(self):
        if not self.user or not self.token:
            return False
        try:
            fresh = auth.resume_session(self.token)
        except sqlite3.Error:
            self.tell("Не удалось проверить вход. Попробуй ещё раз.", True)
            return False
        if not fresh or fresh["id"] != self.user["id"]:
            self.clear_login("Вход завершён. Войди снова.")
            return False
        self.user = fresh
        return True

    async def authenticated(self, user):
        token = await asyncio.to_thread(auth.create_session, user["id"])
        try:
            saved = await self.preferences.set(auth.SESSION_STORAGE_KEY, token)
        except Exception:
            saved = False
        self.token = token
        self.activate(user)
        if not saved:
            self.tell("Вход выполнен. В этом браузере он не сохранится после закрытия.", True)

    def activate(self, user):
        self.user = user
        self.notice.visible = False
        self.auth_slot.visible = False
        self.app_view.visible = True
        self.profile_button.visible = True
        self.friend_panel = create_friends_panel(self.page, user, on_change=self.friendships_changed, is_authenticated=self.require_login)
        self.friends_slot.controls = [self.friend_panel]
        self.show_screen(0)
        self.resize()

    def clear_login(self, message=""):
        self.user = self.token = None
        self.release_camera()
        self.reset_draft()
        self.feed.controls.clear()
        self.friends_slot.controls.clear()
        self.friend_panel = None
        self.app_view.visible = False
        self.profile_button.visible = False
        self.notice.visible = False
        self.auth_form = create_auth_form(self.page, self.authenticated)
        self.auth_form.error_text.value = message
        self.auth_form.error_text.visible = bool(message)
        self.auth_slot.controls = [self.auth_form]
        self.auth_slot.visible = True
        self.reset_scroll()
        self.feed_mode = "friends"
        self.cursor = None
        self.resize()

    async def logout(self, event=None):
        if self.busy:
            return
        self.set_busy(True)
        try:
            await asyncio.to_thread(auth.end_session, self.token)
        except sqlite3.Error:
            self.set_busy(False)
            self.tell("Не удалось завершить вход. Попробуй ещё раз.", True)
            return
        try:
            await self.preferences.remove(auth.SESSION_STORAGE_KEY)
        except Exception:
            pass
        self.clear_login()
        self.set_busy(False)

    async def scroll_top(self):
        try:
            await self.body.scroll_to(offset=0, duration=0)
        except Exception:
            logger.debug("Could not reset scroll position", exc_info=True)

    def reset_scroll(self):
        if hasattr(self.page, "run_task"):
            self.page.run_task(self.scroll_top)

    def navigate(self, event):
        self.show_screen(event.control.selected_index)

    def show_screen(self, index):
        if self.busy or not self.require_login():
            return
        if self.screen == 1 and index != 1:
            self.release_camera()
        changed_screen = self.screen != index
        self.screen = index
        self.navigation.selected_index = index
        self.notice.visible = False
        for i, view in enumerate(self.views):
            view.visible = i == index
        for i, button in enumerate(self.sidebar_buttons):
            button.style = ft.ButtonStyle(bgcolor=SOFT if i == index else "transparent", color=ACCENT if i == index else MUTED,
                alignment=ft.Alignment.CENTER_LEFT, shape=ft.RoundedRectangleBorder(radius=14))
        if index == 0:
            self.refresh_feed()
        elif index == 2 and self.friend_panel:
            self.friend_panel.refresh()
        elif index == 3:
            self.load_profile()
        self.page.update()
        if changed_screen:
            self.reset_scroll()

    def filter_feed(self, mode):
        if self.busy:
            return
        self.feed_mode = mode
        self.refresh_feed()
        self.reset_scroll()

    def friendships_changed(self):
        if self.user and self.screen == 0:
            self.refresh_feed()

    def refresh_feed(self, event=None):
        self.load_feed(reset=True)

    def load_more(self, event=None):
        self.load_feed(reset=False)

    def load_feed(self, reset=True):
        if not self.require_login():
            return
        cursor = None if reset else self.cursor
        try:
            posts = db.get_feed(self.user["id"], PAGE_SIZE + 1, cursor, self.feed_mode == "own")
            visible = posts[:PAGE_SIZE]
            cards = [self.post_card(post) for post in visible]
        except (sqlite3.Error, OSError):
            logger.exception("Could not load feed")
            self.tell("Лента не загрузилась. Нажми обновить.", True)
            return
        if reset:
            self.feed.controls.clear()
        self.feed.controls.extend(cards)
        if visible:
            self.cursor = visible[-1]["id"]
        self.more_button.visible = len(posts) > PAGE_SIZE
        self.empty_feed.visible = not bool(self.feed.controls)
        for button, active in ((self.all_filter, self.feed_mode == "friends"), (self.own_filter, self.feed_mode == "own")):
            button.style = ft.ButtonStyle(bgcolor=ACCENT if active else SOFT, color="#FFFFFF" if active else ACCENT,
                                          elevation=0, shape=ft.RoundedRectangleBorder(radius=14))
        self.page.update()

    def image(self, data, square=True):
        return ft.Image(src=base64.b64encode(data).decode("ascii"), aspect_ratio=1 if square else 4 / 3,
                        fit=ft.BoxFit.CONTAIN, error_content=ft.Text("Не удалось показать фото", size=18))

    def post_card(self, post):
        try:
            image = self.image(media.read_photo(post["photo_path"]))
        except (OSError, ValueError):
            image = ft.Container(content=stack([ft.Icon(ft.Icons.IMAGE_NOT_SUPPORTED_OUTLINED, size=48, color=MUTED),
                ft.Text("Фото недоступно", color=MUTED, text_align=ft.TextAlign.CENTER)]),
                height=240, alignment=ft.Alignment.CENTER)
        menu = ft.PopupMenuButton(icon=ft.Icons.MORE_HORIZ, tooltip="Действия с публикацией", width=48, height=48,
            visible=post["user_id"] == self.user["id"], items=[
                ft.PopupMenuItem(content="Редактировать", icon=ft.Icons.EDIT_OUTLINED, height=52, on_click=lambda e: self.edit_post(post)),
                ft.PopupMenuItem(content="Удалить", icon=ft.Icons.DELETE_OUTLINE, height=52, on_click=lambda e: self.confirm_delete(post)),
            ])
        try:
            date = datetime.fromisoformat(post["created_at"]).replace(tzinfo=timezone.utc).astimezone().strftime("%d.%m")
        except (ValueError, TypeError):
            date = ""
        return ft.Container(bgcolor="#FFFFFF", border=ft.Border.all(1, LINE), border_radius=24,
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS, content=stack([
                ft.Container(padding=16, content=ft.Row(controls=[avatar(post["display_name"]),
                    ft.Text(post["display_name"], size=21, weight=ft.FontWeight.BOLD, expand=True,
                            max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, tooltip=f"@{post['username']}"), menu])),
                ft.Container(content=image, bgcolor=SOFT),
                ft.Container(padding=20, content=stack([
                    ft.Row(controls=[ft.Icon(ft.Icons.STAR_ROUNDED, color=ACCENT, size=28),
                        ft.Text(f"{post['rating']} / 5", size=24, weight=ft.FontWeight.BOLD, color=ACCENT),
                        ft.Container(expand=True), ft.Text(date, size=16, color=MUTED)]),
                    *([ft.Text(post["comment"], size=22, color=INK)] if post["comment"] else []),
                ])),
            ], spacing=0))

    def confirm_delete(self, post):
        if not self.require_login() or post["user_id"] != self.user["id"]:
            return
        def remove(event):
            if not self.require_login():
                self.page.pop_dialog()
                return
            try:
                path = db.delete_post(post["id"], self.user["id"])
            except sqlite3.Error:
                self.tell("Не удалось удалить публикацию.", True)
                return
            self.page.pop_dialog()
            if path:
                try:
                    media.delete_photo(path)
                except (OSError, ValueError):
                    logger.warning("Could not remove an orphaned photo", exc_info=True)
            self.refresh_feed()
            self.tell("Публикация удалена" if path else "Публикация уже удалена")
        self.page.show_dialog(ft.AlertDialog(modal=True, title=ft.Text("Удалить публикацию?"),
            content=ft.Text("Фотография, оценка и отзыв будут удалены."),
            actions=[ft.TextButton(content="Отмена", on_click=lambda e: self.page.pop_dialog()),
                     ft.Button(content="Удалить", on_click=remove)]))

    def edit_post(self, post):
        if not self.require_login() or post["user_id"] != self.user["id"]:
            return
        comment = text_field("Отзыв", value=post["comment"], on_change=sync_text)
        rating = ft.Dropdown(label="Оценка", value=str(post["rating"]), text_size=18,
            options=[ft.DropdownOption(key=str(n), text=str(n)) for n in range(1, 6)])
        error = ft.Text("", color=ERROR, visible=False)
        def save(event):
            if not self.require_login():
                self.page.pop_dialog()
                return
            try:
                if rating.value not in {"1", "2", "3", "4", "5"}:
                    raise ValueError("Выбери оценку от 1 до 5")
                changed = db.update_post(post["id"], int(rating.value), comment.value or "", self.user["id"])
            except ValueError as exc:
                error.value = str(exc)
                error.visible = True
                self.page.update()
                return
            except sqlite3.Error:
                error.value = "Не удалось сохранить изменения. Попробуй ещё раз."
                error.visible = True
                self.page.update()
                return
            self.page.pop_dialog()
            self.refresh_feed()
            self.tell("Изменения сохранены" if changed else "Публикация уже удалена")
        self.page.show_dialog(ft.AlertDialog(modal=True, title=ft.Text("Редактирование"),
            content=stack([rating, comment, error], tight=True),
            actions=[ft.TextButton(content="Отмена", on_click=lambda e: self.page.pop_dialog()),
                     ft.Button(content="Сохранить", on_click=save)]))

    def release_camera(self):
        self.camera_slot.controls.clear()
        self.camera_ready = False
        self.camera = fc.Camera()
        self.capture_button.visible = False
        self.preview.visible = bool(self.photo_data)
        self.draft.visible = bool(self.photo_data)
        self.camera_hint.visible = not bool(self.photo_data)
        self.connect_button.content = "Переснять" if self.photo_data else "Открыть камеру"
        self.connect_button.visible = True
        self.resize()

    async def open_camera(self, event=None):
        if self.busy or not self.require_login():
            return
        token = self.token
        self.set_busy(True)
        self.camera_slot.controls = [self.camera]
        self.camera_hint.visible = False
        self.resize()
        try:
            cameras = await self.camera.get_available_cameras()
            if token != self.token or not self.require_login():
                return
            if not cameras:
                raise ValueError("Камера не найдена. Можно выбрать фото из галереи.")
            camera = next((c for c in cameras if getattr(c, "lens_direction", None) == fc.CameraLensDirection.BACK), cameras[0]) if hasattr(fc, "CameraLensDirection") else cameras[0]
            await self.camera.initialize(description=camera, resolution_preset=fc.ResolutionPreset.HIGH, enable_audio=False)
            if token != self.token or not self.require_login():
                return
            self.camera_ready = True
            self.capture_button.visible = True
            self.connect_button.visible = False
            self.preview.visible = False
            self.draft.visible = False
        except ValueError as exc:
            self.release_camera()
            self.tell(str(exc), True)
        except Exception:
            logger.warning("Camera could not be opened", exc_info=True)
            self.release_camera()
            self.tell("Не удалось открыть камеру. Разреши доступ в браузере или выбери фото из галереи.", True)
        finally:
            self.set_busy(False)

    async def take_photo(self, event=None):
        if self.busy or not self.camera_ready or not self.require_login():
            return
        token = self.token
        self.set_busy(True)
        try:
            captured = await self.camera.take_picture()
            data = await asyncio.to_thread(media.normalize_photo, bytes(captured or b""))
            if token == self.token and self.require_login():
                self.accept_photo(data)
        except ValueError as exc:
            self.tell(str(exc), True)
        except Exception:
            logger.warning("Camera capture failed", exc_info=True)
            self.tell("Снимок не получился. Попробуй ещё раз или выбери фото из галереи.", True)
        finally:
            self.set_busy(False)

    async def pick_photo(self, event=None):
        if self.busy or not self.require_login():
            return
        token = self.token
        self.set_busy(True)
        try:
            files = await self.picker.pick_files(file_type=ft.FilePickerFileType.CUSTOM,
                allowed_extensions=["jpg", "jpeg", "png", "webp"], allow_multiple=False,
                with_data=True, cancel_upload_on_window_blur=False)
            if not files:
                return
            file = files[0]
            if file.size > media.MAX_PHOTO_BYTES:
                raise ValueError("Фотография должна быть не больше 8 МБ")
            raw = file.bytes
            if raw is None and file.path:
                with Path(file.path).open("rb") as stream:
                    raw = stream.read(media.MAX_PHOTO_BYTES + 1)
            data = await asyncio.to_thread(media.normalize_photo, bytes(raw or b""))
            if token == self.token and self.require_login():
                self.accept_photo(data)
        except ValueError as exc:
            self.tell(str(exc), True)
        except Exception:
            logger.warning("Photo picker failed", exc_info=True)
            self.tell("Не удалось открыть фотографию. Попробуй другой файл.", True)
        finally:
            self.set_busy(False)

    def accept_photo(self, data):
        self.photo_data = data
        self.release_camera()
        self.preview.controls = [self.image(data, square=False)]
        self.preview.visible = True
        self.draft.visible = True
        self.camera_hint.visible = False
        self.notice.visible = False
        self.page.update()

    def set_rating(self, value):
        self.rating = value
        self.rating_error.visible = False
        for index, button in enumerate(self.rating_buttons, 1):
            button.icon = ft.Icons.STAR_ROUNDED if index <= value else ft.Icons.STAR_BORDER_ROUNDED
            button.icon_color = ACCENT if index <= value else MUTED
        self.page.update()

    def reset_draft(self):
        self.photo_data = None
        self.rating = None
        self.comment.value = ""
        self.comment.error_text = None
        self.rating_error.visible = False
        self.preview.controls.clear()
        self.preview.visible = False
        self.draft.visible = False
        self.camera_hint.visible = True
        self.connect_button.content = "Открыть камеру"
        for button in self.rating_buttons:
            button.icon = ft.Icons.STAR_BORDER_ROUNDED
            button.icon_color = MUTED

    def discard_draft(self, event=None):
        if not self.busy:
            self.reset_draft()
            self.page.update()

    async def publish(self, event=None):
        if self.busy or not self.require_login():
            return
        text = (self.comment.value or "").strip()
        self.comment.error_text = "Не более 30 символов" if len(text) > 30 else None
        self.rating_error.value = "Выбери оценку от 1 до 5"
        self.rating_error.visible = self.rating not in range(1, 6) if isinstance(self.rating, int) else True
        if not self.photo_data:
            self.tell("Сначала сделай снимок или выбери фото.", True)
            return
        if self.comment.error_text or self.rating_error.visible:
            self.page.update()
            return
        token, user_id, data, rating = self.token, self.user["id"], self.photo_data, self.rating
        def store():
            session_user = auth.resume_session(token)
            if not session_user or session_user["id"] != user_id:
                raise ValueError("Войди в аккаунт ещё раз")
            path = media.save_photo(data)
            try:
                return db.save_post(path, rating, text, user_id)
            except Exception:
                media.delete_photo(path)
                raise
        self.set_busy(True)
        try:
            await asyncio.to_thread(store)
            if token == self.token and self.require_login():
                self.reset_draft()
                self.feed_mode = "friends"
                self.set_busy(False)
                self.show_screen(0)
                self.tell("Вкусом поделились!")
        except ValueError as exc:
            self.tell(str(exc), True)
        except (OSError, sqlite3.Error):
            logger.exception("Could not publish a post")
            self.tell("Публикация не сохранилась. Фото осталось в черновике — попробуй ещё раз.", True)
        finally:
            self.set_busy(False)

    def load_profile(self):
        if not self.require_login():
            return
        self.profile_heading.value = self.user["display_name"]
        self.profile_login.value = f"@{self.user['username']}"
        self.profile_name.value = self.user["display_name"]
        self.profile_avatar.controls = [avatar(self.user["display_name"], 64)]
        try:
            stats = db.get_stats(self.user["id"])
            self.stats_posts.value = str(stats["posts"])
            self.stats_friends.value = str(stats["friends"])
        except sqlite3.Error:
            self.tell("Не удалось загрузить профиль. Попробуй ещё раз.", True)

    def save_profile(self, event=None):
        if self.busy or not self.require_login():
            return
        try:
            if not db.update_display_name(self.user["id"], self.profile_name.value or ""):
                raise ValueError("Аккаунт не найден")
        except ValueError as exc:
            self.profile_name.error_text = str(exc)
            self.page.update()
            return
        except sqlite3.Error:
            self.tell("Не удалось сохранить имя. Попробуй ещё раз.", True)
            return
        self.profile_name.error_text = None
        self.load_profile()
        self.tell("Имя сохранено")

    def password_dialog(self, event=None):
        if self.busy or not self.require_login():
            return
        current = text_field("Текущий пароль", password=True, can_reveal_password=True, on_change=sync_text)
        new = text_field("Новый пароль", password=True, can_reveal_password=True, on_change=sync_text)
        repeat = text_field("Повтори новый пароль", password=True, can_reveal_password=True, on_change=sync_text)
        error = ft.Text("", color=ERROR, visible=False)
        async def save(event):
            if self.busy or not self.require_login():
                return
            if (new.value or "") != (repeat.value or ""):
                error.value = "Пароли не совпадают"
                error.visible = True
                self.page.update()
                return
            values = (self.user["id"], current.value or "", new.value or "")
            self.set_busy(True)
            save_button.disabled = True
            cancel_button.disabled = True
            self.page.update()
            try:
                await asyncio.to_thread(auth.change_password, *values)
            except ValueError as exc:
                error.value = str(exc)
                error.visible = True
            except sqlite3.Error:
                error.value = "Не удалось сменить пароль. Попробуй ещё раз."
                error.visible = True
            else:
                current.value = new.value = repeat.value = ""
                self.page.pop_dialog()
                try:
                    await self.preferences.remove(auth.SESSION_STORAGE_KEY)
                except Exception:
                    pass
                self.clear_login("Пароль изменён. Войди с новым паролем.")
            finally:
                save_button.disabled = False
                cancel_button.disabled = False
                self.set_busy(False)
        save_button = ft.Button(content="Сменить пароль", on_click=save)
        cancel_button = ft.TextButton(content="Отмена", on_click=lambda e: None if self.busy else self.page.pop_dialog())
        self.page.show_dialog(ft.AlertDialog(modal=True, title=ft.Text("Смена пароля"),
            content=stack([current, new, repeat, error], tight=True),
            actions=[cancel_button, save_button]))


async def main(page: ft.Page):
    app = Application(page)
    await app.start()


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    if os.environ.get("DT_HEADLESS") == "1":
        os.environ["FLET_FORCE_WEB_SERVER"] = "1"
    ft.run(main, host=os.environ.get("DT_HOST", "127.0.0.1"), port=int(os.environ.get("PORT", "8550")),
           view=ft.AppView.WEB_BROWSER)
