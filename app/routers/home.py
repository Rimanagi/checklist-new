from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.templates import templates
from app.connected_servers import connected_servers

router = APIRouter()

@router.get("/", response_class=HTMLResponse)
def main_page(request: Request):
    """
    Отображает главную страницу
    """
    servers = [server.model_dump() for server in connected_servers]
    return templates.TemplateResponse("index.html", {"request": request, "servers": servers})
