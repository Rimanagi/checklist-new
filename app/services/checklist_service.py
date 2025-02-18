from app.schemas import Checklist
from datetime import datetime

# Например, функция создания нового чеклиста на основе данных из формы
def create_checklist(data: dict, user: str) -> Checklist:
    checklist = Checklist(username=user, created_at=datetime.now())
    # Можно добавить в checklist.items данные из data, если они уже есть
    if "items" in data:
        checklist.items = data["items"]
    return checklist