import json
import string
import urllib.parse
import random
from datetime import datetime
from typing import Optional

# import jwt
from bson import ObjectId
from fastapi import APIRouter, Request, Form, Body, HTTPException  # , status, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from rich.progress import TaskID

from app.connected_servers import connected_servers
from app.schemas import Checklist, Task
from app.templates import templates
from database import locations_collection, checklists_collection, users_collection, passwords_collection

# from app.config import (SECRET_KEY, ALGORITHM, ADMIN_USERNAME)
# from app.services.checklist_service import create_checklist

router = APIRouter()


def get_context(request: Request, **kwargs):
    context = {"request": request}
    context.update(kwargs)
    return context


@router.api_route("/create_checklist", methods=["GET", "POST"], response_class=HTMLResponse)
async def create_checklist_page(
        request: Request,
        checklist: Optional[Checklist] = Body(None)
):
    if request.method == "GET":
        checklist = Checklist()
    # Получаем список пользователей
    users = []
    cursor = users_collection.find({})
    async for user in cursor:
        user["id"] = str(user["_id"])
        users.append(user)

    context = get_context(request, checklist=checklist, users=users)
    return templates.TemplateResponse("create_checklist.html", context)


from fastapi import Form, HTTPException


@router.post("/select_location", response_class=HTMLResponse)
async def select_location_page(
        request: Request,
        checklist_obj: Checklist = Body(...),
):
    try:
        checklist = Checklist.model_validate_json(checklist_obj)
    except Exception:
        raise HTTPException(status_code=400, detail="Чеклист не передался или имеет неверный формат")

    doc = await locations_collection.find_one({})
    if doc:
        doc.pop("_id", None)
        locations = list(doc.keys())
    else:
        locations = []

    task = Task()
    context = get_context(request, checklist=checklist, locations=locations, task=task)
    return templates.TemplateResponse("select_location.html", context)


@router.post("/select_location/{location}/select_objects", response_class=HTMLResponse)
async def select_objects(
    request: Request,
    location: str,
    checklist_obj: str = Form(...),  # Чеклист в виде JSON‑строки
    task_obj: str = Form(...),       # Объект task в виде JSON‑строки
):
    # Десериализуем чеклист и task
    try:
        checklist = Checklist.model_validate_json(checklist_obj)
    except Exception:
        raise HTTPException(status_code=400, detail="Чеклист не передался или имеет неверный формат")
    try:
        task = Task.model_validate_json(task_obj)
    except Exception:
        task = Task()

    # Считываем данные о локациях из базы (JSON-файл)
    doc = await locations_collection.find_one({})
    if doc:
        doc.pop("_id", None)
        location_data = doc.get(location)
    else:
        location_data = None
    if not location_data:
        return HTMLResponse(f"Локация {location} не найдена", status_code=404)

    # Получаем список объектов для выбранной локации
    objects = location_data.get("object_list", [])

    # Вычисляем, какие объекты уже выбраны в task (по cr_code)
    preselected_codes = []
    if task.objects:
        preselected_codes = [obj.get("cr_code") for obj in task.objects if isinstance(obj, dict)]

    form = await request.form()
    if "obj" in form:
        # Если чекбоксы отправлены, собираем выбранные объекты
        selected = []
        for obj_str in form.getlist("obj"):
            try:
                selected.append(json.loads(obj_str))
            except Exception:
                pass
        if not selected:
            context = get_context(
                request,
                checklist=checklist,
                location=location,
                objects=objects,
                preselected_codes=preselected_codes,
                error="Выберите хотя бы один объект"
            )
            return templates.TemplateResponse("select_objects.html", context)
        # Обновляем task: записываем локацию и выбранные объекты
        task.location = location
        task.objects = selected
        # Добавляем task в checklist
        checklist.tasks.append(task)
        # Возвращаем страницу создания чеклиста, передавая только обновлённый checklist
        return templates.TemplateResponse("create_checklist.html", get_context(request, checklist=checklist))
    else:
        # Первоначальный переход – просто отображаем страницу выбора объектов
        context = get_context(
            request,
            checklist=checklist,
            location=location,
            objects=objects,
            preselected_codes=preselected_codes
        )
        return templates.TemplateResponse("select_objects.html", context)

# Страница выбора объектов для выбранной локации (selected_user передаётся дальше).
@router.post("/select_location/{location}/select_objects", response_class=HTMLResponse)
async def select_objects_page(
        request: Request,
        location: str,
        task: str,
        checklist: str = Form(...),  # Чеклист передается в обязательном порядке как JSON-строка
):
    # Десериализуем чеклист
    try:
        checklist = Checklist.model_validate_json(checklist)
    except Exception:
        raise HTTPException(status_code=400, detail="Чеклист не передался или имеет неверный формат")

    doc = await locations_collection.find_one({})
    if doc:
        doc.pop("_id", None)
        location_data = doc.get(location)
    else:
        location_data = None
    if not location_data:
        return HTMLResponse(f"Локация {location} не найдена", status_code=404)


# Удаление локации из чеклиста по индексу.
@router.get("/delete_location", response_class=HTMLResponse)
def delete_location(request: Request, index: int, data: str, checklist_id: str = None, selected_user: str = None):
    try:
        current_checklist = json.loads(urllib.parse.unquote(data))
    except Exception:
        current_checklist = []
    if 0 <= index < len(current_checklist):
        current_checklist.pop(index)
    new_data = urllib.parse.quote(json.dumps(current_checklist))
    if checklist_id is not None and checklist_id.strip() != "":
        redirect_url = f"/create_checklist?data={new_data}&checklist_id={checklist_id}"
    else:
        redirect_url = f"/create_checklist?data={new_data}"
    if selected_user:
        redirect_url += f"&selected_user={selected_user}"
    return RedirectResponse(url=redirect_url, status_code=302)


# Редактирование локации: переход на выбор объектов с предвыбранными значениями.
@router.get("/edit_location", response_class=HTMLResponse)
def edit_location(request: Request, index: int, data: str, checklist_id: str = None, selected_user: str = None):
    try:
        current_checklist = json.loads(urllib.parse.unquote(data))
    except Exception:
        current_checklist = []
    if 0 <= index < len(current_checklist):
        item = current_checklist[index]
        location = item.get("location")
        preselected = urllib.parse.quote(json.dumps(item.get("objects", [])))
        if checklist_id is not None and checklist_id.strip() != "":
            redirect_url = (f"/select_objects?location={urllib.parse.quote(location)}"
                            f"&data={urllib.parse.quote(data)}&preselected={preselected}"
                            f"&index={index}&checklist_id={checklist_id}")
        else:
            redirect_url = (f"/select_objects?location={urllib.parse.quote(location)}"
                            f"&data={urllib.parse.quote(data)}&preselected={preselected}&index={index}")
        if selected_user:
            redirect_url += f"&selected_user={selected_user}"
        return RedirectResponse(url=redirect_url, status_code=302)
    return RedirectResponse(url=f"/create_checklist?data={urllib.parse.quote(data)}", status_code=302)


# Сохранение чеклиста: обновление, если передан checklist_id, или создание нового.
@router.post("/save_checklist")
async def save_checklist(
        request: Request,
        data: str = Form("[]"),
        checklist_id: str = Form(None),
        selected_user: str = Form(...),
):
    if not selected_user:
        return HTMLResponse("Ошибка: необходимо выбрать пользователя", status_code=400)
    try:
        checklist = json.loads(data)
    except Exception:
        checklist = []
    if not checklist:
        return RedirectResponse(url="/create_checklist", status_code=302)

    if checklist_id is not None and checklist_id.strip() != "":
        await checklists_collection.update_one(
            {"_id": ObjectId(checklist_id)},
            {"$set": {"checklist": checklist, "created_at": datetime.now()}}
        )
        await passwords_collection.update_one(
            {"checklist_id": checklist_id},
            {"$set": {"user": selected_user}}
        )
    else:
        document = {
            "checklist": checklist,
            "created_at": datetime.now()
        }
        result = await checklists_collection.insert_one(document)
        new_checklist_id = str(result.inserted_id)
        generated_password = ''.join(random.choices(string.digits, k=8))
        password_doc = {
            "checklist_id": new_checklist_id,
            "user": selected_user,
            "password": generated_password,
            "created_at": datetime.now()
        }
        await passwords_collection.insert_one(password_doc)
    return RedirectResponse(url="/checklists", status_code=302)


# Просмотр сохранённых чеклистов.
@router.get("/checklists", response_class=HTMLResponse)
async def get_checklists(request: Request):
    checklists = []
    async for document in checklists_collection.find({}):
        checklist_id = str(document["_id"])
        document["id"] = checklist_id
        document.pop("_id", None)
        if "created_at" in document and isinstance(document["created_at"], datetime):
            document["created_at"] = document["created_at"].strftime("%d-%m-%y %H:%M")
        password_doc = await passwords_collection.find_one({"checklist_id": checklist_id})
        if password_doc:
            document["user"] = password_doc.get("user", "")
            document["password"] = password_doc.get("password", "")
        else:
            document["user"] = ""
            document["password"] = ""
        checklists.append(document)
    return templates.TemplateResponse("checklists.html", {"request": request, "checklists": checklists})


# Удаление чеклиста.
@router.post("/delete_checklist")
async def delete_checklist(request: Request, checklist_id: str = Form(...)):
    await checklists_collection.delete_one({"_id": ObjectId(checklist_id)})
    return RedirectResponse(url="/checklists", status_code=302)


# Редактирование чеклиста: перенаправляем на create_checklist с данными.
@router.get("/edit_checklist", response_class=HTMLResponse)
async def edit_checklist(request: Request, checklist_id: str, selected_user: str = None):
    document = await checklists_collection.find_one({"_id": ObjectId(checklist_id)})
    if not document:
        return HTMLResponse("Чеклист не найден", status_code=404)
    data = urllib.parse.quote(json.dumps(document.get("checklist", [])))
    password_doc = await passwords_collection.find_one({"checklist_id": checklist_id})
    if password_doc:
        selected_user = password_doc.get("user")
    else:
        selected_user = ""
    return RedirectResponse(
        url=f"/create_checklist?data={data}&checklist_id={checklist_id}&selected_user={selected_user}",
        status_code=302
    )


# Новый эндпоинт для отправки чеклиста на внешний сервер по WebSocket.
@router.post("/send_checklist")
async def send_checklist(
        checklist: dict = Body(...),
        server_ip: str = Body(...),

):
    target_server = None
    for s in connected_servers:
        if s["ip"] == server_ip:
            target_server = s
            break
    if not target_server:
        raise HTTPException(status_code=404, detail="Server not found or not connected")
    try:
        await target_server["ws"].send_text(json.dumps(checklist))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send checklist: {str(e)}")
    return {"detail": "Checklist sent successfully"}

# def get_current_user_from_cookie(request: Request):
#     token = request.cookies.get("access_token")
#     if not token:
#         raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
#     try:
#         payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
#         username = payload.get("sub")
#         if username is None or username != ADMIN_USERNAME:
#             raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
#         return username
#     except jwt.PyJWTError:
#         raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
