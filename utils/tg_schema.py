from datetime import datetime
from typing import Optional, Any

from pydantic import BaseModel, constr, Field

from utils import validator as v


class TGUser(BaseModel):
    id: int
    is_bot: bool
    first_name: str
    username: str
    language_code: Optional[constr(max_length=2)]


class TGUserCreate(TGUser):
    bot: Any
    chat_id: int
    messenger = v.Messengers.telegram


class TGChat(BaseModel):
    id: int
    first_name: str
    username: str
    type: str


class TGMessage(BaseModel):
    message_id: int
    from_user: TGUser = Field(alias='from')
    chat: TGChat
    date: datetime
    text: str


class Update(BaseModel):
    update_id: int
    message: TGMessage


class TGUpdate(Update):
    source: v.Source = v.Source.messenger
    messenger: v.Messengers = v.Messengers.telegram

    @classmethod
    def from_update(cls, update):
        return cls(**update.dict())
