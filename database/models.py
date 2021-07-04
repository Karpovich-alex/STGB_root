import logging
from typing import Optional, List, Dict

import telegram
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, desc
from sqlalchemy.orm import declarative_base, relationship

from .base import current_session as s

Base = declarative_base()


# 'from': {'language_code': 'ru', 'username': 'sash_ka', 'first_name': 'Alex', 'is_bot': False,
#                              'id': 68658464}
class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    # TODO: Change size of string
    username = Column(String(128))
    first_name = Column(String(128))
    full_name = Column(String(128))
    language_code = Column(String(2))
    messages = relationship('Message', backref='user')

    def __repr__(self):
        return "<User id: {id} username: {username}>".format(id=self.id, username=self.username)

    @classmethod
    def check_user(cls, user: telegram.User = None, **filter_args):
        if user:
            filter_args = {'id': user.id, 'username': user.username}  # for user from tg
        u = s.query(User).filter_by(**filter_args).first()
        return bool(u)

    @classmethod
    def create_user(cls, user: telegram.User) -> 'User':
        if cls.check_user(user=user):
            raise AttributeError('This user has already exist')

        u = User(id=user.id, username=user.username, first_name=user.first_name,
                 language_code=user.language_code, full_name=user.full_name)
        s.add(u)
        s.commit()
        return u

    @classmethod
    def get_user(cls, user: telegram.User, **filter_args) -> 'User':

        if cls.check_user(user=user):
            return s.query(User).filter_by(id=user.id).first()
        return cls.create_user(user)


class Message(Base):
    __tablename__ = 'message'
    id = Column(Integer, primary_key=True)
    text = Column(String)
    time = Column(DateTime)

    user_id = Column(Integer, ForeignKey('users.id'))
    bot_id = Column(Integer, ForeignKey('bot.id'))

    @classmethod
    def add_message(cls, message: telegram.Message) -> Optional['Message']:
        try:
            m = cls(id=message.message_id, text=message.text, time=message.date, bot_id=message.bot.id,
                    user_id=message.chat_id)
            s.add(m)
            s.commit()
            return m
        except Exception as e:
            logging.exception(e)
            return None

    def __repr__(self):
        return "<Message from user: {user_id} to bot: {bot_id}>".format(user_id=self.user_id, bot_id=self.bot_id)

    def to_dict(self) -> Dict:
        return {'text': self.text, 'time': self.time, 'user_id': self.user_id}

    @classmethod
    def get_messages(cls, bot_id, user_id) -> List['Message']:
        messages = s.query(Message).filter_by(user_id=user_id, bot_id=bot_id).order_by('time').all()
        return messages


class Bot(Base):
    __tablename__ = 'bot'
    id = Column(Integer, primary_key=True)

    @classmethod
    def exist(cls, bot):
        if s.query(Bot).filter_by(id=bot.id).first():
            return True
        return False

    @classmethod
    def init_bot(cls, bot: telegram.Bot):
        if Bot.exist(bot):
            return None
        try:
            b = Bot(id=bot.id)
            s.add(b)
            s.commit()
            return b
        except Exception as e:
            logging.exception(e)
            return None

    @classmethod
    def get_all(cls):
        return s.query(cls).all()

    @classmethod
    def get_messages(cls, bot_id) -> List['Message']:
        messages = s.query(Message).order_by('user_id', desc('time')).distinct('user_id').filter_by(bot_id=bot_id).all()
        return messages
    # class Chat(Base):
    #     __tablename__ = 'chat'
    #     id = Column(Integer, primary_key=True)
    #     tg_id = Column(Integer)
