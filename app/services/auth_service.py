from fastapi import HTTPException, status
from app.config import ADMIN_USERNAME, ADMIN_PASSWORD


# todo ебаная шляпа
#  нужно не забыть протестировать и проверить, что только авторизованный может что-то делать на сайте
def verify_admin(username: str, password: str):
    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        return True
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Неверный логин или пароль")


# try:
    #     username = get_current_user_from_cookie(request)
    # except HTTPException:
    #     return RedirectResponse(url="/login", status_code=302)