from datetime import datetime
import random, string
from typing import Optional

from pydantic import BaseModel, Field


class ClientServer(BaseModel):
    device_name: str
    ip_address: str
    connected_at: datetime


class Task(BaseModel):
    location: str | None = None
    objects: list = list()


class Checklist(BaseModel):
    checklist_id: Optional[str] = None
    username: str | None = None
    tasks: list[Optional[Task]] = []
    one_time_password: str = Field(default_factory=lambda: ''.join(random.choices(string.digits, k=8)))
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())

    def add_item(self, task: Task | None = None):
        self.tasks.append(task)


class SelectObjectsPayload(BaseModel):
    task: Task
    checklist: Checklist
