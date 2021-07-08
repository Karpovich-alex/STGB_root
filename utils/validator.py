import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel


class Source(Enum):
    messenger = 0
    system = 1


class User(BaseModel):
    username: str
    id: int
    first_name: str
    full_name: Optional[str]
    language_code: Optional[str]
    is_bot: Optional[bool]
    messenger: Optional[str]
    bot_id: Optional[int]
    source: Optional[Source]


class Message(BaseModel):
    id: int
    user: User
    date: datetime.datetime
    text: str
    bot: User

    def encode(self) -> bytes:
        return self.json().encode()

    @classmethod
    def decode(cls, message_object: bytes) -> 'Message':
        return cls.parse_raw(message_object)
