from datetime import datetime
import random, string

from pydantic import BaseModel, Field


class ClientServer(BaseModel):
    device_name: str
    ip_address: str
    connected_at: datetime


class Task(BaseModel):
    location: str | None = None
    objects: str | None = None
    # data = {
    #     'location': location,
    #     'objects': objects
    # }


class Checklist(BaseModel):
    checklist_id: str | None = None
    username: str | None = None
    tasks: list = Field(default_factory=list[Task | None])
    one_time_password: str = Field(default_factory=lambda: ''.join(random.choices(string.digits, k=8)))
    created_at: datetime = Field(default_factory=lambda: datetime.now())

    def add_item(self, task: Task | None = None):
        self.tasks.append(task)
