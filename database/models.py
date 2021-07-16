import enum
import logging
from typing import Optional, List, Dict, Union

import telegram
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum, Table
from sqlalchemy.orm import declarative_base, relationship

import utils.validator as v
################
from utils.connector import Notify
from .base import current_session as s

################
Base = declarative_base()
notify = Notify()


class Messengers(enum.Enum):
    support = 0
    telegram = 1

    @classmethod
    def check_value(cls, value):
        return value in cls.__members__


class MessengerConnector:
    @classmethod
    def get_messenger_id(cls, unique_id):
        c = s.query(cls).filter_by(id=unique_id).first()
        return c.messenger_id


UsersInChat = Table('usersinchat', Base.metadata,
                    Column('user_id', Integer, ForeignKey('users.id')),
                    Column('chat_id', Integer, ForeignKey('chat.id')))


def parse_user(user: v.User, filter_args: Dict) -> Dict:
    if user.source == v.Source.messenger:
        filter_args['messenger_id'] = user.id
        filter_args['messenger'] = filter_args.get('messenger', Messengers[user.messenger])
    else:
        filter_args['id'] = user.id
    return filter_args


class User(Base, MessengerConnector):
    __tablename__ = 'users'
    id = Column(Integer, autoincrement=True, primary_key=True)
    messenger_id = Column(Integer)  # id in messenger
    messenger = Column(Enum(Messengers))  # откуда отправили сообщение

    bot_id = Column(Integer, ForeignKey('bot.id'), nullable=False)
    bot = relationship('Bot', backref='users')

    # TODO: Change size of string
    username = Column(String(128))
    first_name = Column(String(128))
    full_name = Column(String(128))
    language_code = Column(String(2))
    chats = relationship('Chat', secondary='usersinchat', back_populates='users')
    messages = relationship('Message', back_populates='user')

    def __init__(self, *args, **kwargs):
        super(Base, self).__init__(*args, **kwargs)

    def __repr__(self):
        return "<User id: {id} username: {username}>".format(id=self.id, username=self.username)

    # @classmethod
    # def check_user(cls, messenger_user: v.User = None, user: v.User = None, **filter_args) -> bool:
    #     if messenger_user:
    #         filter_args['messenger'] = filter_args.get('messenger', messenger_user.bot.messenger)
    #         filter_args = {'messenger_id': messenger_user.id,
    #                        'bot_id': messenger_user.bot.id}  # for user from messenger
    #     elif user:
    #         filter_args['messenger'] = filter_args.get('messenger', user.bot.messenger)
    #         filter_args = {'messenger_id': user.id, 'bot_id': user.bot.id}
    #     u = s.query(User).filter_by(**filter_args).first()
    #     return bool(u)
    @classmethod
    def check_user(cls, user: v.User, **filter_args) -> Union['User', bool]:
        filter_args = parse_user(user, filter_args)
        u = s.query(User).filter_by(**filter_args).first()
        return u or False

    @classmethod
    def create_user(cls, user: v.User) -> 'User':
        if cls.check_user(user=user):
            raise AttributeError('This user has already exist')

        bot_id = Bot.get_id(messenger=user.messenger, messenger_id=user.bot_id)
        u = cls(username=user.username, first_name=user.first_name,
                language_code=user.language_code, full_name=user.full_name, messenger=user.messenger,
                bot_id=user.bot_id)
        if user.source == v.Source.messenger:
            u.messenger_id = user.id
        else:
            u.id = user.id
        c = Chat(bot_id=bot_id, messenger_id=u.messenger_id)
        u.chats.append(c)
        s.add(u)
        s.commit()
        return u

    @classmethod
    def get_user(cls, user: v.User) -> 'User':
        u = cls.check_user(user)
        if u:
            return u
        else:
            return cls.create_user(user)

    # @classmethod
    # def get_user(cls, user: v.User = None,
    #              bot: v.User = None,
    #              tg_user: telegram.User = None,
    #              messenger_id=None,
    #              bot_m_id=None,
    #              **filter_args) -> 'User':
    #     if user and bot:
    #         filter_args['messenger_id'] = user.id
    #         if Messengers.check_value(bot.messenger):
    #             filter_args['messenger'] = Messengers[bot.messenger]
    #         else:
    #             raise ValueError('This messenger is not supported')
    #         return cls.check_user(**filter_args) or cls.create_user(user, bot_m_id=bot.id)
    #
    #     if messenger_id:
    #         filter_args['messenger_id'] = messenger_id
    #     if filter_args:
    #         u = cls.check_user(**filter_args)
    #     else:
    #         u = cls.check_user(user=user)
    #     if u:
    #         return u
    #     elif tg_user:
    #         return cls.create_user(tg_user, bot_m_id)
    #     else:
    #         raise AttributeError

    def get_chat(self, bot_m_id) -> 'Chat':
        # TODO: Change
        return self.chats[0]

    @classmethod
    def get_user_id(cls, user: Optional[telegram.User] = None,
                    messenger_id: Optional[int] = None, **filter_args) -> Union[int, bool]:
        # TODO: Maybe change return value and add raise error
        filter_args['messenger'] = Messengers.telegram
        if messenger_id:
            filter_args['messenger_id'] = messenger_id
        if user:
            filter_args['messenger_id'] = user.id

        u = cls.check_user(**filter_args)
        return u.id if u else u

    @classmethod
    def get_support_users(cls, bot_id) -> Optional[List['User']]:
        users = s.query(cls).filter_by(bot_id=bot_id, messenger=Messengers.support).all()
        return users


def on_message_add(f):
    def dec(*args, **kwargs):
        message: 'Message' = f(*args, **kwargs)
        notify.handle_insert(message, message.chat.get_users_ids())
        return message

    return dec


class Message(Base):
    __tablename__ = 'message'
    id = Column(Integer, primary_key=True)
    messenger_id = Column(Integer)
    text = Column(String)
    time = Column(DateTime)

    chat_id = Column(Integer, ForeignKey('chat.id'), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)

    chat = relationship('Chat', back_populates='messages')
    user = relationship('User', back_populates='messages')

    @classmethod
    @on_message_add
    def add_message(cls, message: v.Message,
                    user: Optional['User'] = None,
                    chat: Optional['Chat'] = None,
                    user_id=None,
                    chat_id=None) -> Optional['Message']:

        params = {}
        if user:
            params['user'] = user
        if chat:
            params['chat'] = chat
        if chat_id:
            params['chat_id'] = chat_id
        if user_id:
            params['user_id'] = user_id
        if isinstance(message, telegram.Message):
            m = cls(messenger_id=message.message_id, text=message.text, time=message.date, **params)
        else:
            m = cls(messenger_id=message.id, text=message.text, time=message.date, **params)

        s.add(m)
        s.commit()
        return m

    def __repr__(self):
        return "<Message from user: {user_id} to chat: {chat_id}>".format(user_id=self.user_id,
                                                                          chat_id=self.chat_id)

    def to_dict(self) -> Dict:
        return {'text': self.text, 'time': self.time, 'chat_id': self.chat_id, 'user_id': self.user_id,
                'username': self.user.username}

    # @classmethod
    # def get_messages(cls, chat_id) -> List['Message']:
    #     messages = s.query(Message).filter_by(chat_id=chat_id).order_by('time').all()
    #     return messages


class Bot(Base):
    __tablename__ = 'bot'
    id = Column(Integer, primary_key=True, autoincrement=True)
    messenger_id = Column(Integer)
    messenger = Column(Enum(Messengers), nullable=False)
    chats = relationship('Chat', back_populates='bot')

    @classmethod
    def exist(cls, bot) -> bool:
        messenger = Messengers.telegram
        if s.query(cls).filter_by(messenger_id=bot.id, messenger=messenger).first():
            return True
        return False

    @classmethod
    def get_id(cls, messenger_id, messenger: Union[str, Messengers]) -> int:
        if type(messenger) == str and Messengers.check_value(messenger):
            messenger = Messengers[messenger]
        bot = s.query(cls).filter_by(messenger=messenger, messenger_id=messenger_id).first()
        return bot.id

    @classmethod
    def init_bot(cls, bot: telegram.Bot) -> Optional['Bot']:
        messenger = Messengers.telegram
        if Bot.exist(bot):
            return s.query(cls).filter_by(messenger_id=bot.id, messenger=messenger).first()
        try:
            b = cls(messenger_id=bot.id, messenger=messenger)
            s.add(b)
            s.commit()
            return b
        except Exception as e:
            logging.exception(e)
            return None

    @classmethod
    def get_all(cls) -> List['Bot']:
        return s.query(cls).all()

    @classmethod
    def get_bot(cls, bot_id) -> 'Bot':
        return s.query(cls).filter_by(id=bot_id).first()

    @classmethod
    def get_chats(cls, bot_id) -> List['Chat']:
        return cls.get_bot(bot_id).chats

    def __repr__(self):
        return "<Bot #{bot_id} in messenger {messenger}>".format(bot_id=self.id, messenger=self.messenger)


class Chat(Base, MessengerConnector):
    __tablename__ = 'chat'
    id = Column(Integer, primary_key=True, autoincrement=True)
    messenger_id = Column(Integer, nullable=False)  # id chat in messenger

    bot_id = Column(Integer, ForeignKey('bot.id'), nullable=False)

    bot = relationship('Bot', back_populates='chats')
    messages = relationship('Message', back_populates='chat', order_by=lambda: Message.time)
    users = relationship('User', secondary='usersinchat', back_populates='chats')

    def __init__(self, *args, **kwargs):
        super(Base, self).__init__(*args, **kwargs)

    @classmethod
    def create_chat(cls, user, bot_id, messenger_id):
        c = Chat(bot_id=bot_id, messenger_id=messenger_id)
        c.users.append(user)
        s.add(c)
        s.commit()

    @classmethod
    def get_id(cls, messenger_id, bot_id):
        c = s.query(cls).filter_by(messenger_id=messenger_id, bot_id=bot_id).first()
        return c.id

    @classmethod
    def get_chat(cls, chat_id=None, messenger_id=None, messenger=None) -> Optional['Chat']:
        c = None
        if messenger_id and messenger:
            c = s.query(Chat).filter_by(messenger_id=messenger_id).filter(
                Chat.bot.has(messenger=Messengers.telegram)).first()
            # c = s.query(cls).filter_by(messenger_id=messenger_id).filter(Chat.bot.messenger == messenger).first()
        elif chat_id:
            c = s.query(cls).filter_by(id=chat_id).first()
        return c or False

    def get_last_message(self) -> Optional['Message']:
        try:
            m = self.messages[-1]
            return m
        except IndexError:
            return None

    def to_dict_last(self) -> Dict:
        ''' Return chat id and last message'''
        return {'chat_id': self.id, 'messages': [self.get_last_message().to_dict() or {}]}

    def to_dict(self) -> Dict:
        ''' Return chat id and all messages'''
        return {'chat_id': self.id, 'messages': [m.to_dict() for m in self.get_all_messages()]}

    def __repr__(self):
        return "<Chat #{id}>".format(id=self.id)

    def get_all_messages(self) -> Optional[List['Message']]:
        return self.messages

    def add_message(self, msg: Message) -> 'Chat':
        self.messages.append(msg)
        s.add(self)
        s.commit()
        return self

    def get_users_ids(self):
        return [u.id for u in self.users]
