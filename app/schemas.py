from datetime import date
from typing import Literal
from zoneinfo import ZoneInfo
from pydantic import BaseModel, Field, ConfigDict, field_validator
class HomeworkIn(BaseModel):
    subject: str = Field(min_length=1,max_length=300)
    text: str = Field(min_length=1,max_length=20000)
    due_date: date
class HomeworkOut(HomeworkIn):
    id: int
    group_id: int
    model_config = ConfigDict(from_attributes=True)
class GroupIn(BaseModel):
    name: str = Field(min_length=1,max_length=100)
    password: str | None = Field(default=None,min_length=12,max_length=200)
    published: bool = False
    active: bool = True
    timezone: str = 'Europe/Moscow'
    anchor_monday: date = date(2026,10,19)
    anchor_week: Literal['upper','lower'] = 'lower'
    @field_validator('timezone')
    @classmethod
    def tz(cls,v):
        try: ZoneInfo(v)
        except Exception: raise ValueError('Неизвестный часовой пояс')
        return v
    @field_validator('anchor_monday')
    @classmethod
    def monday(cls,v):
        if v.weekday()!=0: raise ValueError('Опорная дата должна быть понедельником')
        return v
class Login(BaseModel):
    password: str = Field(min_length=1,max_length=200)
    group_id: int | None = None
class Refresh(BaseModel):
    refresh_token: str = Field(min_length=20,max_length=300)
class Lesson(BaseModel):
    slot: int = Field(ge=1,le=100)
    subject: str = Field(min_length=1,max_length=300)
    teacher: str = Field(default='',max_length=300)
    room: str = Field(default='',max_length=100)
    subgroup_id: int | None = None
    week: Literal['upper','lower','both'] = 'both'
class DayIn(BaseModel):
    shortened: bool = False
    lessons: list[Lesson] = Field(default_factory=list,max_length=300)
class Repeat(BaseModel):
    start: date
    weeks: int = Field(ge=1,le=104)
class NameIn(BaseModel):
    name: str = Field(min_length=1,max_length=100)
