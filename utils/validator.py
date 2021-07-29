import datetime
from enum import Enum
from typing import Optional, Any

from pydantic import BaseModel


class Source(Enum):
    messenger = 0
    system = 1


class Messengers(Enum):
    support = 0
    telegram = 1

    @classmethod
    def check_value(cls, value):
        return value in cls.__members__


class BaseUser(BaseModel):
    id: int
    username: str


class User(BaseUser):
    id: Optional[int]
    full_name: Optional[str]
    source: Optional[Source]
    messenger: Any


class WebUser(BaseUser):
    full_name: str

    @classmethod
    def from_orm(cls, user):  # user: 'm.WebUser'
        return cls(id=user.uid, username=user.username, full_name=user.full_name)


class UserInDB(User):
    hashed_password: str
    #
    # @classmethod
    # def create(cls, user: 'RegistryUser'):
    #     user_dict = user.dict(include={'username', 'full_name'})
    #     user_dict["hashed_password"] = get_password_hash(user.password)
    #     new_user = cls(**user_dict)
    #     return new_user


class RegistryUser(BaseModel):
    username: str
    full_name: Optional[str] = None
    password: str


class Bot(BaseUser):
    messenger: Messengers


class MessengerUser(User):
    first_name: str
    source = Source.messenger
    messenger: Messengers
    language_code: Optional[str]
    is_bot: Optional[bool]

    bot_id: Optional[int]


class DbUser(BaseModel):
    id: int
    messenger_id: int
    messenger: Messengers
    bot_id: int

    username: str
    first_name: str
    full_name: str
    language_code: str


class Chat(BaseModel):
    id: int
    messages: Optional['Message']


class BaseMessage(BaseModel):
    id: int
    user: User
    chat: Optional[Chat]
    date: datetime.datetime
    text: str

    def encode(self) -> bytes:
        return self.json().encode()

    @classmethod
    def decode(cls, message_object: bytes) -> 'BaseMessage':
        return cls.parse_raw(message_object)


class Message(BaseMessage):
    chat: Chat


class MessengerMessage(BaseMessage):
    user: MessengerUser
    bot: Bot
