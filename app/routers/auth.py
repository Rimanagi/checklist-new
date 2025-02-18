from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm

from app.config import ADMIN_USERNAME, ADMIN_PASSWORD
from app.utils.jwt_helper import create_access_token
from app.templates import templates

router = APIRouter()


@router.get("/login", response_class=HTMLResponse)
def get_login_page(request: Request):
    """
    Отображает страницу логина.
    """
    return templates.TemplateResponse("login.html", {"request": request})


@router.post("/login", response_class=HTMLResponse, )
def post_login(request: Request, form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Обрабатывает форму логина.
    Если логин/пароль неверные, возвращаем шаблон с ошибкой.
    Иначе генерируем токен, сохраняем в куках и перенаправляет на главную страницу.
    """
    if form_data.username != ADMIN_USERNAME or form_data.password != ADMIN_PASSWORD:
        return templates.TemplateResponse(
            "login.html", {"request": request, "error": "Неверный логин или пароль"}
        )

    access_token = create_access_token({"sub": form_data.username})  # todo - пересмотреть эту строку
    print(f'{form_data.username=}, {access_token=}')
    response = RedirectResponse(url="/", status_code=302)
    response.set_cookie(key="access_token", value=access_token, httponly=True)
    return response


@router.get("/register", response_class=HTMLResponse)
def get_register_page(request: Request):
    """
    Отображает страницу с регистрацией
    """
    return templates.TemplateResponse("register.html", {"request": request, "error": "Регистрация отключена"})
