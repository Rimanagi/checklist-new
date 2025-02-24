import json
from datetime import datetime
from typing import Optional
import urllib.parse

from bson import ObjectId
from fastapi import APIRouter, Request, Form, Body, HTTPException  # , status, Depends
from fastapi.params import Query, Depends
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse

from app.connected_servers import connected_servers
from app.schemas import Checklist, Task, SelectObjectsPayload
from app.templates import templates
# from app.utils.auth_checker import get_current_user
from database import locations_collection, checklists_collection, users_collection, passwords_collection

# from app.config import (SECRET_KEY, ALGORITHM, ADMIN_USERNAME)
# from app.services.checklist_service import create_checklist

router = APIRouter()


def get_context(request: Request, **kwargs):
    context = {"request": request}
    context.update(kwargs)
    return context


def convert_datetime(obj):
    if isinstance(obj, dict):
        return {k: convert_datetime(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_datetime(item) for item in obj]
    elif isinstance(obj, datetime):
        return obj.isoformat()
    else:
        return obj


@router.get("/create_checklist", response_class=HTMLResponse)
async def create_checklist_page(
        request: Request,
        data: str = None,
        checklist_id: Optional[str] = Query(None),
):
    # Если передан параметр data, пытаемся его распарсить
    tasks_override = None
    if data:
        try:
            tasks_override = json.loads(urllib.parse.unquote(data))
        except Exception:
            tasks_override = None

    if checklist_id:
        # Загружаем чеклист из базы по checklist_id
        checklist_data = await checklists_collection.find_one({"checklist_id": checklist_id})
        if checklist_data:
            checklist = Checklist(**checklist_data)
            # Если переданы новые данные, обновляем список задач
            if tasks_override is not None:
                checklist.tasks = tasks_override
        else:
            # Если чеклист не найден в базе, пробуем взять его из cookie
            unsaved_cookie = request.cookies.get("unsaved_checklist")
            if unsaved_cookie:
                unsaved = json.loads(unsaved_cookie)
                checklist = Checklist(**unsaved)
            else:
                checklist = Checklist()
    else:
        checklist = Checklist()

    # Загружаем пользователей
    users = []
    cursor = users_collection.find({})
    async for user in cursor:
        user["id"] = str(user["_id"])
        users.append(user)

    context = get_context(request, checklist=checklist, users=users, selected_user=checklist.username)
    return templates.TemplateResponse("create_checklist.html", context)


@router.post("/select_location", response_class=HTMLResponse)
async def select_location_page(
        request: Request,
        checklist: Checklist = Body(...),
):
    print(checklist.checklist_id)
    doc = await locations_collection.find_one({})
    if doc:
        doc.pop("_id", None)
        locations = list(doc.keys())
    else:
        locations = []

    task = Task()
    # todo как тут присвоить локацию таске?
    context = get_context(request, checklist=checklist, locations=locations, task=task)
    return templates.TemplateResponse("select_location.html", context)


# Страница выбора объектов для выбранной локации (selected_user передаётся дальше).
@router.post("/select_location/{location}/select_objects", response_class=HTMLResponse)
async def select_objects_page(
        request: Request,
        location: str,
        payload: SelectObjectsPayload,
):
    task = payload.task
    checklist = payload.checklist
    # Всегда устанавливаем выбранную локацию в задаче
    task.location = location

    # Загружаем данные локации из базы
    doc = await locations_collection.find_one({})
    if doc:
        doc.pop("_id", None)
        location_data = doc.get(location)
    else:
        location_data = None
    if not location_data:
        return HTMLResponse(f"Локация {location} не найдена", status_code=404)
    objects = location_data.get("object_list", [])

    # Если task уже содержит список объектов (например, при редактировании),
    # он будет передан в шаблон, и шаблон отметит соответствующие чекбоксы.
    context = get_context(request, checklist=checklist, objects=objects, task=task)
    return templates.TemplateResponse("select_objects.html", context)


@router.get("/select_objects/edit/{index}", response_class=HTMLResponse)
async def edit_task(request: Request, index: int):
    unsaved_cookie = request.cookies.get("unsaved_checklist")
    if not unsaved_cookie:
        raise HTTPException(status_code=404, detail="Временный чеклист не найден")
    checklist_data = json.loads(unsaved_cookie)
    tasks = checklist_data.get("tasks", [])
    if index < 0 or index >= len(tasks):
        raise HTTPException(status_code=400, detail="Некорректный индекс задачи")

    task_data = tasks[index]
    if not task_data.get("location"):
        raise HTTPException(status_code=400, detail="Локация не установлена для данной задачи")

    location = task_data["location"]
    doc = await locations_collection.find_one({})
    if doc:
        doc.pop("_id", None)
        location_data = doc.get(location)
    else:
        location_data = None
    if not location_data:
        raise HTTPException(status_code=404, detail=f"Локация {location} не найдена")
    objects = location_data.get("object_list", [])

    # Преобразуем данные в экземпляры моделей
    checklist = Checklist(**checklist_data)
    task = Task(**task_data)

    context = get_context(request, checklist=checklist, objects=objects, task=task)
    return templates.TemplateResponse("select_objects.html", context)


@router.post("/save_unsaved_checklist")
async def save_unsaved_checklist(payload: dict = Body(...)):
    # Ожидаем payload вида: { "checklist": { ... } }
    checklist_data = payload.get("checklist")
    if checklist_data:
        response = JSONResponse({"status": "saved"})
        # Сохраняем JSON в cookie; cookie может быть HttpOnly, чтобы её не читал JS
        response.set_cookie("unsaved_checklist", json.dumps(checklist_data), httponly=True)
        return response
    raise HTTPException(status_code=400, detail="Checklist data not provided")


@router.get("/delete_task/{index}", response_class=HTMLResponse)
async def delete_task(request: Request, index: int):
    unsaved_cookie = request.cookies.get("unsaved_checklist")

    if not unsaved_cookie:
        raise HTTPException(status_code=404, detail="Временный чеклист не найден")
    checklist_data = json.loads(unsaved_cookie)
    tasks = checklist_data.get("tasks", [])
    if index < 0 or index >= len(tasks):
        raise HTTPException(status_code=400, detail="Некорректный индекс задачи")
    # Удаляем задачу с заданным индексом
    del tasks[index]
    checklist_data["tasks"] = tasks
    # Подготавливаем редирект на страницу create_checklist, передавая checklist_id (если он есть)
    redirect_url = f"/create_checklist?checklist_id={checklist_data.get('checklist_id', '')}"
    response = RedirectResponse(redirect_url, status_code=302)
    # Обновляем cookie с новым состоянием чеклиста
    response.set_cookie("unsaved_checklist", json.dumps(checklist_data), httponly=True)
    return response


@router.post("/save_checklist", response_class=HTMLResponse)
async def save_checklist(
        request: Request,
        checklist: str = Form(...),
        selected_user: str = Form(...)
):
    try:
        checklist_data = json.loads(checklist)
    except Exception as e:
        raise HTTPException(status_code=400, detail="Неверный формат чеклиста")

    checklist_data["username"] = selected_user.strip()

    if not checklist_data.get("username"):
        context = get_context(request, error="Пользователь не выбран", checklist=Checklist(**checklist_data))
        return templates.TemplateResponse("create_checklist.html", context)

    if not checklist_data.get("tasks") or len(checklist_data["tasks"]) == 0:
        context = get_context(request, error="Чеклист пуст. Добавьте хотя бы одну задачу",
                              checklist=Checklist(**checklist_data))
        return templates.TemplateResponse("create_checklist.html", context)

    try:
        checklist_obj = Checklist(**checklist_data)
    except Exception as e:
        raise HTTPException(status_code=400, detail="Ошибка в данных чеклиста")

    # Если в данных уже есть checklist_id, обновляем документ
    if checklist_data.get("checklist_id"):
        await checklists_collection.update_one(
            {"checklist_id": checklist_data["checklist_id"]},
            {"$set": checklist_obj.model_dump()}
        )
    else:
        # Иначе вставляем новый чеклист
        result = await checklists_collection.insert_one(checklist_obj.model_dump())
        await checklists_collection.update_one(
            {"_id": result.inserted_id},
            {"$set": {"checklist_id": str(result.inserted_id)}}
        )

    # Редирект на страницу со списком чеклистов
    return RedirectResponse("/checklists", status_code=302)


@router.get("/checklists", response_class=HTMLResponse)
async def list_checklists(request: Request):
    checklists_cursor = checklists_collection.find({})
    checklists = await checklists_cursor.to_list(length=100)
    for checklist in checklists:
        if "_id" in checklist:
            checklist["id"] = str(checklist["_id"])
            checklist.pop("_id")
        if "created_at" in checklist and isinstance(checklist["created_at"], datetime):
            checklist["created_at"] = checklist["created_at"].isoformat()
        # Если у вас в чеклисте есть вложенные datetime, преобразуйте их аналогичным образом
    context = get_context(request, checklists=checklists)
    return templates.TemplateResponse("checklists.html", context)


@router.post("/delete_checklist")
async def delete_checklist(request: Request, checklist_id: str = Form(...)):
    await checklists_collection.delete_one({"_id": ObjectId(checklist_id)})
    return RedirectResponse(url="/checklists", status_code=302)
