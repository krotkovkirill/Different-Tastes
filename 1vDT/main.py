import asyncio
import base64
import sqlite3
from pathlib import Path
from uuid import uuid4

from database import DATA_DIR, init_db, save_post, get_feed, delete_post, update_post

import flet as ft
import flet_camera as fc

from auth import create_session, resume_session, end_session, SESSION_STORAGE_KEY
from auth_ui import create_auth_form
from friends_ui import create_friends_panel


async def main(page: ft.Page):
    init_db()
    photos_dir = DATA_DIR / "photos"
    photos_dir.mkdir(parents=True, exist_ok=True)

    page.title = "Different Tastes"
    page.scroll = ft.ScrollMode.AUTO
    page.theme_mode = ft.ThemeMode.LIGHT
    page.theme = ft.Theme(
        color_scheme_seed="#176B5B",
        text_theme=ft.TextTheme(
            body_medium=ft.TextStyle(size=18),
            body_large=ft.TextStyle(size=18),
            label_large=ft.TextStyle(size=18, weight=ft.FontWeight.W_600),
        ),
        button_theme=ft.ButtonTheme(style=ft.ButtonStyle(
            bgcolor={ft.ControlState.DEFAULT: "#176B5B", ft.ControlState.DISABLED: "#D5DDD8"},
            color={ft.ControlState.DEFAULT: "#FFFFFF", ft.ControlState.DISABLED: "#63716A"},
            text_style=ft.TextStyle(size=18, weight=ft.FontWeight.W_600),
            shape=ft.RoundedRectangleBorder(radius=16),
        )),
        navigation_bar_theme=ft.NavigationBarTheme(
            label_text_style=ft.TextStyle(size=16, weight=ft.FontWeight.W_600),
            height=80,
        ),
    )
    page.bgcolor = "#F7F8FA"
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.padding = 0

    preferences = ft.SharedPreferences()
    current_token = None
    current_user = None
    title = ft.Text("different tastes", size=26, weight=ft.FontWeight.BOLD, expand=True, max_lines=1)
    status = ft.Text("", size=18, visible=False)
    camera = fc.Camera()
    photo_bytes = None
    preview = ft.Column(horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
    comment = ft.TextField(
        label="Отзыв:",
        text_size=18,
    )
    rating = ft.Dropdown(
        label="Оценка",
        options=[ft.DropdownOption(key=str(value), text=str(value)) for value in range(1, 6)],
        text_size=18,
    )
    feed = ft.Column(spacing=20, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
    empty_feed = ft.Container(
        padding=ft.Padding.symmetric(vertical=32),
        content=ft.Column(controls=[
            ft.Container(
                content=ft.Icon(ft.Icons.CAMERA_ALT_OUTLINED, size=64, color="#176B5B"),
                bgcolor="#E7F1EB", width=128, height=128,
                alignment=ft.Alignment.CENTER, border_radius=36,
            ),
            ft.Text("Пока нет снимков", size=32, weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER),
            ft.Column(controls=[
                ft.Button(content="Сделать снимок", height=56, on_click=lambda event: show_screen(1)),
                ft.TextButton(content="Добавить друзей", height=56, on_click=lambda event: show_screen(2)),
            ], horizontal_alignment=ft.CrossAxisAlignment.STRETCH, spacing=8),
        ], spacing=28, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
    )

    def set_status(message):
        status.value = message
        status.visible = bool(message)

    def make_image(image_bytes, fill=False):
        return ft.Image(
            src=base64.b64encode(image_bytes).decode("ascii"),
            aspect_ratio=1 if fill else 4 / 3,
            fit=ft.BoxFit.CONTAIN,
            error_content=ft.Text("Не удалось отобразить фотографию"),
        )

    def remove_post(post_id):
        if not require_login():
            return
        try:
            saved_path = delete_post(post_id, current_user["id"])
        except sqlite3.Error as error:
            set_status(f"Не удалось удалить публикацию: {error}")
            page.update()
            return

        set_status("Публикация удалена" if saved_path else "Публикация не найдена или недоступна")
        if saved_path:
            try:
                photo_path = Path(saved_path).resolve()
                if photo_path.parent != photos_dir.resolve():
                    raise OSError("Фотография находится вне папки снимков")
                photo_path.unlink(missing_ok=True)
            except OSError:
                set_status("Пост удалён, но файл фотографии удалить не удалось")

        load_feed()
        page.update()

    def edit_post(post):
        if not require_login() or post["user_id"] != current_user["id"]:
            return
        edit_comment = ft.TextField(label="Отзыв:", value=post["comment"], text_size=18)
        edit_rating = ft.Dropdown(
            label="Оценка",
            value=str(post["rating"]),
            options=[ft.DropdownOption(key=str(value), text=str(value)) for value in range(1, 6)],
            text_size=18,
        )
        edit_error = ft.Text(color="red")

        def cancel_edit(event):
            page.pop_dialog()

        def save_edit(event):
            if not require_login():
                page.pop_dialog()
                return
            text = (edit_comment.value or "").strip()
            edit_comment.error_text = None
            edit_rating.error_text = None
            edit_error.value = ""

            if len(text) > 30:
                edit_comment.error_text = "Не более 30 символов"
            if edit_rating.value not in {"1", "2", "3", "4", "5"}:
                edit_rating.error_text = "Выбери оценку от 1 до 5"
            if edit_comment.error_text or edit_rating.error_text:
                page.update()
                return

            try:
                updated = update_post(post["id"], int(edit_rating.value), text, current_user["id"])
            except sqlite3.Error as error:
                edit_error.value = f"Не удалось сохранить изменения: {error}"
                page.update()
                return

            page.pop_dialog()
            set_status("Публикация обновлена" if updated else "Публикация не найдена или недоступна")
            load_feed()
            page.update()

        page.show_dialog(
            ft.AlertDialog(
                modal=True,
                title=ft.Text("Редактировать публикацию"),
                content=ft.Column(
                    controls=[edit_comment, edit_rating, edit_error],
                    tight=True,
                    spacing=16,
                    horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                ),
                actions=[
                    ft.TextButton(content="Отмена", on_click=cancel_edit),
                    ft.Button(content="Сохранить", on_click=save_edit),
                ],
            )
        )

    def make_post_card(post):
        is_owner = current_user is not None and post["user_id"] == current_user["id"]
        author = post["display_name"]
        avatar = ft.Container(
            content=ft.Text(author[:1].upper(), color="#176B5B", size=22, weight=ft.FontWeight.BOLD),
            width=48,
            height=48,
            alignment=ft.Alignment.CENTER,
            bgcolor="#E7F1EB",
            border_radius=24,
        )
        actions = ft.PopupMenuButton(
            icon=ft.Icons.MORE_HORIZ,
            tooltip="Действия с публикацией",
            width=48, height=48, icon_size=28,
            visible=is_owner,
            items=[
                ft.PopupMenuItem(content="Редактировать", icon=ft.Icons.EDIT_OUTLINED, height=52, on_click=lambda event: edit_post(post)),
                ft.PopupMenuItem(content="Удалить", icon=ft.Icons.DELETE_OUTLINE, height=52, on_click=lambda event: remove_post(post["id"])),
            ],
        )
        image = make_image(post["photo"], fill=True) if post["photo"] else ft.Container(
            aspect_ratio=1,
            alignment=ft.Alignment.CENTER,
            content=ft.Column(controls=[
                ft.Icon(ft.Icons.IMAGE_NOT_SUPPORTED_OUTLINED, color="#63716A", size=36),
                ft.Text("Фото недоступно", color="#63716A"),
            ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
        )
        rating_badge = ft.Container(
            bgcolor="#E7F1EB",
            border_radius=14,
            padding=ft.Padding.symmetric(horizontal=12, vertical=8),
            content=ft.Row(controls=[
                ft.Icon(ft.Icons.STAR_ROUNDED, color="#176B5B", size=26),
                ft.Text(f"{post['rating']} / 5", color="#176B5B", weight=ft.FontWeight.BOLD, size=24),
            ], spacing=6, tight=True),
        )
        return ft.Container(
            bgcolor="#FFFFFF",
            border=ft.Border.all(1, "#E2E8E5"),
            border_radius=24,
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            content=ft.Column(controls=[
                ft.Container(
                    padding=16,
                    content=ft.Row(controls=[
                        avatar,
                        ft.Text(author, size=22, weight=ft.FontWeight.BOLD, expand=True,
                                max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, tooltip=f"@{post['username']}"),
                        actions,
                    ], spacing=10),
                ),
                ft.Container(content=image, bgcolor="#F0F3F1"),
                ft.Container(
                    padding=16,
                    content=ft.Column(controls=[
                        ft.Row(controls=[rating_badge]),
                        *([ft.Text(post["comment"], size=22, color="#202A25")] if post["comment"] else []),
                    ], spacing=12),
                ),
            ], spacing=0, horizontal_alignment=ft.CrossAxisAlignment.STRETCH),
        )

    def load_feed(event=None):
        if not require_login():
            return
        try:
            posts = get_feed(current_user["id"])
        except sqlite3.Error as error:
            set_status(f"Не удалось загрузить ленту: {error}")
            page.update()
            return

        feed.controls.clear()
        for post in posts:
            try:
                post["photo"] = Path(post["photo_path"]).read_bytes()
            except OSError:
                post["photo"] = None
            feed.controls.append(make_post_card(post))
        empty_feed.visible = not bool(posts)
        page.update()

    async def open_camera(event):
        if not require_login():
            return
        camera_button.disabled = True
        logout_button.disabled = True
        photo_button.disabled = True
        set_status("Подключение камеры")
        page.update()
        camera_ready = False

        try:
            cameras = await camera.get_available_cameras()
            if not cameras:
                set_status("Камера не найдена")
            else:
                await camera.initialize(
                    description=cameras[0],
                    resolution_preset=fc.ResolutionPreset.MEDIUM,
                    enable_audio=False,
                )
                camera_ready = True
                set_status("Камера подключена")
        except Exception as error:
            set_status(f"Ошибка подключения камеры: {error}")
        finally:
            logout_button.disabled = False
            camera_button.disabled = camera_ready
            photo_button.disabled = not camera_ready
            page.update()

    async def take_photo(event):
        nonlocal photo_bytes
        if not require_login():
            return
        photo_button.disabled = True
        logout_button.disabled = True
        draft_form.disabled = True
        page.update()
        try:
            captured = await camera.take_picture()
            if not captured:
                raise ValueError("Камера вернула пустой снимок")
            if not require_login():
                return
            photo_bytes = bytes(captured)
            preview.controls = [make_image(photo_bytes)]
            draft_form.visible = True
            photo_button.content = "Переснять"
            set_status("Добавь подпись и оценку")
        except Exception as error:
            set_status(f"Ошибка при съёмке: {error}")
        finally:
            logout_button.disabled = False
            photo_button.disabled = False
            draft_form.disabled = False
            page.update()

    def reset_draft():
        nonlocal photo_bytes
        photo_bytes = None
        preview.controls.clear()
        comment.value = ""
        comment.error_text = None
        rating.value = None
        rating.error_text = None
        draft_form.visible = False
        photo_button.content = "Сделать снимок"

    def clear_photo(event):
        reset_draft()
        set_status("Можно сделать новый снимок")
        page.update()

    def publish_post(event):
        if not require_login():
            return
        text = (comment.value or "").strip()
        comment.error_text = None
        rating.error_text = None

        if photo_bytes is None:
            set_status("Сначала сделай снимок")
            page.update()
            return

        if len(text) > 30:
            comment.error_text = "Не более 30 символов"
        if rating.value not in {"1", "2", "3", "4", "5"}:
            rating.error_text = "Выбери оценку от 1 до 5"
        if comment.error_text or rating.error_text:
            page.update()
            return

        post = {
            "user_id": current_user["id"],
            "photo": photo_bytes,
            "rating": int(rating.value),
            "comment": text,
        }
        photo_path = photos_dir / f"{uuid4().hex}.bin"
        try:
            photo_path.write_bytes(photo_bytes)
            post["id"] = save_post(photo_path, post["rating"], post["comment"], current_user["id"])
        except (OSError, sqlite3.Error) as error:
            try:
                photo_path.unlink(missing_ok=True)
            except OSError:
                pass
            set_status(f"Не удалось сохранить публикацию: {error}")
            page.update()
            return

        reset_draft()
        load_feed()
        set_status("Публикация сохранена")
        show_screen(0)

    camera_button = ft.Button(content="Подключить камеру", height=56, on_click=open_camera)
    photo_button = ft.Button(
        content="Сделать снимок", height=56, on_click=take_photo, disabled=True
    )
    draft_form = ft.Column(
        controls=[
            preview,
            comment,
            rating,
            ft.Button(content="Опубликовать", height=56, on_click=publish_post),
            ft.TextButton(content="Убрать снимок", height=56, on_click=clear_photo),
        ],
        visible=False,
        spacing=16,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
    )
    def show_screen(index):
        if not require_login():
            return
        navigation.selected_index = index
        feed_screen.visible = index == 0
        camera_screen.visible = index == 1
        friends_screen.visible = index == 2
        if index == 0:
            load_feed()
        page.update()

    def navigate(event):
        show_screen(event.control.selected_index)

    def clear_login():
        nonlocal current_user, current_token, auth_form, camera
        current_user = None
        current_token = None
        reset_draft()
        feed.controls.clear()
        friends_slot.controls.clear()
        empty_feed.visible = True
        logout_button.visible = False
        set_status("")
        app_content.visible = False
        navigation.visible = False
        camera_slot.controls.clear()
        camera = fc.Camera()
        resize_layout()
        camera_button.disabled = False
        photo_button.disabled = True
        auth_form = create_auth_form(page, on_authenticated)
        auth_slot.controls = [auth_form]
        auth_slot.visible = True
        page.update()

    def require_login():
        if current_user is None or current_token is None:
            return False
        try:
            user = resume_session(current_token)
        except sqlite3.Error:
            set_status("Не удалось проверить вход. Повтори попытку.")
            page.update()
            return False
        if user is None or user["id"] != current_user["id"]:
            clear_login()
            auth_form.controls[4].value = "Вход завершён. Войди снова."
            page.update()
            return False
        return True

    async def logout(event):
        if logout_button.disabled:
            return
        logout_button.disabled = True
        page.update()
        try:
            await asyncio.to_thread(end_session, current_token)
        except sqlite3.Error:
            set_status("Не удалось выйти из аккаунта. Попробуй ещё раз.")
            logout_button.disabled = False
            page.update()
            return
        try:
            await preferences.remove(SESSION_STORAGE_KEY)
        except Exception:
            pass
        clear_login()
        logout_button.disabled = False
        page.update()

    async def on_authenticated(user):
        nonlocal current_token
        token = await asyncio.to_thread(create_session, user["id"])
        try:
            saved = await preferences.set(SESSION_STORAGE_KEY, token)
        except Exception:
            saved = False
        current_token = token
        activate_user(user)
        if not saved:
            set_status("Вход выполнен. Браузер не смог сохранить его для следующего запуска.")
            page.update()

    def activate_user(user):
        nonlocal current_user
        current_user = user
        logout_button.visible = True
        logout_button.tooltip = f"Выйти: @{user['username']}"
        auth_slot.visible = False
        app_content.visible = True
        navigation.visible = True
        camera_slot.controls = [camera]
        friends_slot.controls = [create_friends_panel(page, user, on_change=load_feed, is_authenticated=require_login)]
        show_screen(0)

    friends_slot = ft.Column(horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
    camera_slot = ft.Column(controls=[camera], horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
    auth_form = create_auth_form(page, on_authenticated)
    auth_form.disabled = True
    auth_slot = ft.Column(controls=[auth_form], visible=False, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
    loading = ft.ProgressRing(width=32, height=32)
    logout_button = ft.IconButton(icon=ft.Icons.LOGOUT, tooltip="Выйти из аккаунта", width=48, height=48, icon_size=26, visible=False, on_click=logout)
    feed_screen = ft.Column(controls=[
        ft.Row(controls=[
            ft.Text("Лента", size=32, weight=ft.FontWeight.BOLD, expand=True),
            ft.IconButton(icon=ft.Icons.REFRESH_ROUNDED, tooltip="Обновить ленту", icon_color="#176B5B", width=48, height=48, icon_size=28, on_click=load_feed),
        ]),
        empty_feed,
        feed,
    ], spacing=16, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
    camera_screen = ft.Column(controls=[
        ft.Text("Камера", size=32, weight=ft.FontWeight.BOLD),
        camera_button,
        camera_slot,
        photo_button,
        draft_form,
    ], visible=False, spacing=16, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
    friends_screen = ft.Column(controls=[friends_slot], visible=False, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
    navigation = ft.NavigationBar(
        destinations=[
            ft.NavigationBarDestination(icon=ft.Icons.HOME_OUTLINED, selected_icon=ft.Icons.HOME, label="Лента"),
            ft.NavigationBarDestination(icon=ft.Icons.CAMERA_ALT_OUTLINED, selected_icon=ft.Icons.CAMERA_ALT, label="Камера"),
            ft.NavigationBarDestination(icon=ft.Icons.PEOPLE_OUTLINE, selected_icon=ft.Icons.PEOPLE, label="Друзья"),
        ],
        selected_index=0,
        visible=False,
        on_change=navigate,
    )
    page.navigation_bar = navigation
    app_content = ft.Column(controls=[
        status,
        feed_screen,
        camera_screen,
        friends_screen,
    ], visible=False, spacing=20, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
    root_view = ft.Container(
        content=ft.Column(controls=[
            ft.Row(controls=[title, logout_button], spacing=12),
            loading,
            auth_slot,
            app_content,
        ], spacing=24, horizontal_alignment=ft.CrossAxisAlignment.STRETCH),
    )

    def resize_layout(event=None):
        viewport_width = getattr(page, "width", None) or 390
        gutter = 24 if viewport_width >= 600 else 16
        root_view.width = min(viewport_width, 760)
        root_view.padding = ft.Padding.symmetric(horizontal=gutter, vertical=20)
        camera.width = max(1, root_view.width - 2 * gutter)
        camera.height = camera.width * 3 / 4
        page.update()

    page.on_resize = resize_layout
    page.add(root_view)
    resize_layout()
    try:
        token = await preferences.get(SESSION_STORAGE_KEY)
        user = await asyncio.to_thread(resume_session, token)
        if user is not None:
            current_token = token
            activate_user(user)
        elif token is not None:
            await preferences.remove(SESSION_STORAGE_KEY)
    except Exception:
        auth_form.controls[4].value = "Не удалось восстановить вход. Войди ещё раз."
    finally:
        loading.visible = False
        auth_form.disabled = False
        auth_slot.visible = current_user is None
        page.update()


if __name__ == "__main__":
    ft.run(main, view=ft.AppView.WEB_BROWSER)
