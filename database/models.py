import uuid
from typing import Optional, List, Dict, Union

import telegram
from passlib.context import CryptContext
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum, Table, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func

import utils.tg_schema as tgs
import utils.validator as v
from utils.validator import Messengers
from .base import current_session as s
from .db_utils import on_message_add

Base = declarative_base()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# TODO:
# 1. Настроить коннектор для пользователей
# 2. Сделать класс UserBase от которого наследовать User and WebUser
# 3. Настроить классы Pydantic для общения с месенджерами и вебом
# 4. Настроить доконца авторизацию
# 5. Хендлер для кастомных команд в мессенджере
# 6. Роутер для новых сообщений для распределения между несколькими людьми
# 7. Добавление новых ботов из веба
# 8.
#
#
#

class MessengerConnector:
    @classmethod
    def get_messenger_id(cls, unique_id):
        c = s.query(cls).filter_by(id=unique_id).first()
        if not c:
            c = s.query(cls).filter_by(uid=unique_id).first()
        return c.messenger_id or None


UsersInChat = Table('usersinchat', Base.metadata,
                    Column('user_id', Integer, ForeignKey('userconnector.id')),
                    Column('chat_id', Integer, ForeignKey('chat.id')))

UsersBots = Table('usersbots',
                  Base.metadata,
                  Column('user_id', Integer, ForeignKey('webusers.uid')),
                  Column('bot_id', Integer, ForeignKey('bot.id')))


def parse_user(user: tgs.TGUser, filter_args: Dict) -> Dict:
    if not user:
        return filter_args
    # if user.source == v.Source.messenger:
    #     filter_args['messenger_id'] = filter_args.get('id', user.id)
    #     filter_args['messenger'] = filter_args.get('messenger', user.messenger)
    # else:
    filter_args['id'] = user.id
    return filter_args


class UserConnector(Base, MessengerConnector):
    __tablename__ = 'userconnector'
    id = Column(Integer, autoincrement=True, primary_key=True)
    relation = Column(Enum(v.Source))
    chats = relationship('Chat', secondary='usersinchat', back_populates='userconnectors', lazy='dynamic')
    messages = relationship('Message', back_populates='userconnector')

    def __init__(self, relation):
        self.relation = relation

    def __repr__(self):
        return "<UserConnector id: {id}>".format(id=self.id)

    @property
    def user(self):
        if self.relation == v.Source.system:
            return s.query(WebUser).filter_by(uid=self.id).first()
        elif self.relation == v.Source.messenger:
            return s.query(User).filter_by(uid=self.id).first()


class WebUser(Base):
    __tablename__ = 'webusers'
    uid = Column(Integer, ForeignKey('userconnector.id'), unique=True)
    id = Column(Integer, autoincrement=True, primary_key=True)
    username = Column(String(128), unique=True, index=True)
    full_name = Column(String(128))
    hashed_password = Column(String(100))

    _bots = relationship('Bot', secondary='usersbots', backref='webuser', lazy='dynamic')
    connector = relationship("UserConnector",  # backref=backref("user", uselist=False),
                             primaryjoin="and_(UserConnector.id==WebUser.uid, "
                                         f"UserConnector.relation=='{v.Source.system.name}')")

    @property
    def chats(self):
        return self._chats.all()

    @property
    def bots(self):
        return self._bots.all()

    def contain_bot(self, bot_id):
        return self.get_bot_by_id(bot_id)

    @property
    def _chats(self):
        sq = s.query(UsersBots).where(text(f"usersbots.user_id={self.uid}")).subquery()
        return s.query(Chat).join(sq, Chat.bot_id == sq.c.bot_id)
        # return s.query(Chat).join(s.query(UsersBots).where(user_id=self.uid))

    def get_bot(self, api_token):
        return self._bots.filter_by(api_token=api_token).first()

    def get_chat(self, bot_id):
        # return s.query(Chat).join(sq, Chat.bot_id == sq.c.bot_id).all()
        return self._chats.filter_by(bot_id=bot_id).all()

    def get_chat_by_id(self, chat_id):
        return self._chats.filter(Chat.id == chat_id).first()

    def get_bot_by_id(self, bot_id):
        return self._bots.where(Bot.id == bot_id).first()

    def is_allowed(self, **obj_id):
        assert len(obj_id) == 1
        obj_name, obj_id = obj_id.popitem()  # bot_id -> bot
        obj_name = obj_name.split('_')[0]
        if obj_name == 'chat':
            return self.get_chat_by_id(obj_id)
        if obj_name == 'bot':
            return self.get_bot_by_id(obj_id)

    def __repr__(self):
        return "<WebUser uid: {uid} username: {username}>".format(uid=self.uid, username=self.username)

    def to_base(self):
        return v.WebUser.from_orm(self)

    # TODO: Check double commit
    def add_bot(self, bot: 'Bot'):
        self._bots.append(bot)
        s.commit()

    @classmethod
    def get_password_hash(cls, password):
        return pwd_context.hash(password)

    @classmethod
    def create_user(cls, user: Union[v.RegistryUser, v.UserInDB]):
        if cls.check_user(user):
            return None
        if isinstance(user, v.UserInDB):
            hashed_password = user.hashed_password
        else:
            hashed_password = cls.get_password_hash(user.password)
        new_user = cls(username=user.username, hashed_password=hashed_password, full_name=user.full_name)
        uc = UserConnector(relation=v.Source.system)
        new_user.connector = uc
        s.add_all([new_user, uc])
        s.commit()
        return new_user

    @classmethod
    def check_user(cls, user=None, **filter_args) -> Optional['WebUser']:
        if user:
            if 'username' in user.__dict__:
                filter_args['username'] = user.username
            if 'id' in user.__dict__ and user.id:
                filter_args['uid'] = user.id
        u = s.query(cls).filter_by(**filter_args).first()
        return u

    @classmethod
    def get_user(cls, user=None, **kwargs) -> Optional['WebUser']:
        u = cls.check_user(user, **kwargs)
        if u:
            return u
        else:
            if not user:
                return
            return cls.create_user(user)


class User(Base, MessengerConnector):
    __tablename__ = 'users'
    uid = Column(Integer, ForeignKey('userconnector.id'), unique=True)
    id = Column(Integer, autoincrement=True, primary_key=True)
    messenger_id = Column(Integer)  # id in messenger
    messenger = Column(Enum(Messengers))  # откуда отправили сообщение

    # TODO: Change this relation to many-to-many
    bot_id = Column(Integer, ForeignKey('bot.id'), nullable=False)
    bot = relationship('Bot', backref='users')

    connector = relationship("UserConnector",  # backref=backref("user", uselist=False),
                             primaryjoin=f"and_(UserConnector.id==User.uid, UserConnector.relation=='{v.Source.messenger.name}')")

    # TODO: Change size of string
    username = Column(String(128))
    first_name = Column(String(128))
    full_name = Column(String(128))
    language_code = Column(String(2))

    # def __init__(self, *args, **kwargs):
    #     super(Base, self).__init__(*args, **kwargs)

    @property
    def chats(self):
        return self.connector.chats.all()

    def add_chat(self, chat):
        self.connector.chats.append(chat)

    @property
    def messages(self):
        return self.connector.messages

    def __repr__(self):
        return "<User uid: {uid} username: {username}>".format(uid=self.uid, username=self.username)

    @classmethod
    def check_user(cls, user: Union[tgs.TGUser, tgs.TGUserCreate], **filter_args) -> Optional['User']:
        filter_args['messenger_id'] = user.id
        u = s.query(User).filter_by(**filter_args).first()
        return u

    @classmethod
    def create_user(cls, user: tgs.TGUserCreate) -> 'User':
        if cls.check_user(user=user):
            raise AttributeError('This user has already exist')
        # bot = Bot.get(id=user.bot_id)
        u = cls(username=user.username, first_name=user.first_name,
                language_code=user.language_code, messenger=user.messenger,
                bot=user.bot, messenger_id=user.id)
        uc = UserConnector(relation=v.Source.messenger)
        u.connector = uc

        c = Chat(bot=user.bot, messenger_id=user.chat_id)
        u.add_chat(c)

        s.add_all([u, uc, c])
        s.commit()
        return u

    @classmethod
    def get_user(cls, user: Union[tgs.TGUser, tgs.TGUserCreate]) -> 'User':
        u = cls.check_user(user)
        if u:
            return u
        else:
            return cls.create_user(user)

    #
    #     # @classmethod
    #     # def get_user(cls, user: v.User = None,
    #     #              bot: v.User = None,
    #     #              tg_user: telegram.User = None,
    #     #              messenger_id=None,
    #     #              bot_m_id=None,
    #     #              **filter_args) -> 'User':
    #     #     if user and bot:
    #     #         filter_args['messenger_id'] = user.id
    #     #         if Messengers.check_value(bot.messenger):
    #     #             filter_args['messenger'] = Messengers[bot.messenger]
    #     #         else:
    #     #             raise ValueError('This messenger is not supported')
    #     #         return cls.check_user(**filter_args) or cls.create_user(user, bot_m_id=bot.id)
    #     #
    #     #     if messenger_id:
    #     #         filter_args['messenger_id'] = messenger_id
    #     #     if filter_args:
    #     #         u = cls.check_user(**filter_args)
    #     #     else:
    #     #         u = cls.check_user(user=user)
    #     #     if u:
    #     #         return u
    #     #     elif tg_user:
    #     #         return cls.create_user(tg_user, bot_m_id)
    #     #     else:
    #     #         raise AttributeError
    #
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


class Message(Base):
    __tablename__ = 'message'
    id = Column(Integer, primary_key=True)
    messenger_id = Column(Integer)
    text = Column(String)
    time = Column(DateTime, server_default=func.now())

    chat_id = Column(Integer, ForeignKey('chat.id'), nullable=False)
    user_id = Column(Integer, ForeignKey('userconnector.id'), nullable=False)

    chat = relationship('Chat', back_populates='messages')
    userconnector = relationship('UserConnector', back_populates='messages')

    @property
    def user(self):
        return self.userconnector.user

    @classmethod
    @on_message_add
    def add_message(cls, message: Union[telegram.Message, tgs.TGMessage],
                    user: Optional['User'] = None,
                    chat: Optional['Chat'] = None,
                    user_id=None,
                    chat_id=None,
                    bot=None) -> Optional['Message']:

        params = {}
        if user:
            params['user_id'] = user.uid
        if chat:
            params['chat'] = chat
        if chat_id:
            params['chat_id'] = chat_id
        if user_id:
            params['user_id'] = user_id
        chat = Chat.get_chat(messenger_id=message.chat.id)
        if isinstance(message, tgs.TGMessage):
            tg_user = tgs.TGUserCreate(**message.from_user.dict(), chat_id=message.chat.id, bot=bot)
            user = User.get_user(tg_user)
            # chat = Chat.get_chat(messenger_id=message.chat.id)
            m = cls(messenger_id=message.message_id, text=message.text, time=message.date, chat=chat, user_id=user.uid)
        else:
            user = WebUser.get_user(user_id=user_id)
            # chat = Chat.get_chat(messenger_id=message.chat.id)
            if user not in chat.users:
                if user.contain_bot(chat.bot_id):
                    chat.add_user(user)
            m = cls(messenger_id=message.message_id, text=message.text, time=message.date, **params)

        s.add(m)
        s.commit()
        return m

    def __repr__(self):
        return "<Message from user: {user_id} to chat: {chat_id}>".format(user_id=self.user_id,
                                                                          chat_id=self.chat_id)

    def to_dict(self) -> Dict:
        return {'id': self.id, 'text': self.text, 'time': self.time, 'chat_id': self.chat_id, 'user_id': self.user_id,
                'username': self.user.username}

    def get_bot_id(self) -> int:
        return self.chat.bot_id


class Bot(Base):
    __tablename__ = 'bot'
    id = Column(Integer, primary_key=True, autoincrement=True)

    messenger = Column(Enum(Messengers), nullable=False)
    messenger_id = Column(Integer)
    messenger_name = Column(String(45))

    nickname = Column(String(45))

    token = Column(String(45))
    api_token = Column(UUID(as_uuid=True), default=uuid.uuid4(), nullable=False)

    chats = relationship('Chat', back_populates='bot')

    def __init__(self, **kwargs):
        kwargs['api_token'] = self.__table__.c.api_token.default.arg
        super(Bot, self).__init__(**kwargs)

    def commit(self):
        if not self.id:
            s.add(self)
            s.commit()
            return self

    @classmethod
    def exist(cls, bot, messenger) -> bool:
        if s.query(cls).filter_by(messenger_id=bot.id, messenger=messenger).first():
            return True
        return False

    @classmethod
    def get_id(cls, messenger_id, messenger: Union[str, Messengers]) -> int:
        if type(messenger) == str and Messengers.check_value(messenger):
            messenger = Messengers[messenger]
        bot = cls.get(messenger=messenger, messenger_id=messenger_id)
        return bot.id

    @classmethod
    def create(cls, messenger_id, token, messenger=Messengers.telegram):
        b = cls(messenger_id, token, messenger=messenger)
        s.add(b)
        s.commit()
        return b

    @classmethod
    def verify_api(cls, api_token):
        b = cls.get(api_token=api_token)
        return b

    #
    #     @classmethod
    #     def get_all(cls) -> List['Bot']:
    #         return s.query(cls).all()

    @classmethod
    def get(cls, bot_id=None, **filter_args) -> 'Bot':
        if bot_id:
            filter_args['id'] = bot_id
        return s.query(cls).filter_by(**filter_args).first()

    def __repr__(self):
        return "<Bot #{bot_id} in messenger {messenger}>".format(bot_id=self.id, messenger=self.messenger)


class Chat(Base, MessengerConnector):
    __tablename__ = 'chat'
    id = Column(Integer, primary_key=True, autoincrement=True)
    messenger_id = Column(Integer, nullable=False)  # id chat in messenger

    bot_id = Column(Integer, ForeignKey('bot.id'))

    bot = relationship('Bot', back_populates='chats')
    messages = relationship('Message', back_populates='chat', order_by=lambda: Message.time)
    userconnectors = relationship('UserConnector', secondary='usersinchat', back_populates='chats')

    @property
    def users(self):
        return [uc.user for uc in self.userconnectors]

    def add_user(self, user):
        self.userconnectors.append(user.connector)

    @property
    def user(self):
        return self.userconnectors[0].user

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

    def get_messages(self):
        return self.me

    @classmethod
    def get_chat(cls, chat_id=None, messenger_id=None) -> Optional['Chat']:
        params = {}
        if chat_id:
            params['id'] = chat_id
        if messenger_id:
            params['messenger_id'] = messenger_id
        c = s.query(Chat).filter_by(**params).first()

        return c or False

    @property
    def last_message(self):
        return self.get_last_message()

    def get_last_message(self) -> Optional['Message']:
        try:
            m = self.messages[-1]
            return m
        except IndexError:
            return None

    def to_dict_last(self) -> Dict:
        ''' Return chat id and last message'''
        return {'chat_id': self.id, 'messages': [self.last_message.to_dict() or {}]}

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
