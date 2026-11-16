import base64
import io
import os

import flet.fastapi as flet_fastapi
import uvicorn
from fastapi import Header, HTTPException, Response
from PIL import Image

import database as db
import media
import widget_auth
from main import main


def create_app():
    app = flet_fastapi.FastAPI(on_startup=[db.init_db], docs_url=None, redoc_url=None, openapi_url=None)

    @app.get("/api/widget/latest")
    def latest(response: Response, authorization: str | None = Header(default=None)):
        response.headers["Cache-Control"] = "no-store, private"
        scheme, _, token = (authorization or "").partition(" ")
        user_id = widget_auth.connection_user(token) if scheme.lower() == "bearer" else None
        if user_id is None:
            raise HTTPException(status_code=401, detail="Widget connection required", headers={
                "WWW-Authenticate": "Bearer", "Cache-Control": "no-store, private",
            })
        posts = db.get_feed(user_id, limit=1)
        post = None
        if posts:
            item = posts[0]
            thumbnail = None
            try:
                normalized = media.normalize_photo(media.read_photo(item["photo_path"]))
                with Image.open(io.BytesIO(normalized)) as image:
                    image.thumbnail((480, 480))
                    output = io.BytesIO()
                    image.save(output, format="JPEG", quality=82, optimize=True)
                    thumbnail = base64.b64encode(output.getvalue()).decode("ascii")
            except (OSError, ValueError):
                pass
            post = {"id": item["id"], "username": item["username"][:80], "rating": item["rating"],
                    "comment": item["comment"], "created_at": item["created_at"], "image_base64": thumbnail}
        return {"post": post, "feed_url": os.environ.get("DT_PUBLIC_URL", "https://152.234.209.214/")}

    app.mount("/", flet_fastapi.app(main, app_name="Different Tastes", app_short_name="Different Tastes"))
    return app


if __name__ == "__main__":
    uvicorn.run(create_app(), host=os.environ.get("DT_HOST", "127.0.0.1"), port=int(os.environ.get("PORT", "8550")),
                proxy_headers=True, forwarded_allow_ips="127.0.0.1")
