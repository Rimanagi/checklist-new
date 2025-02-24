from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import RedirectResponse

active_sessions = set()


class SessionMiddleware(BaseHTTPMiddleware):
    """Middleware для проверки сессии перед каждым запросом"""

    async def dispatch(self, request: Request, call_next):
        if request.url.path not in ["/login"] and not request.url.path.startswith("/static/"):  # Разрешаем эти пути без авторизации
            session_token = request.cookies.get('access_token')
            if not session_token or session_token not in active_sessions:
                return RedirectResponse(url="/login")

        response = await call_next(request)
        return response