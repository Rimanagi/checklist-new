from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

import uvicorn

from app.routers import home, auth, websocket, checklist

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(home.router, tags=["home"])
app.include_router(auth.router, tags=["auth"])
app.include_router(checklist.router, tags=["checklist"])
app.include_router(websocket.router, tags=["websocket"])

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)


# todo не работает проверка на авторизованного пользователя (сейчас на сайт может зайти кто угодно)
# todo мне не нравится реализация websockets, особенно все что касается admin_connections
# todo /ws/servers/updates - шляпа какая-то лишняя в checklists
# todo checklist.py - почистить нахуй код без лишних повторений