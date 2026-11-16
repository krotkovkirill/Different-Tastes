import asyncio
import hashlib
import io
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "1vDT"))

from PIL import Image
import flet as ft
import auth
import database as db
import main
import media


def photo_bytes(size=(80, 60), mode="RGB"):
    stream = io.BytesIO()
    Image.new(mode, size, "red").save(stream, format="PNG")
    return stream.getvalue()


class DatabaseCase(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.data_patch = patch.object(db, "DATA_DIR", Path(self.directory.name))
        self.path_patch = patch.object(db, "DB_PATH", Path(self.directory.name) / "test.db")
        self.data_patch.start()
        self.path_patch.start()
        self.addCleanup(self.directory.cleanup)
        self.addCleanup(self.data_patch.stop)
        self.addCleanup(self.path_patch.stop)
        db.init_db()
        self.a = db.create_user("alice", auth.hash_password("old-password"))
        self.b = db.create_user("bob", auth.hash_password("other-password"))
        self.c = db.create_user("chris", "unused")

    def test_friendship_permissions(self):
        with self.assertRaises(ValueError):
            db.send_friend_request(self.a, self.a)
        request = db.send_friend_request(self.a, self.b)
        for pair in ((self.a, self.b), (self.b, self.a)):
            with self.assertRaises(ValueError):
                db.send_friend_request(*pair)
        self.assertFalse(db.respond_friend_request(request, self.a, True))
        self.assertFalse(db.respond_friend_request(request, self.c, True))
        self.assertFalse(db.remove_friendship(request, self.c))
        self.assertTrue(db.respond_friend_request(request, self.b, True))
        self.assertEqual(db.get_friendships(self.b)[0]["user_id"], self.a)
        self.assertTrue(db.remove_friendship(request, self.b))
        self.assertEqual(db.get_friendships(self.a), [])
        request = db.send_friend_request(self.a, self.b)
        self.assertTrue(db.respond_friend_request(request, self.b, False))
        request = db.send_friend_request(self.b, self.a)
        self.assertTrue(db.remove_friendship(request, self.b))

    def test_feed_privacy_pagination_and_ownership(self):
        ids = [db.save_post("photos/test.jpg", 4, "", user) for user in (self.a, self.b, self.c, self.a)]
        request = db.send_friend_request(self.a, self.b)
        self.assertEqual([p["id"] for p in db.get_feed(self.a)], [ids[3], ids[0]])
        db.respond_friend_request(request, self.b, True)
        self.assertEqual([p["id"] for p in db.get_feed(self.a, 2)], [ids[3], ids[1]])
        self.assertEqual([p["id"] for p in db.get_feed(self.a, 2, ids[1])], [ids[0]])
        self.assertEqual([p["id"] for p in db.get_feed(self.a, own_only=True)], [ids[3], ids[0]])
        self.assertFalse(db.update_post(ids[1], 1, "bad", self.a))
        self.assertIsNone(db.delete_post(ids[1], self.a))
        self.assertTrue(db.update_post(ids[0], 5, "good", self.a))
        self.assertEqual(db.delete_post(ids[0], self.a), "photos/test.jpg")
        db.remove_friendship(request, self.b)
        self.assertEqual([p["id"] for p in db.get_feed(self.a)], [ids[3]])

    def test_post_validation(self):
        for rating in (0, 6, True, "5"):
            with self.assertRaises(ValueError):
                db.save_post("test", rating, "", self.a)
        with self.assertRaises(ValueError):
            db.save_post("test", 4, "a" * 31, self.a)
        with self.assertRaises(sqlite3.IntegrityError):
            db.save_post("test", 4, "", 9999)
        db.save_post("test", 4, " " * 3, self.a)
        self.assertEqual(db.get_posts(self.a)[0]["comment"], "")

    def test_auth_validation_and_legacy_login(self):
        self.assertEqual(auth.login_user(" ALICE ", "old-password")["id"], self.a)
        with self.assertRaisesRegex(ValueError, "Неверный пароль"):
            auth.sign_in("alice", "new-password")
        short = auth.sign_in("я ✨", "1")
        self.assertEqual(auth.sign_in("Я ✨", "1")["id"], short["id"])
        self.assertEqual(db.find_user("я ✨", self.a)["id"], short["id"])
        self.assertEqual(auth.sign_in("@ник", "p")["id"], db.find_user("@ник", self.a)["id"])
        long_nick, long_password = "n" * 160, "🔑" * 160
        long_user = auth.sign_in(long_nick, long_password)
        self.assertEqual(auth.sign_in(long_nick, long_password)["id"], long_user["id"])
        with self.assertRaisesRegex(ValueError, "Неверный пароль"):
            auth.sign_in("я ✨", "wrong")
        self.assertEqual(auth.sign_in("я ✨", "1")["id"], short["id"])
        for nickname, password in (("  ", "test"), ("empty_password", "")):
            with self.assertRaises(ValueError):
                auth.sign_in(nickname, password)
        self.assertIsNone(db.get_user_by_username("empty_password"))
        user = auth.sign_in("new_user", "new-password")
        self.assertEqual(user["username"], "new_user")
        self.assertNotIn("password_hash", user)
        old_id = db.create_user("legacy", auth.hash_password("1234"))
        self.assertEqual(auth.login_user("legacy", "1234")["id"], old_id)
        self.assertFalse(auth.verify_password("invalid", "password"))

    def test_rate_limit_and_expiry(self):
        with patch.object(auth.time, "time", return_value=1000):
            for _ in range(5):
                with self.assertRaises(ValueError):
                    auth.login_user("alice", "wrong")
            with self.assertRaisesRegex(ValueError, "попыток"):
                auth.login_user("alice", "old-password")
        with patch.object(auth.time, "time", return_value=1300):
            self.assertEqual(auth.login_user("alice", "old-password")["id"], self.a)

    def test_sessions_and_password_change(self):
        with patch.object(auth.time, "time", return_value=1000):
            token = auth.create_session(self.a)
            self.assertEqual(auth.resume_session(token)["id"], self.a)
            with db.transaction() as connection:
                row = connection.execute("SELECT * FROM sessions").fetchone()
            self.assertEqual(row["token_hash"], hashlib.sha256(token.encode()).hexdigest())
            self.assertNotEqual(row["token_hash"], token)
        with patch.object(auth.time, "time", return_value=1000 + auth.SESSION_TTL):
            self.assertIsNone(auth.resume_session(token))
        current = auth.create_session(self.a)
        other = auth.create_session(self.a)
        with self.assertRaises(ValueError):
            auth.change_password(self.a, "wrong-password", "changed-password")
        self.assertIsNotNone(auth.resume_session(current))
        auth.change_password(self.a, "old-password", "changed-password")
        self.assertIsNone(auth.resume_session(current))
        self.assertIsNone(auth.resume_session(other))
        self.assertEqual(auth.login_user("alice", "changed-password")["id"], self.a)
        for value in (None, 123, "invalid", "x" * 43, "\ud800" * 43):
            self.assertIsNone(auth.resume_session(value))
        current = auth.create_session(self.a)
        auth.end_session(current)
        self.assertIsNone(auth.resume_session(current))

    def test_profile_and_search_return_public_fields(self):
        self.assertEqual(db.find_user("@ALICE", self.b)["username"], "alice")
        self.assertIsNone(db.find_user("alice", self.a))
        self.assertNotIn("password_hash", db.find_user("alice", self.b))
        self.assertEqual(db.get_stats(self.a), {"posts": 0, "friends": 0})
        with db.transaction() as connection:
            self.assertEqual({row[1] for row in connection.execute("PRAGMA table_info(users)")},
                             {"id", "username", "password_hash"})

    def test_photo_normalization_and_paths(self):
        normalized = media.normalize_photo(photo_bytes((2000, 1000)))
        with Image.open(io.BytesIO(normalized)) as image:
            self.assertEqual(image.format, "JPEG")
            self.assertEqual(image.size, (1600, 800))
            self.assertFalse(image.getexif())
        stored = media.save_photo(normalized)
        self.assertFalse(Path(stored).is_absolute())
        self.assertEqual(media.read_photo(stored), normalized)
        with self.assertRaises(ValueError):
            media.photo_file("../outside.jpg")
        with self.assertRaises(ValueError):
            media.photo_file("/etc/passwd")
        legacy = f"/old/location/photos/{Path(stored).name}"
        self.assertEqual(media.read_photo(legacy), normalized)
        media.delete_photo(stored)
        self.assertFalse(media.photo_file(stored).exists())
        for invalid in (b"", b"not an image", b"a" * (media.MAX_PHOTO_BYTES + 1)):
            with self.assertRaises(ValueError):
                media.normalize_photo(invalid)
        with patch.object(Image, "MAX_IMAGE_PIXELS", 1):
            with self.assertRaises(ValueError):
                media.normalize_photo(photo_bytes())

    def test_orientation_and_metadata_are_normalized(self):
        image = Image.new("RGB", (40, 80), "blue")
        exif = image.getexif()
        exif[274] = 6
        exif[270] = "private metadata"
        stream = io.BytesIO()
        image.save(stream, format="JPEG", exif=exif)
        normalized = media.normalize_photo(stream.getvalue())
        with Image.open(io.BytesIO(normalized)) as result:
            self.assertEqual(result.size, (80, 40))
            self.assertFalse(result.getexif())

    def test_simple_user_migration_preserves_accounts_and_links(self):
        post_id = db.save_post("photos/example.jpg", 4, "test", self.a)
        request_id = db.send_friend_request(self.a, self.b)
        db.respond_friend_request(request_id, self.b, True)
        token = auth.create_session(self.a)
        original_hash = db.get_user(self.a)["password_hash"]
        with db.transaction() as connection:
            connection.execute("ALTER TABLE users ADD COLUMN display_name TEXT NOT NULL DEFAULT 'Old name'")
            connection.execute("ALTER TABLE users ADD COLUMN created_at TEXT NOT NULL DEFAULT '2026-01-01'")
        db.init_db()
        db.init_db()
        self.assertEqual(auth.sign_in("alice", "old-password")["id"], self.a)
        self.assertEqual(db.get_user(self.a)["password_hash"], original_hash)
        self.assertEqual(auth.resume_session(token)["id"], self.a)
        self.assertEqual(db.get_feed(self.b)[0]["id"], post_id)
        self.assertEqual(db.get_stats(self.a)["friends"], 1)
        with db.transaction() as connection:
            self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])
            self.assertEqual({row[1] for row in connection.execute("PRAGMA table_info(users)")},
                             {"id", "username", "password_hash"})
        backups = list((db.DATA_DIR / "backups").glob("*.db"))
        self.assertEqual(len(backups), 1)
        with sqlite3.connect(backups[0]) as connection:
            self.assertIn("display_name", {row[1] for row in connection.execute("PRAGMA table_info(users)")})

    def test_iphone_heic_is_normalized(self):
        source = io.BytesIO()
        Image.new("RGB", (120, 80), "blue").save(source, format="HEIF")
        data = media.normalize_photo(source.getvalue())
        with Image.open(io.BytesIO(data)) as image:
            self.assertEqual(image.format, "JPEG")
            self.assertEqual(image.size, (120, 80))
            self.assertFalse(image.getexif())

    def test_legacy_migration_preserves_unowned_posts(self):
        with db.transaction() as connection:
            connection.execute("DROP TABLE posts")
            connection.execute("CREATE TABLE posts(id INTEGER PRIMARY KEY, photo_path TEXT, rating INTEGER, comment TEXT, created_at TEXT)")
            connection.execute("INSERT INTO posts VALUES (1, 'old.bin', 4, '', CURRENT_TIMESTAMP)")
        db.init_db()
        db.init_db()
        self.assertEqual(db.get_feed(self.a), [])
        with db.transaction() as connection:
            self.assertEqual(connection.execute("SELECT count(*) FROM posts").fetchone()[0], 1)


class Preferences:
    values = {}
    fail_set = False
    fail_remove = False

    async def get(self, key):
        return self.values.get(key)

    async def set(self, key, value):
        if self.fail_set:
            return False
        self.values[key] = value
        return True

    async def remove(self, key):
        if self.fail_remove:
            raise RuntimeError("blocked storage")
        return self.values.pop(key, None) is not None


class Page:
    width = 390

    def add(self, *controls):
        self.controls = list(controls)

    def update(self):
        pass

    def show_dialog(self, dialog):
        self.dialog = dialog

    def pop_dialog(self):
        self.dialog = None


class ApplicationCase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        for target, attribute, value in ((db, "DATA_DIR", Path(self.directory.name)),
                (db, "DB_PATH", Path(self.directory.name) / "test.db"), (ft, "SharedPreferences", Preferences)):
            patcher = patch.object(target, attribute, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = patch.object(ft.context, "disable_auto_update")
        patcher.start()
        self.addCleanup(patcher.stop)
        Preferences.values = {}
        Preferences.fail_set = Preferences.fail_remove = False
        self.page = Page()
        self.app = main.Application(self.page)
        await self.app.start()
        self.user = auth.sign_in("alice", "test-password")
        await self.app.authenticated(self.user)
        self.image = media.normalize_photo(photo_bytes())

    async def test_gallery_publish_edit_delete(self):
        self.assertIsInstance(self.app.gallery_button.action, ft.PickFiles)
        self.assertTrue(self.app.gallery_button.action.with_data)
        self.assertEqual(self.app.gallery_button.action.file_type, ft.FilePickerFileType.IMAGE)
        await self.app.picker.on_result(SimpleNamespace(files=[SimpleNamespace(size=100, bytes=photo_bytes())]))
        self.assertTrue(self.app.draft.visible)
        self.app.set_rating(5)
        self.app.comment.value = "x" * 31
        await self.app.publish()
        self.assertEqual(db.get_posts(self.user["id"]), [])
        self.app.comment.value = ""
        await asyncio.gather(self.app.publish(), self.app.publish())
        posts = db.get_feed(self.user["id"])
        self.assertEqual(len(posts), 1)
        self.assertEqual(self.app.screen, 0)
        path = media.photo_file(posts[0]["photo_path"])
        self.assertTrue(path.exists())
        self.app.edit_post(posts[0])
        self.page.dialog.content.controls[1].value = "Nice"
        self.page.dialog.actions[1].on_click(None)
        self.assertEqual(db.get_posts(self.user["id"])[0]["comment"], "Nice")
        self.app.confirm_delete(posts[0])
        self.page.dialog.actions[0].on_click(None)
        self.assertTrue(path.exists())
        self.app.confirm_delete(posts[0])
        self.page.dialog.actions[1].on_click(None)
        self.assertFalse(path.exists())
        self.assertEqual(db.get_posts(self.user["id"]), [])

    async def test_failed_save_keeps_draft_and_cleans_file(self):
        self.app.accept_photo(self.image)
        self.app.set_rating(4)
        with self.assertLogs("main", level="ERROR"), patch.object(db, "save_post", side_effect=sqlite3.OperationalError("disk full")):
            await self.app.publish()
        self.assertTrue(self.app.draft.visible)
        self.assertIsNotNone(self.app.photo_data)
        self.assertEqual(list((db.DATA_DIR / "photos").iterdir()), [])
        self.assertFalse(self.app.busy)

    async def test_restore_logout_and_stale_actions(self):
        token = self.app.token
        second = main.Application(Page())
        await second.start()
        self.assertEqual(second.user["id"], self.user["id"])
        await self.app.logout()
        self.assertIsNone(auth.resume_session(token))
        self.assertFalse(second.require_login())
        self.assertIsNone(second.user)
        self.assertTrue(second.auth_slot.visible)
        Preferences.fail_set = True
        await self.app.authenticated(self.user)
        self.assertIsNotNone(self.app.user)
        Preferences.fail_remove = True
        token = self.app.token
        await self.app.logout()
        self.assertIsNone(auth.resume_session(token))

    async def test_camera_error_and_import_cancellation(self):
        with patch.object(type(self.app.camera), "get_available_cameras", AsyncMock(return_value=[])):
            await self.app.open_camera()
        self.assertFalse(self.app.busy)
        self.assertFalse(self.app.camera_ready)
        self.assertIn("галереи", self.app.notice.value)
        self.app.accept_photo(self.image)
        await self.app.picker.on_result(SimpleNamespace(files=[]))
        self.assertEqual(self.app.photo_data, self.image)
        await self.app.picker.on_result(SimpleNamespace(files=[SimpleNamespace(size=media.MAX_PHOTO_BYTES + 1)]))
        self.assertIn("8 МБ", self.app.notice.value)

    async def test_pagination_responsive_and_profile(self):
        for _ in range(14):
            db.save_post("photos/missing.jpg", 4, "", self.user["id"])
        self.app.refresh_feed()
        self.assertEqual(len(self.app.feed.controls), 12)
        self.assertTrue(self.app.more_button.visible)
        self.app.load_more()
        self.assertEqual(len(self.app.feed.controls), 14)
        self.assertFalse(self.app.more_button.visible)
        for width in (320, 390, 768, 1280):
            self.page.width = width
            self.app.resize()
            self.assertLessEqual(self.app.body.width, width - (232 if width >= 1000 else 0) - (64 if width >= 600 else 32))
            self.assertEqual(self.app.sidebar.visible, width >= 1000)
        self.app.show_screen(3)
        self.assertEqual(self.app.profile_heading.value, "alice")
        self.assertEqual(self.app.profile_avatar.controls[0].width, 64)
        self.assertEqual(self.app.stats_posts.value, "14")

    async def test_unified_sign_in_and_login(self):
        await self.app.logout()
        form = self.app.auth_form
        form.username.value = "новый ✨"
        form.password.value = "1"
        await form.submit_button.on_click(None)
        self.assertEqual(self.app.user["username"], "новый ✨")
        user_id = self.app.user["id"]
        self.assertEqual(form.password.value, "")
        await self.app.logout()
        form = self.app.auth_form
        form.username.value = "новый ✨"
        form.password.value = "wrong-password"
        await form.submit_button.on_click(None)
        self.assertEqual(form.error_text.value, "Неверный пароль")
        self.assertIsNone(self.app.user)
        form.password.value = "1"
        await form.submit_button.on_click(None)
        self.assertEqual(self.app.user["id"], user_id)

    async def test_theme_persistence_and_page_isolation(self):
        from themes import PALETTES, THEME_STORAGE_KEY
        other = main.Application(Page())
        for index, palette in enumerate(PALETTES):
            self.app.theme_switch.slider.value = index
            await self.app.change_theme(SimpleNamespace(control=self.app.theme_switch.slider, data=str(index)))
            self.assertEqual(self.page.theme.color_scheme.primary, palette[0])
            self.assertEqual(self.app.theme_switch.thumb.left, index * 20)
        self.assertEqual(other.theme_index, 0)
        self.assertEqual(other.page.theme.color_scheme.primary, PALETTES[0][0])
        self.assertEqual(Preferences.values[THEME_STORAGE_KEY], 4)
        await self.app.logout()
        self.assertEqual(self.app.theme_index, 4)
        restored = main.Application(Page())
        await restored.start()
        self.assertEqual(restored.theme_index, 4)
        Preferences.values[THEME_STORAGE_KEY] = "invalid"
        fresh = main.Application(Page())
        await fresh.start()
        self.assertEqual(fresh.theme_index, 0)
        Preferences.fail_set = True
        fresh.theme_switch.slider.value = 1
        await fresh.change_theme(SimpleNamespace(control=fresh.theme_switch.slider))
        self.assertEqual(fresh.theme_index, 1)
        self.assertTrue(fresh.notice.visible)

    async def test_friends_ui_search_and_request(self):
        other = auth.sign_in("friend", "friend-password")
        panel = self.app.friend_panel
        panel.search.value = "friend"
        panel.search_user()
        self.assertEqual(len(panel.results.controls), 1)
        panel.send(other["id"])
        self.assertEqual(db.get_friendships(self.user["id"])[0]["status"], "pending")
        panel.search_user()
        self.assertIn("заявка", panel.message.value)

    async def test_password_dialog_revokes_all_sessions(self):
        old = self.app.token
        self.app.password_dialog()
        current, new, repeat, _ = self.page.dialog.content.controls
        current.value = "test-password"
        new.value = repeat.value = "changed-password"
        await self.page.dialog.actions[1].on_click(None)
        self.assertIsNone(auth.resume_session(old))
        self.assertIsNone(self.app.user)
        self.assertEqual(auth.login_user("alice", "changed-password")["id"], self.user["id"])


if __name__ == "__main__":
    unittest.main()
