import datetime
from typing import List, Dict, Union

from pydantic import BaseModel, Field


class User(BaseModel):
    id: int = Field(alias='uid')
    username: str

    class Config:
        orm_mode = True


# {'text': self.text, 'time': self.time, 'chat_id': self.chat_id, 'user_id': self.user_id,
#                 'username': self.user.username}


class Message(BaseModel):
    id: int
    text: str
    time: datetime.datetime
    user: User

    class Config:
        orm_mode = True


class Chat(BaseModel):
    chat_id: int
    messages: List[Message] = []

    @classmethod
    def parse(cls, message: Dict):
        chat_id = message.get('chat_id')
        return cls(chat_id=chat_id, messages=[message])

    def append(self, message: Union[Message, List]):
        if isinstance(message, list):
            self.messages.extend(message)
        else:
            self.messages.append(message)


class BaseUpdate(BaseModel):
    def append(self, obj):
        if isinstance(obj, list):
            for element in obj:
                self._append(element)
        else:
            self._append(obj)

    def _append(self, update):
        pass

    def contain(self, *args, **kwargs):
        pass

    def get_updates_for(self, *args, **kwargs):
        pass


class Update(BaseUpdate):
    bot_id: int
    chats: List[Chat] = []

    def _append(self, new_update: 'Chat'):
        if self.contain(new_update.chat_id):
            self.set_updates(new_update.messages, new_update.chat_id)
        else:
            self.chats.append(new_update)

    def contain(self, chat_id) -> bool:
        for chat in self.chats:
            if chat.chat_id == chat_id:
                return True
        return False

    def set_updates(self, messages: List[Message], chat_id: int):
        for chat in self.chats:
            if chat.chat_id == chat_id:
                chat.append(messages)
                return

    def get_updates_for(self, chat_id: int) -> Chat:
        for chat in self.chats:
            if chat.chat_id == chat_id:
                return chat
        raise ValueError(f'Chat with id: {chat_id} is not in chats')


class NotifyUpdate(BaseUpdate):
    user_id: int
    updates: List[Update] = []

    def sorted_append(self, new_update: Update):
        if self.contain(new_update.bot_id):
            self.set_update(new_update, bot_id=new_update.bot_id)
        else:
            self.updates.append(new_update)

    def _append(self, new_update: Update):
        self.updates.append(new_update.copy())

    def contain(self, bot_id) -> bool:
        for update in self.updates:
            if update.bot_id == bot_id:
                return True
        return False

    def set_update(self, update: Update, bot_id: int):
        for updates in self.updates:
            if updates.bot_id == bot_id:
                updates.append(update.chats)
                return

    def get_updates_for(self, bot_id: int) -> Update:
        for updates in self.updates:
            if updates.bot_id == bot_id:
                return updates
        raise ValueError(f'Bot with id: {bot_id} is not in updates')

    def sort(self) -> 'NotifyUpdate':
        export_updates = NotifyUpdate(user_id=self.user_id)
        for update in self.updates:
            export_updates.sorted_append(update)
        return export_updates


class MultipleUpdates(BaseUpdate):
    updates: List[Update] = []


class MultipleNotifyUpdates(BaseUpdate):
    updates: List[NotifyUpdate] = []

    @classmethod
    def parse(cls, update: Update, users: List[int]) -> 'MultipleNotifyUpdates':
        return cls(update=[NotifyUpdate(user_id=user_id, update=[update]) for user_id in users])

    def remove(self, user_id):
        for idx, update in enumerate(self.updates):
            if update.user_id == user_id:
                self.updates.pop(idx)
                return True
        return False

    def _append(self, update: NotifyUpdate):
        if self.contain(update.user_id):
            self.set_updates_for(update.updates, update.user_id)
        else:
            self.updates.append(update)

    def contain(self, user_id) -> bool:
        for update in self.updates:
            if update.user_id == user_id:
                return True
        return False

    def set_updates_for(self, update: List[Update], user_id: int):
        for updates in self.updates:
            if updates.user_id == user_id:
                updates.append(update)
                return

    def get_updates_for(self, user_id: int) -> NotifyUpdate:
        for updates in self.updates:
            if updates.user_id == user_id:
                return updates
        raise ValueError(f'User with id: {user_id} is not in updates')

    def pop_updates_for(self, user_id: int) -> NotifyUpdate:
        for idx, updates in enumerate(self.updates):
            if updates.user_id == user_id:
                return self.updates.pop(idx)
        raise ValueError(f'User with id: {user_id} is not in updates')
